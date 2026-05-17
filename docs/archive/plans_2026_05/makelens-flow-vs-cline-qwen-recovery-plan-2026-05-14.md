# MakeLens Flow 성공 경로 vs newauto Cline+Qwen 문제 분석 계획서

작성일: 2026-05-14  
비교 대상:
- MakeLens 성공 런: `C:\Users\petbl\MakeLens\pipeline_output\20260514_020156`
- MakeLens job: `C:\Users\petbl\MakeLens\pipeline_jobs\sc_20260514_020002_b2753f89`
- newauto/Cline 경로: `C:\Users\petbl\newauto`

## 1. 결론

MakeLens가 Flow 이미지 생성까지 안정적으로 가는 핵심 이유는 **Cline/Qwen이 브라우저를 판단해서 움직이는 구조가 아니기 때문**이다.

MakeLens는 스케줄러가 job을 만들고, browser worker가 전용 설정으로 실행되며, Flow 조작은 `flow_playwright_runner.py`에 코드로 고정되어 있다. LLM은 대본/프롬프트 생성 역할에 머물고, Flow UI 조작, 결과 감지, 다운로드, 파일 검증, 재시도, fallback, coverage 판정은 전부 deterministic code가 처리한다.

반대로 newauto는 최근 많이 개선됐지만 아직 단계 전환과 실패 해석에 Cline/Qwen이 끼어든다. 그래서 `/output`을 JSON으로 파싱하거나, `output_shorts.mp4`가 있는데 `/output.mp4` 기준으로 404를 실패로 오판하거나, Flow 상태를 “로그인 문제인지, 생성 지연인지, selector 문제인지, 결과 추출 문제인지” 매번 대화형 추론으로 판단하는 구간이 남아 있다.

중요한 범위 제한:
이 계획은 **사용자가 영상 생성, 쇼츠 생성, HPSL/Flow/TTS/render workflow를 명령할 때만 적용**한다. 일반 코딩, 리팩터링, 문서 작성, 코드 리뷰, 원인 분석, 단순 파일 수정, 질의응답에서는 Cline/Qwen이 현재처럼 유연한 coding assistant로 행동해야 한다. MakeLens식 worker/runner 모드는 “영상 제작 자동화 운영”에만 켜지는 별도 실행 모드다.

## 1.1 적용 범위와 비적용 범위

### 적용 범위: 영상 생성 workflow 명령

아래 의도가 명확하면 Cline/Qwen은 MakeLens식 production workflow 모드로 전환한다.

- “이 기사/URL로 쇼츠 만들어줘”
- “영상 생성해줘”
- “HPSL 대본부터 Flow 이미지, TTS, 렌더까지 진행”
- “Flow 이미지 생성하고 OmniVoice로 음성 만들고 렌더”
- “newauto 프로젝트를 끝까지 제작”
- “진행”, “다음”, “continue”가 이미 시작된 영상 workflow의 후속 단계일 때

이 모드에서 Cline/Qwen의 역할:
- 사용자 의도 파악
- `start_video_workflow`, `continue_video_workflow`, 추후 `flow_generate_all` 같은 고수준 tool 호출
- worker/operator summary 결과 요약
- 실패 시 deterministic diagnosis tool 호출
- 같은 blocker 반복 시 OpenRouter advisory 호출

이 모드에서 Cline/Qwen이 하지 말아야 할 것:
- Flow 브라우저 화면을 매번 임의 추론으로 조작
- 여러 shell/API를 즉흥 조합해 workflow 상태를 추측
- `/output` 같은 바이너리 endpoint를 JSON으로 파싱
- 사용자가 명령하지 않았는데 prompt를 수동 복사/붙여넣기 방식으로 우회
- worker가 처리해야 할 장시간 반복 루프를 대화 컨텍스트에서 직접 운전

### 비적용 범위: 일반 작업

아래 작업에서는 MakeLens식 제약을 적용하지 않는다.

- 코드 수정/리팩터링/테스트 작성
- 계획서 작성/업데이트
- 코드 리뷰
- 로그나 원인 분석만 요청
- 단순 파일 탐색/명령 실행
- 일반적인 질문 답변
- newauto가 아닌 다른 프로젝트의 개발 작업
- 사용자가 “영상 제작을 실행하지 말고 분석만 해”라고 명시한 경우

이때 Cline/Qwen은 일반 coding assistant로 행동한다.

- 필요한 파일을 읽고 직접 수정한다.
- 테스트를 실행한다.
- 합리적 추론과 설명을 한다.
- 필요하면 web/search/OpenRouter를 규칙에 맞게 사용한다.
- MakeLens식 browser worker 전환을 강제로 하지 않는다.

### 의도 판정 규칙

