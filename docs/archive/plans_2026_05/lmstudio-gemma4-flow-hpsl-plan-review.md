# LM Studio Gemma4 + Flow HPSL 계획서 분석 의견

> 분석 기준일: 2026-05-06  
> 대상 문서: `lmstudio-gemma4-flow-hpsl-video-plan.md`  
> 분석 범위: 계획서 내용 + 현재 `newauto` 코드베이스 교차 검증

---

## 1. 전체 평가

계획서의 **방향성은 올바르다**. 기존 파이프라인을 최대한 재사용하고, Flow 자동화를 점진적으로(Assisted → Playwright → API) 확장하는 전략은 현실적이다. HPSL 구조도 기존 `source_draft.py`의 `SourceRegenerateMode`("hook", "point", "story", "lesson")와 자연스럽게 맞물린다.

그러나 **코드베이스를 실제로 대조해보면 간과된 갭이 다수 존재**한다. 아래에 항목별로 정리한다.

---

## 2. 문제점

### 2.1 Gemma4 컨텍스트 윈도우 과소평가

계획서에서 "컨텍스트가 작으므로 단계별로 나누어 호출"이라고만 언급하지만, 현재 `llm_ollama.py`의 Ollama 경로에서 `num_ctx: 2048`로 하드코딩되어 있고, **LM Studio 경로에는 `num_ctx` 설정 자체가 없다**.

```python
# llm_ollama.py:88-94 (LM Studio 경로)
payload = {
    "model": self.model,
    "messages": messages,
    "stream": False,
    "temperature": temperature,
    "max_tokens": num_predict,  # ← num_ctx 없음
}
```

> [!WARNING]
> `google/gemma-4-e4b`의 실제 max context는 모델 설정에 따라 다르지만, LM Studio의 기본값이 적용된다. 계획서의 3단계 호출(fact extraction → HPSL script → visual prompt)에서 **2차 HPSL 호출 시 fact_notes 전체 + 프롬프트 + JSON 출력 공간이 필요**하므로, 명시적 context budget 관리가 반드시 필요하다.

**개선안**: LM Studio `/v1/chat/completions`에서 `max_tokens`와 별도로, fact_notes를 토큰 수 기준으로 잘라넣는 truncation 로직 추가. 계획서 Phase 1에 "context budget 옵션"이 언급되어 있지만 구체적 구현 방안이 없다.

---

### 2.2 JSON repair 유틸의 구체성 부족

계획서에 "JSON repair 유틸 추가"라고만 되어 있으나, 현재 코드베이스에 이미 `parse_utils.py`가 존재한다. 그리고 `visual_planner.py`에는 `_JSON_BLOCK_RE` 같은 JSON 블록 추출 패턴이 이미 있다.

```python
# visual_planner.py:34
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
```

> [!IMPORTANT]
> Gemma4-e4b 수준의 소형 모델은 JSON 출력 시 **markdown 코드블록 감싸기, trailing comma, 누락된 닫는 괄호, 문자열 안의 이스케이프 실패** 등이 빈번하다. 계획서는 "1회 repair prompt"만 언급하지만, 실제로는 regex-based structural repair → re-parse → 실패 시 repair prompt 순서의 **다단계 fallback**이 필요하다.

**개선안**: 
1. 기존 `parse_utils.py`를 확장하여 `extract_json_from_llm_response()` 함수를 만들 것
2. repair 순서: strip markdown fence → fix trailing comma → balance brackets → json.loads → 실패 시 repair prompt
3. 계획서에 이 구체적 순서를 명기할 것

---

### 2.3 VisualSourceMode 타입 불일치

계획서에서 `visual_source_mode` 확장으로 `flow_assisted`, `flow_auto`, `flow_then_comfyui_fallback`을 추가한다고 했지만, 현재 코드의 `_coerce_visual_source_mode()`는 아래와 같다:

```python
# autopilot.py:96-99
def _coerce_visual_source_mode(value: object) -> VisualSourceMode:
    if value in {"upload_only", "hybrid", "comfyui_auto"}:
        return cast(VisualSourceMode, value)
    return "comfyui_auto"
```

> [!WARNING]
> `VisualSourceMode` 타입 정의 자체가 `types.py`에서 검색되지 않는다 (아마 문자열 리터럴 union으로 정의되어 있을 것). 계획서의 새 모드들을 추가하면 **이 coerce 함수, UI의 select 옵션, autopilot worker의 분기 로직** 세 곳을 동시에 수정해야 한다. 계획서에는 autopilot options JSON만 나와 있고 코드 수정 지점이 누락되어 있다.

**개선안**: 영향받는 코드 지점 목록을 계획서에 명시할 것:
- `app/services/autopilot.py` → `_coerce_visual_source_mode()`
- `app/types.py` → `VisualSourceMode` 타입 정의
- `app/workers/autopilot_worker.py` → phase 분기 로직
- 프론트엔드 Step 5 / Autopilot 설정 UI

