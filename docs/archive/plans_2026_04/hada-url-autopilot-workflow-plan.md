# Hada URL Autopilot Workflow Plan

## 결론

`https://news.hada.io/topic?id=28920`는 BraveSearch 키워드 검색 단계 대신 사용할 수 있다.

현재 코드 기준으로는 오토파일럿의 `input_mode="url"` 경로가 이미 있으며, 이 경로는 BraveSearch를 호출하지 않고 `analyze_source_url()`로 단일 URL을 직접 분석한 뒤 `gemma4:e4b` 대본 생성 단계로 넘어간다.

로컬 검증 결과 `app.services.source_fetch.analyze_source_url("https://news.hada.io/topic?id=28920")` 호출은 성공했다. 추출된 제목은 `Obscura - 오픈소스 헤드리스 브라우저 | GeekNews`이고, `news.hada.io` 도메인에서 fact note 5개가 생성되었다.

## 자료 특성

GeekNews 페이지는 Obscura 프로젝트 소개 글과 댓글을 함께 포함한다. 페이지 본문에는 다음 정보가 들어 있다.

- Obscura는 웹 스크래핑과 AI 에이전트 자동화용 오픈소스 헤드리스 브라우저다.
- V8 엔진을 내장하고 Chrome DevTools Protocol을 구현해 Puppeteer와 Playwright 코드를 재사용할 수 있다고 소개한다.
- Headless Chrome 대비 메모리, 바이너리 크기, 페이지 로드 시간 측면에서 가볍다는 수치를 제시한다.
- `--stealth` 모드, 세션별 핑거프린트 랜덤화, 트래커 차단, CLI 스크래핑, CDP API 지원 등을 강조한다.
- 댓글에는 GitHub 계정/프로젝트 신뢰도, 실제 반응 확인 부족, 스텔스 모드 검증 필요성 같은 주의 의견도 포함되어 있다.

이 URL은 “뉴스/소개 기반 해설 영상”에는 적합하지만, BraveSearch처럼 여러 출처를 자동 수집하는 용도는 아니다. 따라서 사실 검증 다양성은 낮다.

## BraveSearch 대체 가능 범위

가능한 것:

- BraveSearch 없이 URL 하나만으로 source draft 입력 생성
- `gemma4:e4b`로 한국어 대본 생성
- 이후 기존 워크플로대로 ComfyUI 이미지 생성, OmniVoice TTS, 렌더 진행

부족한 것:

- 여러 출처 비교
- 최신 반응/외부 검증 자동 수집
- 원문 GitHub README의 상세 정보와 릴리스 정보 자동 결합

권장 보강:

- 1차 URL: `https://news.hada.io/topic?id=28920`
- 2차 보조 URL: `https://github.com/h4ckf0r0day/obscura`
- GeekNews 댓글은 “검증 필요/주의 의견”으로만 사용하고, 제품 기능 설명은 GitHub README 기반으로 보강한다.

## 현재 오토파일럿 경로

브라우저 콘솔/API에서 다음 흐름으로 진행하면 된다.

1. 프로젝트 생성
2. 오토파일럿 시작
3. 입력 모드: `url`
4. URL: `https://news.hada.io/topic?id=28920`
5. 톤: `documentary` 또는 `technical explainer`
6. 목표 길이: `1` 또는 `2`
7. visual source mode: `comfyui_auto`
8. image count: `auto` 또는 `8`
9. render after preflight: `true`

예상 내부 단계:

1. `source_collect`: `analyze_source_url()`이 GeekNews HTML을 가져와 텍스트/fact note 생성
2. `source_generate`: source draft worker가 `gemma4:e4b`로 대본 생성
3. `source_apply`: 생성 대본을 프로젝트 스크립트로 적용
4. `tts_enqueue` / `tts_wait`: OmniVoice TTS 생성
5. `image_enqueue` / `image_wait`: ComfyUI 이미지 생성
6. `plan_refresh`: scene/render plan 갱신
7. `preflight`: 렌더 준비 상태 확인
8. `render_enqueue` / `render_wait`: 최종 영상 생성

## 리스크와 수정 필요점