1. “만들어줘/생성해줘/렌더해줘/업로드해줘”와 “영상/쇼츠/HPSL/Flow/TTS/render”가 같이 나오면 workflow 명령으로 본다.
2. “분석해봐/비교해봐/계획서 작성해/왜 그런지 봐”는 기본적으로 분석/문서 작업으로 본다.
3. URL이 있어도 “요약/분석/팩트체크”면 article reading/analysis이고 workflow를 시작하지 않는다.
4. URL이 있고 “영상/쇼츠/제작/렌더”가 있으면 workflow를 시작한다.
5. 애매하면 destructive하거나 장시간 worker를 시작하지 않고, 먼저 짧게 의도를 확인한다.

## 2. MakeLens 성공 증거

최근 성공 런 `20260514_020156`의 상태:

- `pipeline_jobs\sc_20260514_020002_b2753f89\status.json`
  - `status = completed`
  - `scheduled_slot_key = 2026-05-14T02:00@Asia/Seoul`
  - `final_video_path = ...\final\output.mp4`
  - `publish_video_path = ...\final\output.top_overlay_test.mp4`

- `pipeline_output\20260514_020156\operator_summary.json`
  - `current_stage = complete`
  - `scene_count = 10`
  - `generated_image_count = 10`
  - `placeholder_image_count = 0`
  - `review_stage = uploaded`
  - `youtube_url = https://www.youtube.com/watch?v=Askm60sPT4c`

- `pipeline_output\20260514_020156\images_meta.json`
  - `generated_image_count = 10`
  - `placeholder_image_count = 0`
  - `artifact_type_counts.png = 10`
  - `target_aspect_ratio = 9:16`
  - `target_dimensions = 1080x1920`

- `pipeline_output\20260514_020156\flow_run_log.json`
  - 모든 장면이 `runner = flow_playwright_direct`
  - 모든 장면이 `surface_mode = flow`
  - 모든 장면이 `status = ok`
  - `flow_profile_dir = C:\Users\petbl\music-auto\browser_profiles\automation_notebooklm`

- `pipeline_output\20260514_020156\pipeline_status.json`
  - fetch: ok, 0.344초
  - rewrite: ok, 82.516초
  - tts: ok, 124.172초
  - image: ok, 1689.14초
  - render/qa: ok

중요한 관찰:
MakeLens도 Flow 이미지 10장을 만드는 데 약 28분을 썼다. 빠른 게 아니라, 긴 작업을 **worker가 상태 파일과 로그로 견디면서 끝까지 처리**한다.

## 3. MakeLens Flow 이미지 생성 방식

### 3.1 전용 browser worker lane

MakeLens는 일반 파이프라인 설정과 browser worker 설정을 분리한다.

근거:
- `C:\Users\petbl\MakeLens\pipeline\run_browser_worker.py:12`
  - `build_browser_worker_config()`가 browser lane 전용 backend를 구성한다.
  - `image_backend`가 local이면 browser worker에서는 `flow_browser` 또는 `browser_worker_image_backend`로 승격한다.

효과:
- 스케줄 작업은 “대화형 Cline 컨텍스트”에 묶이지 않는다.
- 브라우저 자동화가 필요한 단계는 interactive worker가 맡는다.
- Qwen context, Cline tool call 상태, 대화 누적량이 Flow 성공 여부를 직접 흔들지 않는다.

### 3.2 Flow 전용 profile을 고정 사용

근거:
- `C:\Users\petbl\MakeLens\pipeline\experimental\flow_playwright_runner.py:1045`
  - `_resolve_flow_profile_dir()`가 `C:\Users\petbl\music-auto\browser_profiles\automation_notebooklm` fallback profile을 선호한다.

성공 런의 `flow_run_log.json`도 같은 profile을 기록한다.

효과:
- 로그인/session/cookie 상태가 스케줄러와 Flow runner에 일관되게 유지된다.
- Cline이 새 브라우저, 다른 profile, 다른 CDP context를 열어 인증 상태를 잃는 위험이 줄어든다.

### 3.3 Flow UI 조작이 코드로 닫혀 있다

근거:
- `C:\Users\petbl\MakeLens\pipeline\experimental\flow_playwright_runner.py:866`
  - `_prepare_flow_workspace()`가 Flow URL 진입, cookie/overlay dismiss, editor 진입, 설정 조정까지 수행한다.
- `C:\Users\petbl\MakeLens\pipeline\experimental\flow_playwright_runner.py:1191`
  - `_run_flow_direct()`가 장면별 루프, prompt 입력, generate 클릭, 결과 대기, 저장, ratio 검증, retry, debug snapshot, coverage validation까지 처리한다.

