# TUBE FACTORY 스타일 오디오/영상 자동화 앱 리서치

## 개요

### 최신 구현 메모

- 2026-05-06 기준으로 LM Studio Gemma4 + Flow Assisted HPSL 경로를 추가했다.
- `app/services/hpsl_script.py`는 source fact_notes를 HPSL JSON으로 생성하고, 1차 구현에서는 `sentences[].narration`을 평문 script로 조인해 기존 `compile_script()`/TTS/render 경로에 태운다. HPSL 원본은 `storage/projects/{pid}/hpsl_script.json`에 보존한다.
- `app/services/parse_utils.py`는 LM Studio/Gemma4 JSON 응답을 위해 markdown fence 제거, JSON 후보 추출, trailing comma 제거, bracket 보정이 가능한 `extract_json_from_llm_response()`를 제공한다.
- `app/services/flow_prompting.py`와 `app/routers/flow.py`를 추가해 문장별 Flow 프롬프트 manifest를 만들고, 사용자가 Flow에서 생성한 이미지/영상을 파일 선택으로 문장 asset에 연결할 수 있게 했다.
- Flow asset 업로드는 `media/flow_sentence_###.ext`와 `flow_assets/flow_sentence_###.ext`에 저장되고, `body_image_mappings`와 `media_order`에 연결되어 기존 scene/render plan이 그대로 사용할 수 있다.
- Step 2 UI에 `Flow Assisted` 패널을 추가했다. 사용자는 Flow 프롬프트 생성, Flow 열기, 프롬프트 복사, 문장별 결과 파일 첨부만 수행하면 된다.
- `VisualSourceMode`는 `flow_assisted`, `flow_auto`, `flow_then_comfyui_fallback`을 포함하도록 확장했고, `db.py`, `scene_plan.py`, `autopilot.py`의 기본 정규화 경로를 보강했다.
- 검증: `python -m compileall app`, `npm run typecheck:frontend`, Flow prompt/asset attach API smoke, 그리고 `tests/test_script_compile.py tests/test_scene_plan.py tests/test_render_plan.py tests/test_visual_relevance.py` 37개 테스트가 통과했다. 전체 pytest 수집은 기존 `tests/test_feature_workflow.py` 들여쓰기 오류로 중단된다.

- 2026-04-30 기준으로 SDXL prompt path 1차 구조화를 진행했다.
- `app/types.py`에 `SdxlDualPrompt`, `ControlNetDecision`, `LoraDecision`, `PromptRepairDecision` 타입과 `VisualBrief`의 optional 확장 필드가 추가되었다.
- `app/services/prompt_compiler.py`는 이제 단일 문자열 대신 `prompt_g`, `prompt_l`, `combined`를 담은 dual prompt 구조를 만들고, 기존 문자열 경로를 위한 `compile_positive_prompt_text()` wrapper를 함께 제공한다.
- `app/services/image_prompting.py`는 prompt suggestion payload에 `prompt_g`, `prompt_l`를 포함하고, 기존 `positive_prompt`는 `combined` 값으로 계속 유지한다.
- `app/services/comfyui_prompt_adapter.py`가 새로 추가되어 router/worker가 동일한 prompt placeholder bridge를 공유한다.
- SDXL ComfyUI 템플릿(`txt2img_sdxl_basic`, `lightning`, `stickman_lora`, `ipadapter_style`, `ipadapter_style_lora`, `controlnet_depth`)은 이제 `CLIPTextEncodeSDXL`의 `text_g`, `text_l`에 분리 placeholder를 사용한다.
- `app/services/prompt_repair.py`가 추가되어 issue code 기반 positive/negative prompt repair 결정을 만들 수 있게 되었고, `app/workers/image_worker.py`는 lightweight item에 대해 1회 bounded repair retry를 수행한다.
- worker now persists `candidate_reviews.repair_attempted`, `candidate_reviews.repair_reason`, and `candidate_reviews.repair_issue_codes`, so retry outcomes stay visible in project metadata even after a repair retry, a heavy-path skip, or a retry-limit exit.
- repair path is now dual-prompt aware: composition/content repairs stay in `prompt_g`, while style/camera repairs stay in `prompt_l`, so SDXL retry submissions no longer collapse back into one combined positive prompt.
- even when retry execution is skipped, worker now records repair suggestions in `candidate_reviews` (`suggested_positive_prompt`, `suggested_prompt_g`, `suggested_prompt_l`, `suggested_negative_prompt`, `suggested_repair_reason`) so operators can inspect the next-best prompt repair without rerunning analysis.
- Step 2 Generated Mapping UI now surfaces repair state and repair suggestions from `candidate_reviews`, including whether retry was executed or skipped plus suggested `prompt_g`/`prompt_l` previews for the next manual fix.
- Step 2 Generated Mapping cards now let operators apply a stored repair suggestion directly into the image prompt form, and manual ComfyUI job submission forwards `positive_prompt_g`/`positive_prompt_l` overrides when a repair suggestion was applied.
- repair issue codes and repair reasons now render with human-readable labels in Step 2, heavy-path suggestion policy adds ControlNet/LoRA/style-reference preservation hints, and Generated Mapping cards show current negative prompt versus suggested negative prompt for faster manual review.
- heavy style/control path는 추가 repair retry를 생략하고 로그로 남기도록 정리했다.
- 관련 검증으로 `tests.test_prompt_compiler`, `tests.test_comfyui_workflows`, `tests.test_comfyui_prompt_adapter`, `tests.test_image_prompting`, `tests.test_image_worker`, `tests.test_prompt_repair`와 typecheck가 통과했다.

- 2026-04-26 기준으로 TTS 경로를 `background task 직접 실행`에서 `queued -> tts_worker` 패턴으로 1차 전환했다.
- `app/main.py`는 render/source_draft/image/autopilot/tts worker의 stdout/stderr를 `storage/logs/*.log`로 남기도록 바뀌었다.
- `app/services/autopilot.py`는 더 이상 `run_tts_job(pid)`를 직접 호출하지 않고 `tts_state`를 `queued`로 등록한 뒤 worker 완료를 기다린다.
- `app/db.py`에는 `tts_error`, `tts_job_id`, `tts_started_at`, `tts_heartbeat_at` 메타데이터와 queued/running stale recovery가 추가되었다.
- `app/services/python_runtime.py`가 실제 `import omnivoice`, `import torch`, `torch.cuda.is_available()` probe로 OmniVoice Python 후보를 판정한다.
- `app/workers/tts_worker.py`는 이제 app Python에서 직접 OmniVoice를 import하지 않고, resolved Python으로 `scripts/run_tts_job.py --project-id PID`를 실행한다.
- `/api/system/health`는 OmniVoice path, import success, torch import, CUDA availability를 함께 반환한다.
- 아직 남은 핵심은 `gpu_guard.py` 원자성 보강과 health check/ComfyUI smoke를 운영 경로에 더 촘촘히 연결하는 것이다.

`C:\Users\petbl\newauto` 기준으로, FastAPI 기반 유튜브 영상 자동 제작 앱의 구조, 현재 구현 상태, 그리고 이 PC에서의 실행 가능 여부를 정리한 문서다.

앱은 다음 5단계 흐름으로 설계되어 있다.

1. 프로젝트 생성
2. 대본 입력
3. 미디어 업로드 및 순서 조정
4. OmniVoice TTS 생성과 FFmpeg 렌더링
5. YouTube OAuth 인증 및 업로드

## 현재 PC 점검 결과

- 저장소 위치: `C:\Users\petbl\newauto`
- Git 저장소: 2026-04-23 기준으로 로컬 Git 저장소 초기화 완료
- `origin`: `https://github.com/alarmpet/newauto.git`
- FFmpeg: 시스템 `PATH`에서 확인됨
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU
- CUDA: `torch.cuda.is_available() == True`
- 로컬 전용 OmniVoice 환경:
  - `C:\Users\petbl\newauto\omnivoice_env`
  - Python `3.10.11`
  - `omnivoice 0.1.4`
  - `torch 2.8.0+cu128`
  - `torchaudio 2.8.0+cu128`
- 보조 폴백 환경:
  - `C:\Users\petbl\music-auto\.venv_omnivoice`
- OmniVoice 헬스체크:
  - `storage/voice_samples/_healthcheck/healthcheck_male_low.wav`
  - `storage/voice_samples/_healthcheck/healthcheck_log.json`
  - 상태: `ok`
- YouTube OAuth 파일:
  - `storage/oauth/client_secret.json` 없음
  - `storage/oauth/token.json` 없음

## 완성된 구조

```text
C:\Users\petbl\newauto\
├─ app/
│  ├─ main.py                ← FastAPI 엔트리
│  ├─ config.py              ← 경로, 상수, Voice 프리셋
│  ├─ db.py                  ← SQLite 프로젝트/상태 관리
│  ├─ text.py                ← 대본 문장 분리 및 TTS 필터링
│  ├─ routers/
│  │  ├─ projects.py         ← 프로젝트 CRUD, 미디어 업로드/정렬
│  │  ├─ render.py           ← TTS/렌더 시작과 상태 조회
│  │  └─ youtube.py          ← OAuth 상태/인증, 업로드 시작
│  ├─ services/
│  │  ├─ tts.py              ← OmniVoice 래퍼와 TTS 실행
│  │  ├─ subtitle.py         ← SRT 생성
│  │  ├─ render.py           ← FFmpeg 오디오 결합, 영상 생성, 자막 합성
│  │  └─ yt_upload.py        ← YouTube resumable upload
│  └─ static/
│     ├─ index.html          ← 단일 페이지 UI
│     ├─ style.css           ← 스타일
│     └─ app.js              ← 프런트 상태/요청 처리
├─ scripts/
│  ├─ check_omnivoice_health.py
│  ├─ generate_voice_samples.py
│  ├─ open_browser.ps1
│  ├─ resolve_omnivoice_python.ps1
│  └─ typecheck.ps1
├─ tests/
├─ storage/
│  ├─ app.db
│  ├─ oauth/
│  ├─ projects/
│  └─ voice_samples/
├─ requirements.txt
├─ requirements-dev.txt
├─ run.bat
└─ research.md
```

## 주요 구현 내용

### 백엔드 구조

- `app/main.py`
  - FastAPI 앱을 초기화하고 라우터를 등록한다.
  - startup 시 SQLite 초기화를 수행한다.
- `app/db.py`
  - `projects` 테이블을 관리한다.
  - 앱 기동 시 누락된 컬럼을 자동 추가하는 마이그레이션 로직이 있다.
- `app/text.py`
  - 대본을 문장 단위로 분리한다.
  - 구두점만 있는 조각이나 읽을 수 없는 텍스트는 TTS 대상에서 제거한다.
- `app/services/tts.py`
  - OmniVoice를 lazy import 하므로 ML 의존성이 없어도 기본 UI 개발은 가능하다.
  - CUDA 가능 시 `float16`, 아니면 `float32`를 선택한다.
  - 문장별 WAV와 `timings.json`을 생성한다.
- `app/services/render.py`
  - FFmpeg 존재 여부를 확인한다.
  - TTS WAV를 하나로 합치고, 자막을 만들고, 미디어와 오디오를 mux 한다.
- `app/services/yt_upload.py`
  - Google OAuth와 YouTube 업로드를 담당한다.
  - 실제 업로드는 OAuth 파일이 있어야 가능하다.

### 프런트엔드 구조

- 사이드바 기반 단일 페이지 UI
- 프로젝트 선택, 대본 저장, 미디어 업로드, TTS, 렌더링, 업로드 상태를 한 화면에서 처리
- 업로드 상태와 워크플로우 상태를 분리해서 보여줌
- 미디어 순서 재정렬 지원

## 실행 방법

### 1. 개발 서버 실행

`run.bat` 는 아래 순서로 동작한다.

- OmniVoice 실행용 Python 경로를 자동 탐색
- 기본 브라우저에서 `http://127.0.0.1:8000` 오픈
- Uvicorn 개발 서버 실행

우선순위는 다음과 같다.

1. `OMNIVOICE_PYTHON` 환경 변수
2. `OMNIVOICE_ENV_DIR\Scripts\python.exe`
3. 로컬 `omnivoice_env\Scripts\python.exe`
4. `C:\Users\petbl\music-auto\.venv_omnivoice\Scripts\python.exe`

실행:

```powershell
.\run.bat
```

### 2. 타입 체크

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1
```

이 스크립트는 다음을 수행한다.

- 프런트엔드 `tsc`
- OmniVoice Python 환경을 자동 탐색한 뒤 `mypy`

### 3. OmniVoice 연결 확인

```powershell
.\omnivoice_env\Scripts\python.exe .\scripts\check_omnivoice_health.py
```

검증 항목:

- 런타임 device/dtype 결정
- 모델 로드
- 단문 추론
- WAV 저장

### 4. YouTube 업로드 사용

현재 이 PC에는 OAuth 파일이 없으므로 업로드 기능은 아직 미연결 상태다.

필요 파일:

- `storage/oauth/client_secret.json`
- 최초 인증 후 생성되는 `storage/oauth/token.json`

절차:

1. Google Cloud Console에서 데스크톱 앱용 OAuth Client ID를 발급한다.
2. `client_secret.json` 을 `storage/oauth/client_secret.json` 에 둔다.
3. 앱에서 `Authorize` 를 실행한다.
4. 브라우저 인증 완료 후 `token.json` 이 생성되면 업로드 가능하다.

## 테스트 및 검증 메모

2026-04-23 기준 확인한 내용:

- `app.main` import 성공
- 로컬 `omnivoice_env` 에 OmniVoice 및 프로젝트 의존성 설치 완료
- OmniVoice 헬스체크 성공
- FFmpeg 명령 사용 가능

## 2026-04-26 운영 안전장치 1차 구현 메모

- `app/services/usage_registry.py`
  - provider별 day/month usage schema 추가
  - 기존 `storage/brave_usage.json` 을 읽어 `brave_search` usage 로 호환
  - Brave 예약 시 provider usage 와 legacy 파일을 함께 갱신
- `app/services/tool_registry.py`
  - `ffmpeg`, `ollama`, `comfyui`, `faster-whisper`, `yt-dlp`, `playwright-mcp` 상태 점검
  - `/api/system/tools` 에서 설치 여부, 설정 여부, version, install path 노출
- `app/services/gpu_guard.py`
  - 간단한 file-based GPU owner lock 추가
  - `/api/system/operator` 에서 현재 owner/resource/expires_at 노출
- `app/services/system_health.py`
  - 기존 disk/oauth/ffmpeg health 유지
  - operator status 에 queue 집계, tool registry, usage 목록, gpu 상태 결합

현재는 operator API 와 backend registry 까지 구현된 상태다. 실제 worker/TTS/ComfyUI 진입점에 GPU acquire/release 를 붙이는 작업은 다음 단계다.

이번 변경 검증:

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 54 source files`
- `python -m pytest tests/test_system_operator.py tests/test_source_research.py tests/test_feature_workflow.py tests/test_source_worker.py tests/test_source_draft.py -q`
  - `39 passed`
- 테스트를 위해 `python-multipart` 패키지를 사용자 환경에 설치했다.

## 2026-04-26 GPU 경합 제어 1차 연결 메모

- `app/workers/source_draft_worker.py`
  - GPU lock 획득 전 `wait_gpu` phase 로 대기
  - 현재 owner 를 `source_draft_last_log` 에 표시
  - 획득 후 Ollama draft 생성, 종료 시 release
- `app/services/tts.py`
  - preview 와 full TTS job 에 GPU acquire/release 연결
  - source draft 가 GPU를 잡고 있으면 Ollama unload 를 한 번 시도한 뒤 재시도
  - GPU가 계속 busy 면 preview 는 route 에서 409 로 응답
  - 테스트 환경/비모델 환경에서도 동작하도록 `OmniVoiceGenerationConfig` import 실패 시 fallback config 제공
- `app/routers/render.py`
  - TTS preview 의 GPU busy 오류를 500 이 아닌 409 로 변환

추가 검증:

- `python -m pip install soundfile`
  - 현재 Python 테스트 환경에 `soundfile` 설치
- `python -m pytest tests/test_tts_pipeline.py tests/test_source_worker.py tests/test_system_operator.py -q`
  - `19 passed`
- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 54 source files`

## 2026-04-26 Operator UI 1차 연결 메모

- `app/static/index.html`
  - Step 4 Render Readiness 영역에 `Operator` 버튼과 결과 패널 추가
- `app/static/app.js`
  - `/api/system/operator` 호출
  - queue, GPU owner, usage, tool 상태를 한 번에 렌더링
- `app/static/style.css`
  - operator grid/section 기본 스타일 추가

이번 단계는 polling 없이 수동 조회 버튼 방식으로 붙였다. 다음 단계에서 plan 에 적은 대로 live(1.5s) / static(30s) 분리를 적용하면 된다.

추가 검증:

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 54 source files`
- `python -m pytest tests/test_feature_workflow.py tests/test_system_operator.py -q`
  - `30 passed`

## 2026-04-26 Model registry / polling 분리 메모

- `app/services/model_registry.py`
  - Script LLM, OmniVoice, ComfyUI checkpoints/loras 상태를 파일/설정 기준으로 노출
  - 외부 API 조회 없이 현재 로컬 환경 기준의 모델 인벤토리 제공
- `app/services/system_health.py`
  - operator payload 에 `models` 추가
- `app/static/app.js`
  - operator panel 에 models 섹션 추가
  - polling 분리:
    - 프로젝트 상태 `1.5s`
    - operator 상태 `30s`
  - 프로젝트 open 직후 operator status 1회 즉시 조회

추가 검증:

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 55 source files`
- `python -m pytest tests/test_system_operator.py tests/test_feature_workflow.py -q`
  - `30 passed`

## 2026-04-26 ComfyUI 연결 계층 1차 구현 메모

- `app/services/comfyui_workflows.py`
  - workflow template 로드
  - `__POSITIVE_PROMPT__`, `__NEGATIVE_PROMPT__`, `__SEED__`, `__WIDTH__`, `__HEIGHT__`, `__FILENAME_PREFIX__` placeholder 치환
  - exact placeholder 는 숫자 타입 유지
- `app/services/comfyui_client.py`
  - `POST /prompt`
  - `GET /history/{prompt_id}`
  - history payload 에서 image 결과 추출
- `app/workflow_templates/comfyui/txt2img_sdxl_basic.json`
  - 기본 SDXL txt2img 템플릿 추가
- `app/routers/image_gen.py`
  - `/api/projects/{pid}/comfyui/workflow/render`
  - `/api/projects/{pid}/comfyui/workflow/submit`
  - submit 시 `body_image_state="running"` / `body_image_progress=10` 으로 기본 상태 반영

현재 단계는 ComfyUI worker 없이도 서버에서 workflow 를 렌더하고 로컬 ComfyUI에 제출할 수 있는 최소 API를 확보한 상태다.

추가 검증:

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 61 source files`
- `python -m pytest tests/test_comfyui_workflows.py tests/test_comfyui_client.py tests/test_comfyui_routes.py -q`
  - `7 passed`

## 2026-04-26 ComfyUI 결과 import 1차 구현 메모

- `app/routers/image_gen.py`
  - `/api/projects/{pid}/comfyui/history/{prompt_id}`
  - `/api/projects/{pid}/comfyui/history/import`
  - ComfyUI output 파일을 프로젝트 `media/` 로 복사
  - `media_order`, `body_image_state`, `body_image_progress`, `body_image_mappings` 갱신
- output 파일 경로 해석:
  - 우선 `COMFYUI_INSTALL_DIR / result.type / subfolder / filename`
  - 없으면 `COMFYUI_INSTALL_DIR / output / filename` fallback

이 단계까지로 ComfyUI 생성 결과를 프로젝트 미디어 흐름 안으로 편입할 수 있게 됐다. 다음 단계는 worker 가 submit 후 history 완료까지 폴링한 뒤 자동 import 하는 흐름이다.

추가 검증:

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 61 source files`
- `python -m pytest tests/test_comfyui_workflows.py tests/test_comfyui_client.py tests/test_comfyui_routes.py -q`
  - `9 passed`

## 2026-04-26 ComfyUI 이미지 작업 UI 1차 연결 메모

- `app/routers/projects.py`
  - `PUT /api/projects/{pid}/features` 에 `visual_source_mode` 저장 지원 추가
- `app/static/index.html`
  - Step 2 Media 화면에 `AI Image Gen` 패널 추가
  - visual source mode, checkpoint, width/height, seed, sentence index, positive/negative prompt 입력 추가
  - `이미지 생성 큐 등록` 버튼과 generated mapping 목록 추가
- `app/static/app.js`
  - `enqueueImageGen()` 추가
  - `/features` 저장 후 `/comfyui/job` enqueue 흐름 연결
  - `body_image_state/progress/phase/last_log/error` 를 기반으로 상태 카드 렌더링
  - `body_image_mappings` 를 프로젝트 media 미리보기와 함께 표시
- `app/static/style.css`
  - image gen panel / mapping preview 레이아웃 추가

이 단계로 Step 2 에서 다음 흐름이 가능해졌다.

1. visual source mode 를 `upload_only / hybrid / comfyui_auto` 중 선택
2. ComfyUI용 프롬프트와 기본 파라미터 입력
3. 이미지 생성 작업을 큐에 등록
4. 진행 상태와 마지막 로그를 브라우저에서 확인
5. 완료 후 생성 이미지가 media 및 mapping 목록에 반영

추가 검증

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 64 source files`
- `python -m pytest tests/test_feature_workflow.py tests/test_image_worker.py tests/test_comfyui_routes.py -q`
  - `33 passed`

