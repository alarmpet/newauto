# AI Government Article Visual Quality Recovery Plan

작성일: 2026-05-02

대상 프로젝트: `C:\Users\petbl\newauto\storage\projects\55a09de9eec9`

최종 영상: `C:\Users\petbl\newauto\storage\projects\55a09de9eec9\output.mp4`

관련 기사: `https://n.news.naver.com/mnews/article/015/0005282230`

## 1. 결론

이번 영상의 이미지가 뭉개지고 대본과 약하게 연결된 이유는 한 가지가 아닙니다.

가장 큰 원인은 **기사/대본/리포트 데이터가 한글 깨짐 상태로 파이프라인에 들어간 것**입니다. 이후 visual planner가 일부 영어 의미를 복구하긴 했지만, `must_show`, `expected_keywords`, `positive_prompt`에 깨진 한글 토큰이 섞였고, SDXL은 이를 의미 있는 오브젝트로 해석하지 못해 일반적인 건물, 서버랙, UI 아이콘, 추상 다이어그램으로 도망갔습니다.

두 번째 원인은 **AI 정책 갈등 기사인데 도메인이 너무 넓은 `tech`로 처리된 것**입니다. 이 기사는 "AI 기술" 자체보다 "미국 정부, 국방부, 백악관, 앤스로픽, 모델 확산 제동, 안보와 통제 갈등"이 핵심입니다. 현재 `tech` 템플릿은 브라우저/터미널/GPU/서버랙 쪽으로 기울어 있어, 문장별 의미와 맞지 않는 장면을 만듭니다.

세 번째 원인은 **QA가 실제 의미 불일치를 막지 못한 것**입니다. `visual_mismatch_report.md`에서 여러 문장의 `semantic_match_score`가 `0.0` 또는 `0.25`인데도 `decision: warn`으로만 끝났습니다. 그래서 "문장 핵심어가 prompt에 거의 안 들어간 이미지"가 최종 렌더까지 갈 수 있었습니다.

## 2. 이미지별 문제 진단

### 이미지 1

문장:

`나아가 백악관 차원에서도 앤스로픽의 핵심 AI 모델인 '클로드 미토스'의 확산에 제동을 건 것으로 알려졌습니다.`

현재 이미지:

서버랙과 추상적인 네트워크 시설처럼 보입니다.

문제:

- "백악관 차원", "확산에 제동", "접근 확대 차단"이 보이지 않습니다.
- `Claude Mythos` 모델 확산을 제한한다는 핵심이 "서버 시설"로 일반화됐습니다.
- 문장에는 정책적 차단이 핵심인데, 이미지는 기술 인프라 배치도처럼 보입니다.

권장 이미지:

`White House icon pressing a stop button on a branching AI model network, blocked access gate, server nodes behind a red barrier, simple flat explainer diagram, no text`

### 이미지 2

문장:

`최근 미국 국방장관이 상원 청문회에서 앤스로픽을 향해 강한 비판을 제기했습니다.`

현재 이미지:

여러 원형 아이콘과 선이 흩어진 추상 네트워크입니다.

문제:

- "상원 청문회", "국방장관", "비판"이라는 장면 정보가 없습니다.
- 아이콘이 너무 많아 핵심 오브젝트가 없습니다.
- 사람에게는 의미가 아니라 장식적 UI 패턴으로 읽힙니다.

권장 이미지:

`US Senate hearing room icon, defense official silhouette at podium, warning speech bubble aimed at company building icon, simple flat editorial diagram, 2-3 objects only`

### 이미지 3

문장:

`앤스로픽을 둘러싼 논란이 심화되면서, 정부 차원의 개입이 눈에 띄게 늘고 있는 상황입니다.`

현재 이미지:

큰 모니터와 여러 UI 아이콘입니다.

문제:

- "정부 개입 증가"보다 "일반 소프트웨어 대시보드"처럼 보입니다.
- 앤스로픽/정부/논란/개입의 관계가 명확하지 않습니다.
- 프롬프트에 `browser window with terminal panel and automation cursor`가 들어가면서 기사 맥락과 무관한 브라우저 자동화 그림으로 기울었습니다.