효과:
- “지금 어떤 버튼을 눌러야 하지?”를 LLM이 매번 판단하지 않는다.
- selector 후보와 fallback selector가 코드에 있고, 실패 시 실패 클래스가 기록된다.
- 장면마다 동일한 절차가 반복되어 결과 재현성이 높다.

### 3.4 결과 감지가 다층이다

근거:
- `C:\Users\petbl\MakeLens\pipeline\experimental\flow_playwright_runner.py:947`
  - `_wait_for_new_result()`가 blob source, media key, tile id 변화를 모두 본다.
  - visible error snippet을 감지해 `flow_visible_error_estimated` 같은 실패 클래스로 분류한다.
- `C:\Users\petbl\MakeLens\pipeline\experimental\flow_playwright_runner.py:909`
  - `_extract_and_save_latest_image()`가 fetch blob, download menu, locator screenshot 순서로 결과 저장을 시도한다.

효과:
- 단순히 “다운로드 폴더에 새 파일이 있나”만 보지 않는다.
- Flow UI가 다운로드 버튼을 숨기거나 blob URL만 제공해도 저장 경로가 있다.
- 결과가 생겼는지 판단하는 기준이 화면/DOM/미디어 후보 기반이다.

### 3.5 실패가 전체 실패로 바로 번지지 않는다

근거:
- `C:\Users\petbl\MakeLens\pipeline\experimental\step_whisk_images.py:1169`
  - `generate_images_via_flow_browser_with_whisk_fallback()`가 Flow 실패 시 fallback channel, Whisk fallback을 시도한다.
- `C:\Users\petbl\MakeLens\pipeline\experimental\flow_playwright_runner.py:1191`
  - 장면별 retry가 있고, 실패 시 debug snapshot과 `flow_run_log.json`를 남긴다.

효과:
- Flow가 한 번 흔들려도 전체 런이 즉시 인간 판단 대기 상태로 멈추지 않는다.
- 실패 원인이 사후 분석 가능한 구조로 남는다.

### 3.6 산출물 manifest가 render와 직접 연결된다

근거:
- `images_meta.json`이 `scene_image_map`, `image_paths`, `generated_image_count`, `placeholder_image_count`를 가진다.
- render는 `images_meta.json`와 `images\scene_XX.png`를 기준으로 `existing_images` 모드로 진행한다.

효과:
- “어떤 파일이 몇 번째 문장/장면에 붙었는지”가 명확하다.
- render 직전에 파일 존재와 coverage를 검사하기 쉽다.

## 4. newauto/Cline+Qwen 경로의 문제

### 4.1 Cline/Qwen이 orchestration과 diagnosis까지 떠안는다

newauto의 `newauto_stepwise_mcp.py`는 stepwise tool을 제공하지만, 실제 진행은 여전히 “사용자가 진행이라고 말함 -> Cline/Qwen이 현재 상태를 해석 -> 적절한 tool 선택” 흐름이다.

문제:
- Cline context가 커지면 tool 선택이 흔들린다.
- 같은 오류를 반복해도 OpenRouter escalation을 누락할 수 있다.
- 바이너리 endpoint를 JSON으로 파싱하는 식의 도메인 계약 위반이 발생한다.

최근 확인한 실제 예:
- `/api/projects/87b2c4f3d1a3/output`은 MP4 `FileResponse`인데 Cline이 `json.loads()`를 시도했다.
- 프로젝트는 `output_shorts.mp4`가 성공적으로 있었는데, 기본 `/output`이 landscape만 보던 시점에는 404를 “미완료”처럼 해석했다.

### 4.2 Flow 자동화가 MakeLens보다 얇고 단계형이다

newauto의 Flow 직접 생성 코드는 이미 MakeLens식 일부를 가져왔다.

근거:
- `scripts\flow_browser_automation.py:553`
  - `_prepare_flow_workspace()`
- `scripts\flow_browser_automation.py:613`
  - `_wait_for_new_result()`
- `scripts\flow_browser_automation.py:848`
  - `_save_latest_result_image()`
- `scripts\flow_browser_automation.py:1160`
  - `_generate_direct_records()`

하지만 MakeLens와 비교하면 아직 차이가 있다.

차이:
- newauto는 `continue_video_workflow`가 기본적으로 1개 prompt씩 진행한다.
- Flow generation pacing과 lock은 있지만, full job worker가 “모든 문장 생성 -> coverage 검증 -> TTS -> render”를 한 프로세스에서 끝까지 잡는 구조가 약하다.
- 실패 시 MakeLens처럼 `flow_run_log.json`, `images_meta.json`, `operator_summary.json`로 전체 런을 일관되게 요약하는 계층이 부족하다.
- debug snapshot과 OpenRouter vision escalation이 legacy wrapper에 일부 남아 있지만, main direct path와 완전히 결합되어 있지 않다.

