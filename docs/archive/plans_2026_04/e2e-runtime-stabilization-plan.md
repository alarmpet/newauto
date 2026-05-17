# End-to-End Runtime Stabilization Plan

작성일: 2026-04-26

## 1. 목표

현재 자동화 파이프라인은 synthetic 입력 기준으로 `render` 단독 검증은 성공했지만, 실제 `script -> TTS -> image -> render` end-to-end 실행은 런타임 경계에서 막혀 있다.

- Render: synthetic 1분 샘플로 `output.mp4` 생성 성공
- TTS: 실행 Python 불일치와 OmniVoice 모델 로딩 실패로 중단
- Image generation: ComfyUI 서버는 살아 있지만 `KSampler` 실행 중 `stderr/logger flush` 오류로 실패

이 문서의 목표는 문제를 임시 우회하지 않고, 코드베이스의 실제 실행 경로에 맞춰 안정화 계획을 확정한 뒤 1분 real end-to-end 테스트로 닫는 것이다.

## 2. 외부 심층 분석 반영 요약

`C:\Users\petbl\.gemini\antigravity\brain\0baaa172-8c92-4f84-b28c-27338b8a4661\e2e_stabilization_deep_analysis.md`를 검토한 결과, 기존 계획에 다음 보강이 필요하다.

| 항목 | 반영 결정 |
|---|---|
| Autopilot의 직접 `run_tts_job(pid)` 호출 | TTS를 render/image처럼 `queued -> worker poll` 패턴으로 통일한다. Autopilot은 TTS를 직접 실행하지 않고 큐 등록 후 상태를 기다린다. |
| Worker Python 정책 | `autopilot_worker`는 app Python 유지, 실제 OmniVoice 실행만 resolved OmniVoice Python subprocess로 격리한다. |
| TTS 오류 소실 | `tts_error.json`과 DB 상태 메시지를 남긴다. Autopilot에는 generic error 대신 원인 코드와 action hint를 전달한다. |
| Worker 로그 소실 | `app/main.py`의 `stdout/stderr=DEVNULL`을 `storage/logs/{worker}.log` redirect로 바꾼다. |
| GPU guard race condition | 파일 read-check-write 방식에 atomic file lock을 추가하고, 중기적으로 SQLite lock table 전환을 검토한다. |
| `unload_model()` 불완전 | `del _model`, `gc.collect()`, `torch.cuda.empty_cache()` 순서로 명시한다. |
| ComfyUI smoke와 Operator 연결 | 실시간 health에서 긴 smoke를 돌리지 않고 `storage/diagnostics/comfyui_smoke_latest.json` 캐시를 읽는다. |
| Python resolver 검증 부족 | 디렉터리 존재가 아니라 candidate Python으로 `import omnivoice`, `import torch`, CUDA availability를 실제 실행해 검증한다. |
| E2E 성공 조건 부족 | `scene_plan.scenes > 0`뿐 아니라 scene duration, render total duration, media existence를 확인한다. |

## 3. 현재 확인된 사실

| 영역 | 실제 상태 | 근거 |
|---|---|---|
| Render | 정상 | `storage/projects/17f7cb051329/output.mp4`, duration `60.3s`, report `done` |
| TTS import | 기본 Python에서 실패 가능 | 기본 Python에는 `omnivoice`가 없음 |
| TTS model load | OmniVoice env에서도 실패 | `OmniVoice.from_pretrained(...)` 중 Windows `os error 1455` |
| Worker spawn | 취약 | `app/main.py`가 worker를 `sys.executable`로 실행하고 로그를 `DEVNULL`로 버림 |
| Autopilot TTS | 취약 | `app/services/autopilot.py`가 `run_tts_job(pid)`를 직접 호출 |
| ComfyUI server | alive | `/system_stats` 응답 정상 |
| ComfyUI workflow submit | 정상 | `prompt_id` 반환, `node_errors={}` |
| ComfyUI sampling | 실패 | history status `error`, `KSampler`, `OSError: [Errno 22] Invalid argument` |
| Image worker diagnostics | 1차 보강 완료 | ComfyUI `execution_error`를 timeout 대신 즉시 surface |

