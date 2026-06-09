# Bible Narration And Image Generation Plan

상태: `Updated after codebase analysis`

## 구현 진행 현황

- `[완료]` Phase 0 기반 데이터 모델 일부: DB 컬럼, 타입, migration fallback, clone 복사, 프론트 typedef
- `[완료]` Phase 1 일부: marker 기반 `script_compile` 모듈, Standard/Bible Longform compile, `/script` 저장 시 `RegionalSentence[]` 생성
- `[완료]` Phase 2 일부: TTS가 `regional_sentences`를 우선 사용, `timings.json`/manifest에 region 기록, bible region 기본 speed override, `unload_model()` 추가
- `[완료]` Phase 5 일부: Step 1 Content Mode 선택 UI, compiled script preview, region list, TTS region badge
- `[남음]` Bible search/commit API, render_plan 기반 렌더, region-aware subtitle, preflight/UI 연결, image generation worker, ComfyUI/Ollama 연동

## 목표

현재 `newauto`는 다음 단일 파이프라인으로 동작한다.

1. Step 1에서 제목과 스크립트를 저장한다.
2. 저장 시 `script` 문자열을 `sentences: list[str]`로 분리한다.
3. Step 2에서 미디어를 업로드하고 `media_order`로 순서를 관리한다.
4. Step 3에서 `sentences` 전체에 동일 TTS 프로필을 적용해 WAV와 `timings.json`을 만든다.
5. Step 4에서 전체 오디오 길이를 `media_order` 개수로 균등 분배해 영상 트랙을 만들고, 단일 ASS 자막 스타일을 얹는다.

성경 롱폼 목표는 이 흐름 위에 옵션 모드를 추가하되, 기존 일반 영상 흐름을 깨지 않는 것이다.

- `Standard`: 현재 동작 그대로 유지
- `Bible Longform`: 사용자 원고에 성경 구절/낭독 구간을 결합하고, 구간별 TTS/자막/배경/이미지 생성 정책을 적용
- `Upload Only`: 수동 업로드 미디어만 사용
- `Hybrid`: 업로드 미디어와 생성 이미지를 함께 사용
- `ComfyUI Auto`: 본문 구간 이미지를 자동 생성

핵심 원칙은 UI 옵션보다 데이터 흐름을 먼저 분리하는 것이다. 지금 구조는 `script`, `sentences`, `timings`, `media_order`가 모두 구간 정보를 잃기 때문에, 성경 롱폼은 먼저 `compiled_script`, `RegionalSentence`, `RegionalTimingEntry`, `render_plan.json`을 통과시키는 구조로 바꿔야 한다.

## 현재 코드베이스 진단

### 1. 스크립트 저장은 단일 원고만 가진다

관련 파일:

- `app/routers/projects.py`
- `app/db.py`
- `app/types.py`
- `app/static/app.js`

현재 `PUT /api/projects/{pid}/script`는 `title`, `script`만 받는다. 내부에서는 `split_sentences(script)`를 호출해 바로 `sentences`를 만들고, `script.txt`에도 같은 문자열을 저장한다.

문제:

- 사용자가 입력한 원고와 TTS/렌더에 실제 사용되는 원고를 구분할 수 없다.
- 성경 구절을 자동 삽입하면 사용자의 원본 입력을 덮어쓸 위험이 있다.
- `script`를 기준으로 `normalize_tts_profile(..., project["script"])`가 호출되므로, 나중에 `compiled_script`가 생겨도 TTS 프리셋 추론 기준이 어긋날 수 있다.
- 클론 기능도 현재 `script`와 `sentences`만 복사한다.

개선 방향:

- DB에 `content_mode`, `visual_source_mode`, `user_script`, `compiled_script`, `selected_verses`, `render_plan`을 추가한다.
- 기존 `script`는 호환 필드로 유지하되, 신규 코드에서는 `user_script`와 `compiled_script`를 명시적으로 사용한다.
- Standard 모드에서는 `user_script == compiled_script == script`로 유지한다.
- Bible Longform 모드에서는 사용자 입력은 `user_script`, TTS/렌더 입력은 `compiled_script`로 분리한다.

### 2. 문장 분리는 region marker를 보존하지 못한다

