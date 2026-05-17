# 기사 영상 이미지 매칭 붕괴 원인 분석 및 복구 계획서

대상 프로젝트: `9a63dd20f4c0`  
대상 기사: `https://n.news.naver.com/mnews/article/015/0005282494`  
작성 목적: 대본과 이미지의 매칭 실패, 장면 스타일 붕괴, 품질 저하가 왜 반복되는지 코드베이스와 실제 워크플로우를 기준으로 분석하고, 재발 방지용 개선 계획을 정의한다.

## 1. 문제 요약

현재 파이프라인의 핵심 문제는 "이미지 생성 모델이 못 그린다"가 아니다.  
실제 원인은 다음 4단계가 연쇄적으로 무너지는 구조에 있다.

1. 문장 의미를 시각 개념으로 바꾸는 단계에서 핵심 의미가 사라진다.
2. 사라진 자리를 generic fallback이 메우면서 장면이 평준화된다.
3. 후보 선택 점수는 실제 이미지 의미보다 프롬프트 자기일치에 더 끌린다.
4. 복구 루프도 망가진 의미를 기준으로 돌기 때문에 엉뚱한 이미지를 더 강화한다.

그래서 결과적으로 다음 같은 현상이 나온다.

- 금융 기사 첫 문장이 계곡/돌담 같은 무관한 풍경 이미지로 선택된다.
- 복잡한 금융 과제를 설명해야 할 문장이 체크리스트 든 스틱맨으로 수렴한다.
- "일부 금융사는 속도를 늦추고, 다른 금융사는 계속 투자한다" 같은 문장이 시계, 체크리스트, 추상 기호로 치환된다.
- 한 번 generic drift가 시작되면 여러 문장에서 비슷한 구도와 비슷한 잘못된 소품이 반복된다.

## 2. 실제 증상

이번 프로젝트에서 확인된 대표 사례:

### 사례 A. 문장 0

문장:

> 한때 금융계를 바꿀 '게임 체인저'로 불렸던 양자 컴퓨팅 기술.

실제 선택 결과:

- 선택 이미지: `autopilot_scene_000_00011_.png`
- 선택 점수: `0.45`
- 선택 프롬프트: `glowing circuit board`, `spotlight`, `essay_editorial`

문제:

- "금융계", "게임 체인저", "양자 컴퓨팅"의 관계가 아니라, 추상적 회로판 메타포로 축약됨
- 결과 화면은 기사 맥락보다 분위기성 풍경/메타포 쪽으로 쉽게 미끄러짐
- `keyword_coverage.issue_codes` 에 이미 `GENERIC_SYMBOL_WITHOUT_ALLOW` 가 남아 있었음

### 사례 B. 문장 3

문장:

> 예를 들어, 수많은 변수를 고려해야 하는 투자 포트폴리오를 구성하거나, 예측하기 어려운 시장 변동성을 분석하는 것 등...

자동 프롬프트:

- `primary_prop = "예를"`
- `secondary_prop = "들어"`
- must_show = `["예를", "들어", "concrete visual subject tied to the sentence"]`

문제:

- 핵심 의미인 `투자 포트폴리오`, `시장 변동성`, `복잡한 변수`, `계산 난이도`는 사라짐
- 한국어 조사/접속부가 시각 목표로 승격됨
- 이후 프롬프트 수리도 이 잘못된 `must_show` 를 기준으로 돌아감

### 사례 C. 문장 4

문장:

> 하지만 실제 금융 현장의 복잡한 과제에 적용하여 실질적인 솔루션을 개발하는 과정에서, 기술적인 한계점들이 드러나기 시작했습니다.

실제 선택 결과:

- 선택 이미지: `autopilot_scene_004_00009_.png`
- 프롬프트: `Flipchartvisu, Stick figure, ... large checklist with three bold check marks ...`
- vision issue: `LOW_ENTROPY`, `LOW_EDGE_DETAIL`, `EXTREME_EXPOSURE`

문제:

- 문장 의미는 "실제 금융 적용 과정에서 한계가 드러남"인데, 시각적으로는 체크리스트 스틱맨
- 품질도 낮지만, 더 큰 문제는 의미 자체가 틀어졌다는 점

