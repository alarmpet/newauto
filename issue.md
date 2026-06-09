# NewAuto Studio Workflow 점검 및 개선 계획

Updated: 2026-05-16 KST

## 실제 실행 기준

- Project ID: `324b2eff3737`
- 대본: 전기차 구매, 가성비, LFP/NCM, 한국형 LFP, 전고체 배터리, K-배터리 기술 주권
- 이미지: ComfyUI `sd_xl_base_1.0.safetensors` + LoRA `Stickfigures-000005.safetensors`
- 음성: OmniVoice `omnivoice_env\Scripts\python.exe`, CUDA 사용 가능
- 렌더: NewAuto Studio render worker, landscape `output.mp4`
- YouTube: 업로드하지 않음. 렌더 완료 전제조건까지만 확인

## 최종 실행 결과

- Script: 원문 복구 후 10개 문장으로 정상 분리
- Media: 실제 ComfyUI+LoRA 이미지 10장 생성
- TTS: 실제 OmniVoice 음성 10개 wav 및 timings 생성
- Preflight: 모든 항목 통과
- Render: `storage/projects/324b2eff3737/output.mp4` 생성 완료
- Render report: 59.06초, duration guard 통과, subtitle display cue 23개, render segment 10개
- YouTube: 업로드 호출하지 않음
- 이미지 맥락 품질: 완성본 확인 결과 다수 장면이 문장 핵심키워드와 불일치. 세부 분석과 개선안은 [image-context-quality-plan.md](image-context-quality-plan.md)에 분리 작성.
- 검증: `.\omnivoice_env\Scripts\python.exe -m pytest tests/test_image_prompting.py tests/test_lmstudio_runtime.py tests/test_comfyui_routes.py tests/test_feature_workflow.py -q`
- 결과: 86 passed, 2 warnings

## 반영한 코드 수정

- `app/services/image_prompting.py`
  - 전체 이미지 프롬프트 생성 시 `start_idx/count`를 실제 문장 수로 캡핑.
  - 범위를 넘은 요청이 첫 문장 프롬프트 반복으로 이어지지 않도록 수정.
- `tests/test_image_prompting.py`
  - count 초과 요청이 첫 문장 반복을 만들지 않는 회귀 테스트 추가.
- `app/services/lmstudio_runtime.py`
  - LM Studio `/v1/models` 목록을 로드된 모델로 오인하던 문제를 완화.
  - `lms ps`가 사용 가능하면 실제 로드 상태를 먼저 확인.
- `tests/test_lmstudio_runtime.py`
  - `lms ps`가 "No models are currently loaded"를 반환하면 빈 목록으로 처리하는 테스트 추가.
- `app/services/render.py`
  - render 실패 cleanup 중 Windows 파일 잠금 `PermissionError/WinError 32`가 원래 오류를 덮지 않도록 방어.

## 발견한 문제

### 1. Script

- 실제 첫 실행에서 한글 대본이 `???`로 저장되어 문장 6개로 깨졌다.
- 원인은 PowerShell/프로세스 입력 인코딩 또는 실행 중인 API 런타임의 문자열 전달 경로로 추정된다.
- 조치: 현재 프로젝트는 UTF-8 입력 설정 후 DB 필드를 원문으로 복구했고, 10문장으로 재분리했다.
- 개선: 대본 저장 직후 mojibake 감지, `sentences` 미리보기, 저장 전후 hash 비교를 UI/preflight에 추가한다.

### 2. Media

- 원래 보고된 "전체 이미지 프롬프트가 각각 똑같아 보임" 문제는 count 초과 시 첫 문장으로 되돌아갈 수 있는 코드 구조가 있었다.
- 수정 후 실제 EV/LFP 대본 10문장은 각각 다른 프롬프트로 생성됐다.
- 다만 실제 완성본 검수 결과, 2번 이후 visual plan이 대부분 fallback으로 떨어져 이미지가 대본 맥락과 크게 어긋났다.
- 반영: `ev_battery` 도메인 감지, `storage/visual_vocab/ev_battery.json`, EV battery explainer prompt template, EV fallback 핵심 객체 보존, EV 후보 0.72 미만 retry 기준을 추가했다.
- ComfyUI 첫 시도에서 `KSampler`가 stderr/tqdm flush 문제로 실패했다. ComfyUI를 로그 리다이렉션 방식으로 재시작한 뒤 정상 생성됐다.
- LM Studio unload 경로는 `ok: true`를 반환했지만 실제 모델 목록이 남아 있는 것처럼 판단해 이미지 큐가 409로 막혔다. `lms ps` 기준 감지로 수정했다.
- 이미지 생성 후 0번/1번 mapping이 이전 후보 파일명을 계속 선택해 `media_order`와 불일치했다. 현재 프로젝트는 새 `ev_lfp_real_*` 파일로 동기화했다.
- 후보 품질 점수는 `[0.89, 0.86, 0.59, 0.58, 0.44, 0.54, 0.48, 0.62, 0.53, 0.58]`이고 8개 장면에 retry 권고가 붙었다.
- 개선: 이미지 재생성 시 기존 후보를 선택하더라도 `media_order`와 mapping을 함께 갱신하고, heavy LoRA 경로에서도 낮은 점수 후보에 대한 재시도 옵션을 제공한다.
- 개선: EV/배터리 도메인용 visual planner, LoRA 사용 기준, 낮은 후보 점수 차단은 [image-context-quality-plan.md](image-context-quality-plan.md) 우선순위로 진행한다.

### 3. TTS

- OmniVoice runtime probe는 `omnivoice_env\Scripts\python.exe`를 정상 선택했고 `omnivoice_import_ok`, `torch_import_ok`, `cuda_available` 모두 true였다.
- TTS 산출물은 `storage/projects/324b2eff3737/tts` 아래에 생성됐다.
- 작업 중 `tts_progress`가 0%로 유지되다가 완료 시 100%가 됐다.
- 개선: 문장별 wav 생성이 완료될 때마다 진행률과 현재 문장 idx를 갱신한다.

### 4. Render

- Preflight에서 기본 자막 모드 `sentence`가 한국어 긴 문장을 한 큐로 표시해 `Subtitle layout failed`가 발생했다.
- 조치: `cue_split_mode`를 `readable`로 전환 후 preflight 통과 및 렌더 완료.
- 이전 드라이런에서 ffmpeg 실패 후 cleanup `WinError 32`가 원래 오류를 덮는 현상이 있었고, cleanup 예외 억제를 반영했다.
- 개선: 한국어 긴 문장 프로젝트는 TTS 또는 render preflight 단계에서 `readable` 자막 모드를 자동 권장/자동 전환한다.
- 완료: `body_image_progress`가 이미지 생성 중 100을 넘는 값으로 표시되던 문제는 `image_worker.py`에서 0~100 clamp로 보정했다.

