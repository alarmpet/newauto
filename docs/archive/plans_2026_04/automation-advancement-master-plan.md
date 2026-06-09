## 2026-04-27 Implementation Update

- Visual relevance Phase 5 preflight/render gate is now implemented:
  - `visual_relevance` validation now checks prompt-manifest linkage, not only sentence hash linkage
  - render/preflight now fails early for:
    - `IMAGE_PROMPT_MANIFEST_MISSING`
    - `IMAGE_VISUAL_BRIEF_MISSING`
    - `IMAGE_PROMPT_MUST_SHOW_MISSING`
    - `IMAGE_SENTENCE_HASH_MISMATCH`
  - batch queue items now preserve `sentence_hash`, and imported generated mappings preserve `manifest_sentence_hash`
  - this closes the gap where a queued image job could finish after the script changed and still slip into final render
- Current visual relevance track status:
  - done: Phase 0 stale media guard
  - done: Phase 1 Korean keyword/fixture cleanup
  - done: Phase 2 VisualBrief generation
  - done: Phase 3 Prompt Compiler V2
  - done: Phase 5 render/preflight relevance gate
  - done: Phase 6a sentence-level status display
  - done: Phase 4 candidate generation/selection foundation
  - next: Phase 6b candidate detail panel and selection UX
- Visual relevance recovery plan added after reviewing the latest Korean Stickfigures sample:
  - see `visual-relevance-recovery-plan.md`
  - root cause is not simply LoRA strength; generated images were not reliably tied to the active sentence/script
  - the latest final sample reused images from older batches, so Korean narration could be correct while visuals stayed off-context
  - next priority is `sentence_hash`-based media validation, UTF-8 keyword fixture cleanup, structured `VisualBrief`, prompt compiler v2, and candidate selection before render
- Visual relevance Phase 0 emergency guard is now implemented:
  - generated ComfyUI image mappings store sentence text/hash metadata
  - scene plan ignores stale generated mappings
  - preflight exposes `visual_relevance`
  - render fails before FFmpeg if `comfyui_auto` generated images do not match current script sentences
  - verified with typecheck and targeted image/scene/render-plan tests
- Visual relevance Phase 1 keyword cleanup is now implemented:
  - `image_prompting.py` now has clean UTF-8 Korean keyword mappings for concrete daily-script concepts
  - `run_stickman_lora_batch.py` no longer ships corrupted Korean sample sentences
  - prompt suggestions include `sentence_hash` and both Stickfigures trigger hints
  - Korean image prompting tests now cover daily-script keyword images
- Visual relevance Phase 2 brief generation is now implemented:
  - `app/services/visual_brief.py` converts each sentence/prompt-token result into a structured `VisualBrief`
  - prompt suggestions and manifests now carry `visual_brief`
  - each brief keeps `must_show` so later prompt compiler/preflight phases can check whether the image prompt has a concrete target
- Visual relevance Phase 3 prompt compiler is now implemented:
  - `app/services/prompt_compiler.py` builds positive/negative prompts from `VisualBrief`
  - prompt suggestions now expose `missing_must_show`
  - we now have a programmatic compliance check proving whether a compiled prompt actually includes the required object/action tokens
- P1 image prompting is now shifted toward simple, high-readability visuals instead of narration-dump prompts.
- `app/services/image_prompting.py`
  - now builds English SDXL-friendly prompts around a stickman main character
  - extracts intuitive visual tokens from sentence context and core keywords
  - keeps scenes simple, high-contrast, and immediately readable
- `app/services/stickman_reference_library.py`
  - now stores reusable stickman scene templates and external reference metadata
  - prompt generation can tag each scene with a `template_key` and source reference names
  - template coverage now includes `temptation`, `recovery`, `storm_fear`, and `study_focus`
- `app/workflow_templates/comfyui/txt2img_sdxl_stickman_lora.json`
  - added a LoRA-capable SDXL workflow variant using `LoraLoader`
- `app/routers/image_gen.py`
  - manual workflow render/submit and batch-auto queue now accept optional `lora_name` and `lora_strength`
  - when `lora_name` is present, the route switches to the stickman LoRA workflow automatically
- `app/static/index.html` and `app/static/app.js`
  - Step 2 image panel now exposes `LoRA Name` and `LoRA Strength` controls directly in the UI
  - prompt suggestion status now shows the selected `template_key`
- `app/services/model_registry.py`
  - operator/system model status now reports whether a `Stickfigures`-style LoRA file is actually present
- `scripts/install_stickfigures_lora.ps1`
  - resolves model metadata and trigger words from Civitai
  - installs the Stickfigures LoRA when `CIVITAI_API_TOKEN` or `-Token` is available
  - fails with a clear message when the asset requires login and no token is configured
- Stickfigures LoRA is now actually installed and verified:
  - file: `C:\Users\petbl\autotube\ComfyUI\models\loras\Stickfigures-000005.safetensors`
  - a real `txt2img_sdxl_stickman_lora` workflow run succeeded and produced `C:\Users\petbl\autotube\ComfyUI\output\lora_verify_stickman_00001_.png`
