# 오토파일럿 최종 렌더 기능 계획서

작성일: 2026-04-26

## 1. 목표

사용자가 다음 중 하나만 입력하고 `오토파일럿` 버튼을 누르면, 프로그램이 최종 렌더 결과까지 자동으로 진행한다.

- 직접 대본 입력
- 기사 URL 입력
- 키워드 입력

최종 목표는 “한 번 누르면 알아서 영상 파일이 나오는 흐름”이다. 다만 유료 API, 업로드/게시, 위험한 자동 재시도는 기본값으로 켜지 않는다.

## 2. 현재 이미 있는 자산

| 영역 | 이미 있음 | 오토파일럿에서 할 일 |
|---|---|---|
| 대본 입력 | `script`, `user_script`, `compiled_script`, `regional_sentences` | 직접 대본 입력 시 compile/save를 자동 실행 |
| URL 분석 | `source/url/analyze`, SSRF 방어, fact notes | URL 입력 시 analyze -> draft generate -> apply 자동 연결 |
| 키워드 리서치 | Brave-only, 월 2000건 hard limit, cache | 키워드 입력 시 collect -> draft generate -> apply 자동 연결 |
| 대본 생성 | source draft worker, regenerate mode | hook/point/story/lesson 기본값 선택 및 worker 완료 대기 |
| TTS | TTS route/job, GPU guard | 대본 apply 후 TTS 자동 큐 등록 및 완료 대기 |
| 이미지 생성 | ComfyUI batch auto, image worker, GPU guard | 문장 범위 기준 이미지 일괄 생성 자동 큐 등록 |
| 장면 계획 | `scene_plan` service/API | 이미지 완료 후 자동 갱신 사용 |
| 렌더 계획 | `render_plan` service/API | 이미지 완료 후 자동 갱신 사용 |
| 실제 렌더 | render worker, render report | preflight 통과 후 render 큐 등록 및 report 확인 |
| 운영 상태 | Operator, usage, GPU, browser smoke | Autopilot 상태 카드와 실패 원인 표시 |

## 3. UX 설계

### 3.1 버튼 위치

Step 1 Source Assist 상단에 `오토파일럿` 패널을 추가한다.

입력 탭:

- `대본`
- `URL`
- `키워드`

실행 버튼:

- `오토파일럿 시작`
- `일시정지`
- `재개`
- `중단`

상태 표시:

- 현재 단계
- 전체 진행률
- 마지막 로그
- 다음으로 실행될 작업
- 실패 원인
- 비용/무료 한도 경고
- GPU 대기 상태

### 3.2 기본값

- 입력이 대본이면: Source Assist를 건너뛰고 바로 `script compile -> TTS`.
- 입력이 URL이면: `URL analyze -> draft generate -> apply`.
- 입력이 키워드면: `Brave collect -> URL/fact notes -> draft generate -> apply`.
- 이미지 방식 기본값: `comfyui_auto`.
- 이미지 batch count 기본값: 최대 12개, 실제 문장 수가 더 적으면 문장 수만큼.
- 렌더 포맷 기본값: 현재 프로젝트 render setting을 따름.
- 업로드는 실행하지 않음.

## 4. 오토파일럿 상태 머신

새 필드 후보:

- `autopilot_state`: `idle | queued | running | paused | done | error | canceled`
- `autopilot_progress`: `0..100`
- `autopilot_phase`: 현재 단계 key
- `autopilot_last_log`: 마지막 사람이 읽는 로그
- `autopilot_error`: 실패 메시지
- `autopilot_job_id`: 실행 id
- `autopilot_started_at`
- `autopilot_heartbeat_at`
- `autopilot_options`: 입력/옵션 저장
- `autopilot_last_error_code`: 사람이 검색/필터링하기 쉬운 오류 코드
- `autopilot_debug_summary`: UI에 보여줄 짧은 디버그 요약
- `autopilot_wait_started_at`: 현재 대기 상태가 시작된 시각
- `autopilot_retry_count`: 현재 phase 재시도 횟수

단계:

| Phase | 설명 | 완료 조건 |
|---|---|---|
| `prepare_input` | 입력 검증 및 옵션 저장 | 대본/URL/키워드 중 하나 유효 |
| `source_collect` | URL 분석 또는 키워드 수집 | source fact notes 생성 |
| `source_generate` | Gemma/Ollama 대본 초안 생성 | source draft `done` |
| `source_apply` | draft를 user script로 적용 | compiled script, sentences 생성 |
| `tts_enqueue` | TTS 작업 등록 | TTS `running` 또는 `queued` |
| `tts_wait` | TTS 완료 대기 | TTS `done` |
| `image_enqueue` | ComfyUI batch image 작업 등록 | body image `queued` |
| `image_wait` | 이미지 생성/가져오기 대기 | body image `done` |
| `plan_refresh` | scene/render plan build 호출 및 확인 | scene_plan/render_plan 존재 |
| `preflight` | 렌더 전 품질 점검 | 치명 check 통과 |
| `render_enqueue` | render 작업 등록 | render `queued` |
| `render_wait` | 렌더 완료 대기 | render `done` |
| `report` | render report 확인 | render_report 존재 |
| `done` | 최종 완료 | output 파일 존재 |

## 4.1 단계별 로그/디버깅 설계

오토파일럿은 “실패하면 어디서 왜 멈췄는지 바로 알 수 있는 것”을 핵심 기능으로 포함한다.

새 저장 위치 후보:

- DB 요약 필드:
  - `autopilot_phase`
  - `autopilot_last_log`
  - `autopilot_error`
  - `autopilot_last_error_code`
  - `autopilot_debug_summary`
- 파일 로그:
  - `storage/projects/{pid}/autopilot/events.jsonl`
  - `storage/projects/{pid}/autopilot/debug_snapshot.json`
  - `storage/projects/{pid}/autopilot/last_failure.json`
- UI:
  - Autopilot 카드에 최근 10개 이벤트 표시.
  - 실패 시 `디버그 보기` 버튼으로 마지막 실패 snapshot 표시.
  - render 단계 실패는 기존 `render_report.json` 링크/요약을 같이 표시.

로그 이벤트 schema:

```json
{
  "ts": "2026-04-26T09:10:00+09:00",
  "job_id": "auto_abc123",
  "phase": "image_wait",
  "level": "info",
  "event": "wait_worker",
  "message": "ComfyUI image worker is running.",
  "progress": 67,
  "worker_state": "running",
  "related_state": {
    "source_draft_state": "done",
    "tts_state": "done",
    "body_image_state": "running",
    "render_state": "idle"
  },
  "debug": {
    "gpu_owner": "image-job:project123",
    "brave_remaining": 1932,
    "attempt": 1
  }
}
```

`last_failure.json` schema:

```json
{
  "ts": "2026-04-26T09:15:00+09:00",
  "job_id": "auto_abc123",
  "phase": "preflight",
  "error_code": "PREFLIGHT_RENDER_PLAN_MEDIA_MISSING",
  "message": "2 render-plan segments are missing media files.",
  "action_hint": "이미지 생성 결과를 확인하거나 Scene/Render Plan을 다시 생성한 뒤 재개하세요.",
  "recoverable": true,
  "project_state": {
    "tts_state": "done",
    "body_image_state": "done",
    "render_state": "idle"
  }
}
```

로그 레벨:

- `debug`: 개발/검증용 상세 값.
- `info`: 정상 단계 진입/완료.
- `warn`: 자동 진행은 멈추지 않지만 주의가 필요한 상태.
- `pause`: 사용자 조치 후 재개 가능한 멈춤.
- `error`: 자동 복구가 어려운 실패.

오류 코드 규칙:

| Prefix | 의미 |
|---|---|
| `INPUT_` | 입력 검증 문제 |
| `SOURCE_` | URL/키워드/source draft 문제 |
| `COPY_` | 저작권/유사도 문제 |
| `TTS_` | TTS 생성 문제 |
| `IMAGE_` | ComfyUI/image worker 문제 |
| `PLAN_` | scene/render plan 문제 |
| `PREFLIGHT_` | 렌더 전 점검 문제 |
| `RENDER_` | FFmpeg/render worker 문제 |
| `REPORT_` | render report 생성/조회 문제 |
| `SYSTEM_` | GPU/tool/disk/worker heartbeat 문제 |

단계별로 반드시 남길 로그:

| Phase | 필수 로그 |
|---|---|
| `prepare_input` | input mode, 입력 길이, 옵션 요약 |
| `source_collect` | URL/domain 또는 keyword, cache hit 여부, Brave used/remaining |
| `source_generate` | model, regenerate mode, worker job id, copy risk score |
| `source_apply` | sentence count, compiled script 길이, region count |
| `tts_enqueue` | voice preset, profile summary, seed, sentence count |
| `tts_wait` | progress, heartbeat, 실패 시 마지막 TTS error |
| `image_enqueue` | visual mode, checkpoint, image count, width/height, seed base |
| `image_wait` | ComfyUI prompt ids, imported file count, failed scene index |
| `plan_refresh` | scene count, render segment count, missing media count |
| `preflight` | 실패 check key/message 전체 |
| `render_enqueue` | render formats, media count, render job id |
| `render_wait` | render phase, progress detail, FFmpeg tail |
| `report` | output path, size, duration, fallback_used |

로그 보존 정책:

- `events.jsonl`은 프로젝트별 최근 2000줄 또는 5MB까지만 유지.
- 오래된 이벤트는 `events.1.jsonl`로 회전.
- `last_failure.json`은 항상 최신 실패 1건을 덮어쓴다.
- `debug_snapshot.json`은 현재 상태를 덮어쓴다.

개인정보/저작권 보호:

- 원문 기사 전체나 대본 전체를 로그에 저장하지 않는다.
- 입력 URL, domain, source title, 짧은 excerpt hash만 저장한다.
- 대본은 길이, sentence count, copy risk score만 저장한다.
- 필요 시 사용자가 명시적으로 `debug_verbose=true`를 켠 경우에만 더 자세한 값 저장.

## 4.2 재진입/Skip Condition 매트릭스

오토파일럿은 서버 재시작, pause/resume, 사용자의 수동 수정 이후에도 같은 단계를 중복 실행하지 않아야 한다. 각 phase는 “실행 조건”, “skip 조건”, “재진입 시 동작”을 명확히 둔다.

| Phase | 실행 조건 | Skip 조건 | 재진입/Resume 동작 |
|---|---|---|---|
| `prepare_input` | `autopilot_state=queued` 또는 옵션 변경 | `autopilot_options` 유효, 입력 fingerprint 동일 | 옵션 fingerprint 비교 후 같으면 다음 phase |
| `source_collect` | input mode가 `url` 또는 `keyword` | `source_draft_sources`와 `source_draft_fact_notes` 존재 | cache hit/기존 fact notes 재사용 |
| `source_generate` | URL/keyword mode이고 draft 없음 | `source_draft_state=done` 및 `source_draft_script` 존재 | running이면 wait, done이면 다음 phase |
| `source_apply` | URL/keyword mode이고 draft 존재 | `compiled_script`와 `sentences`가 draft와 동일 fingerprint | `user_script`가 비어있지 않고 autopilot이 만든 값이 아니면 pause |
| `tts_enqueue` | `sentences` 존재, TTS 미완료 | `tts_state=done` 및 timings 존재 | running이면 `tts_wait`, error면 pause/error |
| `tts_wait` | TTS queued/running | `tts_state=done` | heartbeat 만료면 error, done이면 다음 phase |
| `image_enqueue` | visual mode가 `comfyui_auto/hybrid`, 이미지 부족 | `body_image_state=done` 및 mapping 수가 목표 이상 | running이면 `image_wait`, done이면 다음 phase |
| `image_wait` | body image queued/running | `body_image_state=done` | GPU/worker owner를 로그에 남기며 wait |
| `plan_refresh` | TTS와 이미지가 완료됨 | scene/render plan fingerprint가 최신 | `POST /scene-plan/build`, `POST /render-plan/build`에 해당하는 service 호출을 순서대로 수행 |
| `preflight` | render 직전 | 직전 preflight ok fingerprint가 현재 상태와 동일 | 실패 check가 있으면 pause |
| `render_enqueue` | preflight ok, render 미완료 | `render_state=done` 및 output 존재 | running이면 `render_wait`, error면 pause/error |
| `render_wait` | render queued/running | `render_state=done` | render heartbeat 만료면 error |
| `report` | render done | 최신 `render_report.json` 존재 | 없으면 report 재조회/생성 시도, 실패 시 error |
| `done` | output 존재 | 해당 없음 | 최종 상태 고정 |

fingerprint 후보:

- 입력 fingerprint: input mode, script/url/keyword hash, tone, target_minutes, regenerate_mode.
- 대본 fingerprint: compiled_script hash, sentence count, region count.
- 이미지 fingerprint: body_image_mappings path/prompt hash.
- plan fingerprint: scene count, render segment count, media path 목록.
- preflight fingerprint: script/media/timing/render_plan updated_at 조합.

중요 정책:

- phase handler는 가능한 순수 함수 형태로 만든다.
- 입력은 `(project, options, now)`이고 출력은 `next_phase`, `updates`, `events`, `side_effect_request`로 분리한다.
- 실제 DB update와 worker enqueue는 dispatcher가 수행한다.
- 이렇게 나누면 `test_autopilot_worker.py`에서 TTS/ComfyUI/render 없이 phase 전이를 mock하기 쉽다.

## 5. 입력별 상세 흐름

### 5.1 직접 대본 입력

1. 사용자가 제목/대본 입력.
2. `오토파일럿 시작`.
3. 서버가 `script`, `user_script`, `compiled_script`, `regional_sentences`, `sentences` 저장.
4. TTS 큐 등록.
5. 이미지 batch 생성.
6. scene/render plan build를 자동 호출한다.
7. preflight.
8. render 큐 등록.
9. render report 확인.

### 5.2 URL 입력

1. 사용자가 기사 URL 입력.
2. `source/url/analyze` 실행.
3. fact notes 생성.
4. source draft worker 큐 등록.
5. draft 완료 후 copy risk 확인.
6. 안전하고 `user_script` 덮어쓰기 위험이 없으면 apply.
7. 이후 TTS/Image/Render 흐름 진행.

저작권 정책:

- 원문 긴 문장 직접 사용 금지.
- copy risk 높으면 `autopilot_state=paused`로 멈춤.
- 사용자가 `재작성 후 계속` 또는 `중단` 선택.
- apply 전에 `user_script`가 비어있지 않고 오토파일럿이 만든 값이 아니면 pause한다.
- pause 없이 apply해야 하는 경우에도 `storage/projects/{pid}/autopilot/pre_apply_backup.txt`에 기존 `user_script`를 백업한다.

### 5.3 키워드 입력

1. 사용자가 키워드 입력.
2. Brave Search만 사용.
3. 월 2000건 한도 초과 시 즉시 pause/error.
4. keyword cache hit이면 Brave 호출 없이 진행.
5. 수집한 source 기반 draft 생성.
6. 이후 URL 입력 흐름과 동일.

비용 정책:

- Brave 월 2000건 안에서만 사용.
- Bing/SerpAPI/CSE 자동 fallback 금지.
- paid provider는 오토파일럿 기본 옵션에 포함하지 않음.

이미지 수 산정:

- `image_count` 기본값은 고정 숫자 12가 아니라 `auto`.
- auto 계산식 1차안:
  - `target_minutes`가 숫자이면 `min(sentence_count, max(4, target_minutes * 4))`.
  - `target_minutes=auto`이면 `min(sentence_count, max(6, ceil(sentence_count / 4)))`.
  - 상한은 v1에서 24장.
- 사용자가 직접 숫자를 넣으면 그 값을 우선하되, 문장 수를 넘지 않는다.

## 6. Worker 설계

새 파일 후보:

- `app/workers/autopilot_worker.py`
- `app/services/autopilot.py`
- `app/routers/autopilot.py`
- `tests/test_autopilot_worker.py`
- `tests/test_autopilot_routes.py`

worker 원칙:

- 기존 worker를 직접 재구현하지 않는다.
- 각 단계는 기존 API/service/db helper를 호출한다.
- 긴 작업은 기존 worker에 맡기고 상태만 기다린다.
- 서버 재시작 시 stale autopilot job을 recoverable error로 전환한다.
- `paused` 상태에서는 다음 단계를 시작하지 않는다.
- `render_worker.py`, `source_draft_worker.py`, `image_worker.py` 패턴을 따른다.
- `storage/autopilot_worker.lock`으로 단일 worker만 실행한다.
- polling 주기: 3초.
- heartbeat 주기: 10초.
- startup spawn은 `app/main.py`에서 수행하고, `NEWAUTO_DISABLE_BACKGROUND_WORKERS=1`이면 실행하지 않는다.
- stale 기준: heartbeat 60초 초과 또는 runtime 7200초 초과 시 recoverable error.

대기 방식:

- source draft 완료 대기: `source_draft_state`.
- TTS 완료 대기: `tts_state`.
- image 완료 대기: `body_image_state`.
- render 완료 대기: `render_state`.

cancel 정책:

- 아직 시작하지 않은 후속 phase는 실행하지 않는다.
- 이미 기존 worker에 큐 등록된 작업은 v1에서 강제 중단하지 않는다.
- 이미 ComfyUI에 submit된 작업은 자연 완료될 수 있으며, cancel 이후 import된 결과는 오토파일럿 후속 단계에서 사용하지 않는다.
- ComfyUI prompt cancel API 연동은 복잡도와 안정성 때문에 v2로 미룬다.

pause 중 manual 변경 정책:

- v1 정책은 “manual 변경 감지 시 autopilot 자동 pause 유지 + resume 시 fingerprint 재검증”이다.
- 사용자가 pause 중 TTS, 이미지, render plan 등을 수동으로 바꾸면 resume 시 해당 phase skip/재실행 조건을 다시 계산한다.
- 수동 변경이 현재 autopilot fingerprint와 충돌하면 `SYSTEM_MANUAL_CHANGE_DETECTED`로 pause하고 사용자 확인을 요구한다.

## 7. GPU/리소스 정책

오토파일럿 worker는 GPU를 직접 오래 점유하지 않는다. GPU 작업은 기존 worker별 guard를 따른다.

| 작업 | 실행 주체 | GPU guard |
|---|---|---|
| source draft | `source_draft_worker` | `ollama` |
| TTS | `tts` job | `tts` |
| ComfyUI image | `image_worker` | `comfyui` |
| render | `render_worker` | 보통 CPU/FFmpeg 중심 |

정책:

- 오토파일럿은 GPU lock을 직접 잡지 않는다.
- GPU busy면 상태를 `wait_gpu` 계열 로그로 표시.
- 같은 프로젝트에서 이미 실행 중인 작업이 있으면 중복 큐 등록하지 않는다.
- 8GB VRAM 기준 동시 실행은 금지하고 순차 진행한다.
- 다른 프로젝트가 GPU를 점유 중이면 `gpu_guard.current_owner()`를 status card와 events log에 표시한다.
- 같은 phase에서 GPU wait가 5분을 넘으면 자동으로 `paused` 전환한다.
- 이때 error code는 `SYSTEM_GPU_WAIT_TIMEOUT`으로 남긴다.
- action hint는 “다른 프로젝트 작업이 GPU를 사용 중입니다. Operator에서 현재 owner를 확인하고 완료 후 재개하세요.”로 표시한다.
- wait timeout은 phase별로 조정 가능하되 v1 기본값은 5분이다.

## 8. Preflight와 Pause 정책

자동으로 계속 가면 안 되는 상황:

- source copy risk가 기준 이상.
- Brave 월 무료 한도 초과.
- ComfyUI 연결 실패가 반복됨.
- TTS 실패.
- render preflight 치명 실패.
- render_plan media 누락.
- output 파일 생성 실패.

pause 처리:

- `autopilot_state=paused`
- `autopilot_phase` 유지
- UI에 “해결 후 재개” 버튼 표시
- 사용자가 설정 수정, 파일 업로드, ComfyUI 실행 후 `재개`

error 처리:

- 자동 복구가 불가능하거나 작업 자체가 실패한 경우.
- render report 또는 last_log 링크/요약 표시.

## 8.1 plan_refresh 실제 동작

`plan_refresh`는 단순 확인 단계가 아니다. `image_wait` 이후 반드시 scene/render plan build를 수행한다.

순서:

1. 최신 project를 다시 조회한다.
2. `build_scene_plan(project, render_format=preferred_render_format)` 호출.
3. `scene_plan` 저장.
4. 저장된 최신 project를 다시 조회한다.
5. `build_render_plan(project)` 호출.
6. `render_plan` 저장.
7. render plan segment의 media 누락 수를 계산한다.
8. 누락이 있으면 `PLAN_RENDER_MEDIA_MISSING`으로 pause한다.

skip 조건:

- scene/render plan fingerprint가 현재 script, timings, body_image_mappings와 동일하면 build를 건너뛴다.
- fingerprint가 없거나 다르면 항상 rebuild한다.

중요:

- `/scene-plan/build`, `/render-plan/build` 엔드포인트와 동일한 service 함수를 재사용한다.
- UI 버튼을 누르는 방식으로 구현하지 않고 backend service를 직접 호출한다.
- build 실패는 `PLAN_BUILD_FAILED`로 기록한다.

## 8.2 Action Hint와 Retry Strategy

오류 메시지와 복구 힌트는 phase 안에 흩어 쓰지 않고 한 곳에서 관리한다.

파일 후보:

- `app/services/autopilot_errors.py`

예시:

```python
ACTION_HINTS = {
    "PREFLIGHT_RENDER_PLAN_MEDIA_MISSING": "이미지 생성 결과를 확인하거나 Scene/Render Plan을 다시 생성한 뒤 재개하세요.",
    "BRAVE_RATE_LIMIT": "Brave 월 무료 한도를 초과했습니다. 다음 달 리셋 후 재개하거나 수동 대본 입력으로 진행하세요.",
    "SYSTEM_GPU_WAIT_TIMEOUT": "다른 작업이 GPU를 오래 사용 중입니다. Operator에서 owner를 확인하고 완료 후 재개하세요.",
    "COPY_RISK_HIGH": "원문과 유사도가 높습니다. 재작성 지시를 추가한 뒤 다시 생성하세요.",
}

RETRY_STRATEGIES = {
    "SOURCE_FETCH_TIMEOUT": "retry_once_after_30s",
    "COMFYUI_HISTORY_TIMEOUT": "retry_once_after_60s",
    "SYSTEM_GPU_WAIT_TIMEOUT": "no_retry_pause",
    "COPY_RISK_HIGH": "no_retry_pause",
    "PREFLIGHT_RENDER_PLAN_MEDIA_MISSING": "no_retry_pause",
}
```

재시도 원칙:

- transient error만 자동 1회 재시도한다.
- 저작권, quota, preflight, media 누락, 사용자 확인이 필요한 문제는 자동 재시도하지 않는다.
- 재시도 이벤트에는 `retry_count`, `retry_after_sec`, `previous_error_code`를 남긴다.

## 9. UI 상태 카드

Autopilot 카드 표시 항목:

- 입력 모드: 대본/URL/키워드
- 현재 단계
- 전체 진행률
- 현재 worker 상태
- GPU owner
- Brave 남은 무료 검색량
- 마지막 로그
- 다음 액션
- 최종 output 링크
- render report 버튼

단계별 진행률 예시:

| 단계 | 진행률 |
|---|---:|
| 입력 준비 | 5 |
| source collect | 15 |
| draft generate | 25 |
| apply | 35 |
| TTS | 50 |
| image | 70 |
| plan/preflight | 80 |
| render | 95 |
| report/done | 100 |

진행률 계산:

- 전체 진행률은 phase 고정 점프가 아니라 phase range와 phase 내부 sub-progress를 조합한다.
- 계산식:
  - `global = phase_start + ((phase_end - phase_start) * phase_progress / 100)`
- 예시:
  - `source_collect` range 5~15에서 Brave 5개 중 3개 수집이면 `5 + 10 * 60% = 11`.
  - `render_wait` range 80~95에서 render worker progress 40%면 `80 + 15 * 40% = 86`.
- 기존 render progress visibility 패턴을 재사용한다.
- UI에는 전체 진행률과 phase 내부 진행률을 둘 다 표시한다.

## 10. API 초안

### Start

`POST /api/projects/{pid}/autopilot/start`

payload:

```json
{
  "input_mode": "script",
  "script": "...",
  "url": "",
  "keyword": "",
  "tone": "documentary",
  "target_minutes": "auto",
  "regenerate_mode": "hook",
  "visual_source_mode": "comfyui_auto",
  "image_count": "auto",
  "render_after_preflight": true,
  "debug_verbose": false
}
```

Pydantic payload / TypedDict 후보:

```python
AutopilotInputMode = Literal["script", "url", "keyword"]
AutopilotImageCount = int | Literal["auto"]

class AutopilotOptions(TypedDict):
    input_mode: AutopilotInputMode
    script: str
    url: str
    keyword: str
    tone: str
    target_minutes: str
    regenerate_mode: SourceRegenerateMode
    visual_source_mode: VisualSourceMode
    image_count: AutopilotImageCount
    render_after_preflight: bool
    debug_verbose: bool
```

validation:

- `input_mode=script`: `script` 필수.
- `input_mode=url`: `url` 필수, private/localhost 차단은 기존 source fetch 정책 재사용.
- `input_mode=keyword`: `keyword` 필수, Brave hard limit 확인.
- `image_count`는 `"auto"` 또는 1~48 정수.
- `debug_verbose=false` 기본값.

### Status

`GET /api/projects/{pid}/autopilot/status`

### Events

`GET /api/projects/{pid}/autopilot/events?limit=100`

최근 오토파일럿 이벤트 로그를 반환한다.

### Debug Snapshot