관련 파일:

- `app/text.py`
- `tests/test_tts_pipeline.py`
- `app/static/app.js`

현재 `split_sentences()`는 `(?<=[.!?])\s+|\n+`로 나누고 읽을 수 없는 조각만 필터링한다. 프론트의 `estimateSentenceCount()`도 유사한 정규식으로 개수를 추정한다.

문제:

- `<<intro>>`, `<<body>>`, `<<bible>>` 같은 marker를 넣으면 marker가 문장처럼 취급되거나 TTS 입력에 섞일 수 있다.
- marker 경계가 사라져 TTS, subtitle, render 단계로 구간 정보가 전달되지 않는다.
- 한국어 문장부호 `다.`, `요.`, `?`, `!` 외에 줄바꿈 의존도가 커 긴 내레이션에서 문장 분리 품질이 낮을 수 있다.
- 프론트 문장 개수와 백엔드 실제 필터링 결과가 달라질 수 있다. 백엔드는 읽을 수 없는 세그먼트를 제거하지만 프론트는 `filter(Boolean)`만 한다.

개선 방향:

- 기존 `split_sentences()`는 Standard 호환용으로 유지한다.
- 신규 `app/services/script_compile.py` 또는 `app/script_compile.py`를 추가한다.
- compile 단계에서 marker를 제거하고 `RegionalSentence[]`를 만든다.
- 프론트 문장 수는 가능하면 저장 후 서버 응답의 `sentences.length`를 신뢰하고, Bible Longform에서는 `compiled_script` 미리보기 기준으로 표시한다.

추천 타입:

```python
Region = Literal["intro", "body", "bible"]

class RegionalSentence(TypedDict):
    idx: int
    text: str
    region: Region
```

### 3. TTS는 구간별 override를 받을 수 없다

관련 파일:

- `app/services/tts.py`
- `app/routers/render.py`
- `app/tts_profiles.py`
- `tests/test_tts_pipeline.py`

현재 `run_tts_job()`은 `project["sentences"]`를 `list[str]`로 받아 모든 문장에 동일한 `voice_preset`과 `tts_profile`을 적용한다. 문장별 seed만 `base_seed + index`로 바꾼다.

문제:

- `intro`, `body`, `bible`을 구분할 수 없다.
- 성경 구절만 속도를 낮추거나 다른 voice preset을 적용할 수 없다.
- `tts_run_manifest.json`에 region이 없어, 나중에 생성 결과를 검증하거나 재현하기 어렵다.
- `_project_tts_profile()`이 `project["script"]`를 기준으로 normalization을 수행한다. 성경 모드에서는 `compiled_script` 기준이어야 한다.
- OmniVoice 모델을 내리는 `unload_model()`이 없다. ComfyUI와 같은 GPU 작업을 같은 PC에서 이어 실행하려면 VRAM 해제가 필요하다.

개선 방향:

- `run_tts_job()` 시작 시 `project["regional_sentences"]`가 있으면 그것을 우선 사용하고, 없으면 기존 `sentences`를 `body` region으로 감싼다.
- `RegionalSentence` 단위로 effective profile을 만든다.
- `bible_tts_profile` 또는 `region_tts_overrides`를 프로젝트 설정에 둔다. 1차 구현은 `bible_speed=0.90` 정도로 좁게 시작한다.
- `timings.json`과 `tts_run_manifest.json`에 `region`을 추가한다.
- `unload_model()`을 추가하고, 이미지 생성 직전에 호출할 수 있게 한다.

추천 타입:

```python
class RegionalTimingEntry(TypedDict):
    idx: int
    text: str
    start: float
    end: float
    dur: float
    region: NotRequired[Region]
```

호환 규칙:

- 기존 `timings.json`에는 `region`이 없으므로 읽을 때 기본값은 `body`로 처리한다.
- 기존 `sentences: list[str]`는 유지한다. 단, 새 코드에서는 `regional_sentences`를 우선한다.

### 4. 자막은 단일 스타일만 지원한다

관련 파일:

- `app/services/subtitle.py`
- `app/services/render.py`
- `tests/test_subtitle_rendering.py`

