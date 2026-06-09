# Editorial Symbolic Image Upgrade Plan

작성일: 2026-05-02

대상 문제:

- `simple_diagram`은 이해는 쉽지만, 영상 이미지로는 너무 단순하고 반복적인 도형처럼 보임.
- ComfyUI/SDXL 프롬프트는 고품질 장면을 만들 수 있지만, 프롬프트가 복잡해지면 작은 아이콘, 인포그래픽, 흐릿한 노드, 추상 도형으로 무너짐.
- 사용자가 원하는 방향은 `ube` 영상처럼 이미지 퀄리티와 장면성이 있으면서도, 문장 핵심 키워드 1~2개가 즉시 읽히는 이미지.

## 1. 첨부 이미지 기준 분석

첨부 예시는 단순한 “아이콘 다이어그램”이 아니라 다음 공통점을 가집니다.

1. 실제 장면 기반
   - 마트 진열대, 보라색 제품 진열, 디저트 플레이트처럼 현실적인 공간과 물체가 먼저 보임.
   - 시청자는 설명을 읽기 전에 “식품, 제품 출시, 말차/우베”라는 맥락을 바로 감지함.

2. 핵심 키워드가 1~2개로 제한됨
   - 이미지 전체가 많은 개념을 설명하지 않음.
   - 예: 보라색 제품군, 말차와 우베 색 대비, 식품 매대.

3. 장면은 풍부하지만 의미는 단순함
   - 상품 수는 많아도 모두 같은 카테고리라 시각 노이즈가 적음.
   - 반대로 현재 AI 정책 영상의 실패 이미지는 서로 다른 작은 아이콘과 도형이 많아 하나의 장면으로 읽히지 않음.

4. 자막과 이미지의 역할이 분리됨
   - 이미지 안에 복잡한 텍스트를 넣지 않음.
   - 문장의 상세 정보는 자막/음성이 담당하고, 이미지는 핵심 분위기와 키워드를 담당함.

결론:

> 목표 스타일은 `simple_diagram`이 아니라 `editorial_symbolic`이다.  
> “현실감 있는 단일 장면 + 핵심 상징 1~2개 + 텍스트 최소화”가 기준이다.

## 2. 현재 코드베이스 문제

### 2.1 `simple_diagram`은 최후의 안전장치에 가깝다

관련 파일:

- `app/services/image_prompting.py`
- `app/services/prompt_compiler.py`
- `app/services/image_quality.py`
- `app/services/visual_relevance.py`

현재 `simple_diagram`은 다음 특징을 강제한다.

- `simple flat 2d explainer diagram`
- `maximum two large symbols`
- `no small icons`
- `plain background`

이 방식은 실패 방지에는 좋지만, 사용자가 원하는 `ube`식 장면 품질과는 충돌한다.

### 2.2 AI 정책 도메인이 장면형 vocab을 갖고 있지 않음

현재 `storage/visual_vocab/ai_policy_conflict.json`은 다음처럼 상징 중심이다.

- government shield
- AI company cube
- stop button
- warning divider
- hearing podium

하지만 장면형 이미지에는 다음 같은 구체적 공간이 필요하다.

- 국회 청문회장
- 정부 브리핑룸
- AI 연구실 또는 서버룸
- 백악관 앞 차단선
- 보안 검토 테이블
- 항공기와 타깃을 보여주는 군사 브리핑 보드

### 2.3 후보 선택 점수는 “의미 포함”을 보지만 “좋은 장면성”을 충분히 보지 못함

현재 QA는 다음은 어느 정도 잡는다.

- 너무 복잡한 다이어그램
- 작은 아이콘 그리드
- 낮은 후보 점수
- 키워드 누락

하지만 다음은 별도 점수가 약하다.

- 사진/일러스트로서의 장면 몰입감
- 중앙 주제의 명확성
- 도형만 있는지, 실제 공간이 있는지
- 프롬프트가 너무 아이콘 중심으로 치우쳤는지

### 2.4 직접 생성한 `simple_direct_scene`은 방향성 검증용이지 최종 스타일이 아님

직접 만든 이미지의 장점:

- 문장별 핵심 키워드는 잘 읽힘.
- TTS/렌더 테스트 안정성은 확보됨.

한계:

- 영상 이미지로서의 질감이 없음.
- 장면이 아니라 슬라이드에 가까움.
- 여러 장면이 비슷한 도형 반복으로 보임.

## 3. 목표 스타일 정의

새 스타일 프리셋:

`editorial_symbolic`

정의:

- 현실적인 장면 또는 고품질 editorial illustration을 기본으로 함.
- 핵심 상징은 1~2개만 강하게 배치함.
- 다이어그램, 포스터, 작은 노드, 텍스트 라벨은 금지함.
- 장면 안의 물체/공간이 문장의 핵심 키워드를 바로 연상시켜야 함.

프롬프트 원칙:

```text
one high-quality editorial scene,
one clear subject,
one or two symbolic objects only,
real place or product-like setting,
cinematic but clean composition,
no text, no dashboard, no tiny icons
```

예시:

- 정부와 AI 기업 갈등:
  - `a government briefing room table facing a glowing AI model cube behind glass`
- 국방장관 비판:
  - `a senate hearing room with one empty podium and a red warning folder aimed at an AI cube`
- 백악관 제동:
  - `White House security gate with a red stop barrier blocking a glowing AI network sphere`
- 항공기 목표물 비유:
  - `military briefing board showing a simplified aircraft silhouette and target marker`

## 4. 구현 계획

### P0. `editorial_symbolic` 스타일 프리셋 추가

파일:

- `app/static/index.html`
- `app/static/app.js`
- `app/routers/projects.py`
- `app/services/image_prompting.py`

작업:

1. 스타일 셀렉트에 `Editorial Symbolic` 추가.
2. `STYLE_PRESET_OVERRIDES`에 `editorial_symbolic` 추가.
3. `simple_diagram` 자동 추천 대신 도메인별 추천을 분리.
   - 뉴스/기술/정책: 기본 추천 `editorial_symbolic`
   - 댓글 관리/숫자 비교/차트형 설명: `simple_diagram`
   - 식품/제품/라이프스타일: `food_trend_editorial`

수용 기준:

- UI에서 `Editorial Symbolic` 선택 가능.
- 선택 시 프롬프트에 `high-quality editorial illustration`, `one clear subject`, `one or two symbolic objects`가 들어감.
- `simple flat diagram` 문구는 들어가지 않음.

### P0. AI 정책 도메인용 장면 vocab 추가

파일:

- `storage/visual_vocab/ai_policy_conflict.json`
- `app/services/visual_planner.py`

추가할 vocab 구조:

```json
{
  "concept": "white house blocks ai model spread",
  "keywords": ["백악관", "제동", "확산", "AI 모델"],
  "scene": "White House security gate with one red stop barrier",
  "hero_object": "glowing AI network sphere",
  "symbol": "red stop barrier",
  "relation": "the barrier blocks the AI model from spreading"
}
```

필수 concept:

- government vs AI company
- senate hearing criticism
- white house access restriction
- defense decision authority
- aircraft target analogy
- AI model spread blocked

수용 기준:

- AI 정책 문장마다 `scene`, `hero_object`, `symbol` 중 최소 2개가 visual plan에 들어감.
- `government shield`, `AI cube` 같은 순수 아이콘만 남는 fallback 비율을 줄임.

### P0. 프롬프트 컴파일러를 “장면 + 상징” 구조로 분리

파일:

- `app/services/image_prompting.py`
- `app/services/prompt_compiler.py`

새 컴파일 규칙:

1. `scene_anchor`
   - 현실/일러스트 배경.
   - 예: `senate hearing room`, `White House security gate`, `military briefing room`.

2. `hero_subject`
   - 이미지의 주인공.
   - 예: `glowing AI model cube`, `red stop barrier`, `aircraft silhouette`.

3. `symbolic_marker`
   - 핵심 의미를 돕는 보조 상징 1개.
   - 예: `warning folder`, `target marker`, `locked access gate`.

금지:

- `many nodes`
- `complex infographic`
- `dashboard`
- `flowchart`
- `tiny labels`
- `multiple panels`
- `generic shield icon only`
- `flat icon only`