## 4. 핵심 문제

### 4.1 TTS 실행 경로가 아직 단일화되지 않음

기존 계획은 TTS subprocess runner를 도입한다고 되어 있었지만, 현재 코드에는 Autopilot이 `run_tts_job(pid)`를 직접 호출하는 경로가 남아 있다. 이 상태에서 `run_tts_job()` 내부만 subprocess로 바꾸면 sync/async 의미가 흐려지고, render/image worker와 다른 상태 전이 패턴이 유지된다.

결정:

- `app/workers/tts_worker.py`를 새로 추가한다.
- `/api/render/{pid}/tts/start`와 Autopilot은 `tts_state="queued"`로 큐 등록만 한다.
- `tts_worker`가 queued 프로젝트를 claim하고, resolved OmniVoice Python으로 `scripts/run_tts_job.py --project-id PID`를 실행한다.
- Autopilot은 `_wait_for_state(pid, "tts_state", "done")` 패턴으로 기다린다.

### 4.2 Worker Python과 TTS Python을 분리해야 함

Autopilot, render, source draft, image worker는 app Python으로 충분하다. OmniVoice만 별도 env가 필요하다. 따라서 전체 앱을 `omnivoice_env`로 띄우는 방향은 피하고, TTS 실행 subprocess만 resolved OmniVoice Python을 사용한다.

완료 기준:

- app Python에 `omnivoice`가 없어도 앱과 Autopilot이 정상 실행된다.
- TTS worker가 사용할 Python path가 `/api/system/health` 또는 Operator에 노출된다.
- resolver는 candidate Python에서 실제 import 검증을 수행한다.

### 4.3 GPU guard가 프로세스 간 원자성을 보장하지 않음

현재 `gpu_guard.acquire()`는 파일을 읽고, 상태를 확인하고, 다시 쓰는 방식이다. detached worker가 동시에 acquire하면 둘 다 성공할 수 있는 race condition이 있다.

단기 결정:

- Windows에서는 `msvcrt.locking()` 또는 cross-platform file lock helper로 `gpu_guard.json` read/check/write 구간을 감싼다.
- `current_owner()`는 lock 실패와 무관하게 마지막 owner를 읽어 상태 카드에 표시한다.

중기 결정:

- SQLite WAL 기반 `gpu_locks` table로 전환할 수 있도록 인터페이스는 유지한다.

### 4.4 TTS 오류가 Autopilot에서 generic error로 사라짐

현재 `run_tts_job()` 실패는 stderr traceback 후 `tts_state="error"`만 남길 수 있다. Autopilot은 이후 `TTS generation did not complete successfully.`만 보게 된다.

결정:

- `storage/projects/{pid}/tts/tts_error.json` 저장
- DB에는 최소 `render_last_log` 또는 신규 `tts_error` 필드로 마지막 오류 요약 저장
- error code 예:
  - `TTS_IMPORT_FAILED`
  - `TTS_MODEL_LOAD_PAGEFILE_1455`
  - `TTS_GPU_BUSY`
  - `TTS_SUBPROCESS_EXITED`

### 4.5 Worker 로그가 사라짐

`app/main.py`는 현재 worker stdout/stderr를 `DEVNULL`로 보낸다. 런타임 traceback을 잃는 구조다.

결정:

- `storage/logs/render_worker.log`
- `storage/logs/source_draft_worker.log`
- `storage/logs/image_worker.log`
- `storage/logs/autopilot_worker.log`
- `storage/logs/tts_worker.log`

모든 worker spawn helper는 append mode 로그 파일로 stdout/stderr를 redirect한다.

### 4.6 ComfyUI health는 alive가 아니라 generation 가능 여부를 봐야 함