### 사례 D. 문장 9

문장:

> 일부 기관들은 속도를 늦추는 모습을 보이지만, 다른 주요 금융사들은 여전히 양자 컴퓨팅을 미래 성장 동력으로 보고 막대한 투자를 지속하고 있습니다.

자동 프롬프트의 핵심:

- `primary_keywords = ["sharp alarm clock", "unfinished to-do notebook", "일부", "기관들"]`
- `symbolic_marker = "sharp alarm clock"`

문제:

- "속도 조절 vs 지속 투자"라는 산업적 대비가 "알람시계"로 환원됨
- 문장 간 상대 비교 구조가 사라지고 단일 상징물만 남음

## 3. 현재 워크플로우에서 의미가 망가지는 지점

현재 흐름은 대략 아래 순서다.

1. `visual_planner.build_scene_visual_plan()`
2. `image_prompting.suggest_image_prompt_batch()`
3. `autopilot._build_image_batch_items()`
4. `image_worker._run_job_with_heartbeat()`
5. `comfyui_pipeline.import_history_image()`
6. `comfyui_pipeline._select_best_candidate()`
7. `visual_relevance.validate_generated_image_mappings()`
8. `render.run_render_job()`

문제는 1번에서 망가진 의미가 2, 3, 4, 5, 6에서 다시 증폭된다는 점이다.

## 4. 근본 원인

### 4.1 `visual_planner` 가 문장 의미를 "핵심 명사"가 아니라 "잡힌 토큰" 기준으로 만든다

관련 코드:

- `app/services/visual_planner.py`
- `_extract_concrete_tokens()`
- `_fallback_entry()`

핵심 문제:

- 한국어 긴 문장에서 의미 단위를 안정적으로 뽑지 못한다.
- 추출 실패 시 문장 선두 단어, 접속 표현, 부분 토큰이 그대로 `primary_keywords`, `must_show` 로 올라간다.
- 예: `예를`, `들어`, `실제`, `금융`, `일부`, `기관들`

왜 치명적인가:

- 이후 모든 단계가 `must_show`, `primary_prop`, `primary_keywords` 를 정답처럼 취급한다.
- 즉, 잘못 뽑힌 토큰이 전체 파이프라인의 기준 오염원이 된다.

### 4.2 `essay` 도메인의 fallback 설계가 너무 generic 하다

관련 코드:

- `app/services/visual_planner.py`
- `_extract_visual_tokens()`
- `_fallback_entry()`
- `_repair_generic_essay_entry()`

관찰:

- `essay` 분기에서 시각 토큰이 부족하면 추상 상징을 넣는다.
- 대표 generic token:
  - `large checklist with three bold check marks`
  - `compass on a folded map`
  - `quiet road fork`
  - `sharp alarm clock`

왜 반복적으로 망가지는가:

- 금융/정책/산업 기사처럼 추상도가 높은 문장은 `essay` 로 떨어질 가능성이 높다.
- 그 상태에서 시각 토큰이 빈약하면 거의 같은 generic set이 반복된다.
- 그래서 문장마다 다른 의미를 가져도 결과는 비슷한 스틱맨, 시계, 체크리스트로 수렴한다.

### 4.3 `build_visual_brief()` 가 generic fallback을 자연스럽게 합법화한다

관련 코드:

- `app/services/visual_brief.py`
- `_primary_prop()`
- `_action_from_tokens()`
- `_scene_from_template()`

핵심 문제:

- 토큰이 빈약하거나 부정확해도 `concrete visual subject tied to the sentence`, `grounded editorial environment` 같은 안전 문구로 포장된다.
- 이 포장은 "정답 미정" 상태를 숨긴다.

결과:

- 상류에서 의미를 못 잡았는데도, 하류는 "적당한 브리프가 만들어졌다"고 오판한다.
- 그래서 실제로는 fallback인데 UI/로그 상으로는 정상적인 브리프로 보인다.

### 4.4 `image_prompting` 이 잘못된 브리프를 예쁜 프롬프트로 확장할 뿐, 의미를 복구하지 못한다

관련 코드:

- `app/services/image_prompting.py`
- `suggest_image_prompt()`
- `_template_for_visual_plan()`
- `_fallback_tokens()`

핵심 문제:

- `visual_plan_entry["source"] == "fallback"` 인 경우에도 `essay_editorial` 같은 그럴듯한 템플릿을 얹는다.
- 프롬프트 수리 루프는 품질 이슈를 줄이려 하지만, 의미 이탈 자체는 고치지 못한다.
- `keyword_coverage` 실패 후에도 주로 표면 문구만 손본다.

실제 결과:

- "엉성한 의미 + 그럴듯한 스타일 문장" 조합이 생성 프롬프트가 된다.
- 그래서 이미지 품질은 어느 정도 나와도 내용은 엉뚱해진다.

### 4.5 `autopilot` 의 후보 수 자체가 의미 회복에 부족하다

관련 코드:

- `app/services/autopilot.py`
- `_candidate_total_for_prompt()`
- `_build_image_batch_items()`

관찰:

- `fast` 모드면 후보 1장
- `balanced` 모드여도 추상 장면은 보통 2장

문제:

- 이미 프롬프트가 잘못된 상태에서 후보 1~2장은 의미 다양성 확보에 턱없이 부족하다.
- 결국 "나쁜 프롬프트의 변형" 2장 중 하나를 고르게 된다.

### 4.6 후보 선택 점수가 실제 이미지 의미보다 프롬프트 자기일치에 과도하게 의존한다

관련 코드:

- `app/services/comfyui_pipeline.py`
- `_compute_candidate_score_details()`
- `_select_best_candidate()`

핵심 문제:

- 점수 구성은 `coverage_pass`, `must_show_coverage`, `keyword_hits`, `non_fallback` 중심이다.
- 그런데 이 값들의 기준이 이미 오염된 `brief` 와 `prompt` 다.
- 즉, "문장과 잘 맞는가"보다 "잘못된 프롬프트를 충실히 따랐는가"를 더 많이 본다.

실제 부작용:

- `예를/들어`, `실제/금융`, `알람시계` 같은 잘못된 단서도 프롬프트 내부에서는 자기일관성을 가진다.
- 그래서 실제 문장과 틀려도 scoring 상으론 완전히 탈락하지 않는다.

### 4.7 이미지 QA는 품질은 보지만 의미 회복 경로는 약하다

관련 코드:

- `app/services/comfyui_pipeline.py`
- `app/services/visual_relevance.py`
- `app/services/image_quality.py`

문제:

- `LOW_ENTROPY`, `LOW_EDGE_DETAIL`, `EXTREME_EXPOSURE` 같은 품질 신호는 잡는다.
- 하지만 "이 이미지가 문장의 핵심 산업 맥락을 보여주는가"는 약하게 본다.
- 특히 `essay` 장면은 strict semantic gate가 약해, generic drift를 많이 허용한다.

결과:

- 품질이 낮은 잘못된 이미지도 남고
- 품질이 괜찮은데 의미가 틀린 이미지도 남는다

### 4.8 repair 루프가 "잘못된 장면 의미"를 더 강화한다

관련 코드:

- `app/workers/image_worker.py`
- `_build_repair_suggestion()`
- repair retry 루프

핵심 문제:

- retry는 현재 prompt와 brief를 전제로 한다.
- 즉, "이 장면은 체크리스트 스틱맨이 맞다"는 가정하에 선명도나 레이아웃을 고친다.
- 장면 개념 자체를 재설계하지 않는다.

그래서 생기는 일:

- 복구가 아니라 잘못된 시각 개념의 보정이 된다.
- 결과적으로 "더 또렷한 오답"이 나온다.

### 4.9 수동 복구용 단일 이미지 API가 프로젝트 메타를 덮어쓰는 운영 버그가 있다

관련 코드:

- `app/routers/image_gen.py`
- `enqueue_comfyui_job()`

문제:

- 단일 수동 job은 `body_image_options=payload.model_dump()` 로 전체 옵션을 통째로 덮어쓴다.
- 이 과정에서 `image_prompts_manifest_path`, `batch_items`, 기존 `candidate_groups`, 기타 문맥 메타가 날아갈 수 있다.