- `scripts/run_stickman_lora_batch.py`
  - now creates a sample project, generates a representative LoRA batch, imports outputs into project media, and saves a batch summary for visual review
  - now also supports `--sentence-indices` and `--variants-per-scene` for focused hard-scene sweeps
- `scripts/check_comfyui_smoke.py`
  - now supports `--lora-name` and `--lora-strength`, so smoke verification can cover real LoRA workflows too
- batch image jobs and autopilot image jobs now persist `image_prompts_manifest.json` so generated prompts can be reviewed after queueing
- real manual verification confirmed that UTF-8 file/API input preserves Korean keyword matching, while PowerShell inline Korean input can still distort prompt generation during shell-side diagnostics
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_image_prompting.py tests\test_comfyui_routes.py tests\test_image_worker.py tests\test_autopilot_worker.py -q`
  - real ComfyUI LoRA workflow verification: single image generated successfully with `Stickfigures-000005.safetensors`
  - real representative batch generation: project `b609e71caad0`, imported media count `8`
  - focused hard-scene sweep: project `6eca26cb33be`, scene indices `1,3,6`, `3` variants each

- P0 audio stabilization from the Korean ComfyUI E2E track is now implemented in code.
- `app/services/tts.py`
  - trims long tail silence before saving sentence WAV files
  - keeps `duration=None` behavior and writes timeline gaps directly into `timings.json`
- `app/services/render.py`
  - inserts explicit `0.3s` silence clips between sentence WAV files during concat
  - forces loudnorm output to `24000Hz mono pcm_s16le`
  - blocks render completion if raw vs normalized audio duration drift exceeds `1.0s`
- Render reports now store `audio_raw_duration_sec` and `audio_normalized_duration_sec`.
- Verified with:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_tts_pipeline.py tests\test_render_visual_track.py tests\test_render_report.py -q`

## 2026-04-26 Implementation Update

- Autopilot Phase 1 skeleton is now live in code:
  - DB/status fields
  - control/debug API
  - Step 1 status card and debug surface
- Script-mode execution logic is now also live:
  - dedicated autopilot worker
  - queued claim/heartbeat/recovery
  - script -> TTS -> image -> plan -> preflight -> render orchestration
- URL/keyword execution logic is now also live:
  - source collection
  - source draft worker wait
  - risk gate and auto-apply
  - overwrite/Brave-limit pause handling
- Operator/report aggregation is now also live:
  - render reports keep autopilot job/input/state/phase metadata
  - Operator shows autopilot queue counts and recent autopilot runs
- Runtime stabilization plan added:
  - see `e2e-runtime-stabilization-plan.md`
  - render is verified, but real TTS and ComfyUI generation must be stabilized before the next full autopilot E2E run
- Runtime stabilization plan was revised with the external deep analysis:
  - TTS must move to a `queued -> tts_worker -> resolved OmniVoice subprocess` path
  - Autopilot must stop calling `run_tts_job(pid)` directly
  - worker stdout/stderr must be written to `storage/logs/*.log`
  - `gpu_guard.py` needs atomic acquire/release protection before parallel real E2E runs
  - ComfyUI generation health should read a cached smoke result instead of running heavy smoke inside Operator polling
- Runtime stabilization implementation has now started in code:
  - `POST /tts` is queue-based instead of direct background execution
  - `tts_worker` now claims queued jobs with heartbeat/recovery metadata
  - Autopilot now waits on queued TTS instead of calling `run_tts_job(pid)` directly
  - worker stdout/stderr now land in `storage/logs/*.log`
  - TTS error state now persists as project metadata for operator/debug visibility
- Runtime stabilization implementation is now extended further:
  - `python_runtime.py` resolves OmniVoice Python by real import probing, not directory existence
  - `tts_worker` now launches `scripts/run_tts_job.py` with the resolved OmniVoice Python
  - `/api/system/health` now shows OmniVoice path/import/torch/CUDA status instead of a shallow boolean
  - `tts_error.json` is now written into the project `tts/` directory on failure
- CapCut/OmniVoice enhancement plan added:
  - see `capcut-omnivoice-enhancement-plan.md`
  - next quality track is CapCut-style keyframe/caption/template editing plus OmniVoice batch TTS stabilization
- Phase 2a OmniVoice 1455 mitigation is now implemented and measured:
  - full TTS generation now clears Python/CUDA memory every 5 sentences
  - tts worker resolver failures are persisted to project error state instead of crashing the worker path
  - real 18-sentence TTS measurement passed with about 84.58 seconds of generated audio
  - sample project: `storage/projects/7ee7587d99ca`
- The next acceptance-quality sample must be regenerated under a stricter plan:
  - see `korean-comfyui-e2e-video-plan.md`
  - Korean script only
  - fixed/consistent OmniVoice voice policy
  - ComfyUI-generated images only
  - final output must be a 60-120s `output.mp4`
  - result: sample project `9ee64e214b2c` completed successfully
  - output: `storage/projects/9ee64e214b2c/output.mp4`
  - note: existing `8188` instance and a fresh `8190` instance reproduced `KSampler failed: [Errno 22] Invalid argument`, and the fix was to relaunch ComfyUI with file-backed stderr; detached `8193` smoke succeeded first, then `8188` was relaunched the same way and also passed smoke