`/system_stats`가 정상이어도 KSampler 단계에서 실패할 수 있다. 단, Operator status 호출마다 실제 image smoke를 돌리면 너무 무겁다.

결정:

- `scripts/check_comfyui_generation.py`는 수동 또는 preflight에서 실행한다.
- 결과는 `storage/diagnostics/comfyui_smoke_latest.json`에 저장한다.
- `list_tool_status()`는 이 캐시 파일만 읽어 `last smoke: ok/error`를 표시한다.

## 5. 구현 계획

### Phase 0. 진단 산출물 고정

목표: 현재 실패를 재현 가능한 데이터로 남긴다.

추가 산출물:

- `storage/diagnostics/e2e_runtime/latest.json`
- `scripts/check_e2e_runtime_health.py`

체크 항목:

- app Python path
- resolved OmniVoice Python path
- candidate Python별 `import omnivoice`, `import torch`, `torch.cuda.is_available()`
- pagefile/free memory snapshot
- GPU guard owner
- ComfyUI `/system_stats`
- ComfyUI smoke cache 상태
- latest TTS health/error 상태

### Phase 1. Worker 로그와 Python resolver 고정

목표: 실패 원인을 잃지 않고, TTS Python을 실제 import 기준으로 선택한다.

변경 파일:

- `app/main.py`
- 신규 `app/services/python_runtime.py`
- `scripts/resolve_omnivoice_python.ps1`

작업:

- worker spawn 공통 helper 추가
- worker stdout/stderr를 `storage/logs/*.log`로 redirect
- resolved OmniVoice Python 후보 순서 정리
- 후보 검증은 파일 존재가 아니라 subprocess import 실행으로 수행

완료 기준:

- 기본 Python에 `omnivoice`가 없어도 app worker 시작 가능
- Operator 또는 health payload에서 worker log path와 resolved TTS Python 확인 가능
- typecheck 통과

### Phase 2. TTS queued worker 패턴 도입

목표: TTS 실행을 render/image worker와 같은 큐 기반 패턴으로 통일한다.

신규/변경 파일:

- 신규 `app/workers/tts_worker.py`
- 신규 `scripts/run_tts_job.py`
- `app/services/tts.py`
- `app/services/autopilot.py`
- `app/routers/render.py`
- `app/db.py`
- `app/types.py`

상태 전이:

```text
idle -> queued -> running -> done
idle -> queued -> running -> error
```

정책:

- route와 Autopilot은 `tts_state="queued"`만 설정한다.
- `tts_worker`가 queued 프로젝트를 claim한다.
- `tts_worker`는 resolved OmniVoice Python으로 `scripts/run_tts_job.py --project-id PID` 실행한다.
- `scripts/run_tts_job.py`는 실제 OmniVoice import/model load/synthesis를 담당한다.
- 실패 시 `tts_error.json`과 DB 오류 요약을 남긴다.

Autopilot 변경:

- `run_tts_job(pid)` 직접 호출 제거
- TTS phase는 큐 등록 후 `_wait_for_state()` 사용
- 실패 시 `tts_error.json`을 읽어 `last_failure.json`에 error code/action hint 반영

완료 기준:

- app Python에서 `omnivoice` import가 불가능해도 TTS queue 등록 가능
- TTS 실패 원인이 Autopilot UI/debug log에 표시
- 기존 `tests/test_autopilot_worker.py`의 direct patch 전략을 queued worker mock 전략으로 갱신

### Phase 3. OmniVoice 메모리 안정화

목표: `os error 1455` 재현 조건을 줄이고, 실패 시 사용자가 조치 가능한 원인으로 표시한다.

변경 파일:

- `app/services/tts.py`
- `scripts/check_omnivoice_health.py`
- `scripts/run_tts_job.py`

작업:

- `unload_model()`에 `del _model`, `gc.collect()`, `torch.cuda.empty_cache()` 반영
- TTS runner 시작 전 GPU owner와 memory snapshot 기록
- health check는 owner `healthcheck:omnivoice`, timeout 0 또는 즉시 skip 정책 사용
- `OSError` 메시지에 `1455`가 있으면 `TTS_MODEL_LOAD_PAGEFILE_1455`로 분류

완료 기준:

- health check가 다른 GPU 작업을 장시간 대기시키지 않음
- 1455 실패가 generic TTS error가 아니라 명확한 action hint로 표시

### Phase 4. GPU guard 원자성 보강

목표: 여러 detached worker가 동시에 GPU lock을 잡는 race condition을 제거한다.

변경 파일:

- `app/services/gpu_guard.py`
- `tests/test_system_operator.py`

작업:

- `gpu_guard.json` 접근 구간에 atomic lock helper 적용
- lock 파일 손상 시 recovery path 명시
- `current_owner()`와 `get_status()`는 Operator status card에서 계속 사용 가능하게 유지

완료 기준:

- 병렬 acquire 테스트에서 한 owner만 성공
- timeout 중 owner 정보가 정확히 노출

### Phase 5. ComfyUI 재기동과 generation smoke 체계

목표: ComfyUI alive가 아니라 실제 이미지 생성 가능 여부를 검증한다.

신규/변경 파일:

- `scripts/restart_comfyui.ps1`
- `scripts/check_comfyui_generation.py`
- `app/services/tool_registry.py`
- `app/services/comfyui_pipeline.py`

작업:

- ComfyUI stdout/stderr를 `storage/logs/comfyui.log`로 redirect
- `PYTHONIOENCODING=utf-8`, `PYTHONUNBUFFERED=1` 적용
- 512x512 low-cost prompt smoke 추가
- smoke 결과를 `storage/diagnostics/comfyui_smoke_latest.json`에 저장
- `list_tool_status()`는 캐시만 읽음
- `import_history_image()`가 이미 조회한 `ComfyImageResult` 또는 history를 받을 수 있게 리팩터링해 중복 `/history` 호출 제거

완료 기준:

- smoke 성공 시 output image path 기록
- smoke 실패 시 ComfyUI history execution error와 log path 기록
- image worker가 생성 결과를 project media로 import하고 scene/render plan 자동 갱신

### Phase 6. End-to-end 재검증

목표: synthetic 없이 실제 1분 파이프라인을 끝까지 검증한다.

흐름:

```text
create project
save 1-minute script
queue TTS
wait TTS done
queue ComfyUI image batch, count 3~6
auto refresh scene/render plan
preflight
render
render report
```

성공 기준:

- `tts_state=done`
- `body_image_state=done`
- `scene_plan.scenes > 0`
- 모든 scene duration이 `> 0`
- `render_plan.segments > 0`
- `render_plan.total_duration > 0`
- render segment media file 존재
- `preflight.ok=true`
- `render_state=done`
- output duration 45~90초
- render report `status=done`

산출물:

- `storage/diagnostics/e2e_runtime/{timestamp}.json`
- sample project id
- output path
- TTS runtime info
- ComfyUI prompt ids
- render report summary
- worker log path summary

## 6. 코드 변경 파일 예상

