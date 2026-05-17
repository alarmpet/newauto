# ChatGPT Image 2.0 Article Visual Quality Recovery Plan

## 1. 진단 대상

- 프로젝트: `3accf1ac492c`
- 영상: `C:\Users\petbl\newauto\storage\projects\3accf1ac492c\output.mp4`
- 기사 주제: 챗GPT 이미지 2.0 출시 후 이용자 증가, 이미지 내 텍스트 렌더링 개선, 한국 이용자의 사진 변환 활용
- 비교 기준: 우베 기사 프로젝트 `f8c0fd9c4455`

## 2. 결론

이번 영상의 이미지 품질이 우베 영상보다 나빠진 핵심 이유는 이미지 모델 자체보다 **시각 기획 단계가 무력화된 것**이다.

우베 영상은 `food_trend` 도메인 감지, `scene_visual_plan.json`, `storage/visual_vocab/food_trend.json`, 후보 점수 0.80대의 selected image 흐름이 유지되었다. 반면 이번 프로젝트는 최종 상태에서 `scene_visual_plan.json`이 없고, `disable_llm_visual_planner=True`가 fallback visual planner를 쓰는 대신 planner 전체를 우회했다. 그 결과 문장 2~6처럼 수치/텍스트 렌더링이 핵심인 장면도 프롬프트가 `browser window with terminal panel and automation cursor` 같은 일반 기술 프롬프트로 떨어졌다.

마지막 렌더에서는 일부 핵심 장면을 수동 다이어그램으로 급히 보정했지만, 이 보정은 생성 이미지와 스타일이 섞이고, 우베 영상처럼 자연스러운 도메인 전용 이미지 흐름을 만들지는 못했다.

## 3. 문장별 비교 분석

| # | 대본 문장 요지 | 현재 이미지 | 문제점 | 권장 이미지 방향 |
|---|---|---|---|---|
| 0 | 챗GPT 이미지 2.0이 공개 첫 주부터 관심 | 어두운 모니터/대시보드 | 제품 출시, 이미지 생성, 사용자 관심이 보이지 않고 일반 관제실처럼 보임 | 중앙에 `AI image model launch`를 상징하는 이미지 생성 캔버스, 업로드 사진, 생성 결과 카드 |
| 1 | 사진 한 장으로 원하는 스타일/분위기 반영 | 브라우저/터미널 UI | 사진 변환이라는 핵심을 놓침. 개발자 자동화처럼 보임 | 한 장의 입력 사진이 패션 화보/애니메이션/미니 캐릭터 카드로 분기되는 3분할 다이어그램 |
| 2 | DAU 전주 대비 60% 증가 | 수동 막대 다이어그램 | 의미는 맞지만 급히 만든 자산이라 생성 이미지와 스타일 불일치 | simple diagram preset으로 `DAU +60%`, 상승 막대, 사용자 아이콘, 전주/이번주 비교 |
| 3 | 신규 이용자 130% 증가 | 수동 막대 다이어그램 | 의미는 맞지만 장면 2와 스타일 반복, 모델 생성 결과가 아님 | `NEW USERS +130%`를 더 큰 성장 막대와 신규 사용자 아이콘으로 분리 |
| 4 | 두 개 상승 막대와 숫자 배지가 직관적 | 수동 KPI 카드 | 문장이 이미지 설명문처럼 들어가 영상 흐름상 중복됨 | 2~3번 장면과 합치거나, `60% vs 130%` 비교 카드 한 장으로 통합 |
| 5 | 이미지 안 텍스트 구현 능력 개선 | 수동 before/after 카드 | 뜻은 맞지만 너무 단순하고 “이미지 안 텍스트” 맥락이 약함 | 깨진 간판/포스터 before, 깨끗한 다국어 포스터 after |
| 6 | 한글·일본어·중국어 글자 깨짐 감소 | 수동 before/after 반복 | 5번과 거의 같은 이미지라 정보 밀도가 낮음 | 한국어/일본어/중국어 3개 문자 블록이 깨짐에서 정돈으로 바뀌는 비교 패널 |
| 7 | 한국 이용자의 패션 화보/애니/미니 캐릭터 활용 | 어두운 대시보드 | 가장 큰 mismatch 중 하나. 한국 이용자 활용 사례가 전혀 보이지 않음 | 스마트폰/사진 카드가 3개 스타일 결과로 변환되는 밝은 예시 이미지 |
| 8 | 장난감에서 창작/실무 도구로 이동 | 수동 tool-shift 다이어그램 | 의미는 맞지만 너무 건조하고 시각 장악력 약함 | 창작 워크플로우: 개인 사진 -> AI 편집 -> 썸네일/포스터/상업 이미지 결과 |
| 9 | 경쟁은 의도 시각화 정확도/속도로 이동 | 수동 워크플로우 | 의미는 맞지만 영어 텍스트 중심, 한국어 영상 톤과 어긋남 | `의도 -> AI -> 결과` 아이콘 다이어그램, 속도/정확도 배지, 텍스트 최소화 |

