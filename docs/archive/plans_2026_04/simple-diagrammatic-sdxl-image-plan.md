# Simple Diagram Image Generation Plan

작성일: 2026-04-29

## Implementation Status

Current `newauto` implementation now has a conservative P0 slice in place:

- Added `style_preset=simple_diagram`
- Added `storage/visual_vocab/diagram.json`
- Re-shaped `VisualBrief` into a simpler icon-first composition when `simple_diagram` is selected
- Compiled diagram prompts away from photographic camera language and toward flat explainer structure
- Added diagram-specific quality checks for style collision, text-control gaps, and complexity drift

This is intentionally a prompt-layer implementation on top of the current `newauto` stack, not a MakeLens/Whisk runtime migration.

## 0. 업데이트 요약

이 문서는 최초 초안의 SDXL/ComfyUI/ControlNet 중심 계획을 수정한다.

핵심 변경:

- V1은 로컬 ComfyUI/ControlNet이 아니라 Whisk/Flow 브라우저 워커의 prompt-only 제어에 집중한다.
- `simple_diagram`은 모델/워크플로우가 아니라 style mode/preset으로 정의한다.
- 시각 기획은 planner 단계에서 하고, prompt 조립은 adapter 단계에서 한다.
- `diagram.json` vocab은 단순 문자열 치환기가 아니라 LLM planner에 주입하는 few-shot 가이드로 사용한다.
- ControlNet, SDXL LoRA, 로컬 ComfyUI는 V2+ 실험 항목으로 내린다.

현재 열린 `newauto` 워크스페이스에는 아래 MakeLens 파일이 없다.

- `pipeline/sentence_scene_planner.py`
- `pipeline/image_prompt_adapter.py`
- `post_render_qa.py`
- `grok_whisk_sentence_scene_style_mode`
- `grok_whisk_sentence_scene_negative_constraints`

따라서 본 계획서는 두 레이어로 쓴다.

- MakeLens 적용 위치: 사용자가 지적한 현재 운영 파이프라인 기준
- newauto 대응 위치: 현재 이 워크스페이스에서 대응되는 파일 기준

## 1. 목표

첨부 이미지처럼 대본의 문장 맥락과 핵심 키워드를 심플하고 직관적인 설명형 이미지로 만든다.

원하는 이미지 특징:

- 한 문장에 하나의 중심 개념
- 1~3개의 보조 아이콘
- 화살표, 저울, 비교, 흐름, 부담, 중심-주변 구조
- 단순한 배경
- 굵고 깨끗한 외곽선
- flat 2D explainer style
- 텍스트는 이미지 내부가 아니라 영상 자막에서 처리

원하지 않는 이미지:

- 실사풍
- 복잡한 배경
- 인물이 여러 명 나오는 장면
- 자동차, 도로, 나침반, 체크리스트 같은 generic drift
- 깨진 문자나 읽을 수 없는 가짜 텍스트
- 3D 렌더/피규어/장난감 같은 질감

## 2. 아키텍처 정정

초안의 파일 기준:

- `visual_planner.py`
- `prompt_compiler.py`
- `image_prompting.py`

MakeLens 기준 적용 위치:

- `pipeline/sentence_scene_planner.py`
  - 문장 의미 분석
  - 중심 대상 추출
  - 레이아웃 선택
  - 보조 아이콘 선택
  - 시각 은유와 관계 구조 결정

- `pipeline/image_prompt_adapter.py`
  - planner 결과를 Whisk/Flow용 positive prompt로 변환
  - style mode 적용
  - negative constraints 병합
  - prompt-only V1의 핵심 구현 위치

- `config.py`
  - `grok_whisk_sentence_scene_style_mode`에 `simple_diagram` 추가
  - `grok_whisk_sentence_scene_negative_constraints`에 diagram 금지어 병합

- `post_render_qa.py` 또는 browser worker retry layer
  - 이미지 내부 텍스트 유출
  - 스타일 충돌
  - 복잡도 초과
  - 실사/3D drift 감지 후 재시도

newauto 대응 위치:

- `app/services/visual_planner.py`
- `app/services/image_prompting.py`
- `app/services/prompt_compiler.py`
- `app/services/prompt_quality.py`
- `app/services/image_quality.py`

## 3. 렌더링 백엔드 전략

V1: Whisk/Flow prompt-only

- 현재 안정화된 메인 이미지 엔진이 Whisk/Flow 브라우저 워커라면 이 경로를 우선한다.
- ControlNet, SDXL LoRA, local ComfyUI에 의존하지 않는다.
- 8GB VRAM 환경에서 Qwen/TTS/ComfyUI 경합이 재발하지 않는다.
- 실패 시 prompt를 더 단순화해 재시도한다.

V2: 로컬 ComfyUI 실험

- ControlNet Canny/Lineart/Scribble은 구조 고정에는 좋지만 메인 경로가 아니다.
- 로컬 GPU 여유가 있고 ControlNet 모델/노드가 설치된 경우에만 opt-in으로 사용한다.
- 운영 기본값으로 올리지 않는다.