### 4.3 prompt manifest 품질 차이

newauto:
- `app\services\flow_prompting.py:108`의 `_build_flow_prompt()`는 안정적이지만 상대적으로 단순하다.
- HPSL sentence의 `core_keyword`, `visual_keyword`를 사용하고, “realistic editorial documentary” 고정형 template에 가깝다.

MakeLens:
- 성공 런은 `sentence_scene_plan.json`, `visual_scene_rows.json`, `sentence_scene_prompt_review.json`를 생성한다.
- Flow prompt에는 장면별 `prompt_recipe`, camera/action/environment/tone 변주가 반영된다.
- Flow runner에서 `_build_flow_submission_prompt()`가 ratio, no text/no watermark constraints, scene variation fragments를 누락 없이 붙인다.

결과:
- MakeLens는 “Flow에 넣기 직전 prompt”가 browser runner에서 다시 정규화된다.
- newauto는 prompt 생성 단계와 Flow submit 단계가 더 분리되어 있어, submit 직전 안전 보강 계층이 약하다.

### 4.4 성공/실패 판정 체계 차이

MakeLens:
- `pipeline_status.json`, `operator_summary.json`, `images_meta.json`, `flow_run_log.json`, `render_meta.json`, `tts_meta.json`가 각 단계를 독립적으로 증명한다.
- `worker.py:531`의 `process_job()`가 result validation, YouTube review/upload, scheduled outcome finalize까지 처리한다.
- `worker.py:378`의 `_scheduled_autopilot_browser_worker_guard_error()`가 browser worker 상태를 선제적으로 guard한다.

newauto:
- 개별 project JSON과 render report는 있으나, 전체 workflow run을 MakeLens식으로 한눈에 보는 operator summary가 약하다.
- Cline이 중간 API를 직접 호출해서 상태를 해석한다.
- 상태 해석 오류가 곧 잘못된 다음 행동으로 이어진다.

### 4.5 현재 MakeLens도 실패한다는 점

MakeLens의 현재 `scheduled_autopilot_status.json`는 2026-05-14 20:00 슬롯이 실패로 되어 있다.

- `status = failed`
- `reason = browser_worker_duplicate_resident_processes`
- `fail_streak = 3`

즉 MakeLens도 완전무결한 것이 아니다. 다만 차이는 실패가 “Flow가 안 됨” 같은 모호한 말이 아니라, browser worker resident process 중복이라는 **구체적인 operational failure class**로 고정된다는 점이다.

## 5. 핵심 원인 비교표

| 영역 | MakeLens | newauto + Cline/Qwen | 문제 |
|---|---|---|---|
| 실행 주체 | scheduler + worker | Cline stepwise + MCP + 일부 script | LLM이 orchestration 판단에 과도하게 개입 |
| 브라우저 profile | Flow 전용 profile 고정 | CDP/profile은 있으나 Cline task 경로 영향 큼 | 인증/세션 해석 혼선 |
| Flow 조작 | 전용 Playwright runner | 직접 runner + stepwise wrapper 혼합 | 일부 판단이 대화형 상태로 빠짐 |
| 결과 감지 | blob/media/tile/download/screenshot | media/download/blob 지원 있으나 summary/coverage 약함 | 실패 원인 분류가 덜 체계적 |
| 산출물 manifest | images_meta + flow_run_log + operator_summary | flow_prompts + project state 중심 | run-level 증명 약함 |
| fallback | Flow channel retry -> Whisk | mostly retry/continue/user 확인 | 자동 fallback chain 약함 |
| 실패 보고 | failure_class 고정 | Cline 설명 의존 | 반복 실수와 오판 가능 |
| LLM 역할 | rewrite/prompt 쪽 | rewrite + orchestration + diagnosis | Qwen context/추론 오류가 운영 실패로 전파 |

## 6. newauto 개선 계획

### Antigravity 검토 반영 사항

`makelens-flow-recovery-plan-review-antigravity-2026-05-14.md`의 검토 의견은 대체로 타당하다. 특히 아래 세 가지는 기존 계획에 반영한다.

1. `operator_summary.json` 도입 후에는 Cline/Qwen이 `/status`, `/render-report`, `/flow/manifest`, 파일시스템을 여러 번 뒤지며 상태를 추론하는 방식을 줄인다.
   - workflow 상태 확인의 기본 진입점은 `get_operator_summary` 또는 `/api/projects/{pid}/operator-summary`로 단일화한다.
   - 복잡한 예외 상황에서만 `diagnose_runtime`, `forensic_diagnose`, 개별 API를 호출한다.