## 4. 우베 영상보다 나빠진 이유

### 4.1 `disable_llm_visual_planner`의 동작이 잘못됨

현재 `build_scene_visual_plan()` 자체는 `disable_llm_visual_planner=True`일 때 fallback plan을 반환할 수 있다. 하지만 `image_prompting.suggest_image_prompt_batch()`는 이 옵션이 켜져 있으면 `build_scene_visual_plan()` 호출 자체를 건너뛴다.

결과:

- fallback visual plan도 생성되지 않음
- `visual_plan` 필드가 manifest에 없음
- `composition_template`이 프롬프트에 반영되지 않음
- growth metric/text rendering vocab이 있어도 실제 이미지 프롬프트로 전달되지 않음

이번 manifest에서도 문장 2~6의 `visual_plan`은 비어 있고, `positive_prompt`는 반복적으로 브라우저/터미널 UI를 요구한다.

### 4.2 tech fallback vocab coverage가 아직 너무 일반적임

`storage/visual_vocab/tech.json`에 성장 지표와 텍스트 렌더링 vocab은 추가되어 있지만, planner 우회 때문에 사용되지 않았다. 또한 planner가 없을 때 `visual_brief` 단독 fallback은 여전히 다음과 같은 일반 기술 오브젝트로 쉽게 떨어진다.

- `browser window with terminal panel and automation cursor`
- `structured data table flowing out of a browser window`
- `neural network dashboard with glowing model graph`

AI 이미지 제품 기사에서는 “브라우저 자동화”보다 “이미지 생성 캔버스, 업로드 사진, 스타일 변환 카드, 텍스트 렌더링 before/after”가 기본이어야 한다.

### 4.3 점수 게이트가 의미 품질을 충분히 막지 못함

현재 선택된 생성 이미지 중 0, 1, 7번은 점수가 약 `0.653~0.656`이다. 우베 프로젝트 selected score는 `0.798~0.879`였다.

문제:

- `manual_art_directed=True`와 수동 다이어그램 보정이 섞이면서 최종 `validate_generated_image_mappings()`는 0 issues가 됨
- 하지만 0.65대 생성 이미지가 그대로 들어간 장면은 의미상 불량임
- 진단 리포트의 “0 issues”가 실제 시청 품질을 보장하지 못함

### 4.4 수동 다이어그램 fallback이 영상 스타일을 깨뜨림

숫자 장면은 수동 다이어그램으로 의미를 맞췄지만, 다음 문제가 남았다.

- ComfyUI 생성 이미지와 수동 PIL 다이어그램의 스타일이 다름
- 일부 다이어그램이 영어 텍스트 중심이라 한국어 영상과 어색함
- 수동 자산은 임시 응급처치이지, 자동 워크플로우의 정상 결과가 아님

### 4.5 source/script 인코딩 오류가 초반 파이프라인을 오염시킴

초기 프로젝트에서 `script.txt`와 title이 mojibake 상태로 한 번 저장되었다. 이후 대본은 UTF-8로 복구했지만 title은 여전히 깨져 있다.

