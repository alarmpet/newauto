# Korean ComfyUI E2E Test Video Plan

## 2026-04-27 P0 Audio Update

- `[Done]` TTS tail silence trim added before each sentence WAV is written.
- `[Done]` Sentence timing now includes an intentional `0.3s` gap between sentences.
- `[Done]` Render audio concat inserts explicit silence WAV segments between sentence files.
- `[Done]` Loudnorm output is now forced to `24000Hz mono pcm_s16le`.
- `[Done]` Render now fails if raw vs normalized audio duration drift exceeds `1.0s`.
- `[Next]` P1 stays focused on Korean -> English visual prompt translation and prompt manifest storage.

상태: `[Completed - sample produced with detached ComfyUI stderr workaround]`

현재 구현 상태:

- `[완료]` `seed_mode=fixed/per_sentence` 백엔드/manifest 경로 구현
- `[완료]` ComfyUI smoke helper `scripts/check_comfyui_smoke.py` 추가
- `[완료]` ComfyUI smoke 실측 재현 및 우회 확인
  - `8188` 기존 인스턴스: `ComfyUI KSampler failed: [Errno 22] Invalid argument`
  - `8190` 기본 옵션 인스턴스: 동일 오류 재현
  - `8193` stderr file redirect detached 인스턴스: smoke 성공
  - `8188`도 동일한 detached file redirect 방식으로 재기동 후 smoke 성공
- `[완료]` 한글 대본 + ComfyUI 실이미지 + 최종 MP4 재생성
  - 프로젝트: `9ee64e214b2c`
  - 산출물: `storage/projects/9ee64e214b2c/output.mp4`

## 0. 품질 재검토 반영

참조 문서: `C:\Users\petbl\.gemini\antigravity\brain\dbc65872-79d3-4fb5-9446-d57a5569768d\implementation_plan.md`

최근 샘플 `9ee64e214b2c`는 E2E 성공 샘플이지만, 최종 품질 기준으로는 아래 문제가 남아 있다.

| 항목 | 코드/워크플로우 확인 결과 | 반영 결정 |
|---|---|---|
| 이미지 흐림 | 수동 E2E는 `768x432`로 생성했고 렌더는 `1920x1080`이라 확대 비율이 큼. Autopilot 기본은 이미 `1024x576`으로 되어 있음. | 수동/테스트/E2E 기본도 `1024x576`으로 통일, 렌더 전 이미지 해상도 guard 추가 |
| 이미지-대본 관련성 | `image_prompting.py`가 한글 문장을 그대로 SDXL prompt에 넣음. SDXL CLIP에는 약함. | Ollama/Gemma4 기반 한글 대본 -> 영어 시각 프롬프트 변환기 추가 |
| 목소리 일관성 | `seed_mode=fixed`는 구현됨. 다만 샘플은 `duration=7.5`를 강제해 문장별 자연 길이를 방해함. | `duration=None` 기본으로 되돌리고 fixed seed만 유지 |
| TTS 무음 | `duration=7.5` 강제가 짧은 문장 뒤 무음을 만들 가능성이 큼. | tail silence trim, 문장 간 0.3초 intentional silence 삽입 |
| loudnorm 출력 | `_normalize_audio()`가 `-ar 24000 -ac 1`을 명시하지 않음. | loudnorm 후 sample rate/channel 고정 및 raw/normalized duration guard 추가 |
| ComfyUI steps | workflow 기본 `steps=20` | 품질 샘플 기본은 `30`으로 상향, 8GB VRAM에서 OOM이면 20 fallback |
| placeholder 타입 | exact placeholder는 int로 들어가지만 검증이 약함 | rendered workflow의 `width/height/seed` 타입 검증 테스트 추가 |

### 다음 구현 순서

1. `[P0]` TTS 자연 길이/무음 개선
   - `duration=None`을 한글 E2E/Autopilot 기본으로 사용
   - 기존 preset 자체는 `duration=None` 유지 확인
   - tail silence trim 함수 추가
   - `_concat_audio()`에서 문장 사이 0.3초 silence pad를 의도적으로 삽입
   - `_normalize_audio()` 출력에 `-ar 24000 -ac 1 -c:a pcm_s16le` 명시
   - raw/normalized audio duration 차이가 1초 초과하면 render 실패 처리

2. `[P1]` 이미지 프롬프트 관련성 개선
   - `app/services/image_prompt_translator.py` 신규
   - 입력: 전체 한글 대본 요약, 현재 문장, 앞뒤 문장, style hint
   - 출력: 영어 시각 프롬프트, negative prompt, visual consistency prefix
   - Ollama 실패 시 기존 heuristic prompt로 fallback
   - 실제 사용 prompt를 `storage/projects/{pid}/image_prompts_manifest.json`에 저장