2. OpenRouter 개입 범위를 재조정한다.
   - Flow worker 내부의 장면별 retry, fallback channel, Whisk/ComfyUI fallback은 worker가 자체 처리한다.
   - OpenRouter는 매 작은 실패마다 호출하지 않는다.
   - OpenRouter는 worker 자체가 멈췄거나, health guard가 심각한 운영 문제를 보고했거나, 같은 operational blocker가 반복될 때 호출한다.

3. `진행`/`다음`의 의미를 바꾼다.
   - 영상 workflow 모드에서 사용자가 `진행`이라고 하면 단순히 “한 문장만 생성”하지 않는다.
   - 다음 인간 개입 지점까지 non-stop으로 전진한다.
   - 인간 개입 지점은 인증/CAPTCHA/계정 잠금, 치명적 health guard 실패, render/upload 전 확인이 필요한 정책 차단, worker unrecoverable failure이다.

이에 따라 우선순위는 `P0 -> P2 -> P3`가 가장 높다. 즉 먼저 Cline/Qwen 제어면을 줄이고, single source of truth를 만들고, Flow generate-all worker를 승격한다.

### P0. 영상 workflow 한정 Cline/Qwen 역할 축소

목표:
영상 생성 workflow에서만 Qwen은 “다음 tool 선택자”가 아니라 “상태 요약을 읽는 보조자”로 낮춘다. 일반 코딩/분석 작업에서는 이 제한을 적용하지 않는다.

작업:
1. `continue_video_workflow` 내부에서 Flow 단계의 다음 행동을 완전히 결정한다.
2. Cline 응답은 tool 결과를 요약만 하게 한다.
3. `/output`, `/render-report`, `/status` 같은 endpoint 계약을 `.clinerules`와 MCP prompt에 계속 고정한다.
4. 동일 blocker 3회 규칙은 이미 추가했으므로, Flow 실패 class에도 직접 연결한다.
5. `.clinerules`에 “영상 workflow 모드”와 “일반 assistant 모드”를 분리해 적는다.
6. workflow intent detector를 MCP prompt에 추가한다.
7. `operator_summary` 도입 후에는 상태 확인 tool을 `get_operator_summary` 중심으로 간소화한다.
8. workflow 모드에서 `진행`은 다음 인간 개입 지점까지 진행하는 명령으로 해석한다.

성공 기준:
- 사용자가 `진행`만 반복해도 Cline이 임의 shell/API 호출을 섞지 않는다.
- Cline이 `/output`을 JSON으로 파싱하지 않는다.
- 사용자가 일반 코드 수정이나 분석을 요청할 때는 Cline/Qwen이 MakeLens식 worker 모드로 과잉 전환하지 않는다.
- 영상 workflow에서 Cline/Qwen은 여러 상태 endpoint를 직접 조합하지 않고 operator summary를 먼저 읽는다.
- 영상 workflow에서 `진행` 한 번으로 Flow generate-all worker가 가능한 구간을 끝까지 처리한다.

### P1. MakeLens Flow runner를 newauto에 정식 이식

목표:
영상 workflow 모드에서 사용하는 `scripts\flow_browser_automation.py`를 MakeLens `flow_playwright_runner.py` 수준으로 끌어올린다. 일반 작업에서는 이 runner를 자동 호출하지 않는다.

작업:
1. MakeLens의 `_flow_surface_state()` 이식
2. MakeLens의 blob source/media key/tile id 동시 감지 방식 이식
3. MakeLens의 ratio validation 이식
4. MakeLens의 `_write_debug_snapshot()`를 newauto direct path에 결합
5. 장면별 `flow_run_log.json`를 `storage/projects/<pid>/flow_run_log.json`에 저장
6. 장면별 실패 class를 `flow_prompts.json.entries[].status/error`에 반영

성공 기준:
- Flow 실패 시 `flow_generation_failed` 대신 `flow_prompt_input_missing`, `flow_visible_error_estimated`, `flow_timeout_no_surface`, `flow_result_extract_failed`, `portrait_compliance_failed`처럼 구체적으로 기록된다.
- 한 장면 실패가 곧 전체 Cline 대화 멈춤으로 번지지 않는다.

### P2. run-level operator summary 추가

목표:
영상 workflow 프로젝트에 대해 MakeLens `operator_summary.json`처럼 현재 프로젝트의 전체 상태를 한 파일/API로 증명한다.

Antigravity 반영:
이 항목은 단순 리포트 추가가 아니라 **LLM 상태 확인 경로의 단일화**가 목적이다. `operator_summary`가 생기면 Cline/Qwen은 여러 endpoint를 순회하며 추론하지 않고, 먼저 operator summary만 읽는다.

