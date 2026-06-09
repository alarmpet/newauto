# newauto Windows Studio 전환 마스터 플랜

작성일: 2026-05-15  
업데이트: 2026-05-15 (코드베이스/워크플로우/DB/research.md/timeline.md 재검토 반영)
목표: 현재 브라우저 콘솔/웹 UI 중심의 `newauto`를, 첨부 이미지처럼 Windows에 설치해서 쓰는 영상 자동화 스튜디오 프로그램으로 전환한다.

## 0. 업데이트 노트 (2026-05-15 재검토)

이 절은 1차 작성본과 실제 코드/워크플로우/DB/타임라인을 비교한 결과 잘못된 가정, 누락된 자산, 과소평가된 리스크를 한곳에 모은다. 본문의 각 항목은 12절·13절에서 자세히 풀어 쓴다.

수정 사항:

- `app/static/index.html`의 mojibake 흔적은 현재 작업트리에서 확인되지 않는다. 한글이 정상 표시된다. mojibake 점검은 “레거시 로그(`docs/archive/legacy_logs/research.md`, `timeline.md`) 및 소스 수집 캐시” 범위로 좁힌다. `app/services/text_health.py::looks_mojibake`와 `app/services/source_fetch.py::_looks_mojibake`가 이미 가동 중이다.
- 장면(scene) 모델은 사실상 이미 존재한다. `app/types.py::ScenePlanScene` + `RenderPlanSegment`에 `sentence_idx, text, region, duration_sec, visual_intent, prompt, style, media_path, key_concept, visual_metaphor, subject, props, background, avoid, core_meaning, primary_keywords, secondary_keywords, subject_modes, must_show, may_show, prompt_hint, vocab_refs, domain, motion, effect, caption_style`가 들어 있다. Phase 2는 “새 모델 추가”가 아니라 “기존 ScenePlanScene/RenderPlanSegment에 카드 UI용 필드(scene_id, locked, voice_asset_path, subtitle_override 등)를 부가”로 다시 정의한다.
- “원클릭 진행” 엔진은 `autopilot` 라우터(start/status/events/debug/pause/resume/cancel)와 `app/workers/autopilot_worker.py`, `app/services/autopilot.py`로 이미 구현되어 있다. Phase 5의 작업은 엔진이 아니라 “장면 카드 UI 결합 + 누락 검증 가이드 + 결과 검사 패널”이다.
- LM Studio/MCP 에이전트 트랙(`scripts/newauto_stepwise_mcp.py`, `scripts/lmstudio_direct_operator.py`, `lmstudio-do.cmd`)이 본문에 누락되어 있다. Windows Studio 제품 안에서 (a) LM Studio를 외부 오케스트레이터로 유지할지, (b) Tauri 앱 안에 직접 LLM 디스패처를 내장할지를 명시적으로 선택해야 한다. 본 업데이트는 (a) 기본·(b) 옵션을 권장한다.
- 패키징(PyInstaller + Tauri sidecar)에 대한 구체 위험이 1차본에 빠져 있다: (1) `app/main.py`가 `sys.executable -m app.workers.*`로 워커를 띄우는 구조는 PyInstaller `--onedir` 바이너리에서 그대로 작동하지 않는다. (2) `app/config.py`의 `STORAGE_DIR`, `DB_PATH`가 소스트리 기준이라 설치형에서 사용자 데이터 디렉토리(`%LOCALAPPDATA%\newauto Studio\`)로 이동시켜야 한다. (3) FFmpeg/OmniVoice/ComfyUI/Flow CDP 프로파일/LoRA 모델 외부 의존성을 설치 마법사로 검사·설치해야 한다.
- 포트 정책은 이미 `NEWAUTO_API_PORT=9002`로 정해져 있다. 1차본의 “동적 포트” 문구를 “기본 9002, Tauri sidecar 모드일 때만 사용 가능 포트 탐색 + stdout 핸드셰이크”로 정밀화한다.
- `port_9001_runtime_mismatch` 경고가 `agent_eval_smoke`에서 여전히 관측될 수 있다(원인: 시스템 Python 3.10이 9001을 점유). Phase 0에 “omnivoice_env Python 단일화”를 명시적 완료 기준으로 추가한다.
- 테스트 베이스라인 명령을 Phase 0에 박는다(`pytest -q`, `python -m mypy app`, `node --check app/static/app.js`). `tests/test_flow_uivision.py`는 현재 작업트리에서 삭제되어 있으므로 해당 회귀는 Playwright direct path 회귀로 대체한다.
- “렌더 플랜이 없는 MVP 경로(사진 업로드만)”에 대한 V1 fallback이 `start=0, end=0`을 반환하므로 MVP 모드에서도 동작하는 “photos-only render plan builder”를 명시한다.

요지: 1차본은 “엔진을 만들 필요 없이 껍데기와 UX를 짠다”에 가깝게 맞다. 다만 (a) 무엇이 이미 끝났는지, (b) 패키징 전환에서 정확히 무엇이 깨질지, (c) LM Studio 에이전트 트랙과 어떻게 합치할지가 빠져 있었다. 12·13절을 새로 추가한다.

## 1. 결론

> 2026-05-15 추가 결정: Media 단계는 별도 간소화 계획서
> `docs/media-simplification-plan-2026-05-15.md`를 우선 기준으로 한다.
> 기존 Flow/visual relevance/prompt repair/다중 fallback 중심의 복잡한 UI는 기본 화면에서
> 비활성화하고, `미디어 업로드`, `썸네일 업로드`, `출력 비율`, `줌+패닝 강도`,
> `대본 기반 LM Studio 프롬프트 일괄 생성`, `프롬프트 복사`, `LM Studio 종료 후 ComfyUI + LoRA 이미지 생성` 흐름만
> 기본 Media UX로 노출한다.
> 또한 사용자-facing 용어에서 `Flow`를 제거하고 `AI 이미지 생성`/`문장 이미지`로 치환한다.
> LM Studio에서 Gemma4 e8b로 모든 문장 프롬프트를 만든 뒤에는 `lms.exe unload <model>` 또는 명시적 사용자 안내로
> LM Studio를 종료/언로드하고, 그 다음 별도 `이미지 생성` 버튼으로 ComfyUI + LoRA를 실행한다.
> SQLite WAL 제안은 이미 `app/db.py`의 `PRAGMA journal_mode=WAL`/`busy_timeout=5000`으로 반영되어 있다.

`newauto`는 이미 핵심 엔진을 많이 갖고 있다. 현재 코드 기준으로 대본 저장, 문장 분할, 미디어 업로드, OmniVoice TTS, 자막 스타일, Ken Burns 계열 사진 움직임, BGM, 렌더, YouTube 업로드, Flow/ComfyUI 이미지 생성, Autopilot까지 기반이 있다. 따라서 1차 목표는 엔진을 새로 만드는 것이 아니라 다음 세 가지다.

1. Windows 앱 껍데기: 브라우저 탭 대신 `newauto Studio.exe`로 실행.
2. 편집 UX 재설계: 대본, 음성, 사진/Flow, 자막, 움직임, 최종 렌더를 한 화면의 작업 흐름으로 정리.
3. 제작 안정성: 문장별 타임라인, 음성 길이, 이미지 매칭, 자막 싱크, 진행률/오류 복구를 자동 점검.

추천 구조는 `Tauri + FastAPI sidecar + 기존 Python 엔진`이다. Tauri는 Windows에서 `.msi` 또는 `-setup.exe` 설치 파일을 만들 수 있고, Python/FastAPI 서버는 PyInstaller로 묶어 sidecar로 실행할 수 있다. Electron도 가능하지만 설치 용량과 메모리 면에서 Tauri가 더 알맞다.

## 2. 외부 도구 조사 요약

조사 기준: 2026년 현재 사용자가 실제로 기대하는 영상 자동화 기능.

| 도구 | 배울 점 | newauto에 반영할 기능 |
| --- | --- | --- |
| Pictory | 대본을 장면으로 나누고, 장면마다 영상/이미지, AI 음성, 자막을 자동 배치 | `대본 업로드 -> 문장/장면 분할 -> 장면 카드 생성 -> 자동 미디어 연결` |
| CapCut | 쉬운 효과 선택, 자막 스타일, 숏폼/가로 영상 프리셋 | 이미지 움직임 효과 갤러리, 자막 프리셋, 9:16/16:9 즉시 전환 |
| Descript | 텍스트 편집이 곧 타임라인 편집 | 대본 문장을 클릭하면 해당 음성/사진/자막 구간을 바로 편집 |
| VEED/InVideo | 템플릿 기반 빠른 제작, 자동 자막, 브라우저 기반 간편 UX | “빠른 자동 제작” 모드와 “고급 수동 조정” 모드 분리 |
| Runway/Kling 계열 | 이미지/텍스트 기반 생성 영상 | 1차는 사진 움직임과 Flow 이미지, 2차로 이미지-to-video API 연결 |

참고 자료:

- Pictory Script to Video: https://pictory.ai/pictory-features/script-to-video
- Pictory Text to Video with AI Voice-Over API 문서: https://docs.pictory.ai/guides/text-to-video/ai-voiceover
- Tauri Windows Installer: https://tauri.app/distribute/windows-installer/
- Tauri sidecar: https://tauri.app/fr/develop/sidecar/
- electron-builder NSIS: https://www.electron.build/nsis.html
- PyInstaller 사용 문서: https://www.pyinstaller.org/en/stable/usage.html

## 3. 현재 newauto 자산

이미 활용할 수 있는 내부 자산:

- `app/services/tts.py`: OmniVoice 로딩, 문장별 TTS 생성, 속도/언어/지시문/시드/후처리.
- `app/tts_profiles.py`: 여러 목소리 프리셋과 프로필 정규화.
- `app/services/subtitle.py`: ASS 자막 생성, 위치/크기/색/테두리/배경/효과.
- `app/services/render.py`: FFmpeg 렌더, 진행률, 이미지/영상/오디오 합성.
- `app/services/render_plan.py`: 장면별 미디어, motion, effect 계획.
- `app/services/flow_prompting.py`: 문장별 Flow 프롬프트 매니페스트와 asset 연결.
- `app/static/index.html`, `app/static/app.js`, `app/static/style.css`: 현재 웹 UI(약 6,400줄, 한글 정상 표시).
- `app/routers/render.py`, `app/routers/projects.py`, `app/routers/flow.py`, `app/routers/image_gen.py`, `app/routers/autopilot.py`, `app/routers/system.py`: API 기반 작업 흐름.
- `app/services/autopilot.py`, `app/workers/autopilot_worker.py`, `app/routers/autopilot.py`: URL/키워드/스크립트 입력에서 최종 렌더까지 “진행 버튼” 엔진. start/status/events/debug/pause/resume/cancel API 완비.
- `app/services/hpsl_script.py`, `app/services/script_compile.py`, `app/services/script_safety.py`: 대본 분할/Hook-Point-Story-Lesson 구조/위험 점수.
- `app/services/visual_brief.py`, `app/services/visual_planner.py`, `app/services/visual_vocab.py`, `app/services/visual_relevance.py`: 문장-이미지 의미 연결과 검증.
- `app/services/comfyui_client.py`, `app/services/comfyui_capabilities.py`, `app/services/comfyui_pipeline.py`, `app/services/image_generation_profiles.py`, `app/services/prompt_compiler.py`, `app/services/prompt_quality.py`, `app/services/prompt_repair.py`: ComfyUI/SDXL/LoRA/ControlNet/IPAdapter 경로.
- `app/services/text_health.py::looks_mojibake`, `app/services/source_fetch.py::_looks_mojibake`: 한글 mojibake 감지(이미 가동 중).
- `app/services/gpu_guard.py`, `app/services/usage_registry.py`, `app/services/tool_registry.py`, `app/services/model_registry.py`, `app/workers/worker_lock.py`: GPU/모델/도구 점유와 워커 락.
- `scripts/newauto_mcp.py`, `scripts/newauto_stepwise_mcp.py`, `scripts/lmstudio_openclaw_operator_mcp.py`, `scripts/lmstudio_direct_operator.py`, `lmstudio-do.cmd`: LM Studio/Cline MCP 통합 + 스텝와이즈 워크플로우(source_collect → hpsl_script → flow_prompts → flow_generate → flow_wait_sentence → tts_wait → render_wait).
- `scripts/flow_browser_automation.py`: Playwright + CDP 기반 Flow 직접 생성/다운로드 경로(MakeLens 패턴 채택).
- `tests/test_tts_*`, `tests/test_subtitle_rendering.py`, `tests/test_render_*`, `tests/test_flow_files.py`, `tests/test_feature_workflow.py`: 회귀 테스트 자산. `tests/test_flow_uivision.py`는 현재 작업트리에서 삭제됨(Playwright direct 경로로 대체 회귀 필요).

주의점:

- 1차본은 `app/static/index.html` mojibake를 지적했으나 현 시점 작업트리에서는 한글이 정상 표시된다. mojibake 위험은 “레거시 로그/소스 수집 캐시/OpenRouter·LM Studio JSON 응답”으로 좁힌다. 단, Windows 콘솔/배치 파일(`run-*.cmd`)을 손볼 때는 `chcp 65001`을 사용하고 BOM 없는 UTF-8 저장을 유지한다.
- 작업트리에 미커밋 변경이 많고 다수의 `*-plan.md`가 삭제 상태다(`git status` 참조). 구현 시 기존 변경을 보존하고 단계별 브랜치 또는 별도 PR 단위로 진행한다.
- 현 시점 활성 LLM은 LM Studio(`http://127.0.0.1:1234`) 위 Qwen3.5-9B 또는 Gemma4-e4b이며, `app/config.py::SCRIPT_LLM_MODEL` 기본값이 `qwen/qwen3.5-9b`다. Ollama fallback 경로는 살아 있다.

## 4. 목표 제품 UX

앱 이름 예시: `newauto Studio`

첫 화면은 랜딩 페이지가 아니라 바로 제작 화면이다.

### 4.1 좌측 작업 흐름

1. 프로젝트
2. 대본
3. 음성
4. 사진/Flow
5. 자막
6. 움직임
7. 렌더
8. 내보내기/YouTube

### 4.2 중앙 작업 영역

대본을 붙여넣거나 `.txt`, `.docx`, `.md`로 업로드한다. 저장하면 문장 단위로 자동 분할되고, 각 문장이 하나의 장면 카드가 된다.

장면 카드 필드:

- 문장 텍스트
- 예상 음성 길이
- 연결된 음성 파일
- 연결된 사진/Flow 생성 이미지
- 자막 미리보기
- 움직임 효과
- 경고 상태: 이미지 없음, 음성 없음, 자막 너무 김, 길이 불일치

### 4.3 우측 미리보기

현재 선택된 장면을 실시간으로 미리본다.

- 선택 사진
- 자막 위치/크기/색상/테두리 반영
- 움직임 효과 간이 재생
- 음성 샘플 재생

## 5. 기능 상세 계획

### 5.1 Windows 설치형 앱

권장 구현:

- Frontend: 기존 HTML/JS를 단계적으로 React 또는 Svelte로 정리. 1차는 기존 정적 UI를 그대로 Tauri WebView에 넣어도 된다.
- Desktop shell: Tauri 2.
- Backend sidecar: 기존 FastAPI 서버를 PyInstaller `onedir`로 패키징.
- Installer: Tauri NSIS `newauto Studio Setup.exe`.
- 앱 시작 시 Tauri가 sidecar를 띄우고, WebView가 `http://127.0.0.1:{dynamic_port}`에 접속한다.
- 종료 시 sidecar와 작업 큐를 정상 종료한다.

왜 Tauri인가:

- 현재 newauto는 Python/FastAPI 자산이 크다.
- Tauri는 기존 웹 UI를 재사용하면서 Windows 설치 파일을 만들 수 있다.
- Electron보다 가볍고, 장기적으로 파일 선택/폴더 선택/드래그앤드롭 같은 Windows 네이티브 기능을 붙이기 좋다.

대안:

- Electron: 개발은 빠르지만 용량과 메모리가 커질 수 있다.
- PySide6: 완전 Python 앱으로 가능하지만 현재 웹 UI와 API 자산을 많이 다시 만들어야 한다.

### 5.2 대본 업로드와 문장 분할

필수 기능:

- `.txt`, `.md`, `.docx`, 클립보드 붙여넣기.
- 한국어 문장 분할: 마침표, 물음표, 느낌표, 줄바꿈, 따옴표 처리.
- 너무 긴 문장 자동 쪼개기.
- 너무 짧은 문장 병합 옵션.
- 문장별 장면 번호 자동 생성.
- “대본 원본”과 “렌더용 분할본”을 분리 저장.

엔진 재사용:

- 한국어 문장 분할은 `app/text.py`(공통 splitter)와 `app/services/script_compile.py`(intro/body/bible 마커 분할, region-aware compile)에서 이미 처리한다. 새 splitter를 만들 필요 없음.
- 너무 긴/짧은 문장 자동 분할/병합은 `script_compile`의 region별 max length/min length 규칙으로 처리한다.

데이터 모델 보강(기존 `ScenePlanScene` + `RenderPlanSegment`에 합산):

| 새 필드(UI 카드용) | 저장 위치 | 비고 |
| --- | --- | --- |
| `locked` (bool) | `body_image_options.scene_overrides[idx].locked` 또는 `scene_plan.scenes[idx].locked`(NotRequired 추가) | 사용자가 “이 장면은 다시 생성하지 마라” 지정 |
| `voice_asset_path` | TTS는 `storage/projects/{pid}/tts/sentence_{idx:03}.wav`로 이미 결정적 → 신규 필드 불필요. `tts_run_manifest.json`에서 idx→실제 파일을 조회 |
| `voice_preset_override` | `tts_run_manifest.entries[idx].preset` 확장 | 문장별 목소리 변경 |
| `subtitle_override` | `subtitle_style` + (신규) `scene_plan.scenes[idx].subtitle_override: SubtitleStyle | None` | 장면별 자막 색/위치/효과 |
| `motion_preset` | `render_plan.segments[idx].motion`에 이미 존재 | 단순히 enum 확장 |
| `flow_status` | `flow_prompts.json` entries[idx].status에 이미 존재 (`pending|generated|attached|failed`) | UI에서 카드 뱃지로 노출 |

기존에 이미 있어 활용할 필드: `idx, sentence_idx, text, region, duration_sec, visual_intent, prompt, style, media_path, key_concept, visual_metaphor, subject, props, background, avoid, core_meaning, primary_keywords, secondary_keywords, subject_modes, must_show, may_show, prompt_hint, vocab_refs, domain`.

### 5.3 OmniVoice 음성 생성

현재 자산을 확장한다.

필수 UX:

- 목소리 프리셋: 남성 차분, 여성 밝음, 뉴스 앵커, 낮은 남성, 스토리텔러, 영어 등.
- 속도: 0.75x-1.25x.
- 문장별 생성 또는 전체 대본 생성 선택.
- 문장별 재생/재생성.
- 특정 문장만 목소리 변경.
- 샘플 듣기 후 “이 설정 잠금”.
- 실패 시 해당 문장만 재시도.

엔진 보강:

- word-level 또는 sentence-level timestamp를 저장해서 자막 싱크에 사용.
- 음성 길이와 목표 장면 길이를 비교해 자동으로 장면 시간을 조정.
- GPU 점유 상태를 앱 하단에 표시.

### 5.4 사진 업로드와 Flow 연결

두 가지 입력을 같은 장면 타임라인에 연결한다.

모드 A: 사진 직접 업로드

- 장수 제한 없음.
- 드래그앤드롭.
- 파일명/촬영일/선택 순서 기준 정렬.
- 썸네일 그리드에서 순서 변경.
- 문장 수보다 사진이 적으면 반복/자동 배분.
- 사진이 많으면 장면별 후보로 보관.

모드 B: 대본 기반 Flow 생성

- 대본을 문장별로 분할.
- 각 문장에 Flow 프롬프트 자동 생성.
- Flow 결과 이미지가 들어오면 해당 문장 카드에 자동 연결.
- 이미지가 문장 의미와 맞지 않으면 `visual_relevance` 검사로 경고.
- Flow 실패 시 ComfyUI fallback 또는 업로드 이미지 fallback.

### 5.5 자막 편집

이미 있는 `SubtitleStyle`을 UI로 제대로 노출한다.

필수 옵션:

- 글꼴
- 크기
- 색상
- 테두리 색상/두께
- 그림자
- 배경 박스 색상/투명도
- 위치: 상단, 위쪽, 중앙, 아래쪽, 하단
- 좌우/상하 여백
- 줄 길이
- 최소 표시 시간
- 효과: 없음, 페이드, 팝, 가라오케

추가해야 할 고급 옵션:

- 숏폼용 큰 자막 프리셋.
- 뉴스형 하단 자막 프리셋.
- 감성 내레이션 프리셋.
- “현재 자막이 화면 밖으로 나감” 자동 검사.
- 실시간 자막 미리보기.

### 5.6 사진 움직임 효과

첨부 이미지의 “강렬한 움직임 / 보통 움직임 / 움직임 없음”을 기본으로 두고, 고급 프리셋을 추가한다.

기본:

- 움직임 없음
- 보통 움직임: 느린 확대/축소
- 강렬한 움직임: 큰 줌, 좌우 팬, 약한 흔들림

고급:

- Slow Zoom In
- Slow Zoom Out
- Pan Left
- Pan Right
- Pan Up
- Pan Down
- Parallax Light
- Push In + Fade
- Documentary Hold
- Beat Cut

엔진:

- `render_plan.py`의 `motion` 값을 enum으로 확장.
- FFmpeg filter graph에서 scale/crop/x/y expression으로 구현.
- 자막과 이미지 움직임이 따로 움직이도록 자막은 최종 overlay 단계에서 합성.

### 5.7 최종 렌더

“진행” 버튼 하나로 전체 파이프라인을 실행한다.

실행 순서:

1. Preflight: FFmpeg, OmniVoice, 저장 폴더, GPU, 미디어 누락 검사.
2. 대본 문장 분할 확정.
3. TTS 누락 문장만 생성.
4. Flow/이미지 누락 장면만 생성 또는 업로드 이미지 배분.
5. Render plan 생성.
6. 자막 ASS 생성.
7. FFmpeg 렌더.
8. 최종 결과 미리보기.
9. 저장 폴더 열기 / YouTube 업로드 선택.

진행률 표시:

- STEP 1/7 대본 점검
- STEP 2/7 음성 생성
- STEP 3/7 이미지 준비
- STEP 4/7 장면 합성
- STEP 5/7 자막 합성
- STEP 6/7 인코딩
- STEP 7/7 결과 검사

## 6. 화면 설계

### 6.1 메인 제작 화면

왼쪽: 프로젝트/작업 단계  
가운데: 장면 리스트  
오른쪽: 미리보기/설정 패널  
하단: 전체 진행률/로그/오류 복구 버튼

### 6.2 첨부 이미지 스타일 반영

첨부 이미지는 어두운 배경, 큰 섹션 제목, 파일 선택 버튼, 선택 상태, 진행률이 명확하다. 이것을 유지하되 더 전문적인 데스크톱 앱으로 다듬는다.

디자인 원칙:

- 어두운 작업형 UI.
- 섹션별 아이콘.
- 카드 남발 금지, 장면 목록과 설정 패널 중심.
- 중요한 버튼은 `진행`, `미리보기`, `재생성`, `렌더`.
- 파일 선택은 Windows 파일 다이얼로그.
- 장면 목록은 드래그로 순서 변경.

## 7. 구현 로드맵

### Phase 0: 안정화

기간: 1-2일

- 작업트리 미커밋 변경 정리(`git status`상 다량의 변경 + 삭제된 plan 문서). 패키징 전환 PR과 충돌하지 않도록 베이스라인 커밋을 만든다.
- 한글 mojibake 잔존 범위는 “레거시 로그/캐시/외부 API JSON”으로 좁히고, 현재 UI는 정상 표시되므로 별도 수정 불필요(0절 참고).
- UTF-8 규칙 점검 체크리스트:
  - `app/main.py::_spawn_worker`가 워커 로그를 `encoding="utf-8"`로 연다(확인 완료).
  - `app/db.py::update_project`의 JSON 직렬화가 `ensure_ascii=False`다(확인 완료).
  - 모든 `*.cmd`는 첫 줄 `chcp 65001 >NUL`. (현 `run-*.cmd`는 일부에만 적용)
- omnivoice_env Python 단일화:
  - `port_9001_runtime_mismatch` 경고가 사라질 때까지 `scripts/agent_eval_smoke.py --skip-web` 결과 `runtime_matches_expected=true` 보장.
  - 9001/9002 동시 점유 시 9001 측 시스템 Python 3.10 프로세스를 정리한다.
- 테스트 베이스라인 명령 고정(README 또는 `scripts/final_verification.ps1`에 박는다):
  - `python -m pytest -q tests/test_tts_pipeline.py tests/test_subtitle_rendering.py tests/test_render_visual_track.py tests/test_feature_workflow.py`
  - `python -m mypy app` (또는 omnivoice_env 한정 서브셋)
  - `node --check app/static/app.js`
  - `python -m py_compile app scripts`
- `tests/test_flow_uivision.py`를 Playwright direct 경로로 대체하는 `tests/test_flow_playwright_direct.py` 스켈레톤을 추가하고 회귀 픽스처를 옮긴다(엔드 투 엔드는 별도, 단위 가능한 부분만).

완료 기준:

- 베이스라인 명령 4종이 모두 green.
- `agent_eval_smoke --skip-web`가 `ok=true`이고 runtime 경고 없음.
- 프로젝트 생성부터 렌더까지 기존 기능이 깨지지 않음(체크리스트 프로젝트 1개 실 렌더 통과).

### Phase 1: Windows 앱 껍데기

기간: 4-7일(1차본 2-4일에서 상향: PyInstaller 워커 인보케이션, AppData 경로 이전, FFmpeg/OmniVoice/ComfyUI 의존성 처리가 추가됨)

- `src-tauri` 추가, Tauri 2 NSIS 빌드 활성화.
- PyInstaller `--onedir`로 FastAPI 서버 빌드. **`sys.executable`로 워커를 재호출하는 현 구조는 그대로 작동하지 않으므로** 다음 중 하나를 채택한다:
  1. (권장) `app/main.py`에 `--worker {render|tts|image|source_draft|autopilot}` 서브커맨드를 도입하고, `_spawn_worker`가 동일 바이너리를 자기-호출하도록 변경한다. 이 패턴은 PyInstaller에서 안전하다.
  2. 워커를 메인 프로세스 내 daemon threads/`asyncio` task로 통합한다(GIL/torch 사용 워커는 그대로 별 프로세스가 안전하므로 1안 권장).
- 사용자 데이터 디렉토리 이전:
  - `app/config.py`의 `STORAGE_DIR/DB_PATH/PROJECTS_DIR/OAUTH_DIR/...`이 소스트리 기준이다. `%LOCALAPPDATA%\newauto Studio\`(또는 `NEWAUTO_DATA_DIR` env)로 옮길 수 있게 한다.
  - 우선순위: `NEWAUTO_DATA_DIR` 환경변수 → `%LOCALAPPDATA%\newauto Studio` → 소스트리(개발 모드).
  - 첫 실행 시 빈 디렉토리를 만들고 마이그레이션 안내(기존 사용자는 손수 복사).
- 외부 의존성 부트스트랩 마법사:
  - FFmpeg: `winget install Gyan.FFmpeg` 또는 번들 zip.
  - OmniVoice/torch: 별도 venv 또는 사용자 기존 omnivoice_env 탐색.
  - ComfyUI: 설치 경로 확인(`COMFYUI_INSTALL_DIR` 기본 `C:\Users\petbl\autotube\ComfyUI`).
  - Flow CDP 프로파일: 첫 실행 시 사용자가 로그인하도록 Chrome 또는 Edge를 띄워준다.
- 포트 정책:
  - Tauri sidecar는 PyInstaller 바이너리를 띄우면서 `--listen 127.0.0.1:0`(0이면 사용 가능 포트 자동 선택)을 넘기고, FastAPI는 startup 후 실제 바인딩 포트를 stdout 한 줄로 출력(`NEWAUTO_LISTEN_PORT={n}`)한다. Tauri는 그 줄을 파싱해 WebView 시작 URL을 결정한다.
  - 기존 `NEWAUTO_API_PORT=9002`는 개발 모드 기본값으로 남긴다.
- 종료 처리: Tauri `on_close` 핸들러가 `/api/system/shutdown`(신규)을 호출하고, FastAPI는 워커들에게 graceful shutdown 신호를 보낸 뒤 종료한다. `worker_lock.py`의 lock 파일은 종료 시 정리한다.

완료 기준:

- `newauto Studio Setup.exe` 한 번으로 다른 Windows PC에 설치되고, 첫 실행 마법사가 FFmpeg/Python/ComfyUI/OmniVoice 상태를 진단해 부족한 항목을 안내한다.
- 설치 후 첫 실행에서 빈 프로젝트 생성 → 사진 1장 업로드 → 짧은 TTS 1문장 → 1초 렌더가 동작한다.
- 종료 후 잔존 프로세스/락 파일이 없다.

### Phase 2: 장면 중심 데이터 모델 보강

기간: 2-3일(1차본 3-5일에서 단축: ScenePlanScene/RenderPlanSegment가 이미 충분히 풍부함)

- `ScenePlanScene`에 NotRequired 필드 추가: `locked: bool`, `subtitle_override: SubtitleStyle | None`.
- `RenderPlanSegment.motion`을 enum화: 기존 `none/slow_zoom_in/slow_zoom_out/still_locked/micro_motion_locked` + 신규 `pan_left/pan_right/pan_up/pan_down/parallax_light/push_in_fade/documentary_hold/beat_cut`. `app/services/render.py::_zoompan_filter`/`_segment_effect_filter`에 분기 추가.
- “photos-only MVP 경로”용 `app/services/render_plan.py::build_render_plan` V1 fallback 보강:
  - 현재 V1 분기는 `start=0, end=0`만 반환한다. scene_plan이 없을 때도 `media_order`와 평균 듀레이션(`tts_run_manifest.total_duration / len(media)`)으로 segment 시간을 계산해 렌더가 곧장 돌도록 만든다.
- 문장 카드 API: `GET /api/projects/{pid}/scene-cards` (기존 `scene-plan`을 카드 뷰로 평탄화) + `PATCH /api/projects/{pid}/scene-cards/{idx}` (locked/subtitle_override/motion override 저장).
- 호환 어댑터: 기존 `sentences`/`media_order` 경로에서 생성된 프로젝트도 카드 뷰가 동작해야 한다.

완료 기준:

- 기존 프로젝트를 열면 카드가 즉시 생성된다(빈 carrier 포함).
- `locked=true` 카드는 autopilot 재실행 시 재생성 대상에서 제외된다.
- 사진만 업로드한 MVP 프로젝트가 `진행` 한 번으로 mp4까지 떨어진다.

### Phase 3: 새 제작 UI

기간: 5-8일

- 대본 업로드 화면.
- 장면 리스트.
- 사진 무제한 업로드와 드래그 정렬.
- OmniVoice 프리셋/속도/샘플 듣기.
- 자막 스타일 패널.
- 움직임 효과 갤러리.
- 오른쪽 미리보기.

완료 기준:

- 사용자가 한 화면에서 대본, 음성, 사진, 자막, 움직임을 조정할 수 있음.

### Phase 4: Flow/ComfyUI 연결 고도화

기간: 4-7일

- 문장별 Flow 프롬프트 생성 UI.
- Flow 결과 이미지 자동 감지/연결.
- 실패 장면만 재생성.
- visual relevance 경고 표시.

완료 기준:

- 대본 문장마다 Flow 이미지가 연결되고, 누락/불일치가 장면 카드에 표시됨.

### Phase 5: 렌더 파이프라인 통합

기간: 2-4일(단축: autopilot 엔진은 이미 존재. 작업은 UI/검사 패널/카드 결합)

- 원클릭 `진행` 버튼은 `POST /api/projects/{pid}/autopilot/start`에 매핑한다(이미 존재).
- 단계별 진행률은 `GET /api/projects/{pid}/autopilot/status` + `events`를 풀링해 좌측 작업 단계 UI에 표시.
- 실패 시 재시도는 `autopilot/pause + resume`을 활용하고, `last_failure.json`의 `action_hint` 메시지를 카드에 노출.
- 최종 검사 패널은 기존 자산 결합:
  - `GET /api/projects/{pid}/preflight` → STEP 1
  - `GET /api/projects/{pid}/render-report` → STEP 6
  - `GET /api/projects/{pid}/final-scene-review` → STEP 7
  - `GET /api/projects/{pid}/operator-summary` → 하단 시스템 로그
- 가로/세로 동시 렌더는 `render_formats: ["landscape", "shorts"]`로 이미 지원(현 `RenderFormat` 리스트). UI에서 체크박스 노출.
- 워치독: `app/main.py`의 `_start_render_watchdog`는 30초마다 5종 stale 잡을 회수한다. 패키지에서도 동일하게 동작하도록 워커 PID 추적을 lockfile에 통합한다.

완료 기준:

- 대본과 사진만 넣고 `진행`을 누르면 최종 mp4 + thumbnails + report가 한 화면에 표시된다.
- 중간에 강제 종료 후 재실행해도 stale 잡이 자동 회수되고 사용자에게 “복구됨” 토스트가 뜬다.

### Phase 6: 제품화

기간: 3-5일

- 설치 파일명/버전.
- 앱 데이터 폴더 정책.
- 로그 폴더 열기.
- 자동 업데이트 후보 검토.
- 샘플 프로젝트 포함.
- 사용자용 간단 매뉴얼.

완료 기준:

- 다른 Windows PC에서 설치 후 기본 샘플 렌더 성공.

## 8. 기술 리스크와 대응

| 리스크 | 대응 |
| --- | --- |
| OmniVoice/torch 패키징 용량 큼 | 1차는 로컬 개발 PC 설치형, 2차로 모델 다운로드/검사 마법사 제공. PyInstaller bundle에 torch를 포함하지 말고 사용자 omnivoice_env를 탐색·연결 |
| PyInstaller bundle에서 워커 재호출 실패 | `app/main.py`에 `--worker {name}` 서브커맨드 도입, `_spawn_worker`가 동일 바이너리 자기-호출. (현 `sys.executable -m app.workers.*`는 dev에서만 동작) |
| 소스트리 기준 storage 경로 | `NEWAUTO_DATA_DIR` env 우선, 기본 `%LOCALAPPDATA%\newauto Studio`. `app/config.py` 모듈 임포트 시점 mkdir에 주의(권한 부족 시 fall back to `%TEMP%`) |
| GPU/LLM/ComfyUI 동시 점유 | 이미 있는 `gpu_guard`, `worker_lock`, `usage_registry`, `tool_registry`, `model_registry` 확장. 설치형에서는 동시 점유를 1로 강제 |
| 자막 싱크 밀림 | 음성 실제 길이와 word/sentence timing 기반으로 렌더 플랜 생성(이미 `app/services/transcribe.py::save_word_timings` + `subtitle.py::_prepare_display_timings` 가동 중) |
| Flow 자동화 실패 | Flow 실패 장면만 ComfyUI 또는 업로드 이미지로 fallback(`visual_source_mode=flow_then_comfyui_fallback`이 이미 구현됨) |
| 한글 경로/파일명 문제 | 모든 내부 경로는 UTF-8, FFmpeg 인자 list 전달, 임시 파일은 ASCII-safe slug 병행. `_escape_filter_path`/`_sanitize_filename`가 이미 가동 중 |
| 설치형 앱에서 백엔드 포트 충돌 | Tauri sidecar는 `--listen :0`으로 부팅, FastAPI가 stdout으로 실제 포트 통보 → WebView가 그 포트에 연결. 개발 모드 기본 9002 유지 |
| port 9001/9002 런타임 불일치 | `agent_eval_smoke`가 이미 감지. Phase 0 완료 기준에 “runtime 경고 0건” 박음 |
| Flow CDP 프로파일이 다른 PC에 없음 | 첫 실행 마법사가 빈 Chrome 프로필을 만들고 Flow 로그인 안내 |
| FFmpeg/ComfyUI 미설치 | 부트스트랩 마법사에서 `winget` 또는 manual 안내. 미설치 상태에서도 “사진+TTS+자막 렌더”까지는 동작 |
| LM Studio 미실행 | 13절의 Optional 분기로 LLM 기능 비활성 모드 제공. autopilot은 “스크립트 직접 작성” 경로로 fallback |
| ComfyUI 미실행 | `visual_source_mode=upload_only`로 fallback. preflight가 이미 검출 |
| Tauri WebView CSP/CORS | sidecar 백엔드는 동일 호스트에서 동작하므로 same-origin. Tauri config `csp`에 `connect-src 'self' http://127.0.0.1:*` 명시 |
| 워커 grandchild 누수 | 종료 시 lockfile 기반 PID 회수 + JobObject(`AssignProcessToJobObject`)로 Tauri 종료 시 자식 모두 정리 |

## 9. MVP 범위

가장 먼저 만들 버전은 다음까지만 포함한다.

- Windows 앱으로 실행.
- 대본 텍스트 업로드/붙여넣기.
- 문장별 장면 카드.
- OmniVoice 목소리/속도 선택.
- 사진 무제한 업로드와 순서 변경.
- 자막 위치/크기/색/테두리.
- 움직임 없음/보통/강렬함.
- 세로 1080x1920, 가로 1920x1080.
- `진행` 버튼으로 최종 렌더.

MVP에서 미루는 것:

- 복잡한 멀티트랙 편집.
- 이미지-to-video 생성.
- 클라우드 협업.
- 자동 업데이트.
- 완전한 음성 클로닝 UI.

## 10. 첫 구현 작업 목록

1. Phase 0 베이스라인 4종 명령(`pytest -q`, `mypy app`, `node --check`, `py_compile`)을 `scripts/final_verification.ps1`에 박고 green 확인.
2. `port_9001_runtime_mismatch` 해결(omnivoice_env Python 단일화) — `agent_eval_smoke --skip-web` runtime 경고 0건.
3. `app/config.py`에 `NEWAUTO_DATA_DIR` 지원 추가, 기존 경로를 lazy resolver로 감싸기(소스트리 기본값 유지).
4. `app/main.py`에 `--worker {render|tts|image|source_draft|autopilot}` 서브커맨드 도입, `_spawn_worker`를 자기-호출 패턴으로 전환.
5. `app/services/render_plan.py` V1 fallback에 평균 듀레이션 기반 segment 시간 계산 추가(MVP photos-only 경로).
6. `ScenePlanScene`에 `locked`/`subtitle_override` NotRequired 필드 추가, `db._load_scene_plan`/`update_project` 직렬화 동기화.
7. `motion` enum 확장 + `app/services/render.py`의 zoompan/pan/parallax 필터 분기.
8. 카드 API: `GET/PATCH /api/projects/{pid}/scene-cards` 추가.
9. `docs/windows-app-architecture.md` 작성(이 문서의 12·13절을 분리 정리).
10. `src-tauri` 최소 앱 추가, Sidecar 바이너리 자리표시자, stdout 포트 핸드셰이크.
11. PyInstaller `--onedir` 빌드 스크립트 + 의존성 점검 마법사 1차.
12. NSIS 설치 파일 생성 검증(다른 Windows PC에서 빈 프로젝트 1개 렌더 통과).
13. 자막 프리셋(숏폼/뉴스/내레이션) 저장·불러오기 UI.
14. LM Studio 트랙 통합(13절): Tauri 메뉴 → “AI 모드” 켜기/끄기, 켜지면 `lmstudio-do.cmd` 또는 직접 HTTP API.

## 11. 최종 제품 비전

`newauto Studio`의 강점은 “영상 편집기”가 아니라 “대본 기반 자동 제작 공장”이다. CapCut처럼 예쁘게 조정할 수 있고, Pictory처럼 대본에서 자동으로 만들고, Descript처럼 문장을 타임라인처럼 다루며, newauto만의 OmniVoice/Flow/ComfyUI/로컬 렌더 자산으로 비용과 통제권을 잡는 방향이 가장 좋다.

사용자가 해야 할 일은 세 가지면 충분해야 한다.

1. 대본을 넣는다.
2. 목소리와 사진/Flow 방식을 고른다.
3. 진행을 누른다.

나머지는 앱이 문장별로 음성, 이미지, 자막, 움직임, 렌더 상태를 책임진다.

## 12. 코드/DB/워크플로우 대비 차이와 보강 항목 (2026-05-15)

### 12.1 이미 존재해 “구현”이 아니라 “노출”만 필요한 자산

| 1차본이 “추가” 또는 “설계”라 부른 항목 | 실제 상태 | 위치 |
| --- | --- | --- |
| 문장별 분할 | 완료 | `app/text.py`, `app/services/script_compile.py` |
| 장면 모델(`scene_id, sentence_idx, text, ...`) | 거의 완료 | `ScenePlanScene` + `RenderPlanSegment`(types.py 303-352) |
| 자막 스타일(글꼴/크기/색/테두리/그림자/배경/위치/여백/줄길이/최소표시/효과) | 완료 | `app/services/subtitle.py` + `app/types.py::SubtitleStyle` |
| OmniVoice 프리셋, 속도, 샘플 듣기 | 완료 | `app/tts_profiles.py`, `app/routers/render.py::generate_tts_preview` |
| Flow 프롬프트 매니페스트와 asset 연결 | 완료 | `app/services/flow_prompting.py`, `app/routers/flow.py` |
| ComfyUI 자동 이미지 + Flow Assisted/Auto + fallback | 완료 | `visual_source_mode` enum + `comfyui_pipeline.py` + `flow_browser_automation.py` |
| 원클릭 진행 엔진 | 완료 | `app/routers/autopilot.py` + `app/services/autopilot.py` + `app/workers/autopilot_worker.py` |
| Preflight, render-report, operator-summary, final-scene-review | 완료 | `app/services/preflight.py`, `render_report.py`, `operator_summary.py` |
| stale 잡 복구 + heartbeat watchdog | 완료 | `app/db.py::recover_stale_*` + `app/main.py::_start_render_watchdog` |
| GPU/모델/도구 점유 가드 | 완료 | `gpu_guard.py`, `usage_registry.py`, `tool_registry.py`, `model_registry.py` |
| LM Studio MCP stepwise 워크플로우 | 완료 | `scripts/newauto_stepwise_mcp.py`(source_collect → hpsl → flow → tts → render) |
| LM Studio 직접 디스패처(Cline 없이) | 완료 | `scripts/lmstudio_direct_operator.py`, `lmstudio-do.cmd` |
| Brave/DuckDuckGo 소스 수집 fallback | 완료 | `app/services/source_fetch.py`, `app/services/web_search.py` |
| Visual relevance/visual mismatch report | 완료 | `app/services/visual_relevance.py` |
| YouTube 업로드 + 예약 + 썸네일 | 완료 | `app/routers/youtube.py`, `app/services/yt_upload.py` |

Phase 3/4/5의 작업 비중은 “기존 API를 카드 UI에 묶고 라벨/뱃지/액션 버튼을 깔끔하게 노출하는 것” 이 절대 다수다.

### 12.2 잘못 가정했거나 누락된 사실

1. `app/static/index.html`의 mojibake는 현 작업트리에서 확인되지 않는다. 한글이 정상 표시된다. 따라서 Phase 0의 우선순위에서 “UI 한글 인코딩 복구”를 빼고, 대신 `port_9001_runtime_mismatch` 해결 + 베이스라인 테스트 green을 박는다.
2. 1차본의 “동적 포트”는 모호하다. 실제 코드는 `NEWAUTO_API_PORT=9002`로 단일화돼 있다. Tauri sidecar 도입 시점에 “sidecar는 `:0`으로 부팅하고 stdout으로 실제 포트 통보 → Tauri가 그 포트로 WebView 시작” 패턴을 명시.
3. 1차본의 “장면 모델 추가”는 사실상 중복이다. `ScenePlanScene`이 이미 풍부하고 `RenderPlanSegment`가 motion/effect/caption_style을 갖는다. 추가 필드는 `locked` + `subtitle_override` 두 개로 충분하다.
4. PyInstaller `--onedir` 패키지에서 `sys.executable -m app.workers.*` 패턴은 동작하지 않는다(번들 진입점은 모듈 호출이 아님). `app/main.py`에 워커 서브커맨드를 도입해야 한다.
5. 사용자 데이터 위치 정책이 없다. 소스트리 `storage/`가 그대로 패키지에 들어가면 권한 문제 + 업데이트 시 사용자 데이터 손실 위험.
6. `tests/test_flow_uivision.py`는 작업트리에서 삭제됐다. Ui.Vision 경로는 Playwright direct로 대체됐다. 회귀 테스트도 갈아끼워야 한다.
7. 1차본은 LM Studio/MCP 에이전트 트랙을 언급하지 않는다. 최근 2주(5/06–5/15) 작업의 절반 이상이 그 트랙이고, 그게 곧 “자동 모드”의 사용자 입장 가치다. 13절을 별도로 추가.

### 12.3 새로 잡아야 할 아키텍처 결정

- **데이터 디렉토리 정책 (P0)**: env `NEWAUTO_DATA_DIR` → `%LOCALAPPDATA%\newauto Studio\` → 소스트리. `app/config.py`를 lazy resolver로 감싸고 모든 `mkdir`를 `STORAGE_DIR` 결정 직후로 옮긴다.
- **워커 인보케이션 패턴 (P0)**: `app/main.py`에 `python -m app.main --worker render` 식 서브커맨드를 도입. 패키지 내에선 `newauto-studio.exe --worker render`로 자기-호출.
- **포트 핸드셰이크 (P1)**: `app/main.py` startup 콜백이 `print(f"NEWAUTO_LISTEN_PORT={server.servers[0].sockets[0].getsockname()[1]}", flush=True)`. Tauri sidecar `OnStdout` 핸들러가 파싱.
- **외부 의존성 진단/설치 마법사 (P1)**: 첫 실행 시 `/api/system/diagnostics`(이미 존재)를 호출해 5종 의존성(FFmpeg, OmniVoice/torch, ComfyUI, LM Studio, Chrome) 상태를 카드로 표시. 부족 항목은 `winget` 또는 수동 안내 링크.
- **Tauri 종료 시 자식 정리 (P1)**: Windows JobObject 활용 + lockfile 기반 PID 정리. `worker_lock.py`에 “shutdown sweep” 추가.
- **자동 업데이트 (P2)**: Tauri 2 updater + 코드 사인 인증서. 1차 MVP에선 빼고 2차에서 추가.

### 12.4 회귀 테스트 보강

Phase 0 베이스라인에 추가:

- `tests/test_render_visual_track.py`(이미 변경됨) green 유지.
- 신규 `tests/test_data_dir_resolution.py`: `NEWAUTO_DATA_DIR` env 우선순위 + `%LOCALAPPDATA%` fallback.
- 신규 `tests/test_worker_self_invocation.py`: `python -m app.main --worker render` 진입이 5초 안에 lockfile을 만들고 정상 종료.
- 신규 `tests/test_render_plan_photos_only.py`: scene_plan 없이 `media_order`만 있는 프로젝트의 V1 fallback이 segment 시간을 0이 아니게 계산.
- `tests/test_flow_playwright_direct.py`로 `tests/test_flow_uivision.py` 대체 회귀 옮김.
- `scripts/agent_eval_smoke.py --skip-web`을 CI 베이스라인에 포함(runtime mismatch가 다시 들어오는 회귀 차단).

## 13. LM Studio/MCP 에이전트 트랙 통합

newauto Studio가 두 가지 자동화 레이어를 갖도록 분리한다.

**레이어 A — 결정적 파이프라인(현재 autopilot 엔진)**:
1. 대본 → 문장 분할 → TTS → 이미지(Flow/ComfyUI/Upload) → 자막 → 렌더 → 업로드.
2. 1차 MVP의 “진행” 버튼이 호출하는 흐름.
3. 사용자 입력 없이 결정적으로 동작.

**레이어 B — 에이전트 보조(현재 LM Studio + MCP)**:
1. 대본/소스가 모호하거나, “URL 한 줄 → 영상까지” 같은 자유 입력을 처리.
2. `scripts/newauto_stepwise_mcp.py` + `lmstudio_direct_operator.py` 사용.
3. LM Studio가 안 떠 있으면 자동 비활성, 사용자는 레이어 A만으로 충분히 작업 가능.

### 13.1 통합 모드

UI 우상단에 “AI 모드” 토글 (기본 OFF):

- OFF: 레이어 A만 노출. autopilot 엔진이 사용자 입력으로 채워진 필드를 그대로 실행.
- ON: 좌측 1번 단계에 “URL/키워드/주제만 적기” 입력칸 + “HPSL 자동 작성” 버튼이 활성화된다. 클릭 시 Tauri는 `lmstudio-do.cmd` 또는 `127.0.0.1:1234/v1/chat/completions`를 직접 호출하거나, `newauto-stepwise-mcp`를 통해 단계별 승인 워크플로우로 분기한다.

### 13.2 LM Studio 헬스 체크

- 첫 실행 + AI 모드 ON 시 `GET http://127.0.0.1:1234/v1/models` 호출.
- 모델 누락 시 안내: “LM Studio에 `qwen/qwen3.5-9b` 또는 `google/gemma-4-e4b`를 로드하세요.”
- 컨텍스트 길이 점검: `scripts/check_cline_lmstudio_health.py --context-target 88000`을 내부적으로 실행. 부족 시 경고.

### 13.3 MCP 통합 선택지

권장 기본값: 외부 MCP 미사용. Tauri 앱이 LM Studio HTTP API와 newauto API를 직접 호출한다(이 편이 패키징과 권한이 단순).

선택 기능: Cline/MCP 사용자에게 `run-newauto-stepwise-mcp.cmd`를 그대로 제공(앱이 “MCP 서버 시작” 메뉴를 노출). 이 경우 `FLOW_AUTOMATION_BACKEND=playwright`, `NEWAUTO_API_PORT=9002` 같은 환경 변수가 자동 설정되도록 한다.

### 13.4 에이전트 안전 가드

- 에이전트가 `run_powershell` 등 OpenClaw operator 도구를 호출할 때는 destructive 명령(`Remove-Item -Recurse`, `Stop-Process`, `winget uninstall`)을 `approval_required`로 막는다(이미 구현됨, `command_policy.py` 계열).
- 에이전트가 사용자 데이터 디렉토리(`NEWAUTO_DATA_DIR`) 바깥에 쓰지 못하도록 화이트리스트 강제.
- 모든 에이전트 호출 로그는 `storage/agent_evals/`에 누적해 추적 가능.

### 13.5 13절의 완료 기준

- LM Studio가 꺼져 있어도 레이어 A는 정상 동작.
- LM Studio가 켜져 있고 AI 모드 ON일 때, 사용자는 URL 하나 + 진행 버튼만으로 mp4를 받는다.
- AI 모드 ON에서 destructive 명령을 시도하면 모달 승인 창이 뜬다.
- `agent_eval_smoke --skip-web`이 패키지 환경에서도 ok=true를 반환한다.