권장 이미지:

`company building icon surrounded by increasing government oversight icons, magnifying glass, policy document, warning triangle, simple flat diagram with one central subject`

## 3. 코드베이스에서 확인된 원인

### 3.1 인코딩/모지바케 데이터가 파이프라인 내부까지 전파됨

확인 위치:

- `storage/projects/55a09de9eec9/visual_mismatch_report.md`
- `storage/projects/55a09de9eec9/image_prompts_manifest.json`
- `app/services/domain_detection.py`
- `app/workers/source_draft_worker.py`

증상:

- `sentence`, `expected_keywords`, `must_show`에 깨진 한글이 저장됨.
- `domain_detection.py` 내부 한국어 needle 일부도 이미 깨진 문자열로 보임.
- `source_draft_worker.py`의 기본 tone 문자열도 깨진 상태.
- 기존 워커가 패치 전 코드를 물고 있어, 서버만 재시작해도 worker 결과는 계속 깨질 수 있음.

필요 조치:

- Naver fetch 디코딩 보정만으로 끝내면 안 됩니다.
- source fetch, source draft, scene visual plan, prompt manifest 저장 전에 `mojibake guard`가 필요합니다.
- 깨진 캐시는 자동 폐기해야 합니다.
- 코드 파일 자체에 깨진 한국어 상수가 있으면 원본 의미로 복구하거나 영어 상수로 치환해야 합니다.

### 3.2 도메인 분류가 너무 거칠다

현재 흐름:

- 기사에 `AI`, `model`, `company`가 들어가면 `tech`로 처리됨.
- `tech` 도메인은 GPU, 서버랙, 브라우저 자동화, 터미널, 데이터센터 쪽 토큰을 강하게 밀어줌.

문제:

이번 기사는 `tech`가 아니라 `ai_policy_conflict` 또는 `news_explainer`에 가까움.

필요 조치:

- `ai_policy_conflict` 도메인을 신설.
- 강한 키워드:
  - `government`, `White House`, `Defense Department`, `Senate hearing`, `national security`, `lawsuit`, `access restriction`, `federal agency`
  - `백악관`, `국방부`, `국방장관`, `상원`, `청문회`, `국가 안보`, `소송`, `확산 제동`, `사용 중단`, `공급망 위험`
- 이 도메인은 GPU/브라우저 자동화 토큰을 기본 fallback으로 쓰면 안 됨.

### 3.3 visual planner가 핵심 관계를 구도 문법으로 고정하지 못함

현재 manifest 예:

- `company building icon`
- `turning arrow and blueprint icon`
- `browser window with terminal panel and automation cursor`
- `stacked GPU rack icon`

문제:

- 문장별 핵심 관계가 "누가 누구에게 무엇을 했는가"로 구조화되지 않음.
- `Claude Mythos 확산 제동`이 `GPU rack`으로 바뀜.
- `국방장관의 청문회 비판`이 `browser window`로 바뀜.
- LLM이 만든 core_meaning은 비교적 괜찮아도, compiler 단계에서 일반 tech fallback으로 희석됨.

필요 조치:

구성 템플릿을 명시해야 합니다.

- `GovernmentVsCompany`: 정부 건물/방패 아이콘 vs 회사 건물 아이콘, 중앙 경고선
- `HearingCriticism`: 청문회 연단 + 경고 말풍선 + 회사 아이콘
- `AccessRestriction`: AI 네트워크 확산선 + 차단 게이트/정지 표식
- `PolicyOversight`: 문서/도장/돋보기 + AI 모델 아이콘
- `SecurityRiskBalance`: 저울 한쪽은 혁신 아이콘, 한쪽은 안보 방패
- `ValuationCompute`: 서버 자원 + 상승 그래프, 단 숫자 텍스트 없이 배지형

### 3.4 simple diagram prompt가 너무 길고 모순적임

현재 positive prompt는 다음 요소가 같이 들어갑니다.