작업:
1. `storage/projects/<pid>/operator_summary.json` 생성
2. 포함 필드:
   - `project_id`
   - `current_stage`
   - `source_draft_state`
   - `script_sentence_count`
   - `flow_prompt_count`
   - `generated_image_count`
   - `placeholder_image_count`
   - `asset_coverage`
   - `tts_state`
   - `render_state`
   - `outputs`
   - `failure_class`
   - `recommended_next_tool`
3. `/api/projects/{pid}/operator-summary` 추가
4. `diagnose_runtime`이 이 파일을 우선 표시
5. MCP tool `get_operator_summary(project_id)` 추가
6. `.clinerules`에서 workflow 상태 확인의 기본 경로를 `get_operator_summary`로 단순화
7. summary에 `human_intervention_required`, `human_intervention_reason`, `next_autonomous_action` 필드 추가

성공 기준:
- Cline이 여러 JSON/API를 추측으로 조합하지 않아도 된다.
- “이미 성공인데 실패로 오해”하는 문제가 줄어든다.
- workflow 상태 확인 tool 호출 수가 줄어든다.
- operator summary만 보고 “계속 진행 가능 / 인간 개입 필요 / 실패 복구 필요”를 판단할 수 있다.

### P3. Flow 이미지 backend를 worker job으로 승격

목표:
영상 workflow 모드에서 MakeLens처럼 Flow 이미지 생성을 대화형 한 단계씩이 아니라 worker job으로 실행한다.

Antigravity 반영:
`진행`은 “문장 하나 생성”이 아니라 “다음 인간 개입 지점까지 전진”으로 해석한다. Flow worker는 missing prompt 전체를 처리하고, Cline/Qwen은 worker enqueue와 summary polling만 담당한다.

작업:
1. `POST /api/projects/{pid}/flow/generate-all` 추가
2. background worker가 missing entries를 순차 처리
3. lock/pacing은 worker 내부에서 처리
4. progress:
   - `flow_state`
   - `flow_progress`
   - `flow_active_sentence`
   - `flow_last_error`
   - `flow_failure_class`
5. Cline `continue_video_workflow`는 worker enqueue와 status polling만 수행
6. `continue_video_workflow`의 `flow_generate` 단계는 generate-all worker를 기본 경로로 사용
7. worker가 다음 상황에서만 멈춤:
   - login/CAPTCHA/account lock 필요
   - health guard fatal
   - all fallback exhausted
   - user policy confirmation required
8. worker 완료 후 coverage가 충분하면 자동으로 TTS 단계로 넘어갈 수 있게 `next_autonomous_action`을 기록

성공 기준:
- 사용자가 Flow 인증만 해두면 이미지 6~10장을 한 worker가 끝까지 처리한다.
- Cline context가 커져도 Flow 루프 자체는 중단되지 않는다.
- `진행` 한 번이 한 문장 생성으로 소모되지 않는다.
- worker가 멈출 때는 사람이 할 수 있는 구체적 조치가 summary에 남는다.

### P4. Flow prompt submit 전 정규화 계층 강화

목표:
영상 workflow에서 MakeLens처럼 Flow에 실제 제출되는 prompt를 마지막 순간에 보강한다.

작업:
1. `flow_submit_prompt` 필드 추가
2. ratio fragment 자동 보강
3. `no visible text`, `no numerals`, `no typography`, `no watermark`, `no labels` 누락 보강
4. 장면별 variation:
   - camera
   - action
   - environment
   - tone
5. prompt word count와 submit prompt를 manifest에 기록

성공 기준:
- Flow prompt가 너무 짧거나 Korean-heavy일 때도 submit prompt가 영어 editorial image prompt로 안정화된다.
- 장면 간 이미지가 덜 반복된다.

### P5. fallback chain 도입

목표:
영상 workflow에서 Flow 실패가 바로 수동 대기로 떨어지지 않게 한다.

Antigravity 반영:
fallback chain 도입 후 OpenRouter는 장면별 retry 실패마다 호출하지 않는다. worker 내부 fallback이 끝난 뒤에도 원인이 불명확하거나, browser/session/worker가 운영적으로 막힌 경우에만 advisory를 요청한다.

작업:
1. Flow primary profile 실패 시 Edge/Firefox fallback profile 시도
2. Flow service visible error면 일정 cooldown 후 같은 scene 재시도
3. Whisk/ComfyUI fallback 정책을 명확히 분리
4. fallback 결과도 manifest에 `backend_used`, `fallback_from`, `fallback_reason` 기록
5. fallback 단계별 failure class를 operator summary에 집계
6. OpenRouter 호출 조건을 `operational_blocker` 중심으로 재정의

