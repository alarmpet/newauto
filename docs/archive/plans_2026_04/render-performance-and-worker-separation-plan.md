# Render Performance And Worker Separation Plan

상태: `[완료]`

## 목표

- Ken Burns 이미지 렌더가 비정상적으로 길어지는 문제를 막는다.
- 렌더 실패 시 오래 남는 중간 산출물을 정리한다.
- SQLite 동시 접근 충돌을 줄인다.
- 렌더를 웹서버 요청 프로세스와 분리해 `uvicorn --reload` 와 독립적으로 돌린다.
- worker heartbeat 기반 stale render 복구를 넣는다.
- Step 4 UI에서 `queued` 상태와 worker heartbeat를 보여준다.

## 최종 권장 순서

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 5 (WAL)
5. Phase 6 (worker)
6. Phase 7 (watchdog)
7. Phase 4 (속도)
8. Phase 8 (UI)

## 완료 내역

### Phase 1 `[완료]`

- `app/services/render.py`
- Ken Burns 이미지 입력을 `-loop 1 -framerate 1 -i` 로 바꿨습니다.
- `zoompan` 뒤에 `trim=duration=...` 와 `setpts=PTS-STARTPTS` 를 넣어 목표 길이만 정확히 출력하게 했습니다.

### Phase 2 `[완료]`

- `_run_with_progress()` 에 runaway duration guard를 넣었습니다.
- 예상 길이의 1.5배를 넘기면 FFmpeg 프로세스를 종료하고 명확한 오류를 반환합니다.
- 회귀 테스트를 추가했습니다.

### Phase 3 `[완료]`

- 렌더 예외 시 `_visual_landscape.mp4`, `_visual_shorts.mp4`, `audio_raw.wav` 를 정리하도록 했습니다.
- 실패한 렌더가 디스크를 계속 잡아먹지 않게 했습니다.

### Phase 5 `[완료]`

- `app/db.py` 연결 시 아래 pragma를 적용했습니다.
- `journal_mode=WAL`
- `synchronous=NORMAL`
- `busy_timeout=5000`

### Phase 6 `[완료]`

- `app/workers/render_worker.py` 를 추가했습니다.
- `app/workers/worker_lock.py` 로 단일 worker lock을 넣었습니다.
- `/api/projects/{pid}/render` 는 이제 즉시 렌더하지 않고 `queued` 상태로 enqueue 합니다.
- startup 시 detached worker 프로세스를 띄우도록 `app/main.py` 를 변경했습니다.

### Phase 7 `[완료]`

- `render_job_id`
- `render_started_at`
- `render_heartbeat_at`
- worker가 heartbeat를 주기적으로 갱신하고, watchdog가 stale render를 `error` 로 복구합니다.
- startup recovery도 render 메타데이터를 함께 정리하도록 보강했습니다.

### Phase 4 `[완료]`

- `zoompan` 입력 overscan을 기존 `2x` 에서 `1.2x` 수준으로 낮췄습니다.
- Ken Burns 렌더의 불필요한 스케일 비용을 줄였습니다.

### Phase 8 `[완료]`

- Step 4 UI가 `queued` 상태를 표시합니다.
- render log 영역에 queue 안내와 최근 heartbeat를 함께 보여줍니다.
- render 상태 타입도 `queued` 를 포함하도록 맞췄습니다.

## 검증

- `scripts/typecheck.ps1`
- `node --check app/static/app.js`
- `.\omnivoice_env\Scripts\python.exe -m unittest discover -s tests -v`

## 추가된 테스트

- `tests/test_render_visual_track.py`
  - trim/setpts 적용
  - kenburns 이미지 입력에서 `-t` 제거
  - runaway duration 강제 중단
- `tests/test_render_worker.py`
  - queued render claim
  - stale heartbeat recovery
  - stale worker lock 재사용
- `tests/test_feature_workflow.py`
  - render 시작 시 `queued` 상태 저장

## 메모

- 테스트에서는 실제 background worker가 돌지 않도록 `NEWAUTO_DISABLE_BACKGROUND_WORKERS=1` 경로를 추가했습니다.
- 실사용 경로에서는 startup 시 worker와 watchdog가 정상 동작합니다.