결론:

`simple_diagram`의 성공 여부는 V1 prompt engineering과 planner vocab injection이 좌우한다.

## 4. Style Mode 정의

새 style mode:

`simple_diagram`

MakeLens config 예시:

```python
grok_whisk_sentence_scene_style_mode = "simple_diagram"
```

positive style guide:

```text
simple 2d explainer diagram, clean black outline, flat vector illustration,
minimal infographic style, one clear central metaphor, large readable shapes,
limited color palette, plain soft background, simple icon-like composition,
few objects only, no internal text
```

negative constraints:

```text
photorealistic, cinematic realism, complex background, clutter, tiny details,
readable text, fake text, broken letters, logo, watermark, messy handwriting,
dense crowd, duplicate characters, extra limbs, distorted hands, 3d render,
painterly texture, toy-like render, random car, random road, compass, checklist
```

Whisk/Flow prompt policy:

- 이미지를 “scene”보다 “diagram panel”로 지시한다.
- `one central object`, `two or three supporting icons`, `plain background`를 반복적으로 명시한다.
- “한국어 제목/라벨을 이미지 안에 넣어라”는 지시를 금지한다.
- 필요한 텍스트 정보는 subtitle layer에서 처리한다.

## 5. Planner 출력 스키마

`pipeline/sentence_scene_planner.py`에 추가할 권장 필드:

```json
{
  "core_meaning": "문장의 핵심 의미",
  "key_terms": ["핵심 키워드"],
  "diagram_subject": "중심 아이콘 또는 중심 캐릭터",
  "diagram_props": ["보조 아이콘 1", "보조 아이콘 2"],
  "diagram_relation": "arrow | scale | center_orbit | before_after | burden | flow | compare",
  "diagram_layout": "center_icon | left_right_compare | three_outputs | character_with_symbols | scale_balance | chase_burden",
  "visual_metaphor": "이미지 전체 은유",
  "avoid": ["피해야 할 요소"]
}
```

규칙:

- `diagram_props`는 최대 3개
- `diagram_subject`는 반드시 하나
- `diagram_relation`은 반드시 하나
- 추상어를 그대로 이미지에 넣지 말고 시각 기호로 변환

## 6. Diagram Vocab

추가 파일:

`storage/visual_vocab/diagram.json`

역할:

- 단순 치환 사전이 아니다.
- planner LLM system prompt에 few-shot example로 주입한다.
- LLM이 문맥에 맞춰 아이콘을 선택하도록 돕는다.

초기 vocab:

```json
{
  "ai": ["AI brain icon", "robot assistant", "node network"],
  "data_center": ["server stack", "cooling fan", "power plug"],
  "electricity": ["lightning bolt", "power meter", "factory chimney"],
  "country": ["simple map silhouette"],
  "comparison": ["balance scale", "left-right split"],
  "growth": ["upward arrow", "rising bar icon"],
  "uncertainty": ["question bubble", "foggy path"],
  "pressure": ["heavy backpack", "weight block"],
  "schedule": ["calendar check", "ticket"],
  "payment": ["credit card icon"],
  "message": ["envelope icon"],
  "documents": ["paper stack"],
  "research": ["magnifying glass", "document stack"],
  "automation": ["robot hand", "flow arrows", "gear icon"]
}
```

few-shot 예시:

- 문장: “AI가 정보를 정리하고 답을 만든다.”
  - subject: `AI brain icon`
  - props: `magnifying glass`, `document stack`, `checked paper`
  - relation: `three_outputs`
  - layout: `three_outputs`

- 문장: “데이터센터 전력 소비가 국가 단위 소비와 비교된다.”
  - subject: `balance scale`
  - props: `server stack`, `country map silhouette`, `lightning bolt`
  - relation: `scale`
  - layout: `left_right_compare`

- 문장: “AI 에이전트가 예약, 결제, 메시지를 처리한다.”
  - subject: `robot assistant`
  - props: `calendar check`, `credit card icon`, `envelope icon`
  - relation: `center_orbit`
  - layout: `center_icon`

## 7. Prompt Adapter 정책

`pipeline/image_prompt_adapter.py`에서 `style_mode == "simple_diagram"`일 때 전용 adapter를 사용한다.

템플릿:

```text
simple 2d explainer diagram, clean black outline, flat vector illustration,
{diagram_layout} layout, {diagram_subject} as the central visual idea,
{diagram_relation} relationship, supporting icons: {diagram_props},
plain soft background, limited color palette, large readable shapes,
few objects only, no internal text, no logo, no watermark
```

adapter 규칙:

- 대본 원문을 positive prompt에 직접 넣지 않는다.
- `core_meaning`은 prompt 설명으로만 쓰고, 이미지 요소는 `diagram_subject/props/relation/layout`에서만 가져온다.
- props가 4개 이상이면 상위 3개만 사용한다.
- prompt 길이가 길어지면 context 문장을 제거하고 구조 요소만 남긴다.
- negative constraints는 config의 기본값과 style mode 전용 금지어를 병합한다.