## 2026-04-26 ComfyUI 프롬프트 추천 1차 구현 메모

- `app/services/image_prompting.py`
  - 현재 프로젝트의 `sentences`, `source_draft_fact_notes`, `source_draft_sources`, `content_mode` 를 바탕으로 ComfyUI용 기본 positive/negative prompt 생성
  - 일반 영상은 `documentary still frame`, 성경 롱폼은 `reverent biblical illustration` 스타일로 분기
- `app/routers/image_gen.py`
  - `GET /api/projects/{pid}/comfyui/prompt-suggestion?sentence_idx=...` 추가
- `app/static/index.html`
  - Step 2 `AI Image Gen` 패널에 `프롬프트 추천` 버튼 추가
- `app/static/app.js`
  - 추천 API 호출 후 positive prompt 자동 채움
  - negative prompt 가 비어 있을 때만 기본 negative prompt 자동 채움

이번 단계로 사용자는 매번 프롬프트를 처음부터 쓰지 않아도, 이미 작성된 대본 문장과 Source Assist fact note 를 기반으로 기본 장면 프롬프트를 바로 받을 수 있다.

추가 검증

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 66 source files`
- `python -m pytest tests/test_image_prompting.py tests/test_comfyui_routes.py -q`
  - `7 passed`

## 2026-04-26 ComfyUI multi-scene batch 1차 구현 메모

- `app/routers/image_gen.py`
  - `GET /api/projects/{pid}/comfyui/prompt-suggestions?start_idx=&count=` 추가
  - `POST /api/projects/{pid}/comfyui/job/batch-auto` 추가
  - source prompt suggestion 결과를 여러 문장 범위로 확장해서 batch queue payload 생성
- `app/workers/image_worker.py`
  - `body_image_options.batch_items` 지원
  - 한 프로젝트 이미지 작업 안에서 여러 scene 을 순차 submit -> history poll -> import 하도록 확장
  - 진행률/로그를 `n/total` 기준으로 업데이트
- `app/static/index.html`
  - Step 2 `AI Image Gen` 패널에 `Batch Start`, `Batch Count`, `선택 구간 일괄 생성` 추가
- `app/static/app.js`
  - batch auto enqueue 호출 추가
  - 일괄 생성 등록 후 body image 상태 카드와 visual source mode 상태 동기화

이번 단계로 사용자는 Step 2 에서 문장 시작 번호와 개수만 정하면 여러 장면을 한 번에 큐에 넣을 수 있다. worker 는 각 장면을 순차 생성하고 media / body_image_mappings 에 계속 누적한다.

추가 검증

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 66 source files`
- `python -m pytest tests/test_image_worker.py tests/test_comfyui_routes.py tests/test_image_prompting.py -q`
  - `12 passed`

## 2026-04-26 Scene Plan 1차 구현 메모

- `app/types.py`
  - `ScenePlan`, `ScenePlanScene` 타입 추가
- `app/db.py`
  - `scene_plan` 컬럼 및 migration 추가
  - project load/save 경로에 `scene_plan` 직렬화 연결
- `app/services/scene_plan.py`
  - `tts/timings.json`, `regional_sentences`, `body_image_mappings`, `source_draft_fact_notes` 를 합쳐 장면 계획 생성
  - timing 이 있으면 실제 `dur` 사용, 없으면 문장 길이 기반 보수적 fallback duration 사용
- `app/routers/projects.py`
  - `GET /api/projects/{pid}/scene-plan`
  - `POST /api/projects/{pid}/scene-plan/build`
- `app/static/index.html`
  - Step 2 `Scene Plan 생성` 버튼 및 scene plan preview 영역 추가
- `app/static/app.js`
  - scene plan build 호출 후 프로젝트 상태에 반영
  - 장면 번호 / 문장 인덱스 / region / duration / prompt / media 연결 상태 미리보기 렌더링

이 단계로 생성된 이미지와 문장 사이의 관계가 단순 mapping 을 넘어서 “얼마나 길게, 어떤 의도로, 어떤 스타일로 보여줄 장면인지”라는 계획 데이터로 저장되기 시작했다.

추가 검증

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 68 source files`
- `python -m pytest tests/test_scene_plan.py tests/test_comfyui_routes.py tests/test_image_worker.py -q`
  - `12 passed`

## 2026-04-26 Render Plan 1차 구현 메모

- `app/services/render_plan.py`
  - `scene_plan` 을 `render_plan` segment 구조로 변환
  - scene 별 `duration_sec` 를 누적해 `start/end` 계산
  - 연결된 `media_path` 를 render segment media 로 반영
- `app/routers/projects.py`
  - `GET /api/projects/{pid}/render-plan`
  - `POST /api/projects/{pid}/render-plan/build`
- `app/services/render.py`
  - render 시작 시 `scene_plan` 이 있으면 `render_plan` 을 우선 구성/저장
  - 실제 visual build 에서는 `render_plan` 의 media 경로를 우선 사용
  - `render_plan` 에 usable media 가 없을 때만 기존 `media_order` fallback
- `app/static/index.html`
  - Step 2 `Render Plan 생성` 버튼 및 render plan preview 영역 추가
- `app/static/app.js`
  - render plan build 호출
  - segment start/end 및 media 목록 preview 렌더링

이 단계로 scene/image 수준에서 만든 계획 데이터가 실제 render input selection 으로 이어지기 시작했다. 아직 motion/effect/caption style 까지 확장되진 않았지만, 장면별 시간대와 연결 media 를 렌더가 인지하는 최소 구조는 만들어졌다.

추가 검증

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 70 source files`
- `python -m pytest tests/test_render_plan.py tests/test_scene_plan.py tests/test_render_visual_track.py -q`
  - `15 passed`

## 2026-04-26 Render Plan 연출 메타데이터 1차 구현 메모

- `app/types.py`
  - `RenderPlanSegment` 에 `motion`, `effect`, `caption_style` 추가
- `app/db.py`
  - render plan load path 에 새 필드 fallback 파싱 추가
- `app/services/render_plan.py`
  - region / duration 기반 기본 연출값 빌드
    - intro: `emphasis`, 짧지 않으면 `fade`
    - bible: `quote`, `slow_zoom_out`
    - body: `plain`, `slow_zoom_in`
- `app/static/app.js`
  - Render Plan preview 에 motion / effect / caption style 표시

이번 단계는 실제 FFmpeg 연출 로직을 전부 바꾼 건 아니지만, render plan 이 이제 단순 시간 구간이 아니라 “어떻게 보여줄지”에 대한 메타데이터를 갖기 시작했다는 점에서 다음 단계 자동화의 기반이 된다.

추가 검증

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `Success: no issues found in 70 source files`
- `python -m pytest tests/test_render_plan.py tests/test_scene_plan.py tests/test_render_visual_track.py -q`
  - `15 passed`

추가로 권장되는 검증:

- `python -m unittest discover -s tests -v`
- 실제 브라우저에서 프로젝트 생성 → 대본 저장 → TTS → 렌더 → 출력 확인
- OAuth 파일 배치 후 YouTube 업로드 연동 테스트

## 2026-04-22 Update

### Architecture changes

- Added project-level media upload tracking fields in SQLite:
  - `media_upload_state`
  - `media_upload_progress`
  - `media_upload_completed`
  - `media_upload_total`
  - `media_upload_error`
- Added schema migration logic in `app/db.py` so existing local databases gain the new columns automatically at startup.
- Expanded `/api/projects/{pid}/status` to include media upload state so the browser can distinguish upload transfer, server save progress, and post-upload readiness.
- Changed `/api/projects/{pid}/media` to return a richer payload with:
  - updated project snapshot
  - accepted file list
  - skipped file list
- Hardened `/api/projects/{pid}/media/order` so partial reorder payloads do not accidentally drop existing media entries.

### Workflow changes

- Split "workflow progress" from "media upload progress" in the browser UI.
- Added a dedicated upload status panel with:
  - browser transfer progress
  - server-side save progress
  - accepted/skipped file summary
- Upgraded media confirmation UX so uploaded images and videos can be:
  - checked immediately in the browser
  - previewed in a larger panel
  - reordered via drag and drop
  - reordered via left/right controls
- Prevented concurrent confusion by disabling the media picker while an upload request is active.
- Blocked render start while media upload state is still `running`.

### Typing and verification workflow

- Added `app/types.py` TypedDict-based response and project types for backend state consistency.
- Added frontend type checking with `@ts-check` and `tsc` via `tsconfig.json`.
- Added backend type checking with `mypy` via `mypy.ini` and `requirements-dev.txt`.
- Added `tests/test_media_workflow.py` to verify:
  - mixed media upload response shape
  - skipped file reporting
  - media upload status persistence
  - reorder persistence without dropping unspecified files
- Added `scripts/typecheck.ps1` as a single verification entry point for frontend and backend type checks.

## 2026-04-23 Update

### OmniVoice validation

- Confirmed real OmniVoice inference works in this environment with CUDA enabled.
- Added `scripts/check_omnivoice_health.py` to validate:
  - model load
  - runtime device/dtype resolution
  - one-sentence inference
  - WAV output writing
- Healthcheck output location:
  - `storage/voice_samples/_healthcheck/healthcheck_male_low.wav`
  - `storage/voice_samples/_healthcheck/healthcheck_log.json`

### New male voice presets

- Added five new male voice presets:
  - `male-30s-40s-lowmid`
  - `male-40s-50s-lowmid`
  - `male-announcer-30s-40s`
  - `male-low-30s-40s`
  - `male-pastor-30s-40s`
- Exact age bands and persona nuance are approximated with OmniVoice-supported `instruct` tokens plus `pitch` and optional `speed`.
- Added matching Korean labels for the UI TTS dropdown.

### Voice sample generation

- Added `scripts/generate_voice_samples.py` for repeatable preset sample generation.
- Default output directory:
  - `storage/voice_samples/2026-04-male-presets/`
- Generated artifact layout:
  - preset-specific `.wav` files
  - `manifest.json` with preset id, label, output filename, and kwargs

### Workflow changes

- Updated `run.bat` to open the default browser to `http://127.0.0.1:8000`.
- Kept the launch flow simple by leaving Uvicorn as the foreground process while browser opening runs in a short-lived background process.

### TTS robustness changes

- Centralized script sentence normalization in `app/text.py` so script save and TTS execution share the same filtering rules.
- Filtered punctuation-only and separator-only fragments before TTS synthesis.
- Hardened `run_tts_job()` to:
  - normalize legacy stored sentence lists before synthesis
  - fail fast on empty OmniVoice audio buffers
  - clear stale partial `.wav` outputs and `timings.json` before and after failed runs
- Added `tests/test_tts_pipeline.py` to verify:
  - punctuation-only fragments are removed from split results
  - legacy stored projects are normalized during TTS runs
  - stale TTS artifacts are removed after empty-audio failures

## 2026-04-23 Thumbnail and Subtitle Settings Update

### Architecture changes

- Added project-level thumbnail and subtitle style fields in SQLite:
  - `thumbnail_file`
  - `subtitle_style`
- Added migration logic so existing local databases gain the new columns automatically.
- Extended project and status response types to include thumbnail metadata and effective subtitle style.
- Added typed subtitle style defaults and normalization in `app/services/subtitle.py`.
- Kept SRT generation for compatibility and added ASS generation for styled render output.

### Workflow changes

- Added a separate YouTube thumbnail workflow under the Media step:
  - upload one thumbnail independently from render media
  - replace the previous thumbnail on new upload
  - preview and delete the current thumbnail
- Added a Subtitle Style panel under the Render step with controls for:
  - font family
  - font size
  - text color
  - outline color and width
  - shadow
  - top/middle/bottom position
  - vertical margin
  - background color and opacity
  - line length
  - none/fade/pop effect
- Changed render output to generate `subtitles.ass` and mux it with FFmpeg using the ASS filter.
- Added YouTube thumbnail integration after successful video upload by calling `thumbnails.set` when a thumbnail exists.

### Verification

- Added backend tests for thumbnail upload, replacement, retrieval, deletion, and invalid file rejection.
- Added tests for subtitle style merge/validation and ASS subtitle output.
- Added a mocked YouTube upload test that verifies thumbnail upload is triggered.
- Verified frontend and backend type checks with `scripts/typecheck.ps1`.

## 2026-04-23 Subtitle Display Enhancement Update

### Architecture changes

- Expanded subtitle style typing to support five subtitle anchors:
  - `top`
  - `upper`
  - `middle`
  - `lower`
  - `bottom`
- Added two new subtitle style fields:
  - `margin_h`
  - `min_display_sec`
- Updated subtitle normalization so legacy stored projects still load safely without a database migration.
- Reworked subtitle rendering helpers so both SRT and ASS output share:
  - smarter two-line wrapping
  - minimum display-time extension for short cues

### Render and workflow changes

- Replaced the old simple midpoint wrapping with a smarter split strategy that prefers:
  - sentence-ending punctuation
  - secondary punctuation
  - whitespace
  - midpoint fallback
- Kept subtitle output to a maximum of two lines per cue.
- Added fixed-screen anchor handling for `upper`, `middle`, and `lower` positions while preserving `margin_v` control for `top` and `bottom`.
- Switched ASS horizontal safe area from hardcoded values to project subtitle style `margin_h`.
- Added frontend controls for:
  - five-position subtitle placement
  - horizontal margin
  - minimum display seconds
  - four subtitle presets
- Expanded the render preview so the browser reflects the new position anchors and horizontal subtitle width changes.

### Verification

- Extended subtitle rendering tests to cover:
  - five-position ASS output
  - horizontal margin propagation
  - minimum display-time extension
  - long-line wrapping into two lines
- Verified `scripts/typecheck.ps1`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-23 Feature Recommendation Implementation Update

### Architecture changes

- Expanded project storage and response types to support:
  - `kenburns_enabled`
  - `bgm_file`
  - `bgm_volume_db`
  - `bgm_ducking_enabled`
  - `render_formats`
  - `youtube_schedule_at`
- Added schema migration entries in `app/db.py` so existing local databases pick up the new feature fields automatically.
- Added new backend services:
  - `app/services/preflight.py`
  - `app/services/system_health.py`
  - `app/services/transcribe.py`
  - `app/services/stock.py`
- Added new routers:
  - `app/routers/system.py`
  - `app/routers/stock.py`

### Workflow changes

- Added render pre-flight inspection through `GET /api/projects/{pid}/preflight`.
- Added system diagnostics through `GET /api/system/health`.
- Added loudnorm normalization before final mux.
- Added optional Ken Burns motion for image-based visual tracks.
- Added BGM upload, storage, and render-time mixing with optional ducking.
- Added selectable landscape / shorts render outputs.
- Added project cloning for reusable settings and optional copied assets.
- Added YouTube upload scheduling input support and post-upload statistics lookup.
- Added `timings_words.json` generation and karaoke-style ASS subtitle output.
- Added stock media search aggregation for Pexels and Pixabay.

### Verification

- Added `tests/test_feature_workflow.py` to cover:
  - pre-flight reporting
  - feature setting persistence
  - BGM upload
  - project cloning
  - system health route
  - shorts output route
  - karaoke render path
  - stock search service
  - YouTube stats route
- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-23 OmniVoice Tuning P0 Update

### Architecture changes

- Added `app/tts_profiles.py` as the shared source of truth for TTS preset definitions, legacy preset alias normalization, language detection, and `tts_profile` normalization.
- Extended the project persistence model with `tts_profile` JSON storage so voice tuning is no longer limited to a single preset string.
- Added `app/services/tts_profile.py` as a thin export layer for TTS profile helpers reused by scripts and future UI work.

### Workflow changes

- Step 3 now captures and persists a structured TTS profile:
  - `mode`
  - `language`
  - `instruct`
  - `speed`
  - `duration`
  - `num_step`
  - `guidance_scale`
  - `denoise`
  - `postprocess_output`
- TTS execution now passes `language` and `OmniVoiceGenerationConfig` into `OmniVoice.generate(...)`.
- Replaced the old narrow male-low preset cluster with a broader preset set for clearer contrast in Korean workflows.
- Preserved backward compatibility by mapping old preset ids such as `male-calm` and `narrator` onto the new canonical presets.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-24 Render Visual Track Stability Update

### Architecture changes

- Changed FFmpeg and ffprobe subprocess handling in `app/services/render.py` to collect raw bytes and decode as UTF-8 with replacement so Windows locale differences no longer hide stderr.
- Added media dimension probing and reusable invalid-media detection to catch unreadable or metadata-less inputs before the render pipeline reaches concat.
- Tightened the Ken Burns image branch so `zoompan` now emits the explicit target resolution instead of silently falling back to FFmpeg defaults.

### Workflow changes

- Render jobs now enter a `validate_media` phase before building the visual track.
- Step 4 error logs now surface a short Korean explanation for common FFmpeg failures such as concat size mismatches and invalid input media.
- Pre-flight now includes a `media_metadata` check so users can spot broken media before launching render.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-24 Render Progress Visibility Update

### Architecture changes

- Added render progress state fields to project persistence for phase-local progress, progress detail text, last observed FFmpeg speed, and ETA.
- Added `_run_with_progress()` in `app/services/render.py` using `subprocess.Popen` plus FFmpeg `-progress pipe:1` parsing with concurrent stdout/stderr draining.
- Reused the new progress runner for `normalize_audio`, visual track build, and mux steps so long-running FFmpeg stages can stream status instead of only reporting completion.

### Workflow changes

- Step 4 can now show per-phase progress details such as percent, speed, frame count, elapsed time, and ETA while render is running.
- When ETA is not reliable, the UI falls back to a size-based or heartbeat-style detail string instead of looking frozen.
- Running renders no longer show the idle placeholder while progress detail is being collected.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-24 Interrupted Task Recovery Update

### Architecture changes

- Added `db.recover_interrupted_tasks()` to convert stale `running` task states into recoverable error states when the server starts again.
- Wired startup to call interrupted-task recovery immediately after `init_db()`, so background jobs that cannot survive a restart no longer remain stuck as `running`.

### Workflow changes

- After a server restart, interrupted render, TTS, upload, and media upload jobs are automatically marked as interrupted instead of blocking new actions with stale `running` state.
- Render-specific transient fields such as phase, per-phase progress, speed, and ETA are reset during recovery so the UI starts from a clean state on the next attempt.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-24 Step 4 Inline Help Update

### Workflow changes

- Added inline help badges to the Step 4 render controls so users can see what each render toggle does without leaving the screen.
- Added inline help badges to the Step 4 subtitle style controls covering font, size, colors, outline, shadow, placement, margins, timing, background, line length, and effects.
- Help content is shown on hover and keyboard focus, so the screen stays compact while remaining readable and accessible.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-24 Additional Male Voice Presets Update

### Architecture changes

- Extended the canonical TTS preset catalog with three new middle-aged male presets:
  - `male-40s-50s-lowmid`
  - `male-announcer-40s-50s`
  - `male-pastor-40s-50s`
- Because Step 3 already hydrates from `/api/tts/presets`, the new presets automatically flow into the runtime dropdown and sample-preview path.
- Updated `scripts/generate_voice_samples.py` to continue following the canonical preset catalog, so regenerated sample sets include the new presets without extra wiring.

### Workflow changes

- Users can now choose the new 40s~50s male styles in Step 3 and immediately test them with the existing `샘플 듣기` flow.
- The new presets use supported OmniVoice voice-design token combinations based on `male`, `middle-aged`, `low pitch`, and `moderate pitch`.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.
- Verified the preset catalog exposes the new labels and instruct tokens.

## 2026-04-24 Render stderr None Crash Fix

### Architecture changes

- Hardened `app/services/render.py` log helpers so render bookkeeping no longer assumes FFmpeg always returns stderr text.
- `_tail_lines()` now accepts nullable text safely.
- `_run()` now uses the safe tail helper in both success and failure branches.

### Workflow changes

- Rendering no longer crashes with `NoneType.strip` during `build_visual_landscape` or other FFmpeg phases when stderr is empty or missing.
- If FFmpeg actually fails without stderr output, the renderer now raises a fallback runtime message instead of a secondary Python attribute error.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.
- Added regression tests for:
  - `_tail_lines(None)`
  - `_tail_lines("   ")`
  - `_run()` success with `stderr=None`
  - `_run()` failure with `stderr=None`

## 2026-04-23 OmniVoice Preview Error Fix

### Architecture changes

