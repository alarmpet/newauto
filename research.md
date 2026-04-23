# TUBE FACTORY 스타일 오디오/영상 자동화 앱 리서치

## 개요

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