현재 `write_ass()`는 단일 `SubtitleStyle`만 받아 `Style: Default` 하나를 만들고 모든 Dialogue에 적용한다.

문제:

- 성경 구절 구간에만 큰 글자, 중앙 배치, 다른 배경 박스, 느린 fade 같은 스타일을 줄 수 없다.
- `TimingEntry`에 region이 없어 ASS 이벤트별 스타일 선택이 불가능하다.
- `word_timings`도 `cue_idx`만 있으므로 region-aware karaoke/debug 표시가 어렵다.

개선 방향:

- `write_ass()`는 기존 signature를 유지하되 선택 인자로 `region_styles`를 받도록 확장한다.
- region이 없는 timing은 `body`로 취급한다.
- ASS에는 `Default`, `Intro`, `Body`, `Bible` 스타일을 만들고 Dialogue에서 region에 맞는 style name을 사용한다.
- Bible 1차 기본값은 `position=middle 또는 lower`, `font_size` 증가, `background_opacity` 증가, `effect=fade` 정도로 제한한다.

### 5. 렌더는 전체 미디어 균등 분배만 한다

관련 파일:

- `app/services/render.py`
- `tests/test_render_visual_track.py`

현재 `_build_visual_track()`은 전체 `total_duration / len(media_files)`로 각 미디어 길이를 균등 배분한다. `run_render_job()`은 `media_order` 전체를 한 리스트로 넘긴다.

문제:

- intro/body/bible 구간별 배경을 지정할 수 없다.
- 본문 생성 이미지와 업로드 미디어를 섞는 정책이 없다.
- 성경 구절 배경을 별도 파일로 고정하거나, Bible 구간에만 다른 zoom 속도를 주는 구조가 없다.
- 영상 길이와 미디어 분배가 sentence/timing region을 모르기 때문에 구간 경계에 맞춰 화면을 바꾸기 어렵다.

개선 방향:

- 렌더 전에 `render_plan.json`을 생성한다.
- `_build_visual_track()`에 `render_plan` 기반 경로를 추가한다. 기존 리스트 기반 경로는 Standard 호환으로 유지한다.
- `render_plan`은 region별 duration, media mapping, generated image mapping, bible background를 포함한다.
- 1차 구현에서는 `Upload Only`만 지원해도 `render_plan` 구조를 먼저 사용한다.

추천 최소 구조:

```json
{
  "version": 1,
  "total_duration": 120.0,
  "segments": [
    {
      "region": "intro",
      "start": 0.0,
      "end": 12.0,
      "media": [{"path": "media/intro.jpg", "kind": "image"}],
      "visual_policy": {"fit": "cover", "kenburns": true}
    },
    {
      "region": "body",
      "start": 12.0,
      "end": 96.0,
      "media": [{"path": "media/body_01.jpg", "kind": "image"}],
      "visual_policy": {"fit": "cover", "kenburns": true}
    },
    {
      "region": "bible",
      "start": 96.0,
      "end": 120.0,
      "media": [{"path": "media/bible_bg.jpg", "kind": "image"}],
      "visual_policy": {"fit": "cover", "kenburns": "slow"}
    }
  ]
}
```

### 6. Worker 경계는 render 중심이다

관련 파일:

- `app/workers/render_worker.py`
- `app/main.py`
- `app/db.py`

현재 render는 별도 프로세스 worker가 queue를 polling한다. 반면 TTS는 FastAPI `BackgroundTasks`로 같은 서버 프로세스 안에서 돈다.

문제:

- 성경 롱폼에서 TTS, ComfyUI 이미지 생성, render가 모두 GPU/CPU/디스크를 크게 쓴다.
- ComfyUI 호출을 render worker 안에 넣으면 이미지 생성 실패가 render 실패로 섞인다.
- render worker heartbeat와 image generation 상태가 같은 필드에 섞일 위험이 있다.
- `recover_interrupted_tasks()`는 TTS/render/upload/media_upload만 복구한다. image generation 상태가 없다.

개선 방향:

- `image_gen_worker.py`를 별도로 추가한다.
- DB에는 `image_gen_state`, `image_gen_progress`, `image_gen_error`, `image_gen_job_id`, `image_gen_heartbeat_at`을 별도로 둔다.
- render worker는 생성 완료된 파일과 `render_plan.json`만 소비한다.
- ComfyUI 2차 구현 전에도 worker/상태 필드는 미리 설계해 둔다.