### 5. YouTube

- 이번 실행에서는 업로드하지 않았다.
- OAuth client secret은 존재했고, render 완료 산출물도 준비됐다.
- 개선: 업로드 버튼/작업 시작 전 `output.mp4` 또는 `output_shorts.mp4` 중 실제 렌더 산출물을 명확히 선택하게 한다.

## 우선순위

1. 완료: 이미지 프롬프트 count 초과 반복 방지.
2. 완료: LM Studio 로드 상태 감지 보정.
3. 완료: render cleanup `WinError 32` 방어.
4. 완료: EV/배터리 도메인 prompt fallback 및 vocab 보강.
5. 다음: 대본 저장 직후 mojibake 감지 및 저장 경로 인코딩 회귀 테스트.
6. 다음: 이미지 재생성 후 mapping/media_order 동기화 자동화.
7. 다음: ComfyUI 실행 시 stdout/stderr 리다이렉션을 기본 런처 규칙으로 고정.
8. 다음: TTS 진행률 세분화.
9. 다음: 한국어 긴 문장 자막 `readable` 자동 권장.
## 2026-05-16 LM Studio/Gemma4 고정 및 연결 검증

- 요청한 `gemma4 e8b` 계열 식별자는 현재 LM Studio 설치 모델 목록에서 확인되지 않았다. 실제 로드/설치된 모델은 `google/gemma-4-e4b`이므로 NewAuto Studio 기본 모델을 이 값으로 고정했다.
- `app/config.py`: 기본 `LLM_PROVIDER`를 `lmstudio`로 변경하고, 기본 `SCRIPT_LLM_MODEL`을 `google/gemma-4-e4b`로 고정했다. 잘못된 provider 값도 Ollama가 아니라 LM Studio로 되돌아가게 했다.
- `app/services/visual_planner.py`: LM Studio 사용 시 `/v1/models`만 보지 않고 `lms ps` 기반 로드 모델을 먼저 확인한다. 로드된 모델이 있으면 `SCRIPT_LLM_MODEL`과 정확히 일치해야 visual planner를 ready로 판단한다.
- `app/services/system_health.py`, `app/types.py`: `/api/system/diagnostics`에 `llm_provider`, `llm_model`, `llm_base_url`, `llm_ready`, `lmstudio_loaded_models`를 추가했다.
- 실제 연결 테스트:
  - `lms ps`: `google/gemma-4-e4b` 로드 확인.
  - `OllamaClient` LM Studio 모드 직접 호출: `response OK` 확인.
  - NewAuto Studio API 재시작 후 `/api/system/diagnostics`: `llm_provider=lmstudio`, `llm_model=google/gemma-4-e4b`, `llm_base_url=http://127.0.0.1:1234`, `llm_ready=true`, `lmstudio_loaded_models=["google/gemma-4-e4b"]` 확인.
- 검증:
  - `.\omnivoice_env\Scripts\python.exe -m pytest tests/test_config.py tests/test_llm_ollama.py tests/test_visual_planner.py tests/test_domain_detection.py tests/test_image_prompting.py tests/test_comfyui_pipeline.py tests/test_lmstudio_runtime.py tests/test_comfyui_routes.py tests/test_feature_workflow.py tests/test_system_operator.py -q`
  - 결과: 131 passed, 2 warnings
## Media 단일 기준 문서

- 앞으로 이미지 프롬프트 생성, ComfyUI, LoRA, 후보 선택, visual relevance, render 연결 기준은 [media-image-generation-master-guide-plan.md](docs/media-image-generation-master-guide-plan.md)를 우선 기준으로 삼는다.
- 기존 `comfyui.txt`, `comfysdxl.txt`, `image-context-quality-plan.md`, archive 계획서는 참고 자료로만 사용하고, 실제 NewAuto Studio Media 구현 판단은 위 문서로 통합한다.

## 2026-05-16 Media 이미지 프롬프트 안정화 진행

- `.clinerules`의 primary local model 표기를 실제 NewAuto Studio 기본값인 `google/gemma-4-e4b`로 동기화했다.
- `app/services/visual_planner.py`는 4문장 이상 대본을 3문장 batch로 나누어 LM Studio에 요청한다. 긴 전체 JSON 응답 하나가 깨져 각 문장 이미지 프롬프트가 fallback으로 비슷해지는 위험을 줄였다.
- `app/services/prompt_quality.py`는 EV/배터리 도메인에서 battery/EV/LFP/NCM/solid-state 등 핵심 시각 객체가 빠진 prompt와 Stickfigures 계열 스타일을 issue code로 차단한다.
- 추가/수정 테스트: `tests/test_visual_planner.py`, `tests/test_prompt_quality.py`.
- 검증: `python -m pytest tests/test_visual_planner.py tests/test_prompt_quality.py tests/test_image_prompting.py tests/test_comfyui_pipeline.py` 결과 49 passed.

## 2026-05-16 Media ComfyUI 진입 차단/상태 로그 보강

- `app/routers/image_gen.py`: ComfyUI batch queue 등록 전에 prompt quality report를 검사한다. EV/배터리 등 strict 도메인에서 fallback 비율 초과, EV 핵심 객체 누락, Stickfigures 스타일 차단 issue가 있으면 `body_image_state=blocked`로 중단한다.
- `app/workers/image_worker.py`: 우회 진입한 job item의 blocking prompt issue를 ComfyUI submit 직전에 다시 검사한다.
- `app/workers/image_worker.py`: ComfyUI history poll 중 prompt id, scene index, attempt, 남은 timeout을 `body_image_last_log`에 주기적으로 남기고 heartbeat도 갱신한다.
- 추가/수정 테스트: `tests/test_comfyui_routes.py`.
- 검증: `python -m pytest tests/test_comfyui_routes.py tests/test_image_worker.py tests/test_prompt_quality.py tests/test_image_prompting.py` 결과 79 passed.

## 2026-05-16 EV/LFP Media smoke