- Replaced custom free-form preset `instruct` strings with OmniVoice-supported voice design tokens such as `male, low pitch` and `whisper, young adult`.
- Added explicit preview error translation in the TTS preview route so invalid preview profiles return a client-visible `400` instead of an internal server error.

### Workflow changes

- `샘플 듣기` now uses preset instructions that OmniVoice can resolve without crashing.
- Blank preview requests continue to use the shared sample text, and language detection now uses a clean Hangul regex.
- When a preview profile is invalid, the UI receives the validation message instead of a generic `500`.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.
- Reproduced `/api/projects/{pid}/tts/preview` returning `200` for a valid profile after the fix.

## 2026-04-24 TTS Gender Mismatch Deterministic Fix

### Architecture changes

- Added `/api/tts/presets` as the single source of truth for TTS preset order, labels, legacy aliases, canonical preset payloads, and shared sample text.
- Extended typed contracts with `TtsPresetCatalogResponse`.
- Updated `scripts/generate_voice_samples.py` to use the canonical backend preset catalog instead of its own preset subset.

### Workflow changes

- Step 3 now hydrates the voice dropdown from the backend preset catalog instead of relying on a duplicated frontend preset table.
- Legacy preset ids such as `male-30s-40s-lowmid` are normalized to canonical ids before the UI uses them.
- Selecting a preset now rewrites the full Step 3 form from the canonical preset definition.
- Added a dirty-state rule so unchanged preset selections do not keep sending stale advanced overrides.
- Added effective profile visibility in Step 3:
  - current canonical preset id
  - mode
  - language
  - instruct
  - speed
  - sampling parameters
- Added a warning badge when advanced controls are overriding the preset defaults.
- Loading an old project saved with a legacy preset now resolves to the canonical male/female preset path instead of silently falling through.

### Remaining limitation

- This fixes deterministic app-level gender mismatches caused by stale form state and preset alias drift.
- Korean voice-design consistency at the model level may still require further evaluation or clone-mode expansion.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-23 TTS Preview Update

### Architecture changes

- Added a dedicated TTS preview API that synthesizes a short sample with the current voice preset and tuning profile without running the full project TTS job.
- Added `TtsPreviewResponse` to keep the preview payload typed across the API and frontend.

### Workflow changes

- Step 3 now includes a sample text box, a `샘플 듣기` action, and an inline audio player.
- Preview generation writes `tts_preview.wav` under the project directory and exposes it through a dedicated audio route.
- Preview synthesis uses the same normalized preset and `tts_profile` pipeline as the real TTS job, so users can hear the actual tuning differences before launching full generation.
- Cleaned the default OmniVoice sample text and Hangul language detection so blank preview requests use a readable Korean sample.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-23 Render And Subtitle Fixes Update

### Architecture changes

- Extended project persistence with `render_phase` and `render_last_log` so render jobs can expose the current stage and recent FFmpeg output instead of only a coarse percentage.
- Added `scripts/check_encoding.py` and wired it into `scripts/typecheck.ps1` so mojibake in user-facing files is caught during the normal validation flow.

### Workflow changes

- Render jobs now update status by phase, including media preparation, audio concatenation, loudness normalization, subtitle generation, and per-format mux steps.
- Step 4 now shows the active render phase and the latest render log snippet in the UI.
- Subtitle defaults were tightened for readability:
  - default `max_line_chars` reduced to `26`
  - width-aware effective line length calculation based on `font_size` and `margin_h`
  - smarter two-line wrapping for long cues
- `lower` subtitle placement was rebalanced so preview and actual ASS rendering land closer to the intended lower-third area.
- Rewrote the main static HTML entry and remaining critical app.js messages as clean UTF-8 Korean strings for render, upload, thumbnail, and OAuth flows.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-24 Render Performance And Worker Separation Update

### Architecture changes

- Extended render persistence with:
  - `render_job_id`
  - `render_started_at`
  - `render_heartbeat_at`
- Switched SQLite connections to WAL mode with a busy timeout so the web app, render worker, and watchdog can share the same database more safely.
- Added a detached render worker entry point under `app/workers/` plus a single-instance lock file guard.
- Added watchdog-based stale render recovery in startup flow so abandoned `running` renders are converted back into recoverable errors.
- Added a test-only background-worker disable switch through `NEWAUTO_DISABLE_BACKGROUND_WORKERS=1` to keep API tests deterministic.

### Render pipeline changes

- Fixed the Ken Burns duration explosion by changing the image path to:
  - looped image input with `-framerate 1`
  - `zoompan`
  - `trim=duration=...`
  - `setpts=PTS-STARTPTS`
- Added a runaway-duration guard in `_run_with_progress()` so renders stop early when FFmpeg output time grows far beyond the expected timeline.
- Reduced the Ken Burns overscan scale from the previous heavy `2x` path to a lighter `1.2x` path for better wall-clock performance.
- Added partial render cleanup on failure for temporary video/audio artifacts.

### Workflow changes

- `/api/projects/{pid}/render` now queues render work instead of executing it inside the request-serving web process.
- Step 4 now understands the `queued` render state and shows worker heartbeat information in the render log panel.
- Render recovery now clears stale job metadata as well as progress fields.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-24 Subtitle Layout Consistency Update

### Architecture changes

- Reworked subtitle wrapping so the first rendered line now respects the configured line-length cap more reliably.
- Added block-height-aware subtitle placement helpers so vertical position can account for:
  - font size
  - line count
  - outline width
- Rebalanced effective line-length calculation for large fonts by lowering the old hard floor and using a more realistic character-width estimate.

### Workflow changes

- `lower` subtitle placement now targets a lower-third center ratio instead of relying on the previous fixed ASS margin.
- Dialogue events now override `MarginV` per cue based on actual wrapped line count, which keeps one-line and two-line captions visually closer to the intended anchor.
- Step 4 subtitle preview now follows the same position ratios used by backend rendering, reducing preview/render mismatch.
- ASS output now uses `WrapStyle: 0` as a safety net for extreme overflow cases.

### Verification

- Added subtitle regression tests covering:
  - first-line max-length behavior
  - large-font effective line length
  - lower-third center placement
  - top margin fine-tuning
  - screenshot-like long sentence wrapping
- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-24 TTS Seed Lock And Senior Male Presets Update

### Architecture changes

- Extended `TtsProfile` with `seed` so preview and full TTS can share the same deterministic base configuration.
- Added preview-lock signing for TTS preview responses:
  - canonical preset id
  - effective profile
  - signature
- Added a sentence-level `tts_run_manifest.json` artifact that records the effective profile and seed used for every generated sentence.
- Switched OmniVoice synthesis seeding to a wrapper-level RNG lock using `omnivoice.utils.common.fix_random_seed()` before each generation call.

### Workflow changes

- Added four new senior male presets to the shared preset catalog:
  - `male-60s-low`
  - `male-pastor-60s`
  - `male-narration-60s`
  - `male-announcer-60s`
- Step 3 preview now returns a preview lock and keeps the concrete seed visible in the UI state.
- `TTS 시작` now reuses the preview seed when a matching preview lock is present, and rejects runs when tuning changed after preview.
- Voice sample generation script now uses the same preview synthesis path so offline comparison samples reflect the real effective profile behavior.

### Verification

- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`.

## 2026-04-24 Source Assist URL Analyze MVP Update

### Architecture changes

- Extended project persistence with source-draft fields:
  - `source_draft_state`
  - `source_draft_progress`
  - `source_draft_error`
  - `source_draft_input_mode`
  - `source_draft_query`
  - `source_draft_sources`
  - `source_draft_fact_notes`
  - `source_draft_script`
  - `source_draft_warnings`
  - `source_draft_model`
  - `source_draft_risk_score`
- Added `SOURCE_CACHE_DIR`, `OLLAMA_BASE_URL`, and `SCRIPT_LLM_MODEL` config entries for the upcoming source-research pipeline.
- Added `app/services/source_fetch.py` for:
  - URL normalization
  - SSRF blocking for localhost/private/reserved IPs
  - redirect-limited HTML fetch
  - lightweight article text extraction
  - prompt-injection string redaction
  - 24-hour local source cache

### Workflow changes

- Added `POST /api/projects/{pid}/source/url/analyze` to analyze a single article URL synchronously and persist the extracted source summary plus fact notes.
- Added `GET /api/projects/{pid}/source/draft` and `DELETE /api/projects/{pid}/source/draft` for Source Assist state retrieval/reset.
- Added a Step 1 `Source Assist` panel with:
  - article URL input
  - analyze action
  - clear action
  - source summary card
  - fact note list
  - safety warning list
- This MVP stops at URL analysis; LLM draft generation and `Apply to Script` remain planned follow-up work.

### Verification

- Added tests for:
  - prompt-injection redaction
  - localhost SSRF rejection
  - URL analysis fact-note extraction
  - source-draft persistence and clear-route reset
- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover tests`.

## 2026-04-24 Source Assist Draft Generation Update

### Architecture changes

- Added `app/services/llm_ollama.py` as a lightweight local Ollama API client using the official `/api/generate` flow with:
  - `stream=false`
  - `keep_alive=-1` for warm requests
  - `keep_alive=0` for unload
- Added `app/services/source_draft.py` to build prompt text from persisted fact notes and generate a script draft.
- Added `app/services/script_safety.py` for:
  - longest-match copy risk scoring
  - long quote detection

### Workflow changes

- Added `POST /api/projects/{pid}/source/script/generate` to generate a draft script from the analyzed source fact notes.
- Added `POST /api/projects/{pid}/source/script/apply` to write the generated draft back into:
  - `script`
  - `user_script`
  - `compiled_script`
  - `regional_sentences`
  - `sentences`
- Step 1 Source Assist now includes:
  - tone selector
  - target length selector
  - draft generation action
  - apply-to-script action
  - draft preview
  - risk score / model summary

### Current limitation

- Draft generation currently runs synchronously in the request path.
- Keyword research, regenerate tuning, and worker-based background generation remain follow-up work.

### Verification

- Added tests for:
  - script safety helpers
  - source draft generation persistence
  - apply-to-script persistence
- Verified `scripts/typecheck.ps1`.
- Verified `node --check app/static/app.js`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover tests`.

## 2026-04-24 Source Assist Keyword Research Update

### Architecture changes

- Added `app/services/source_research.py` for Brave-based keyword source collection.
- Added a local usage ledger at `storage/brave_usage.json` with:
  - month
  - used count
  - remaining count
- Enforced a hard monthly limit of `2000` requests through `BRAVE_FREE_MONTHLY_LIMIT`.

### Workflow changes

- Added `POST /api/projects/{pid}/source/keyword/collect`.
- Keyword research now:
  - uses Brave Web Search only
  - increments a local monthly usage counter
  - blocks additional requests with `429` once the free limit is exhausted
  - does not fall back to Bing, SerpAPI, or Google CSE to avoid accidental paid usage
- Step 1 Source Assist now includes a keyword input and `키워드 수집` action.

### Verification

- Added tests for:
  - monthly usage reset
  - over-limit blocking
  - Brave result parsing
  - keyword collect route persistence
- Verified `scripts/typecheck.ps1`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover tests`.

## 2026-04-24 Source Assist Keyword Cache And Source Cards Update

### Architecture changes

- Added a 24-hour keyword cache under `storage/source_research_cache`.
- Repeated keyword searches now return cached Brave result URLs without consuming another monthly Brave request.

### Workflow changes

- Step 1 Source Assist summary area now renders multiple source cards instead of only the first analyzed source.
- Cached keyword hits still reuse the later article-fetch pipeline, but they skip the Brave search request itself.

### Verification

- Added a cache-hit regression test that confirms Brave is not called again for the same keyword inside the cache window.
- Verified `scripts/typecheck.ps1`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover tests`.

## 2026-04-25 Source Assist Status And Regenerate Update

### Workflow changes

- Added `GET /api/projects/_/source/brave/status` so the browser can show current Brave monthly usage without parsing warning strings.
- Step 1 Source Assist now shows:
  - Brave used/limit count
  - remaining monthly quota
  - a separate `Regenerate` button for draft retries from the same analyzed sources

### Verification

- Added a route test for Brave status responses.
- Verified `scripts/typecheck.ps1`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover tests`.

## 2026-04-26 Source Assist Regenerate Mode Update

### Architecture changes

- Extended source draft persistence with:
  - `source_draft_previous_script`
  - `source_draft_regenerate_mode`
  - `source_draft_regenerate_note`
  - `source_draft_job_id`
  - `source_draft_started_at`
  - `source_draft_heartbeat_at`
  - `source_draft_phase`
  - `source_draft_last_log`
  - `source_draft_options`
- Extended `app/services/source_draft.py` to support regenerate structure modes:
  - `hook`
  - `point`
  - `story`
  - `lesson`
- Added mode-specific temperature and copy-risk threshold helpers.

### Workflow changes

- `POST /api/projects/{pid}/source/script/generate` now accepts:
  - `mode`
  - `note`
- Added `POST /api/projects/{pid}/source/script/restore-previous` to swap the current and previous draft scripts.
- Step 1 Source Assist now includes:
  - regenerate mode buttons
  - additional guidance input
  - restore-previous button
  - mode badge in draft preview
- Added a `409` concurrency guard when source draft generation is already running.

### Worker-ready groundwork

- Extended `/api/projects/{pid}/status` with source draft phase/log/timestamp fields.
- Updated startup interrupted-task recovery so queued/running source draft jobs are reset to recoverable error state after restart.

### Verification

- Added tests for:
  - regenerate prompt mode branching
  - stricter lesson-mode risk threshold
  - running-state concurrency guard
  - previous draft restore
- Verified `scripts/typecheck.ps1`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover tests`.

## 2026-04-26 Source Draft Worker Separation Update

### Architecture changes

- Added DB helpers:
  - `claim_next_queued_source_draft()`
  - `touch_source_draft_heartbeat()`
  - `recover_stale_source_draft_jobs(...)`
- Added `app/workers/source_draft_worker.py` using the same single-instance lock / polling pattern as render worker.
- Updated startup to launch the source draft worker and sweep stale source draft jobs in the watchdog loop.

### Workflow changes

- `POST /api/projects/{pid}/source/script/generate` now queues work instead of blocking the request until Ollama finishes.
- Source draft generation now transitions through:
  - `queued`
  - `running`
  - `done`
  - `error`
- Step 1 Source Assist polling now refreshes source draft status from `/api/projects/{pid}/status`.
- The browser now shows queued/running state rather than pretending generation completed immediately.

### Verification

- Added tests for:
  - queued source draft claim
  - source draft interrupted recovery
  - queued generate route response
  - source draft status field exposure
- Verified `scripts/typecheck.ps1`.
- Verified `omnivoice_env\\Scripts\\python.exe -m unittest discover tests`.

## 2026-04-26 Automation Finish Execution Plan

### Decision

- Added `automation-finish-execution-plan.md` as the clean finish-line plan because older sections in `automation-advancement-master-plan.md` contain encoding-damaged Korean text.
- The finish plan treats the current automation as mostly functional and focuses the remaining work on result quality and operations.

### Remaining rounds

- Round 1: make `render_plan` metadata affect real render output.
  - Segment duration.
  - Motion.
  - Fade/effect.
  - Caption style.
- Round 2: automatically rebuild `scene_plan` and `render_plan` after image generation/import finishes.
- Round 3: add render report and preflight quality gates.
- Round 4: add recent regression metrics and browser smoke verification.

### Guardrails

- Keep actual render start manual by default.
- Keep Brave Search within the free monthly quota and do not enable paid fallback by default.
- Preserve `media_order` fallback when `render_plan` is missing or invalid.
- Keep GPU stewardship centralized around the existing GPU guard policy.

## 2026-04-26 Render Plan Runtime Reflection Update

### Architecture changes

- `app/services/render.py`
  - Added per-segment `VisualSegment` resolution from `render_plan`.
  - Real render now uses segment duration instead of uniform media split when `render_plan` is present.
  - Image motion now respects segment `motion`:
    - `slow_zoom_in`
    - `slow_zoom_out`
    - `none`
  - Segment `effect="fade"` now adds FFmpeg fade-in/out at the visual segment layer.
- `app/services/render_plan.py`
  - Render plan segments now persist `sentence_idx` so subtitle styling can map back to cue indices.
- `app/services/subtitle.py`
  - Added ASS style variants:
    - `Default`
    - `Quote`
    - `Emphasis`
  - `caption_style` now affects actual subtitle rendering rather than only preview metadata.

### Behavioral result

- `render_plan` is no longer just a preview artifact.
- The final video can now visibly change when segment metadata changes.
- `media_order` fallback is still preserved when `render_plan` is unavailable or unusable.

### Verification

- Verified `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`.
- Verified `python -m pytest tests\test_render_plan.py tests\test_render_visual_track.py tests\test_subtitle_rendering.py -q`.

## 2026-04-26 Image -> Scene/Render Plan Auto Refresh Update

### Architecture changes

- `app/workers/image_worker.py`
  - After ComfyUI import completes, the worker now auto-refreshes:
    - `scene_plan`
    - `render_plan`
  - Auto refresh runs after image success and does not automatically start render.
  - Added opt-out support through `auto_build_plans_after_image`.
- `app/routers/image_gen.py`
  - Added `auto_build_plans_after_image` to single and batch enqueue payloads.
  - Batch jobs now persist the flag in `body_image_options`.

### Behavioral result

- Generated images immediately update the downstream scene/render planning layer.
- Operators do not need to manually click both plan build actions after every successful image run.
- Manual render control is still preserved.

### Verification

- Verified `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`.
- Verified `python -m pytest tests\test_image_worker.py tests\test_render_plan.py tests\test_render_visual_track.py tests\test_subtitle_rendering.py -q`.

## 2026-04-26 Render Report / Preflight Update

### Architecture changes

- Added `app/services/render_report.py`.
  - Saves `render_report.json` per project.
  - Supports report load for UI/API use.
- Updated `app/services/render.py`.
  - FFmpeg stages now return stderr tail summaries.
  - Render success and render failure both write a render report.
- Updated `app/services/preflight.py`.
  - Added subtitle cue presence check.
  - Added scene/render plan sync check.
  - Added render-plan media availability check.
- Updated `app/routers/render.py`.
  - Added `GET /api/projects/{pid}/render-report`.

### UI changes

- Step 4 now has a `Render Report` action.
- The browser can show:
  - render status
  - output file presence/size/duration
  - segment motion/effect/caption_style summary
  - fallback usage
  - FFmpeg tail / error summary

### Verification

- Verified `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`.
- Verified `python -m pytest tests\test_render_report.py tests\test_feature_workflow.py tests\test_render_visual_track.py -q`.
- Verified `node --check app\static\app.js`.

## 2026-04-26 Operator Recent Render Metrics Update

### Architecture changes

- `app/services/render_report.py`
  - Added recent render report summarization.
- `app/services/system_health.py`
  - Operator payload now includes recent render metrics:
    - total
    - success
    - error
    - fallback
    - missing_media

### UI changes

- Operator panel now shows a recent render summary block.

### Verification

- Verified `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`.
- Verified `python -m pytest tests\test_render_report.py tests\test_system_operator.py tests\test_feature_workflow.py tests\test_render_visual_track.py -q`.

## 2026-04-26 Browser Smoke Update

### Architecture changes

- `app/static/app.js`
  - Added URL deep-link support:
    - `?project=<id>`
    - `?project=<id>&step=<n>`
  - Project open and active step now sync back into the browser URL.
- Added `scripts/check_browser_smoke.py`.
  - Starts a temporary local server with background workers disabled.
  - Creates a temporary project through the real API.
  - Opens Step 2 and Step 4 using headless Chrome.
  - Saves DOM dumps and screenshots under `storage/browser_smoke`.
  - Fails if expected workflow text is missing.

### Behavioral result

- We now have a repeatable browser-level smoke check for the most important workflow surfaces.
- The same deep links are useful for manual debugging, review, and sharing a specific step state.

### Verification

- Verified `python scripts\check_browser_smoke.py`.
  - Result: `Browser smoke passed.`
- Verified `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`.

## 2026-04-26 Final Verification Script Update

### Architecture changes

- Added `scripts/final_verification.ps1`.
  - Runs:
    - backend/frontend typecheck
    - targeted pytest suite
    - browser smoke script

### Behavioral result

- We now have a single command that re-checks the core finish-line gates after changes.
- This lowers the cost of future regression checks and makes the current “done” state reproducible.

### Verification

- Verified `powershell -ExecutionPolicy Bypass -File .\scripts\final_verification.ps1`.
  - Typecheck: passed
  - Targeted pytest: `69 passed`
  - Browser smoke: passed

## 2026-04-26 Autopilot End-to-End Render Plan

### Decision

- Added `autopilot-end-to-end-render-plan.md` for a future one-button flow from user input to final render.
- The plan treats autopilot as an orchestration/state-machine layer over existing workers instead of a replacement pipeline.

### Planned input modes

- Script:
  - save/compile script directly, then TTS -> image -> plan -> preflight -> render -> report.
- URL:
  - analyze source, generate copyright-safe draft, apply, then continue the render chain.
- Keyword:
  - Brave-only source collection within the free monthly quota, generate draft, apply, then continue the render chain.

### Guardrails

- Keep upload/publish disabled by default.
- Keep paid API fallback disabled by default.
- Pause instead of continuing when copy risk, Brave limit, preflight, GPU/tool, or render-plan media issues appear.
- Reuse source draft, TTS, image, and render workers rather than duplicating long-running logic.

### Debugging/logging addition

- Updated the autopilot plan to require phase-level debug artifacts:
  - `autopilot/events.jsonl`
  - `autopilot/debug_snapshot.json`
  - `autopilot/last_failure.json`
- Each phase must log:
  - phase entry/completion
  - worker state
  - relevant quota/GPU state
  - recoverable pause hints
  - short error code
- The plan explicitly avoids storing full source article text or full generated scripts in logs unless verbose debug is manually enabled.

### Stability review additions

- Added a phase re-entry / skip-condition matrix for resume and recovery safety.
- Clarified that `plan_refresh` must call the same scene/render plan build services used by the manual endpoints.
- Added GPU wait timeout policy:
  - expose `gpu_guard.current_owner()`
  - pause after 5 minutes
  - record `SYSTEM_GPU_WAIT_TIMEOUT`
- Added cancel policy:
  - no new phases after cancel
  - already submitted worker jobs may finish naturally
  - ComfyUI job cancellation deferred to v2
- Added manual-change policy:
  - pause remains active
  - resume revalidates fingerprints
  - conflicting manual changes pause with `SYSTEM_MANUAL_CHANGE_DETECTED`
- Added centralized `ACTION_HINTS` and `RETRY_STRATEGIES` plan.
- Added `user_script` overwrite protection:
  - pause before applying if user text would be overwritten
  - write `pre_apply_backup.txt` when auto-apply proceeds
- Added report/operator integration requirement with `autopilot_job_id`.

### Phase 1 implementation update

- Implemented the first live autopilot skeleton in code:
  - DB fields and typed status exposure
  - `app/services/autopilot.py` event/debug snapshot file writer
  - `app/routers/autopilot.py` orchestration control routes
  - Step 1 UI card for start/pause/resume/cancel, recent events, and debug snapshot
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_autopilot_routes.py tests\test_feature_workflow.py tests\test_image_prompting.py -q`
  - `node --check app\static\app.js`
