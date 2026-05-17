# 자동화 프로그램 마감 실행 계획

작성일: 2026-04-26

이 문서는 `automation-advancement-master-plan.md` 이후 남은 핵심 작업을 한 번에 마감하기 위한 실행 계획이다. 목표는 “작동하는 자동화”를 넘어, 렌더 결과가 대본/장면 의도를 반영하고 운영자가 실패 원인을 바로 확인할 수 있는 상태까지 끌어올리는 것이다.

## 1. 현재 상태 요약

이미 구현된 기반:

- Source Assist: URL/키워드 기반 draft 생성, Brave 월 2000건 한도 기반 사용량 추적, 저작권 회피형 재작성 방향.
- Source Draft Worker: 비동기 draft 생성, 상태 조회, stale 감지의 1차 구조.
- TTS: preview/full job에 GPU guard 적용.
- ComfyUI 이미지 생성: 단일/배치 큐, workflow submit/poll/import, prompt suggestion, body image mapping.
- Scene Plan: `scene_plan` 저장 컬럼/API/UI, sentence timing과 body image mapping 기반 장면 의도 생성.
- Render Plan: `render_plan` 저장/API/UI, scene/image 우선 media 선택, segment metadata(`motion`, `effect`, `caption_style`) 1차 생성.
- Operator: tool registry, usage registry, GPU guard, system/operator API와 UI.
- 검증: 최근 기준 typecheck 통과, scene/render 관련 targeted pytest 통과.

아직 부족한 핵심:

- `render_plan` metadata가 실제 FFmpeg 렌더 결과에 충분히 반영되지 않음.
- 이미지 생성 완료 후 `scene_plan`/`render_plan` 자동 갱신 흐름이 약함.
- 렌더 결과에 대한 report/preflight/회귀 지표가 부족함.
- 브라우저 기준 검증이 UI 체감 품질까지 충분히 덮지 못함.

## 2. 마감 정의

이번 마감의 완료 기준:

- Source Assist -> Apply -> TTS -> Image Gen -> Scene Plan -> Render Plan -> Render -> Report 흐름을 명시적 버튼 중심으로 안정적으로 실행할 수 있다.
- 이미지 생성이 끝나면 장면/렌더 계획이 자동으로 최신화되며, 실제 렌더는 기본적으로 수동 버튼으로 유지한다.
- `render_plan`의 segment별 `motion`, `effect`, `caption_style`이 결과물에 보이는 수준으로 반영된다.
- 실패나 품질 저하가 발생하면 Operator 또는 Render Report에서 원인을 추적할 수 있다.
- 무료 한도 정책을 유지하며, 유료 외부 API 호출은 기본값으로 켜지지 않는다.
- typecheck, targeted pytest, 브라우저 smoke 검증을 통과한다.

이번 마감에서 제외하는 항목:

- 자동 업로드/게시.
- 유료 API 자동 결제 또는 paid fallback 자동 전환.
- 복잡한 영상 편집기 수준의 transition/effect 시스템.
- 완전 자동 chain을 기본값으로 켜는 것. 이는 운영 안정화 이후 옵션으로만 둔다.

## 3. 실행 라운드

### Round 1. Render Plan 실행 반영 강화

목표:

- `render_plan`이 단순 표시용 계획이 아니라 실제 렌더 입력이 되도록 만든다.

작업:

- segment별 duration을 렌더 visual track 구성에 반영한다.
- `motion` 값을 FFmpeg 필터로 매핑한다.
  - `none`: 정지 이미지 유지.
  - `slow_zoom_in`: 완만한 zoompan 또는 scale/crop 기반 확대.
  - `slow_zoom_out`: 확대된 시작점에서 완만히 축소.
- `effect` 1차 반영은 안정성이 높은 값부터 적용한다.
  - `none`: 기존 동작.
  - `fade`: segment 시작/끝 fade-in/out.
  - transition은 segment 경계 안정성이 확인된 뒤 확장한다.
- `caption_style`을 subtitle 렌더 정책에 연결한다.
  - `plain`: 기존 기본 스타일.
  - `quote`: 성경/인용 구간 강조 스타일.
  - `emphasis`: 훅/핵심 포인트 구간 강조 스타일.
- `render_plan`이 없거나 불완전하면 기존 `media_order` 기반 렌더로 fallback한다.

주요 파일:

- `app/services/render.py`
- `app/services/render_plan.py`
- `app/types.py`
- `tests/test_render_plan.py`
- `tests/test_render_visual_track.py`

완료 기준:

- 동일 프로젝트에서 `motion/effect/caption_style` 값을 바꾸면 렌더 입력 또는 결과가 달라진다.
- `render_plan`이 깨져도 기존 렌더가 실패하지 않는다.
- targeted pytest에 render metadata 반영 테스트가 추가된다.

### Round 2. Image -> Scene -> Render Plan 자동 갱신

목표:

- 이미지 생성 완료 후 사용자가 별도로 “Scene Plan 생성”, “Render Plan 생성”을 반복 클릭하지 않아도 최신 계획이 준비되게 만든다.

작업:

- `image_worker`가 이미지 import와 body image mapping 저장을 완료한 뒤 `scene_plan`을 자동 rebuild한다.
- `scene_plan` rebuild 성공 후 `render_plan`도 자동 rebuild한다.
- 자동 갱신은 계획까지만 수행하고, 실제 렌더 시작은 수동 버튼으로 유지한다.
- UI 상태 메시지에 다음을 표시한다.
  - 이미지 생성 완료.
  - Scene Plan 자동 갱신 완료/실패.
  - Render Plan 자동 갱신 완료/실패.
- 프로젝트 옵션에 `auto_build_plans_after_image`를 둔다.
  - 기본값: `true`.
  - 문제 추적이 필요할 때 끌 수 있게 한다.

주요 파일:

- `app/workers/image_worker.py`
- `app/services/scene_plan.py`
- `app/services/render_plan.py`
- `app/routers/image_gen.py`
- `app/static/app.js`
- `app/types.py`

완료 기준:

- 단일 이미지와 배치 이미지 생성 모두 완료 후 plan이 최신화된다.
- plan 자동 갱신 실패가 이미지 생성 성공 상태를 덮어쓰지 않는다.
- 렌더는 자동으로 시작되지 않는다.

### Round 3. Render Report와 품질 게이트

목표:

- 렌더가 끝났을 때 “성공/실패”만 보는 것이 아니라, 결과물 품질과 위험 신호를 확인할 수 있게 만든다.

작업:

- 렌더 완료 시 `render_report.json`을 생성한다.
- report 항목:
  - project id/name.
  - render 시작/종료 시간.
  - 출력 파일 경로와 파일 크기.
  - 오디오 길이, 최종 영상 길이.
  - 사용된 `render_plan` segment 수.
  - segment별 media path, motion, effect, caption_style.
  - 누락된 media segment 수.
  - subtitle cue 수.
  - FFmpeg command 요약과 stderr tail.
  - fallback 발생 여부.
- 렌더 전 preflight를 추가한다.
  - media 누락.
  - scene_plan/render_plan stale 가능성.
  - TTS 오디오 없음.
  - subtitle cue 없음.
- Step 4 또는 Operator에 최근 render report 요약을 표시한다.

주요 파일:

- `app/services/render_report.py`
- `app/services/preflight.py`
- `app/services/render.py`
- `app/routers/render.py`
- `app/static/app.js`
- `tests/test_render_report.py`

완료 기준:

- 렌더 성공/실패 모두 report가 남는다.
- media 누락이나 fallback 여부가 UI 또는 API에서 확인된다.
- report 생성 실패가 렌더 파일 생성을 망가뜨리지 않는다.

### Round 4. 운영 회귀 지표와 브라우저 검증

목표:

- 기능이 늘어나도 실제 UI에서 깨지는 부분을 빠르게 잡고, 최근 품질 추세를 운영자가 볼 수 있게 한다.

작업:

- 최근 N개 render report를 집계한다.
  - 렌더 성공률.
  - 평균 render 시간.
  - media 누락 평균.
  - fallback 발생 횟수.
  - ComfyUI job 실패 횟수.
  - source draft 재작성/위험 경고 횟수.
- Operator dashboard에 lightweight summary를 추가한다.
  - live job status: 짧은 주기.
  - quota/resource/report aggregate: 30초 이상 긴 주기.
- 브라우저 smoke 검증을 추가한다.
  - 앱 접속.
  - 프로젝트 화면 진입.
  - Step 2의 AI Image Gen/Scene Plan/Render Plan 컨트롤 표시 확인.
  - 버튼 텍스트 overflow/겹침 확인.
  - console error 감지.

주요 파일:

- `app/services/system_health.py`
- `app/services/render_report.py`
- `app/static/app.js`
- `tests` 또는 `scripts/check_browser_smoke.*`

완료 기준:

- Operator에서 최근 품질 추세를 확인할 수 있다.
- 브라우저 smoke가 최소 1개 대표 화면에서 통과한다.
- UI 업데이트가 폴링 비용을 과하게 올리지 않는다.

## 4. 의존성 그래프

권장 순서:

1. Round 1: 실제 렌더 반영 강화.
2. Round 2: 이미지 완료 후 plan 자동 갱신.
3. Round 3: render report와 preflight.
4. Round 4: 운영 지표와 브라우저 검증.

병렬 가능 항목:

- Round 3의 report schema 설계는 Round 1과 병렬 검토 가능.
- Round 4의 browser smoke 초안은 Round 2와 병렬 가능.
- Operator aggregate UI는 report 파일 구조가 정해진 뒤 진행한다.

Round 1을 먼저 하는 이유:

- 결과물의 체감 품질을 좌우하는 핵심이 `render_plan` metadata의 실제 반영이다.
- 이후 report/preflight는 이 실행 결과를 기준으로 품질을 측정해야 한다.

## 5. 테스트 계획

라운드별 최소 검증:

- Round 1:
  - `python -m pytest tests/test_render_plan.py tests/test_render_visual_track.py -q`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
- Round 2:
  - image worker 단위 테스트 또는 라우터 테스트.
  - 단일/배치 image job 완료 후 scene/render plan updated timestamp 확인.
- Round 3:
  - `tests/test_render_report.py`
  - render 실패 케이스에서도 report 생성 확인.
- Round 4:
  - browser smoke script.
  - Operator API 응답에 aggregate 값 포함 확인.

최종 마감 검증:

- typecheck 전체 통과.
- source/scene/render 관련 targeted pytest 통과.
- 앱 시작 후 대표 프로젝트에서 Step 2/Step 4 UI 확인.
- 무료 한도 정책이 기본값으로 유지되는지 확인.

## 6. 위험 관리

렌더 안정성:

- FFmpeg filter가 실패하면 기존 visual track 생성 방식으로 fallback한다.
- 첫 구현에서 transition은 `fade` 중심으로 제한한다.
- segment별 effect가 복잡해질 경우 report에는 “requested effect”와 “applied effect”를 분리 기록한다.

자동 연쇄:

- 이미지 생성 후 plan rebuild까지만 자동화한다.
- TTS/render/upload는 기본 수동으로 유지한다.
- 자동 chain 옵션은 Operator dashboard 고도화 이후 별도 옵션으로 둔다.

GPU/리소스:

- 기존 GPU guard 정책을 유지한다.
- ComfyUI, Ollama, TTS, Whisper가 동시에 VRAM을 잡지 않도록 acquire/release 정책을 건드릴 때는 master plan의 GPU stewardship 표와 동기화한다.

비용:

- Brave Search 월 2000건 무료 한도 내 사용을 기본 정책으로 유지한다.
- Bing/SerpAPI/CSE는 fallback 후보로만 문서화하고 기본 자동 사용은 금지한다.
- paid provider가 필요하면 UI/API에서 명시적 opt-in이 있어야 한다.

## 7. 마감 후 남길 고도화 후보

이번 마감 이후로 미루는 항목:

- 완전 자동 chain 버튼.
- 고급 transition library 또는 scene grammar.
- 영상별 성과/피드백 기반 다음 대본 자동 보정.
- 외부 MCP/Skills marketplace에서 추가 worker 설치.
- ComfyUI workflow 자동 다운로드/버전 고정.
- 다중 render preset과 A/B 렌더.

## 8. 최종 체크리스트

- [x] `render_plan` metadata가 실제 렌더 결과에 반영된다.
- [x] 이미지 생성 완료 후 `scene_plan`과 `render_plan`이 자동 갱신된다.
- [x] 렌더 성공/실패 report가 생성된다.
- [x] preflight warning이 렌더 전 확인된다.
- [x] Operator에 최근 품질 회귀 지표가 표시된다.
- [x] 브라우저 smoke 검증이 통과한다.
- [x] typecheck가 통과한다.
- [x] targeted pytest가 통과한다.
- [x] 무료 한도/수동 렌더 정책이 유지된다.

## 9. 현재 결론

이번 마감 기준의 핵심 자동화는 구현 완료 상태로 본다.

- 결과물 연출:
  `render_plan`의 duration/motion/effect/caption_style이 실제 렌더 결과에 연결됨.
- 자동 연쇄:
  이미지 생성 완료 후 `scene_plan`/`render_plan` 자동 갱신이 연결됨.
- 운영/품질:
  `render_report`, 강화된 preflight, Operator 최근 지표, 브라우저 smoke 검증이 연결됨.
- 검증 루프:
  `scripts/final_verification.ps1`로 typecheck, targeted pytest, browser smoke를 한 번에 재실행할 수 있음.

남은 것은 필수 마감이 아니라 선택적 polish 범주다.