- 검증용 API 서버: `http://127.0.0.1:9003`.
- smoke project: `726788fd6c3b`.
- prompt manifest: `C:\Users\petbl\newauto\storage\projects\726788fd6c3b\image_prompts_manifest.json`.
- 결과: 10문장 모두 `ev_battery`, `txt2img_sdxl_basic`, LoRA 없음, Stickfigures trigger 0개, prompt coverage issue 0개로 통과.
- 1장 ComfyUI smoke 생성 완료: `C:\Users\petbl\newauto\storage\projects\726788fd6c3b\media\ev_smoke_scene_000_v1_00001_.png`.
- worker 상태 로그: `poll_history`에서 prompt id와 attempt가 표시되었고, 완료 후 `media_order`/`body_image_mappings`가 1개 생성됨.
- 발견/수정: EV runtime이 여전히 `txt2img_sdxl_stickman_lora`와 `Flipchartvisu, Stick figure`로 흐르던 문제를 수정했다. `prompt_compiler.py`와 `image_prompting.py`에서 EV 도메인을 Stickfigures 제외, SDXL basic/LoRA 없음으로 고정했다.
- 발견/수정: EV prompt의 4번째 `must_show`가 누락될 수 있어 prompt repair가 최대 5개 must_show를 보강하도록 수정했다.
- 발견/수정: 첫 smoke 이미지는 배터리 셀은 나왔지만 가격/비교 맥락이 약하고 3D 배터리 단품으로 흐르는 경향이 있었다. EV template을 flat 2d explainer diagram, EV silhouette, comparison icon 중심으로 강화하고 3D cylinder battery only를 negative에 추가했다.
- 검증: `python -m pytest tests/test_image_prompting.py tests/test_prompt_quality.py tests/test_comfyui_routes.py tests/test_image_worker.py` 결과 81 passed.

## 2026-05-16 EV/LFP 10장 ComfyUI full smoke

- 10장 전체 ComfyUI 생성 완료. 최종 상태: `body_image_state=done`, `body_image_phase=done`, `body_image_mappings=10`, `scene_plan/render_plan` 생성됨.
- contact sheet: `C:\Users\petbl\newauto\storage\projects\726788fd6c3b\diagnostic_contact_sheet.jpg`.
- visual mismatch report: `C:\Users\petbl\newauto\storage\projects\726788fd6c3b\visual_mismatch_report.md`.
- worker 상태 로그 확인: `poll_history`에서 scene index, prompt id, attempt, heartbeat가 계속 갱신됨.
- 발견/수정: 진행률이 100을 넘어 105/115/125로 표시되는 버그가 있었다. `image_worker.py`에서 progress 값을 0~100으로 clamp하도록 수정했다.
- 발견/수정: 전체 재생성 중 sentence 0이 이전 1장 smoke 후보를 다시 선택했다. `image_gen.py`에서 선택 범위의 기존 `body_image_mappings`, `candidate_groups`, `candidate_reviews`를 queue 등록 시 초기화하도록 수정했다.
- 발견/수정: EV strict 도메인에서 `IMAGE_SEMANTIC_MATCH_TOO_LOW`가 있어도 점수가 높으면 통과하던 문제가 있었다. `comfyui_pipeline.py`에서 EV 후보의 semantic mismatch는 점수와 무관하게 retry 권고로 처리한다.
- 남은 품질 이슈: 생성 이미지는 Stickfigures/LoRA 문제는 사라졌지만 일부 장면이 자동차 전시장, 서버룸, 단품 배터리 등으로 흐르며 semantic mismatch가 발생했다. 다음 단계는 강화된 retry 정책으로 10장 재생성 후 실제 장면 매칭을 재확인하는 것이다.
- 검증: `python -m pytest tests/test_comfyui_routes.py tests/test_image_worker.py tests/test_comfyui_pipeline.py` 결과 53 passed.

## 2026-05-16 Jensen Huang/Nvidia 대본 NewAuto Studio 생성 실행

- 모델: `lmstudio + google/gemma-4-e4b` 유지.
- 입력 대본: 젠슨 황 엔비디아 CEO가 트럼프 대통령 요청으로 방중 경제사절단에 합류했다는 4문장 한국어 대본.
- 프로젝트 ID: `f4b97ca049c8`.
- 프로젝트 경로: `C:\Users\petbl\newauto\storage\projects\f4b97ca049c8`.
- 최종 출력물: `C:\Users\petbl\newauto\storage\projects\f4b97ca049c8\output.mp4`.
- 실행 결과:
  - TTS: 완료. `tts_state=done`, 4개 wav 생성, 총 음성 길이 약 40.81초.
  - Media: ComfyUI 이미지 생성 완료. 4개 문장 매핑 완료, 후보/재시도 포함 총 8개 이미지 파일 생성.
  - Render: 완료. `render_state=done`, `output.mp4` 생성, 영상 길이 약 40.8초.
  - 자막: 최초 preflight에서 긴 한국어 문장 때문에 `subtitle_layout` 실패. `cue_split_mode=readable`로 전환 후 preflight 통과 및 렌더 완료.
- 검증 파일:
  - `render_report.json`
  - `final_scene_review.json`
  - `diagnostic_contact_sheet.jpg`
  - `visual_mismatch_report.md`
  - `preflight_report_after_readable.json`
- 확인된 문제:
  - 영상 생성은 완료됐지만 이미지 후보 점수는 일부 낮다.
  - Scene 0, 1, 3은 `retry_recommended` 및 `LOW_EDGE_DETAIL` 경고가 남았다.
  - Scene 0은 국제회의/엔비디아 CEO 합류 맥락 대신 건물 조감도 느낌이 강해 의미 매칭이 약하다.
  - Scene 1은 CNBC/공식 확인 맥락 대신 공항 디스플레이 같은 장면으로 생성되어 뉴스 기사/공식 확인 핵심이 약하다.
  - Scene 2는 전화 요청 장면으로 상대적으로 가장 잘 맞는다.
  - Scene 3은 항공기/탑승 맥락은 맞지만 Jensen Huang 탑승 행위가 약하다.
- 반영할 개선:
  - 뉴스/반도체/정치외교 도메인용 visual brief를 별도 강화한다.
  - 인물 실명/기업명/장소가 포함된 문장은 `main_subject`, `must_show`, `avoid`를 더 강하게 유지한다.
  - `retry_recommended`가 남아도 최종 pass 처리되는 현재 정책은 엄격 도메인에서는 operator warning이 아니라 재생성/차단으로 올릴지 검토한다.
  - 긴 한국어 대본은 autopilot script 입력과 수동 workflow 모두에서 기본 `cue_split_mode=readable`을 적용해야 한다.

## 2026-05-16 Media Prompt Operating Guide 구축 계획

- 목적: Gemma4가 매번 즉흥적으로 이미지 프롬프트를 만들지 않고, 검증된 내부 운영 문서를 참고해 ComfyUI/LoRA/template/domain 전략을 일관되게 사용하도록 한다.
- 새 계획서: `docs/media-prompt-operating-guide-research-plan-2026-05-16.md`.
- 방향:
  - 실시간 검색형이 아니라, 풍부한 자료수집 후 고정 운영 가이드를 만든다.
  - 로컬 문서, 코드베이스, 실패 프로젝트, ComfyUI/SDXL/LoRA 자료를 수집한다.
  - 최종 운영 문서는 `docs/media-prompt-operating-guide.md`로 만든다.
  - Gemma4 visual planner는 이 문서의 도메인별 전략, LoRA 사용/금지 기준, ComfyUI template 선택 기준, JSON schema를 참고한다.
  - 문제나 실패가 생기면 `planning_failure`, `domain_detection_failure`, `prompt_compilation_failure`, `template_selection_failure`, `generation_failure`, `candidate_selection_failure`, `visual_relevance_failure`, `subtitle_preflight_failure`, `render_failure`로 원인을 분류한다.
  - 같은 실패가 반복되면 문서 수정에 그치지 않고 quality gate, visual relevance, retry 정책, 테스트를 함께 보강한다.