추천 실행 순서:

1. script save/compile
2. verse search/commit
3. TTS
4. `unload_model()`
5. image generation queue
6. render queue

### 7. Preflight는 성경 모드 조건을 모른다

관련 파일:

- `app/services/preflight.py`
- `app/routers/render.py`
- `app/static/app.js`

현재 preflight는 script, TTS, timings, media, ffmpeg, disk, oauth를 점검한다.

문제:

- `content_mode`가 없으므로 성경 모드 전용 체크가 불가능하다.
- Bible Longform에서 `compiled_script`, `selected_verses`, bible background, render_plan 준비 여부를 확인하지 못한다.
- Hybrid/ComfyUI Auto에서 ComfyUI reachable, 생성 이미지 완료 여부를 확인하지 못한다.
- OAuth는 렌더 필수 조건이 아닌 YouTube 업로드 조건인데 현재 preflight에 포함되어 있어 렌더 준비성과 업로드 준비성이 섞인다.

개선 방향:

- 렌더 preflight와 YouTube upload preflight를 분리하거나, `category`를 추가한다.
- 성경 모드에서는 다음 체크를 추가한다.
  - `content_mode`
  - `compiled_script`
  - `regional_sentences`
  - `selected_verses`
  - `render_plan`
  - `bible_background`
  - `image_generation_done` if `visual_source_mode in {"hybrid", "comfyui_auto"}`
  - `comfyui_reachable` if `visual_source_mode in {"hybrid", "comfyui_auto"}`

### 8. 프론트엔드는 기존 5단계 워크플로우에 강하게 묶여 있다

관련 파일:

- `app/static/index.html`
- `app/static/app.js`
- `app/static/style.css`

현재 UI는 Script, Media, TTS, Render, YouTube 5단계다. Project typedef에도 `script`, `sentences`, `media_order` 중심 필드만 있다.

문제:

- `content_mode`, `visual_source_mode`가 없다.
- Bible 검색/추천/선택/commit 화면이 없다.
- `compiled_script` 미리보기 영역이 없다.
- media는 단일 `media_order`만 보여준다. intro/body/bible bucket을 표현할 곳이 없다.
- TTS 리스트는 `project.sentences`만 표시하므로 region badge, bible override 표시가 없다.

개선 방향:

- 1차 UI는 기존 5단계를 유지하되 Step 1에 `Content Mode`와 Bible commit 패널을 넣는다.
- Step 2에는 `Visual Source Mode`와 region mapping 패널을 넣는다.
- Step 3 TTS 리스트에는 region badge와 effective speed를 표시한다.
- Step 4 preflight에는 성경 모드 전용 체크를 표시한다.

## 데이터 모델 업데이트 계획

### DB 컬럼

`projects` 테이블에 추가할 최소 컬럼:

- `content_mode TEXT NOT NULL DEFAULT 'standard'`
- `visual_source_mode TEXT NOT NULL DEFAULT 'upload_only'`
- `user_script TEXT NOT NULL DEFAULT ''`
- `compiled_script TEXT NOT NULL DEFAULT ''`
- `regional_sentences TEXT NOT NULL DEFAULT '[]'`
- `bible_query TEXT NOT NULL DEFAULT ''`
- `selected_verses TEXT NOT NULL DEFAULT '[]'`
- `bible_background_file TEXT NOT NULL DEFAULT ''`
- `body_image_state TEXT NOT NULL DEFAULT 'idle'`
- `body_image_progress INTEGER NOT NULL DEFAULT 0`
- `body_image_error TEXT NOT NULL DEFAULT ''`
- `body_image_mappings TEXT NOT NULL DEFAULT '[]'`
- `render_plan TEXT NOT NULL DEFAULT '{}'`

호환 마이그레이션:

1. 새 컬럼을 추가한다.
2. 기존 row는 `content_mode='standard'`, `visual_source_mode='upload_only'`로 둔다.
3. 기존 `script` 값을 `user_script`와 `compiled_script`에 복사한다.
4. 기존 `sentences`는 `regional_sentences`로 변환하지 않아도 된다. 읽을 때 fallback으로 `body` region을 부여한다.
5. `compiled_script`가 비어 있으면 `script`를 fallback으로 사용한다.

주의:

- `update_project()`의 JSON 직렬화 대상에 `regional_sentences`, `selected_verses`, `body_image_mappings`, `render_plan`을 추가해야 한다.
- `_row_to_project()`에서 타입 normalization과 fallback을 처리해야 한다.
- `ProjectRecord`, `ProjectStatus`, 프론트 JSDoc typedef를 모두 같이 갱신해야 한다.

## API 업데이트 계획

### Script

기존:

- `PUT /api/projects/{pid}/script`

변경:

- 기존 엔드포인트는 유지한다.
- payload에 선택적으로 `content_mode`를 받을 수 있게 한다.
- Standard 모드에서는 기존처럼 바로 `sentences`를 만든다.
- Bible Longform 모드에서는 `user_script`를 저장하고, commit 전까지 `compiled_script`는 자동 덮어쓰지 않는다.

추가:

- `POST /api/projects/{pid}/bible/search`
  - 로컬 성경 데이터에서 후보 구절 검색
  - LLM은 후보 rerank에만 사용 가능
- `POST /api/projects/{pid}/bible/commit`
  - `selected_verses`를 받아 `compiled_script` 생성
  - `RegionalSentence[]` 생성
  - `sentences`는 TTS 호환용으로 text만 추출해 저장
- `POST /api/projects/{pid}/script/compile`
  - 성경 검색 없이 marker 기반 compile만 수행할 때 사용 가능

### Media

기존:

- `POST /api/projects/{pid}/media`
- `PUT /api/projects/{pid}/media/order`

추가 또는 확장:

- `PUT /api/projects/{pid}/visual-source`
  - `visual_source_mode` 저장
- `PUT /api/projects/{pid}/media/mapping`
  - `media_order`를 유지하면서 region별 mapping을 `render_plan` 또는 별도 JSON에 저장
- `POST /api/projects/{pid}/bible-background`
  - Bible 구간 전용 배경 업로드

### TTS

기존:

- `POST /api/projects/{pid}/tts`

확장:

- payload에 선택적으로 `region_tts_overrides` 또는 `bible_speed`를 추가한다.
- TTS 실행은 `compiled_script/regional_sentences` 기준으로 수행한다.
- manifest에 region/effective profile을 기록한다.

### Render

기존:

- `POST /api/projects/{pid}/render`

확장:

- render queue 전에 `render_plan` 존재 여부를 확인한다.
- Standard 모드에서는 없으면 기존 방식으로 렌더 가능하다.
- Bible Longform 모드에서는 render_plan이 없으면 400으로 막고 preflight에서 이유를 보여준다.

## 구현 순서

### Phase 0. 기반 안정화

목표: 기존 기능을 깨지 않고 성경 모드 데이터를 저장할 수 있게 한다.

- `[완료]` DB 컬럼 추가와 migration fallback 구현
- `[완료]` `ProjectRecord`, 프론트 typedef 갱신
- `[완료]` `content_mode`, `visual_source_mode`, `user_script`, `compiled_script` 기본값 처리
- `[완료]` 기존 프로젝트 clone이 새 필드를 복사하도록 수정
- `script`를 호환 필드로 유지하되 내부 기준을 `compiled_script`로 옮길 준비
- 테스트:
  - `[완료]` 기존 프로젝트가 migration 후 정상 조회되는지
  - `[완료]` Standard 모드 저장/TTS 기존 테스트가 그대로 통과하는지

### Phase 1. Script compile와 RegionalSentence

목표: marker와 Bible commit 결과가 TTS 입력으로 안정적으로 전달되게 한다.