`GET /api/projects/{pid}/autopilot/debug`

현재 단계, 관련 worker 상태, 마지막 실패, 복구 힌트를 반환한다.

### Pause

`POST /api/projects/{pid}/autopilot/pause`

### Resume

`POST /api/projects/{pid}/autopilot/resume`

### Cancel

`POST /api/projects/{pid}/autopilot/cancel`

## 11. 구현 단계

### Phase 1. 상태/DB/API 골격

작업:

- autopilot DB 컬럼 추가.
- status/start/pause/resume/cancel API 추가.
- events/debug API 추가.
- 프로젝트별 `autopilot/events.jsonl`, `debug_snapshot.json`, `last_failure.json` writer 추가.
- Step 1 UI에 오토파일럿 카드 추가.
- 기존 project status polling에 autopilot 상태 포함.

완료 기준:

- 버튼 클릭 시 `queued`.
- worker 없이도 status가 UI에 표시.
- 단계 전환 이벤트가 `events.jsonl`에 남는다.
- 실패 snapshot이 UI/API에서 확인된다.

### Phase 2. 직접 대본 -> 최종 렌더

작업:

- script input mode 구현.
- save/compile 자동 실행.
- TTS 큐 등록 및 완료 대기.
- 이미지 batch 큐 등록 및 완료 대기.
- preflight 후 render 큐 등록.
- render report 확인.

완료 기준:

- 직접 대본 입력만으로 output 생성.

### Phase 3. URL/키워드 -> 최종 렌더

작업:

- URL analyze 자동 연결.
- keyword collect 자동 연결.
- source draft worker enqueue/wait.
- apply 자동 연결.
- copy risk pause 구현.

완료 기준:

- URL 또는 키워드 입력만으로 대본 생성 후 output 생성.
- Brave hard limit 유지.

### Phase 4. Pause/Resume/Cancel 안정화

작업:

- phase별 재진입 가능성 점검.
- 이미 완료된 단계는 건너뛰기.
- 실패한 단계는 명확한 로그 제공.
- cancel 시 아직 시작하지 않은 후속 큐 등록 방지.
- pause/error 시 `last_failure.json`과 복구 힌트 생성.
- resume 시 이전 실패 코드와 해결 여부를 이벤트에 기록.

완료 기준:

- 서버 재시작/중단 후 상태가 꼬이지 않음.
- 어떤 phase에서 멈췄는지 UI에서 1분 안에 파악 가능.

### Phase 5. 브라우저 검증 확장

작업:

- `scripts/check_browser_smoke.py`에 autopilot 패널 확인 추가.
- script-mode dry smoke 추가.
- URL/keyword는 외부 호출 없는 mock route test 위주.

완료 기준:

- `scripts/final_verification.ps1`에 autopilot 테스트 포함.

### Phase 6. Report/Operator 통합

작업:

- render report에 `autopilot_job_id`, `autopilot_input_mode`, `autopilot_phase_history_count`를 추가한다.
- Operator dashboard에 `최근 Autopilot Runs` 섹션을 추가한다.
- 표시 항목:
  - total/success/error/paused/canceled
  - 평균 완료 시간
  - 최근 실패 error code top 5
  - 최근 GPU wait timeout 수
- `autopilot/events.jsonl`과 `render_report.json`을 job id로 연결한다.

완료 기준:

- Operator에서 최근 오토파일럿 성공/실패 추세를 볼 수 있다.
- render report에서 어떤 autopilot run이 만든 결과물인지 추적 가능하다.

## 12. 테스트 계획

필수 테스트:

- `test_autopilot_routes.py`
  - start/status/pause/resume/cancel.
  - 동시 실행 409.
  - 잘못된 입력 400.
- `test_autopilot_worker.py`
  - script mode end-to-end 상태 전이.
  - URL mode source draft wait.
  - keyword mode Brave limit 초과 pause.
  - copy risk pause.
  - TTS 실패 error.
  - image 실패 error.
  - preflight 실패 pause.
  - render 완료 report 확인.
  - 각 phase 진입/완료 이벤트 로그 생성.
  - 실패 시 `last_failure.json` 생성.
  - verbose off 상태에서 원문/전체 대본이 로그에 저장되지 않음.
  - phase handler 순수 함수 mock으로 외부 TTS/ComfyUI/render 없이 상태 전이 검증.
  - dispatcher 테스트는 DB update와 enqueue 호출 여부만 검증.