- 우선 반영할 실제 사례:
  - Jensen/Nvidia 대본의 Scene 0/1/3 이미지 매칭 약함.
  - EV/LFP 대본의 일부 장면 semantic mismatch.
  - 긴 한국어 문장 subtitle layout 실패 후 readable split 필요.

## 2026-05-16 LM Studio 프롬프트 모델 비교: Gemma4 vs Qwen3.5

- 목적: NewAuto Studio의 "대본 -> 이미지 프롬프트/장면 계획" 단계에서 `lmstudio + google/gemma-4-e4b`와 `lmstudio + qwen/qwen3.5-9b` 중 어느 쪽이 실제 워크플로우에 더 안정적인지 확인했다.
- 범위: 이미지 생성까지 가지 않고, 같은 EV/LFP 배터리 대본으로 Media 프롬프트 생성 단계만 분리 테스트했다. ComfyUI/LoRA 품질과 별개로 LLM 프롬프트 생성 안정성만 비교했다.
- Gemma4 테스트:
  - 모델: `google/gemma-4-e4b`
  - 결과 파일: `storage/logs/prompt_model_compare_gemma4_e4b_3s.json`
  - 3문장 대표 샘플 생성 완료.
  - 소요 시간: 약 240.7초.
  - `prompt_count=3`, `passed_count=3`, `issue_row_count=0`, `stick_trigger_count=0`.
  - 템플릿은 `txt2img_sdxl_basic`, LoRA는 사용하지 않음.
  - 단, `plan_source=llm_batched_mixed`, `fallback_plan_entries=2`로 일부 문장은 LLM 원본 계획 대신 보강 fallback/repair가 개입했다. 즉 사용 가능하지만 속도와 완전한 LLM 응답률은 아직 개선 대상이다.
- Qwen3.5 테스트:
  - 모델: `qwen/qwen3.5-9b`
  - 3문장 테스트는 6분 내 결과 JSON 생성 실패.
  - 1문장 축소 테스트도 4분 내 결과 JSON 생성 실패.
  - LM Studio 상태가 장시간 `GENERATING`에 머물렀고 NewAuto의 현재 visual planner 프롬프트/타임아웃/JSON 응답 형식에 drop-in으로는 맞지 않았다.
- 판단:
  - 현재 NewAuto Studio 설정에서는 `lmstudio + google/gemma-4-e4b`가 더 타당하다.
  - Qwen3.5는 별도 전용 프롬프트 포맷, 출력 길이 제한, timeout, JSON 강제 스키마 튜닝을 하기 전에는 기본 프롬프트 생성 모델로 쓰지 않는다.
  - `.clinerules`, `app/config.py`, visual planner readiness 기준은 계속 `google/gemma-4-e4b` 기준으로 유지한다.
- 다음 개선:
  - Gemma4도 3문장에 약 4분이 걸렸으므로 batch prompt를 더 짧게 줄이고, 장면 계획 JSON 스키마를 더 작게 제한한다.
  - fallback이 섞인 경우에도 문장별 핵심 키워드, domain, must_show가 충분한지 prompt quality gate에서 계속 차단/보강한다.
  - Qwen3.5 재평가는 전용 짧은 system prompt와 1문장 JSON-only 스키마를 별도로 만든 뒤에 다시 진행한다.
## 2026-05-16 Media Prompt 계획서 검토/검증 업데이트

- 검토 대상: `docs/media-prompt-operating-guide-research-plan-2026-05-16.md`.
- 결과: 기존 초안은 방향은 맞았지만 일부 내용이 깨져 있었고, 구현되지 않은 도메인을 구현된 것처럼 적은 부분이 있어 전체 재작성했다.
- 반영한 검증 사항:
  - 실제 구현 도메인은 `tech`, `ev_battery`, `food_trend`, `agriculture_environment`, `science_materials`, `news_explainer`, `ai_policy_conflict`, `essay`, `generic` 기준으로 정리했다.
  - `semiconductor_business`, `politics_diplomacy`, `finance_market`는 아직 구현 도메인이 아니므로 삭제하지 않고 `tech/news_explainer/essay` 하위 sub-strategy 후보로만 남겼다.
  - ComfyUI template 목록은 실제 `app/workflow_templates/comfyui` 파일 기준으로 정리했다.
  - `GENERIC_FALLBACK_IN_MUST_SHOW`, `GENERIC_FALLBACK_IN_PROMPT`, EV strict prompt issue는 이미 worker gate에 반영되어 있으므로 "미구현" 표현을 제거했다.
  - Gemma4가 여러 Media 문서를 동시에 참고하지 않도록 최종 단일 문서 정책을 추가했다.
- 단일 문서화 방향:
  - 최종 기준 문서는 `docs/media-prompt-operating-guide.md` 하나로 만든다.
  - 기존 Media 관련 문서는 최종 가이드에 필요한 내용만 흡수한 뒤 `docs/archive/media_prompt_legacy/`로 이동하거나 deprecated 처리한다.
  - `issue.md`, 앱 도움말, Gemma4 planner prompt는 최종적으로 `docs/media-prompt-operating-guide.md`만 가리키게 한다.
- 삭제/정리 원칙:
  - 최종 가이드가 완성되기 전에는 관련 문서를 즉시 삭제하지 않는다.
  - 먼저 내용 흡수, 링크 교체, deprecated banner 추가, archive 이동 순서로 진행한다.
  - 완전히 중복된 scratch 계획서만 최종 확인 후 삭제한다.

## 2026-05-16 Media Prompt 최종 단일 운영 가이드 생성

- 최종 기준 문서: `docs/media-prompt-operating-guide.md`.
- 이 문서를 NewAuto Studio Media 이미지 프롬프트/ComfyUI/LoRA/template/domain/failure-analysis의 단일 기준으로 사용한다.
- `docs/media-image-generation-master-guide-plan.md`와 `docs/media-simplification-plan-2026-05-15.md`에는 deprecated 배너를 추가했다.
- `docs/media-prompt-operating-guide-research-plan-2026-05-16.md`도 최종 가이드에 의해 superseded 처리했다.
- 다음 정리 작업:
  - 코드와 Gemma4 visual planner prompt가 `docs/media-prompt-operating-guide.md`의 compact rules를 참조하도록 연결한다.
  - 기존 Media 문서는 유효 내용 흡수 확인 후 `docs/archive/media_prompt_legacy/`로 이동한다.
  - 이후 `issue.md`와 앱 도움말에서 Media 관련 링크는 최종 가이드 하나만 가리키도록 정리한다.