영향:

- 도메인 감지 haystack에 깨진 title/source text가 섞일 수 있음
- LLM planner 입력이 깨진 문장을 읽으면 엉뚱한 도메인/템플릿을 생성할 수 있음
- 실제로 초반에는 댓글/정렬 도메인 템플릿이 섞였음

### 4.6 ComfyUI timeout 이후 복구 정책이 “품질 완료”가 아니라 “렌더 완료”에 치우침

마지막 장면에서 ComfyUI history timeout이 발생했고, 이후 수동 diagram fallback으로 렌더를 완료했다.

이번 요청은 최종 영상 생성이 목적이었기 때문에 렌더 완료는 맞지만, 품질 관점에서는 다음 정책이 필요하다.

- timeout 장면만 lightweight prompt-only retry
- 2회 실패 시 style-consistent diagram template generator
- 수동 fallback도 prompt manifest, visual plan, QA reason에 정식 기록
- fallback 사용 시 최종 리포트에서 “완전 성공”이 아니라 “render completed with fallback”으로 표시

## 5. 개선 계획

### P0. Planner 우회 버그 수정

목표: `disable_llm_visual_planner=True`는 visual planner 전체 비활성화가 아니라 **LLM만 비활성화하고 deterministic fallback planner는 사용**해야 한다.

작업:

1. `app/services/image_prompting.py`
   - `suggest_image_prompt_batch()`에서 `disable_llm_visual_planner=True`여도 `build_scene_visual_plan(project)`를 호출하도록 수정한다.
   - 옵션 이름이 헷갈리면 `disable_llm_visual_planner` 대신 내부 의미를 `use_fallback_visual_planner`로 명확히 해석한다.
2. `build_scene_visual_plan()`의 현재 동작은 유지한다.
   - 옵션이 켜져 있으면 `_normalize_entries(..., source="fallback")` 반환.
3. 테스트 추가:
   - `disable_llm_visual_planner=True`인 tech growth sentence가 `GrowthMetricComparison` visual plan을 manifest에 포함해야 한다.
   - 같은 조건에서 `positive_prompt`에 `two rising bars`, `numeric badges`, `60 percent`, `130 percent` 중 핵심 표현이 포함되어야 한다.

Acceptance:

- 이번 기사 문장 2~4가 자동 manifest에서 `GrowthMetricComparison`을 갖는다.
- 문장 5~6이 자동 manifest에서 `BeforeAfterTextRendering`을 갖는다.
- 문장 1/7이 `TransformationFlow`를 갖는다.

### P0. AI 이미지 제품 전용 tech vocab/template 추가

목표: AI 이미지 모델 기사에서 브라우저/터미널/서버 대시보드로 빠지는 것을 막는다.

작업:

1. `storage/visual_vocab/tech.json`
   - `AI image generation product launch`
   - `photo style transformation`
   - `growth metric comparison`
   - `multilingual text rendering`
   - `creative production workflow`
   항목을 별도 concept으로 강화한다.
2. `visual_planner._domain_vocab_tokens()`
   - tech domain에서도 sentence와 vocab keyword 매칭이 되면 generic tech object보다 vocab을 우선한다.
3. `visual_brief` tech fallback priority 조정
   - `사진`, `스타일`, `화보`, `애니메이션`, `캐릭터`, `텍스트`, `글자`, `%`, `이용자`, `DAU`는 browser automation보다 우선.

Acceptance:

- “사진 한 장”, “패션 화보”, “애니메이션”, “미니 캐릭터” 문장에서 `browser window with terminal panel`이 나오지 않는다.
- “전주 대비 60%”, “130%” 문장에서 dashboard가 아니라 simple metric diagram이 나온다.

### P0. 의미 점수 게이트 강화

목표: 0.65대 이미지를 최종 영상에 그대로 넣지 않는다.

작업:

1. `visual_relevance.py`
   - generated image score가 0.72 미만이면 tech/article diagram 프로젝트에서도 blocking issue로 처리.
   - `manual_art_directed=True`라도 generated metadata가 있는 이미지는 manual_light로 낮추지 않는다.