- `wide centered explainer diagram shot`
- `simple centered explainer icon composition`
- `large ... clearly visible`
- `minimal editorial cartoon`
- `clean outline`
- `large readable icons`
- `calm neutral palette`
- `clear arrow or comparison structure`

문제:

- 비슷한 스타일 지시가 과하게 반복됩니다.
- `icon composition`과 `company building icon`이 결합되면서 SDXL이 등각투시 건축물/추상 UI로 생성합니다.
- "flat 2D"를 요구하지만 결과는 isometric 3D풍으로 나옵니다.
- `no readable text`는 맞지만, 그 대신 추상 아이콘만 많아져 의미가 사라집니다.

필요 조치:

simple diagram용 prompt를 짧은 문법으로 제한합니다.

권장 구조:

`flat 2D Korean news explainer illustration, [template layout], [subject 1], [subject 2], [relationship action], 2 or 3 large icons only, thick clean black outline, cream background, no text, no logo`

금지어 강화:

`isometric, 3d render, tiny icon grid, dashboard UI, abstract network, generic server room, blueprint maze, random interface panels`

### 3.5 QA가 의미 불일치를 통과시킴

현재 리포트:

- sentence 0: `semantic_match_score: 0.0`, `decision: warn`
- sentence 3: `semantic_match_score: 0.0`, `decision: warn`
- sentence 6: `semantic_match_score: 0.0`, `decision: warn`
- sentence 7: `semantic_match_score: 0.0`, `decision: warn`

문제:

의미 매칭이 0점인데도 자동 렌더를 막지 않았습니다.

필요 조치:

- simple diagram/news/ai_policy_conflict 도메인에서는 `semantic_match_score < 0.34`면 `block_and_retry`.
- `must_show` 중 최소 1개 이상이 prompt에 있고, prompt의 핵심 오브젝트가 이미지 선택 리포트에도 있어야 통과.
- `browser window with terminal panel and automation cursor` 같은 fallback 토큰이 2회 이상 반복되면 block.
- `candidate_score`가 0.72 이상이어도 semantic score가 낮으면 통과 금지.

### 3.6 Vision QA는 밝은 다이어그램을 잘못 막고, 뭉개진 의미는 못 막음

확인된 현상:

- 밝은 미니멀 다이어그램이 `EXTREME_EXPOSURE`로 탈락.
- 반대로 "뭉개진 추상 아이콘 다이어그램"은 후보 점수가 높게 나옴.

필요 조치:

- `EXTREME_EXPOSURE`는 simple diagram에서는 단독 hard fail로 쓰지 말고, 오브젝트 크기/선명도/대비와 함께 판단.
- 새 issue code 추가:
  - `DIAGRAM_TOO_ABSTRACT`
  - `TINY_ICON_GRID`
  - `ISOMETRIC_BLUEPRINT_DRIFT`
  - `MISSING_RELATIONSHIP_ACTION`
  - `POLICY_CONTEXT_NOT_VISIBLE`
- 이미지 품질 점수에 "중앙 주제 면적", "아이콘 수", "관계 화살표/차단선 존재" 휴리스틱 추가.

### 3.7 콘솔 워크플로우 UX 문제

확인된 문제:

- 화면 텍스트가 한글 깨짐으로 보임.
- 오토파일럿 카드에서 `visual_source_mode`가 보이지 않아 사용자가 `upload_only` 상태로 시작하기 쉬움.
- 이미지 스타일 설정은 Step 2에 숨어 있고, Step 1 오토파일럿 시작 전 자연스럽게 연결되지 않음.
- Step 2의 저장 버튼이 화면 위치/스크롤에 따라 직관적으로 접근되지 않음.
- render worker가 중복 실행되어 렌더 레이스가 발생했고, 13초짜리 실패 결과가 한 번 생성됨.

필요 조치:

- Step 1 오토파일럿 패널에 `Visual Engine`, `Style Preset`, `Render after Preflight`를 직접 노출.
- URL 모드에서는 기본값을 `comfyui_auto + simple_diagram` 또는 기사 도메인 추천값으로 자동 설정.
- `upload_only`인데 미디어가 없으면 시작 버튼 비활성화.
- worker 중복 실행을 감지하는 operator banner 추가.