## 2026-05-16 Gemma4 Visual Planner 운영 가이드 연결

- `app/services/visual_planner.py`에 `docs/media-prompt-operating-guide.md` 기반 compact operating rules를 추가했다.
- 전체 문서를 매번 LLM 프롬프트에 넣지 않고, 도메인별 핵심 규칙만 system prompt에 주입한다.
- 추가된 핵심 규칙:
  - `must_show`, `main_subject`, `action`, `environment`, `avoid` 보존.
  - generic office/dashboard/empty building/road/signpost/checklist/city drift 금지.
  - EV battery, named executive, semiconductor business news, political/business delegation에서는 Stickfigures LoRA 금지.
  - 기본 template은 `txt2img_sdxl_basic`, 기본 `lora_policy=none`.
  - Jensen Huang/Nvidia/Trump/delegation/Air Force One/Beijing/Alaska/China-trip 문맥은 `semiconductor_business_news` 또는 delegation 계열 sub-strategy로 처리하도록 명시.
- Visual planner 출력 schema 예시에 `sub_strategy`, `template_hint`, `lora_policy`를 추가했다.
- 테스트 추가:
  - `tests/test_visual_planner.py`에서 운영 가이드 경로, Jensen/Nvidia sub-strategy, LoRA 금지 정책, template/schema 확장이 prompt에 포함되는지 검증.
- 검증:
  - `python -m pytest tests/test_visual_planner.py tests/test_image_prompting.py tests/test_prompt_quality.py -q` 결과 51 passed.
  - `python -m pytest tests/test_comfyui_routes.py tests/test_image_worker.py tests/test_comfyui_pipeline.py -q` 결과 53 passed, FastAPI on_event deprecation warning 2개.

## 2026-05-16 Jensen/Nvidia 대본 재생성 결과

- 프로젝트 ID: `9316ad51b227`.
- 최종 영상: `C:\Users\petbl\newauto\storage\projects\9316ad51b227\output.mp4`.
- contact sheet: `C:\Users\petbl\newauto\storage\projects\9316ad51b227\diagnostic_contact_sheet.jpg`.
- render report: `C:\Users\petbl\newauto\storage\projects\9316ad51b227\render_report.json`.
- visual mismatch report: `C:\Users\petbl\newauto\storage\projects\9316ad51b227\visual_mismatch_report.md`.
- 결과:
  - TTS 완료, 약 41.03초.
  - readable subtitle split 적용으로 preflight 통과.
  - ComfyUI 이미지 4개 문장 매핑 완료.
  - Render 완료, `output.mp4` 생성.
- 품질 확인:
  - Scene 0은 이전보다 명시적으로 두 인물 대화/공식 요청 장면에 가까워졌지만 candidate score 0.50으로 여전히 retry 권고.
  - Scene 1은 score 0.886으로 통과했지만 과도한 상징적 뉴스 장면이라 CNBC/공식 확인 맥락은 더 직접화 필요.
  - Scene 2는 fallback으로 떨어졌고 Stickfigures trigger가 들어가 건물 외관으로 드리프트했다. 운영 가이드의 named executive/delegation LoRA 금지 규칙이 fallback/autopilot batch path까지 완전히 전파되지 않은 증거다.
  - Scene 3은 항공기/공항/탑승 맥락이 이전보다 좋아졌지만 candidate score 0.398 및 LOW_EDGE_DETAIL 경고.
- 다음 개선:
  - `autopilot._build_image_batch_items()`의 Stickfigures 자동 전환 로직이 prompt의 `lora_policy=none` 또는 named executive/delegation sub-strategy를 존중하도록 수정해야 한다.
  - `visual_planner` schema 확장값(`sub_strategy`, `template_hint`, `lora_policy`)을 `VisualPlanEntry` normalization과 `image_prompting`/batch item까지 보존해야 한다.
  - named executive/delegation sub-strategy는 strict domain처럼 retry 권고가 남으면 최종 pass가 아니라 재생성/차단으로 올려야 한다.

## 2026-05-16 ComfyUI/LoRA 외부 자료 수집 및 반영

- 이번 단계에서 GitHub/웹 자료를 실제로 수집해 `docs/media-prompt-operating-guide.md`에 반영했다.
- 확인한 주요 출처:
  - ComfyUI GitHub README: node graph/API backend, workflow metadata, prompt emphasis/dynamic prompt behavior.
  - ComfyUI Cloud/API docs: workflow는 API-format JSON graph이며 prompt submission 후 `prompt_id`로 비동기 실행.
  - ComfyUI Community Manual Load LoRA: LoRA는 diffusion model과 CLIP을 수정하며 `lora_name`, `strength_model`, `strength_clip` 입력을 갖는다.
  - ComfyUI Dev Load LoRA guide: LoRA trigger word는 제작자 문서에 따르고, style/character/scene/lighting 목적에 맞게 사용해야 한다.
  - Tech Tactician SDXL ComfyUI workflow notes: SDXL workflow는 native nodes와 `CLIPTextEncodeSDXL`/LoRA toggle 구조를 쓸 수 있고 LoRA는 기본 비활성화 상태가 안정적이다.
  - Civitai Stickfigures SDXL LoRA: base model SDXL 1.0, trigger words `Flipchartvisu`, `Stick figure`.
- 운영 가이드 반영:
  - 외부 자료 출처 섹션 추가.
  - LoRA는 generic factual grounding 용도가 아니라 style/character/scene/lighting 보정용이라는 정책 추가.
  - `strength_model`, `strength_clip`, trigger word, local file, domain allow/block 정보를 LoRA별 필수 기록 항목으로 명시.
  - Stickfigures LoRA의 trigger word와 금지 도메인/금지 sub-strategy를 명확히 기록.
  - `Flipchartvisu` 또는 `Stick figure`가 named executive/news/EV/semiconductor delegation prompt에 들어가면 LoRA policy failure로 처리해야 한다고 명시.
  - SDXL dual prompt 정책(`prompt_g`, `prompt_l`) 추가.
- 코드 반영:
  - `app/types.py`: `VisualPlanEntry`에 `sub_strategy`, `template_hint`, `lora_policy` 보존 필드 추가.
  - `app/services/visual_planner.py`: LLM normalize 과정에서 세 필드를 보존.
  - `app/services/autopilot.py`: Stickfigures 자동 전환 로직이 `lora_policy=none`, strict/news/tech/EV domain, Jensen/Nvidia/Trump/delegation/Air Force One/Beijing/Alaska 같은 named executive/delegation 문맥을 존중하도록 차단.