- `[완료]` `script_compile` 모듈 추가
- `[완료]` `compile_standard_script()`
- `[완료]` `compile_bible_longform_script()`
- `[완료]` marker 파싱: `<<intro>>`, `<<body>>`, `<<bible>>`
- `[완료]` marker는 TTS 문장에 포함하지 않는다.
- `[완료]` region이 없는 문장은 기본 `body`로 처리한다.
- `[완료]` `PUT /script`에서 compile 결과 저장
- `[남음]` `POST /bible/search`, `POST /bible/commit`에서 검색/선택 구절 기반 compile 결과 저장
- 테스트:
  - `[완료]` marker가 TTS 문장에 포함되지 않음
  - `[완료]` region 순서와 idx가 안정적임
  - `[완료]` 기존 `split_sentences()` 테스트 유지

### Phase 2. TTS region override

목표: 성경 구간에 다른 속도/프리셋을 적용할 수 있게 한다.

- `[완료]` `RegionalSentence` fallback 로더 추가
- `[완료]` `_project_tts_profile()`을 `compiled_script` 기준으로 변경
- `[완료]` `_effective_sentence_profile()`에 region 인자 추가
- `[완료]` bible region 기본 speed override 적용
- `[완료]` `timings.json`에 region 추가
- `[완료]` `tts_run_manifest.json`에 region, effective profile, kwargs, seed 기록
- `[완료]` `unload_model()` 추가
- `[남음]` API payload 기반 `region_tts_overrides` 또는 `bible_speed` 설정
- 테스트:
  - `[완료]` region 없는 기존 timing 호환
  - `[완료]` bible 문장만 speed override
  - `[완료]` manifest에 region 기록
  - `[완료]` `unload_model()` 호출 시 `_model`이 None으로 바뀜

### Phase 3. Region-aware subtitle

목표: 성경 구절 구간에 별도 자막 스타일을 적용한다.

- `TimingEntry` 타입에 optional `region` 추가
- `write_ass()`에 `region_styles` 선택 인자 추가
- ASS 스타일 `Default`, `Intro`, `Body`, `Bible` 생성
- region 없는 timing은 `Body` 또는 `Default`로 fallback
- 테스트:
  - Bible timing이 Bible style Dialogue로 출력됨
  - 기존 단일 스타일 테스트 유지

### Phase 4. Render plan과 Upload Only Bible Longform

목표: 이미지 생성 없이도 성경 롱폼 영상이 렌더되게 한다.

- `render_plan` 생성기 추가
- region별 duration 계산: timings의 region start/end 기준
- `media_order` 기반으로 intro/body/bible mapping 생성
- bible background file 지원
- `_build_visual_track()`에 render_plan 경로 추가
- Standard는 기존 `_build_visual_track(media_files, total_duration, ...)` 경로 유지
- 테스트:
  - region duration 계산
  - render_plan 없는 Standard 렌더 가능
  - Bible Longform에서 render_plan 없으면 preflight/render가 막힘

### Phase 5. Preflight와 UI 최소 연결

목표: 사용자가 현재 막힌 이유를 UI에서 알 수 있게 한다.

- `build_preflight_report()`에 content mode 조건 추가
- OAuth 체크는 upload category로 분리하거나 메시지를 "YouTube upload only"로 명확히 변경
- Step 1:
  - `[완료]` Content Mode 선택
  - Bible 검색/선택/commit
  - `[완료]` compiled script preview
- Step 2:
  - Visual Source Mode 선택
  - Bible background 업로드
  - region mapping 표시
- Step 3:
  - `[완료]` TTS 리스트에 region badge 표시
- Step 4:
  - region-aware preflight 결과 표시
- 테스트:
  - 프론트 typecheck
  - API workflow test

### Phase 6. Image generation worker

목표: ComfyUI 자동 이미지를 render와 분리된 작업으로 처리한다.

- `image_gen_worker.py` 추가
- DB queue/state 추가
- ComfyUI client 모듈 추가
- body chunk derivation 추가
- generated image mapping 저장
- `unload_model()` 후 image generation queue 실행
- render는 생성 이미지 완료 후 가능
- 테스트:
  - worker claim/recover
  - 실패 시 render_state와 독립적으로 image_gen_state만 error
  - generated mapping이 render_plan에 반영됨

### Phase 7. ComfyUI Auto와 Ollama assist

목표: 사용자가 적은 본문에서 자동으로 구간별 프롬프트와 이미지를 만든다.

