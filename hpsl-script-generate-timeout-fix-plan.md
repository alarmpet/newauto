# HPSL 대본 생성 Timeout 오류 원인 분석 및 수정 계획

> 작성일: 2026-05-07  
> 증상: LM Studio에서 `continue_stepwise_hpsl_video_workflow()` 호출 시 `Request timed out` 발생  
> 단계: `script_generate` (2단계 — HPSL 대본 생성)

---

## 1. 오류 재현 경로

```
사용자: "비트코인 키워드로 HPSL 쇼츠 대본 만들어줘"
  └─ Gemma4: make_hpsl_flow_short_video()      → 성공 (1단계: 자료 수집)
사용자: "ok"
  └─ Gemma4: continue_stepwise_hpsl_video_workflow()
      └─ next_step == "script_generate"
          └─ _queue_hpsl_script(pid, state)    → ❌ Request timed out
```

---

## 2. 정확한 원인 — 타임아웃 구조 충돌

### 2.1 타임아웃 체인 (코드 기반)

```
LM Studio MCP client
  └─ tool call timeout: ~60초 (LM Studio 기본값)
      └─ continue_stepwise_hpsl_video_workflow()
          └─ _queue_hpsl_script()
              ├─ POST /api/projects/{pid}/source/script/generate  [timeout=30초]
              │     └─ source_draft_worker 큐 등록 즉시 반환 ✅
              └─ _poll_project(pid, timeout_sec=240)  ← ❌ 여기서 240초 블로킹 루프
                  └─ 3초마다 GET /api/projects/{pid} 폴링
```

**핵심**: `_poll_project(timeout_sec=240)`은 source_draft_worker가 HPSL 대본을 완성할 때까지 **MCP 스레드 안에서 240초 동안 동기 블로킹**한다.

LM Studio MCP client의 tool call timeout은 60~120초로 이보다 훨씬 짧다. 결과적으로:

- **LM Studio**: 60초 후 `Request timed out` 반환
- **MCP Python 프로세스**: 240초 동안 계속 폴링 실행 중
- **source_draft_worker**: 아무것도 모르고 계속 작업 중

이 상황에서 사용자가 다시 `ok`를 입력하면, Gemma4가 `continue_stepwise_hpsl_video_workflow()`를 한 번 더 호출하고, 워커가 아직 실행 중이라면 두 번째 폴링이 시작된다.

### 2.2 HPSL 1분 대본 — `target_minutes=1` 경로 분기 확인

```python
# hpsl_script.py:333-336
if target_minutes <= 1:
    payload = _fallback_payload_from_fact_notes(...)  # LLM 미사용
    model_name = f"{SCRIPT_LLM_MODEL}:deterministic-hpsl-1min"
    fallback_reason = "1-minute HPSL drafts use deterministic assembly..."
```

`target_minutes=1`이면 LLM 호출 없이 사실 노트를 조합하는 **deterministic 경로**를 쓴다. 따라서 LLM 응답 대기는 없다.

**그러나 문제는 `_poll_project(timeout_sec=240)`에 있다.** source_draft_worker가 실행될 때까지의 대기 시간, GPU guard 획득 대기, worker 초기화 시간 등이 합쳐지면 수십 초가 걸릴 수 있다. LM Studio가 이 240초 폴링 루프가 끝나기 전에 timeout한다.

### 2.3 source_draft_worker GPU guard 대기

```python
# source_draft_worker.py:66
if gpu_guard.acquire(LLM_RESOURCE, gpu_owner, timeout_sec=900):
    break
```

다른 작업이 GPU guard를 점유하고 있으면 **최대 900초** 대기한다. 이 경우 `_poll_project(timeout_sec=240)`이 240초 후 타임아웃 에러를 발생시키고, MCP가 에러를 반환한다.

---

## 3. 부차 원인 — `make_hpsl_flow_short_video` 사용

Gemma4가 `make_hpsl_flow_short_video`를 먼저 호출했다. 이 함수는:

```python
# newauto_mcp.py:1178-1194
def make_hpsl_flow_short_video(...) -> str:
    """Compatibility wrapper. ..."""
    return start_stepwise_hpsl_video_workflow(...)
```

단순 compatibility wrapper이므로 기능 자체는 동일하다. 단, `start_stepwise_hpsl_video_workflow`의 docstring에 "Do not reject user date filters; pass them through"라고 되어 있으나, Gemma4가 미래 날짜(2026-05-06 이후)에 대해 "접근 불가"로 판단한 것은 **Gemma4의 date reasoning 오류**다. MCP 코드 문제가 아니다.

