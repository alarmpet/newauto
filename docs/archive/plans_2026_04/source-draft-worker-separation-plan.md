# Source Draft Worker Separation Plan (Revised)

상태: `[In Progress]`

- `[완료]` worker-ready 상태 필드 추가: phase/log/job/timestamps/options
- `[완료]` status route에 source draft 상태 필드 노출
- `[완료]` 서버 재시작 시 queued/running source draft 복구 정리
- `[완료]` 실제 worker 프로세스 분리와 queue claim/heartbeat 연결
- `[완료]` generate route enqueue 전환
- `[남음]` source draft stale watchdog 세부 UI 고도화

## 목표

현재 Source Assist 의 초안 생성은 [app/routers/projects.py:395-437](app/routers/projects.py) `generate_source_script` 가 요청-응답 경로에서 **동기** 실행한다. 이를 별도 worker 기반 비동기 처리로 분리해서:

- 60–300초 LLM cold start 동안 브라우저가 멈춘 것처럼 보이지 않게
- Ollama warm/generate/unload 흐름을 worker 안에서 일관되게 관리
- Regenerate (mode 분기), keyword research, batch 생성도 같은 worker 경로 재사용

## 코드 검증 — 이미 갖춰진 자산

[render-performance-and-worker-separation-plan.md](render-performance-and-worker-separation-plan.md) 가 만든 패턴을 그대로 따라가면 됨:

- [app/workers/render_worker.py](app/workers/render_worker.py) 47줄 — polling, single-instance lock, heartbeat thread, claim helper 호출 패턴
- [app/workers/worker_lock.py](app/workers/worker_lock.py) — file-lock 기반 단일 인스턴스 보장
- [app/db.py](app/db.py) `claim_next_queued_render`, `touch_render_heartbeat`, `recover_interrupted_tasks`, render watchdog 컬럼 (`render_job_id`, `render_started_at`, `render_heartbeat_at`)
- [app/main.py](app/main.py) startup 에서 `subprocess.Popen` detached 로 worker spawn
- `NEWAUTO_DISABLE_BACKGROUND_WORKERS=1` 환경변수로 테스트 시 worker 끄는 패턴
- WAL 모드 SQLite (worker + server 동시 쓰기 안전)

→ **본 plan 은 같은 패턴을 source draft 용으로 평행 복제**. 새 패턴 만들지 않음.

## 현재 sync 호출의 문제

[projects.py:395-437](app/routers/projects.py) `generate_source_script` 흐름:

```python
db.update_project(pid, source_draft_state="running", ...)
generated = generate_script_draft(...)      # ← 여기서 60–300초 블로킹
db.update_project(pid, source_draft_state="done", ...)
```

문제:

- HTTP 요청이 60–300초 묶임 → 브라우저 timeout 가능 (보통 ~5분)
- Uvicorn worker 1개라면 다른 요청이 대기 (다른 프로젝트 status 폴링 포함)
- 사용자가 새로고침하면 작업이 어디서 끊긴지 추적 불가
- `--reload` 로 코드 수정 시 in-flight 생성이 SIGINT 받음

## VRAM/모델 격리 정책

source draft worker 의 핵심 책임은 **Ollama 를 제어된 시점에 warm/unload**:

```
worker process:
  start → claim queued job
       → set running + heartbeat thread on
       → OllamaClient.warm()       # cold 60–300s 가능
       → generate (streaming)
       → safety check (CPU only)
       → OllamaClient.unload()     # ★ TTS/render 가 GPU 사용 가능
       → set done/error + heartbeat off
       → poll next
```

server process 의 TTS BG task 는 별도 process 의 worker 에서 unload 가 끝났음을 직접 알 수 없음. 두 가지 옵션:

A) **worker 가 종료 직전 DB 에 `gpu_busy=False` 같은 플래그** → server 는 TTS 시작 전 확인
B) **TTS 자체가 OmniVoice 모델 로드 시 Ollama unload 신호 송신** → 단순. `OllamaClient.unload()` 는 idempotent (이미 unloaded 이면 no-op)