- `test_browser_smoke.py` 또는 기존 script 확장.
  - Autopilot 패널 존재.
  - 버튼/상태 텍스트 표시.
  - `디버그 보기` 패널 표시.

mock 전략:

- phase handler:
  - `(project, options, context) -> PhaseResult` 형태의 순수 함수로 작성.
  - worker polling, sleep, 외부 API를 직접 호출하지 않는다.
- dispatcher:
  - `PhaseResult.side_effect_request`를 보고 실제 enqueue/service 호출.
  - 테스트에서는 dispatcher 의존성을 fake adapter로 교체한다.
- adapter 후보:
  - `SourceAdapter`
  - `TtsAdapter`
  - `ImageAdapter`
  - `PlanAdapter`
  - `RenderAdapter`

검증 명령:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1
python -m pytest tests\test_autopilot_routes.py tests\test_autopilot_worker.py -q
python scripts\check_browser_smoke.py
powershell -ExecutionPolicy Bypass -File .\scripts\final_verification.ps1
```

## 13. 완료 기준

- [ ] 대본 입력 후 오토파일럿으로 최종 render output 생성.
- [ ] URL 입력 후 분석/각색/대본 적용/TTS/Image/Render 완료.
- [ ] 키워드 입력 후 Brave 무료 한도 내 source 수집부터 render 완료.
- [ ] 중간 실패 시 pause/error가 명확히 표시.
- [ ] 유료 API fallback은 기본 비활성.
- [ ] 업로드/게시 자동 실행은 기본 비활성.
- [ ] GPU-heavy 작업이 순차 worker 정책을 따른다.
- [ ] GPU wait가 5분을 넘으면 자동 pause되고 current owner가 표시된다.
- [ ] render report와 Operator 지표에 오토파일럿 결과가 반영된다.
- [ ] 각 phase 진입/완료/실패 로그가 남는다.
- [ ] 실패 시 `last_failure.json`과 UI 복구 힌트가 표시된다.
- [ ] 로그에 원문 기사 전체나 대본 전체를 저장하지 않는다.
- [ ] pause/resume 시 phase별 skip condition이 적용된다.
- [ ] apply 전 기존 `user_script` 덮어쓰기 위험을 pause 또는 백업으로 처리한다.
- [ ] 브라우저 smoke와 final verification이 통과한다.

## 14. 구현 우선순위

가장 현실적인 순서:

1. Phase 1: 상태/API/UI 골격.
2. Phase 2: 직접 대본 입력 -> 최종 렌더.
3. Phase 3: URL/키워드 입력 -> 최종 렌더.
4. Phase 4: pause/resume/cancel 안정화.
5. Phase 5: browser smoke/final verification 확장.
6. Phase 6: report/operator 통합.

먼저 script mode를 끝내는 이유:

- 외부 URL/Brave/Ollama 변수 없이 TTS/Image/Render chain을 검증할 수 있다.
- chain 안정화 후 URL/키워드 입력만 앞단에 붙이면 된다.

## 15. 결론

오토파일럿은 새 렌더 시스템이 아니라 기존 자동화 자산을 “작업 지휘자”로 묶는 기능이다.

핵심은 다음 세 가지다.

- 기존 worker를 재사용한다.
- 자동 진행 중에도 pause/resume/cancel로 제어권을 남긴다.
- 무료 한도, GPU guard, render report를 오토파일럿의 기본 안전장치로 삼는다.
## 2026-04-26 Phase 1 Implementation Update

- Completed:
  - autopilot DB fields and typed project/status exposure
  - `app/services/autopilot.py` event/debug snapshot writer
  - `app/routers/autopilot.py` start/status/events/debug/pause/resume/cancel API
  - Step 1 Autopilot card with status, recent events, and debug snapshot
  - route/status regression tests and typecheck coverage
- Additional implementation now completed:
  - `app/workers/autopilot_worker.py`
  - `script` mode orchestration path for save/compile -> TTS -> image queue/wait -> plan refresh -> preflight -> render queue/wait
  - queued claim, heartbeat, and stale recovery for running autopilot jobs
  - `url` / `keyword` orchestration path for source collect -> draft worker wait -> risk check -> auto apply
  - `user_script` overwrite pause with `pre_apply_backup.txt`
  - Brave limit pause handling
- Deferred to next implementation phase:
  - pause/resume 재진입 정밀화
  - richer failure hints / retry strategy wiring
  - operator-level autopilot run aggregates