- External quality review has been incorporated into the Korean E2E plan:
  - source: `C:\Users\petbl\.gemini\antigravity\brain\dbc65872-79d3-4fb5-9446-d57a5569768d\implementation_plan.md`
  - next quality round is not another basic E2E proof; it is a polish pass for TTS naturalness, image relevance, image resolution, and audio/render guardrails
  - P0: remove forced TTS `duration=7.5`, trim tail silence, add intentional 0.3s sentence gaps, and force loudnorm output to `24000Hz mono pcm_s16le`
  - P1: translate Korean narration into English visual prompts through Ollama/Gemma4 before ComfyUI generation, and store `image_prompts_manifest.json`
  - P1: standardize ComfyUI generation at `1024x576`, raise SDXL workflow steps to 30 where VRAM allows, and block very low-resolution generated media before render
  - P2: add render quality metrics for audio duration drift, silence ratio, generated image size, and prompt manifest linkage
- Remaining autopilot work is now runtime stabilization, deeper recovery polish, and retry/quality policies.

# Automation Advancement Master Plan

상태: `[Revised Draft]`

목표: 현재 자동화 프로그램을 **자료 수집 → 대본 생성 → TTS → 이미지 생성 → 렌더 → 업로드/검수**까지 안정적으로 이어지는 제작 파이프라인으로 고도화한다.

이 문서는 기존 구현을 재사용하는 것을 최우선으로 한다. 각 단계는 “이미 있음”과 “추가할 것”을 분리해 재구현 위험을 줄인다.

## 핵심 수정 요약

이번 개정에서 반영한 가장 큰 변경:

- 각 Phase 첫머리에 `이미 있음 ↔ 추가할 것` 표를 추가한다.
- ComfyUI 이미지 생성은 `P2` 가 아니라 `P1` 로 격상한다.
- GPU/VRAM stewardship 를 마스터 정책으로 통합한다.
- `storage/brave_usage.json` 과 새 usage schema 충돌을 마이그레이션 항목으로 명시한다.
- ComfyUI workflow node id 하드코딩 대신 placeholder/token 기반 injection 을 기본으로 한다.
- `scene_plan` 과 `render_plan` 의 책임을 분리한다.
- Skills 경로는 현재 Codex 환경 기준으로 `.codex/skills` 를 기본으로 두고, Claude Code 사용 시 `.claude/skills` mirror 를 별도 옵션으로 둔다.

## 현재 자산 요약

| 영역 | 이미 있음 | 추가할 것 |
|---|---|---|
| Backend | FastAPI, SQLite WAL, router/service 구조 | tool/model/usage registry |
| Worker | `source_draft_worker`, `render_worker`, heartbeat/recover 패턴 | `image_worker`, GPU lock 통합 |
| Source | URL/keyword 입력, Brave 월 2000 limit, cache, Ollama draft | brief/outline/rewrite loop, source ledger |
| Script safety | `script_safety.py` copy-risk, long quote 검사 | threshold 초과 자동 재작성 |
| TTS | preset, preview, seed lock, region speed override | 구조 기반 추천, pause/intensity metadata |
| Render | `render_plan` 컬럼/type, FFmpeg render, progress | render_plan 실행 고도화, quality report |
| Visual mode | `VisualSourceMode = upload_only/hybrid/comfyui_auto` | UI 연결, ComfyUI worker |
| System health | `app/services/system_health.py`, `/api/system/health` | operator dashboard 로 확장 |

## 마스터 GPU Stewardship

8GB VRAM 환경에서 Ollama, OmniVoice TTS, ComfyUI, faster-whisper 가 동시에 올라오면 충돌 가능성이 높다. 모든 GPU-heavy 작업은 아래 정책을 공유한다.

| 작업 | 예상 VRAM | Acquire 전 | 실행 중 | Release 후 |
|---|---:|---|---|---|
| Source draft / Ollama | 5-6GB | TTS/ComfyUI/image worker 대기, 필요 시 TTS unload | heartbeat 유지, cold start phase 표시 | `OllamaClient.unload()` |
| TTS / OmniVoice | 약 2GB | Ollama unload 요청, image worker 대기 | preview/full TTS lock 유지 | 필요 시 `tts.unload_model()` |
| ComfyUI image gen | 5-7GB | Ollama unload, TTS full job 대기 | scene 단위 queue, job timeout | 가능하면 workflow 종료 후 idle 상태 유지 또는 unload 옵션 |
| faster-whisper | 1-4GB | TTS/ComfyUI 와 동시 실행 금지 | batch 단위 실행 | model 객체 해제 |
| Render / FFmpeg | GPU 미사용 기본 | GPU lock 불필요, 단 NVENC 사용 시 필요 | CPU/IO 중심 | 없음 |

구현 계획:

- `app/services/gpu_guard.py` 추가
  - `acquire(resource, owner, timeout_sec)`
  - `release(owner)`
  - `current_owner()`