---

### 2.4 HPSL ↔ 기존 script 파이프라인 변환 갭

계획서에서 HPSL JSON의 `sentences` 배열이 최종 `user_script`/`compiled_script`/`regional_sentences`로 변환된다고 했지만, **변환 규칙이 정의되어 있지 않다**.

현재 `source_draft.py`의 `generate_script_draft()`는 **평문 스크립트**를 반환한다:

```python
# source_draft.py:176
script = sanitize_source_draft_script(response.response.strip())
```

그리고 `script_compile.py`의 `compile_script()`가 이 평문을 문장 단위로 분할한다. HPSL JSON에서 `sentences[].narration`을 이어붙여 평문으로 만든 뒤 기존 경로에 넣을 건지, 아니면 HPSL의 `sentences[]`를 직접 `regional_sentences`로 매핑할 건지가 **설계 분기점**인데 계획서에서 다루지 않았다.

**개선안**: 두 가지 옵션 중 택일하고 명시:
- **Option A**: `hpsl.sentences[].narration`을 `\n` 조인하여 `user_script`에 넣고, 기존 `compile_script()` 경로를 그대로 탐. (간단, 하지만 HPSL 메타데이터 손실)
- **Option B**: `hpsl.sentences[]`를 직접 `regional_sentences`로 매핑하고, `compiled_script`는 조인 문자열로 생성. (HPSL 구조 보존, 하지만 `compile_script()` 우회 필요)

추천: **Option A로 시작**, Phase 2에서 HPSL 메타데이터가 필요한 곳(visual prompt 등)에서는 별도 `hpsl_script.json`을 직접 참조.

---

### 2.5 source_draft.py의 num_predict 제한

현재 `source_draft.py`에서 LLM 호출 시 `num_predict=500`으로 고정되어 있다:

```python
# source_draft.py:168-173
response = client.generate(
    prompt=prompt,
    system=SYSTEM_PROMPT,
    num_predict=500,
    temperature=_temperature_for_mode(mode),
)
```

HPSL 대본은 hook + points + story + lesson + sentences 배열을 JSON으로 출력해야 하므로 **500 토큰은 턱없이 부족**하다. 1분 쇼츠 기준으로도 최소 8~12개 문장이 필요하고, JSON 오버헤드까지 고려하면 **1500~2500 토큰**은 필요하다.

**개선안**: `hpsl_script.py`에서는 `num_predict`를 최소 2000으로 설정. 계획서 Phase 2 완료 기준에 "HPSL JSON을 2회 이내 안정적으로 파싱"이라고 되어 있는데, `num_predict` 부족으로 JSON이 잘리면 파싱 자체가 불가능하다.

---

### 2.6 Flow Assisted 모드의 asset 감지 메커니즘 미정의

계획서의 Mode A (Flow Assisted)에서 사용자가 Flow에서 생성한 파일을 다운로드 폴더에 저장한 뒤 newauto가 연결한다고 했지만, **어떻게 감지할지**가 없다:

- 사용자가 수동으로 "Attach Asset" 버튼을 누르는 건지?
- 다운로드 폴더를 file watcher로 감시하는 건지?
- 드래그 앤 드롭인지?

**개선안**: 초기 구현은 **수동 파일 선택 (file input)** 방식이 가장 안전하다. File watcher는 오탐이 많고, 다운로드 폴더 경로도 사용자마다 다르다. UI에 "파일 선택" 버튼을 두고, 선택된 파일을 `storage/projects/{pid}/flow_assets/sentence_{idx}.{ext}`로 복사하는 방식을 계획서에 구체화할 것.

---

### 2.7 Autopilot phase 순서의 기존 호환성

계획서의 새 phase 목록:
```
source_collect → source_generate_hpsl → source_apply → visual_plan → 
flow_prompt_generate → flow_generate_or_wait → tts_enqueue → ...
```

현재 autopilot worker의 phase 진행 로직을 보면, `prepare_input` → source 관련 → compile → image/tts → render 순서로 진행된다. 새 phase들을 끼워넣으면 **기존 `script` 입력 모드의 autopilot이 깨질 수 있다**.

**개선안**: HPSL/Flow 전용 phase는 `input_mode`가 `url` 또는 `keyword`이고 `script_structure`가 `hpsl`일 때만 활성화되도록 조건부 분기를 설계할 것. 기존 `script` 입력 모드는 현재 phase 순서를 그대로 유지.

---

### 2.8 테스트 계획의 실질적 검증 부족

테스트 계획에 Unit/Integration/Manual이 나열되어 있지만:

1. **LM Studio 의존 테스트의 CI 전략이 없다** — LM Studio가 꺼져 있을 때 테스트가 어떻게 동작할지. Mock? Skip?
2. **Flow browser mock의 범위가 불명확** — `FakeFlowAdapter`가 실제 Playwright 없이 어디까지 검증하는지
3. **기존 테스트와의 충돌 가능성** — `types.py` 수정 시 기존 테스트 전체에 영향

