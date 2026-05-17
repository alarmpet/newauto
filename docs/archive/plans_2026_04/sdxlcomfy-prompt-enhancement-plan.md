# SDXL Comfy Prompt Enhancement Plan

작성일: 2026-04-30

## Implementation Status

Current P0 slice completed in `newauto`:

- `app/types.py` now carries dual prompt, ControlNet, LoRA, repair-related typed structures, and `VisualBrief` optional expansion fields.
- `app/services/prompt_compiler.py` now returns structured `SdxlDualPrompt` with `prompt_g`, `prompt_l`, and `combined`, while `compile_positive_prompt_text()` preserves a string wrapper for older call sites.
- `suggest_image_prompt()` now records `prompt_g` and `prompt_l` alongside `positive_prompt`.
- Added `app/services/comfyui_prompt_adapter.py` so router and worker paths build prompt placeholders through one shared bridge.
- SDXL workflow templates now read `__POSITIVE_PROMPT_G__` and `__POSITIVE_PROMPT_L__` for `CLIPTextEncodeSDXL`.
- Added `app/services/prompt_repair.py` with issue-code-based repair decisions for a first bounded retry path.
- `app/workers/image_worker.py` now performs at most one repair retry for lightweight items when candidate review recommends retry, and skips repair retry for heavier style/control paths.
- `candidate_reviews` now persist repair metadata (`repair_attempted`, `repair_reason`, `repair_issue_codes`) so retry decisions remain visible after worker execution.
- Repair retry now preserves SDXL prompt separation by updating `prompt_g` for composition/content fixes and `prompt_l` for style/camera fixes instead of collapsing both to one combined string.
- Heavy-path, GPU-busy, and retry-limit exits now also persist repair suggestions (`suggested_positive_prompt`, split `suggested_prompt_g/l`, and `suggested_repair_reason`) in `candidate_reviews` even when no retry is executed.
- Focused unittest and typecheck for the new P0 slice are passing.

## 1. 분석 요약

`sdxlcomfy.txt`의 핵심 제안은 다음 한 문장으로 정리된다.

> LLM이 문장/개념을 먼저 구조화하고, SDXL/ComfyUI에서는 Prompt, ControlNet, LoRA를 각각 의미, 구도, 스타일 담당으로 나누어 제어한다.

이 방향은 우리 프로그램의 최근 문제와 잘 맞는다. 자동차, 도로, 체크리스트, 과한 실사 배경처럼 대본 맥락과 무관한 이미지가 나오는 이유는 이미지 모델이 나쁜 것이 아니라, 프롬프트가 `무엇을 그릴지`, `어떤 관계로 배치할지`, `어떤 스타일로 제한할지`를 충분히 분리해서 전달하지 못했기 때문이다.

다만 문서의 원안을 그대로 적용하면 위험하다.

- Gemma 4, SDXL, ControlNet, LoRA를 한 워크스테이션에서 동시에 강하게 쓰는 구조는 8GB VRAM 환경에서 병목/OOM 위험이 크다.
- ControlNet/LoRA는 좋은 도구지만, 현재 기본 운영 경로는 prompt-only와 lightweight ComfyUI 경로가 더 안정적이다.
- 문서의 `Gemma 4 4B`, `Thinking Mode`, `2026년 초 발표` 같은 모델 설명은 구현 계획의 참고 개념으로만 다루고, 실제 코드에는 특정 미검증 모델명에 종속되지 않도록 한다.

따라서 적용 방향은 다음으로 정한다.

1. V1: LLM/규칙 기반 scene brief를 더 구조화하고, prompt-only에서도 잘 작동하는 프롬프트 스키마를 강화한다.
2. V2: 이미 있는 SDXL/ComfyUI profile, LoRA, IPAdapter, ControlNet Depth 경로에 구조화 필드를 점진적으로 연결한다.
3. V3: Vision QA 또는 CLIP/VLM 기반 피드백 루프로 생성 결과를 재평가하고 자동 재시도한다.

## 2. 현재 코드 현실

이미 구현된 기반:

- `app/services/image_prompting.py`
  - `style_preset=simple_diagram`
  - `k_webtoon`
  - 기술/에세이 도메인별 visual brief 보정
  - `recommended_style_preset`

- `app/services/prompt_compiler.py`
  - `VisualBrief` 기반 positive/negative prompt 생성
  - `simple_diagram` 전용 flat explainer prompt