## 4. 개선 작업 계획

### P0. 깨진 한글 데이터 차단

대상:

- `app/services/source_fetch.py`
- `app/services/source_draft.py`
- `app/services/visual_planner.py`
- `app/services/image_prompting.py`
- `app/services/visual_relevance.py`
- `app/workers/source_draft_worker.py`
- `app/services/domain_detection.py`

작업:

1. `text_health.py` 신규 서비스 추가.
2. `looks_mojibake(text)` 구현.
   - `ì`, `ë`, `í`, `챙`, `챘`, `�`, `湲`, `臾`, `?ㅼ`, `?덉` 등 비정상 패턴 비율 검사.
3. source cache read 시 mojibake 감지되면 cache miss 처리.
4. source draft 결과가 mojibake면 job error로 중단.
5. scene visual plan, prompt manifest에 mojibake 토큰이 들어가면 해당 entry를 LLM repair 또는 vocab fallback으로 교체.
6. 코드 내부 깨진 한국어 needle은 영어 중심으로 복구하고, 한국어 needle은 정상 UTF-8 문자열만 남김.

Acceptance:

- 새 Naver 기사 URL 실행 시 `script.txt`, `visual_mismatch_report.md`, `image_prompts_manifest.json`에 깨진 한글이 0건.
- 깨진 cache 파일은 자동 폐기.

### P0. AI 정책 갈등 도메인 신설

대상:

- `app/services/domain_detection.py`
- `storage/visual_vocab/ai_policy_conflict.json`
- `app/services/visual_planner.py`
- `app/services/image_prompting.py`
- `app/services/prompt_compiler.py`

작업:

1. `ai_policy_conflict` 도메인 추가.
2. `tech`보다 먼저 강한 정책/정부 키워드를 감지.
3. vocab 추가:
   - `government oversight`
   - `senate hearing criticism`
   - `white house access restriction`
   - `ai model spread blocked`
   - `national security risk`
   - `company policy conflict`
   - `court lawsuit`
   - `compute resource valuation`
4. `browser window with terminal panel and automation cursor` fallback 금지.
5. `GPU rack`은 "컴퓨팅 자원/투자/서버 비용" 문장에만 허용.

Acceptance:

- 이번 앤스로픽 기사 문장 8개 중 6개 이상이 `ai_policy_conflict` 또는 `news_explainer`로 분류.
- 청문회 문장 prompt에 `hearing podium`, `defense official`, `company icon` 포함.
- 백악관 제동 문장 prompt에 `White House icon`, `blocked AI network`, `stop gate` 포함.

### P0. 구조화된 다이어그램 템플릿 적용

대상:

- `app/services/visual_planner.py`
- `app/services/image_prompting.py`
- `app/services/prompt_compiler.py`

작업:

1. composition template 필수화.
2. 추상 문장은 fallback이 아니라 템플릿으로 변환.
3. `must_show`는 최대 3개, 모두 영어 구체 명사로 제한.
4. 관계 동사 추가:
   - `blocks`
   - `criticizes`
   - `restricts access`
   - `balances`
   - `escalates`
5. template별 prompt 예:
   - `HearingCriticism`: `hearing podium, defense official silhouette, warning speech bubble, company building icon`
   - `AccessRestriction`: `White House icon, stop gate, branching AI model network`
   - `SecurityRiskBalance`: `balance scale, innovation chip icon, national security shield`

Acceptance:

- 모든 simple diagram prompt에 `composition_template` 존재.
- `must_show`에 깨진 한글, 일반 추상어, fallback browser token 없음.

### P0. Semantic Gate 강화

대상:

- `app/services/visual_relevance.py`
- `app/services/preflight.py`
- `app/services/render.py`

작업:

1. `semantic_match_score < 0.34`면 simple diagram/news/policy 도메인에서 hard fail.
2. `decision: warn`이 3개 이상이면 preflight fail.
3. `expected_keywords`가 깨진 한글이면 report 자체를 `TEXT_HEALTH_FAILED`로 fail.
4. `force_render_with_failed_visuals`는 수동 테스트 플래그로만 허용하고 autopilot 기본 경로에서는 금지.