---

## 4. 수정 계획

### Phase 1 (즉시 수정 필수) — `_queue_hpsl_script` 비동기화

**현재 구조 (문제)**:
```
MCP tool call (60초 제한)
  └─ _queue_hpsl_script()
      └─ _poll_project(timeout_sec=240)  ← 여기서 블로킹
```

**변경 구조**:
```
MCP tool call A: "script_generate"
  └─ 큐에 등록만 하고 즉시 반환 (≤5초)
  └─ next_step = "script_generate_wait"

MCP tool call B: "script_generate_wait" (사용자가 "진행" 입력 후)
  └─ 대본 완성 여부만 확인
  └─ 완성 → next_step = "flow_prompts"
  └─ 미완성 → "아직 생성 중이야. 잠시 후 다시 진행이라고 말해줘." 반환
```

**수정 코드 (`newauto_mcp.py`)**:

```python
# _queue_hpsl_script를 분리:

def _enqueue_hpsl_script(pid: str, state: dict[str, object]) -> None:
    """source_draft_worker에 큐잉만 하고 즉시 반환."""
    _ensure_source_draft_worker()
    _json_request(
        "POST",
        f"/api/projects/{pid}/source/script/generate",
        form={
            "tone": str(state.get("tone") or "설명형"),
            "target_minutes": str(max(1, min(8, _object_to_int(state.get("target_minutes"), 1)))),
            "language": "ko",
            "mode": "",
            "note": "HPSL은 훅-포인트-스토리-교훈 구조다. 이 4단계를 지키고, 각 문장이 Flow 장면 하나가 되게 작성해.",
            "script_structure": "hpsl",
        },
        timeout=30,
    )


def _check_hpsl_script_done(pid: str) -> dict[str, object]:
    """source_draft_state가 done이면 project 반환, 아니면 None."""
    project = _json_request("GET", f"/api/projects/{pid}", timeout=15)
    state = str(project.get("source_draft_state") or "")
    if state == "done":
        return project
    if state == "error":
        raise NewautoError(str(project.get("source_draft_error") or "source draft generation failed"))
    return {}  # 아직 생성 중


# continue_stepwise_hpsl_video_workflow에서:

if next_step == "script_generate":
    _enqueue_hpsl_script(pid, state)  # 큐잉만, 블로킹 없음
    _set_next_step(state, "script_generate_wait")
    return (
        "2단계 시작: HPSL 대본 생성을 큐에 등록했어.\n\n"
        f"- project_id: {pid}\n"
        f"- newauto: {_project_url(pid, step=1)}\n\n"
        "대본 생성에 30~120초가 걸려. 잠시 후 `진행`이라고 말하면 완성 여부를 확인할게."
    )

if next_step == "script_generate_wait":
    project = _check_hpsl_script_done(pid)
    if not project:
        project_peek = _json_request("GET", f"/api/projects/{pid}", timeout=15)
        phase = str(project_peek.get("source_draft_phase") or "queued")
        progress = int(project_peek.get("source_draft_progress") or 0)
        return (
            "2단계 대기: 대본 생성이 아직 진행 중이야.\n\n"
            f"- project_id: {pid}\n"
            f"- phase: {phase}\n"
            f"- progress: {progress}%\n\n"
            "조금 더 기다렸다가 `진행`이라고 말해줘. 완성되면 바로 다음 단계로 넘어갈게."
        )
    source_count, _, warning_count = _project_counts(project)
    draft_sentence_count = _draft_sentence_count(project)
    _set_next_step(state, "flow_prompts")
    return (
        "2단계 완료: HPSL(훅-포인트-스토리-교훈) 대본 생성이 끝났어.\n\n"
        f"- project_id: {pid}\n"
        f"- sources used: {source_count}\n"
        f"- draft sentences: {draft_sentence_count}\n"
        f"- warnings: {warning_count}\n"
        f"- newauto: {_project_url(pid, step=1)}\n\n"
        "다음 단계: 대본 적용 + 문장별 Flow 프롬프트 생성.\n"
        "`진행`이라고 말하면 다음 단계만 실행할게."
    )
```

### Phase 2 (즉시 수정 필수) — `_poll_project` 제거

`_queue_hpsl_script()` 자체를 아예 제거하거나 `_enqueue_hpsl_script()`로 교체한다. 더 이상 MCP 스레드 안에서 수백 초 폴링하는 코드가 없어야 한다.