- `app/services/prompt_quality.py`
  - raw text, generic object, close-up, diagram style collision 등 issue code 감지

- `app/services/image_generation_profiles.py`
  - SDXL standard/fast/lightning/style reference/controlnet depth profile
  - KSampler 파라미터와 micro-conditioning 연결

- `app/workflow_templates/comfyui/*.json`
  - `CLIPTextEncodeSDXL` 사용
  - basic/lightning/stickman LoRA/IPAdapter/ControlNet Depth 템플릿 존재

- `app/services/comfyui_pipeline.py`
  - candidate score
  - vision QA V1
  - style consistency V1

아직 부족한 부분:

- SDXL dual prompt 역할 분리(`prompt_g`, `prompt_l`)가 코드 개념으로 명시되어 있지 않다.
- `VisualBrief`가 ControlNet/LoRA 추천을 담는 수준까지 확장되어 있지 않다.
- ControlNet은 Depth profile만 있고, diagram에 더 적합한 Canny/Lineart/Scribble은 아직 없다.
- 프롬프트 실패 시 issue code별 자동 repair 정책이 아직 제한적이다.
- 생성 결과를 보고 prompt/control/lora 값을 조정하는 feedback loop는 V1 수준의 품질 점수에 머물러 있다.

추가 코드 검토로 확인한 구조적 간극:

- `app/types.py`의 `VisualBrief`는 아직 `mode`, `main_subject`, `primary_prop` 중심이다. 따라서 `visual_intent`, `prompt_g`, `prompt_l`, `controlnet_type`, `lora_name` 같은 새 필드는 반드시 타입 정의에서 먼저 열어야 한다.
- `app/services/prompt_compiler.py`의 `compile_positive_prompt()`는 현재 문자열 하나를 반환한다. SDXL dual prompt를 제대로 쓰려면 내부 문자열 조립만 고치는 수준이 아니라 반환 구조를 분리해야 한다.
- `app/services/comfyui_pipeline.py`는 `retry_recommended=True`를 기록하지만, 이 플래그를 보고 prompt를 고쳐 재전송하는 오케스트레이터는 없다.
- `app/workers/image_worker.py`와 `app/routers/image_gen.py`는 placeholder를 직접 만들고 있으므로, VisualBrief의 ControlNet/LoRA 결정을 ComfyUI JSON placeholder로 변환하는 bridge가 별도 계층으로 필요하다.
- `app/services/gpu_guard.py`는 이미 존재한다. ControlNet/Vision QA 같은 무거운 경로는 이 가드를 통과하지 못하면 early exit로 prompt-only 경로를 타야 한다.

## 3. 목표

대본의 문장과 핵심 키워드를 다음 형태로 안정적으로 이미지화한다.

- 실사 장면이 필요한 문장: 구체적인 subject/action/place 중심으로 생성
- 설명형/기술형 문장: `simple_diagram` 중심으로 생성
- 캐릭터 일관성이 필요한 영상: `k_webtoon` 또는 style reference 중심으로 생성
- 구조가 중요한 장면: ControlNet Canny/Lineart/Scribble opt-in
- 스타일이 중요한 장면: LoRA/IPAdapter opt-in

최종 목표는 “모델에게 예쁜 그림을 부탁하는 것”이 아니라, 매 문장마다 다음 결정을 명시적으로 내리는 것이다.

```json
{
  "core_meaning": "문장의 핵심 의미",
  "visual_intent": "literal | metaphor | diagram | character_scene",
  "subject": "중앙 대상",
  "action": "보이는 동작",
  "setting": "배경 또는 패널 환경",
  "props": ["보조 시각 요소"],
  "layout": "center_icon | left_right_compare | flow | scale | chase | burden | close_action",
  "style_mode": "default | simple_diagram | k_webtoon | documentary_interface",
  "prompt_g": "전체 개념과 구도",
  "prompt_l": "선, 색, 질감, 조명, 세부 스타일",
  "negative_prompt": "금지 요소",
  "controlnet": {
    "enabled": false,
    "type": "",
    "strength": 0.0,
    "start_percent": 0.0,
    "end_percent": 0.0
  },
  "lora": {
    "enabled": false,
    "name": "",
    "strength": 0.0
  },
  "qa_expectations": ["must_show subject", "no readable text", "no random vehicles"]
}
```