- worker 는 DB heartbeat 와 별개로 GPU guard 를 사용한다.
- `source_draft_worker`, `image_worker`, TTS route/job 진입점에 acquire/release 를 붙인다.
- Render 는 기본적으로 GPU guard 대상이 아니지만, NVENC 옵션 도입 시 guard 대상에 포함한다.
- UI에는 “GPU 사용 중: 대본 생성 / 이미지 생성 / TTS” 처럼 한글로 표시한다.

권장 실행 순서:

```text
Source draft: acquire ollama -> generate -> unload -> release
TTS: acquire tts -> synthesize -> optional unload -> release
ComfyUI: acquire comfyui -> generate scenes -> release
Render: no gpu lock by default -> ffmpeg
```

## Usage/Quota Schema 통합

현재 `BRAVE_USAGE_PATH = storage/brave_usage.json` 이 존재한다. 새 plan 의 `storage/usage/brave_search.json` 과 공존하면 혼란이 생기므로 마이그레이션을 명확히 한다.

결정:

- 단기: 기존 `storage/brave_usage.json` 유지
- 중기: `storage/usage/providers.json` 로 통합
- 마이그레이션 시 기존 파일을 읽어 새 schema 로 옮긴 뒤, 기존 파일은 backward-compatible read only 로 둔다.

통합 schema:

```json
{
  "provider": "brave_search",
  "day_count": 3,
  "month_count": 120,
  "day_limit": null,
  "month_limit": 2000,
  "last_day_reset": "2026-04-26",
  "last_month_reset": "2026-04"
}
```

적용 대상:

- `brave_search`: 월 2000
- `comfyui`: 일/월 생성 수
- `ollama`: 일/월 job 수, token 추정치
- `external_download`: 일/월 다운로드 수
- `youtube_upload`: 일/월 업로드 수

## Phase 0 — 운영 안전장치

목표: 새 기능을 붙이기 전에 비용, GPU, 설치 상태, 실패 복구를 한 곳에서 관리한다.

- `[완료]` `usage_registry.py` 추가 및 Brave legacy usage 호환 시작
- `[완료]` `tool_registry.py` + `/api/system/tools` 기본 노출
- `[완료]` `gpu_guard.py` + `/api/system/operator` 기본 GPU 상태 노출
- `[완료]` operator queue/status 기본 집계 추가
- `[완료]` source draft worker/TTS preview/full job 에 GPU acquire/release 연결
- `[완료]` Step 4 Operator 버튼/패널에서 queue/tool/usage/GPU 상태 기본 표시
- `[완료]` `model_registry.py` 추가 및 operator models 상태 표시
- `[완료]` Operator live/static polling 분리: 프로젝트 상태 1.5초, operator 상태 30초

| 이미 있음 | 추가할 것 |
|---|---|
| `app/services/system_health.py` | `tool_registry.py`, `model_registry.py`, `gpu_guard.py` |
| `/api/system/health` | `/api/system/tools`, `/api/system/operator` |
| `storage/brave_usage.json` | unified usage schema migration |
| worker heartbeat/recover 패턴 | GPU owner/status 표시 |

작업:

- `app/services/tool_registry.py`
  - `ollama`, `comfyui`, `ffmpeg`, `faster-whisper`, `yt-dlp`, `playwright-mcp` 상태 점검
- `app/services/model_registry.py`
  - 모델 경로, source URL, license, hash, enabled flag 관리
- `app/services/gpu_guard.py`
  - GPU-heavy job 단일 실행 정책
- `app/services/usage_registry.py`
  - provider별 day/month usage 통합
- `app/routers/system.py`
  - 기존 health route 유지 + operator/tool endpoint 확장

테스트:

- 미설치 도구는 `error` 가 아니라 `unavailable`
- usage limit 초과 시 enqueue 차단
- GPU guard 가 동시 acquire 를 막음
- 기존 `storage/brave_usage.json` 을 읽어 새 schema 로 변환 가능

## Phase 1A — ComfyUI 이미지 생성 파이프라인

목표: 이미 존재하는 `VisualSourceMode` 를 실제 제품 기능으로 연결하고, 자동 영상화 가치를 빠르게 실현한다.

우선순위: `[P1]`  
이유: 사용자 환경에 ComfyUI 설치가 이미 확인된 plan 이 있고, type 시스템에 `comfyui_auto/hybrid` 가 존재한다.

- `[완료]` `comfyui_workflows.py` placeholder injection + 템플릿 로더 추가
- `[완료]` `comfyui_client.py` `/prompt` + `/history` 클라이언트 추가
- `[완료]` 기본 SDXL 템플릿 `txt2img_sdxl_basic.json` 추가
- `[완료]` `/api/projects/{pid}/comfyui/workflow/render|submit` 최소 API 추가
- `[완료]` `/api/projects/{pid}/comfyui/history/{prompt_id}|import` history 조회 및 media import API 추가
- `[남음]` `image_worker.py` 큐/heartbeat 연결
- `[완료]` 생성 결과를 media/import 및 `body_image_mappings` 에 연결
- `[남음]` UI에서 visual source mode / prompt / submit 흐름 연결

| 이미 있음 | 추가할 것 |
|---|---|
| `VisualSourceMode = upload_only/hybrid/comfyui_auto` | UI에서 mode 선택/상태 표시 |
| render fallback 구조 | generated media import |
| worker 패턴 | `image_worker.py` |
| `render_plan` type/컬럼 일부 | scene image 결과를 render_plan 에 연결 |

