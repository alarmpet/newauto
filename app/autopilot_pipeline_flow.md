# 🎥 Autopilot 영상 생성 파이프라인 흐름 요약
## 개요
본 파이프라인은 FastAPI 백엔드(`app/main.py`)를 통해 `/api/projects/{pid}/autopilot/start` 엔드포인트로 시작하며, 소스 수집부터 최종 렌더링까지의 모든 비동기 및 순차적 과정을 관리합니다. 핵심 로직은 `app/services/autopilot.py`에 구현되어 상태 추적(State Machine) 방식으로 동작합니다.

## 주요 단계별 흐름
### ⚙️ 1단계: 입력 정의 및 소스 확보 (Input & Source Collection)
| 액션 | 함수 / 서비스 | 설명 | 결과물 |
| :--- | :--- | :--- | :--- |
| **입력 분석** | `_validate_start_payload` | API 요청에 따라 input\_mode(script/url/keyword)를 검증합니다. | 유효한 작업 파라미터 셋 (`AutopilotOptions`) |
| **스크립트 입력** (Script Mode) | `_save_script_input`, `compile_script` | 사용자가 제공한 스크립트를 받아 컴파일하고, 문장 단위(regional\_sentences), 개별 문장(sentences)으로 구조화합니다. | `compiled_script.txt`, 분할된 문장 리스트 (ProjectDB 업데이트) |
| **URL 소스 확보** (URL Mode) | `analyze_source_url` | 제공된 URL에서 사실적 정보를 추출하고, 이를 기반으로 스크립트 초안을 생성합니다. | `source\_draft\_sources`, `fact_notes` (ProjectDB 업데이트) |
| **Keyword 소스 확보** (Keyword Mode)| `collect_sources_from_keyword` | 키워드를 기반으로 검색 엔진(Brave 등)에서 다수의 소스를 수집하고, 본문 내용을 추출하여 사실 노트와 소스를 구성합니다. | `source\_draft\_sources`, `fact_notes` (ProjectDB 업데이트) |
| **Source Draft 적용** | `_apply_source_draft` | 확보된 외부 소스 데이터를 기반으로 스크립트 초안을 생성하고, 이를 메인 스크립트로 덮어씁니다. | `source\_draft\_script`가 포함된 프로젝트 기록 (Phase: source\_generate) |

### 🔁 2단계: 상태 대기 및 워커 제어 (State Waiting & Worker Control)
*   **핵심 로직**: `_wait_for_state` 함수를 통해 파이프라인의 각 주요 단계(Source Draft, Image Gen, TTS 등)가 완료될 때까지 폴링합니다.
*   **안전 장치**: 프로젝트 상태(`autopilot_state`)가 'paused' 또는 'error'로 바뀌면 즉시 작업을 중단하고 사용자에게 검토를 요청하며, `last_failure` 스냅샷을 저장합니다.

### 🖼️ 3단계: 미디어 에셋 생성 (Media Asset Generation)
이 단계는 주로 백그라운드 워커(`image_worker`, `tts_worker`)에서 비동기적으로 처리됩니다.

#### A. 이미지 생성 (Image Generation)
*   **프롬프트 준비**: `suggest_image_prompt_batch`가 스크립트의 문장 단위 정보를 이용해 각 장면에 필요한 텍스트 프롬프트를 배치(Batch)로 만듭니다. 이 과정에서 **Visual Plan** 및 **Subject Mode** 분석이 포함됩니다.
*   **요청 구성**: `_build_image_batch_items`는 ComfyUI에 전달할 모든 파라미터(Checkpoint, LORA 정보, Width/Height, Seed 등)를 포함한 요청 목록을 생성합니다. (Sticker-figure LoRA 자동 적용 로직 포함).
*   **실행**: 이 요청이 ComfyUI 백엔드(`comfyui_pipeline`)로 전달되어 이미지 생성을 시작하고, 상태 변화를 대기합니다.

#### 🔊 음성 합성 (Text-to-Speech, TTS)
*   **프로필 결정**: `_effective_autopilot_tts_profile`을 통해 최종 TTS 프로필(목소리 프리셋, 모드 등)을 확정합니다.
*   **합성 요청**: 분할된 스크립트를 기반으로 음성 클립 생성을 워커에 위임합니다.

#### 📝 자막 및 전처리 (Subtitle & Preprocessing)
*   **자막 스타일링**: `normalize_subtitle_style`을 통해 최종 자막 표시 방식(위치, 애니메이션 등)을 결정합니다.
*   **상태 업데이트**: 이 모든 과정의 진척도는 `_update_runtime` 함수를 통해 프로젝트 레코드가 지속적으로 업데이트됩니다.

### 🎞️ 4단계: 최종 렌더링 (Final Rendering)
1.  **플랜 빌드**: 모든 미디어 에셋(이미지 파일, 오디오 클립, 자막 파일 경로 등)이 준비되면 `build_render_plan`을 호출하여 통합적인 렌더 플랜을 생성합니다.
2.  **최종 실행**: 이 렌더 플랜은 렌더링 워커에게 전달되어 최종 비디오 파일을 합성하고 출력합니다 (`render.py`).

## 파이프라인 주요 의존성 (Dependency Map)
*   `app/routers/autopilot.py` $\rightarrow$ `autopilot_svc.start()` 실행 트리거
*   `app/services/autopilot.py` $\rightarrow$ **전체 흐름 제어** 및 상태 관리
    *   $\rightarrow$ `source_research`, `analyze_source_url` (정보 수집)
    *   $\rightarrow$ `compile_script`, `flatten_regional_sentences` (텍스트 전처리)
    *   $\rightarrow$ `image_prompting.py` $\rightarrow$ ComfyUI (시각 자산 생성)
    *   $\rightarrow$ `tts.py` / TTS Worker (음성 자산 생성)
    *   $\rightarrow$ `render_plan.py` $\rightarrow$ 최종 합성(Rendering)

---
**작업 진행 상황**: 전체 파이프라인 흐름 요약 및 저장 완료.
**남은 일**: 없음. (요청된 내용을 성공적으로 처리함.)
**차단 요인**: 없음.