성공 기준:
- 한 profile/session 문제로 전체 workflow가 막히지 않는다.
- fallback이 썼는지 최종 report에서 보인다.
- OpenRouter 호출이 noisy retry가 아니라 실제 의사결정 지점에 집중된다.

### P6. browser worker health guard

목표:
영상 workflow 시작/진행 시 MakeLens의 현재 실패 원인인 `browser_worker_duplicate_resident_processes` 같은 문제를 newauto도 사전에 잡는다.

작업:
1. `check_flow_browser_health.py` 추가
2. 검사 항목:
   - CDP port reachable
   - profile lock
   - duplicate browser worker
   - Flow URL reachable
   - prompt surface visible
   - authenticated or login-required classification
3. `continue_video_workflow` Flow 단계 전에 health guard 실행

성공 기준:
- “Flow 로그인/팝업 확인해줘” 같은 모호한 메시지 대신 정확한 guard reason을 반환한다.

## 7. 구현 순서

전제:
아래 구현은 영상 생성 workflow 실행 경로에만 연결한다. 일반 assistant 작업에는 자동으로 적용하지 않는다.

1. workflow intent detector를 먼저 추가한다.
   - 이유: 영상 제작 명령과 일반 작업을 분리하지 않으면 Cline/Qwen 행동이 전체적으로 경직된다.
   - 산출물: `.clinerules`, `newauto_stepwise_mcp.py` prompt, tool catalog에 workflow/non-workflow 판정 규칙 추가.
2. `operator_summary`와 `get_operator_summary`부터 만든다.
   - 이유: Cline/Qwen 오판을 즉시 줄인다.
   - Antigravity 반영: summary가 생기면 `.clinerules`와 MCP prompt에서 여러 상태 확인 tool 호출을 줄이고, summary 중심으로 단순화한다.
3. `continue_video_workflow`의 의미를 “다음 인간 개입 지점까지 진행”으로 바꾼다.
   - 이유: 한 문장씩 Cline/Qwen에게 상태를 돌려주는 구조가 현재 불안정성의 핵심이다.
   - 단, 인증/CAPTCHA/계정 잠금/치명적 guard 실패에서는 멈춘다.
4. `flow_run_log.json`와 debug snapshot을 newauto direct path에 붙인다.
   - 이유: 실패 원인을 사람이 다시 재현하지 않아도 된다.
5. MakeLens의 result detection/ratio validation을 이식한다.
   - 이유: 이미지 생성 성공률 자체를 올린다.
6. Flow generate-all worker를 추가한다.
   - 이유: Cline 대화 상태에서 장시간 browser loop를 분리한다.
7. fallback channel과 health guard를 추가한다.
   - 이유: 운영 안정성 강화.
8. OpenRouter escalation 조건을 operational blocker 기준으로 재정의한다.
   - 이유: worker 내부 retry/fallback이 생기면 작은 실패마다 외부 조언을 받을 필요가 없다.

## 8. 즉시 적용 가능한 운영 규칙

영상 workflow 모드에서만 적용:

1. Cline에게 Flow 브라우저 화면을 직접 “보고 판단”시키지 않는다.
2. workflow 상태 확인은 먼저 `operator_summary.json` 또는 `get_operator_summary`로 한다.
3. Flow 세부 결과 확인은 `flow_run_log.json`, `flow_prompts.json`, project media mapping 기준으로 한다.
4. JSON 상태는 `/operator-summary`, 필요 시 `/render-report`, `/status` 순서로 확인한다.
5. `/output`은 MP4 바이너리로만 취급한다.
6. Flow worker 내부의 장면별 retry/fallback은 worker가 처리한다.
7. OpenRouter는 worker unrecoverable failure, fatal health guard, 반복 operational blocker, screenshot 기반 UI 판단 필요 시에 호출한다.
8. 사용자에게 선택지를 묻기 전에 `operator_summary -> diagnose_runtime -> forensic_diagnose -> repair_runtime` 순서로 deterministic check를 먼저 한다.
9. 영상 workflow가 아닌 작업에서는 위 규칙을 강제하지 않고 일반 coding assistant 방식으로 처리한다.

## 9. 최종 목표

newauto는 Cline/Qwen을 제거할 필요가 없다. 다만 **영상 제작 workflow에서만** MakeLens처럼 역할을 재배치해야 한다.

영상 workflow 모드:
- Qwen/Cline: 사용자 요청 해석, 요약, 고수준 step 호출
- newauto server/worker: 상태 전이, browser automation, asset mapping, TTS, render
- OpenRouter: 반복 blocker와 screenshot/vision 분석의 외부 조언
- 사용자: 인증/CAPTCHA/계정 잠금 같은 인간 개입이 필요한 부분만 처리