- 테스트:
  - `python -m pytest tests/test_visual_planner.py tests/test_autopilot_worker.py tests/test_image_prompting.py tests/test_prompt_quality.py -q` 결과 61 passed.
  - `python -m pytest tests/test_comfyui_routes.py tests/test_image_worker.py tests/test_comfyui_pipeline.py -q` 결과 53 passed, FastAPI on_event deprecation warning 2개.
## 2026-05-16 Media Guide / Jensen Workflow Update

- Active Media guide is now `docs/media-prompt-operating-guide.md`.
- Legacy Media prompt documents were archived under `docs/archive/media_prompt_legacy/`; older links above are historical only.
- LM Studio prompt generation was run with `google/gemma-4-e4b`, ComfyUI at `http://127.0.0.1:8188`, and Omnivoice TTS.
- Latest Jensen/Nvidia workflow output:
  - Project: `C:\Users\petbl\newauto\storage\projects\14ec02ab8fc3`
  - Video: `C:\Users\petbl\newauto\storage\projects\14ec02ab8fc3\output.mp4`
  - Contact sheet: `C:\Users\petbl\newauto\storage\projects\14ec02ab8fc3\diagnostic_contact_sheet.jpg`
- Fixed:
  - Removed automatic Stickfigures LoRA upgrade from autopilot image batch creation.
  - Downgraded blocked Stickfigures requests to `txt2img_sdxl_basic`.
  - Removed `Flipchartvisu` / `Stick figure` trigger terms when blocked.
  - Prevented generic fallback visual plans from using Stickfigures-style prompts.
- Verified:
  - Actual queued batch items for project `14ec02ab8fc3` were all `txt2img_sdxl_basic`, empty `lora_name`, `lora_strength=0.0`.
  - `visual_mismatch_report.md` for project `14ec02ab8fc3` has no `Flipchartvisu`, `Stick figure`, `stickman`, or `txt2img_sdxl_stickman_lora` hits.
  - Tests: `python -m pytest tests/test_image_prompting.py tests/test_autopilot_worker.py tests/test_visual_planner.py tests/test_prompt_quality.py -q` => 63 passed.
- Remaining issue:
  - The final video renders, TTS/subtitles are usable, and LoRA misuse is blocked, but visual semantic matching is still weak for scenes 0-2.
  - Candidate review still marks all 4 scenes as requiring operator review; scenes 1-2 fall back to generic/abstract imagery.
  - Next implementation should add a first-class `political_business_delegation` / `semiconductor_business_news` visual domain with concrete scene templates for executive arrival, official confirmation, phone-call request, and airport boarding.

## 2026-05-16 Jensen/Nvidia Visual and TTS Follow-up

- Detailed plan: `docs/jensen-news-visual-tts-fix-plan-2026-05-16.md`
- User screenshot reviewed: `C:\Users\petbl\Downloads\화면 캡처 2026-05-16 160248.png`
- Confirmed issue:
  - Scene 0 image is unrelated fantasy landscape, not Jensen Huang / Nvidia / Trump / delegation context.
  - Scenes 1-2 also remain too abstract and generic.
  - TTS reads Korean alias plus English parenthetical alias, for example `엔비디아(Nvidia)`.
- Implemented now:
  - TTS text normalization removes Latin parenthetical aliases after Korean words before synthesis.
  - Example: `젠슨 황(Jensen Huang) 엔비디아(Nvidia) CEO` -> `젠슨 황 엔비디아 CEO`.
  - Standalone English acronyms such as `CNBC`, `CEO`, `LFP`, `NCM` remain untouched.
- Verified:
  - `python -m pytest tests/test_tts_pipeline.py tests/test_tts_worker.py -q` => 25 passed.
- Next image implementation direction:
  - Replace generic cinematic/fantasy fallback with simple 2D caricature news illustration.
  - Add deterministic templates for delegation inclusion, official confirmation, phone-call request, and airport boarding.
  - Force `txt2img_sdxl_basic`, `lora_policy=none`, bright/simple composition, no fantasy scenery.

## 2026-05-16 Jensen/Nvidia Regeneration With Simple News Caricature

- New generated project: `C:\Users\petbl\newauto\storage\projects\066827c044eb`
- Final video: `C:\Users\petbl\newauto\storage\projects\066827c044eb\output.mp4`
- Contact sheet: `C:\Users\petbl\newauto\storage\projects\066827c044eb\diagnostic_contact_sheet.jpg`
- Applied code changes:
  - Added deterministic simple 2D news caricature prompt templates for Jensen/Nvidia delegation scenes.
  - Scene templates now cover delegation inclusion, official confirmation, phone-call request, and airport boarding.
  - Forced generated items to `txt2img_sdxl_basic`, `lora_strength=0.0`.
  - TTS normalized `젠슨 황(Jensen Huang) 엔비디아(Nvidia)` to `젠슨 황 엔비디아`.
  - Added render option `allow_visual_relevance_warnings_for_render` so manually reviewed warning-level visual relevance failures can still render.
- Verified:
  - Latest TTS timings no longer include `Jensen Huang` or `Nvidia` parenthetical aliases.
  - Latest contact sheet no longer shows fantasy landscape for scene 0; it uses simple business/news caricature imagery.
  - Latest render completed: duration 39.9s, drift 0.0s.
  - Tests: `python -m pytest tests/test_image_prompting.py tests/test_tts_pipeline.py tests/test_autopilot_worker.py -q` => 53 passed.
- Remaining caution:
  - Visual relevance scorer still reports semantic match warnings because its report path is reading some sentence text in mojibake form, so automated score is harsher than the visible output.
  - Scene 0 is still somewhat cluttered with too many meeting participants. Next improvement should limit news caricature prompts to 2-4 characters and one large prop.

## 2026-05-16 Output Quality Analysis: Project 066827c044eb

- Reviewed output: `C:\Users\petbl\newauto\storage\projects\066827c044eb\output.mp4`
- Audio track check:
  - `ffprobe` confirms 2 streams: H.264 video + AAC audio.
  - Audio stream: AAC LC, 24000 Hz, mono, duration 39.9s, bitrate about 103 kb/s.
  - `volumedetect` on both `output.mp4` audio and `audio.wav`: mean volume about `-8.1 dB`, max volume about `-0.9 dB`.
  - Therefore the rendered file is not actually silent at the container/audio-signal level.
- Likely audio problem:
  - Some players or preview surfaces may fail or mute 24kHz mono AAC even though ffmpeg sees it correctly.
  - Safer render target should mux final audio as 48kHz stereo AAC, e.g. `-ar 48000 -ac 2 -c:a aac -b:a 192k`.
  - UI should add a post-render audio audibility check and warn if player-compatible audio profile is not met.