| 파일 | 변경 이유 |
|---|---|
| `app/main.py` | worker spawn helper, log redirect, `tts_worker` startup |
| `app/workers/tts_worker.py` | TTS queue worker 신규 |
| `app/services/python_runtime.py` | OmniVoice Python resolver |
| `app/services/tts.py` | subprocess-safe TTS service, error persistence, unload 개선 |
| `scripts/run_tts_job.py` | resolved OmniVoice Python에서 실제 synthesis 실행 |
| `scripts/check_e2e_runtime_health.py` | 종합 진단 |
| `scripts/check_omnivoice_health.py` | GPU-safe health check |
| `scripts/check_comfyui_generation.py` | 실제 이미지 생성 smoke |
| `scripts/restart_comfyui.ps1` | stderr 안정화 재기동 |
| `app/services/gpu_guard.py` | atomic acquire/release |
| `app/services/system_health.py` | TTS/ComfyUI runtime status 표시 |
| `app/services/tool_registry.py` | ComfyUI smoke cache 표시 |
| `app/services/comfyui_pipeline.py` | 중복 history 조회 제거 |
| `app/services/autopilot.py` | TTS direct call 제거, queued/wait 패턴 |
| `app/routers/render.py` | TTS start route를 queue 기반으로 변경 |
| `app/db.py`, `app/types.py` | TTS queued/error metadata 반영 |
| `tests/test_*` | resolver, TTS worker, GPU lock, ComfyUI smoke cache 검증 |

## 7. 테스트 계획

단위 테스트:

- Python resolver 후보 순서와 import 검증
- TTS worker claim/skip/retry 상태 전이
- TTS subprocess 실패 JSON parsing
- `tts_error.json` 저장
- `unload_model()` cleanup 호출
- GPU guard 병렬 acquire 방지
- ComfyUI execution error parsing
- ComfyUI smoke cache를 `ToolStatus`에 반영
- E2E validation이 duration 0 fallback을 실패 처리

통합 테스트:

- synthetic TTS render 1분 테스트 유지
- ComfyUI smoke는 CI에서는 mock, 로컬 manual에서는 real
- OmniVoice real health는 `NEWAUTO_RUN_REAL_TTS_HEALTH=1`일 때만 실행

검증 명령:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1
python -m pytest tests\test_comfyui_client.py tests\test_image_worker.py tests\test_tts_pipeline.py tests\test_system_operator.py tests\test_autopilot_worker.py -q
python scripts\check_e2e_runtime_health.py
python scripts\check_comfyui_generation.py
powershell -ExecutionPolicy Bypass -File .\scripts\final_verification.ps1
```

## 8. 리스크와 결정

| 리스크 | 결정 |
|---|---|
| 앱 전체를 `omnivoice_env`로 띄우면 다른 의존성이 깨질 수 있음 | app Python과 TTS Python을 분리 |
| TTS direct call과 queued worker가 공존하면 상태 전이가 이중화됨 | direct call 제거, queued worker로 통일 |
| ComfyUI 자동 restart가 사용자 작업을 끊을 수 있음 | 자동 restart는 하지 않고 script/operator action으로 분리 |
| health check가 GPU를 점유할 수 있음 | GPU busy면 즉시 skip하고 cached status 표시 |
| real TTS/image 테스트는 오래 걸림 | 일반 테스트와 real smoke를 분리 |
| pagefile 1455는 OS 상태 의존 | 코드에서는 원인 기록과 action hint 제공, OS 설정 변경은 사용자 확인 후 수행 |

## 9. 우선순위

1. Worker 로그 redirect와 Python resolver 실제 import 검증
2. TTS를 queued worker 패턴으로 통일하고 Autopilot direct `run_tts_job()` 제거
3. TTS 오류 DB/JSON persistence 추가
4. `unload_model()` cleanup 강화
5. `gpu_guard.py` atomic lock 보강
6. ComfyUI restart/smoke/cache 체계 추가
7. real 1분 end-to-end 재검증

## 10. 현재 결론

현재 실패는 render 기능 문제가 아니라 runtime boundary 문제다.

- TTS는 Python과 worker 실행 경계를 분리해야 한다.
- Autopilot은 TTS를 직접 실행하지 말고 queued worker를 기다려야 한다.
- ComfyUI는 alive check가 아니라 generation smoke가 필요하다.
- worker 로그와 TTS error persistence 없이는 다음 실패도 원인 추적이 어렵다.

따라서 다음 구현 라운드는 기능 추가가 아니라 `TTS worker 분리 + 로그/진단 + GPU lock 안정화`를 우선으로 진행한다.