- Remaining work stays aligned with the plan:
  - worker dispatcher
  - phase execution
  - end-to-end TTS/image/render chaining

### Script-mode worker update

- Added the first executable autopilot worker path for `script` mode.
- New pieces:
  - `db.claim_next_queued_autopilot()`
  - `db.touch_autopilot_heartbeat()`
  - `db.recover_stale_autopilot_jobs()`
  - `app/workers/autopilot_worker.py`
- Current execution path:
  - save/compile script
  - run TTS directly inside the autopilot worker
  - queue ComfyUI image batch and wait for `image_worker`
  - rebuild scene/render plans
  - run preflight
  - queue render and wait for `render_worker`
- This means autopilot is no longer only a UI/API shell; `script` mode now has a real worker-driven orchestration path.

### URL/keyword worker update

- Extended the same autopilot worker to cover `url` and `keyword` modes.
- Added source-collection orchestration:
  - URL -> `analyze_source_url`
  - keyword -> Brave collection + source extraction
  - queue source draft worker
  - wait for `source_draft_state=done`
- Added safety behavior:
  - pause on high copy-risk score
  - pause and write `pre_apply_backup.txt` before overwriting non-empty `user_script`
  - pause with `BRAVE_RATE_LIMIT` on keyword quota exhaustion
- Verified with dedicated worker regression tests plus shared route/status coverage.

### Operator/report integration update

- Extended `render_report.json` so each render now keeps the related autopilot metadata:
  - `autopilot_job_id`
  - `autopilot_input_mode`
  - `autopilot_state`
  - `autopilot_phase`
- Extended `/api/system/operator` with autopilot-aware operational summaries:
  - queue counts for `autopilot_queued`, `autopilot_running`, `autopilot_paused`
  - recent autopilot aggregate metrics
  - recent autopilot run summaries with phase/progress/error-code visibility
- Updated the Step 4 Operator panel and Render Report panel so operators can see whether a render came from autopilot and what the last autopilot state was without digging into project files.
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_render_report.py tests\test_system_operator.py tests\test_autopilot_worker.py -q`
  - `node --check app\static\app.js`

### Live pipeline diagnosis update

- Ran a real 1-minute render-path validation with synthetic TTS assets.
  - Result: render completed successfully.
  - Final sample output: `storage/projects/17f7cb051329/output.mp4`
  - Report summary:
    - `audio_duration_sec`: `60.3`
    - `output_duration_sec`: `60.3`
    - `subtitle_cue_count`: `18`
    - `render_plan_segment_count`: `18`
    - `fallback_used`: `False`
- Ran a real TTS-path validation.
  - Failure 1: the default Python interpreter did not have `omnivoice` installed.
  - Failure 2: `omnivoice_env\Scripts\python.exe` could import `omnivoice`, but model load failed with Windows `os error 1455` during `OmniVoice.from_pretrained(...)`.
  - Structural finding: `app/main.py` starts workers with `sys.executable`, so launching the app from the wrong Python also launches TTS/background workers from the wrong Python.
- Ran a real ComfyUI generation-path validation.
  - Server health was reachable at `http://127.0.0.1:8188/system_stats`.
  - Workflow submission succeeded and returned `prompt_id`.
  - Actual generation failed inside ComfyUI `KSampler` with:
    - `OSError: [Errno 22] Invalid argument`
    - traceback path points to `tqdm -> sys.stderr.flush() -> ComfyUI app/logger.py flush`
  - This means the current image failure is not a simple worker timeout; it is a concrete ComfyUI execution error in the running server process.

### Diagnostic hardening update

- Updated `app/services/comfyui_client.py`
  - Added `extract_execution_error(...)` to parse ComfyUI history status and surface node-level execution failures.
- Updated `app/workers/image_worker.py`
  - Poll loop now fails fast on ComfyUI execution errors instead of waiting until the generic history timeout expires.
- Added regression coverage:
  - `tests/test_comfyui_client.py`
  - `tests/test_image_worker.py`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_comfyui_client.py tests\test_image_worker.py -q`

## 2026-04-27 OmniVoice Phase 2a stabilization update

- Added lightweight memory cleanup inside the full TTS sentence loop:
  - every 5 generated sentences, run Python GC and clear CUDA cache
  - synchronize CUDA when available so cleanup completes before the next sentence batch continues
- Kept cleanup as `_cleanup_generation_memory()` so the cadence is covered by a deterministic unit test without loading OmniVoice.
- Hardened `tts_worker` so OmniVoice Python resolver failures are written into project `tts_state=error` / `tts_error` instead of escaping the worker job path.
- Real measurement:
  - project `7ee7587d99ca`
  - 18 sentences
  - about `84.58` seconds of generated WAV segments
  - result `tts_state=done`, `tts_progress=100`
  - no Windows `os error 1455` during this run
- Follow-up risk:
  - 180-second and longer scripts still need measurement before dropping Phase 2b/2c entirely.
  - A PowerShell inline Korean script attempt hit the TTS-readable sentence filter before model inference, so Korean should be rechecked through the browser/API input path.

## 2026-04-27 Korean E2E groundwork update

- Added `seed_mode` to the TTS profile model so we can explicitly choose between:
  - `per_sentence`: legacy behavior, `seed + index`
  - `fixed`: same seed across the whole narration for more stable voice identity
- Wired `seed_mode` through:
  - `app/types.py`
  - `app/tts_profiles.py`
  - `app/routers/render.py`
  - `app/services/tts.py`
  - `app/static/app.js`
- Added regression coverage for:
  - default `per_sentence` normalization
  - fixed seed persistence through `/api/projects/{pid}/tts`
  - fixed seed manifest output in full TTS runs
- Added `scripts/check_comfyui_smoke.py`:
  - checks `system_stats`
  - renders the existing `txt2img_sdxl_basic` workflow template
  - submits a real prompt
  - polls history until either image output, execution error, or timeout
- Real ComfyUI smoke findings:
  - existing `8188` instance failed with `ComfyUI KSampler failed: [Errno 22] Invalid argument`
  - a fresh `8190` instance started without `--novram --cpu-vae` reproduced the same error
  - `sd_xl_base_1.0.safetensors` and `DreamShaper_8_pruned.safetensors` both failed the same way
- Current conclusion:
  - the acceptance-quality Korean video is blocked by the current ComfyUI runtime state, not by our image worker queue or render integration.

## 2026-04-27 Korean E2E completion update

- Root cause update for ComfyUI:
  - the `KSampler failed: [Errno 22] Invalid argument` failure was tied to the active process stderr/logger state
  - the existing `8188` instance and a fresh `8190` instance both reproduced the failure
  - a detached `8193` instance launched with stdout/stderr redirected to real log files completed the same smoke workflow successfully
  - after that, `8188` was relaunched with the same file-backed stderr approach and also passed smoke
- Added `scripts/run_comfyui_detached.ps1` so we can restart ComfyUI with file-backed stdout/stderr instead of relying on a fragile console-attached launch path.
- Produced a full Korean acceptance sample end-to-end:
  - project `9ee64e214b2c`
  - script source `storage/fixtures/korean_e2e_script.txt`
  - TTS profile used `seed_mode="fixed"` with seed `424242`
  - ComfyUI generated 8 scene images
  - render completed to `storage/projects/9ee64e214b2c/output.mp4`
- Verification:
  - video duration `61.166667` seconds
  - video stream `1920x1080`, `h264`, `30fps`
  - audio stream `aac`
  - QA frame written to `storage/projects/9ee64e214b2c/qa/frame_10s.jpg`
  - `tts_run_manifest.json` recorded `seed_mode="fixed"` and the same seed for all 8 sentences
## 2026-04-27 Audio polish update

- Implemented the first P0 audio polish pass from the Korean ComfyUI E2E plan.
- `app/services/tts.py`
  - added tail silence trimming before sentence WAV output
  - preserved natural `duration=None` behavior
  - applied a deliberate `0.3s` inter-sentence gap directly in `timings.json`
- `app/services/render.py`
  - `concat_audio` now inserts explicit silence WAV files between sentence clips
  - `normalize_audio` now forces `24000Hz mono pcm_s16le`
  - render now validates raw vs normalized audio duration drift and fails over `1.0s`
- `app/services/render_report.py` and `app/types.py`
  - render reports now store `audio_raw_duration_sec` and `audio_normalized_duration_sec`
- Regression coverage added in:
  - `tests/test_tts_pipeline.py`
  - `tests/test_render_visual_track.py`
  - `tests/test_render_report.py`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_tts_pipeline.py tests\test_render_visual_track.py tests\test_render_report.py -q`

## 2026-04-27 Stickman image prompting update

- Reworked `app/services/image_prompting.py` away from sentence-dump prompts.
- The new prompt strategy is:
  - English SDXL-friendly prompt text
  - stickman main character as the default visual anchor
  - high-contrast, simple, instantly readable scenes
  - sentence/context mapped to intuitive visual tokens such as giant, sling, prayer, road, rain, money, clock, and decision poses
- This is meant to improve:
  - prompt adherence on lightweight ComfyUI flows
  - readability for short-form narration scenes
  - visual consistency when the user prefers simple but obvious story beats
- Added `app/services/stickman_reference_library.py`
  - keeps external source metadata for stickman prompting references
  - keeps reusable scene templates such as `giant_battle`, `prayer`, `time_pressure`, and `money_choice`
- Added a LoRA-capable ComfyUI workflow:
  - `app/workflow_templates/comfyui/txt2img_sdxl_stickman_lora.json`
  - uses `LoraLoader` so a stickman LoRA can be applied when available
- Extended image-gen routes:
  - `lora_name`
  - `lora_strength`
  - auto-switch from `txt2img_sdxl_basic` to `txt2img_sdxl_stickman_lora` when LoRA is requested
- Prompt payloads now include:
  - `template_key`
  - `reference_names`
- Regression coverage updated in:
  - `tests/test_image_prompting.py`
  - `tests/test_comfyui_routes.py`
  - existing `tests/test_image_worker.py`
- Added prompt manifest persistence:
  - manual batch queue and autopilot queue now save `storage/projects/{pid}/image_prompts_manifest.json`
  - queued `body_image_options` now keeps `image_prompts_manifest_path` for traceability
- Manual visual validation notes:
  - PowerShell inline Korean input is still unreliable for image-prompt diagnostics because shell-side encoding can collapse Korean keyword matching into fallback prompts
  - UTF-8 file input produced the expected mapped prompts such as giant/sling and prayer
  - prompt style was tightened further toward `minimalist 2d stickman poster`, `single hero`, `one oversized prop`, and stronger negatives against crowd/speech-bubble/scenic drift
- Additional regression coverage:
  - `tests/test_autopilot_worker.py`
- Verified with:
  - `python -m pytest tests\test_image_prompting.py tests\test_comfyui_routes.py tests\test_image_worker.py tests\test_autopilot_worker.py -q`
- 2026-04-27 follow-up:
  - stickman template coverage expanded to `temptation`, `recovery`, `storm_fear`, and `study_focus`
  - Step 2 image panel now sends `LoRA Name` and `LoRA Strength` directly to ComfyUI jobs
  - operator model status now includes a dedicated `Stickfigures LoRA` entry so installation readiness is visible without opening the filesystem
  - `Stickfigures-000005.safetensors` was installed under the ComfyUI LoRA directory and a real `txt2img_sdxl_stickman_lora` verification run produced `lora_verify_stickman_00001_.png`
  - `scripts/check_comfyui_smoke.py` was extended so LoRA workflows can be smoke-tested with actual `lora_name` / `lora_strength`
  - `scripts/run_stickman_lora_batch.py` generated an 8-scene sample project `b609e71caad0`; early review suggests silhouette consistency is much better, but `money_choice`, `prayer`, and `storm_fear` still need prompt tuning for stronger semantic accuracy
  - `scripts/run_stickman_lora_batch.py` now supports focused multi-seed sweeps; project `6eca26cb33be` was generated with 3 variants each for `prayer`, `money_choice`, and `storm_fear`

## 2026-04-27 Visual relevance emergency guard

- Implemented Phase 0 from `visual-relevance-recovery-plan.md`.
- Added `app/services/visual_relevance.py` with:
  - stable sentence hashing
  - generated-image mapping validation
  - readable render/preflight issue formatting
- Extended `BodyImageMapping` metadata with `sentence_text`, `sentence_hash`, `project_id`, and `prompt_id`.
- `app/services/comfyui_pipeline.py` now records the current sentence text/hash when importing a ComfyUI output.
- `app/services/scene_plan.py` ignores generated mappings whose stored hash no longer matches the current sentence.
- `app/services/preflight.py` adds a `visual_relevance` check for `comfyui_auto` projects.
- `app/services/render.py` now blocks render before FFmpeg if generated image mappings are missing, stale, or mismatched.
- Regression coverage:
  - `tests/test_visual_relevance.py`
  - updated `tests/test_scene_plan.py`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_visual_relevance.py tests\test_scene_plan.py tests\test_comfyui_routes.py tests\test_image_worker.py tests\test_render_plan.py -q`

## 2026-04-27 Visual relevance keyword cleanup

- Implemented Phase 1 from `visual-relevance-recovery-plan.md`.
- Rebuilt `app/services/image_prompting.py` with clean UTF-8 Korean keyword mappings.
- Added concrete daily-script mappings for:
  - 연락/message/phone
  - 관계/reconnection
  - 계획/checklist
  - 마음/noise/anxiety/calm
  - 노트/book/desk/study
  - 다시 시작/recovery
- Prompt suggestions now include:
  - both Stickfigures trigger hints: `Flipchartvisu`, `Stick figure`
  - `sentence_hash`
- Rebuilt `scripts/run_stickman_lora_batch.py` with clean Korean sample sentences and `sentence_hash` in summary items.
- Rebuilt `tests/test_image_prompting.py` with clean Korean fixtures and daily-script keyword cases.
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_image_prompting.py tests\test_visual_relevance.py tests\test_scene_plan.py tests\test_comfyui_routes.py tests\test_image_worker.py tests\test_render_plan.py -q`

## 2026-04-27 Visual brief generator

- Implemented Phase 2 from `visual-relevance-recovery-plan.md`.
- Added `app/services/visual_brief.py`.
- Added `VisualBriefMode` and `VisualBrief` typed structures in `app/types.py`.
- `build_visual_brief()` now creates structured records with:
  - `mode`
  - `main_subject`
  - `action`
  - `primary_prop`
  - `secondary_prop`
  - `scene`
  - `emotion`
  - `must_show`
  - `avoid`
  - `rationale`
- `app/services/image_prompting.py` now attaches `visual_brief` to every prompt suggestion and saved prompt manifest.
- `must_show` is always populated so Phase 3 prompt compiler and Phase 5 preflight checks have a concrete object/action target.
- Regression coverage:
  - `tests/test_visual_brief.py`
  - updated `tests/test_image_prompting.py`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_visual_brief.py tests\test_image_prompting.py tests\test_visual_relevance.py tests\test_comfyui_routes.py tests\test_image_worker.py -q`

## 2026-04-27 Prompt compiler v2

- Implemented Phase 3 from `visual-relevance-recovery-plan.md`.
- Added `app/services/prompt_compiler.py`.
- `compile_positive_prompt()` now builds prompts from `VisualBrief` fields:
  - `Flipchartvisu`
  - `Stick figure`
  - `stickman main character`
  - shot
  - primary prop
  - action
  - scene
  - emotion
- `compile_negative_prompt()` now adds stable guard rails such as:
  - `tiny subject`
  - `missing main prop`
  - `crowd`
  - `multiple characters`
- `check_prompt_compliance()` verifies whether all `must_show` items are present in the compiled prompt.
- `app/services/image_prompting.py` now uses the prompt compiler and returns `missing_must_show`.
- Regression coverage:
  - `tests/test_prompt_compiler.py`
  - updated `tests/test_image_prompting.py`
  - compatible route behavior confirmed through `tests/test_comfyui_routes.py`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_prompt_compiler.py tests\test_visual_brief.py tests\test_image_prompting.py tests\test_visual_relevance.py tests\test_comfyui_routes.py tests\test_image_worker.py -q`

## 2026-04-27 Visual relevance Phase 5 preflight gate

- Implemented Phase 5 from `visual-relevance-recovery-plan.md`.
- `app/services/visual_relevance.py` now validates prompt-manifest linkage in addition to sentence-hash linkage.
- Added manifest-backed failure detection for:
  - `IMAGE_PROMPT_MANIFEST_MISSING`
  - `IMAGE_VISUAL_BRIEF_MISSING`
  - `IMAGE_PROMPT_MUST_SHOW_MISSING`
- `app/routers/image_gen.py` batch enqueue now persists per-item `sentence_hash`.
- `app/workers/image_worker.py` now carries queued `sentence_hash` into imported mappings as `manifest_sentence_hash`.
- `app/services/comfyui_pipeline.py` import now stores `manifest_sentence_hash` on generated mappings.
- This closes the stale-queue gap where an image job could be enqueued under one script version and imported after the script changed.
- Regression coverage:
  - rebuilt `tests/test_visual_relevance.py`
  - updated route/worker compatibility through `tests/test_comfyui_routes.py` and `tests/test_image_worker.py`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_visual_relevance.py tests\test_comfyui_routes.py tests\test_image_worker.py tests\test_prompt_compiler.py tests\test_image_prompting.py -q`

## 2026-04-27 Visual relevance Phase 6a status UI

- Implemented Phase 6a from `visual-relevance-recovery-plan.md`.
- `app/services/visual_relevance.py` now builds per-sentence `visual_relevance_rows` and `visual_relevance_summary`.
- `app/routers/projects.py` and `app/routers/render.py` now expose those fields in project/status responses.
- Step 2 image panel now includes an `Image Relevance` card with sentence-level `PASS / STALE / MISSING` visibility.
- Each row shows:
  - sentence index
  - current sentence text
  - selected media path
  - first relevance reason
  - issue code list
- Frontend files updated:
  - `app/static/index.html`
  - `app/static/app.js`
  - `app/static/style.css`
- Regression coverage:
  - rebuilt `tests/test_visual_relevance.py`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_visual_relevance.py tests\test_comfyui_routes.py tests\test_image_worker.py tests\test_image_prompting.py -q`

## 2026-04-27 Visual relevance Phase 4 candidate foundation

- Implemented the Phase 4 foundation from `visual-relevance-recovery-plan.md`.
- Batch image jobs now support `variants_per_scene` in `POST /api/projects/{pid}/comfyui/job/batch-auto`.
- Worker/import flow now preserves candidate metadata:
  - `candidate_index`
  - `candidate_total`
  - `candidate_score`
  - `selected_reason`