- Ollama는 성경 구절 원문 생성이 아니라 추천/정렬/프롬프트 보조에만 사용
- 성경 구절 텍스트는 항상 로컬 Bible 데이터에서 가져온다.
- prompt manifest 저장
- regenerate/retry UI 추가
- ComfyUI 연결 상태 health check 추가

## 우선 해결해야 할 문제 10개

1. `script` 단일 필드 문제: `user_script`와 `compiled_script`를 분리하지 않으면 원본 원고가 손상된다.
2. `split_sentences()` region 손실: marker를 TTS에 흘려보내지 않는 compile 계층이 필요하다.
3. `sentences: list[str]` 한계: `RegionalSentence[]`가 없으면 구간별 TTS/자막/렌더가 불가능하다.
4. TTS 프로필 기준: `project["script"]`가 아니라 `compiled_script` 기준으로 normalization해야 한다.
5. `timings.json` region 누락: ASS와 render_plan이 같은 구간 경계를 공유할 수 없다.
6. 단일 ASS 스타일: 성경 구절 화면을 별도 스타일로 만들 수 없다.
7. 전체 미디어 균등 분배: 구간별 배경/이미지 생성 결과를 넣을 수 없다.
8. render worker와 image generation 경계: ComfyUI 작업을 render worker 안에 넣으면 상태와 장애가 섞인다.
9. OmniVoice unload 부재: TTS 후 이미지 생성으로 넘어갈 때 VRAM 경쟁 위험이 있다.
10. preflight 범위 혼합: 렌더 준비와 YouTube 업로드 준비가 섞여 있어 성경 모드 조건을 명확히 안내하기 어렵다.

## 테스트 전략

기존 테스트는 유지하면서 다음 테스트를 추가한다.

- `tests/test_script_compile.py`
  - marker parsing
  - selected verses commit
  - Standard fallback
- `tests/test_bible_workflow.py`
  - search/commit API
  - user_script와 compiled_script 분리
  - migration fallback
- `tests/test_tts_pipeline.py`
  - region-aware TTS
  - manifest region
  - bible speed override
  - unload model
- `tests/test_subtitle_rendering.py`
  - region style ASS output
- `tests/test_render_visual_track.py`
  - render_plan visual track
  - bible background fallback
- `tests/test_feature_workflow.py`
  - preflight mode-specific checks
  - clone copies new fields
- 프론트:
  - `npm run typecheck:frontend`

## 1차 릴리스 범위

1차 목표는 `Bible Longform + Upload Only`다.

포함:

- Content Mode
- user_script/compiled_script 분리
- local Bible search/commit
- RegionalSentence
- region-aware TTS timings/manifest
- Bible subtitle style
- render_plan 기반 Upload Only 렌더
- Bible 전용 preflight

제외:

- ComfyUI 자동 생성
- Ollama 자동 추천 고도화
- regenerate/retry UI
- image generation worker 실제 실행

단, 1차에서도 `visual_source_mode`, `image_gen_state`, `render_plan` 같은 확장 포인트는 미리 설계해 둔다. 나중에 ComfyUI를 붙일 때 렌더/TTS/DB 구조를 다시 갈아엎지 않기 위해서다.

## 최종 결론

현재 코드베이스와 가장 잘 맞는 방향은 "기존 5단계 UX 유지 + 내부 데이터 흐름의 region-aware 확장"이다.

바로 UI부터 크게 바꾸면 `script -> sentences -> timings -> render`로 이어지는 현재 단일 구조와 충돌한다. 따라서 구현은 다음 순서가 안전하다.

1. DB와 타입에 `user_script`, `compiled_script`, `content_mode`, `visual_source_mode` 추가
2. compile 계층에서 `RegionalSentence[]` 생성
3. TTS가 region을 받아 `timings.json`과 manifest에 기록
4. subtitle/render가 같은 region 정보를 사용
5. Upload Only Bible Longform을 먼저 완성
6. 이후 image generation worker와 ComfyUI Auto를 붙임

이 순서라면 기존 일반 영상 프로젝트는 그대로 유지하면서, 성경 롱폼의 핵심인 "구절 선택, 구간별 낭독, 구간별 화면 구성, 이후 자동 이미지 생성"까지 흔들리지 않게 확장할 수 있다.