Acceptance:

- 의미 점수 0.0인 이미지가 렌더로 통과하지 않음.
- failed report가 사용자에게 "어떤 문장, 어떤 핵심어가 이미지에 없음"을 정상 한글로 표시.

### P1. Simple Diagram SDXL prompt 짧게 재설계

대상:

- `app/services/prompt_compiler.py`
- `app/services/image_prompting.py`

작업:

1. simple diagram prompt를 60~90 token 이내로 제한.
2. `prompt_g`: 장면 관계와 핵심 오브젝트만.
3. `prompt_l`: 스타일만.
4. `isometric`, `blueprint`, `dashboard`, `tiny icon grid` negative 강화.
5. `flat 2D`, `front-facing`, `large icons`, `2 or 3 objects only`를 반복 없이 고정.

Acceptance:

- 같은 기사 재생성 시 이미지가 건축 도면/서버 미로처럼 뭉개지지 않음.
- contact sheet에서 문장별 핵심 오브젝트가 육안으로 식별됨.

### P1. 다이어그램 Vision QA 개선

대상:

- `app/services/image_quality.py`
- `app/services/comfyui_pipeline.py`
- `tests/test_image_quality.py`

작업:

1. simple diagram에서 `EXTREME_EXPOSURE` 단독 hard fail 제거.
2. `ISOMETRIC_BLUEPRINT_DRIFT` 감지.
3. `TINY_ICON_GRID` 감지 강화.
4. 중앙 주제 면적이 작고 아이콘 수가 많으면 감점.
5. 템플릿 관계가 보이지 않으면 `MISSING_RELATIONSHIP_ACTION`.

Acceptance:

- 밝은 배경의 선명한 다이어그램은 통과.
- 이미지 2처럼 아이콘이 너무 흩어진 추상 네트워크는 fail.

### P1. 콘솔 워크플로우 개선

대상:

- `app/static/index.html`
- `app/static/app.js`
- `app/static/style.css`

작업:

1. 오토파일럿 패널에 visual source mode, style preset을 직접 표시.
2. URL 입력 후 도메인 분석 결과를 표시:
   - `추천 스타일: Simple Diagram`
   - `추천 도메인: AI Policy Conflict`
3. 시작 전 체크리스트 표시:
   - URL 분석 가능
   - 이미지 자동 생성 ON
   - TTS voice preset 고정
   - render worker 1개
4. 한글 깨짐 UI 문자열 복구.
5. `upload_only` + 미디어 없음이면 시작 버튼 비활성화.

Acceptance:

- 사용자가 Step 1 한 화면에서 URL, 이미지 스타일, 렌더 옵션을 확인하고 시작 가능.
- Playwright 클릭 테스트에서 숨겨진 Step 2 설정을 건드리지 않아도 정상 payload 생성.

### P1. Worker 중복 실행 방지

대상:

- `app/workers/worker_lock.py`
- `app/services/system_health.py`
- `app/static/app.js`

작업:

1. operator health에서 worker 종류별 실행 개수 표시.
2. render worker가 2개 이상이면 UI 경고.
3. stale lock 정리 로직 추가.
4. render job claim 시 job_id 기반 idempotency 강화.

Acceptance:

- render worker 2개 실행 시 사용자에게 경고.
- 같은 프로젝트 output.mp4를 동시에 렌더하지 않음.

## 5. 테스트 계획

### 자동 테스트

- `python -m unittest tests.test_source_fetch`
- `python -m unittest tests.test_domain_detection`
- `python -m unittest tests.test_visual_planner`
- `python -m unittest tests.test_image_prompting`
- `python -m unittest tests.test_prompt_compiler`
- `python -m unittest tests.test_visual_relevance`
- `python -m unittest tests.test_image_quality`
- `npm run typecheck:frontend`

### 수동/브라우저 테스트