## 4. Phase 0: 인코딩 및 자료 보존

문제:

- `sdxlcomfy.txt`는 PowerShell 기본 인코딩으로 읽으면 한글이 깨진다.
- 잘못 읽은 텍스트를 기반으로 계획이나 테스트를 만들면 잘못된 진단이 반복된다.

작업:

- 문서/가이드 파일은 반드시 UTF-8로 읽는 운영 규칙을 추가한다.
- PowerShell 진단 시 `Get-Content -Encoding UTF8` 사용을 문서화한다.
- 계획서나 프롬프트 fixture에 깨진 한글이 들어가지 않도록 테스트 fixture를 UTF-8 파일 기반으로 둔다.

Acceptance:

- `sdxlcomfy.txt`의 제목이 깨지지 않고 `SDXL 및 ComfyUI 환경...`으로 읽힌다.
- prompt 관련 테스트 fixture에 `諛`, `?섍`, `�` 같은 mojibake 조각이 없다.

## 5. Phase 1: 타입 스키마 선행 확장

목표:

이 단계는 실제 구현의 첫 단추다. `VisualBrief`와 후보 선택/재시도 관련 타입을 먼저 확장하지 않으면, 이후 prompt compiler, worker, workflow adapter 변경이 모두 암묵적 dict 조작으로 흐르게 된다.

대상 파일:

- `app/types.py`
- `app/services/comfyui_pipeline.py`
- `tests/test_visual_brief.py`
- `tests/test_candidate_selection.py`

추가 타입:

```python
VisualIntent = Literal["literal", "metaphor", "diagram", "character_scene"]
DiagramLayout = Literal[
    "center_icon",
    "left_right_compare",
    "three_outputs",
    "flow",
    "scale",
    "chase",
    "burden",
    "close_action",
]

class SdxlDualPrompt(TypedDict):
    prompt_g: str
    prompt_l: str
    combined: str

class ControlNetDecision(TypedDict):
    enabled: bool
    type: str
    strength: float
    start_percent: float
    end_percent: float

class LoraDecision(TypedDict):
    enabled: bool
    name: str
    strength: float

class PromptRepairDecision(TypedDict):
    should_retry: bool
    attempt: int
    issue_codes: list[str]
    repaired_positive_prompt: str
    repaired_negative_prompt: str
    repair_reason: str
```

`VisualBrief` 추가 필드:

```python
visual_intent: NotRequired[VisualIntent]
layout: NotRequired[str]
prompt_g: NotRequired[str]
prompt_l: NotRequired[str]
controlnet: NotRequired[ControlNetDecision]
lora: NotRequired[LoraDecision]
style_mode: NotRequired[str]
qa_expectations: NotRequired[list[str]]
```

정책:

- 기존 필드는 바로 제거하지 않는다. `main_subject`, `primary_prop`, `scene`, `must_show`는 하위 호환 필드로 유지한다.
- 새 필드는 `NotRequired`로 시작해 기존 manifest와 오래된 프로젝트가 깨지지 않게 한다.
- `CandidateSelectionDecision`은 `retry_recommended` 외에 `repair_attempted`, `repair_issue_codes`, `repair_reason`을 추가할 수 있도록 확장한다.

Acceptance:

- 기존 프로젝트의 `image_prompts_manifest.json`을 읽어도 타입/런타임 오류가 없다.
- 새 prompt suggestion 결과에는 가능한 경우 `visual_intent`, `layout`, `prompt_g`, `prompt_l`가 포함된다.
- typecheck가 `app/types.py` 변경 후 통과한다.

## 6. Phase 2: Triangle Scene Brief 확장

목표:

현재 `VisualBrief`를 prompt용 힌트에서 “Triangle Control decision”으로 확장한다.

대상 파일:

- `app/services/visual_brief.py`
- `app/services/image_prompting.py`
- `app/types.py`
- `tests/test_visual_brief.py`
- `tests/test_image_prompting.py`

정책:

- `simple_diagram`은 기본적으로 `visual_intent=diagram`.
- 기술/설명형 문장은 explicit preset이 없어도 `recommended_style_preset=simple_diagram`.
- 에세이 문장 중 “모래 위를 달리는 일”처럼 직관적 실사/행동이 명확하면 `visual_intent=literal`.
- 추상어만 있는 문장은 `metaphor`.
- 동일 주인공이 중요한 영상은 `character_scene`.