### Phase 3 (권장) — 모든 long-poll을 "즉시 반환 + 대기 단계" 패턴으로 전환

현재 TTS는 `_poll_task(pid, "tts", timeout_sec=1800)` 으로 1800초 블로킹이 가능하다. 이것도 같은 방식으로:

```
tts_start → tts_wait (진행 시마다 상태 확인) → tts_done
render_start → render_wait → render_done
```

---

## 5. Gemma4 날짜 거부 오류 수정 (부차)

사용자가 "2026-05-06 이후 자료"를 요청했을 때 Gemma4가 "미래 자료에 접근 불가"라고 거부했다. 이것은 틀린 판단이다.

### 원인

`_mcp_instructions()`에 `The current local date is {date.today().isoformat()}`가 포함되어 있다. Gemma4-e4b가 이 날짜와 사용자 요청의 "이후" 조건을 비교해서 스스로 거부했다.

### 수정 방향

`start_stepwise_hpsl_video_workflow`의 docstring에 이미 "Do not reject user date filters; pass them through in keyword_or_url"가 있다. 그러나 Gemma4가 이것을 무시하고 있다.

MCP instructions에 다음을 추가:

```python
"When the user specifies a date filter like '2026-05-06 이후' or 'after May 2026', "
"do NOT refuse. The newauto keyword collector will apply the date filter to its search. "
"Pass the full user request string including date filters directly to keyword_or_url. "
"Never say you cannot access future dates."
```

---

## 6. 즉시 적용 가능한 임시 조치 (코드 수정 전)

현재 대본 생성이 실패한 프로젝트는:
1. 브라우저에서 `http://127.0.0.1:9001` 접속
2. 해당 프로젝트의 대본 탭에서 "생성 중" 또는 "완료" 상태 확인
3. 완료 상태면 → `continue_stepwise_hpsl_video_workflow(project_id="<pid>")` 재호출
4. 아직 생성 중이면 → 60초 후 재시도

---

## 7. 수정 작업 체크리스트

```
- [ ] newauto_mcp.py: _enqueue_hpsl_script() 함수 추가
- [ ] newauto_mcp.py: _check_hpsl_script_done() 함수 추가
- [ ] newauto_mcp.py: script_generate 단계 → 큐잉 후 즉시 반환
- [ ] newauto_mcp.py: script_generate_wait 단계 추가
- [ ] newauto_mcp.py: _queue_hpsl_script() 제거 또는 deprecated 처리
- [ ] newauto_mcp.py: _mcp_instructions()에 날짜 필터 거부 금지 지시 추가
- [ ] 선택: tts, render 단계도 같은 패턴으로 분리
- [ ] 테스트: "비트코인 2026-05-06 이후" 키워드로 1단계~2단계 왕복 확인
```

---

## 8. 테스트 기준

| 번호 | 기준 | 확인 방법 |
|------|------|---------|
| 1 | `script_generate` 단계의 MCP tool call이 30초 이내 반환 | LM Studio 응답 시간 확인 |
| 2 | "2026-05-06 이후" 날짜 포함 요청을 Gemma4가 거부하지 않음 | 직접 요청 테스트 |
| 3 | `script_generate_wait` 단계에서 미완성 시 안내 후 재시도 가능 | 연속 `진행` 2회 테스트 |
| 4 | 대본 완성 후 `flow_prompts` 단계로 올바르게 전환 | stepwise state 파일 확인 |
| 5 | TTS 단계도 timeout 없이 반환 | 1분 이내 반환 확인 |

---

## 2026-05-07 코드베이스 검토 반영 및 구현 상태

### 검토 결과

- 현재 `scripts/newauto_mcp.py`의 `script_generate` 단계가 계획서 진단처럼 `_poll_project(pid, timeout_sec=240)`에 의존하고 있었다.
- 1분 HPSL 대본 자체는 `app/services/hpsl_script.py`에서 deterministic 경로를 타므로 Gemma4 JSON 생성 지연이 주원인이 아니다.
- 실제 timeout 원인은 MCP tool call 안에서 worker 완료를 기다리는 동기식 polling 구조다.
- `research.md`와 `timeline.md` 기준으로 Flow 쪽은 이미 `flow_generate` / `flow_wait_sentence`로 분리되어 있으므로, 이번 수정은 같은 패턴을 HPSL 대본 생성 단계에 적용하는 것이 맞다.
- TTS/render도 `_start_tts_and_wait`, `_render_and_wait`에 긴 polling이 남아 있지만 이번 사용자 오류의 직접 지점은 `script_generate`다. 다음 계획에서 동일한 wait 단계 분리를 적용한다.