### ComfyUI 연결 계층

추가 파일:

- `app/services/comfyui_client.py`
- `app/services/comfyui_workflows.py`
- `app/workers/image_worker.py`
- `app/routers/image_gen.py`
- `tests/test_comfyui_client.py`
- `tests/test_image_worker.py`

설정:

- `COMFYUI_BASE_URL=http://127.0.0.1:8188`
- `COMFYUI_ENABLED=0` 기본값
- `COMFYUI_MAX_JOBS_PER_DAY=100`
- `COMFYUI_TIMEOUT_SEC=900`
- `COMFYUI_INSTALL_DIR=C:\Users\petbl\autotube\ComfyUI` 는 자동 탐지 후보로만 사용

### Workflow Template 정책

node id 하드코딩은 금지한다.

금지 예:

```json
{
  "positive_node": "6",
  "negative_node": "7"
}
```

권장:

- workflow JSON 안에 `__POSITIVE_PROMPT__`, `__NEGATIVE_PROMPT__`, `__SEED__`, `__WIDTH__`, `__HEIGHT__` placeholder 를 직접 넣는다.
- injection 은 string replacement 후 JSON parse 로 검증한다.
- placeholder 가 없으면 `class_type` 과 input field 로 후보를 찾되, 후보가 2개 이상이면 error 로 중단한다.

### Throughput / VRAM 추정

8GB VRAM 기준 보수 추정:

| Workflow | 해상도 | 예상 속도 | OOM 위험 | 기본값 |
|---|---:|---:|---|---|
| SDXL basic | 1024x576 | 30-90초/장 | 중간 | landscape |
| SDXL shorts | 576x1024 | 30-90초/장 | 중간 | shorts |
| Flux 계열 | 1024급 | 1-4분/장 | 높음 | 기본 off |
| upscale | 2x | 20-120초/장 | 중간 | 선택 |

정책:

- 첫 구현은 SDXL basic 1장씩 순차 생성
- scene 8개면 약 4-12분을 예상
- OOM 1회 발생 시 batch/해상도 자동 낮춤
- 2회 연속 실패 시 stock/upload fallback 으로 전환

## Phase 1B — 자료 수집/대본 생성 고도화

목표: 기사 URL/키워드에서 바로 초안으로 가는 흐름을 brief/outline/rewrite loop 로 안정화한다.

| 이미 있음 | 추가할 것 |
|---|---|
| `source_fetch.py`, `source_research.py` | source brief/claim ledger |
| `source_draft.py` | outline 단계 |
| `llm_ollama.py` | rewrite loop 에 재사용 |
| `script_safety.py` | threshold 초과 시 자동 재작성 |
| `script_compile.py` | TTS-ready sentence 연결 |
| `source_draft_worker.py` | phase 세분화: brief/outline/rewrite |

### Source Brief

`source_draft_sources` 와 `source_draft_fact_notes` 를 확장한다.

```json
{
  "source_brief": {
    "topic": "핵심 주제",
    "angle": "영상 관점",
    "facts": [
      {
        "claim": "검증 가능한 주장",
        "source_id": "src_1",
        "confidence": "high",
        "copyright_risk": "low"
      }
    ],
    "open_questions": [],
    "avoid_claims": []
  }
}
```

### 생성 파이프라인

```text
source/facts -> brief -> outline -> script -> safety check -> rewrite if needed -> compile
```

정책:

- copy-risk threshold 초과 시 최대 2회 자동 rewrite
- 긴 원문 겹침이 남으면 `needs_review`
- `hook/point/story/lesson` 은 outline 단계부터 반영
- `Apply` 는 계속 수동 버튼으로 유지

### Apply 후 chain 정책

기본값:

- Source draft 생성
- 사용자가 확인
- `Apply` 수동 클릭
- TTS 수동 클릭
- Image Gen 수동 클릭
- Render 수동 클릭

자동 chain:

- Phase 8 Operator 옵션으로만 제공
- 기본 off
- 디버깅과 제어권을 위해 각 단계 재시도 버튼 유지

## Phase 1C — Scene Plan

목표: 대본을 이미지 생성과 렌더가 이해할 수 있는 장면 의도로 바꾼다.

| 이미 있음 | 추가할 것 |
|---|---|
| compiled sentences / regional sentences | `scene_plan` service/type/저장소 |
| `VisualSourceMode` | mode별 scene generation 정책 |
| Source regenerate mode | scene style preset 연결 |

정의:

- `scene_plan` = 의도
- `render_plan` = 실행

`scene_plan` 예:

```json
{
  "version": 1,
  "scenes": [
    {
      "idx": 1,
      "duration_sec": 8.5,
      "visual_intent": "긴장감 있는 뉴스풍 도입",
      "prompt_ko": "...",
      "prompt_en": "...",
      "style": "documentary realistic",
      "avoid": ["text", "logo", "watermark"],
      "source_sentence_ids": [1, 2]
    }
  ]
}
```

구현:

- `app/services/scene_plan.py`
- `app/types.py` 에 `ScenePlan`
- `app/db.py` 에 `scene_plan` 컬럼 추가
- `app/static/app.js` 에 scene preview

## Phase 2 — Render Plan / Render 고도화

목표: 이미 존재하는 `render_plan` 을 실제 렌더 실행 계획으로 발전시킨다.

| 이미 있음 | 추가할 것 |
|---|---|
| `app/types.py` `RenderPlan` | media_path/motion/caption/effect 확장 |
| `app/db.py` `render_plan` 컬럼 | render_plan builder |
| `app/services/render.py` | plan 기반 visual build |
| render progress/phase | render quality report |

`render_plan` 정의:

- `render_plan` = 실행
- 어떤 파일을 몇 초부터 몇 초까지, 어떤 motion/effect/caption style 로 사용할지 기록

예:

```json
{
  "version": 2,
  "format": "shorts",
  "fps": 30,
  "segments": [
    {
      "media_path": "generated/scene_001.png",
      "start": 0.0,
      "end": 8.5,
      "motion": "slow_zoom_in",
      "caption_style": "emphasis",
      "effect": "none"
    }
  ]
}
```

추가 작업:

- `app/services/render_plan.py`
- `scene_plan + image_manifest + timings -> render_plan`
- 기존 media 순서 렌더는 fallback 으로 유지
- `render_report.json`
  - 길이, loudness, 자막 누락, scene duration, 사용 이미지 수, ffmpeg 로그 요약

## Phase 3 — TTS 고도화

목표: 대본 구조와 화자 스타일을 더 잘 연결한다.

| 이미 있음 | 추가할 것 |
|---|---|
| TTS preset catalog | source mode 기반 preset 추천 |
| preview lock / seed lock | region별 pause/intensity metadata |
| `script_compile.py` regional sentences | hook/body/lesson 구간별 속도 정책 |
| TTS manifest | source mode, region override 기록 |

작업:

- `hook/point/story/lesson` 에 따른 TTS 추천
- 도입/본문/마무리별 pause/speed 가이드
- TTS 예상 길이와 목표 길이 차이 표시
- 모델 미지원 emotion 은 속도/쉼표/문장 분할로 우회

## Phase 4 — Operator Dashboard

목표: 사용자가 작업 상태, 리소스, quota, 최근 오류를 한 화면에서 확인한다.

| 이미 있음 | 추가할 것 |
|---|---|
| `/api/system/health` | `/api/system/operator` |
| project status polling | live/static polling 분리 |
| worker phase/log | worker log summary |
| Brave usage | unified quota cards |

Polling 정책:

- live: 작업 상태, 현재 phase, progress → 1.5초
- static: tool status, quota, CPU/RAM/GPU, 버전 → 30초
- worker log tail → 사용자가 패널을 열었을 때만 갱신

학습 루프:

- 최근 N개 영상의 회귀 지표 저장
  - 자막 누락 횟수
  - 렌더 실패율
  - ComfyUI fallback 비율
  - copy-risk rewrite 발생률
- 문제가 반복되면 다음 작업의 검수 강도를 자동 상향

예:

```text
최근 5개 영상 중 자막 누락 3건 -> render preflight strict mode 자동 추천
최근 3개 이미지 작업 중 OOM 2건 -> 기본 해상도 한 단계 낮춤 추천
```

## Phase 5 — Skills 운영 체계

목표: 반복되는 개발/검수 작업을 skill 로 분리한다.

| 이미 있음 | 추가할 것 |
|---|---|
| 현재 세션은 Codex skill 체계 사용 가능 | newauto 전용 local skill |
| 사용자가 Claude Code 환경을 병행할 가능성 | `.claude/skills` mirror 옵션 |

경로 정책:

- 현재 Codex 기준: `$CODEX_HOME/skills` 또는 `.codex/skills`
- Claude Code 로 실행하는 별도 환경이면 `.claude/skills` 에 동일 내용을 mirror
- 제품 런타임은 skill 에 의존하지 않는다.

추천 skills:

- `newauto-source-strategist`
- `newauto-comfy-workflow`
- `newauto-render-qa`
- `newauto-ui-polish`
- `newauto-release-operator`

## Phase 6 — MCP 활용

목표: MCP 는 제품 런타임 의존성이 아니라 개발/검수/운영 자동화에 우선 사용한다.

| 이미 있음 | 추가할 것 |
|---|---|
| GitHub connector 사용 가능 | release/tag/vendor 검증 workflow |
| 브라우저 검수가 필요함 | Playwright MCP |
| Brave API wrapper | MCP는 개발 리서치 보조로만 |

우선순위:

- Playwright MCP: 실제 UI 클릭/스크린샷 검수
- GitHub MCP: vendor 버전 추적, issue/PR 정리
- Brave/Search MCP: 제품 기능이 아니라 조사 보조
- Filesystem MCP: 큰 asset/model registry 탐색

주의:

- 제품 서버가 MCP 를 직접 호출하지 않는다.
- 제품 기능은 Python service layer 로 구현한다.

## Phase 7 — GitHub 직접 다운로드 / Vendor 관리