Acceptance:

- 문장별 manifest에 `visual_intent`, `layout`, `prompt_g`, `prompt_l`가 저장된다.
- GPU/데이터센터/AI 에이전트/기업 전환 문장이 모두 같은 `AI brain icon`으로 뭉개지지 않는다.

## 7. Phase 3: SDXL Dual Prompt Adapter

목표:

SDXL의 `CLIPTextEncodeSDXL` 구조에 맞춰 전체 개념과 세부 스타일을 분리한다.

현재 템플릿은 `CLIPTextEncodeSDXL`을 사용하지만, 서비스 레벨에서는 `prompt_g/prompt_l` 구분이 명확하지 않다. 이를 명시적 adapter로 만든다.

중요한 시그니처 변경:

- 현재 `compile_positive_prompt(...) -> str`
- 목표 `compile_positive_prompt(...) -> SdxlDualPrompt`

하위 호환 전략:

- 1차 구현에서는 `compile_positive_prompt_text(...) -> str` wrapper를 유지한다.
- 기존 호출부는 즉시 모두 바꾸지 않고, 먼저 `suggest_image_prompt()`와 ComfyUI batch path부터 dual prompt 객체를 사용한다.
- `combined`는 기존 단일 positive prompt placeholder에 넣을 수 있는 fallback이다.

대상 파일:

- `app/services/prompt_compiler.py`
- `app/services/comfyui_workflows.py`
- `app/routers/image_gen.py`
- `app/workers/image_worker.py`
- `tests/test_prompt_compiler.py`
- `tests/test_comfyui_workflows.py`

규칙:

- `prompt_g`
  - 전체 장면 의미
  - 구도
  - 주체 간 관계
  - 핵심 은유

- `prompt_l`
  - 선 스타일
  - 색상
  - 조명
  - 질감
  - 카메라 또는 다이어그램 표현 방식

예시:

```text
prompt_g:
simple explainer diagram panel, central balance scale comparing server stack and country map silhouette, electricity demand comparison, left-right layout

prompt_l:
clean black outline, flat vector illustration, limited muted colors, plain warm gray background, large readable shapes, no internal text
```

Acceptance:

- `simple_diagram` prompt에는 `35mm lens`, `photorealistic`, `cinematic`이 섞이지 않는다.
- documentary/real scene prompt에는 diagram-only 표현이 섞이지 않는다.
- workflow placeholder가 positive prompt 하나만 받더라도 내부적으로 `prompt_g + prompt_l`의 역할 분리 결과를 보존한다.
- ComfyUI template가 `CLIPTextEncodeSDXL`의 `text_g`, `text_l`을 별도 placeholder로 받을 수 있도록 `__POSITIVE_PROMPT_G__`, `__POSITIVE_PROMPT_L__`를 지원한다.
- 기존 `__POSITIVE_PROMPT__`는 `combined` fallback으로 유지한다.

## 8. Phase 4: ComfyUI Placeholder Bridge

목표:

VisualBrief와 compiler 결과를 실제 ComfyUI workflow placeholder로 변환하는 계층을 만든다. 이 계층이 없으면 ControlNet/LoRA 결정이 manifest에는 남아도 ComfyUI JSON에는 반영되지 않는다.

대상 파일:

- `app/services/comfyui_prompt_adapter.py` 신규
- `app/services/comfyui_workflows.py`
- `app/routers/image_gen.py`
- `app/workers/image_worker.py`
- `tests/test_comfyui_prompt_adapter.py` 신규
- `tests/test_comfyui_workflows.py`
- `tests/test_image_worker.py`

역할:

```python
def build_comfyui_placeholders(
    *,
    dual_prompt: SdxlDualPrompt,
    negative_prompt: str,
    brief: VisualBrief,
    base_placeholders: PlaceholderMap,
) -> PlaceholderMap:
    ...
```

매핑:

| source | placeholder |
| --- | --- |
| `dual_prompt.prompt_g` | `__POSITIVE_PROMPT_G__` |
| `dual_prompt.prompt_l` | `__POSITIVE_PROMPT_L__` |
| `dual_prompt.combined` | `__POSITIVE_PROMPT__` |
| negative prompt | `__NEGATIVE_PROMPT__` |
| `brief.controlnet.strength` | `__CONTROL_STRENGTH__` |
| `brief.controlnet.start_percent` | `__CONTROL_START_PERCENT__` |
| `brief.controlnet.end_percent` | `__CONTROL_END_PERCENT__` |
| `brief.lora.name` | `__LORA_NAME__` |
| `brief.lora.strength` | `__LORA_STRENGTH__` |

정책:

- route와 worker가 각자 placeholder를 손으로 만들지 않도록 공통 adapter를 사용한다.
- ControlNet/LoRA가 disabled이면 기존 profile/default 값을 유지한다.
- 미지원 placeholder는 workflow render 단계에서 무시되지 않고 테스트로 드러나야 한다.

Acceptance:

- dual prompt가 workflow JSON의 SDXL text_g/text_l 입력에 각각 들어간다.
- ControlNet strength/start/end가 template에 연결된다.
- LoRA name/strength가 enabled 상태에서만 연결된다.

## 9. Phase 5: Issue Code 기반 Prompt Repair Hook

목표:

QA가 실패했을 때 “그냥 재시도”하지 않고, 실패 이유별로 프롬프트를 고친다.

현재 문제:

- `comfyui_pipeline.py`는 `retry_recommended=True`를 기록할 뿐 실제 재시도 지시는 하지 않는다.
- 따라서 repair는 `comfyui_pipeline.py` 안에 섞지 말고 별도 서비스와 worker orchestration으로 분리한다.

대상 파일:

- `app/services/prompt_repair.py` 신규
- `app/services/prompt_quality.py`
- `app/services/image_prompting.py`
- `app/services/comfyui_pipeline.py`
- `app/workers/image_worker.py`
- `tests/test_prompt_quality.py`
- `tests/test_image_prompting.py`
- `tests/test_prompt_repair.py` 신규
- `tests/test_image_worker.py`

구조:

1. `comfyui_pipeline.py`
   - 후보 생성 결과를 평가한다.
   - `candidate_reviews[].retry_recommended`, `vision_qa_issue_codes`, `selection_reason`을 반환한다.

2. `prompt_repair.py`
   - issue code와 기존 `VisualBrief`, positive/negative prompt를 받아 repair result를 만든다.
   - script, subtitle, sentence text는 수정하지 않는다.

3. `image_worker.py`
   - retry가 허용된 job에서만 1회 또는 설정된 횟수만큼 repair generation을 enqueue/submit한다.
   - VRAM guard가 바쁘면 repair retry를 생략하고 `retry_deferred_gpu_busy`로 기록한다.

repair 정책:

| issue code | repair |
| --- | --- |
| `RAW_TEXT_VISUAL_TARGET` | 한글/원문을 visual icon으로 치환 |
| `GENERIC_SYMBOL_WITHOUT_ALLOW` | 자동차/나침반/체크리스트 제거, subject 재선택 |
| `DIAGRAM_STYLE_COLLISION` | 사진/렌즈/실사 표현 제거 |
| `DIAGRAM_COMPLEXITY_RISK` | props를 최대 3개로 축소 |
| `BOOK_TEXT_RISK` | book/document close-up 대신 icon stack으로 변환 |
| `CLOSEUP_RISK` | medium-wide 또는 panel composition 추가 |
| `MISSING_FRAMING_SLOT` | layout/framing anchor 추가 |
| `MISSING_CAMERA_TECHNICAL_SLOT` | 실사 모드에만 camera anchor 추가 |

Acceptance:

- 한 번의 repair 후 같은 issue code가 반복되면 candidate review에 남긴다.
- prompt repair는 원문 script나 subtitle text를 바꾸지 않는다.
- repair attempt 수는 job option으로 제한한다. 기본값은 0 또는 1.
- worker log에 `repair_attempted`, `repair_skipped_reason`이 남는다.

## 10. Phase 6: GPU Guard Early Exit

목표:

8GB VRAM 환경에서 무거운 경로가 전체 파이프라인을 막지 않게 한다.

대상 파일:

- `app/services/gpu_guard.py`
- `app/workers/image_worker.py`
- `app/services/autopilot.py`
- `app/routers/image_gen.py`
- `tests/test_image_worker.py`
- `tests/test_autopilot_worker.py`

정책:

- ControlNet, Vision QA V2, multi-candidate exhaustive retry는 heavy path로 분류한다.
- `gpu_guard.acquire()`에 실패하면 다음 중 하나를 선택한다.
  - prompt-only standard/lightning profile로 fallback
  - repair retry를 defer
  - 현재 후보 중 best score를 선택하고 warning 기록
- TTS/LLM 작업이 GPU를 잡고 있으면 ComfyUI heavy retry를 기다리지 않는다.

Acceptance:

- GPU lock이 다른 owner에게 잡혀 있을 때 ControlNet/Vision QA V2가 실행되지 않는다.
- fallback 결과가 `candidate_reviews` 또는 job log에 기록된다.
- 일반 prompt-only batch는 기존처럼 동작한다.

## 11. Phase 7: ControlNet 확장 정책

목표:

ControlNet을 기본값으로 강제하지 않고, 구조가 필요한 장면에서만 opt-in한다.

현재 상태:

- `sdxl_controlnet_depth` profile은 있다.
- Depth는 원근/공간 제어에는 좋지만, 첨부 이미지 같은 단순 도식에는 Canny/Lineart/Scribble이 더 적합하다.

추가할 profile:

- `sdxl_controlnet_canny`
- `sdxl_controlnet_lineart`
- `sdxl_controlnet_scribble`

선택 정책:

| visual_intent/layout | 권장 ControlNet |
| --- | --- |
| `diagram`, `center_icon`, `flow`, `scale` | Lineart 또는 Scribble |
| `literal`, 인물 동작 | OpenPose, V2 이후 |
| 풍경/공간 분리 | Depth |
| UI/문서/도식 패널 | Canny 또는 Lineart |

운영 제한:

- 8GB VRAM 환경에서는 batch 전체에 ControlNet을 걸지 않는다.
- scene별 opt-in 또는 테스트 1~3장만 먼저 적용한다.
- capability check 실패 시 prompt-only로 fallback한다.

Acceptance:

- ControlNet 미설치 환경에서도 pipeline은 실패하지 않고 prompt-only로 안내된다.
- ControlNet 사용 시 `controlnet_type`, `strength`, `start_percent`, `end_percent`가 manifest에 기록된다.

## 12. Phase 8: LoRA/IPAdapter 스타일 정책

목표:

LoRA를 “무조건 켜는 스타일 버튼”이 아니라, 문장/영상 목적에 맞는 style controller로 다룬다.

현재 상태:

- Stickfigures LoRA 경로가 있음.
- IPAdapter style reference 경로가 있음.
- LoRA + IPAdapter 혼합 workflow도 있음.

문제:

- 기술/다이어그램 콘텐츠에 인물 중심 LoRA가 들어가면 오히려 drift가 생긴다.
- `simple_diagram`은 Stickfigures LoRA와 충돌할 수 있다.

정책:

- `simple_diagram`: 기본 LoRA off
- `k_webtoon`: LoRA보다 style reference/IPAdapter 우선
- 동일 캐릭터가 필요한 에세이/스토리: style reference 또는 character LoRA opt-in
- 기술 뉴스/AI 설명: diagram-friendly style만 허용

Acceptance:

- `simple_diagram + stickfigures_lora` 조합은 warning 또는 blocked 상태로 표시된다.
- candidate review에 style controller 정보가 저장된다.

## 13. Phase 9: Feedback Loop V1/V2

목표:

생성 결과를 보고 다음 prompt를 개선한다.

V1: text/metadata 기반

- 현재 `candidate_score`, `vision_qa_score`, `style_consistency_score`를 활용한다.
- missing subject, style collision, low contrast, duplicate image, low detail이면 retry reason을 남긴다.

V2: vision model 기반

- 생성 이미지에 대해 다음 질문을 한다.

```text
Does this image clearly show the planned subject, props, relation, and style?
Return JSON only:
{
  "matches_subject": true,
  "matches_relation": true,
  "style_matches": true,
  "text_leak": false,
  "unexpected_objects": [],
  "retry_prompt_hint": ""
}
```

운영 제한:

- V2는 opt-in.
- 전체 14~30장 영상에 바로 적용하지 않고 실패 후보에만 적용한다.

Acceptance:

- V1은 기본값으로 빠르게 동작한다.
- V2는 비용/시간을 명확히 표시하고 선택적으로만 실행한다.