권장: B. 모든 GPU-heavy 작업의 시작점에서 다른 모델 unload 호출 → state 추적 부담 없음. 본 plan 에서는 worker 측만 보장하고 TTS 측 호출은 별도 plan 에서.

## 데이터 모델 추가

```python
# app/db.py SCHEMA + MIGRATION_COLUMNS
source_draft_job_id        TEXT NOT NULL DEFAULT '',
source_draft_started_at    TEXT NOT NULL DEFAULT '',
source_draft_heartbeat_at  TEXT NOT NULL DEFAULT '',
source_draft_phase         TEXT NOT NULL DEFAULT '',  -- prepare/warm_model/generate/safety_check
source_draft_last_log      TEXT NOT NULL DEFAULT '',
```

`source_draft_state` Literal 확장:
```python
SourceDraftState = Literal["idle", "queued", "running", "done", "error"]  # 'queued' 추가
```

ProjectStatus 폴링 subset 에 추가:
- `source_draft_state`, `source_draft_progress`, `source_draft_phase`, `source_draft_last_log`
- `source_draft_started_at`, `source_draft_heartbeat_at` 는 server 측 표시용으로만 추가 (UI 의 "marker since 28s ago" 표시)

## DB Helper 추가

[render-worker.py:39](app/workers/render_worker.py) 의 `db.claim_next_queued_render()` 평행 복제:

```python
# app/db.py
def claim_next_queued_source_draft() -> str | None:
    """source_draft_state='queued' 행 1개를 'running' 으로 atomic claim."""
    job_id = uuid.uuid4().hex
    now = _now()
    with tx() as conn:
        row = conn.execute(
            "SELECT id FROM projects WHERE source_draft_state='queued' "
            "ORDER BY updated_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        pid = str(row["id"])
        conn.execute(
            "UPDATE projects SET source_draft_state='running', "
            "source_draft_job_id=?, source_draft_started_at=?, source_draft_heartbeat_at=?, "
            "updated_at=? WHERE id=? AND source_draft_state='queued'",
            (job_id, now, now, now, pid),
        )
        return pid


def touch_source_draft_heartbeat(pid: str) -> None:
    with tx() as conn:
        conn.execute(
            "UPDATE projects SET source_draft_heartbeat_at=? WHERE id=?",
            (_now(), pid),
        )
```

`recover_interrupted_tasks()` 보강 — 이미 render 처리 부분이 있으므로 비슷한 블록 추가:

```python
# app/db.py recover_interrupted_tasks 안
source_count = conn.execute(
    """
    UPDATE projects SET
        source_draft_state='error',
        source_draft_progress=0,
        source_draft_error=?,
        source_draft_phase='',
        source_draft_last_log='',
        updated_at=?
    WHERE source_draft_state IN ('queued', 'running')
    """,
    ("이전 작업이 서버 재시작으로 중단되었습니다.", _now()),
).rowcount
return {..., "source_draft": source_count}
```

→ 기존 sync 호출에서 잔존하는 `running` 행도 함께 정리됨.

## Worker 구현