일반 assistant 모드:
- Qwen/Cline: 지금처럼 코드 읽기, 수정, 테스트, 분석, 문서 작성, 질문 답변을 유연하게 수행
- newauto worker: 사용자가 명시적으로 영상 제작을 시작할 때만 관여
- OpenRouter: 반복 blocker, 어려운 디버깅, 외부 조언이 필요한 경우에만 사용

이 구조가 되면 MakeLens처럼 “알아서 기사 긁고, 대본 받고, Flow 이미지 만들고, OmniVoice 음성 만들고, 렌더까지 가는” 경로가 Cline 대화 품질에 덜 의존하게 된다.

동시에 사용자가 일반 개발 작업을 시킬 때는 Codex/Cline식 협업 능력을 잃지 않는다. 즉 목표는 “Cline/Qwen을 제한하는 것”이 아니라, **영상 제작 자동화만 생산 라인 모드로 격리하는 것**이다.

## 8.1 2026-05-14 implementation update: operator summary source of truth

Implemented in newauto:

- `app/services/operator_summary.py`
  - Builds and writes `storage/projects/<project_id>/operator_summary.json`.
  - Summarizes script sentence count, Flow prompt count, generated image coverage, missing image indexes, TTS/render/source states, render outputs, failure class, and the next autonomous action.
  - Uses render report outputs when available, otherwise detects `output_shorts.mp4` and `output.mp4`.

- `GET /api/projects/{project_id}/operator-summary`
  - Added to `app/routers/render.py`.
  - This is now the first endpoint Cline/Qwen should read for video workflow state instead of probing many status/output endpoints and guessing.

- `scripts/newauto_stepwise_mcp.py`
  - Added `get_operator_summary(project_id="")`.
  - `diagnose_runtime(project_id="")` now prepends `operator_summary_json` when a project id is known.
  - `visible_tools` now exposes `get_operator_summary` so Cline/Qwen can select it explicitly.

Required Cline/Qwen behavior after this update:

1. For video workflow commands only, call `get_operator_summary` first.
2. If `recommended_next_tool` is `continue_video_workflow`, do not manually inspect `/output` as JSON and do not hand-drive Flow UI by inference.
3. If `human_intervention_required` is true or `recommended_next_tool` is `ask_openrouter_subagent`, use OpenRouter as an advisory failure classifier with the `operator_summary_json` payload.
4. For non-video commands, keep normal coding-assistant behavior.

Verification:

- `python -m py_compile app\services\operator_summary.py app\routers\render.py scripts\newauto_stepwise_mcp.py`
- `python -m pytest tests/test_render_report.py tests/test_feature_workflow.py -q`
- Result: 41 passed.

## 8.2 2026-05-14 implementation update: Flow generate-all worker

Implemented in newauto:

- `scripts/flow_generate_all_worker.py`
  - Runs the existing Playwright/direct Flow generator for all missing Flow prompt entries.
  - Writes `storage/projects/<project_id>/flow_generate_all_status.json`.
  - Writes `storage/projects/<project_id>/flow_run_log.json` with `runner=flow_playwright_direct`, `surface_mode=flow`, per-sentence status, attempts, attached assets, and failure class.
  - Updates project `body_image_state/body_image_phase/body_image_progress/body_image_error` so the workflow has worker-grade state instead of chat-context guesses.
  - Rebuilds `operator_summary.json` after completion or failure.

- `scripts/newauto_mcp.py`
  - `flow_generate` now starts the generate-all worker in the background instead of generating one sentence per Cline/Qwen turn.
  - Added `flow_generate_wait` step that only checks worker status, asset coverage, and next step.
  - This mirrors the MakeLens production line behavior: Cline/Qwen starts or checks the worker; the worker owns browser generation, result capture, attach, logging, and completion state.

- `app/services/operator_summary.py`
  - `operator_summary_json` now includes `flow_generate_all_status`, so Cline/Qwen can see running/done/error/partial status without probing random files or endpoints.

Required Cline/Qwen behavior after this update:

1. In video workflow mode, when `next_step=flow_generate`, call `continue_video_workflow` and let it start the worker.
2. While `next_step=flow_generate_wait`, do not manually click Flow or retry per sentence. Check `get_operator_summary` or `continue_video_workflow` only.
3. If worker status is `error` or `partial`, use `operator_summary_json` + `flow_run_log.json` for deterministic diagnosis, then escalate to OpenRouter only for repeated operational blockers or screenshot/UI ambiguity.
4. Non-video coding tasks remain normal assistant work.

Verification:

- `python -m py_compile app\services\operator_summary.py scripts\flow_generate_all_worker.py scripts\newauto_mcp.py`
- `python -m pytest tests/test_flow_files.py tests/test_render_report.py tests/test_feature_workflow.py -q`
- Result: 44 passed.
