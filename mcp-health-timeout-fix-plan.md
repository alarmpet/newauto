# [목표] MCP 워크플로우 타임아웃 근본 원인 분석 및 해결 계획

사용자가 HPSL 비디오 워크플로우를 진행할 때 (특히 "진행" 명령 시점) `Request timed out` 오류가 반복적으로 발생하는 문제의 원인을 규명하고 이를 해결하기 위한 구현 계획입니다.

## 1. 근본 원인 분석 (Root Cause Analysis)

현재 시스템에서 타임아웃이 발생하는 원인은 대본 생성이나 LLM 호출 자체가 지연되어서가 아니라, **MCP 클라이언트가 FastAPI 서버의 상태를 확인하는 과정에서 발생하는 병목 현상** 때문입니다.

1. **상태 확인 루프**: MCP 툴(`continue_stepwise_hpsl_video_workflow`)이 실행될 때 가장 먼저 `_ensure_server()` 함수가 호출되어 서버가 살아있는지 확인합니다.
2. **짧은 타임아웃**: 서버 상태 확인(`_health_ok`)은 `GET /health` API를 호출하며, **5초**의 짧은 타임아웃을 가집니다.
3. **무거운 /health API 로직**: 서버의 `GET /health` 엔드포인트는 `get_system_health()`를 호출하는데, 이 함수 내에서 `get_omnivoice_runtime_status()`가 실행됩니다. 이 함수는 파이썬 환경(PyTorch, CUDA 가용성 등)을 확인하기 위해 **다수의 무거운 동기적 `subprocess.run` 프로브**를 매번 실행합니다. 이 과정은 5초 이상 소요됩니다.
4. **오판 및 무한 대기**: `GET /health`가 5초 안에 응답하지 않으므로 MCP는 서버가 죽었다고 오판합니다. 이후 서버 재시작을 시도(포트가 이미 사용 중이라 실패)하고, **45초 동안 `GET /health`를 반복 호출하며 대기**합니다.
5. **LM Studio 타임아웃**: 45초의 대기 시간과 프로브 지연이 합쳐지면서, LM Studio의 MCP 툴 실행 제한 시간인 **60초**를 초과하게 되어 최종적으로 사용자에게 `Request timed out` 오류가 발생합니다.

## 2. 해결 방안 (Action Plan)

`/health` 엔드포인트는 로드 밸런서나 상태 확인(Ping) 목적에 맞게 **즉각적인 응답(10ms 이내)**을 반환하도록 경량화해야 합니다.

### Phase 1: `/health` 엔드포인트 경량화
* **변경 대상**: `app/routers/system.py` 및 `app/services/system_health.py`
* **작업 내용**:
  * `/health` API는 단순히 서버가 구동 중임을 알리는 `{"ok": True}` 수준의 가벼운 응답만 반환하도록 수정합니다.
  * 무거운 `get_omnivoice_runtime_status()` (파이썬/CUDA 프로브) 호출은 `/health`에서 제거합니다.
  * 시스템 진단이 필요한 상세 정보는 기존 `/tools` 또는 새로운 상세 진단 엔드포인트(`/api/system/diagnostics`)로 분리합니다.

### Phase 2: 상태 체크 옵션 도입 (캐싱)
* **변경 대상**: `app/services/python_runtime.py`
* **작업 내용**:
  * 파이썬 런타임 프로브 결과를 서버 시작 시 한 번만 검사하여 메모리에 캐싱하거나, 백그라운드 태스크로 주기적으로 갱신하도록 변경합니다.
  * 동기적인 `subprocess.run` 호출이 메인 이벤트 루프를 막지 않도록 조치합니다.

### Phase 3: MCP 클라이언트의 `_health_ok` 안정화
* **변경 대상**: `scripts/newauto_mcp.py`
* **작업 내용**:
  * (선택적) `_health_ok()` 내의 타임아웃을 5초에서 10초 정도로 안전하게 늘립니다. (Phase 1이 적용되면 5초로도 충분하지만 방어적 코딩 적용)

## 3. 요약 및 향후 진행
서버가 멈춘 것이 아니라, 서버 상태를 묻는 질문(`/health`)에 대답하는 과정이 너무 무거워서 생긴 "오해로 인한 블로킹"이었습니다.

위 계획에 따라 코드를 수정하여 타임아웃 문제를 근본적으로 해결하겠습니다.

---

## 2026-05-07 Codebase Review Update

### What The Current Code Actually Does

- MCP readiness does **not** call `/api/system/health`; it calls root `/health` through `HEALTH_URL = http://127.0.0.1:9001/health` in `scripts/newauto_mcp.py`.
- Root `/health` in `app/main.py` is already lightweight and returns only `{"ok": true}`.
- The heavy path is `/api/system/health` and `/api/system/operator`, because `app/services/system_health.py` called `get_omnivoice_runtime_status()` on every request.
- `get_omnivoice_runtime_status()` runs OmniVoice/PyTorch/CUDA subprocess probes, so repeated operator polling or health checks can still block the FastAPI worker and indirectly make MCP calls feel unstable.
- Recent workflow updates already removed long MCP waits from HPSL, Flow, TTS, and render stages. The remaining health risk is therefore diagnostic endpoint weight, not the stepwise workflow state machine.

### Implemented Corrections

- [x] Kept root `/health` as the lightweight MCP readiness endpoint.
- [x] Changed `get_system_health()` so it uses a cached OmniVoice runtime status by default instead of probing synchronously on every request.
- [x] Added `/api/system/diagnostics` for explicit full runtime probing.
- [ ] Optional follow-up: change the browser's manual System Health button to call `/api/system/diagnostics` after isolating the pre-existing large frontend diff.
- [x] Left `/api/system/operator` on the cached/lightweight health path so periodic operator polling does not repeatedly run OmniVoice/PyTorch probes.
- [x] Confirmed `_health_ok()` still uses root `/health`; the 5-second timeout is sufficient after this review because the endpoint is already trivial.

### Updated Plan

```text
MCP readiness
  -> GET /health
  -> lightweight ok response
  -> no OmniVoice probe

Operator polling
  -> GET /api/system/operator
  -> cached health + queue/gpu/tool/model state
  -> no repeated OmniVoice subprocess probe

Manual diagnostics
  -> GET /api/system/diagnostics
  -> refresh OmniVoice/PyTorch/CUDA runtime probe
  -> cache result for later health/operator reads
```

### Remaining Risks

- If `/api/system/diagnostics` is called while the server has only one worker, the explicit diagnostic request can still take several seconds. That is acceptable because it is now user-triggered rather than part of MCP readiness or periodic operator polling.
- If the process restarts, the OmniVoice runtime cache starts empty. `/api/system/health` will still respond quickly but may show OmniVoice as not cached until diagnostics is run.