```python
# app/workers/source_draft_worker.py
import sys, threading, time, uuid
from contextlib import suppress
from pathlib import Path

from .. import db
from ..services.source_draft import generate_script_draft
from ..services.script_safety import copy_risk_score, detect_long_quotes
from .worker_lock import single_instance_lock

POLL_INTERVAL_SEC = 3.0
HEARTBEAT_INTERVAL_SEC = 10.0
WORKER_LOCK_PATH = Path("storage/source_draft_worker.lock")


def _set_phase(pid: str, phase: str, *, progress: int | None = None, log: str = "") -> None:
    fields: dict[str, object] = {"source_draft_phase": phase}
    if progress is not None:
        fields["source_draft_progress"] = progress
    if log:
        fields["source_draft_last_log"] = log
    db.update_project(pid, **fields)


def _run_job_with_heartbeat(pid: str) -> None:
    project = db.get_project(pid)
    if project is None:
        return

    stop_event = threading.Event()

    def heartbeat() -> None:
        # ★ LLM warm 동안 60–300s 무출력 → heartbeat 끊기면 watchdog 가 죽임
        # 별도 thread 가 10s 마다 무조건 갱신
        while not stop_event.wait(HEARTBEAT_INTERVAL_SEC):
            with suppress(Exception):
                db.touch_source_draft_heartbeat(pid)

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()

    try:
        # phase 별 진행률 — UI 의 "모델 준비 중" 표시 근거
        _set_phase(pid, "prepare", progress=10)
        # request 시 저장된 옵션 읽기
        tone = (project.get("source_draft_tone") or "").strip() or "설명형"
        target = max(1, min(int(project.get("source_draft_target_minutes") or 3), 8))
        language = (project.get("source_draft_language") or "ko").strip() or "ko"
        mode = project.get("source_draft_regenerate_mode") or ""
        note = project.get("source_draft_regenerate_note") or ""

        _set_phase(pid, "warm_model", progress=20)
        # generate_script_draft 가 내부에서 warm/generate/unload 모두 처리
        # → phase 전환은 "warm_model" 동안 한 덩어리로 표시 (Ollama warm 시 외부 신호 없음)
        _set_phase(pid, "generate", progress=40)
        generated = generate_script_draft(
            project, tone=tone, target_minutes=target, language=language,
            mode=mode, note=note,
        )

        _set_phase(pid, "safety_check", progress=85)
        db.update_project(
            pid,
            source_draft_state="done",
            source_draft_progress=100,
            source_draft_error="",
            source_draft_script=generated.script,
            source_draft_warnings=generated.warnings,
            source_draft_model=generated.model,
            source_draft_risk_score=generated.risk_score,
            source_draft_previous_script=generated.previous_script,
            source_draft_phase="done",
            source_draft_last_log="",
        )
    except Exception as exc:
        db.update_project(
            pid,
            source_draft_state="error",
            source_draft_error=str(exc),
            source_draft_phase="",
            source_draft_last_log=str(exc)[:500],
        )
    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=1.0)


def main() -> int:
    db.init_db()
    with single_instance_lock(WORKER_LOCK_PATH) as acquired:
        if not acquired:
            return 0
        while True:
            pid = db.claim_next_queued_source_draft()
            if pid is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            _run_job_with_heartbeat(pid)


if __name__ == "__main__":
    raise SystemExit(main())
```

핵심 포인트:

1. **Heartbeat thread 별도** — `OllamaClient.warm()` 가 60–300s 블로킹이라 main thread 가 갱신 못 함. 반드시 별도 thread.
2. **Phase 표시는 추정** — Ollama warm 진행률은 외부에서 알 수 없으므로 "warm_model" → "generate" 전환은 시간 기반 추정 (UI 가 "모델 준비 중" 안내 표시)
3. **이미 source_draft.py 가 warm/unload 보장** — worker 는 그 함수를 그대로 호출

`source_draft_tone`, `source_draft_target_minutes`, `source_draft_language` 컬럼 추가 필요 (request 시 저장 → worker 가 읽음). 또는 별도 `source_draft_options TEXT (JSON)` 1개 컬럼으로 묶어도 무방.

권장: **`source_draft_options TEXT NOT NULL DEFAULT '{}'`** 1개 컬럼 + JSON 직렬화 (sentences/media_order 처럼). 향후 옵션 추가도 쉬움.

## API 변경

### `/source/script/generate` (그리고 regenerate 같은 엔드포인트)

**현재**: sync 호출, 60-300s 블로킹, 끝나면 ProjectRecord 반환
**변경 후**: enqueue 후 즉시 반환

```python
@router.post("/{pid}/source/script/generate")
def generate_source_script(
    pid: str,
    tone: str = Form("설명형"),
    target_minutes: int = Form(3),
    language: str = Form("ko"),
    mode: str = Form(""),
    note: str = Form(""),
) -> ProjectRecord:
    project = _require(pid)
    if project["source_draft_state"] in ("queued", "running"):
        raise HTTPException(409, "이미 다른 생성 작업이 진행 중입니다.")
    if not project["source_draft_sources"]:
        raise HTTPException(400, "먼저 기사 URL 을 분석해 주세요.")

    options = {
        "tone": tone.strip() or "설명형",
        "target_minutes": max(1, min(target_minutes, 8)),
        "language": language.strip() or "ko",
    }
    updated = db.update_project(
        pid,
        source_draft_state="queued",
        source_draft_progress=0,
        source_draft_error="",
        source_draft_phase="queued",
        source_draft_last_log="",
        source_draft_model=SCRIPT_LLM_MODEL,
        source_draft_options=options,
        source_draft_regenerate_mode=mode if mode in ("", "hook", "point", "story", "lesson") else "",
        source_draft_regenerate_note=note.strip()[:200],
    )
    return updated  # state="queued" 로 즉시 반환 — UI 가 폴링 시작
```