목표: 외부 오픈소스 도구를 안전하게 설치/추적한다.

| 이미 있음 | 추가할 것 |
|---|---|
| 수동 설치 가능 | vendor manifest |
| GitHub connector | tag/commit/license/checksum 검증 |
| tool status 필요 | `check_vendor_tools.py` |

후보:

- ComfyUI
- ComfyUI-Manager
- faster-whisper
- WhisperX
- yt-dlp
- rembg/background removal 계열
- Playwright MCP

구현:

- `scripts/vendor_tool.py`
- `scripts/check_vendor_tools.py`
- `storage/vendor_manifest.json`

정책:

- tag/commit 고정
- SHA256 저장
- license unknown 은 실행 제한
- GPL 계열은 별도 표시
- yt-dlp 는 합법적 사용 범위 안내 필요

## 의존성 그래프

직선 순서가 아니라 병렬 가능한 구조로 진행한다.

```text
Phase 0 운영 안전장치
  -> Phase 1A ComfyUI image gen
  -> Phase 1B Source brief/rewrite
  -> Phase 4 Operator dashboard basic

Phase 1B Source brief/rewrite
  -> Phase 1C Scene plan
  -> Phase 3 TTS metadata

Phase 1A ComfyUI + Phase 1C Scene plan
  -> Phase 2 Render plan

Phase 5 Skills
  -> 모든 Phase 와 병렬

Phase 6 MCP
  -> UI 검수/벤더 검증과 병렬

Phase 7 Vendor
  -> ComfyUI/faster-whisper 확장 전 병렬 준비
```

권장 구현 순서:

1. `[P0]` GPU guard + usage registry + tool status
2. `[P1]` ComfyUI client + workflow placeholder injection
3. `[P1]` image worker + generated media import
4. `[P1]` source brief + outline + rewrite loop
5. `[P1]` scene_plan 생성
6. `[P2]` render_plan builder + render.py 연결
7. `[P2]` render quality report
8. `[P2]` TTS 구조 기반 metadata
9. `[P3]` Operator dashboard live/static 분리
10. `[P3]` Skills 문서화
11. `[P3]` MCP 브라우저 검수 자동화
12. `[P4]` GitHub vendor downloader

## 파일 단위 작업 분해

### 기존 파일 확장

- `app/config.py`
  - ComfyUI path/url/env, usage path migration 설정
- `app/db.py`
  - `scene_plan`, image job state, usage migration helper
- `app/types.py`
  - `ScenePlan`, 확장 `RenderPlan`, `ToolStatus`, `UsageRecord`
- `app/services/llm_ollama.py`
  - rewrite loop 와 model warm/unload 정책 재사용
- `app/services/script_safety.py`
  - needs_review threshold, rewrite trigger reason
- `app/services/script_compile.py`
  - scene/TTS metadata 입력으로 재사용
- `app/services/source_draft.py`
  - brief/outline/rewrite loop
- `app/services/source_research.py`
  - usage registry 연결
- `app/services/render.py`
  - render_plan 기반 visual build
- `app/services/system_health.py`
  - operator/tool status 로 확장
- `app/routers/projects.py`
  - apply 후 수동 chain 유지, scene/image endpoint 연결
- `app/static/index.html`
  - ComfyUI/Image/Operator 패널
- `app/static/app.js`
  - live/static polling 분리, scene/image 상태
- `app/static/style.css`
  - dashboard/scene list/warning badge

### 신규 파일

- `app/services/gpu_guard.py`
- `app/services/usage_registry.py`
- `app/services/tool_registry.py`
- `app/services/model_registry.py`
- `app/services/comfyui_client.py`
- `app/services/comfyui_workflows.py`
- `app/services/scene_plan.py`
- `app/services/render_plan.py`
- `app/workers/image_worker.py`
- `app/routers/image_gen.py`
- `scripts/vendor_tool.py`
- `scripts/check_vendor_tools.py`
- `scripts/export_comfy_workflow_manifest.py`
- `scripts/check_render_output.py`

### 테스트

- `tests/test_gpu_guard.py`
- `tests/test_usage_registry.py`
- `tests/test_tool_registry.py`
- `tests/test_model_registry.py`
- `tests/test_comfyui_client.py`
- `tests/test_comfyui_workflows.py`
- `tests/test_image_worker.py`
- `tests/test_source_brief.py`
- `tests/test_scene_plan.py`
- `tests/test_render_plan.py`
- `tests/test_operator_dashboard.py`

## UI 원칙

- 모든 고급 기능은 한글로 상태, 필요 설치, 비용 가능성을 표시한다.
- ComfyUI 미실행 시 “이미지 생성 불가”가 아니라 “ComfyUI 연결 대기”로 표시한다.
- 대본/Apply/TTS/Image/Render 는 기본 수동 클릭으로 유지한다.
- 자동 chain 은 Operator option 으로만 제공하고 기본 off.
- 리소스/quota 는 30초 단위로 갱신해 dashboard 부담을 줄인다.
- 기능 설명은 길게 쓰지 않고 버튼/상태/경고 옆에 필요한 만큼만 둔다.

## 주요 리스크와 대응

