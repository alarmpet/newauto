# Source Regenerate Guidance Plan (Revised)

상태: `[In Progress]`

- `[완료]` regenerate mode 데이터 모델 추가
- `[완료]` `/source/script/generate` mode/note 확장
- `[완료]` previous script 백업/복원 API 추가
- `[완료]` Step 1 mode 선택, 추가 지시, 복원 버튼, mode badge 연결
- `[남음]` side-by-side 비교 보기

## 목표

Source Assist 의 `Regenerate` 기능에 단순 재생성만 넣지 않고, 사용자가 초안의 방향을 빠르게 바꿀 수 있도록 **구조형 재생성 모드**를 추가한다.

핵심 모드 (Korean label / id 통일):

| Korean label | id (Literal) | 용도 |
|---|---|---|
| 훅 | `hook` | 첫 2~4문장 강한 도입 |
| 포인트 | `point` | 핵심 사실 우선 |
| 스토리 | `story` | 사건 흐름 재구성 |
| 교훈 | `lesson` | 시사점/배움 추출 |

이 모드는 **기사/리서치 원문을 다시 수집하지 않고**, 기존 `source_draft_sources` + `source_draft_fact_notes` 를 재사용해서 새 초안을 만든다.

## 코드 검증 (현재 상태)

이미 갖춰진 부분:

- [app/services/source_draft.py](app/services/source_draft.py) `generate_script_draft(project, *, tone, target_minutes, language)` — Ollama warm/generate/unload 순서, `copy_risk_score` + `detect_long_quotes` 안전 검사 호출
- [app/routers/projects.py:395-437](app/routers/projects.py) `POST /source/script/generate` (현재 **sync 호출**)
- [app/routers/projects.py:440-461](app/routers/projects.py) `POST /source/script/apply` — `compile_script("standard", ...)` 후 `user_script/compiled_script/regional_sentences/sentences` + legacy `script` 동시 갱신
- [app/db.py:51-129](app/db.py) `source_draft_*` 11개 컬럼