**개선안**: 
- LM Studio 테스트: `@pytest.mark.skipif(not lmstudio_available())` 데코레이터 패턴 사용
- FakeFlowAdapter: submit → pending → polling → done 상태 전이만 검증하는 상태 머신 테스트
- 기존 테스트 영향 범위를 Phase 1 시작 전에 `pytest --collect-only`로 확인

---

## 3. 누락된 고려사항

### 3.1 에러 복구 전략

현재 autopilot에는 `_pause_with_failure()` → 사용자 수동 재개 패턴이 확립되어 있다. 그런데 계획서의 `flow_generate_or_wait` phase에서:
- Flow 크레딧 부족 시 → ComfyUI fallback은 자동인지 수동인지?
- LM Studio 서버 다운 시 → 재시도 횟수 제한?
- HPSL JSON 파싱 3회 연속 실패 시 → 기존 평문 대본 fallback?

이 각각에 대한 error code와 action_hint 정의가 필요하다.

### 3.2 프론트엔드 라우팅

계획서에 `app/routers/flow.py`를 새로 만든다고 했지만, 현재 라우터 목록(`autopilot.py`, `image_gen.py`, `projects.py`, `render.py`, `stock.py`, `system.py`, `youtube.py`)에서 어떤 엔드포인트가 필요한지 API 설계가 없다. 최소한:

```
POST /api/flow/prompts/{pid}          — Flow 프롬프트 일괄 생성
GET  /api/flow/prompts/{pid}          — 문장별 프롬프트 조회
POST /api/flow/assets/{pid}/{idx}     — asset 파일 업로드
GET  /api/flow/manifest/{pid}         — Flow manifest 조회
```

### 3.3 동시성/GPU 리소스 충돌

현재 `gpu_guard.py`가 ComfyUI와 TTS 간의 GPU 점유를 관리한다. Flow는 외부 서비스이므로 GPU와 무관하지만, **LM Studio가 GPU를 사용할 경우** ComfyUI와 동시 실행이 불가능하다. 계획서에 이 부분이 빠져 있다.

**개선안**: Phase 1에서 LM Studio가 GPU를 사용하는지 확인하고, 사용한다면 `gpu_guard`에 `lmstudio` owner를 추가하여 ComfyUI 이미지 생성과 LLM 호출이 동시에 진행되지 않도록 관리.

---

## 4. 구현 순서 조정 제안

계획서의 Phase 순서는 대체로 합리적이나, 다음 조정을 권장한다:

| 순서 | 계획서 원본 | 조정 제안 | 이유 |
|------|------------|-----------|------|
| 1 | LM Studio 안정화 | **LM Studio 안정화 + JSON repair** | repair 없이 Phase 2 진입 불가 |
| 2 | HPSL 대본 생성 | **HPSL 대본 생성 + script 변환 규칙 확정** | 변환 방식이 Phase 3~6 전체에 영향 |
| 3 | Flow prompt 생성 | 동일 | - |
| 4 | Flow Assisted | **Flow Assisted + API 라우터** | UI만 만들면 백엔드 없이 동작 불가 |
| 5 | Flow Playwright | 동일 (선택) | - |
| 6 | Autopilot 통합 | 동일 | - |

---

## 5. 긍정적 평가

1. **점진적 접근**: Assisted → Auto → API 순서로 위험을 줄이는 전략이 우수하다.
2. **기존 자산 재사용**: 새 앱이 아닌 기존 파이프라인 확장으로 접근한 것이 정확하다.
3. **보안/안전 정책**: prompt injection 방어, 결제/로그인 자동화 금지 등 실질적 위험을 잘 식별했다.
4. **HPSL 구조**: 기존 `SourceRegenerateMode`의 hook/point/story/lesson과 정확히 매핑되어, 향후 모드별 대본 재생성에도 자연스럽게 연결된다.
5. **성공 기준이 구체적**: "키워드 하나로 최종 mp4까지"라는 명확한 E2E 목표가 있다.

---

## 6. 최종 권장 사항

1. **Phase 1을 더 구체화**하라. JSON repair 전략, context budget 관리, `num_predict` 조정이 Phase 2 이후 전체의 성패를 좌우한다.
2. **HPSL → 기존 script 변환 규칙**을 Phase 2 시작 전에 확정하라. 이것이 아키텍처 분기점이다.
3. **GPU 리소스 관리** 계획을 추가하라. LM Studio + ComfyUI 동시 사용 시나리오가 반드시 발생한다.
4. **Flow 라우터 API 설계**를 Phase 4 이전에 완료하라. UI와 백엔드가 동시에 필요하다.
5. **기존 autopilot 호환성 테스트**를 Phase 6 통합 전에 반드시 수행하라. `script` 입력 모드가 깨지면 현재 운영 중인 자동화 전체가 중단된다.