| 리스크 | 대응 |
|---|---|
| 기존 구현 재구현 | 각 Phase 의 `이미 있음 ↔ 추가할 것` 표 기준으로 작업 |
| GPU/VRAM 충돌 | `gpu_guard.py` 와 acquire/release 시퀀스 |
| ComfyUI OOM | SDXL basic 1장 순차, 실패 시 해상도 낮춤, stock fallback |
| workflow node id 변경 | placeholder injection, class_type fallback |
| usage 파일 충돌 | 기존 `storage/brave_usage.json` 유지 후 unified schema migration |
| dashboard 과부하 | live 1.5초 / static 30초 분리 |
| 저작권 유사도 | rewrite loop, needs_review, 긴 quote 차단 |
| skill 경로 혼동 | Codex `.codex/skills`, Claude Code `.claude/skills` mirror 명시 |
| 자동 chain 디버깅 난이도 | 기본 수동, 자동은 Phase 8 옵션 |

## 완료 기준

1. 기존 worker/type/health/render_plan 자산을 재사용하고 중복 구현하지 않는다.
2. GPU-heavy 작업은 모두 acquire/release 정책을 따른다.
3. ComfyUI 가 켜져 있으면 `comfyui_auto/hybrid` 모드에서 scene 이미지가 생성된다.
4. ComfyUI 실패 시 stock/upload fallback 이 작동한다.
5. URL/키워드 입력 후 brief, outline, script, scene_plan 이 생성된다.
6. render_plan 기반 landscape/shorts 출력과 quality report 가 생성된다.
7. Brave 월 2000건 hard limit 과 기존 usage 파일 호환이 유지된다.
8. Operator dashboard 는 live/static polling 을 분리한다.
9. 실제 브라우저에서 Source Assist → Apply → TTS → Image Gen → Render 흐름이 한글 UI로 이해된다.

## 참고 링크

- ComfyUI GitHub: https://github.com/Comfy-Org/ComfyUI
- ComfyUI Workflow JSON: https://comfyuiwiki.com/specs/workflow_json
- ComfyUI API 실행 예시: https://comfyui.nomadoor.net/en/data-utilities/api-run-workflow/
- ComfyUI-Manager GitHub: https://github.com/Comfy-Org/ComfyUI-Manager
- MCP reference servers: https://github.com/modelcontextprotocol/servers
- Playwright MCP: https://github.com/microsoft/playwright-mcp
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- yt-dlp: https://github.com/yt-dlp/yt-dlp

## 2026-04-26 진행 메모

이번 구현 라운드에서 Phase 1A의 UI 연결이 1차 완료됐다.

- 완료:
  - `image_worker.py` 기반 ComfyUI job queue / heartbeat / import
  - Step 2 Media 화면의 `AI Image Gen` 패널
  - `visual_source_mode` 저장 연동
  - ComfyUI prompt/seed/size/sentence index 입력
  - body image 상태/로그/매핑 브라우저 표시
  - source draft / script 기반 ComfyUI 프롬프트 추천 API 및 UI 버튼
  - 시작 문장/개수 기반 multi-scene batch auto enqueue
  - `scene_plan` DB/type/service/API/UI 1차 연결
  - `render_plan` builder/API/UI 1차 연결 및 render 경로 우선 사용
  - `render_plan` segment 연출 메타데이터(`motion/effect/caption_style`) 1차 연결
- 아직 남음:
  - render_plan 메타데이터를 실제 FFmpeg/자막 연출 로직에 더 깊게 반영

## 2026-04-26 마감 실행 계획 링크

남은 작업은 `automation-finish-execution-plan.md`를 기준 문서로 삼는다. 기존 마스터 문서에는 장기 고도화 방향과 완료 이력을 남기고, 실제 마감 실행은 다음 4개 라운드로 분리한다.

1. `render_plan` metadata를 실제 렌더 결과에 반영한다.
2. 이미지 생성/import 완료 후 `scene_plan`과 `render_plan`을 자동 갱신한다.
3. `render_report`와 preflight 품질 게이트를 추가한다.
4. Operator 회귀 지표와 브라우저 smoke 검증으로 운영 마감을 한다.

## 2026-04-26 오토파일럿 계획 링크

대본/URL/키워드 입력 후 `오토파일럿` 버튼으로 최종 렌더까지 자동 진행하는 기능은 `autopilot-end-to-end-render-plan.md`를 기준 문서로 삼는다.

이 계획은 새 렌더 시스템을 만드는 것이 아니라 기존 Source Assist, TTS worker, ComfyUI image worker, scene/render plan, render worker, render report를 하나의 상태 머신으로 묶는 방향이다.

오토파일럿 계획에는 각 단계별 `events.jsonl`, `debug_snapshot.json`, `last_failure.json` 로그를 남겨 실패 phase, 오류 코드, 복구 힌트, 관련 worker 상태를 바로 확인하는 디버깅 요구사항도 포함한다.

추가 검토 결과, 오토파일럿 계획에는 phase별 재진입/skip condition, `plan_refresh`의 scene/render plan build 호출, GPU wait timeout 후 pause, cancel 정책, action hint/retry strategy, user_script 백업 정책도 포함한다.