- Candidate groups are stored under `body_image_options["candidate_groups"]`.
- Selected mappings are now updated per sentence instead of blindly appending duplicate selected mappings.
- Automatic selection currently uses the best candidate score available from imported artifact metadata.
- Added manual selection API:
  - `POST /api/projects/{pid}/comfyui/candidates/select`
- Step 2 Generated Mapping UI now shows:
  - selected reason
  - candidate position/count
- Frontend files updated:
  - `app/static/index.html`
  - `app/static/app.js`
- Regression coverage:
  - updated `tests/test_comfyui_routes.py`
- Verified with:
- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
- `python -m pytest tests\test_comfyui_routes.py tests\test_image_worker.py tests\test_visual_relevance.py tests\test_image_prompting.py -q`

## 2026-04-28 Autopilot quality stabilization

- Autopilot should not rely on the global/manual TTS default path when the project still has `voice_preset=auto` or `mode=auto`.
- The safer policy is to keep manual TTS behavior unchanged and coerce only the autopilot path to a stable design preset with non-empty `instruct`.
- Added source-draft cleanup immediately after generation so the same clean script flows into preview, subtitle, TTS, and scene planning.
- Extended `ScenePlanScene` instead of introducing a parallel visual plan artifact, which keeps the existing plan/render/preflight pipeline as the single source of truth.
- Verified with:
  - `python -m pytest tests\test_source_draft.py tests\test_scene_plan.py tests\test_autopilot_worker.py -q`
  - `python -m pytest tests\test_tts_presets.py -q`

## 2026-04-28 Tech visual vocabulary and prompt guard

- Reused the existing `visual_brief -> prompt_compiler -> visual_relevance` path instead of introducing a parallel planner artifact.
- Added `storage/visual_vocab/tech.json` so browser/headless/V8/CDP/fingerprint/automation/data extraction/security terms can resolve to concrete props.
- Tech-domain fallback now prefers browser-window / terminal-panel / data-table style props instead of generic symbolic placeholders.
- Added a prompt blocklist so phrases like `running fast` or `under heavy rain` are treated as prompt-quality failures for technical explainer scenes.
- Verified with:
  - `python -m pytest tests\test_visual_brief.py tests\test_prompt_compiler.py tests\test_image_prompting.py tests\test_visual_relevance.py -q`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
- 2026-04-28 render/subtitle architecture update:
  - `app/services/render.py` now supports `still_locked` image segments that bypass global `kenburns_enabled`, builds CFR still-image tracks with `trim=end_frame=...`, and allocates segment frames against a total target frame budget so the final segment absorbs rounding drift.
  - Render completion now validates final `output.mp4` duration against audio/timeline expectations and removes failed partial outputs when drift exceeds tolerance.
  - `app/services/subtitle.py` keeps `timings.json` as the TTS source timeline but derives display-only readable subtitle cues at render time. When `word_timings` exist it uses word-first splitting so karaoke mapping stays intact; otherwise it falls back to proportional text splitting.
  - `app/services/autopilot.py` upgrades autopilot-created projects from legacy `sentence` cue mode to `readable` cue mode by default so generated videos stop dumping long full-sentence captions onto the screen.
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `omnivoice_env\Scripts\python.exe -m unittest tests.test_render_plan tests.test_render_visual_track tests.test_subtitle_rendering tests.test_render_report`
  - `omnivoice_env\Scripts\python.exe -m unittest tests.test_autopilot_worker tests.test_media_workflow tests.test_feature_workflow`

## 2026-04-28 Tech documentary prompt and subtitle fallback follow-up

- The first `readable` subtitle rollout exposed a project-specific weakness: `timings.json` stayed correct but `timings_words.json` could contain mojibake text, which made word-first subtitle splitting produce unreadable ASS text. The safer policy is to use word-first only when the joined word timeline text matches the source cue text closely enough; otherwise subtitle rendering should fall back to clean text-based splitting.
- `app/services/subtitle.py` now normalizes source cue text vs. joined word timeline text and requires an 80% cue-match threshold before using word-first splitting. This preserves karaoke mapping when word timing text is healthy and avoids corrupt display text when it is not.
- Technical-news image prompting also needed a second pass. The previous tech path still produced weak, nearly identical prompts because broad AI terms were detected but did not outrank more specific scene signals.
- `storage/visual_vocab/tech.json` now includes concrete props for:
  - AI/model training
  - GPU clusters
  - Google/research labs
  - government strategy rooms
  - collaboration networks
  - orchestration consoles
  - infrastructure control rooms
  - chip/cloud hardware boards
- `app/services/image_prompting.py` now:
  - expands tech-domain detection with project title + compiled script + source excerpt context
  - prioritizes more specific matched tech keywords over broad `ai`/`인공지능` matches
  - uses a `tech_documentary` template instead of the stickman template for tech scenes
- `app/services/prompt_compiler.py` now emits tech-specific positive/negative prompts:
  - no `Flipchartvisu` / `Stick figure`
  - uses cinematic documentary/interface phrasing
  - blocks low-signal outputs like duplicate screens or deformed hardware
- `app/services/render.py` now records `subtitle_cue_count` using actual display cue expansion rather than raw TTS sentence count, which keeps `render_report.json` aligned with the generated `subtitles.ass`.
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `omnivoice_env\Scripts\python.exe -m pytest tests/test_visual_brief.py tests/test_prompt_compiler.py tests/test_image_prompting.py tests/test_subtitle_rendering.py -q`
  - `omnivoice_env\Scripts\python.exe -m pytest tests/test_subtitle_rendering.py tests/test_render_report.py tests/test_render_visual_track.py tests/test_image_prompting.py tests/test_prompt_compiler.py tests/test_visual_brief.py -q`
- Project validation:
  - rebuilt `storage/projects/a75ea6a907de/tts/timings_words.json`
  - regenerated all 16 scene images with `DreamShaper_8_pruned.safetensors` and no LoRA
  - rerendered `storage/projects/a75ea6a907de/output.mp4`
  - final report: `output_duration_sec=118.096`, `duration_guard_passed=true`, `subtitle_cue_count=63`

## 2026-04-28 Still-frame motion policy correction

- A direct inspection of `storage/projects/a75ea6a907de/render_report.json` showed that the supposedly stable video was still rendered with `slow_zoom_in` across every segment.
- Root cause: `app/services/render_plan.py` only assigned `still_locked` when the same image was reused across multiple scenes (or there was only one unique image in the whole project). A project with one generated still image per sentence therefore defaulted back to motion, even though the render pipeline already supported CFR still-frame duplication.
- Policy change:
  - any scene-plan segment with an image `media_path` now defaults to `still_locked`
  - this makes the render-plan layer align with the FPS-stabilized still-image renderer already implemented in `app/services/render.py`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `omnivoice_env\Scripts\python.exe -m pytest tests/test_render_plan.py tests/test_render_visual_track.py tests/test_render_report.py tests/test_subtitle_rendering.py -q`
- Project validation:
  - rebuilt render plan for `a75ea6a907de`
  - rerendered `storage/projects/a75ea6a907de/output.mp4`
  - confirmed leading segment motions in report are `still_locked`
  - confirmed `output_duration_sec=118.096` and `duration_guard_passed=true`
## 2026-04-28 Sentence-context visual planner update

- Implemented the first pass of the sentence-context image generation plan.
- Added `app/services/visual_planner.py` so the pipeline can ask Gemma (`SCRIPT_LLM_MODEL`, currently `gemma4:e4b`) for per-sentence visual planning JSON instead of deriving every image directly from surface keyword rules.
- The planner now produces and caches `scene_visual_plan.json` with:
  - `core_meaning`
  - `primary_keywords`
  - `secondary_keywords`
  - `visual_metaphor`
  - `subject_modes`
  - `must_show`
  - `may_show`
  - `avoid`
  - `prompt_hint`
  - `vocab_refs`
- Added `storage/visual_vocab/essay.json` as context-injection guidance for essay-style abstract lines. The vocabulary is advisory for the LLM planner, not a hard replacement table.
- `app/services/image_prompting.py` now:
  - consumes planner output when available
  - compiles essay scenes with an `essay_editorial` style instead of forcing everything through the stickman path
  - keeps legacy fallback behavior when LLM planning is disabled or unavailable
  - retries prompt assembly when `must_show` coverage is incomplete
  - emits `keyword_coverage`, `retry_count`, and runtime template metadata in prompt suggestions and manifests
- Added `app/services/prompt_quality.py`:
  - summarizes prompt-level keyword coverage
  - writes `prompt_quality_report.json`
  - flags repeated primary terms and repeated generic phrases
- `app/services/scene_plan.py` now stores planner-derived context directly on `ScenePlanScene` so the existing scene/render/preflight path remains the single source of truth.
- `app/services/autopilot.py` now supports `quality_mode`:
  - `fast`
  - `balanced`
  - `exhaustive`
- Candidate count is now derived from the visual plan, so abstract/environment/object-metaphor scenes can request more variants without making that the unconditional default on 8 GB VRAM systems.
- Rebuilt the planning artifacts for project `147ab80b75e9`:
  - `storage/projects/147ab80b75e9/scene_visual_plan.json`
  - `storage/projects/147ab80b75e9/image_prompts_manifest.json`
  - `storage/projects/147ab80b75e9/prompt_quality_report.json`
- Post-fix verification on that project:
  - 14 visual-plan entries
  - 14 prompt suggestions
  - 14 scene-plan scenes
  - 14 render-plan segments
  - `failed_count=0` in `prompt_quality_report.json`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `omnivoice_env\Scripts\python.exe -m pytest tests/test_visual_planner.py tests/test_scene_plan.py tests/test_image_prompting.py tests/test_autopilot_worker.py tests/test_feature_workflow.py tests/test_comfyui_routes.py -q`

## 2026-04-28 Essay image context recovery P0 and P1-V1

- Implemented the updated essay recovery order from `essay-image-context-recovery-plan.md`:
  - Phase 1 vocab cleanup
  - Phase 2 planner + literal simile extraction
  - Phase 3 compiler hardening
  - Phase 4 prompt-quality guard rails
  - Phase 6 regression coverage
  - Phase 5 V1 text-based candidate scoring
- Added `app/services/visual_vocab.py` so essay-domain vocab loading and domain-wide `global_avoid` handling are centralized instead of being copied into individual services.
- Added `app/services/literal_simile.py` with direct Korean simile pattern support for:
  - `...과/와 비슷`
  - `...처럼`
  - `...같은 / 같이`
  - `...듯`
  - `마치 ... 것 같`
- Extended `VisualBrief` and `VisualPlanEntry` with:
  - `visual_priority`
  - `literal_simile`
  - `allow_objects`
- `storage/visual_vocab/essay.json` now carries:
  - `global_avoid`
  - `path_vocab`
  - `literal_simile_examples`
  - cleaned metaphor examples that remove the earlier `busy street` / `city morning` drift
- `app/services/visual_planner.py` now:
  - injects stronger LLM guidance against default road/vehicle metaphors
  - detects literal similes during fallback
  - prefers sentence-specific concrete tokens in fallback `primary_keywords` / `must_show`
  - merges essay `global_avoid` into planner `avoid`
- `app/services/prompt_compiler.py` now:
  - prepends literal similes for `visual_priority=literal_simile`
  - injects essay `global_avoid` into negative prompts
  - automatically adds `car, vehicle, traffic` negatives when essay prompts contain road/path language and those objects are not explicitly allowed
- `app/services/prompt_quality.py` now reports:
  - `FORBIDDEN_OBJECT_IN_NEGATIVE_MISSING`
  - `ESSAY_ROAD_WITHOUT_VEHICLE_BAN`
  - `LITERAL_SIMILE_IGNORED`
  - project-level `FALLBACK_RATE_HIGH`
  - project-level `GENERIC_MUST_SHOW_REPEATED`
- `app/services/comfyui_pipeline.py` candidate scoring no longer depends primarily on imported file size. The score now prefers:
  - prompt compliance / must-show coverage
  - clean issue-code status
  - literal-simile priority
  - non-fallback visual plans
  - file size only as a small tie-breaker
- Added targeted regression coverage:
  - `tests/test_visual_vocab_essay.py`
  - `tests/test_literal_simile.py`
  - `tests/test_prompt_quality.py`
  - `tests/test_candidate_selection.py`
  - updated `tests/test_visual_planner.py`
  - updated `tests/test_prompt_compiler.py`
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `omnivoice_env\Scripts\python.exe -m pytest tests/test_visual_vocab_essay.py tests/test_literal_simile.py tests/test_visual_planner.py tests/test_prompt_compiler.py tests/test_prompt_quality.py tests/test_candidate_selection.py tests/test_image_prompting.py tests/test_comfyui_routes.py -q`

## 2026-04-28 Essay generic-plan repair follow-up

- The first essay recovery pass removed vehicle drift but still left repeated `compass on a folded map` / `large checklist with three bold check marks` prompts in project `147ab80b75e9`.
- Root cause: repaired LLM output could still collapse multiple abstract essay lines into the same generic symbolic placeholders, and the old cached `scene_visual_plan.json` would continue to be reused.
- `app/services/visual_planner.py` was rewritten with:
  - planner cache versioning (`planner_version=2`)
  - stronger Korean concrete-token extraction
  - sentence-level essay semantic heuristics for:
    - `모래 위 ... 비슷합니다`
    - `발자국 ... 의심`
    - `어디로 가고 ... 설명`
    - `가치 ... 질문`
    - `한 페이지 / 한 문장 / 한 사람`
    - `느려 ... 괜찮`
    - `이 길 ... 잊지 않`
    - `흩어지지 ... 반복`
  - `essay_semantic_repair` that rewrites generic compass/checklist entries into sentence-specific `must_show` / `primary_keywords`
- Added a regression test proving that a generic essay entry is rewritten into a concrete semantic one:
  - `tests/test_visual_planner.py::test_build_scene_visual_plan_repairs_generic_essay_entry`
- Rebuilt the project artifacts for `147ab80b75e9` after removing the stale cache:
  - `storage/projects/147ab80b75e9/scene_visual_plan.json`
  - `storage/projects/147ab80b75e9/image_prompts_manifest.json`
  - `storage/projects/147ab80b75e9/prompt_quality_report.json`
- Post-rebuild report:
  - `fallback_rate = 0.0`
  - `project_issue_codes = []`
  - `generic_must_show_repeats = []`

## 2026-04-29 ComfyUI SDXL profile plumbing P0

- Implemented the first P0 block from `comfyui-sdxl-integration-roadmap.md` after reviewing the external Antigravity roadmap review.
- Added `app/services/image_generation_profiles.py` with profile-level runtime settings:
  - `profile_name`
  - `sampler_name`
  - `scheduler`
  - `steps`
  - `cfg`
  - `denoise`
  - `request_timeout_sec`
  - `seed_policy`
  - `score_version`
- Replaced hardcoded KSampler values in:
  - `app/workflow_templates/comfyui/txt2img_sdxl_basic.json`
  - `app/workflow_templates/comfyui/txt2img_sdxl_stickman_lora.json`
- Wired runtime KSampler settings through:
  - `app/services/image_prompting.py`
  - `app/routers/image_gen.py`
  - `app/workers/image_worker.py`
  - `app/services/comfyui_workflows.py`
- `quality_mode` now changes actual ComfyUI KSampler parameters instead of remaining metadata-only.
- `ComfyUIClient` now accepts a configurable timeout, and manual submit / worker submit pass profile timeout values.
- Changed the generic `visual_brief.py` fallback away from `large checklist with three bold check marks` to a neutral realistic object/environment fallback.
- Candidate scoring in `app/services/comfyui_pipeline.py` now:
  - uses `candidate_score_v2`
  - clamps scores to `0.0..1.0`
  - stores `candidate_score_version`
  - stores score components in candidate groups
  - keeps file size as a small sanity component only
- Batch candidate seed generation now spaces variants instead of adjacent linear increments.
- Verified with:
  - `python -m unittest tests.test_comfyui_workflows tests.test_visual_brief tests.test_candidate_selection tests.test_comfyui_routes tests.test_image_prompting`

## 2026-04-29 ComfyUI SDXL prompt and QA hardening P0

- Implemented the remaining low-risk P0 items from `comfyui-sdxl-integration-roadmap.md`.
- `app/services/prompt_compiler.py` now:
  - compiles essay positive prompts with clearer SDXL slot order
  - adds camera and quality anchors such as `35mm lens`, `sharp focus`, `natural color`, `detailed real-world textures`, and `medium wide shot`
  - adds `no readable text`
  - filters raw Hangul visual target phrases from essay positive prompts and falls back to visible neutral anchors
  - expands essay negative prompts with generic-symbol, text, framing, and SDXL artifact controls
- `storage/visual_vocab/essay.json` now expands `global_avoid` with:
  - compass/map/checklist/clipboard drift
  - graph/chart/coins/seedling drift
  - readable-text and cropped/closeup risks
- `app/services/prompt_quality.py` now detects:
  - `RAW_TEXT_VISUAL_TARGET`
  - `GENERIC_SYMBOL_WITHOUT_ALLOW`
  - `BOOK_TEXT_RISK`
  - `CLOSEUP_RISK`
  - `MISSING_FRAMING_SLOT`
  - `MISSING_CAMERA_TECHNICAL_SLOT`
- Project-level prompt quality reports now count and surface these issue codes.
- Added `app/services/parse_utils.py` and replaced repeated numeric parsing helpers in:
  - `app/routers/image_gen.py`
  - `app/workers/image_worker.py`
  - `app/services/comfyui_pipeline.py`