2. `candidate_reviews`
   - `strict_retry`, `borderline`, `manual_fallback`을 구분해서 리포트한다.
3. visual report
   - `meaning_score`와 `aesthetic_score`를 분리한다.
   - 현재처럼 수동 score 0.9로 덮어도, generated scene 0/1/7의 의미 부족은 리포트에 남긴다.

Acceptance:

- 0.65대 selected generated image가 있으면 render preflight에서 차단 또는 retry required.
- 수동 fallback이 있으면 최종 리포트에 fallback count가 표시된다.

### P1. Diagram style generator를 자동화

목표: 수동 PIL 급조가 아니라, 일관된 simple diagram renderer를 정식 도구로 만든다.

작업:

1. `app/services/diagram_assets.py` 추가
   - `GrowthMetricComparison`
   - `BeforeAfterTextRendering`
   - `TransformationFlow`
   - `CreativeWorkflow`
   템플릿을 지원한다.
2. 입력은 `VisualPlanEntry` 또는 `VisualBrief`.
3. 한글 영상용 텍스트 정책:
   - 영상 내부 텍스트는 가능한 숫자/짧은 영문 약어만 사용.
   - 필요 시 한국어 라벨은 자막과 겹치지 않는 상단/좌측에 짧게 배치.
4. 색/선/여백/폰트 스타일을 통일한다.

Acceptance:

- ComfyUI가 timeout되거나 simple diagram scene이 필요하면 같은 스타일의 deterministic diagram 이미지가 자동 생성된다.
- fallback 이미지도 `body_image_mappings`와 manifest에 정식 source로 기록된다.

### P1. ComfyUI timeout 복구 정책 개선

목표: timeout 후 전체 품질이 무너지지 않게 한다.

작업:

1. timeout 발생 시 해당 scene만 retry queue에 남긴다.
2. retry profile 순서:
   - `sdxl_standard` 1회
   - `sdxl_low_vram_lightning` 1회
   - deterministic diagram fallback
3. image worker 상태:
   - batch 진행 중 `body_image_state=done`처럼 보이지 않도록 수정한다.
   - progress는 0~100 사이로 clamp한다.
4. 실패/보정 원인을 `visual_mismatch_report`에 표시한다.

Acceptance:

- timeout이 나도 이미 성공한 scene mappings는 보존된다.
- 실패 scene만 재시도하거나 diagram fallback으로 닫힌다.
- 최종 상태가 “렌더 완료”와 “이미지 품질 완전 성공”을 구분한다.

### P1. 인코딩 방어

목표: mojibake 대본/제목이 planner에 들어가기 전에 막는다.

작업:

1. `source_draft_script`, `script`, `title` 저장 시 mojibake detector 적용.
2. `�`, `??`, `理`, `?대?`, `湲` 같은 패턴이 일정 비율 이상이면 저장/적용 전 차단.
3. PowerShell/stdin 경로로 한글을 넣을 때는 파일 기반 UTF-8 경로를 사용하도록 내부 작업 스크립트도 정리한다.

Acceptance:

- 깨진 한글 대본은 apply/render 이전 단계에서 오류로 잡힌다.
- visual planner는 깨진 문장을 입력받지 않는다.

### P2. 기사 유형별 visual strategy 분기

목표: 같은 tech라도 기사 성격에 맞는 이미지 전략을 선택한다.

분기:

- `ai_product_growth`: 제품 출시, 사용자 증가, 전환율, DAU, 신규 이용자
- `ai_capability_demo`: 기능 개선, 텍스트 렌더링, 스타일 변환, 예시 결과
- `infrastructure_tech`: GPU, 서버, 데이터센터, 모델 학습
- `browser_automation`: 브라우저, 터미널, CDP, 자동화

이번 기사는 `ai_product_growth + ai_capability_demo`이지 `browser_automation`이 아니다.

Acceptance:

- “챗GPT 이미지 2.0” 기사에서는 서버랙/터미널/브라우저 자동화가 기본 fallback으로 나오지 않는다.
- “Obscura/headless browser” 기사에서는 browser automation visual이 계속 사용된다.

## 6. 재생성 권장 워크플로우

1. P0 planner 우회 버그 수정.
2. tech vocab/template 강화.
3. 프로젝트 `3accf1ac492c`의 `title`, `script`, `scene_visual_plan.json`, `image_prompts_manifest.json` 재생성.
4. 이미지 재생성:
   - 0, 1, 7, 8, 9는 반드시 재생성.
   - 2~6은 diagram renderer 또는 simple diagram prompt로 통일 생성.
5. visual diagnostics 재생성.
6. selected score 기준:
   - generated image: `>= 0.72`
   - diagram fallback: source가 명확히 `deterministic_diagram`이어야 함
   - retry recommended: 0
7. TTS는 기존 full-passage OmniVoice 설정 유지.
8. 최종 렌더 후 contact sheet와 output.mp4를 함께 검수.

## 7. 우선순위 요약

P0:

- `disable_llm_visual_planner=True` 시 fallback planner 사용
- AI 이미지 제품용 tech vocab/template 활성화 및 visual_brief 우선순위 보정
- generated image 0.72 미만 차단

P1:

- mojibake 입력 차단
- deterministic diagram asset generator 정식화
- ComfyUI timeout scene-only retry/fallback
- image worker progress/state 정합성 수정

P2:

- tech 기사 하위 전략 분기
- visual report에 fallback/meaning/aesthetic score 분리 표시

## 8. 피드백 반영 업데이트

`chatgpt-image2-feedback.md` 검토 결과, 기존 계획의 큰 진단은 유지하되 실행 우선순위를 다음처럼 조정한다.

### 8.1 가장 먼저 고칠 P0는 두 가지다

즉시 품질을 올리는 최소 수정은 다음 두 개다.

1. `image_prompting.py`의 `disable_llm_visual_planner` short-circuit 제거
2. `visual_relevance.py`의 generated image 0.72 미만 차단 정책 명확화

이 두 가지가 먼저다. `tech.json`에는 이미 `AI image style transformation from one photo`, `AI product user growth metrics`, `multilingual image text rendering improvement` 같은 핵심 vocab이 들어가 있다. 따라서 vocab을 새로 많이 추가하는 것보다, **이미 있는 vocab이 실제 manifest까지 도달하게 만드는 것**이 더 급하다.

### 8.2 `disable_llm_visual_planner`의 의미를 재정의한다

현재 코드상 의도는 다음에 가깝다.

- LLM planner는 끈다.
- deterministic fallback planner는 켠다.

하지만 실제 `suggest_image_prompt_batch()`에서는 옵션이 켜지면 `build_scene_visual_plan()` 호출 자체를 건너뛴다. 이것이 이번 영상의 직접 원인이다.

수정 후 동작:

- `disable_llm_visual_planner=True`라도 `build_scene_visual_plan(project)`는 호출한다.
- `build_scene_visual_plan()` 내부에서 현재 구현대로 fallback plan을 반환한다.
- manifest에는 `visual_plan.source="fallback"`과 `composition_template`이 반드시 들어간다.

테스트 조건:

- `disable_llm_visual_planner=True`
- sentence: `일일 활성 사용자 수는 전주 대비 60% 이상 증가했습니다.`
- expected:
  - `visual_plan.composition_template == "GrowthMetricComparison"`
  - prompt에 `rising bars`, `numeric badges`, `60 percent` 계열 표현 포함

### 8.3 tech vocab 작업은 “추가”보다 “우선순위 보정”이 중요하다

기존 계획의 “AI 이미지 제품용 vocab/template 강화”는 유지하되, 실제 작업은 다음 순서로 좁힌다.