## 14. Phase 10: Simple Diagram 고도화

목표:

첨부 예시처럼 “중심 아이콘 + 보조 아이콘 + 관계 구조”가 한눈에 들어오게 한다.

강화할 vocab:

- AI 시스템: brain icon, robot assistant, neural node
- GPU/칩: GPU rack, chip grid, heat/cooling fan
- 데이터센터: server stack, power cable, cooling airflow
- 기업 전환: company building, turning arrow, blueprint
- 경쟁/추격: running figure, burden factory, arrow trail
- 비교: balance scale, split panel
- 자동화: robot hand, calendar, card, envelope, gear
- 불확실성: question bubble, fog, crossed paths

금지할 drift:

- random car
- random road
- compass
- checklist
- unreadable fake text
- close-up hand holding phone
- duplicate people with no reason
- photorealistic bedroom/office unless literal scene requires it

Acceptance:

- `simple_diagram` 기술 문장 10개 샘플에서 central subject가 4종 이상으로 분산된다.
- 자동차/도로 drift가 0건이어야 한다. 단, 문장 자체가 교통/자동차를 말하는 경우는 예외.

## 15. 테스트 계획

Unit tests:

- `tests.test_visual_brief`
- `tests.test_image_prompting`
- `tests.test_prompt_compiler`
- `tests.test_prompt_quality`
- `tests.test_prompt_repair`
- `tests.test_comfyui_prompt_adapter`
- `tests.test_comfyui_workflows`
- `tests.test_comfyui_routes`
- `tests.test_image_worker`
- `tests.test_candidate_selection`

실전 smoke:

1. 기술 뉴스 문장 3개
2. 에세이 literal sentence 3개
3. simple_diagram sentence 3개
4. k_webtoon sentence 3개

검증 기준:

- prompt에 subject/action/layout/style이 있다.
- negative prompt에 drift blocklist가 있다.
- candidate review에 score/retry reason이 남는다.
- repair retry가 켜진 경우에만 prompt가 수정되어 재시도된다.
- GPU guard가 busy이면 heavy retry가 early exit된다.
- render preflight에서 stale/missing image mapping이 막힌다.

## 16. 우선순위

P0:

- UTF-8 자료 읽기 규칙 문서화
- `app/types.py`의 `VisualBrief`, dual prompt, ControlNet, LoRA, repair 관련 타입 선행 확장
- `prompt_compiler.py`의 `compile_positive_prompt()` 반환 구조 리팩터링 계획 수립 및 wrapper 도입
- `__POSITIVE_PROMPT_G__`, `__POSITIVE_PROMPT_L__`, `__POSITIVE_PROMPT__` placeholder bridge 도입
- `simple_diagram` prompt repair 강화
- `prompt_repair.py` 신규 서비스와 worker-level repair hook 1차
- GPU guard 기반 heavy path early exit

P1:

- `VisualBrief`에 `visual_intent/layout/controlnet/lora` 필드 실제 채움
- ControlNet Canny/Lineart/Scribble capability 및 profile 추가
- style controller policy 추가
- ControlNet/LoRA placeholder bridge를 route/worker 전 경로에 적용

P2:

- Vision QA V2
- ControlNet auto sketch generation
- scene별 feedback loop retry

## 14. 핵심 결론

`sdxlcomfy.txt`의 Triangle Control 전략은 방향이 맞다. 하지만 우리 프로그램에서는 이를 “항상 Gemma + ControlNet + LoRA를 켜는 무거운 파이프라인”으로 구현하면 안 된다.

가장 좋은 적용 방식은 다음이다.

- 기본은 prompt-only에서도 강한 structured prompt.
- SDXL/ComfyUI에서는 dual prompt, profile, micro-conditioning을 활용.
- ControlNet/LoRA는 scene별 opt-in.
- QA 실패 시 issue code별로 prompt를 자동 repair하되, repair hook은 worker가 제어한다.
- heavy path는 GPU guard를 보고 early exit한다.
- VRAM이 허락할 때만 vision feedback loop와 ControlNet 고도화를 켠다.

이렇게 가면 지금까지 만든 `simple_diagram`, `k_webtoon`, SDXL profile, IPAdapter, ControlNet Depth 기반을 버리지 않고, 문서의 좋은 아이디어만 현재 파이프라인에 현실적으로 흡수할 수 있다.