수용 기준:

- prompt 길이는 900자 이하.
- `scene_anchor`가 없는 프롬프트는 품질 경고.
- `must_show`는 최대 2개.

### P0. `simple_direct_scene` 임시 우회 제거 또는 opt-in 처리

현재 직접 생성 방식은 테스트 안정성에는 도움이 됐지만, 최종 자동화 방향으로 두면 품질이 낮아진다.

작업:

- `simple_direct_diagram`은 `debug_only` 또는 `fallback_when_generation_failed`로만 사용.
- 일반 워크플로우는 ComfyUI/Whisk/Flow 후보 중 `editorial_symbolic` 프롬프트로 생성.

수용 기준:

- 기본 자동 생성에서 코드 기반 단순 PNG를 쓰지 않음.
- 단, ComfyUI 실패 시 진단용 placeholder로만 사용 가능.

### P1. 후보 선택 점수에 “editorial scene quality” 추가

파일:

- `app/services/comfyui_pipeline.py`
- `app/services/image_quality.py`
- `tests/test_candidate_selection.py`

새 점수 요소:

- `scene_anchor_score`: 장면 배경이 있는가.
- `subject_focus_score`: 중앙 주제가 화면을 충분히 차지하는가.
- `symbol_count_score`: 핵심 상징이 1~2개인가.
- `diagram_penalty`: 작은 노드, 대시보드, 복잡한 인포그래픽이면 감점.
- `flat_shape_penalty`: 단순 도형만 있고 장면성이 없으면 감점.

수용 기준:

- 도형만 있는 이미지가 고점으로 선택되지 않음.
- 장면성이 있는 후보가 키워드 점수와 함께 우선 선택됨.

### P1. 도메인별 스타일 추천 정책 재정리

파일:

- `app/services/image_prompting.py`
- `app/static/app.js`

정책:

| 도메인 | 기본 추천 |
|---|---|
| food_trend | `food_trend_editorial` |
| ai_policy_conflict | `editorial_symbolic` |
| tech news | `editorial_symbolic` |
| 숫자 비교/통계 | `simple_diagram` |
| 댓글/여론 흐름 | `simple_diagram` 또는 `editorial_symbolic` 선택 |
| 에세이 | `k_webtoon` 또는 `editorial_symbolic` |

수용 기준:

- “정책 갈등” 같은 기사에서 기본이 `simple_diagram`으로 떨어지지 않음.
- 사용자가 원하면 수동으로 `simple_diagram` 선택 가능.

### P2. Vision QA V2: 멀티모달 선택 검토

현재 텍스트/휴리스틱 QA만으로는 “좋은 이미지 느낌”을 완벽히 판단하기 어렵다.

V2 옵션:

- Gemini/Gemma multimodal 또는 경량 caption 모델로 후보 2~3장을 평가.
- 질문:
  - “이 이미지는 문장 핵심 키워드 1~2개를 직관적으로 보여주는가?”
  - “이미지가 너무 도형/아이콘만 있는가?”
  - “작은 노드/텍스트/복잡한 다이어그램이 많은가?”

단, 비용과 시간 때문에 기본값은 off.

## 5. 이번 AI 정책 영상에 대한 재생성 목표

현재 `simple_direct_scene`을 최종으로 보지 않고, 다음 방향으로 재생성한다.

| 장면 | 새 이미지 방향 |
---:|---|
| 0 | 정부 브리핑룸 테이블 위에 빛나는 AI 큐브가 놓이고, 맞은편에 정부 문서철이 놓인 장면 |
| 1 | 붉은 경고등이 켜진 정책 상황실, 중앙에 AI 모델 큐브 하나 |
| 2 | 청문회장 단상과 백악관 차단선 이미지를 한 화면에 과하지 않게 배치 |
| 3 | 상원 청문회장, 마이크 앞 빨간 경고 문서와 AI 큐브 |
| 4 | AI 기업 회의실 테이블 위 잠긴 권한 카드와 AI 모델 큐브 |
| 5 | 군사 브리핑 보드에 항공기 실루엣과 타깃 표시 |
| 6 | 백악관 보안 게이트 앞 빨간 차단막이 AI 네트워크 구체를 막는 장면 |