- Domain-detection consolidation remains pending because the duplicated logic participates in planner fallback behavior and should be changed separately.
- Verified with:
  - `python -m unittest tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 ComfyUI SDXL P0 follow-up cleanup

- Added `app/services/domain_detection.py` to centralize project-aware tech-domain detection.
- Switched both:
  - `app/services/image_prompting.py`
  - `app/services/visual_planner.py`
  to the shared `is_tech_domain()` helper.
- Left `visual_brief.py` local token-only fallback detection in place, because it serves a narrower non-project fallback role and does not need the full project context.
- Added safe prompt-quality repair in `app/services/image_prompting.py`:
  - if `build_keyword_coverage()` returns `MISSING_FRAMING_SLOT`, inject framing
  - if it returns `MISSING_CAMERA_TECHNICAL_SLOT`, inject camera/technical anchors
  - if it returns `BOOK_TEXT_RISK`, add readable-text protection terms to the negative prompt
- Added regression coverage:
  - `tests/test_domain_detection.py`
  - updated `tests/test_image_prompting.py`
- Verified with:
  - `python -m unittest tests.test_domain_detection tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker tests.test_visual_planner`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 ComfyUI SDXL P1 candidate review and seed policy

- Implemented the first P1 candidate selection slice in `app/services/comfyui_pipeline.py`.
- Added `_select_best_candidate()` so candidate selection now returns:
  - selected path/prompt/prompt_id
  - normalized score and score version
  - `selection_reason`
  - `retry_recommended`
  - `retry_reason`
- `import_history_image()` now stores per-sentence candidate review metadata in:
  - `project["body_image_options"]["candidate_reviews"]`
- Current review behavior:
  - score `< 0.60` -> `retry_recommended=True`
  - score `< 0.72` -> borderline
  - otherwise -> normal auto selection
- `app/workers/image_worker.py` now preserves retry recommendations in `body_image_last_log` even when plan refresh runs later in the same job.
- `app/routers/image_gen.py` now exposes and applies explicit batch seed policy selection:
  - `fixed`
  - `spaced`
  - `random`
  - `variant_random`
- User-supplied `seed_policy` now overrides the suggestion/profile default in batch queue construction.
- Added regression coverage for:
  - low-score retry recommendation
  - fixed seed policy behavior
  - worker retry recommendation logging
- Verified with:
  - `python -m unittest tests.test_domain_detection tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker tests.test_visual_planner`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 ComfyUI SDXL Lightning opt-in profile

- Added `app/workflow_templates/comfyui/txt2img_sdxl_lightning.json`.
- Extended `app/services/image_generation_profiles.py` with named generation-profile handling and a new profile:
  - `sdxl_low_vram_lightning`
  - sampler: `euler`
  - scheduler: `sgm_uniform`
  - steps: `6`
  - cfg: `2.0`
  - `requires_lightning_checkpoint=True`
- Added `workflow_template` and `requires_lightning_checkpoint` to generation-profile metadata.
- `app/routers/image_gen.py` now:
  - accepts explicit `generation_profile` on batch-auto input
  - resolves the named profile through `profile_for_request()`
  - uses the profile's workflow template and runtime settings when the profile is explicitly requested
  - keeps standard SDXL defaults unchanged when no profile is requested
- Manual workflow render/submit also switches to the Lightning workflow when:
  - `generation_profile=sdxl_low_vram_lightning`
  - template is default/basic
  - no LoRA override is active
- This remains opt-in only. The code does not silently replace the standard SDXL path with Lightning.
- Verified with:
  - `python -m unittest tests.test_domain_detection tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker tests.test_visual_planner`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 ComfyUI SDXL micro-conditioning first pass

- Switched SDXL-oriented workflows to `CLIPTextEncodeSDXL`:
  - `txt2img_sdxl_basic.json`
  - `txt2img_sdxl_lightning.json`
  - `txt2img_sdxl_stickman_lora.json`
- Added runtime placeholders for SDXL micro-conditioning:
  - `__ORIGINAL_WIDTH__`
  - `__ORIGINAL_HEIGHT__`
  - `__TARGET_WIDTH__`
  - `__TARGET_HEIGHT__`
  - `__CROP_W__`
  - `__CROP_H__`
- Extended `app/services/image_generation_profiles.py` with:
  - profile-level zero-crop defaults
  - `micro_conditioning_values()` helper
- Extended `app/routers/image_gen.py` and `app/workers/image_worker.py` so manual jobs, batch jobs, and worker execution all pass the micro-conditioning values through to the workflow template.
- Current behavior is intentionally conservative:
  - default crop is `(0,0)`
  - original size defaults to requested width/height
  - target size defaults to requested width/height
  - no non-zero crop presets are turned on yet
- Verified with:
  - `python -m unittest tests.test_domain_detection tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker tests.test_visual_planner`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 ComfyUI SDXL IPAdapter style-reference first pass

- Added `app/services/comfyui_capabilities.py` so the backend can detect whether the local ComfyUI install is actually ready for style-reference runs.
- Readiness now checks three pieces independently:
  - an IPAdapter custom-node directory under `custom_nodes`
  - at least one model file under `models/ipadapter`
  - at least one CLIP-Vision model file under `models/clip_vision`
- Added model inventory reporting for `comfyui_ipadapter_style_reference` so Operator status can expose whether the backend is style-reference ready.
- Added a new opt-in generation profile:
  - `sdxl_style_reference`
  - workflow `txt2img_sdxl_ipadapter_style`
  - sampler `dpmpp_2m`
  - scheduler `karras`
  - steps `28`
  - cfg `5.6`
  - fixed seed policy for stronger cross-scene tone consistency
- Added route and worker plumbing for:
  - `style_reference_image`
  - `style_reference_strength`
- Safety policy in this first pass:
  - style reference is opt-in only
  - requests fail fast if IPAdapter prerequisites are not installed
  - requests fail fast if the reference image path cannot be resolved
  - LoRA + style-reference combination is intentionally blocked for now
- Verified with:
  - `python -m unittest tests.test_model_registry tests.test_comfyui_workflows tests.test_comfyui_routes tests.test_image_worker`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 ComfyUI SDXL style-reference UI and auto-selection

- Added Step 2 controls for:
  - generation profile
  - seed policy
  - style reference image
  - style reference strength
- Added a conservative automatic reference selection policy on the backend:
  - project thumbnail
  - first uploaded image
  - first generated image mapping
- Added client-side convenience behavior:
  - when `sdxl_style_reference` is selected, the UI pre-fills the reference input with a sensible default
  - batch generation now forwards explicit `seed_policy`
- The mixed `LoRA + style reference` path is still intentionally blocked.
- Verified with:
  - `python -m unittest tests.test_comfyui_routes tests.test_comfyui_workflows tests.test_model_registry`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 ComfyUI SDXL LoRA + style-reference mixed workflow

- Added `app/workflow_templates/comfyui/txt2img_sdxl_ipadapter_style_lora.json`.
- The `sdxl_style_reference` path can now branch into:
  - pure IPAdapter style-reference workflow
  - IPAdapter + LoRA mixed workflow
- Unified batch-auto template resolution with manual workflow resolution so both paths choose the same mixed template when:
  - `generation_profile=sdxl_style_reference`
  - `lora_name` is non-empty
- Verified with:
  - `python -m unittest tests.test_comfyui_workflows tests.test_comfyui_routes`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 Cross-scene style consistency scoring V1

- Added a lightweight adjacent-scene consistency signal to `candidate_reviews`.
- The new review fields are:
  - `style_consistency_score`
  - `style_consistency_version`
  - `style_consistency_reason`
  - `style_consistency_components`
- Current V1 scoring is metadata-only and compares the selected candidate for each scene against the selected candidate from the previous scene.
- Compared factors:
  - generation profile
  - workflow template
  - style-reference image path
  - LoRA name
  - width/height match
- This gives us a cheap and stable consistency signal without paying the runtime cost of CLIP or VLM image analysis yet.
- Verified with:
  - `python -m unittest tests.test_candidate_selection tests.test_image_worker`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 ControlNet Depth backend opt-in

- Added ControlNet Depth readiness detection in `app/services/comfyui_capabilities.py`.
- Added model inventory reporting for `comfyui_controlnet_depth`.
- Added named generation profile:
  - `sdxl_controlnet_depth`
  - sampler `dpmpp_2m`
  - scheduler `karras`
  - steps `28`
  - cfg `5.5`
- Added workflow template:
  - `app/workflow_templates/comfyui/txt2img_sdxl_controlnet_depth.json`
- Added route and queue payload support for:
  - `control_image`
  - `control_strength`
- Added worker placeholder forwarding for ControlNet execution.
- This is intentionally a backend-only first pass:
  - depth mode only
  - no UI yet
  - no multi-mode routing yet
- Verified with:
  - `python -m unittest tests.test_image_worker tests.test_model_registry tests.test_comfyui_workflows tests.test_comfyui_routes`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 Vision QA V1

- Added `app/services/image_quality.py` using Pillow-based low-cost image analysis.
- The QA result now records:
  - `vision_qa_score`
  - `vision_qa_version`
  - `vision_qa_reason`
  - `vision_qa_issue_codes`
  - `vision_qa_components`
- Current V1 checks:
  - low resolution
  - low entropy
  - low contrast
  - low edge detail
  - extreme exposure
  - near-duplicate previous scene
- Candidate selection now blends the prior prompt/text score with a lightweight image score so obviously weak or duplicate-looking images are penalized earlier.
- Verified with:
  - `python -m unittest tests.test_candidate_selection tests.test_image_worker`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 Step 2 ControlNet / QA UI polish

- Exposed `sdxl_controlnet_depth` in Step 2 alongside control image and control strength inputs.
- Added a shared image reference datalist so style-reference and control-image fields can reuse thumbnail, uploaded media, and generated mappings as quick picks.
- The generated mapping cards now show:
  - candidate score
  - vision QA score + issue codes
  - style consistency score
  - QA summary reason
- Manual and batch image enqueue now forward `control_image` and `control_strength` to match the backend support already in place.
- Verified with:
  - `node --check app/static/app.js`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-29 Simple diagram prompt mode for current newauto stack

- Implemented a conservative prompt-layer version of the new "simple, intuitive, sentence-context diagram image" direction directly inside the current `newauto` stack.
- Added `storage/visual_vocab/diagram.json` with icon-oriented mappings and domain-wide avoid terms for:
  - AI agent orchestration
  - browser automation
  - data center / power comparisons
  - task scheduling
  - choice / direction
  - effort / resistance
  - notification pressure
- Added `style_preset=simple_diagram` to `app/services/image_prompting.py`.
- When `simple_diagram` is selected, prompt suggestion now:
  - converts the existing `VisualBrief` into a simpler icon-first composition
  - prefers a central icon + 1-2 support icons
  - keeps literal similes simple when they are the sentence's main image
  - appends diagram-specific global avoid terms
- `app/services/prompt_compiler.py` now has a dedicated diagram prompt assembly path that:
  - removes photo/editorial camera anchors such as `35mm lens` and `real-world textures`
  - emits flat explainer language such as `large readable icons`, `plain background`, and `clear arrow or comparison structure`
  - hardens negative prompts against photorealism, 3D drift, dense backgrounds, crowd scenes, and readable text
- `app/services/prompt_quality.py` now flags:
  - `DIAGRAM_STYLE_COLLISION`
  - `DIAGRAM_TEXT_CONTROL_MISSING`
  - `DIAGRAM_COMPLEXITY_RISK`
- Added regression coverage in:
  - `tests/test_image_prompting.py`
  - `tests/test_prompt_compiler.py`
  - `tests/test_prompt_quality.py`
- Verified with:
  - `python -m unittest tests.test_image_prompting tests.test_prompt_compiler tests.test_prompt_quality`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-30 Simple diagram feature wiring in Step 2

- Finished the missing project-level persistence path for diagram-style prompting.
- `app/routers/projects.py`
  - `PUT /api/projects/{pid}/features` now accepts `style_preset`
  - allowed values are:
    - `""`
    - `k_webtoon`
    - `simple_diagram`
  - the route merges the value into `project["body_image_options"]["style_preset"]` instead of replacing the whole options object
- `app/static/index.html`
  - added a Step 2 `Style Preset` selector with:
    - `Default`
    - `K-Webtoon`
    - `Simple Diagram`
- `app/static/app.js`
  - feature-save payload now includes `style_preset`
  - feature controls now rehydrate the current preset from `body_image_options`
- Added regression coverage in `tests/test_feature_workflow.py` for:
  - saving `style_preset=simple_diagram`
  - rejecting unknown `style_preset` values
- Verified with:
  - `python -m unittest tests.test_feature_workflow tests.test_image_prompting tests.test_prompt_compiler tests.test_prompt_quality`
  - `node --check app/static/app.js`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-30 Simple diagram recommendation pass

- Added a lightweight recommendation layer so `simple_diagram` can be suggested without silently forcing it.
- `app/services/image_prompting.py`
  - added `_recommended_style_preset(project, sentence)`
  - current policy recommends `simple_diagram` for non-bible tech/explainer projects when no explicit preset is already saved
  - `suggest_image_prompt()` now returns:
    - `requested_style_preset`
    - `recommended_style_preset`
- `app/static/app.js`
  - Step 2 `Style Preset` selector now defaults to a client-side recommendation when the project has no saved preset
  - `suggestImagePrompt()` now saves current feature settings before requesting prompt suggestions, so the chosen preset is reflected immediately
  - prompt suggestion status text now shows which style preset was used or recommended
- Added regression coverage in `tests/test_image_prompting.py`:
  - tech-domain prompt suggestion recommends `simple_diagram`
  - explicit `simple_diagram` use suppresses recommendation fallback
- Verified with:
  - `python -m unittest tests.test_image_prompting tests.test_feature_workflow tests.test_prompt_compiler tests.test_prompt_quality`
  - `node --check app/static/app.js`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-30 Simple diagram tech-icon specificity tuning

- Tightened `simple_diagram` matching so tech/explainer prompts stop collapsing into the same generic AI icon.
- `storage/visual_vocab/diagram.json`
  - added more specific diagram concepts and Korean keywords for:
    - model training architecture
    - GPU cluster
    - company-led shift
- `app/services/image_prompting.py`
  - changed diagram vocab scoring to prefer sentence hits over generic keyword spillover
  - added a penalty so the broad `ai system` concept does not dominate when more specific technical concepts exist
  - when the sentence explicitly mentions `Google / 구글 / company / 기업 / 선도`, `company-led shift` is prioritized to the front of the diagram match list
  - prevented non-tech literal-simile handling from overriding tech-diagram structure
- `tests/test_image_prompting.py`
  - added coverage for:
    - GPU sentences preferring a specific GPU icon over a generic AI icon
    - Korean company-shift sentences preferring company/blueprint imagery
- Practical validation:
  - prompt inspection on project `a75ea6a907de` showed GPU/resource sentences now center on `stacked GPU rack icon`
  - one real ComfyUI generation completed successfully for the company-shift sentence:
    - `simple_diagram_scene_004_00001_.png`
  - a follow-up low-resolution run remained long-running in the local ComfyUI queue, which confirms current throughput / VRAM pressure is still an operational bottleneck separate from prompt correctness
- Verified with:
  - `python -m unittest tests.test_image_prompting`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

## 2026-04-30 Naver comment video relevance gate and news diagram fallback

- Diagnosed project `5717dcffbfb6` after the generated video showed unrelated abstract/simple-diagram images and audible sentence-level voice drift.
- Confirmed the image side was a workflow gate failure, not just a weak prompt:
  - selected generated images had `candidate_score` around `0.21-0.37`
  - selected mappings were marked `retry_recommended`
  - prompt manifests had `IMAGE_PROMPT_QUALITY_FAILED`
  - `visual_source_mode=hybrid` skipped `validate_generated_image_mappings()` because it only enforced checks for `comfyui_auto`
- Updated `app/services/visual_relevance.py`:
  - generated mappings are detected by ComfyUI metadata such as `prompt_id`, `manifest_sentence_hash`, and `candidate_score`
  - generated assets in `hybrid` now receive the same validation path as `comfyui_auto`
  - low selected candidate scores below `0.55` emit `IMAGE_CANDIDATE_SCORE_LOW`
  - selected retry candidates emit `IMAGE_CANDIDATE_RETRY_RECOMMENDED`
  - manual/user-uploaded hybrid mappings without generated metadata are not blocked
  - added `visual_mismatch_report` JSON/Markdown builders
- Integrated mismatch report writing into:
  - `app/services/preflight.py`
  - `app/services/render.py`
- Added lightweight TTS consistency reporting in `app/services/tts.py`:
  - `tts_consistency_report.json` is written beside `tts_run_manifest.json`
  - verifies whether every sentence shares the same voice preset and key generation profile fields
  - records per-sentence duration, RMS, spectral centroid, and relative drift from the first sentence
  - recommends `full_passage_or_reference_voice` if metadata or audio drift checks fail
- Updated simple diagram prompt repair:
  - `app/services/prompt_quality.py` no longer applies essay camera-anchor checks to `simple_diagram`
  - `app/services/image_prompting.py` no longer injects `35mm lens`, `sharp focus`, `natural color`, or `detailed real-world textures` while repairing `simple_diagram`
  - diagram repair now uses flat icon anchors instead
- Added news/comment/election support:
  - `app/services/domain_detection.py` now exposes `is_news_explainer_domain()`
  - `app/services/visual_planner.py` can classify `news_explainer`
  - news fallback tokens cover news article comments, like/dislike spikes, media alerts, comment sorting, coordinated manipulation, public opinion distortion, and response speed
  - `storage/visual_vocab/diagram.json` now includes corresponding diagram concepts
- Updated `naver-comment-video-diagnosis-plan.md` with implementation status and verification.
- Practical validation on `5717dcffbfb6`:
  - new validation reports 33 visual relevance issues instead of silently passing
  - generated:
    - `storage/projects/5717dcffbfb6/visual_mismatch_report.json`
    - `storage/projects/5717dcffbfb6/visual_mismatch_report.md`
- Verified with:
  - `python -m unittest tests.test_visual_relevance tests.test_image_prompting tests.test_prompt_compiler tests.test_prompt_quality tests.test_domain_detection tests.test_visual_planner tests.test_tts_pipeline`
  - `python -m unittest tests.test_tts_pipeline`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## 2026-05-01 Naver comment prompt rebuild and stricter TTS drift report

- Followed up on the Naver comment test project after the initial P0 gate fix.
- Raised `app/services/visual_planner.py` planner cache version from `2` to `3` so existing cached generic fallback plans are invalidated after adding `news_explainer`.
- Tightened `news_explainer` fallback coverage:
  - handled `폭증` and `몰리` reaction-spike language, not only `급증`
  - prioritized comment sorting scenes before generic alert scenes when a sentence contains both alert and sorting language
  - added a user-viewpoint fallback for vague sentences such as `이용자 입장에서도 의미가 있습니다`
- Rebuilt `storage/projects/5717dcffbfb6/image_prompts_manifest.json` with `style_preset=simple_diagram`.
- Rebuilt prompt quality report:
  - `11/11` prompts generated
  - every prompt uses `news_explainer`
  - all keyword coverage checks pass
- Existing selected images still fail validation:
  - `11` x `IMAGE_CANDIDATE_SCORE_LOW`
  - `11` x `IMAGE_CANDIDATE_RETRY_RECOMMENDED`
  - preflight now fails on visual relevance instead of rendering bad images
- Improved TTS consistency report:
  - `_audio_feature_summary()` now estimates pitch using a lightweight autocorrelation pass
  - `tts_consistency_report.json` includes `estimated_pitch_hz`, per-sentence pitch drift, and `max_estimated_pitch_relative_drift`
  - existing project `5717dcffbfb6` now flags `audio_consistency_passed=False`, `max_estimated_pitch_relative_drift=0.5293`, and recommends `full_passage_or_reference_voice`
- Verified with:
  - `python -m unittest tests.test_visual_relevance tests.test_image_prompting tests.test_prompt_compiler tests.test_prompt_quality tests.test_domain_detection tests.test_visual_planner tests.test_tts_pipeline`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## 2026-05-01 Naver comment image regeneration and TTS preflight gate

- Completed a final diagnostic regeneration pass for project `5717dcffbfb6`.
- Found that generated images had completed correctly but the old render output still referenced previous `project_...` media in `render_report.json`.
- Rebuilt `scene_plan` and `render_plan` from current `body_image_mappings`, which now point to `naver_comment_rebuild_scene_*.png`.
- Fixed a render timing edge case in `app/services/scene_plan.py`:
  - previous scene durations used only each TTS cue `dur`
  - inter-sentence gaps therefore accumulated into the render frame planner's final segment correction
  - scene duration now runs from the current cue start to the next cue start, assigning silence to the current visual segment
- Added preflight coverage for `tts/tts_consistency_report.json`:
  - `tts_consistency` passes when metadata is consistent and audio drift is either unchecked or within threshold
  - it fails with a concrete drift summary and recommended mode when pitch/spectral drift indicates voice inconsistency
- Practical validation on `5717dcffbfb6`:
  - generated image relevance issues: `0`
  - selected image scores: `0.633-0.742`
  - regenerated `output.mp4` duration: `87.666667s`
  - audio timeline duration: `87.671s`
  - max visual frame drift: `1` frame
  - preflight now fails only on TTS consistency, with `pitch drift 0.53` and `spectral drift 0.33`
- Verified with:
  - `python -m unittest tests.test_scene_plan tests.test_render_plan tests.test_render_visual_track tests.test_visual_relevance`
  - `python -m unittest tests.test_feature_workflow tests.test_scene_plan tests.test_visual_relevance tests.test_tts_pipeline`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

Follow-up:

- Added `synthesis_mode=full_passage` to TTS profiles and API payloads.
- In full-passage mode, `run_tts_job()` calls OmniVoice once with the whole narration, then splits the returned buffer across sentence files by sentence weight.
- Render audio concatenation now respects the gap encoded in `timings.json` instead of always inserting `0.3s`; this prevents full-passage timings from drifting against the raw audio.
- Full-passage consistency uses a separate pitch drift threshold (`0.35`) because one continuous speaker can still vary pitch naturally across sentence chunks.
- Re-ran project `5717dcffbfb6` with full-passage TTS:
  - `audio_consistency_passed=True`
  - `recommended_tts_mode=full_passage`
  - `preflight_ok=True`
  - final `output.mp4` duration: `84.76s`
  - audio duration: `84.76s`
  - duration drift: `0.0s`
  - visual relevance issues: `0`
- Additional verification:
  - `python -m unittest tests.test_tts_pipeline tests.test_tts_presets tests.test_feature_workflow`
  - `python -m unittest tests.test_render_visual_track tests.test_feature_workflow tests.test_tts_pipeline`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## 2026-05-01 Naver comment strict image gate and diagram QA

- Implemented the follow-up recovery plan in `naver-comment-final-image-audit-plan.md`.
- Added `storage/visual_vocab/news_explainer.json` with structured news/comment concepts and composition templates:
  - `AlertFlow`
  - `SpikeDetection`
  - `SortingControl`
  - `CoordinationPressure`
  - `UserView`
  - `LimitationShield`
  - `SpeedResponse`
  - `PreserveAndReveal`
- Extended the visual planning/prompting schema with `composition_template` so news explainer scenes can carry an explicit layout grammar from `visual_planner.py` into `image_prompting.py`.
- Added `app/services/prompt_strictifier.py` and wired `BORDERLINE_CANDIDATE` through `prompt_repair.py`, `comfyui_pipeline.py`, and `image_worker.py` so a borderline simple-diagram/news image gets one stricter regeneration attempt before final acceptance.
- Kept the existing worker retry floor at `0.55`, but added a stricter final generated-image threshold of `0.72` for `news_explainer`/`simple_diagram` unless `quality_mode=fast`.
- Extended diagram post-generation QA in `image_quality.py`:
  - high edge density can flag `DENSE_DIAGRAM_CLUTTER`
  - many tiny components can flag `TINY_ICON_GRID`
  - weak dominant object area can flag `DOMINANT_SUBJECT_TOO_SMALL`
  - abstract dense UI patterns can flag `ABSTRACT_UI_NO_CLEAR_SUBJECT` and `GENERIC_DASHBOARD_LAYOUT`
- Extended prompt quality checks with news-specific issue codes such as `NEWS_DIAGRAM_TOO_GENERIC`, `NEWS_COMMENT_PANEL_MISSING`, `DENSE_DASHBOARD_RISK`, `REACTION_SPIKE_NOT_DOMINANT`, `USER_VIEWPOINT_MISSING`, and `LIMITATION_METAPHOR_MISSING`.
- Improved `visual_mismatch_report` so it prefers `project["sentences"]`, writes UTF-8 Markdown/JSON with `sentence_source`, includes strict retry and vision QA metadata, and reports `below_final_threshold_selected_images`.
- Regenerated:
  - `storage/projects/5717dcffbfb6/visual_mismatch_report.json`
  - `storage/projects/5717dcffbfb6/visual_mismatch_report.md`
- Current report now shows readable Korean and intentionally blocks the previous selected borderline images with `FINAL_IMAGE_SCORE_TOO_LOW` / `IMAGE_CANDIDATE_BORDERLINE_RETRY_REQUIRED`; new images still need regeneration before that project should be rendered again.
- Verified with:
  - `python -m unittest tests.test_visual_relevance tests.test_candidate_selection tests.test_prompt_repair tests.test_image_quality tests.test_image_prompting tests.test_visual_planner tests.test_prompt_quality`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`