1. Playwright로 새 프로젝트 생성.
2. URL 입력.
3. 오토파일럿 패널에서 추천 도메인/스타일 확인.
4. 클릭으로 오토파일럿 시작.
5. 생성 후 contact sheet 확인.
6. `visual_mismatch_report.md`에서:
   - mojibake 0건
   - semantic score 0.34 미만 0건
   - fallback browser token 반복 0건
7. 최종 render report:
   - duration guard pass
   - subtitle cue 정상
   - TTS consistency pass

## 6. 이번 영상에 대한 즉시 권장 재생성 방향

현재 생성된 영상은 테스트용으로는 성공했지만, 품질 기준으로는 다시 생성하는 것이 맞습니다.

재생성 전 필수 조건:

1. 기존 프로젝트 `55a09de9eec9`를 그대로 재사용하지 말고 새 프로젝트로 시작.
2. 모든 worker 재시작.
3. source cache 삭제.
4. `ai_policy_conflict` 도메인과 템플릿 적용.
5. simple diagram prompt를 짧게 제한.
6. semantic gate를 hard fail로 변경.

권장 문장별 핵심 이미지:

| 문장 | 핵심 이미지 |
|---:|---|
| 0 | AI 회사 건물과 미국 정부 건물이 중앙 경고선으로 마주보는 구도 |
| 1 | 회사 아이콘 주변에 정부 돋보기/문서/경고 삼각형이 늘어나는 구도 |
| 2 | 상원 청문회 연단, 국방 담당자 실루엣, 회사 아이콘을 향한 경고 말풍선 |
| 3 | 국가 안보 방패와 회사 결정권 아이콘이 저울 위에서 충돌 |
| 4 | 백악관 아이콘이 AI 네트워크 확산선을 stop gate로 막는 구도 |
| 5 | 혁신 칩 아이콘과 정부 통제 방패가 균형 저울에 놓인 구도 |
| 6 | AI 기업 빌딩, 정책 문서, 감독 돋보기, 규제 경계선 |
| 7 | 갈림길 표지판: 한쪽은 빠른 AI 혁신, 한쪽은 강한 정부 통제 |
## 2026-05-02 P0 Implementation Log

Status: partially implemented.

Completed:

- Added `app/services/text_health.py` with a lightweight mojibake detector.
- Added `is_ai_policy_conflict_domain()` to `app/services/domain_detection.py`.
- Changed visual planning domain priority so AI government/policy conflict is selected before generic `tech`.
- Added `storage/visual_vocab/ai_policy_conflict.json`.
- Added policy-conflict diagram templates: `GovernmentVsCompany`, `HearingCriticism`, `AccessRestriction`, `PolicyOversight`, `SecurityRiskBalance`.
- Extended simple diagram prompt assembly to use those templates.
- Added stronger simple-diagram negatives for generic server rooms, GPU racks, browser automation UI, isometric blueprint drift, dashboard UI, and tiny icon grids.
- Hardened visual relevance validation so low semantic prompt match now emits `IMAGE_SEMANTIC_MATCH_TOO_LOW`, mojibake emits `TEXT_HEALTH_FAILED`, and mismatch reports mark low semantic score as `block_and_retry`.
- Bumped visual planner cache version from 6 to 7 so stale scene plans are invalidated.
- Fixed fallback visual plans so they do not override legacy default/k-webtoon prompting unless `simple_diagram` is explicitly active.
- Fixed AI policy conflict plans so domain-specific templates are not overwritten by the news-comment `SortingControl` template.

Verified:

- `python -m unittest tests.test_domain_detection tests.test_image_prompting tests.test_prompt_compiler tests.test_visual_planner tests.test_visual_relevance` passed.
- AST parsing passed for the edited Python files.
- Rechecking project `55a09de9eec9` now flags all 8 weak image mappings as `IMAGE_SEMANTIC_MATCH_TOO_LOW` with `block_and_retry`.
- Sample Anthropic/White House and Senate hearing prompts now select `AccessRestriction` and `HearingCriticism` rather than `SortingControl` or generic GPU/browser prompts.

Remaining:

- Next video generation should regenerate scene visual plans and image prompts from scratch; reusing old `image_prompts_manifest.json` will preserve the bad mappings.