`/regenerate` 별도 엔드포인트는 만들지 않음. mode 인자로 통합 — [source-regenerate-guidance-plan.md](source-regenerate-guidance-plan.md) 의 결정과 일치.

### Status 응답에 source_draft 필드 노출

[render router status](app/routers/render.py) 의 ProjectStatus 응답에 추가:

```python
"source_draft_state": project["source_draft_state"],
"source_draft_progress": project["source_draft_progress"],
"source_draft_phase": project["source_draft_phase"],
"source_draft_last_log": project["source_draft_last_log"],
"source_draft_started_at": project["source_draft_started_at"],
"source_draft_heartbeat_at": project["source_draft_heartbeat_at"],
"source_draft_error": project["source_draft_error"],
```

## Watchdog

render 가 사용하는 [recover_interrupted_tasks()](app/db.py) 는 startup 시 1회 실행. **실행 중 stale 감지** 가 필요하면 별도 watchdog (위 §"Helper" 의 stale-detection 블록을 startup 30s 주기 task 로). render 와 같은 watchdog thread 안에 source_draft 도 묶음.

```python
# app/services/watchdog.py (가칭, render 와 통합)
HEARTBEAT_TIMEOUT_SEC = 60
MAX_DRAFT_DURATION_SEC = 600  # 10 minutes

def sweep_stale_source_drafts() -> None:
    cutoff_hb = ...
    cutoff_start = ...
    with db.tx() as conn:
        conn.execute("""
            UPDATE projects SET source_draft_state='error',
              source_draft_error='Worker heartbeat lost or duration exceeded.',
              source_draft_phase='', source_draft_last_log=''
            WHERE source_draft_state='running'
              AND (source_draft_heartbeat_at < ? OR source_draft_started_at < ?)
        """, (cutoff_hb, cutoff_start))
```

## 동시성 정책

- worker 단일 인스턴스 (file-lock)
- 동시 1개 작업만 처리
- 이유: gemma4:e4b VRAM 점유 + TTS/render 와 경합 방지 + 상태 단순

향후 멀티 프로젝트 동시 generate 가 필요하면 worker 개수 늘리지 말고 **batch queue + 순차 처리** 권장.

## UI 변경

Step 1 Source Assist:

```
[ Generate Script Draft ]   ← 클릭 시 즉시 disable + state="queued" 표시

상태 영역:
  ⏳ 대기 중                    (queued)
  ⏳ 모델 준비 중 (15s 경과)    (warm_model — 시간 기반 표시)
  ⏳ 초안 생성 중               (generate)
  ⏳ 복사 위험 검사 중          (safety_check)
  ✓ 완료 / ✗ 실패: <메시지>
```

폴링은 기존 1.5s `pollProjectStatus` 에 `source_draft_*` 필드 추가만으로 처리.

heartbeat 표시 (선택): `started_at` 과 `heartbeat_at` 차이로 "마지막 신호 N초 전" 표시 → 사용자가 stuck 인지 판단 가능.

## Test 환경

```python
# 테스트에서 worker 자동 spawn 차단
os.environ["NEWAUTO_DISABLE_BACKGROUND_WORKERS"] = "1"
```

→ render 와 동일 패턴. `app/main.py` startup 에서 이 env 가 truthy 이면 source_draft worker spawn 도 skip.

## 구현 단계

### Phase 1. DB + 서비스 + Worker 골격 `[Pending]` (P0)