`source_draft_fact_notes` 의 실제 구조 ([source_draft.py:28](app/services/source_draft.py#L28)):

```python
fact_notes = [item["note"] for item in project["source_draft_fact_notes"] if item.get("note")]
```

→ list of `{"note": str, ...}` dict. 본 plan 의 prompt 도 같은 구조로 접근.

부족한 부분:

- regenerate mode 분기 없음 — `_build_prompt()` 가 단일 템플릿
- 이전 초안 보존 없음 — Apply 직전 비교 불가
- 모드별 안전성 임계값 차등 없음
- 동시 클릭 race condition (현재 generate route 가 concurrency guard 없음)

## 데이터 모델 변경

```python
# app/types.py
SourceRegenerateMode = Literal["", "hook", "point", "story", "lesson"]

# DB 컬럼 (SCHEMA + MIGRATION_COLUMNS 양쪽)
source_draft_regenerate_mode  TEXT NOT NULL DEFAULT '',
source_draft_regenerate_note  TEXT NOT NULL DEFAULT '',
source_draft_previous_script  TEXT NOT NULL DEFAULT '',  -- 직전 초안 백업 (필수, 선택 아님)
```

`source_draft_previous_script` 가 **"선택" 이 아닌 필수** 인 이유:
- 비교 UX (이전 vs 현재) 가 regenerate 의 핵심
- Apply 직전 사용자가 "원래가 더 나았다" 판단 시 즉시 복원 가능
- 비용은 TEXT 1개 — 무시 가능

ProjectStatus 폴링 subset 에는 `source_draft_regenerate_mode` 만 추가 (UI badge 용). previous_script 는 GET /source/draft 로 조회.

## 서비스 변경

### `generate_script_draft()` 시그니처 확장

```python
# app/services/source_draft.py
@dataclass(frozen=True)
class GeneratedSourceDraft:
    script: str
    warnings: list[str]
    model: str
    risk_score: float
    mode: SourceRegenerateMode   # 신규
    previous_script: str         # 신규 — 호출 직전 script 보존본


def generate_script_draft(
    project: ProjectRecord,
    *,
    tone: str,
    target_minutes: int,
    language: str = "ko",
    mode: SourceRegenerateMode = "",   # 신규
    note: str = "",                    # 신규
) -> GeneratedSourceDraft:
    prompt = _build_prompt(project, tone=tone, target_minutes=target_minutes, language=language, mode=mode, note=note)
    source_text = "\n".join(s["excerpt"] for s in project["source_draft_sources"])
    previous = project["source_draft_script"]   # 호출 시점의 script 보존

    client = OllamaClient(model=SCRIPT_LLM_MODEL)
    client.warm()
    try:
        response = client.generate(prompt=prompt, system=SYSTEM_PROMPT, num_predict=500, temperature=_temperature_for_mode(mode))
    finally:
        client.unload()

    script = response.response.strip()
    if not script:
        raise HTTPException(502, "대본 초안을 생성하지 못했습니다.")
    risk_score = copy_risk_score(source_text, script)

    warnings = list(project["source_draft_warnings"])
    threshold = _risk_threshold_for_mode(mode)   # mode별 차등
    if risk_score >= threshold:
        warnings.append(f"원문과 유사한 구간 비율이 높습니다 ({risk_score:.0%}). 표현을 한 번 더 다듬어 주세요.")
    for quote in detect_long_quotes(source_text, script):
        warnings.append(f"원문과 길게 겹치는 표현이 감지되었습니다: {quote[:40].strip()}...")
    return GeneratedSourceDraft(
        script=script,
        warnings=list(dict.fromkeys(warnings)),
        model=response.model,
        risk_score=risk_score,
        mode=mode,
        previous_script=previous,
    )
```

### Mode 별 prompt 구성

```python
_MODE_INSTRUCTIONS: dict[SourceRegenerateMode, str] = {
    "": "도입 1개, 본문 3~6문단, 마무리 1개 정도의 흐름으로 작성한다.",
    "hook": (
        "[훅 모드]\n"
        "- 첫 2~4문장에서 시청자 관심을 강하게 잡아야 한다.\n"
        "- 문제 제기, 의외성, 짧은 대조를 활용한다.\n"
        "- 도입이 끝나자마자 본론으로 진입한다."
    ),
    "point": (
        "[포인트 모드]\n"
        "- 핵심 사실 3~5개를 우선순위 순서로 정리한다.\n"
        "- 각 문단은 하나의 포인트만 다룬다.\n"
        "- 수사를 줄이고 정보 밀도를 높인다."
    ),
    "story": (
        "[스토리 모드]\n"
        "- 사건이 흘러가는 시간 순서를 따라 재구성한다.\n"
        "- 인물, 배경, 전환을 자연스럽게 연결한다.\n"
        "- 원문에 없는 감정/추측은 추가하지 않는다."
    ),
    "lesson": (
        "[교훈 모드]\n"
        "- 사건이 시청자에게 어떤 의미를 갖는지 해석 중심으로 마무리한다.\n"
        "- 단정적 훈계 대신 통찰을 제시한다.\n"
        "- 과도한 일반화는 피한다."
    ),
}


_MODE_TEMPERATURE: dict[SourceRegenerateMode, float] = {
    "": 0.4, "hook": 0.55, "point": 0.30, "story": 0.45, "lesson": 0.50,
}


_MODE_RISK_THRESHOLD: dict[SourceRegenerateMode, float] = {
    # point 는 fact 인용이 많아 자연 overlap 높음 → threshold 약간 완화
    "": 0.30, "hook": 0.30, "point": 0.40, "story": 0.30, "lesson": 0.25,
}


def _temperature_for_mode(mode: SourceRegenerateMode) -> float:
    return _MODE_TEMPERATURE.get(mode, 0.4)


def _risk_threshold_for_mode(mode: SourceRegenerateMode) -> float:
    return _MODE_RISK_THRESHOLD.get(mode, 0.30)


def _build_prompt(project, *, tone, target_minutes, language, mode, note) -> str:
    source = project["source_draft_sources"][0] if project["source_draft_sources"] else None
    fact_notes = [item["note"] for item in project["source_draft_fact_notes"] if item.get("note")]
    if source is None or not fact_notes:
        raise HTTPException(400, "먼저 기사 URL을 분석해 fact note를 준비해 주세요.")
    joined_notes = "\n".join(f"- {n}" for n in fact_notes[:10])
    mode_block = _MODE_INSTRUCTIONS.get(mode, _MODE_INSTRUCTIONS[""])
    note_block = f"\n[추가 지시]\n{note.strip()}\n" if note.strip() else ""
    return f"""다음 자료를 바탕으로 영상용 대본 초안을 작성해 줘.

[작성 조건]
- 언어: {language}
- 톤: {tone}
- 목표 길이: 약 {target_minutes}분
- 기사 원문을 그대로 복사하지 말고 재구성
- 과장 없이 설명형 문체

{mode_block}
{note_block}
[기사 정보]
제목: {source["title"]}
도메인: {source["domain"]}
요약: {source["excerpt"]}

[Fact Notes]
{joined_notes}
"""
```

## API

### 신규 — Regenerate 엔드포인트

```
POST /api/projects/{pid}/source/script/regenerate
Form fields:
  mode: hook | point | story | lesson  (필수)
  note: str (선택, ≤ 200자)
  tone: str (default "설명형")
  target_minutes: int (1~8)
  language: str (default "ko")
```

동작:

1. `_require(pid)` + `source_draft_sources` 존재 확인
2. **concurrency guard**: `source_draft_state == "running"` 이면 409 (Phase 1 worker 분리 전까지)
3. `source_draft_regenerate_mode/note` 저장
4. `generate_script_draft(..., mode=mode, note=note)` 호출
5. 결과를 DB 갱신 — **`source_draft_previous_script` 에 호출 직전 script 백업**

### 기존 generate route 도 mode 받기

`POST /source/script/generate` 도 같은 `mode/note` 필드를 받게 확장. 그러면 첫 generate 와 regenerate 가 같은 코드 경로 사용 (regenerate = generate + previous 보존).

→ **`/regenerate` 별도 엔드포인트 만들지 않고 `/generate` 가 mode 인자로 처리**하는 것이 코드 중복 적음. UI 만 명칭을 분리.

권장 결정: **단일 `/generate` 엔드포인트 + mode 옵션**. 회귀 호환을 위해 mode 미지정 시 기본 동작(빈 mode) 유지.

### 이전 초안 복원

```
POST /api/projects/{pid}/source/script/restore-previous
```

동작:
- `source_draft_previous_script` 가 비어 있지 않으면 `source_draft_script` 와 swap
- swap 후 양쪽이 모두 보존되어 다시 토글 가능 → 사용자가 "이전 / 현재" 왕복 가능

## 프론트 변경

Step 1 Source Assist:

```
[ Generate Script Draft ]   ← 첫 생성 (mode="")

[ Regenerate ]    [ 훅 | 포인트 | 스토리 | 교훈 ]    [ 추가 지시 입력... ]

Draft Preview
  ┌─────────────────────────────────────────┐
  │ Mode: 스토리  ·  Risk: 18%               │
  │ ⟳ 이전 초안과 비교  | ↺ 이전 초안으로 복원 │
  ├─────────────────────────────────────────┤
  │ <draft text>                             │
  └─────────────────────────────────────────┘
```

상태 표시:
- `running` 이면 mode 버튼 disabled
- `previous_script` 비어 있으면 "이전으로 복원" 버튼 hidden

비교 보기 (Phase 3):
- 모달 또는 side-by-side
- difflib unified diff 가 아니라 단순 left/right 텍스트 비교 (가독성 우선)

## 안전 / 품질

- `copy_risk_score`, `detect_long_quotes` 그대로 재사용
- mode 별 임계값:
  - `point` 0.40 (사실 인용 자연 overlap 허용)
  - `lesson` 0.25 (해석 중심이라 overlap 낮아야 정상)
  - 나머지 0.30
- `lesson` 모드 prompt 에 "과도한 일반화 방지" 명시
- `story` 모드 prompt 에 "원문에 없는 감정/추측 금지" 명시

## 동시성 가드 (worker 분리 이전 필수)

[source-draft-worker-separation-plan.md](source-draft-worker-separation-plan.md) 가 완료되면 자연스럽게 해결되지만, 그 전에는:

```python
# /generate, /regenerate 진입 시
if project["source_draft_state"] == "running":
    raise HTTPException(409, "이미 다른 생성 작업이 진행 중입니다.")
```

worker 분리 후엔 queued → running 전이가 worker 락에서 처리되므로 이 가드는 자연 폐기.

## 구현 단계

### Phase 1. DB + 서비스 + API `[Pending]` (P0)

- `source_draft_regenerate_mode/note/previous_script` 컬럼 + migration
- `_MODE_INSTRUCTIONS`, `_temperature_for_mode`, `_risk_threshold_for_mode`
- `generate_script_draft()` 에 `mode/note` 인자 + previous 보존
- `/source/script/generate` Form 필드 확장 — `mode/note`
- 동시성 가드 (409)
- 회귀 테스트 (mode 별 prompt, fact_notes 빈 차단, previous 보존)

### Phase 2. UI `[Pending]` (P0)

- segmented control (4 mode + clear)
- 추가 지시 1줄 입력
- Mode badge in preview
- "이전 초안과 비교" / "이전으로 복원" 버튼 (previous 가 있을 때만)

### Phase 3. 비교 보기 + 모드 추천 `[Pending]` (P1)

- side-by-side diff modal
- mode 선택 시 기본 길이/톤 가이드 (예: hook → 1분, lesson → 5분)

## 회귀 테스트

```python
# tests/test_source_draft.py
def test_generate_with_hook_mode_uses_hook_template():
    # _build_prompt 결과 문자열에 "[훅 모드]" 포함

def test_lesson_mode_has_stricter_risk_threshold():
    assert _risk_threshold_for_mode("lesson") < _risk_threshold_for_mode("point")

def test_previous_script_preserved_after_regenerate(monkeypatch):
    # 호출 전 source_draft_script 가 GeneratedSourceDraft.previous_script 에 보존

def test_empty_fact_notes_blocked_for_all_modes():
    # 모든 mode 에서 fact_notes 빈 → 400

def test_concurrency_guard_returns_409_when_running():
    # source_draft_state="running" 인 상태에서 /generate → 409

# tests/test_feature_workflow.py
def test_regenerate_via_generate_route_with_mode_form_field():
def test_restore_previous_swaps_script_and_previous():
def test_subsequent_regenerates_keep_only_one_previous():
    # previous 가 누적되지 않고 직전 1개만 유지

# tests/test_script_safety.py
def test_warning_threshold_differs_per_mode():
```

## 완료 기준

- 같은 source/fact_notes 로 4개 모드 결과가 명확히 다름 (수동 확인)
- mode badge 가 preview 에 항상 표시
- previous_script 비교/복원이 동작
- mode 별 위험 임계값 차등으로 false positive 줄어듦
- worker 분리 후에도 같은 mode 인자가 worker 경로에서 그대로 동작 (Phase 4 cross-link)