영향:

- 수동 복구를 시도할수록 프로젝트 상태가 불안정해진다.
- 실제로 이번 작업에서도 매니페스트 경로가 사라져 preflight가 다시 막혔다.

이건 품질 저하의 1차 원인은 아니지만, 복구를 어렵게 만드는 2차 운영 버그다.

### 4.10 워커 중복 실행은 재현성까지 악화시킨다

관련 코드:

- `app/main.py`
- `app/workers/*`

관찰:

- 동일 워커가 중복으로 여러 개 떠 있을 수 있다.
- 이 경우 어떤 코드 버전의 워커가 큐를 집는지 불안정해진다.

영향:

- 같은 프로젝트라도 복구 결과가 매번 다르게 보일 수 있다.
- "왜 방금 통과했는데 다시 실패하지?" 같은 운영 혼란이 생긴다.

## 5. 왜 이미지가 중구난방처럼 보이는가

요약하면 아래 조합 때문이다.

1. 문장 의미를 못 뽑음
2. generic 상징물로 대체
3. 그 generic 프롬프트를 여러 문장에 재사용
4. 후보 선택도 그 generic 프롬프트 기준으로 수행
5. repair도 같은 기준으로 돌림

즉 "문장마다 다른 그림을 만들고 있는 것처럼 보이지만", 실제로는 소수의 fallback 시각 문법을 돌려 쓰고 있다.

그래서 사용자 눈에는 다음처럼 보인다.

- 어떤 컷은 뜬금없는 실사 풍경
- 어떤 컷은 스틱맨
- 어떤 컷은 체크리스트
- 어떤 컷은 시계/노트

겉으로는 랜덤 같지만, 내부적으로는 fallback 세트가 랜덤하게 섞여 나오는 것이다.

## 6. 우선순위별 개선 계획

### P0. 장면 의미 추출 실패를 "정상"으로 통과시키지 않기

목표:

- 잘못된 핵심 토큰이 내려가면 바로 차단
- generic fallback이 핵심 슬롯에 들어가면 즉시 재기획

작업:

1. `visual_planner._extract_concrete_tokens()` 를 한국어 의미 단위 중심으로 재작성
2. 금융/산업 문장을 위한 noun-phrase 추출 규칙 추가
3. `must_show` 에 조사, 접속어, 일반명사 1~2글자 토큰이 들어가면 차단
4. `concrete visual subject tied to the sentence` 같은 placeholder가 `must_show` 에 남아 있으면 실패 처리

완료 기준:

- `예를`, `들어`, `실제`, `일부` 같은 토큰이 `primary_prop` 로 내려가지 않음

### P1. `essay` fallback을 generic 상징물 세트에서 산업 기사용 시각 템플릿으로 분리

목표:

- 금융/산업 기사에서 체크리스트, 나침반, 시계 fallback 남용 중단

작업:

1. `essay` 를 최소 3갈래로 분리
   - `industry_editorial`
   - `market_analysis`
   - `institutional_strategy`
2. 각 분기별 allowed visual vocabulary 정의
3. `checklist`, `compass`, `alarm clock` 는 특정 조건에서만 허용

완료 기준:

- 산업 기사에서 generic symbolic prop 등장률 대폭 감소

### P2. visual plan과 prompt 사이의 의미 계약을 강제

목표:

- `visual_plan` 의 핵심 의미가 prompt에서 사라지지 않게 함

작업:

1. `suggest_image_prompt()` 에서 `visual_plan.core_meaning` 기반 semantic anchors 추가
2. prompt 생성 후 `primary_keywords`, `must_show`, `scene_anchor` 반영률 검사
3. 반영률이 낮으면 style repair가 아니라 plan regeneration으로 분기

완료 기준:

- prompt 수리 실패를 "문구 보정"이 아니라 "장면 재기획 필요"로 구분

### P3. 후보 선택 점수를 "프롬프트 자기일치"에서 "문장 의미 일치" 중심으로 재설계

목표:

- 잘못된 프롬프트를 충실히 따르는 이미지를 높은 점수로 뽑지 않기