## 2026-05-01 Leaf-film image gate P0

- Implemented the P0 recovery path from `leaf-film-video-upgrade-plan.md` after reviewing `leaf-film-audit-feedback.md`.
- Domain detection no longer treats broad words such as `research`, `model`, and `training` as tech by themselves. They now require tech co-occurrence, while agriculture/material context can resolve to `agriculture_environment` or `science_materials`.
- `visual_planner._domain_for_project()` now evaluates `news_explainer -> agriculture_environment -> science_materials -> tech -> essay` after bible mode, reducing false tech prompts for environmental science articles.
- `repair_prompts()` now returns `should_retry=False` for empty issue codes, preventing generic repair text from mutating otherwise valid prompts.
- `image_worker` now detects manual art-directed items and skips automatic repair, recording `manual_art_directed_skip` in candidate reviews.
- Generated-image validation now has explicit policies: `strict_generated`, `manual_light`, `upload_only`, and `skip_legacy`. `manual_light` keeps hash/media/hard-QA checks while skipping metadata-only score failures.
- Manual art-directed candidate scoring uses `candidate_score_v2:manual_art_directed_v1`, normalized file sanity, and a higher Vision QA weight.
- Body image mappings now preserve `candidate_score_version` and `vision_qa_issue_codes` when loaded from the database, so reports and gates can inspect them reliably.
- Verified with:
  - `python -m unittest tests.test_domain_detection tests.test_prompt_repair tests.test_candidate_selection tests.test_visual_relevance tests.test_image_worker`
  - `npm run typecheck:frontend`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## 2026-05-01 Leaf-film agriculture/science visual grammar

- Added `storage/visual_vocab/agriculture_environment.json` and `storage/visual_vocab/science_materials.json`.
- The new vocab includes concrete composition templates such as `WasteToMaterial`, `FieldMulchFunction`, `PollutionFragment`, `GrowthComparison`, `NonToxicSprout`, `FutureFarm`, `LabExtraction`, `SoilDecomposition`, and `MaterialSample`.
- `visual_planner` now includes vocab fields such as `icon`, `support`, `relation`, `composition_template`, and `layout` in the LLM guide, and fallback planning can produce concrete agriculture/science `must_show` targets from vocab matches.
- `prompt_compiler` now has agriculture/science positive and negative prompt branches:
  - positive prompts emphasize editorial documentary photography, natural daylight, soil texture, natural material closeup, and concrete process relationships
  - negative prompts block tech-dashboard drift, circuit diagrams, AI brain icons, server racks, hay bales, pipe rolls, empty fields, and generic lab shelves
- `image_prompting` now routes `agriculture_environment` and `science_materials` plans through an `environmental_science_editorial` template using the basic SDXL path with LoRA disabled.
- Candidate score versions can now report `candidate_score_v2:agriculture_environment_v1` or `candidate_score_v2:science_materials_v1` for science/editorial prompts.
- Verified with:
  - `python -m unittest tests.test_prompt_compiler tests.test_image_prompting tests.test_visual_planner tests.test_candidate_selection tests.test_domain_detection`
  - `python -m unittest tests.test_domain_detection tests.test_prompt_repair tests.test_candidate_selection tests.test_visual_relevance tests.test_image_worker tests.test_prompt_compiler tests.test_image_prompting tests.test_visual_planner`
  - `npm run typecheck:frontend`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## 2026-05-01 Leaf-film science QA and contact sheet automation

- Added an `editorial_science` image QA mode to `image_quality.py`.
  - It keeps the existing resolution/entropy/contrast/edge/exposure metrics.
  - It adds lightweight `EDITORIAL_SUBJECT_TOO_SMALL` and `LOW_MATERIAL_DETAIL` checks without claiming full object detection.
- Added prompt/domain-based V1 agriculture/science issue codes in `comfyui_pipeline.py`:
  - `MISSING_DOMINANT_FILM_OBJECT`
  - `SOIL_WITHOUT_PLASTIC_FRAGMENT`
  - `LAB_WITHOUT_PROCESS_FLOW`
  - `GENERIC_FIELD_ONLY`
  - `DECOMPOSITION_NOT_VISIBLE`
  - `SYMBOLIC_ONLY_WHEN_LITERAL_REQUIRED`
- These V1 issue codes are intentionally text/prompt + basic-image-heuristic based. CLIP or Vision LLM review remains a later opt-in stage.
- Added `write_visual_contact_sheet(project)` in `visual_relevance.py`.
  - It writes `diagnostic_contact_sheet.jpg`.
  - Each row includes thumbnail, sentence snippet, candidate score, validation policy, selected reason, issue codes, vision QA codes, must_show, and prompt snippet.
- `image_worker._refresh_project_plans()` now writes both visual mismatch report and contact sheet after generated images refresh scene/render plans.
- Verified with:
  - `python -m unittest tests.test_image_quality tests.test_candidate_selection tests.test_visual_relevance tests.test_image_worker`
  - `python -m unittest tests.test_domain_detection tests.test_prompt_repair tests.test_candidate_selection tests.test_visual_relevance tests.test_image_worker tests.test_prompt_compiler tests.test_image_prompting tests.test_visual_planner tests.test_image_quality`
  - `npm run typecheck:frontend`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## 2026-05-01 Leaf-film final remaining items

- Finished the remaining items in `leaf-film-video-upgrade-plan.md`.
- Added an on-demand diagnostics route:
  - `POST /api/projects/{pid}/visual-diagnostics/regenerate`
  - writes `visual_mismatch_report.json`, `visual_mismatch_report.md`, and `diagnostic_contact_sheet.jpg`
- Added `micro_motion_locked` for photo/editorial agriculture and science scenes.
  - It uses integer `frame_count` in the FFmpeg filter graph.
  - It keeps `trim=end_frame=...` and `setpts=N/(30*TB)`.
  - It keeps diagrams and dense text-like imagery on `still_locked`.
- Extended `render_plan.py` so generated agriculture/science editorial images can opt into the locked micro motion while default generated images remain stable.
- Added selective high-risk multi-candidate queueing to the ComfyUI batch route.
  - High-risk agriculture/science templates such as `SoilDecomposition`, `PollutionFragment`, `LabExtraction`, `GrowthComparison`, and `WasteToMaterial` now get at least two candidates when `selective_high_risk_variants` is enabled.
  - Easy scenes keep the base `variants_per_scene` count to avoid doubling GPU work.
- Verification:
  - `python -m unittest tests.test_render_visual_track tests.test_render_plan`
  - `python -m unittest tests.test_comfyui_routes.ComfyUiRouteTests.test_batch_auto_job_selectively_expands_high_risk_variants tests.test_comfyui_routes.ComfyUiRouteTests.test_visual_diagnostics_regenerate_route_writes_report_and_contact_sheet`
  - `npm run typecheck:frontend`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`
- Note: running the full `tests.test_comfyui_routes` file still exposed pre-existing/flaky route-test issues around mocked image bytes and capability/state interactions. The new route and selective-variant tests pass in isolation.

## 2026-05-02 Food-trend visual planning recovery

- Implemented the recovery path from `ube-article-visual-mismatch-recovery-plan.md`.
- Added `food_trend` domain detection for Korean/English food, dessert, retail, ube, matcha, purple yam, cafe, supermarket, and export terms.
- Added `storage/visual_vocab/food_trend.json` with concrete vocab entries for:
  - ube / purple yam ingredient hero
  - matcha vs ube color comparison
  - social media food spread
  - cafe/bakery launch
  - convenience-store/supermarket retail expansion
  - Philippines ube export growth
  - food-industry trend shelf
- Updated `visual_planner` so food-trend fallback uses vocab tokens and composition templates instead of generic essay interiors.
- Extended Korean concrete token extraction so Hangul nouns such as `우베`, `말차`, `보라색`, `카페`, `편의점`, and `수출` can influence fallback planning.
- Removed the most harmful generic fallback phrases from default brief/prompt compilation:
  - `single everyday object in a quiet realistic room`
  - `quiet realistic environment`
- Added a `food_trend_editorial` image template and prompt compiler branch with product-focused food/editorial language and food-domain negative prompts.
- Tightened visual relevance validation so `allow_low_quality_generated_images` no longer skips generated images that carry prompt/candidate metadata; only `force_render_with_failed_visuals` bypasses strict generated-image validation.
- Extended visual mismatch reports with keyword audit fields:
  - `expected_keywords`
  - `prompt_keyword_hits`
  - `missing_expected_keywords`
  - `generic_fallback_hits`
  - `semantic_match_score`
  - `decision`
- Verification:
  - `python -m compileall app tests`
  - `python -m unittest tests.test_domain_detection tests.test_visual_planner tests.test_prompt_compiler tests.test_prompt_quality tests.test_visual_relevance tests.test_visual_brief tests.test_image_prompting`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`
  - `npm run typecheck:frontend`
- Note: full `python -m unittest discover tests` still exposes pre-existing environment/test-state issues unrelated to this change: ComfyUI route mock image bytes/capability 502s, real DB autopilot history affecting operator ordering, and TTS mock error-output noise.

## 2026-05-02 Food-trend final regeneration follow-up

- Root cause found during live regeneration: the project kept using a valid sentence-hash cache whose `domain` was still `essay`, so new `food_trend` code did not affect the actual prompt manifest.
- Fixed `visual_planner` cache invalidation:
  - bumped planner cache version to `6`
  - rejects cached plans when cached domain differs from the current detected domain
- Fixed food fallback path:
  - `_fallback_entry()` now passes the actual non-tech domain into `build_visual_brief` instead of forcing `generic`
  - generic fallback strings such as `food product display tied to the sentence` are treated as invalid for food-trend planning
  - connector sentences like "영향력은 여기서 멈추지 않습니다" route to retail expansion visuals in a food-trend project
- Fixed prompt-only batch generation:
  - `batch-auto` no longer auto-resolves a previous generated image as `style_reference_image` or `control_image` unless the requested profile is actually `sdxl_style_reference` or `sdxl_controlnet_depth`
  - this prevents stale layouts from turning prompt-only food images into heavy style/control retries
- Regenerated project `f8c0fd9c4455`:
  - 18 candidates generated with prefix `ube_food_v2`
  - 9 selected mappings scored `0.798~0.879`
  - no selected image below threshold, no retry-recommended selected image, no quality-failed image
  - `diagnostic_contact_sheet.jpg` visually confirms the new food/ube retail direction
  - rendered `C:\Users\petbl\newauto\storage\projects\f8c0fd9c4455\output.mp4`, duration `64.133333s`, `duration_guard_passed=true`
- Verification:
  - `python -m unittest tests.test_domain_detection tests.test_visual_planner tests.test_prompt_compiler tests.test_prompt_quality tests.test_visual_relevance tests.test_visual_brief tests.test_image_prompting`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## 2026-05-02 ChatGPT Image 2.0 article workflow

- Ran the Naver article project through the browser console workflow and completed project `3accf1ac492c`.
- Root causes found during the live run:
  - the generated source draft had mojibake, which poisoned the visual planner input;
  - `article/news` domain signals were broader than tech signals, so an AI product article could be classified as `news_explainer`;
  - the default TTS worker must run from `omnivoice_env`, otherwise OmniVoice imports fail;
  - OmniVoice `instruct` accepts only fixed tokens such as `male, middle-aged, moderate pitch, korean accent`;
  - ComfyUI timed out on the final creative-workflow scene, so the final render used manual diagram fallback assets for the metric/text/workflow scenes.
- Code/data fixes:
  - `visual_planner` now prioritizes tech domain detection before generic news-explainer detection.
  - Growth-metric detection now also recognizes `상승 막대`, `숫자 배지`, and `성장 속도`.
  - `storage/visual_vocab/tech.json` now includes photo-to-style transformation and practical creative-workflow vocab entries.
- Final project corrections:
  - rewrote the script as clean UTF-8 Korean in `manual_script_ko.txt`;
  - forced fallback tech visual planning for stability instead of waiting on the local LLM;
  - replaced the 60%, 130%, combined-growth, text-rendering, and workflow scenes with clear diagram assets;
  - regenerated TTS with OmniVoice full-passage mode and a fixed seed.
- Final render:
  - `C:\Users\petbl\newauto\storage\projects\3accf1ac492c\output.mp4`
  - duration `71.696s`
  - `duration_guard_passed=true`
  - `fallback_used=false`
- Verification:
  - `python -m unittest tests.test_visual_planner tests.test_prompt_compiler tests.test_domain_detection`
  - `validate_generated_image_mappings(...)` returned 0 issues after the final manifest/manual-diagram update
  - `ffprobe` confirmed the final duration

## 2026-05-02 ChatGPT Image 2.0 P0 visual recovery implementation

- Fixed the prompt-planning regression where `disable_llm_visual_planner=True` prevented `image_prompting` from calling `build_scene_visual_plan()` at all.
- The option now disables only the LLM planner; deterministic fallback visual planning still produces `visual_plan.source="fallback"` and `composition_template` metadata.
- Preserved tech composition templates during simple-diagram prompt adaptation so growth-metric scenes keep `GrowthMetricComparison` targets instead of being replaced by generic diagram-vocab icons.
- Tightened generated-image validation:
  - generated metadata now forces `strict_generated` before `manual_art_directed` can downgrade the policy;
  - tech/news/simple-diagram/composition-template scenes block selected generated images below final score `0.72`;
  - hard Vision QA failures remain blocking for generated mappings in hybrid/manual workflows.
- Verification:
  - `python -m compileall app tests`
  - `python -m unittest tests.test_image_prompting tests.test_visual_relevance tests.test_visual_planner tests.test_prompt_compiler tests.test_domain_detection`

## 2026-05-02 Food-trend Vision QA refinement

- Added a `food_trend_editorial` Vision QA mode in `app/services/image_quality.py`.
- The new heuristics score:
  - visible purple/ube accent presence,
  - dominant product subject area,
  - empty neutral interior drift.
- New food-trend Vision QA issue codes:
  - `FOOD_TREND_PURPLE_ACCENT_WEAK`
  - `FOOD_TREND_SUBJECT_TOO_SMALL`
  - `FOOD_TREND_EMPTY_INTERIOR`
  - `FOOD_TREND_GENERIC_INTERIOR`
- `app/services/comfyui_pipeline.py` now routes `visual_brief.domain == "food_trend"` candidates through that QA mode and adds prompt-aware follow-up issue codes:
  - `MISSING_UBE_COLOR_SIGNAL`
  - `FOOD_PRODUCT_NOT_DOMINANT`
  - `RETAIL_CONTEXT_NOT_VISIBLE`
- These food-trend follow-up issues apply a bounded Vision QA penalty and mark candidates with `candidate_score_version` suffix `food_trend_v1`.
- Verification:
  - `python -m compileall app tests`
  - `python -m unittest tests.test_image_quality tests.test_domain_detection tests.test_visual_planner tests.test_prompt_compiler tests.test_visual_relevance tests.test_image_prompting`
  - `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## 2026-05-02 Food-trend visual mismatch audit refinement

- Refined `app/services/visual_relevance.py` so `prompt_keyword_hits` no longer depends on exact phrase matches only.
- Added fuzzy keyword matching for food-trend audit phrases, allowing semantic equivalents such as:
  - `food store display` -> `modern food market display`
  - `purple products` -> `purple ube color accent`
  - `new product shelf` -> `changing display shelf`
- Regenerated `f8c0fd9c4455` diagnostics:
  - `visual_mismatch_report.json`
  - `visual_mismatch_report.md`
  - `diagnostic_contact_sheet.jpg`
- After regeneration, sentence `0` in the ube project moved from false-positive `block_and_retry` to `pass`.

## 2026-05-06 LM Studio MCP HPSL timeout recovery

- Root cause: `start_hpsl_flow_workflow` could return a project ID while the source draft worker was not actually able to complete the queued job.
- Fixed the Windows worker lock check in `app/workers/worker_lock.py`:
  - `os.kill(pid, 0)` is unreliable for stale PID checks on Windows.
  - Windows now uses `tasklist /FI "PID eq ..."` to decide whether a lock owner still exists.
- Stabilized 1-minute HPSL generation in `app/services/hpsl_script.py`:
  - target-minute `1` HPSL drafts now use deterministic source-note assembly by default;
  - this prevents LM Studio/Gemma4 JSON failures, long local generation, and heartbeat expiry from blocking a short script.
- Hardened source article decoding in `app/services/source_fetch.py`:
  - added mojibake scoring for UTF-8-as-Latin-1 style Korean corruption;
  - source cache entries that look mojibake are ignored and re-fetched.
- Recovery verification used project `2fbe8fc6b8c2`:
  - recollected keyword sources for `2026년 5월 6일 최신 AI 뉴스`;
  - regenerated HPSL draft to `done` within about 8 seconds;
  - applied the script and generated `storage/projects/2fbe8fc6b8c2/flow_prompts.json`;
  - verified stored `script.txt` has Hangul and no mojibake markers.

## 2026-05-06 One-command LM Studio Flow video workflow

- Added an MCP top-level command in `scripts/newauto_mcp.py`:
  - `make_hpsl_flow_short_video(keyword_or_url, title="", target_minutes=1, tone="설명형")`
  - It creates a new project, collects keyword/URL source material, queues HPSL generation, waits for completion, applies the script, generates Flow prompts, then opens newauto Step 2 and Google Flow.
- Added a second MCP bridge for the post-Flow step:
  - `attach_latest_flow_downloads(project_id, downloads_dir="", count=0, start_sentence_number=1, since_minutes=180)`
  - It scans the user's Downloads folder for recent image/video Flow results and attaches them to missing sentence assets in sentence order.
- Added local-path Flow asset attachment API:
  - `POST /api/flow/assets/{pid}/attach-local`
  - The endpoint copies local Flow outputs into `media/` and `flow_assets/`, updates `body_image_mappings`, updates `media_order`, and preserves the Flow prompt per sentence.
- MCP instructions now steer LM Studio chat behavior:
  - natural full workflow request -> `make_hpsl_flow_short_video`;
  - user says Flow downloads are done -> `attach_latest_flow_downloads`;
  - all sentence assets attached -> `continue_after_flow_assets` for OmniVoice, sync, subtitles, and render.
- Verification:
  - `python -m compileall app\routers\flow.py scripts\newauto_mcp.py`
  - `C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile scripts\newauto_mcp.py`
  - `python -m pytest tests/test_script_compile.py tests/test_scene_plan.py tests/test_render_plan.py tests/test_visual_relevance.py`
  - `POST /api/flow/assets/2fbe8fc6b8c2/attach-local` with empty paths returns HTTP 400 as expected.

## 2026-05-06 Flow browser automation through CDP

- Added `scripts/flow_browser_automation.py`.
- The script launches a dedicated Chrome/Edge CDP browser profile:
  - CDP URL: `http://127.0.0.1:9223`
  - profile: `data/flow-browser-profile`
  - target app: Google Flow
- This keeps Google auth separate from the user's personal browser profile while preserving the Flow login session across MCP calls.
- MCP additions in `scripts/newauto_mcp.py`:
  - `open_flow_for_auth(project_id="")`: opens the persistent Flow browser so the user can sign in or approve permissions.
  - `automate_flow_generation(project_id, start_sentence_number=1, limit=0, click_generate=True)`: uses Playwright over CDP to find a visible prompt input, fill sentence-level Flow prompts, and click Generate where possible.
  - `download_flow_results_from_browser(project_id, expected_count=0)`: tries to click visible Flow download buttons and save results into the Downloads folder.
- Operational contract:
  - user handles only login/permission prompts and any UI block that cannot be automated;
  - after successful download, `attach_latest_flow_downloads` attaches the latest assets to the project;
  - `continue_after_flow_assets` then runs OmniVoice, timing sync, subtitles, and rendering.