- 신규 컬럼 + migration + recover_interrupted_tasks 보강
- `claim_next_queued_source_draft`, `touch_source_draft_heartbeat`
- `app/workers/source_draft_worker.py`
- `app/main.py` startup 에 worker spawn (NEWAUTO_DISABLE_BACKGROUND_WORKERS 가드)
- 회귀 테스트 (claim/heartbeat/recover)

### Phase 2. Generate route enqueue 전환 + UI 폴링 `[Pending]` (P0)

- `/generate` 가 즉시 `state="queued"` 반환
- Status 응답에 `source_draft_*` 필드 추가
- Step 1 UI 가 폴링 + phase 별 안내문 표시
- 회귀 테스트 (route enqueue, status reflect, mode 인자 그대로 worker 까지 전달)

### Phase 3. Watchdog + heartbeat 표시 `[Pending]` (P1)

- 30s 주기 sweep_stale_source_drafts
- UI 의 "마지막 신호 N초 전" 보조 표시
- 회귀 테스트 (heartbeat timeout 시 error 전이)

### Phase 4. Regenerate 도 worker 경로 흡수 `[Pending]` (P1)

- [source-regenerate-guidance-plan.md](source-regenerate-guidance-plan.md) 의 mode 인자가 이미 `/generate` 에 통합되어 있으므로 worker 가 그대로 받음 — 별도 코드 거의 없음
- previous_script 보존이 worker 안에서도 동작하는지 회귀 검증

### Phase 5. (옵션) Keyword research 도 worker 흡수 `[Pending]` (P2)

- 현재 `/source/keyword/collect` 는 [projects.py:324-392](app/routers/projects.py) 에서 sync — 5개 URL fetch 합산하면 30–60s 가능
- worker 분리하면 generate 와 동일한 UX 통일
- 다만 LLM 미사용이라 VRAM 부담 0 → 우선순위 낮음

## 위험과 대응

| 위험 | 대응 |
|---|---|
| LLM warm 60–300s 동안 heartbeat 끊김 | 별도 thread 로 10s 갱신 (Phase 1 핵심) |
| 기존 `running` 행이 sync 호출 잔존분일 수 있음 | `recover_interrupted_tasks` 가 startup 시 정리 |
| worker 가 SIGKILL 당하면 stale 발생 | watchdog (Phase 3) 가 60s heartbeat 후 error 전이 |
| TTS 와 GPU 경합 | worker 가 unload 보장 — 이미 source_draft.py 의 finally 에 호출 |
| concurrency 두 번 클릭 | DB-level guard (queued/running → 409) + claim 의 atomic UPDATE |
| `NEWAUTO_DISABLE_BACKGROUND_WORKERS` 누락으로 테스트가 실제 Ollama 호출 | startup 가드 + CI 환경에서 강제 set |

## 회귀 테스트

```python
# tests/test_source_worker.py
def test_claim_next_queued_returns_one_and_marks_running():
def test_claim_returns_none_when_no_queued():
def test_heartbeat_thread_updates_db_during_long_warm(monkeypatch):
    """가짜 generate_script_draft 가 5초 sleep — 그동안 heartbeat 갱신 검증."""
def test_unload_called_in_finally_even_on_exception(monkeypatch):

# tests/test_db_recovery.py
def test_recover_marks_queued_and_running_source_drafts_as_error():
def test_recovery_includes_source_draft_in_count_dict():

# tests/test_feature_workflow.py
def test_generate_endpoint_returns_queued_immediately():
def test_status_response_contains_source_draft_phase():
def test_concurrent_generate_returns_409():

# tests/test_watchdog.py (Phase 3)
def test_sweep_marks_stale_source_drafts_as_error():
def test_max_duration_kills_long_running_draft():
```

## 완료 기준

- 사용자 클릭 ~50ms 안에 `state="queued"` 응답 (LLM cold 와 무관)
- Step 1 UI 가 phase 변화 + heartbeat 갱신을 1.5s 주기로 표시
- 서버 재시작 후 `running`/`queued` 가 모두 `error` 로 정리됨
- worker SIGKILL 시 60s 이내 watchdog 이 error 로 전이
- regenerate (mode 인자) 가 같은 worker 경로로 처리됨 (Phase 4)
- 기존 sync 호출 대비 같은 결과를 동일 테스트가 통과