핵심:

- 인물 얼굴은 최소화.
- 텍스트 라벨은 금지.
- 장면은 고품질 editorial illustration.
- 핵심 오브젝트는 1~2개.

## 6. 검증 기준

자동 검증:

- prompt must_show 개수 `<= 2`
- prompt에 scene anchor 존재
- prompt에 금지어 없음: `dashboard`, `flowchart`, `tiny icons`, `complex infographic`, `flat icon only`
- 후보 score `>= 0.72`
- `retry_recommended=false`
- final selected image에 `DENSE_DIAGRAM_CLUTTER`, `TINY_ICON_GRID`, `GENERIC_DASHBOARD_LAYOUT` 없음

수동 검증:

- contact sheet만 봐도 장면별 핵심이 구분돼야 함.
- 7장 중 5장 이상이 “도형 슬라이드”가 아니라 “장면 이미지”로 보여야 함.
- 자막 없이도 대략 `정부 vs AI`, `청문회 비판`, `백악관 제동`, `항공기 목표물 비유`가 읽혀야 함.

## 7. 권장 작업 순서

1. `editorial_symbolic` 스타일 프리셋 추가.
2. AI 정책 vocab에 `scene/hero_object/symbol` 필드 확장.
3. `visual_planner.py`에서 새 vocab 필드를 `VisualBrief`/`VisualPlanEntry`로 매핑.
4. `prompt_compiler.py`에 `_editorial_symbolic_positive_slots()`와 negative 분기 추가.
5. `image_quality.py`에 `editorial_symbolic` 휴리스틱 점수 공식 추가.
6. candidate scoring에 도형-only 감점과 scene quality 보상 추가.
7. AI 정책 기사 1개로 이미지 2후보씩 재생성.
8. contact sheet 확인 후 최종 렌더.

## 8. 예상 효과

- `simple_direct_scene`보다 훨씬 영상 이미지답게 보임.
- 기존 ComfyUI 실패처럼 복잡한 인포그래픽으로 흐르는 문제를 줄임.
- `ube` 영상처럼 구체적인 장면성이 살아남.
- 문장 핵심 키워드는 1~2개만 유지되어 시청자가 즉시 이해 가능.

## 9. Review 반영 보완 사항

검토 문서:

`C:\Users\petbl\.gemini\antigravity\brain\bb8ee67d-7b3f-4839-868e-56ead3110943\editorial-symbolic-image-upgrade-review.md`

리뷰 결론:

- 방향성은 맞지만, 현재 계획은 구현 시 어느 파일의 어떤 helper가 어떤 필드를 받을지 덜 구체적이다.
- 특히 `prompt_compiler.py`, `visual_planner.py`, `image_quality.py`의 실제 구조에 맞춘 세부 설계가 필요하다.
- Vision QA V2는 비용/VRAM 리스크가 있으므로 기본 경로가 아니라 opt-in 디버그 경로로 제한해야 한다.

### 9.1 `prompt_compiler.py` 전용 helper 명시

현재 구조:

- `compile_positive_prompt()`는 도메인별 helper를 통해 prompt slot을 만든다.
- food trend는 `_food_trend_positive_slots()`처럼 별도 helper를 쓰는 패턴이 이미 있다.

반영 계획:

1. `_editorial_symbolic_positive_slots(brief, style_hint)` 추가.
2. `compile_positive_prompt()`에서 다음 조건 중 하나면 해당 helper로 분기.
   - `style_preset=editorial_symbolic`이 rationale에 있음
   - `brief["domain"] == "ai_policy_conflict"`이고 simple diagram이 아닌 경우
3. helper는 다음 slot만 조합한다.
   - `scene_anchor`: 실제 배경/공간
   - `hero_subject`: 화면 중심 대상
   - `symbolic_marker`: 보조 상징 0~1개
   - `composition`: cinematic editorial illustration, clean subject focus
4. `compile_negative_prompt()`에도 `editorial_symbolic` 분기 추가.

필수 negative:

```text
dashboard, flowchart, infographic poster, tiny icons, tiny labels,
multiple panels, flat icon only, generic shield icon only,
empty diagram, abstract geometry only, unreadable text, logo, watermark
```

수용 기준:

- `editorial_symbolic` prompt는 `simple flat 2d explainer diagram`을 포함하지 않는다.
- positive prompt에 `scene_anchor`가 반드시 포함된다.
- `must_show`는 최대 2개만 prompt 앞쪽에 배치된다.

### 9.2 `visual_planner.py`와 vocab schema 매핑 명확화

현재 구조:

- `ai_policy_conflict.json`은 `icon`, `support`, `relation`, `composition_template` 중심이다.
- `_repair_ai_policy_conflict_entry()`는 이 값을 `primary_keywords`, `must_show`, `visual_metaphor`로 보정한다.

확장 schema:

```json
{
  "concept": "white house blocks ai model spread",
  "keywords": ["white house", "blocked", "spread", "백악관", "제동", "확산"],
  "scene": "White House security gate",
  "hero_object": "glowing AI network sphere",
  "symbol": "red stop barrier",
  "relation": "the barrier blocks the AI model from spreading",
  "composition_template": "EditorialAccessBarrier"
}
```

매핑 규칙:

- `scene` -> `VisualBrief.scene` 또는 `VisualPlanEntry.visual_metaphor`의 배경 anchor
- `hero_object` -> `primary_prop`
- `symbol` -> `secondary_prop`
- `relation` -> `action`
- `composition_template` -> 기존 필드 유지

추가 방침:

- `VisualBrief` 타입 자체에 새 필드를 무리하게 늘리기보다, P0에서는 기존 필드에 안정적으로 매핑한다.
- P1에서 타입 확장이 필요하면 `scene_anchor`, `hero_subject`, `symbolic_marker`를 `app/types.py`에 `NotRequired[str]`로 추가한다.

수용 기준:

- AI 정책 문장의 visual plan entry에는 순수 아이콘 단어만 남지 않는다.
- 최소 하나의 실제 공간 표현이 들어간다.
  - 예: `government briefing room`, `senate hearing room`, `White House security gate`, `military briefing board`.

### 9.3 `image_quality.py` scoring 공식 구체화

현재 구조:

- `analyze_image_quality()`는 entropy, contrast, edge detail, exposure, dominant area, component count 등을 계산한다.
- `simple_diagram`, `food_trend_editorial`, `editorial_science` 같은 style mode별 블록을 추가할 수 있다.

반영 계획:

`elif style_mode == "editorial_symbolic":` 블록 추가.

점수 요소:

- `editorial_subject_area`
  - `dominant_area`가 너무 작으면 감점.
  - 너무 큰 단일 도형만 있으면 별도 감점 후보.
- `editorial_scene_detail`
  - entropy와 contrast가 너무 낮으면 “도형만 있는 슬라이드” 가능성이 높으므로 감점.
- `editorial_clutter_control`
  - component_count가 너무 높으면 복잡한 인포그래픽/대시보드로 보고 감점.
- `editorial_flat_shape_penalty`
  - edge density는 낮고 dominant_area만 높으면 단순 도형으로 보고 감점.

초기 기준값:

```text
dominant_area < 0.035 -> EDITORIAL_SUBJECT_TOO_SMALL
entropy_score < 0.30 and contrast_score < 0.30 -> EDITORIAL_SCENE_TOO_FLAT
component_count > 36 and dominant_area < 0.09 -> EDITORIAL_CLUTTERED_SYMBOLS
edge_density < 0.025 and entropy_score < 0.35 -> EDITORIAL_FLAT_SHAPE_ONLY
```

수용 기준:

- `simple_direct_scene` 같은 도형 슬라이드는 고점으로 선택되지 않는다.
- 장면 배경이 있고 중심 오브젝트가 분명한 후보가 더 높은 점수를 받는다.

### 9.4 Candidate selection과 ComfyUI pipeline 연결

파일:

- `app/services/comfyui_pipeline.py`
- `app/workers/image_worker.py`
- `tests/test_candidate_selection.py`

반영 계획:

1. `visual_brief.rationale` 또는 style preset이 `editorial_symbolic`이면 `analyze_image_quality(..., style_mode="editorial_symbolic")` 사용.
2. 후보 점수 계산에서 다음 issue는 강한 penalty 적용.
   - `EDITORIAL_FLAT_SHAPE_ONLY`
   - `EDITORIAL_CLUTTERED_SYMBOLS`
   - `GENERIC_DASHBOARD_LAYOUT`
   - `TINY_ICON_GRID`
3. retry prompt repair에서는 단순히 “더 심플하게”가 아니라 “real editorial scene anchor”를 강화.

repair 예시:

```text
Regenerate as a real editorial scene with one clear environment,
not a diagram slide. Keep only one hero object and one symbolic marker.
```

### 9.5 Vision QA V2는 opt-in으로 제한

리뷰 의견 반영:

- 로컬 multimodal LLM은 8GB VRAM 환경에서 ComfyUI/OmniVoice와 경합할 수 있다.
- API 방식도 비용과 지연 시간이 증가한다.

정책:

- 기본 Autopilot에서는 Vision QA V2 off.
- UI/옵션 이름:
  - `vision_qa_mode: "off" | "heuristic" | "multimodal_debug"`
- `multimodal_debug`는 수동 진단/디버그 렌더에서만 허용.
- 자동 재생성 루프에서는 V1 heuristic까지만 사용.

수용 기준:

- 기본 1~2분 테스트 영상 생성 시간이 Vision QA 때문에 늘어나지 않는다.
- OOM 방지를 위해 multimodal_debug 실행 전 GPU guard 확인이 필요하다.

### 9.6 최종 반영 우선순위 재정리

P0:

1. `editorial_symbolic` style preset 추가.
2. `ai_policy_conflict.json`에 `scene/hero_object/symbol` 추가.
3. `visual_planner.py`에서 새 schema를 기존 brief 필드로 매핑.
4. `prompt_compiler.py`에 `_editorial_symbolic_positive_slots()`와 negative 분기 추가.
5. `image_prompting.py` 추천 정책을 `ai_policy_conflict -> editorial_symbolic`으로 변경.

P1:

1. `image_quality.py`에 `editorial_symbolic` heuristic scoring 추가.
2. candidate scoring/repair loop에 editorial issue code 반영.
3. AI 정책 기사로 후보 2장씩 재생성 후 contact sheet 확인.

P2:

1. `Vision QA V2`를 opt-in debug mode로만 추가.
2. 비용/시간/VRAM 로그를 리포트에 남김.

## 10. Implementation Status 2026-05-03

Completed:

- [x] Added `editorial_symbolic` to the feature settings API allowlist and the Step 2 style preset selector.
- [x] Changed automatic style recommendation so tech / AI policy conflict content uses `editorial_symbolic`, while comment-management explainer content can still use `simple_diagram`.
- [x] Added an `editorial_symbolic` style template and prompt compiler branch built around `scene_anchor`, `hero_subject`, and `symbolic_marker`.
- [x] Added editorial-symbolic negative prompt policy to block dashboard, flowchart, tiny-icon, flat-icon-only, and abstract-geometry drift.
- [x] Extended `ai_policy_conflict` vocab with concrete `scene`, `hero_object`, and `symbol` fields.
- [x] Updated visual planner fallback / repair mapping so AI policy conflict plans prefer real scene anchors such as White House security gate, senate hearing room, government briefing room, and military briefing board.
- [x] Added `editorial_symbolic` heuristic QA in `image_quality.py` for flat-shape-only, cluttered-symbol, small-subject, and too-flat-scene cases.
- [x] Connected ComfyUI candidate import scoring to use `style_mode="editorial_symbolic"` for `ai_policy_conflict` and `style_preset=editorial_symbolic`.
- [x] Added regression tests for prompt compiler, image quality, feature settings, and image prompting.

Verification:

- [x] `omnivoice_env\Scripts\python.exe -m unittest tests.test_prompt_compiler tests.test_image_quality tests.test_feature_workflow tests.test_image_prompting`
- [x] `omnivoice_env\Scripts\python.exe -m mypy app`
- [x] `omnivoice_env\Scripts\python.exe -m compileall app tests`