- Verification:
  - `python -m compileall scripts\flow_browser_automation.py scripts\newauto_mcp.py`
  - `C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile scripts\flow_browser_automation.py scripts\newauto_mcp.py`
  - targeted pytest 37 passed.

## 2026-05-06 Stepwise approval workflow mode

- Added approval-gated MCP tools in `scripts/newauto_mcp.py`:
  - `start_stepwise_hpsl_video_workflow(keyword_or_url, title="", target_minutes=1, tone="설명형")`
  - `continue_stepwise_hpsl_video_workflow(project_id="")`
- State is persisted under:
  - `storage/stepwise_workflows/{project_id}.json`
  - `storage/stepwise_workflows/latest.json`
- Each `continue` call runs exactly one stage, reports completion, and stops:
  - source collection is done by `start_stepwise_hpsl_video_workflow`;
  - HPSL script generation;
  - script apply + Flow prompt generation;
  - Flow auth browser open;
  - Flow prompt fill/generate automation;
  - Flow download/asset attach;
  - OmniVoice TTS;
  - scene/render plan + preflight + render.
- If Flow automation cannot find login, prompt input, generate, download, or downloaded files, it does not advance the saved step. The user can fix the visible browser state and send `진행` again to retry the same stage.
- This mode makes failures observable at the exact stage instead of hiding them inside a single end-to-end command.
- Verification:
  - `python -m compileall scripts\newauto_mcp.py scripts\flow_browser_automation.py`
  - `C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile scripts\newauto_mcp.py scripts\flow_browser_automation.py`
  - targeted pytest 37 passed.

## 2026-05-06 LM Studio MCP timeout wrapper recovery

- Changed `make_hpsl_flow_short_video` into a compatibility wrapper around `start_stepwise_hpsl_video_workflow`.
- This prevents older LM Studio chat tool calls from blocking while trying to run source research, HPSL, Flow, TTS, and render in one MCP request.
- Added source draft worker auto-start/recovery in `scripts/newauto_mcp.py`:
  - stale `storage/source_draft_worker.lock` files with dead Windows PIDs are removed;
  - the worker starts detached with LM Studio/Gemma4 environment variables;
  - `continue_stepwise_hpsl_video_workflow` can recover a stopped draft queue before generating the HPSL script.
- Cleaned `scripts/flow_browser_automation.py` typing to avoid `Any` while keeping Playwright CDP behavior unchanged.
- Verification:
  - `python -m compileall scripts\newauto_mcp.py scripts\flow_browser_automation.py app\workers\worker_lock.py app\services\hpsl_script.py app\services\source_fetch.py app\routers\flow.py`
  - `C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile scripts\newauto_mcp.py scripts\flow_browser_automation.py`
  - `python -m pytest tests/test_script_compile.py tests/test_scene_plan.py tests/test_render_plan.py tests/test_visual_relevance.py`
  - `start_stepwise_hpsl_video_workflow("gemini")` created project `7601de0c2876`.
  - `continue_stepwise_hpsl_video_workflow("7601de0c2876")` generated 6 draft sentences.
  - A second `continue` applied the script and generated 6 Flow prompts.
  - `make_hpsl_flow_short_video("gemini")` now returns after source collection with project `2714cba25309`.

## 2026-05-06 HPSL meaning and local browser persistence correction

- Corrected MCP and HPSL prompt language so HPSL always means Hook-Point-Story-Lesson:
  - Korean mapping: 훅, 포인트, 스토리, 교훈.
  - Explicitly forbid expanding HPSL as "High Productivity Scripting Language".
- Updated `scripts/newauto_mcp.py` notes sent into script generation so the stepwise workflow asks for the four HPSL beats directly.
- Updated `app/services/hpsl_script.py` so the LLM prompt also defines HPSL as Hook, Point, Story, Lesson.
- Updated the separate `C:\Users\petbl\local-rag\app\browser_mcp.py` browser MCP:
  - Playwright now uses a shared persistent browser page/profile instead of closing the browser at the end of every tool call.
  - `search_latest_ai_news` now returns deterministic search metadata and top links instead of asking Gemma4 to summarize the search page and potentially call the current date "future".
  - Date-specific searches now use Bing News and add `AI` to ambiguous topics such as `gemini`, avoiding horoscope/zodiac results where possible.
- Verification:
  - `C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile app\browser_mcp.py app\web_agent.py`
  - `python -m compileall scripts\newauto_mcp.py app\services\hpsl_script.py`
  - `python -m pytest tests/test_script_compile.py tests/test_source_draft.py tests/test_scene_plan.py tests/test_render_plan.py tests/test_visual_relevance.py`
  - Direct smoke call `search_latest_ai_news("gemini", "2026-05-06")` returned Bing News results with current date `2026-05-06` treated as today.

## 2026-05-06 URL-block fallback for selected news article

- Fixed a failure mode where LM Studio selected a search result URL but the newauto server received HTTP 403 while fetching the article directly.
- `scripts/newauto_mcp.py` now falls back from URL analysis to keyword collection:
  - extracts a query from the blocked URL slug and host;
  - keeps the blocked URL and reason in the source mode report;
  - continues the stepwise workflow instead of failing the MCP tool call.
- Verification:
  - `python -m compileall scripts\newauto_mcp.py`
  - `C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile scripts\newauto_mcp.py`
  - `python -m pytest tests/test_script_compile.py tests/test_source_draft.py tests/test_scene_plan.py tests/test_render_plan.py tests/test_visual_relevance.py`
  - Replayed blocked URL `https://easternherald.com/2026/05/06/google-home-gemini-3-1-update-smart-home-ai/`.
  - Project `606d1e47987f` collected 3 fallback sources, generated 6 HPSL draft sentences, applied the script, and generated 6 Flow prompts.

## 2026-05-06 Legacy MCP start/finish context overflow prevention

- LM Studio still sometimes picked the older `start_hpsl_flow_workflow` and `finish_hpsl_flow_workflow` pair.
- Converted both legacy tools into compatibility wrappers:
  - `start_hpsl_flow_workflow` now delegates to `start_stepwise_hpsl_video_workflow`;
  - `finish_hpsl_flow_workflow` now delegates to `continue_stepwise_hpsl_video_workflow` and advances only one saved step.
- This prevents the old finish tool from waiting through HPSL generation, applying the script, creating all Flow prompts, and returning a large prompt queue in one chat turn.
- MCP instructions now explicitly say the legacy start/finish pair should not be used for new work unless the user names it.
- Verification:
  - `python -m compileall scripts\newauto_mcp.py`
  - `C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile scripts\newauto_mcp.py`
  - `python -m pytest tests/test_script_compile.py tests/test_source_draft.py tests/test_scene_plan.py tests/test_render_plan.py tests/test_visual_relevance.py`
  - Legacy smoke: `start_hpsl_flow_workflow("gemini AI 2026-05-06 latest news")` created project `f68e76bcd242`, then `finish_hpsl_flow_workflow("f68e76bcd242")` generated only the 6-sentence HPSL draft and stopped.

## 2026-05-06 Flow new-project and prompt-submit automation fix

- The legacy `open_flow` MCP tool was opening a normal browser window, while automation requires the dedicated CDP browser profile.
- Updated `open_flow` to call the CDP browser script and advance `flow_auth -> flow_generate` when a stepwise workflow is active.
- Hardened `scripts/flow_browser_automation.py` for the current Flow UI:
  - finds and clicks the real `+ 새 프로젝트` button by DOM text, prioritizing `button/a` over parent `div` containers;
  - detects the Flow custom prompt editor via `contenteditable=true` / `role=textbox`;
  - expands generate button matching to include the bottom-right arrow/send/create controls;
  - expands Korean download menu matching for later asset collection.
- Verification:
  - `python -m compileall scripts\flow_browser_automation.py scripts\newauto_mcp.py`
  - `C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile scripts\flow_browser_automation.py scripts\newauto_mcp.py`
  - Opened Flow CDP project for `87d3136a4e5c`, clicked `+ 새 프로젝트`, filled one Flow prompt, and clicked the generate arrow successfully.

## 2026-05-07 Ui.Vision Flow backend implementation

- Implemented the first code pass from `flow-rpa-alternative-plan.md` so Flow screen operation can move from Playwright/CDP to Ui.Vision RPA while preserving Playwright as a rollback backend.
- Added Flow prompt export endpoints in `app/routers/flow.py`:
  - `GET /api/flow/prompts/{pid}/csv`
  - `GET /api/flow/prompts/{pid}/sentence/{sentence_number}`
  - `POST /api/flow/prompts/{pid}/uivision/prepare`
- Added filename-based Flow asset attach:
  - `POST /api/flow/assets/{pid}/attach-renamed`
  - filenames like `flow_s001_20260507T010000.png` map directly to sentence 1, avoiding timestamp-order mixups after failed retries.
- Updated `scripts/newauto_mcp.py`:
  - default `FLOW_AUTOMATION_BACKEND=uivision`;
  - `FLOW_MODE=uivision` instructions now prefer `prepare_uivision_flow_batch` and `attach_renamed_flow_downloads`;
  - stepwise `flow_auth`, `flow_generate`, and `flow_download` stages branch across `uivision`, `playwright`, and `assisted`;
  - added MCP tools `prepare_uivision_flow_batch` and `attach_renamed_flow_downloads`.
- Added `uivision/README.md` and folder placeholders for macro/image/csv/log storage, including XRun marker examples.
- Cleaned related TypedDict typing in `flow_prompting.py`, `image_prompting.py`, and MCP stdout/int handling so the changed files pass mypy without `Any`/`unknown` additions.
- Verification:
  - `python -m py_compile app\routers\flow.py app\services\flow_prompting.py app\services\image_prompting.py scripts\newauto_mcp.py tests\test_flow_uivision.py`
  - `python -m mypy app\routers\flow.py scripts\newauto_mcp.py tests\test_flow_uivision.py`
  - `python -m pytest tests\test_flow_uivision.py tests\test_script_compile.py tests\test_source_draft.py tests\test_scene_plan.py tests\test_render_plan.py tests\test_visual_relevance.py`
  - `npm run typecheck:frontend`
## 2026-05-07 Ui.Vision/Flow 실제 조작 검증

- Ui.Vision Chrome 확장 `9.5.9`와 Windows XModules `3.2.3` 설치가 확인됐다.
- XModules 하드드라이브 저장소는 `C:\Users\petbl\Desktop\uivision`이며, 매크로 JSON은 `macros` 폴더에 둘 수 있다.
- 공식 Ui.Vision 문서와 포럼 기준으로 하드드라이브 저장소는 XModules의 FileAccess 기능을 사용하고, command-line API는 `storage=xfile`로 파일 시스템 매크로를 찾을 수 있다.
- Flow 자동화는 당장 Playwright/CDP보다 화면 조작 좌표 기반이 안정적이었다. Flow 인증 후 생성 화면에서 입력창에 prompt를 붙여넣고, 하단 우측 화살표를 누른 뒤, 결과 상세 화면 상단 다운로드 아이콘 -> `1K 원본 크기`를 누르면 무료 다운로드가 가능했다.
- 프로젝트 `fc7439ddbb12`에서 6개 문장 모두 Flow 이미지 생성, 다운로드, `/api/flow/assets/{pid}/attach-local` 연결까지 완료했다.
- 같은 좌표 기반 절차를 `scripts/flow_desktop_control.py`로 분리했다. 인증된 Flow 창이 떠 있는 상태에서 sentence 번호별 prompt TXT를 붙여넣고, 생성 후 1K 다운로드 및 attach-local까지 처리한다.
- 다음 구조 변경 방향: 이 검증된 화면 절차를 Ui.Vision 단건 매크로로 녹화/JSON화하고, 다운로드 직후 파일명을 `flow_sNNN_*`로 바꾸는 XRun 단계를 붙인다.
## 2026-05-07 LM Studio Flow timeout root cause

- Flow 로그인/인증은 완료되어도 LM Studio MCP가 계속 멈추는 원인은 인증이 아니라 동기식 대기 구조였다.
- Flow 이미지 1장은 45~80초가 걸릴 수 있고, 이 시간을 MCP tool call 안에서 기다리면 LM Studio가 timeout을 내기 쉽다.
- `cb505a7a5358` 상태는 `flow_generate`였고, 프롬프트 파일은 준비되어 있었으며 실제 Flow 이미지는 생성됐다. 실패 지점은 생성 후 결과 카드 열기/다운로드/attach였다.
- `scripts/flow_desktop_control.py`에서 새 다운로드가 없을 때 예전 다운로드 파일을 fallback으로 붙일 수 있는 위험한 경로를 제거했다.
- Flow prompt는 한국어 narration을 직접 포함하지 않고 영어 장면 설명만 포함하도록 `flow_prompting.py`를 바꿨다. 한국어 대본은 `script.txt`와 `hpsl_script.json`에 보존한다.
- 다음 구조 변경은 `flow_generate`를 생성 클릭 즉시 반환 단계로 나누고, `flow_wait_sentence` 단계에서 다운로드/attach만 수행하는 1문장 2단계 방식이다.

## 2026-05-07 Flow timeout recovery review 반영

- `lmstudio-flow-timeout-recovery-plan-review.md` 검토 결과 기존 원인 분석은 타당하지만, 아직 코드에 없는 `flow_wait_sentence` 단계가 timeout 해결의 필수 항목으로 확인됐다.
- 계획서를 `click_generate`와 `download_and_attach` 분리 중심으로 업데이트했다.
- 추가 반영 항목:
  - `.crdownload` 감시와 파일 크기 안정화 polling;
  - attach 실패 시 `pending_attach_{N}.json` 저장;
  - Edge/Chromium Flow 창 탐지;
  - 좌표 클릭 전후 스크린샷 및 실패 응답에 경로 포함;
  - `flow_wait_sentence` 호출 시 prompt 재입력 없이 다운로드/attach만 수행.
- 우선순위는 `flow_generate`/`flow_wait_sentence` 분리 -> desktop control 모드 분리 -> 다운로드 polling -> pending attach 순서로 조정했다.

## 2026-05-07 Flow timeout recovery 구현

- `scripts/newauto_mcp.py`의 Ui.Vision `flow_generate` 경로를 변경해 Generate 클릭만 실행한 뒤 `next_step = flow_wait_sentence`로 저장하도록 했다.
- 새 `flow_wait_sentence` 단계는 기존 prompt를 다시 입력하지 않고, 생성 결과 카드 열기 -> 1K 다운로드 -> 새 파일 감지 -> attach만 수행한다.
- `scripts/flow_desktop_control.py`는 `--mode click-generate`와 `--mode download-attach`로 분리했다. 구형 `generate-one` 모드는 호환용으로 남겼지만 내부적으로 두 단계를 순서대로 호출한다.
- 다운로드 감지는 새 파일명, 허용 확장자, `.crdownload` 제외, 파일 크기 2회 안정화 조건을 사용한다.
- attach 실패 시 `storage/projects/{pid}/uivision/pending_attach_{NNN}.json`을 저장하고, 다음 `flow_wait_sentence` 호출에서 Flow 재생성 없이 attach만 재시도하도록 했다.
- Flow 창 탐지는 Chrome뿐 아니라 Edge/Chromium 제목도 허용한다.
- Generate/Download 클릭 전후 스크린샷을 `storage/flow_desktop_screenshots`에 저장해 실패 지점을 확인할 수 있게 했다.
- LM Studio가 직접 `open_flow()`를 호출하는 경우에도 Ui.Vision 모드에서는 CDP/Playwright open을 기다리지 않고 `webbrowser.open(FLOW_URL)`만 실행한 뒤 즉시 반환하도록 변경했다. 이 경로가 남아 있으면 인증은 이미 끝났는데도 `open_flow` tool call timeout이 발생한다.

## 2026-05-07 Source collection fallback recovery

- LM Studio의 `make_hpsl_flow_short_video`가 자료 수집 단계에서 `HTTP 500 Internal Server Error`로 실패하는 경로를 점검했다.
- `app.services.source_research.collect_sources_from_keyword()`에 무료 DuckDuckGo HTML 검색 fallback을 추가했다. Brave API 키가 없거나 Brave 검색 호출이 HTTP/네트워크 오류를 내면 DuckDuckGo HTML 결과를 파싱한다.
- fallback 결과도 기존 keyword cache에 저장해 같은 키워드 재시도 시 검색 호출을 줄인다.
- `scripts.newauto_mcp.start_stepwise_hpsl_video_workflow()`는 자료 수집 실패 시 tool call 자체를 실패시키지 않고 `next_step=source_collect` 상태를 저장한다.
- `continue_stepwise_hpsl_video_workflow()`에 `source_collect` 재시도 단계를 추가해 사용자가 `진행`을 보내면 자료 수집부터 다시 시도할 수 있게 했다.

## 2026-05-07 LM Studio date filter correction

- Gemma4가 `2026-05-06 이후`를 미래 날짜로 오판하고 도구 호출 전에 거절하는 문제가 확인됐다.
- MCP instructions에 현재 로컬 날짜와 전날 날짜를 명시하고, `on or before current date`는 미래가 아니며 `since/after YYYY-MM-DD` 날짜 필터는 workflow tool로 넘기라고 강화했다.
- `start_stepwise_hpsl_video_workflow`와 `make_hpsl_flow_short_video` docstring도 날짜 판단으로 거절하지 말고 전체 요청 문자열을 `keyword_or_url`로 전달하도록 수정했다.

## 2026-05-07 Flow direct-control timeout fix

- 직접 Flow 창을 제어해 LM Studio MCP 경로의 실패 지점을 재현했다. 원인은 단일 timeout이 아니라 여러 Flow 창 선택 오류, 작은 창 기준 고정 좌표, 상세 이미지 화면에서 다음 prompt를 입력하는 상태 오류, Windows 한글/깨진 파일명으로 인한 stale 다운로드 오인으로 분리됐다.
- `scripts/flow_desktop_control.py`는 가장 큰 Flow Chrome/Edge/Chromium 창을 선택하고, prompt 입력/Generate/download/1K 메뉴 클릭을 활성 Flow 창 크기 기준 상대 좌표로 수행한다.
- Generate 전에 현재 Chrome URL을 확인해 `/edit/` 또는 `/scene/` 상세 화면이면 프로젝트 prompt 화면으로 복귀한다. 이로써 다음 문장이 기존 이미지 수정 prompt에 들어가는 문제를 줄였다.
- ASCII Flow prompt는 직접 타이핑하고 비 ASCII만 클립보드 fallback을 사용한다. Flow 화면에서 `Ctrl+V`가 "클립보드 항목 없음" 토스트를 만드는 실패를 줄이기 위한 변경이다.
- 다운로드 단계는 전달받은 `downloads_before`뿐 아니라 다운로드 시작 시점의 현재 Downloads 파일명을 항상 기준선에 합친다. 파일명이 mojibake로 달라져도 오래된 다운로드를 새 파일로 착각하지 않게 됐다.
- 프로젝트 `ad246c22458f`에서 LM Studio MCP가 호출하는 `continue_stepwise_hpsl_video_workflow()` 함수 경로로 검증했다. 1번 문장 download/attach 성공 후 2번 문장에서 stale 파일 오인을 발견했고, 수정 후 새 파일 `Narration_language_Korean_202605070348.jpeg`가 2번 문장에 정상 attach됐다.

## 2026-05-07 LM Studio MCP runtime mismatch diagnosis

- LM Studio에서 `continue_stepwise_hpsl_video_workflow`가 여전히 generic timeout 답변을 내는 문제를 조사했다.
- 현재 `scripts/newauto_mcp.py`에는 사용자가 본 "최종 단계인 Flow 이미지/영상 생성 과정에서 시간 초과" 문구가 존재하지 않는다. 따라서 최신 MCP 함수 반환이 아니라 stale MCP, MCP transport failure 후 Gemma4 요약, 또는 다른 MCP 설정을 의심해야 한다.
- Windows process list에서 `scripts\newauto_mcp.py` 프로세스가 확인되지 않았다. LM Studio의 tool 목록이 보여도 실제 최신 stdio MCP 프로세스가 살아 있는지 별도 검증이 필요하다.
- `127.0.0.1:9001` listener는 `run-newauto-9001.cmd`가 기대하는 `omnivoice_env`가 아니라 Python 3.10 프로세스가 소유하고 있었다. MCP와 API 서버 runtime이 섞이면 최신 코드/의존성/encoding 진단이 불안정해진다.
- 프로젝트 `ad246c22458f` 상태는 `next_step=flow_generate`, coverage `2/6`, missing `[3,4,5,6]`이다. 올바른 다음 동작은 3번 문장 Generate 클릭이며, "최종 렌더링 timeout"이 아니다.
- 대응 계획은 `lmstudio-mcp-flow-runtime-diagnosis-plan.md`로 작성했다. 최우선은 `diagnose_newauto_runtime` MCP tool을 추가해 LM Studio 내부에서 MCP commit, PID, Python executable, 9001 server PID, stepwise state, coverage를 직접 확인하게 만드는 것이다.