1. 이미 추가된 tech vocab이 planner fallback에서 우선 매칭되는지 확인한다.
2. `visual_brief` fallback이 `browser window with terminal panel`로 떨어지기 전에 다음 키워드를 먼저 잡는다.
   - `사진 한 장`
   - `스타일`
   - `패션 화보`
   - `애니메이션`
   - `미니 캐릭터`
   - `텍스트`
   - `글자 깨짐`
   - `한글`
   - `일본어`
   - `중국어`
   - `DAU`
   - `%`
   - `신규 이용자`
3. `browser automation` vocab은 Obscura/headless browser 같은 기사에서만 강하게 작동하도록 strategy를 분리한다.

### 8.4 mojibake 방어는 P1로 내리되 반드시 수행한다

피드백대로 mojibake 방어는 즉시 영상 품질을 복구하는 핵심 P0라기보다는 파이프라인 안전장치에 가깝다. 따라서 우선순위는 P1로 조정한다.

다만 이번 프로젝트에서 실제로 title/script가 한 번 깨졌고, 깨진 입력이 planner를 오염시킨 전례가 있으므로 작업 자체는 유지한다.

적용 위치:

- source draft apply 직전
- script save 직전
- project title update 직전
- visual planner 입력 직전 최종 guard

### 8.5 diagram generator는 P0 이후 별도 사이클로 구현한다

수동 PIL 보정은 자동화 워크플로우 목적과 맞지 않는다. 하지만 deterministic diagram generator는 템플릿, 레이아웃, 폰트, 안전 여백, 자막 충돌 회피까지 설계해야 하므로 P0 버그 수정 뒤 P1 사이클로 진행한다.

권장 구현 순서:

1. `GrowthMetricComparison`만 먼저 구현
2. `BeforeAfterTextRendering` 추가
3. `TransformationFlow` 추가
4. `CreativeWorkflow` 추가

이렇게 해야 “다이어그램 품질 개선”이 또 다른 임시 코드 덩어리로 변하지 않는다.

### 8.6 업데이트된 실행 순서

1. `image_prompting.py`에서 visual planner short-circuit 제거
2. `visual_relevance.py`에서 0.72 미만 generated image 차단/strict retry required 명확화
3. tech fallback priority 보정
4. 관련 단위 테스트 추가
5. `3accf1ac492c`의 scene visual plan, prompt manifest 재생성
6. 0/1/7/8/9 이미지 재생성
7. 2~6은 simple diagram prompt로 재생성하거나, P1 diagram generator 구현 후 재생성
8. diagnostics/contact sheet로 재검수

## 9. 2026-05-02 P0 구현 반영

완료:

- [x] `app/services/image_prompting.py`에서 `disable_llm_visual_planner=True`일 때 `build_scene_visual_plan()` 자체를 건너뛰던 short-circuit을 제거했다.
- [x] `disable_llm_visual_planner=True`의 의미를 "LLM planner만 끄고 deterministic fallback planner는 사용"으로 정리했다.
- [x] `suggest_image_prompt_batch()`가 fallback `visual_plan.source="fallback"` 및 `composition_template`을 prompt payload까지 전달한다.
- [x] simple diagram 적용 시 tech `composition_template`이 있으면 `GrowthMetricComparison` 같은 구조화 템플릿을 generic diagram vocab 아이콘으로 덮어쓰지 않게 했다.
- [x] `app/services/visual_relevance.py`에서 generated image metadata가 있는 mapping은 `manual_art_directed`보다 먼저 `strict_generated`로 검사한다.
- [x] tech/news/simple_diagram/composition_template 장면은 generated image final score `0.72` 미만이면 blocking issue로 처리한다.
- [x] hybrid/manual-art-directed 상태라도 generated mapping의 hard Vision QA 실패는 최종 차단 이슈로 남긴다.
- [x] fallback planner 전파, tech final threshold, generated metadata strict validation 회귀 테스트를 추가했다.

이번 P0 코드 패스 밖에 남은 작업:

- [ ] 해당 기사 프로젝트 자산 및 contact sheet 재생성.
- [ ] P1 deterministic diagram renderer 템플릿 구현.
- [ ] P1 source/title/script 저장 경계의 mojibake guard 구현.