- TTS text check:
  - Actual UTF-8 TTS timings contain normalized text: `젠슨 황 엔비디아 CEO...`
  - Parenthetical aliases `Jensen Huang` and `Nvidia` were removed from TTS input.
  - Some PowerShell output still displays mojibake, but Python UTF-8 reads show the stored project script/timings/subtitles are normal.
- Image quality check:
  - Scene 0 selected image score: `0.474`, issue `DENSE_DIAGRAM_CLUTTER`, operator review required.
  - Scene 1 selected image score: `0.772`, acceptable but still semantically shallow.
  - Scene 2 selected image score: `0.680`, borderline, operator review required.
  - Scene 3 selected image score: `0.743`, acceptable.
  - Contact sheet confirms images are now simple caricature/news style, but scene 0 is cluttered and scene 2 is too generic portrait-like.
- Root visual problems:
  - Prompts still allow too many people and too much background detail.
  - "simple 2d caricature" is not enough; the prompt must force `2-4 characters maximum`, `one large prop`, `flat vector editorial cartoon`, and `plain background`.
  - Retry/fallback currently creates near-duplicates instead of meaningfully simplifying the composition.
  - Render was allowed despite warnings, so low-quality visual output reached final video.
- Next fixes:
  - Resample/mux final audio to 48kHz stereo AAC for player compatibility.
  - Add render post-check that fails or warns if final MP4 audio profile is not 48kHz stereo AAC or if extracted RMS is near silent.
  - Tighten news caricature prompts to max 2-4 characters, one large prop, no meeting room clutter, no wall of documents, no dense diagrams.
  - Do not render automatically when scene 0/2 remain `operator_intervention_required` unless an explicit review-override is set.

## 2026-05-16 Superpowers Plugin Review

- Reviewed:
  - `https://news.hada.io/topic?id=29552`
  - `https://maily.so/makersnote/posts/1do1dwqlox6`
  - `https://github.com/obra/superpowers`
- Plan: `docs/superpowers-adoption-plan-2026-05-16.md`
- Local setup status:
  - Registered Codex marketplace: `codex plugin marketplace add obra/superpowers-marketplace`
  - Upgraded marketplace: `codex plugin marketplace upgrade superpowers-marketplace`
  - Marketplace root: `C:\Users\petbl\.codex\.tmp\marketplaces\superpowers-marketplace`
  - Inspected plugin version: Superpowers `5.1.0`
- Limitation:
  - Current Codex CLI exposes marketplace add/upgrade/remove, but not non-interactive plugin install.
  - Actual plugin activation likely needs Codex App Plugins sidebar or interactive `/plugins`.
- Useful direction for newautostudio:
  - Adopt Superpowers-style gates even before full plugin activation.
  - Use systematic debugging for every failed video.
  - Require artifact verification before saying final output is complete.
  - Write specs/plans under `docs/superpowers/`.
  - Add evidence bundle scripts for project diagnostics.
  - Use TDD for render/TTS/visual relevance behavior changes.

## 2026-05-16 Superpowers Adoption Review Validation

- Reviewed and validated: `docs/superpowers-adoption-review-2026-05-16.md`
- Updated plan: `docs/superpowers-adoption-plan-2026-05-16.md`
- Superpowers skill loading status:
  - Superpowers is not active as a first-class Codex skill in this session.
  - Loaded local inspected Superpowers `v5.1.0` skill files directly from `%TEMP%\superpowers-inspect`.
  - Checked `systematic-debugging`, `verification-before-completion`, `writing-plans`, and `test-driven-development`.
- Verified review claims that were accepted:
  - Final render audio currently uses `AUDIO_SAMPLE_RATE = 24000` and `AUDIO_CHANNELS = 1`.
  - `_mux()` does not force final MP4 audio to 48kHz stereo AAC.
  - `render_report` does not yet expose final audio sample rate, channels, codec, or `volumedetect` metrics.
  - `operator_intervention_required` is recorded by the media pipeline but is not a reliable render-blocking gate.
  - `scripts/collect_project_diagnostics.py`, `app/services/diagnostics.py`, and `docs/superpowers/` do not exist.
  - Existing systems already cover parts of the Superpowers discipline: preflight, render report, visual relevance, contact sheet, prompt quality checks, and operator summary.
- Plan corrections made:
  - Do not treat Superpowers plugin activation as the immediate fix.
  - Do not duplicate existing evidence systems; extend the current ones.
  - Keep the current repo convention of date-stamped plans under `docs/` unless the plugin is fully activated and a deliberate migration is made.
  - Prioritize code-level completion gates: 48kHz stereo AAC output, post-render audio metrics, `operator_intervention_required` render blocking, and a thin diagnostics bundle.

## 2026-05-16 Superpowers P1 Gate Implementation

- Applied Superpowers-style verification workflow to the first implementation batch.
- Updated:
  - `app/services/render.py`
  - `app/services/render_report.py`
  - `app/services/preflight.py`
  - `app/types.py`
  - `tests/test_render_visual_track.py`
  - `tests/test_render_report.py`
  - `docs/superpowers-adoption-plan-2026-05-16.md`
- Implemented:
  - Final MP4 mux now forces AAC 48kHz stereo at 192k.
  - Render report output rows now include audio codec, sample rate, channels, bitrate, profile pass/fail, mean volume, max volume, and audibility pass/fail.
  - `ffmpeg volumedetect` is now part of render report generation for existing outputs.
  - Render now blocks by default when `operator_intervention_required=true`.
  - Preflight now reports `operator_visual_review`.
  - Explicit visual warning override can still render, and the override is written into the render log tail.
- Verification:
  - `python -m pytest tests/test_render_visual_track.py tests/test_render_report.py tests/test_visual_relevance.py -q` => 51 passed.
  - `python -m pytest tests/test_render_visual_track.py tests/test_render_report.py tests/test_tts_pipeline.py tests/test_autopilot_worker.py -q` => 58 passed.
- Next:
  - Add thin diagnostics bundle script/service.
  - Regenerate the Jensen/Nvidia sample after the new render gates so the final artifact is verified with the new 48kHz stereo AAC report metrics.

## 2026-05-16 Superpowers P2 Diagnostics Bundle

- Implemented a thin diagnostics bundle using existing evidence systems instead of adding a parallel reporting stack.
- Added:
  - `app/services/diagnostics.py`
  - `scripts/collect_project_diagnostics.py`
  - `tests/test_diagnostics.py`
- CLI usage:
  - `python scripts\collect_project_diagnostics.py <project_id>`
- Bundle output:
  - `storage/projects/<project_id>/diagnostics_bundle/`