### 1. 단일 URL 입력의 정보량 한계

GeekNews 페이지 자체는 짧은 요약문이다. 현재 `source_fetch`는 최대 6개 fact note를 만들며, 댓글까지 섞어 추출할 수 있다.

대응:

- URL 모드에서도 페이지 내 주요 외부 링크를 보조 출처로 선택 수집하는 옵션을 추가한다.
- 이번 URL에서는 GitHub 원문 링크를 보조 출처로 자동 따라가도록 한다.

### 2. 댓글과 본문 혼합

현재 extractor는 HTML의 본문 영역을 구분하지 않고 길이 기준으로 텍스트를 모은다. GeekNews에서는 댓글이 fact note에 들어갈 수 있다.

대응:

- `news.hada.io` 전용 필터를 추가해 본문 bullet 영역과 댓글 영역을 구분한다.
- 댓글은 별도 `warnings` 또는 `context_notes`로 분류한다.

### 3. ComfyUI 상태

현재 환경에서 ComfyUI 프로세스는 시작되지만 `http://127.0.0.1:8188/system_stats` 응답이 확인되지 않았다.

대응:

- 오토파일럿 시작 전 ComfyUI 헬스체크를 필수화한다.
- 실패 시 `PREFLIGHT_COMFYUI` 또는 `IMAGE_COMFYUI_UNAVAILABLE`로 pause하고 로그에 `comfyui_stderr.log` tail을 표시한다.

### 4. BraveSearch 미사용 시 provenance

BraveSearch를 쓰지 않으면 “검색 결과에서 고른 출처”라는 provenance가 사라진다.

대응:

- `source_draft_input_mode="url"`과 `source_draft_query=<url>`을 명확히 저장한다.
- render report 또는 autopilot debug snapshot에 `direct_url_source=true`를 남긴다.

## 구현 계획

### Phase 1: URL 직접 입력 워크플로 확인

- `analyze_source_url()` 성공 케이스를 `news.hada.io/topic?id=28920` fixture 또는 mock HTML로 테스트 추가
- 오토파일럿 `input_mode="url"`에서 BraveSearch가 호출되지 않는지 테스트
- source draft에 `source_draft_input_mode="url"`이 유지되는지 확인

### Phase 2: GeekNews 추출 품질 개선

- `source_fetch`에 도메인별 후처리 훅 추가
- `news.hada.io`는 본문 링크/본문 bullet/댓글 영역을 분리
- 댓글에서 나온 신뢰도 우려는 fact note가 아니라 warning/context로 분류

### Phase 3: 보조 링크 확장 옵션

- URL 분석 결과에서 주요 외부 링크를 최대 1~2개 추출
- 사용자가 허용하거나 옵션이 켜져 있으면 GitHub README 같은 원문을 추가 분석
- `source_draft_sources`에 GeekNews와 GitHub 원문을 함께 저장

### Phase 4: 실제 오토파일럿 실행

- 새 프로젝트 생성
- `input_mode="url"`로 오토파일럿 시작
- `url="https://news.hada.io/topic?id=28920"`
- `target_minutes=1` 또는 `2`
- `visual_source_mode="comfyui_auto"`
- `image_count=8`
- `render_after_preflight=true`

### Phase 5: 품질 검증

- 대본이 원문 문장을 과도하게 복사하지 않았는지 copy risk 확인
- ComfyUI 이미지가 장면별 문장과 매칭되는지 `visual_relevance` 확인
- OmniVoice TTS가 문장별로 정상 생성됐는지 `timings.json` 확인
- 최종 `output.mp4` 길이, 해상도, 자막 인코딩, 오디오 싱크 확인

## 실행 판단

이 URL은 BraveSearch를 완전히 대체할 수 있는 “직접 URL 입력 소스”로 사용 가능하다.

다만 BraveSearch의 역할이 “출처 발견과 다중 검증”이라면 1:1 대체는 아니다. 이번 건은 이미 사용자가 특정 URL을 지정했으므로, 오토파일럿은 `keyword` 모드가 아니라 `url` 모드로 시작하는 것이 맞다.