## 8. QA 및 Retry

새 issue code:

- `DIAGRAM_TOO_MANY_PROPS`
- `DIAGRAM_STYLE_CONFLICT`
- `DIAGRAM_RAW_TEXT_LEAK`
- `DIAGRAM_LAYOUT_MISSING`
- `DIAGRAM_SUBJECT_MISSING`
- `DIAGRAM_REALISM_DRIFT`
- `DIAGRAM_CLUTTER_HIGH`

Prompt-level QA:

- subject 없음 -> 실패
- layout 없음 -> 실패
- props 3개 초과 -> 단순화 후 재시도
- positive prompt에 `photorealistic`, `cinematic realism`, `3d render` 포함 -> 실패
- positive prompt에 대본 원문/한글 라벨 포함 -> 실패

Image-level QA:

- post render QA 또는 browser worker retry에서 처리
- OCR 또는 text detector가 내부 글자를 많이 감지하면 폐기
- 실사/3D 느낌이 강하면 `DIAGRAM_REALISM_DRIFT`
- 요소가 너무 많거나 배경이 복잡하면 `DIAGRAM_CLUTTER_HIGH`

Retry 정책:

1. props를 3개에서 2개로 줄인다.
2. 배경을 `plain soft background`로 강화한다.
3. `one central icon only`를 추가한다.
4. `no internal text, no labels, no letters`를 negative/positive 양쪽에 명시한다.

## 9. UI / Config

MakeLens config:

- `grok_whisk_sentence_scene_style_mode = "simple_diagram"`
- `grok_whisk_sentence_scene_negative_constraints`에 diagram negative 병합

UI:

- style preset 목록에 `Simple Diagram` 추가
- 기술/경제/설명형 콘텐츠 기본값은 `simple_diagram`
- 감성/에세이는 `k_webtoon` 또는 기존 editorial 유지

브라우저 워커 payload:

```json
{
  "style_mode": "simple_diagram",
  "negative_constraints": "...",
  "scene_plan": {
    "diagram_subject": "...",
    "diagram_props": ["...", "..."],
    "diagram_relation": "...",
    "diagram_layout": "..."
  }
}
```

## 10. 구현 순서

P0: Prompt-only V1

1. `config.py`에 `simple_diagram` style mode 추가
2. negative constraints에 diagram 금지어 병합
3. `storage/visual_vocab/diagram.json` 추가
4. `pipeline/sentence_scene_planner.py`에 diagram schema와 vocab few-shot 주입
5. `pipeline/image_prompt_adapter.py`에 simple diagram adapter 추가
6. prompt-level QA 추가
7. browser worker retry 사유에 diagram issue code 연결

P1: 운영 품질

1. post render QA와 OCR/text leak 검사 연결
2. clutter/realism drift 감지 후 자동 재시도
3. style mode UI 노출
4. 기술/경제/설명형 콘텐츠에 자동 style mode 추천
5. 생성 로그에 subject/layout/props/retry reason 저장

P2: ComfyUI/ControlNet 실험

1. ControlNet Canny/Lineart/Scribble readiness 감지
2. diagram sketch generator 추가
3. sketch 기반 ControlNet workflow 추가
4. 로컬 GPU 여유가 있을 때만 opt-in

## 11. Acceptance Criteria

V1 완료 조건:

- Whisk/Flow 경로에서 `simple_diagram`이 prompt-only로 동작한다.
- 문장 원문이 이미지 prompt에 직접 섞이지 않는다.
- 이미지 내부 텍스트 생성을 요구하지 않는다.
- planner 결과에 subject/layout/relation/props가 남는다.
- prompt adapter가 첨부 예시처럼 단순 도식형 prompt를 만든다.
- 재시도 시 더 단순한 prompt로 자동 축소된다.
- 로컬 ComfyUI를 켜지 않아도 동작한다.

V2 완료 조건:

- ControlNet 설치 환경에서만 opt-in으로 구조 스케치 기반 생성이 가능하다.
- 8GB VRAM 환경에서는 기본값으로 켜지지 않는다.

## 12. 결론

이 기능은 SDXL/ControlNet 기능으로 시작하면 다시 VRAM 경합과 설치 의존성에 묶일 가능성이 크다.

따라서 현재 운영 방향은 다음이 맞다.

1. Whisk/Flow 브라우저 워커에서 prompt-only V1을 먼저 완성한다.
2. Planner에 diagram vocab을 주입해 문맥 기반 도식 기획을 만든다.
3. Prompt adapter에서 simple diagram 스타일을 강제한다.
4. QA/retry로 텍스트 유출, 실사화, 복잡도 초과를 줄인다.
5. ControlNet은 나중의 선택적 고도화로만 둔다.
