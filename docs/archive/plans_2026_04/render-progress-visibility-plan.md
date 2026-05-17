# Render Progress Visibility Plan

상태: `[완료]`

## 목표

- Step 4에서 렌더가 실제로 멈췄는지, 오래 걸리지만 정상 진행 중인지 바로 알 수 있게 한다.
- `가로형 영상 구성` 같은 긴 FFmpeg 단계 안에서도 세부 진행률, 처리 시간, 속도, ETA를 보여준다.
- `진행 중 70%`가 수십 분 동안 고정되어 보이는 UX를 없앤다.

## 적용된 구현 순서

1. Phase 1 FFmpeg progress 스트림 러너
2. Phase 2 phase 내부 진행률 매핑
3. Phase 6 테스트 잠금
4. Phase 3 loudnorm 처리
5. Phase 5 fallback
6. Phase 4 UI 표시

## Phase 1. FFmpeg progress 스트림 러너 `[완료]`

- `app/services/render.py` 에 `_run_with_progress()` 추가
- `subprocess.Popen(...)` + `-progress pipe:1 -nostats -stats_period 0.5` 적용
- stdout progress와 stderr를 별도 thread로 동시에 drain
- `out_time`, `frame`, `fps`, `speed` 를 실시간으로 파싱

완료 기준:

- 장시간 FFmpeg 단계에서 progress event를 주기적으로 생성한다.
- stderr 출력이 많아도 deadlock 없이 진행된다.

## Phase 2. phase 내부 진행률 매핑 `[완료]`

- 새 상태 필드 추가
  - `render_phase_pct`
  - `render_progress_detail`
  - `render_speed_x`
  - `render_eta_sec`
- `_phase_progress_callback()` 으로 phase 내부 퍼센트를 전체 렌더 퍼센트에 매핑
- `normalize_audio`, `build_visual_*`, `mux_*` 단계에서 실시간 progress 반영

완료 기준:

- 긴 단계 안에서도 `render_progress` 가 계속 증가한다.
- phase 내부 퍼센트와 전체 퍼센트가 함께 저장된다.

## Phase 6. 테스트 잠금 `[완료]`

- `tests/test_render_visual_track.py` 확장
- 잠근 항목:
  - `out_time` 파싱
  - 진행 문자열 포맷
  - phase progress → global progress 매핑
  - progress runner event 생성

완료 기준:

- 핵심 progress 로직이 테스트로 고정되었다.

## Phase 3. loudnorm 처리 `[완료]`

- loudnorm 단계도 `_run_with_progress()` 를 사용하도록 연결
- ETA는 강제하지 않고 안전한 진행 문자열 위주로 처리
- `show_eta=False` 로 heartbeat 중심 상태 표시

완료 기준:

- loudnorm 단계도 완전히 무반응처럼 보이지 않는다.

## Phase 5. fallback 및 안전장치 `[완료]`

- progress 정보가 빈약한 경우에도 주기적으로 progress detail emit
- 출력 파일이 존재하면 크기 기반 fallback 표시
- ETA가 없으면 `output XX.X MB` 형태로 진행 힌트 제공

완료 기준:

- FFmpeg progress가 부족해도 화면 갱신이 계속된다.

## Phase 4. UI 표시 개선 `[완료]`

- Step 4 로그 패널에 `render_progress_detail` 우선 표시
- 세부 진행 문자열이 아직 없을 때도 `세부 진행 정보를 수집하는 중입니다.` 로 표시
- `/status` 응답에 새 render progress 필드 반영

표시 예시:

```text
Current phase: 가로형 영상 구성

세부 진행: 43% | 1.31x | frame 4921 | elapsed 00:03:24 | ETA 00:05:42
```

완료 기준:

- 사용자가 렌더가 실제로 진행 중인지 화면만 보고 판단할 수 있다.

## 검증

- `scripts/typecheck.ps1`
- `node --check app/static/app.js`
- `omnivoice_env\Scripts\python.exe -m unittest discover -s tests -v`

## 기대 효과

- 수십 분 동안 같은 퍼센트에 멈춘 것처럼 보이는 문제가 줄어든다.
- 실제 정지와 정상 진행을 더 쉽게 구분할 수 있다.
- 불필요한 중복 렌더 재시작을 줄일 수 있다.