작업:

1. `_compute_candidate_score_details()` 에 문장-이미지 의미 점수 추가
2. `brief.primary_keywords` 대신 `sentence-derived semantic targets` 사용
3. fallback source 항목은 큰 패널티
4. `RAW_TEXT_VISUAL_TARGET`, `GENERIC_SYMBOL_WITHOUT_ALLOW` 가 남아 있으면 점수 상한 제한

완료 기준:

- generic fallback prompt 기반 후보가 자동 1위로 뽑히지 않음

### P4. repair 루프를 "프롬프트 보정"과 "장면 재설계"로 분리

목표:

- 잘못된 개념을 또렷하게 만드는 repair를 중단

작업:

1. `image_worker` 에 retry reason 분기 추가
2. 품질 이슈만 있으면 prompt repair
3. 의미 이슈가 있으면 visual plan regenerate
4. `retry_recommended` 의 원인을 `quality`, `semantic`, `composition`, `style` 로 분리

완료 기준:

- 의미 실패 케이스에서 체크리스트 스틱맨이 반복 재생성되지 않음

### P5. 수동 복구 API를 안전하게 변경

목표:

- 수동 장면 복구가 프로젝트 메타를 망가뜨리지 않게 함

작업:

1. `image_gen.enqueue_comfyui_job()` 에서 `body_image_options` 전체 덮어쓰기 금지
2. 기존 옵션 merge 방식으로 변경
3. `image_prompts_manifest_path`, `candidate_groups`, `candidate_reviews` 보존

완료 기준:

- 수동 생성 후에도 preflight 메타가 유지됨

### P6. 운영 재현성 확보

목표:

- 같은 코드, 같은 프로젝트에서 같은 경로로 복구 가능하게 만들기

작업:

1. 중복 워커 방지 강화
2. 워커 PID/버전 로깅
3. 현재 실행 중인 워커가 어느 코드 버전인지 상태 노출

완료 기준:

- "구버전 워커가 큐를 잡아서 예전 규칙으로 실패" 같은 현상 제거

## 7. 권장 구현 순서

1. P0: 의미 추출 차단 규칙
2. P1: `essay` 세분화와 fallback 교체
3. P2: plan-prompt 계약 검사
4. P3: candidate scoring 재설계
5. P4: semantic retry 분기 추가
6. P5: 수동 복구 API merge 수정
7. P6: 워커 운영 안정화

## 8. 검증 기준

개선 후 반드시 아래를 통과해야 한다.

1. `primary_prop`, `secondary_prop`, `must_show` 에 조사/접속어/placeholder 금지
2. 문장 핵심 산업 개념이 prompt에 최소 1개 이상 반영
3. `essay` 기사에서 `checklist`, `compass`, `alarm clock` 자동 fallback 비율 측정
4. 후보 선택 점수가 낮아도 의미적으로 맞는 이미지를 우선 뽑는지 확인
5. repair 후 prompt가 아니라 visual plan이 바뀌는 케이스가 실제로 존재하는지 확인
6. 수동 장면 복구 후에도 preflight 메타가 보존되는지 확인

## 9. 결론

현재 이미지 생성이 중구난방인 이유는 ComfyUI 자체보다 상류의 장면 기획과 하류의 후보 선택이 같은 오염된 표현을 공유하기 때문이다.

특히 이번 금융 기사 사례는 아래를 명확히 보여준다.

- 기사형 추상 문장 -> `essay`
- `essay` 의미 추출 실패 -> generic symbolic token
- generic symbolic token -> 스틱맨/체크리스트/시계 수렴
- scoring/repair도 같은 기준 사용 -> 오답 강화

따라서 해결의 중심은 "모델 품질 튜닝"이 아니라 다음 두 가지다.

1. 잘못된 시각 개념이 하류로 내려가지 못하게 막기
2. fallback 중심 파이프라인을 domain-aware scene planning 파이프라인으로 바꾸기

이 문서 기준으로 다음 구현 작업은 `visual_planner`, `image_prompting`, `comfyui_pipeline`, `image_worker`, `image_gen router` 순으로 진행하는 것이 가장 효과적이다.