- Bundle files:
  - `ffprobe_output.json`
  - `audio_volumedetect.txt`
  - `render_report.json`
  - `preflight_report.json`
  - `tts_manifest_excerpt.json`
  - `visual_mismatch_report.md`
  - `visual_mismatch_report.json`
  - `final_scene_review.json`
  - `operator_summary.json`
  - `diagnostic_contact_sheet.jpg`
  - `diagnostics_manifest.json`
- Verified:
  - `python -m pytest tests/test_diagnostics.py tests/test_render_report.py tests/test_visual_relevance.py -q` => 28 passed.
  - `python -m pytest tests/test_diagnostics.py tests/test_render_visual_track.py tests/test_render_report.py tests/test_visual_relevance.py tests/test_tts_pipeline.py tests/test_autopilot_worker.py -q` => 83 passed on rerun.
  - Real smoke: `python scripts\collect_project_diagnostics.py 066827c044eb`
  - Real bundle path: `C:\Users\petbl\newauto\storage\projects\066827c044eb\diagnostics_bundle`
- Note:
  - The existing `066827c044eb` output was rendered before the P1 mux fix, so its diagnostic bundle correctly still shows AAC 24kHz mono.
  - A new render is needed to verify final AAC 48kHz stereo on an actual generated video.

## 2026-05-16 TTS Crackle/Noise Diagnosis and Fix

- User clarified the issue is not silence; the audio sounds like static/noise instead of readable speech.
- Diagnosed project: `C:\Users\petbl\newauto\storage\projects\066827c044eb`
- Findings:
  - `output.mp4` audio exists but is old AAC 24kHz mono.
  - `audio_raw.wav` and `audio.wav` contain strong negative DC offset.
  - Existing render `loudnorm` amplified the biased signal instead of removing the offset.
  - Python UTF-8 reading of `tts_run_manifest.json` shows Korean text is valid; PowerShell mojibake display was misleading.
- Code fixes:
  - `app/services/tts.py`
    - Added audio sanitation before writing WAV: squeeze, finite cleanup, DC offset removal, peak guard.
    - `run_tts_job()` now uses `save_audio_file()` instead of direct `soundfile.write()`.
    - TTS consistency report now records `dc_offset_abs` and fails if max offset is too high.
  - `app/services/render.py`
    - Normalize filter changed to `highpass=f=80,loudnorm=I=-14:TP=-1.5:LRA=11`.
- Tests:
  - Added coverage that `save_audio_file()` removes large DC offset before writing.
  - Updated render normalization test to require the highpass filter.
  - `python -m pytest tests/test_tts_pipeline.py tests/test_render_visual_track.py tests/test_render_report.py tests/test_diagnostics.py -q` => 50 passed.
- Created quick repair artifact from the old project for listening comparison:
  - `C:\Users\petbl\newauto\storage\projects\066827c044eb\output_audio_repaired.mp4`
  - Audio stream verified: AAC 48kHz stereo, about 192k.
- Note:
  - The repair artifact reuses old generated TTS audio, so it can remove DC/static harshness but cannot improve voice naturalness as much as regenerating TTS after the new sanitation fix.

## 2026-05-16 HyperFrames Research and Adoption Plan

- User requested detailed GitHub investigation of HyperFrames and whether it can help newautostudio.
- Researched:
  - GitHub: `https://github.com/heygen-com/hyperframes`
  - Official docs: `https://hyperframes.app/docs/1-startup/1-introduction`
  - Local clone: `%TEMP%\hyperframes-inspect`
  - Inspected commit: `2355d505e125fac04357479d444bb11a489a2ed6`
  - License: Apache-2.0
- Plan written:
  - `docs/hyperframes-adoption-plan-2026-05-16.md`
- Key conclusion:
  - HyperFrames should not replace ComfyUI image generation.
  - Best use is as a deterministic HTML/CSS/GSAP motion-graphics overlay engine on top of ComfyUI images.
- Recommended first path:
  - Overlay-only sidecar.
  - Generate transparent WebM/MOV overlay from project timings.
  - Composite it over the current `_visual_<format>.mp4` before final mux.
- Useful HyperFrames features for us:
  - Lower-thirds.
  - Keyword callouts.
  - Source/date badges.
  - Simple route arrows.
  - Quote cards.
  - Shimmer/text effects.
  - Transparent WebM/MOV output with alpha.
  - `lint` and `inspect` gates for text overflow.
- Not recommended initially:
  - Full render backend replacement.
  - Letting HyperFrames infer image semantics.
  - Replacing existing ASS subtitles before overlay quality is proven.
- Next implementation sequence:
  - P0 environment smoke: Node >= 22, `npx hyperframes doctor`, transparent overlay render, FFmpeg alpha composite.
  - P1 `app/services/hyperframes_overlay.py`.
  - P2 optional render integration.
  - P3 news overlay templates for Jensen/Nvidia and tech explainer videos.

## 2026-05-16 HyperFrames Plan Opinion Review

- Reviewed: `docs/hyperframes-adoption-plan-opinion-2026-05-16.md`
- Updated: `docs/hyperframes-adoption-plan-2026-05-16.md`
- Superpowers status:
  - Superpowers is still not active as a first-class Codex skill in this session.
  - Used local inspected Superpowers docs for `writing-plans`, `systematic-debugging`, `verification-before-completion`, and `test-driven-development`.
- Verified accepted claims:
  - `node --version` => `v22.16.0`.
  - `npx --version` => `10.9.2`.
  - FFmpeg encoders include `libvpx-vp9` and `prores_ks`.
  - Current `app/services/render.py::_mux()` burns ASS subtitles with a single `-vf ass=...` path.
  - Current subtitle default font is `Malgun Gothic`.
  - `SystemHealth` is a typed surface in `app/types.py` and is populated in `app/services/system_health.py`.
  - `body_image_options` is already JSON-backed, so overlay option keys do not need a SQLite schema migration.
- Plan corrections accepted:
  - Treat current HyperFrames document as an adoption spec, not an executable implementation plan.
  - Do not create `composited_visual.mp4`; extend `_mux()` with optional overlay input and one `filter_complex` pass.
  - Pin HyperFrames version, initial candidate `hyperframes@0.6.12`; do not use `@latest`.
  - Require vendored Korean font through `@font-face`; do not rely on Chromium fallback fonts.
  - Start with one combined `lower_third_keyword` template only.
  - Add runtime/preflight probes early.
  - Define exact `body_image_options` keys.
  - State clearly that overlays improve editorial motion graphics, not ComfyUI semantic image drift.
- Deferred:
  - Moving documents into `docs/superpowers/...` is deferred to avoid changing the repo documentation convention midstream.
  - Full HyperFrames backend replacement remains deferred.
- Next:
  - Write a separate bite-sized implementation plan before code changes:
    - `docs/hyperframes-overlay-implementation-plan-2026-05-16.md`