### 반영된 개선사항

- [x] `newauto_mcp.py`: `_enqueue_hpsl_script()` 추가
- [x] `newauto_mcp.py`: `_check_hpsl_script_done()` 추가
- [x] `newauto_mcp.py`: `script_generate` 단계가 큐 등록 후 즉시 반환하도록 변경
- [x] `newauto_mcp.py`: `script_generate_wait` 단계 추가
- [x] `newauto_mcp.py`: stepwise 경로에서 `_queue_hpsl_script()` 제거
- [x] `newauto_mcp.py`: 날짜 필터를 채팅에서 거절하지 말고 workflow tool로 넘기라는 MCP instruction 강화
- [ ] 후속 작업: TTS/render 단계도 `tts_start`/`tts_wait`, `render_start`/`render_wait`로 분리

### 업데이트된 워크플로우

```text
사용자: 진행
  -> next_step=script_generate
  -> /source/script/generate 큐 등록
  -> next_step=script_generate_wait
  -> 즉시 응답

사용자: 진행
  -> next_step=script_generate_wait
  -> /api/projects/{pid} 상태 확인
  -> done + draft 있음: next_step=flow_prompts
  -> queued/running: 대기 안내 후 같은 단계 유지
  -> error: worker 오류와 복구 안내 반환
```

### 완료 기준 업데이트

- `script_generate` MCP tool call은 worker 완료를 기다리지 않는다.
- 아직 생성 중인 경우 LM Studio에는 오류가 아니라 `source_draft_state`, `source_draft_phase`, `source_draft_error`가 표시된다.
- 사용자는 같은 방식으로 `진행`만 다시 입력하면 완료 여부를 확인할 수 있다.

---

## 2026-05-07 ASCII Implementation Update

### Codebase Review

- `scripts/newauto_mcp.py` still blocked inside `_poll_project(pid, timeout_sec=240)` during `script_generate`.
- The 1-minute HPSL draft path in `app/services/hpsl_script.py` is deterministic, so the main failure is not Gemma4 JSON generation.
- The real MCP timeout cause is synchronous polling inside one LM Studio tool call.
- Flow already uses a split pattern (`flow_generate` then `flow_wait_sentence`), so HPSL script generation now uses the same pattern.
- TTS/render still have long waits and remain the next follow-up split.

### Completed Checklist

- [x] Added `_enqueue_hpsl_script()`.
- [x] Added `_check_hpsl_script_done()`.
- [x] Changed `script_generate` to enqueue and return quickly.
- [x] Added `script_generate_wait`.
- [x] Removed `_queue_hpsl_script()` from the stepwise path.
- [x] Strengthened MCP instructions so `2026-05-06 이후` is passed to the workflow tool on 2026-05-07 instead of being refused in chat.
- [ ] Follow-up: split TTS/render into start/wait stages.

### New State Machine

```text
continue_stepwise_hpsl_video_workflow
  script_generate
    -> POST /api/projects/{pid}/source/script/generate
    -> set next_step=script_generate_wait
    -> return immediately

  script_generate_wait
    -> GET /api/projects/{pid}
    -> if done and draft exists: set next_step=flow_prompts
    -> if queued/running: return current status and keep same step
    -> if error: return worker error and keep recovery guidance
```

---

## 2026-05-07 TTS/Render Wait Split Completion

### Additional Completed Checklist

- [x] Removed long `_poll_task()` waiting from the LM Studio MCP stepwise path.
- [x] Added `_task_status()` and `_check_task_done()` for one-shot status checks.
- [x] Added `_enqueue_tts()` and changed `tts` to enqueue quickly.
- [x] Added `tts_wait` to report TTS progress or advance to render.
- [x] Added `_enqueue_render()` and changed `render` to enqueue quickly after preflight.
- [x] Added `render_wait` to report render progress or finish the workflow.
- [x] Changed `continue_after_flow_assets()` so it resumes the stepwise workflow instead of waiting through TTS and render in one tool call.

### Updated End-State Flow

```text
tts
  -> queue OmniVoice TTS
  -> next_step=tts_wait
  -> return immediately

tts_wait
  -> check /status once
  -> done: next_step=render
  -> queued/running: return progress and keep same step

render
  -> build scene/render plans
  -> run preflight
  -> queue render
  -> next_step=render_wait
  -> return immediately

render_wait
  -> check /status once
  -> done: next_step=done
  -> queued/running: return progress and keep same step
```