3. `[P1]` 이미지 해상도/워크플로우 품질 guard
   - 모든 E2E/autopilot ComfyUI batch 기본을 `1024x576`으로 통일
   - generated media가 렌더 기준 최소 해상도(예: 960x540)보다 낮으면 preflight warning/error
   - `txt2img_sdxl_basic.json` 기본 `steps`를 30으로 상향
   - `comfyui_workflows.py`에 numeric placeholder validation 추가

4. `[P2]` 품질 리포트
   - `render_report.json`에 `audio_raw_duration_sec`, `audio_normalized_duration_sec`, `audio_silence_ratio`, `min_generated_image_size`, `image_prompt_manifest_path` 추가
   - Operator에 최근 샘플의 silence/image resolution warning 표시

### 수용 기준

- 한글 E2E 샘플을 다시 생성했을 때 output duration은 `60~120초`
- `tts_run_manifest.json`은 `seed_mode="fixed"` 유지
- TTS 문장별 WAV 끝무음이 과도하지 않음
- `audio_raw.wav`와 `audio.wav` duration 차이가 1초 이내
- ComfyUI 생성 이미지는 4장 이상, 각 이미지 최소 `1024x576`
- `image_prompts_manifest.json`에 영어 프롬프트가 저장됨
- 최종 `output.mp4`에서 이미지가 과도하게 흐리거나 대본과 무관하지 않음

목표: 사용자가 실제로 볼 수 있는 **1~2분짜리 완성 MP4**를 다시 만든다. 이번 검증물은 이전 로컬 이미지/영문 대본 샘플과 달리 아래 조건을 반드시 만족해야 한다.

- 대본/자막/내레이션 내용은 한글
- OmniVoice 목소리는 영상 전체에서 일관적
- 이미지는 ComfyUI에서 실제 생성한 결과물만 사용
- 최종 산출물은 `output.mp4`
- 실패 시 어느 단계가 막혔는지 로그와 산출물 경로로 바로 확인 가능

## 1. 현재 문제 진단

### 1.1 이전 MP4의 한계

이전 산출물 `storage/projects/7ee7587d99ca/output.mp4`는 렌더 파이프라인 검증용으로는 성공했지만, 완성도 검수용으로는 부족하다.

- 대본이 영어라 실제 사용 시나리오와 다름
- 장면 이미지는 ComfyUI 실생성이 아니라 로컬에서 만든 검증용 이미지
- TTS가 문장별 `seed + index`를 사용해 문장마다 음색이 흔들릴 수 있음
- 한글 입력 실측은 PowerShell inline 인코딩 경로에서 먼저 막혀 브라우저/API 경로 검증이 필요

### 1.2 코드 기준 원인

| 영역 | 현재 동작 | 문제 |
|---|---|---|
| TTS seed | `app/services/tts.py`의 `_effective_sentence_profile()`이 문장마다 `seed + index` 적용 | 생성 다양성은 생기지만 목소리 일관성이 약해질 수 있음 |
| TTS 입력 | `filter_tts_segments()`는 유니코드 문자를 지원 | 브라우저/API 저장 경로는 괜찮을 가능성이 높지만 PowerShell inline 한글 리터럴은 깨질 수 있음 |
| ComfyUI | `image_worker.py`가 큐/heartbeat/import/plan refresh 지원 | 이전 실측에서 현재 실행 중인 ComfyUI 프로세스가 `KSampler -> tqdm -> stderr.flush()` 오류로 실패 |
| Render | TTS timings + media_order/render_plan 기반 MP4 생성 성공 | ComfyUI 실이미지와 한글 TTS가 준비되면 렌더는 바로 재사용 가능 |

## 2. 완료 기준

이번 계획은 아래 파일이 실제로 생성되어야 완료다.

```text
storage/projects/{pid}/output.mp4
```

검증 기준:

- `ffprobe` duration: `60~120초`
- video stream: `1920x1080`, `h264`, `30fps`
- audio stream: `aac`
- `storage/projects/{pid}/media/` 안에 ComfyUI 생성 이미지가 4장 이상 존재
- `storage/projects/{pid}/tts/timings.json`의 문장 text가 한글
- `storage/projects/{pid}/tts/tts_run_manifest.json`에서 전체 문장의 `voice_preset`, `instruct`, `speed`, `num_step`, `guidance_scale`, `denoise`, `postprocess_output`이 동일
- 샘플 프레임 `storage/projects/{pid}/qa/frame_10s.jpg` 추출 성공

## 3. 권장 실행 순서

### Phase 0. ComfyUI 프로세스 정상화

이전 실패가 ComfyUI workflow 자체보다 실행 중인 서버의 stderr/logger 문제였으므로, 영상 생성 전 ComfyUI를 깨끗하게 재기동한다.

작업:

- 기존 ComfyUI 프로세스 확인
- 실행 중이면 작업 종료 후 재시작
- 가능하면 PowerShell/cmd 콘솔에 직접 붙이지 않고 로그 파일 redirect 방식으로 실행
- `http://127.0.0.1:8188/system_stats` 확인
- ComfyUI smoke 1장 생성 테스트

성공 기준:

- `system_stats` 응답
- smoke prompt가 `execution_error` 없이 history image를 반환
- 실패 시 `storage/logs/comfyui_*.log` 또는 ComfyUI 콘솔 로그 경로 기록

### Phase 1. 한글 대본 프로젝트 생성

브라우저/API 경로를 기준으로 한글 대본을 저장한다. PowerShell inline 한글 리터럴은 이번 검증의 입력 경로로 쓰지 않는다.

대본 조건:

- 12~18문장
- 1문장 4~7초 예상
- 총 60~100초
- 주제는 저작권 이슈 없는 창작 스토리
- 문장 끝은 `.` 대신 `다.`, `요.`처럼 자연스러운 한국어 종결 사용

예시 방향:

```text
새벽의 작은 결심을 통해 실패를 다시 시작의 자료로 바꾸는 이야기.
훅 -> 포인트 -> 스토리 -> 교훈 구조.
```

성공 기준:

- `script`, `compiled_script`, `sentences`가 모두 한글로 저장
- `filter_tts_segments()` 후 문장 수가 12개 이상

### Phase 2. 목소리 일관성 고정

이번 영상은 자연스러운 다양성보다 **일관성**을 우선한다.

변경/실행 정책:

- `voice_preset`: `male-deep-calm` 또는 한글 내레이션에 가장 안정적인 60대/중저음 프리셋 하나로 고정
- `tts_profile.seed`: 전체 영상에서 하나의 seed로 고정
- 문장별 seed 변형은 이번 테스트에서는 비활성화 또는 `seed_mode="fixed"` 옵션으로 우회
- `speed`, `num_step`, `guidance_scale`, `denoise`, `postprocess_output`, `instruct`를 문장 전체에서 동일하게 유지
- Bible region speed override 같은 region별 변형은 이번 테스트에서 사용하지 않음

구현 옵션:

| 옵션 | 작업량 | 장점 | 단점 |
|---|---:|---|---|
| A. 테스트 실행용 임시 fixed seed 경로 | 낮음 | 빠르게 재검증 가능 | 제품 기능으로 남지 않음 |
| B. `tts_profile.seed_mode = fixed/per_sentence` 추가 | 중간 | UI/오토파일럿까지 재사용 가능 | 타입/API/UI/테스트 추가 필요 |
| C. voice cloning reference 도입 | 높음 | 일관성 최고 | 권리/입력/Whisper ref_text 처리 필요 |

권장: **B를 정식 구현**한다. 단, 이번 영상 생성이 급하면 A로 먼저 산출물을 만들고 B를 후속 구현한다.

성공 기준:

- `tts_run_manifest.json`에서 모든 문장의 `seed`가 동일하거나 `seed_mode=fixed`로 기록
- 사용자가 청취했을 때 문장마다 다른 화자처럼 들리지 않음
- 1분 이상 TTS에서 1455 재발 없음

### Phase 3. ComfyUI 장면 이미지 실생성

한글 대본의 장면을 4~6개 visual prompt로 나누고 `image_worker.py`를 통해 생성한다.

작업:

- `visual_source_mode="comfyui_auto"` 저장
- `body_image_options.batch_items`에 scene별 prompt 등록
- 각 item은 `sentence_idx`, `positive_prompt`, `negative_prompt`, `seed`, `width`, `height`, `filename_prefix` 포함
- 8GB VRAM 기준 기본 해상도는 `1024x576`
- 실패하면 `768x432`로 1회 낮춰 재시도
- `auto_build_plans_after_image=true`

프롬프트 원칙:

- 한글 대본을 그대로 ComfyUI에 넣지 않고 영어 시각 프롬프트로 변환
- 같은 영상 안에서는 스타일 고정
- 예: `cinematic documentary still, warm morning light, quiet room, old notebook, realistic, 16:9`
- negative prompt는 공통 사용: `text, watermark, logo, distorted hands, low quality, blurry, duplicate`

성공 기준:

- `body_image_state=done`
- `body_image_mappings` 4개 이상
- `media_order`에 ComfyUI import 파일 4개 이상
- `scene_plan`/`render_plan` 자동 갱신

### Phase 4. Render plan 점검

이미지 생성 후 자동 갱신된 plan을 렌더 전에 확인한다.

체크:

- `scene_plan.scenes[*].media_path`가 실제 media 파일을 가리키는지
- `render_plan.segments[*].media[*].path`가 존재하는지
- segment duration 합계가 TTS duration과 크게 어긋나지 않는지
- motion은 `slow_zoom_in`, `pan_left`, `pan_right` 등 과하지 않은 값 사용
- caption style은 한글 가독성 우선

성공 기준:

- preflight 통과
- missing media 없음
- fallback render가 아니라 render_plan 기반 렌더

### Phase 5. 최종 렌더

작업:

- `render_formats=["landscape"]`
- `kenburns_enabled=true`
- `run_render_job(pid)` 또는 render worker 큐 사용
- 완료 후 `output.mp4` 경로 확인

검증:

```powershell
ffprobe -v error -show_entries format=duration,size -show_streams -of json storage\projects\{pid}\output.mp4
ffmpeg -y -ss 00:00:10 -i storage\projects\{pid}\output.mp4 -frames:v 1 storage\projects\{pid}\qa\frame_10s.jpg
```

성공 기준:

- `render_state=done`
- duration `60~120초`
- video/audio stream 둘 다 존재
- QA frame 생성

## 4. 디버깅 로그 정책

각 단계 실패 시 아래 파일/필드를 확인한다.

| 단계 | 확인 위치 |
|---|---|
| TTS 실패 | `storage/projects/{pid}/tts/tts_error.json`, project `tts_error` |
| TTS 음색 흔들림 | `storage/projects/{pid}/tts/tts_run_manifest.json` |
| ComfyUI submit 실패 | project `body_image_error`, `body_image_last_log` |
| ComfyUI execution 실패 | `ComfyUIClient.extract_execution_error()` 결과, ComfyUI 로그 |
| 이미지 import 실패 | `storage/projects/{pid}/media/`, `body_image_mappings` |
| render 실패 | project `render_last_log`, `storage/projects/{pid}/render_report.json` |
| 결과 검증 | `ffprobe` JSON, `qa/frame_10s.jpg` |

## 5. 우선 수정 후보

### 5.1 TTS seed mode

추가 필드:

```python
seed_mode: Literal["fixed", "per_sentence"]
```

정책:

- 기본값은 기존 호환을 위해 `per_sentence`
- 이번 한글 검증 영상과 오토파일럿 기본값은 `fixed`
- `fixed`이면 `_effective_sentence_profile()`에서 `seed + index`를 하지 않음
- manifest에 `seed_mode` 기록

테스트:

- fixed mode: 모든 manifest seed 동일
- per_sentence mode: 기존처럼 `seed`, `seed+1`, `seed+2`
- region speed override와 seed mode가 서로 독립 동작

### 5.2 ComfyUI restart/smoke helper

추가 스크립트 후보:

```text
scripts/check_comfyui_smoke.py
scripts/run_comfyui_detached.ps1
```

목표:

- 서버 상태 확인
- 작은 이미지 1장 생성
- stderr flush 문제 재발 여부 확인
- 실패 로그 경로 출력

### 5.3 한글 입력 경로 고정

PowerShell inline 한글 대신 아래 중 하나를 사용한다.

- UTF-8 `.txt` fixture를 읽어서 프로젝트 생성
- FastAPI TestClient로 JSON body 저장
- 브라우저 UI에서 직접 입력

## 6. 이번 재생성 작업 체크리스트

1. `[완료]` ComfyUI 재기동 및 smoke 통과
2. `[완료]` 한글 대본 프로젝트 생성
3. `[완료]` TTS fixed seed mode 적용 또는 임시 고정 실행
4. `[완료]` 한글 TTS 60~100초 생성
5. `[완료]` ComfyUI scene image 4~6장 실생성
6. `[완료]` scene_plan/render_plan 자동 갱신
7. `[완료]` preflight 수준 결과 확인
8. `[완료]` 최종 `output.mp4` 렌더
9. `[완료]` ffprobe/QA frame 검증
10. `[완료]` 사용자에게 완성 MP4 전체 경로 보고

## 7. 이번 산출물 보고 형식

완료 후 사용자에게 아래만 명확히 보고한다.

```text
완성 MP4:
C:\Users\petbl\newauto\storage\projects\{pid}\output.mp4

검증:
- 길이: NN.N초
- 해상도: 1920x1080
- 오디오: 있음
- ComfyUI 생성 이미지: N장
- QA 프레임: C:\Users\petbl\newauto\storage\projects\{pid}\qa\frame_10s.jpg
```
## 2026-04-27 P1 Visual Readability Update

- `[Done]` Image prompt generation now prefers simple, intuitive stickman scenes over narration-dump prompts.
- `[Done]` Prompts are rebuilt as English SDXL-friendly visual directions.
- `[Done]` Core sentence/context is mapped into obvious visual tokens so the main action reads at a glance.
- `[Done]` Batch queue and autopilot now save `image_prompts_manifest.json` for later prompt review.
- `[Done]` Stickman reference/template library is now separated so prompt generation can attach `template_key` and external reference metadata.
- `[Next]` The next runtime pass should validate that ComfyUI outputs actually become more readable in the generated batch.
