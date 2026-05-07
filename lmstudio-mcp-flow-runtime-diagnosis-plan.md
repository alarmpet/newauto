# LM Studio MCP Flow Runtime Diagnosis Plan

Date: 2026-05-07
Target project: `ad246c22458f`
Goal: LM Studio chat에서 `continue_stepwise_hpsl_video_workflow`를 눌렀을 때 Flow 자동화가 실제 최신 코드 경로로 안정적으로 진행되게 만든다.

## 1. Current Findings

### Finding A - LM Studio output does not match current MCP code

LM Studio가 방금 보여준 메시지:

```text
최종 단계인 Flow 이미지/영상 생성 과정에서 시간 초과(Timeout) 에러가 발생...
Flow 웹 UI 문제...
권한/인증 필요...
```

이 문구는 현재 `scripts/newauto_mcp.py`에 없다.

현재 코드가 정상 실행되면 `flow_generate`에서는 아래처럼 말해야 한다.

```text
4단계 진행: Flow Generate 클릭만 완료했어.
...
이 호출에서는 다운로드/attach를 기다리지 않았어.
```

`flow_wait_sentence` 실패도 아래처럼 나와야 한다.

```text
4단계 대기: Flow 결과 다운로드/연결을 아직 끝내지 못했어.
...
same sentence retry...
```

따라서 현재 LM Studio 응답은 최신 MCP 함수의 실제 반환문이 아닐 가능성이 높다.

Likely causes:

- LM Studio가 최신 MCP 프로세스를 재시작하지 않았다.
- LM Studio가 `run-newauto-mcp.cmd`가 아닌 다른 MCP 설정을 쓰고 있다.
- MCP tool call이 내부 timeout/transport error로 실패했고, Gemma4가 그 실패를 일반 문장으로 요약했다.
- LM Studio 채팅 컨텍스트에 과거 실패 패턴이 남아서 실제 상태와 다른 답변을 만들고 있다.

### Finding B - No visible `newauto_mcp.py` process

현재 Windows process list에서 `scripts\newauto_mcp.py` 실행 프로세스가 확인되지 않았다.

Expected:

```text
C:\Users\petbl\local-rag\.venv\Scripts\python.exe C:\Users\petbl\newauto\scripts\newauto_mcp.py
```

Actual:

```text
No matching newauto_mcp.py process found.
```

This means LM Studio의 MCP host가 내부적으로 짧게 실행 후 종료했거나, 다른 connector/runtime이 tool 목록을 stale 상태로 들고 있을 수 있다.

### Finding C - Port 9001 is served by the wrong Python process

`run-newauto-9001.cmd`는 `OMNIVOICE_PYTHON`을 찾아서 실행하도록 되어 있다.

Expected:

```text
C:\Users\petbl\newauto\omnivoice_env\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 9001
```

Actual listener:

```text
PID 20036
C:\Users\petbl\AppData\Local\Programs\Python\Python310\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 9001
```

This matters because:

- Python path가 다르면 installed packages, source import path, stdout encoding, worker env가 달라질 수 있다.
- 동시에 `8001`, `9001`, worker processes가 Python 3.10과 `omnivoice_env` 양쪽에서 섞여 떠 있다.
- LM Studio MCP는 `BASE_URL=http://127.0.0.1:9001`만 보고 호출하므로, 어떤 server code가 실제로 떠 있는지 보장해야 한다.

### Finding D - API server is alive, but project text is mojibake

`GET http://127.0.0.1:9001/api/projects/ad246c22458f` succeeds, but Korean script/source data is mojibake.

This is not the direct cause of Flow timeout, but it explains poor script/source quality and can produce wrong visual prompts.

Current project coverage:

```text
flow_sentence_001.jpeg attached
flow_sentence_002.jpeg attached
missing: 3, 4, 5, 6
```

Current stepwise state:

```json
{
  "next_step": "flow_generate",
  "active_sentence_number": 0
}
```

So the correct next behavior is sentence 3 Generate click, not a final rendering timeout.

### Finding E - Direct MCP function path works outside LM Studio

Direct test through the same Python environment used by `run-newauto-mcp.cmd` worked:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe - <<PY
import scripts.newauto_mcp as m
print(m.continue_stepwise_hpsl_video_workflow("ad246c22458f"))
PY
```

Verified results:

- sentence 1 download/attach succeeded
- sentence 2 stale-file bug was reproduced and then fixed
- sentence 2 fresh download/attach succeeded with `Narration_language_Korean_202605070348.jpeg`
- state moved back to `flow_generate`

Therefore the remaining failure is primarily runtime wiring/observability, not the core local function.

## 2. Root Cause Tree

### P0 root cause - MCP/runtime mismatch

The user-visible LM Studio behavior is not executing the latest committed MCP code path.

Evidence:

- returned Korean error text does not exist in current MCP source
- no visible `newauto_mcp.py` process
- state file says `flow_generate`, but LM Studio talks as if it is a final image/video generation timeout

### P0 root cause - server process drift

The local API server on `9001` is not the expected `omnivoice_env` process.

Risk:

- MCP and web server may import different versions/dependencies
- worker queues may talk to different runtime assumptions
- diagnosis is unreliable until only one blessed server process owns `9001`

### P1 root cause - insufficient tool observability

When MCP fails, the user sees a generic apology instead of:

- which project
- which step
- which Python executable
- which server PID
- which Flow screenshot
- stdout/stderr from `flow_desktop_control.py`
- whether this was MCP transport timeout or Flow UI timeout

### P1 root cause - Flow automation state is too implicit

The current workflow infers Flow state by screenshots/coordinates and file downloads. It works, but failure recovery needs structured proof files:

- last tool call id
- expected sentence number
- screenshot before/after
- download baseline count
- downloaded filename
- attached filename
- next exact action

### P2 root cause - mojibake data quality

The project’s source/script data is already mojibake. Even if Flow automation succeeds, the output topic/script quality is poor.

This should not block runtime stabilization, but it should block final production rendering.

## 3. Recovery Plan

## Phase 0 - Freeze and snapshot current runtime

Status: pending

Tasks:

- Record current process table for:
  - `newauto_mcp.py`
  - `uvicorn app.main:app --port 9001`
  - Flow Chrome profile
  - workers
- Record current TCP listener owner for `9001`, `1234`, `9223`.
- Save current stepwise state and project asset coverage.
- Save latest Flow screenshot.

Acceptance:

- A single diagnostic JSON exists at:

```text
storage/runtime_diagnostics/latest.json
```

It must include:

```json
{
  "timestamp": "...",
  "project_id": "ad246c22458f",
  "stepwise_state": "...",
  "api_server_pid": 20036,
  "mcp_processes": [],
  "flow_windows": [],
  "asset_coverage": {
    "attached": 2,
    "total": 6,
    "missing": [3, 4, 5, 6]
  }
}
```

## Phase 1 - Make MCP version visible inside LM Studio

Status: pending

Add a new MCP tool:

```text
diagnose_newauto_runtime(project_id="")
```

It must return:

- MCP source path
- git commit hash
- Python executable
- process id
- cwd
- `BASE_URL`
- `FLOW_AUTOMATION_BACKEND`
- `FLOW_MODE`
- API server `/health`
- API server PID for port 9001
- stepwise state
- project coverage
- latest screenshots

Expected LM Studio test:

```text
diagnose_newauto_runtime project_id=ad246c22458f
```

Expected response must include current commit:

```text
commit: f8c58eab7c8dc76a3471d9999a33da33a5b8c501 or newer
next_step: flow_generate
coverage: 2/6
missing: [3, 4, 5, 6]
```

If LM Studio cannot call this or returns an older commit, the MCP server is stale.

## Phase 2 - Add explicit MCP health marker to every workflow response

Status: pending

Every stepwise response should include a compact debug footer:

```text
debug:
- mcp_commit: <short sha>
- mcp_pid: <pid>
- api_pid_9001: <pid>
- next_step_before: flow_generate
- next_step_after: flow_wait_sentence
```

This prevents Gemma4 from inventing generic failure messages without exposing the actual tool result.

## Phase 3 - Restart and pin the runtime

Status: pending

The runtime should have one blessed launch path:

```powershell
C:\Users\petbl\newauto\run-newauto-9001.cmd
C:\Users\petbl\newauto\run-newauto-mcp.cmd
```

Rules:

- Only one process may listen on `127.0.0.1:9001`.
- It must be the same Python environment resolved by `run-newauto-9001.cmd`, unless we intentionally choose Python 3.10 and document it.
- LM Studio MCP config must point to:

```text
C:\Users\petbl\newauto\run-newauto-mcp.cmd
```

Restart order:

1. Stop old `9001` uvicorn processes.
2. Start `run-newauto-9001.cmd`.
3. Restart LM Studio MCP server for `mcp/newauto-hpsl-flow`.
4. Call `diagnose_newauto_runtime`.
5. Only then call `continue_stepwise_hpsl_video_workflow`.

## Phase 4 - Replace generic timeout with exact failure types

Status: pending

Introduce typed failure codes in MCP responses:

```text
FLOW_WINDOW_NOT_FOUND
FLOW_GENERATE_CLICK_FAILED
FLOW_DOWNLOAD_NOT_READY
FLOW_DOWNLOAD_STALE_BLOCKED
FLOW_ATTACH_FAILED
MCP_TRANSPORT_TIMEOUT
API_SERVER_MISMATCH
API_SERVER_UNREACHABLE
STATE_MISMATCH
```

`continue_stepwise_hpsl_video_workflow` must never return a vague final timeout message.

Example:

```text
4단계 대기: Flow 다운로드가 아직 감지되지 않았어.
- code: FLOW_DOWNLOAD_NOT_READY
- sentence: 3
- screenshot: storage/flow_desktop_screenshots/...
- next action: Flow 결과가 보이면 "진행"
```

## Phase 5 - Add single-step smoke tools

Status: pending

Add MCP tools for direct controlled testing:

```text
flow_generate_one_sentence(project_id, sentence_number)
flow_download_one_sentence(project_id, sentence_number)
flow_asset_coverage(project_id)
```

These are not for normal user workflow; they are for diagnosis.

Why:

- `continue_stepwise_hpsl_video_workflow` has many branches.
- Single-step tools make it obvious whether Generate, Download, or Attach failed.

## Phase 6 - Repair project text encoding before production rendering

Status: pending

Current project `ad246c22458f` has mojibake in script/source fields.

Before final video rendering:

- Either regenerate project from clean UTF-8 source collection
- Or repair project text fields with a reversible UTF-8/mojibake repair utility
- Recreate HPSL script and Flow prompts

Acceptance:

- `script.txt`, `hpsl_script.json`, `flow_prompts.json` show readable Korean.
- Flow prompts remain English.
- HPSL sections are exactly:
  - hook
  - point
  - story
  - lesson

## Phase 7 - Resume real workflow only after diagnostics pass

Status: pending

Resume criteria:

```text
diagnose_newauto_runtime:
  MCP commit: current
  MCP pid: present
  API 9001 pid: single blessed process
  next_step: flow_generate
  coverage: 2/6
  missing: [3,4,5,6]
```

Then continue:

1. sentence 3 Generate click
2. user waits until Flow result visible
3. sentence 3 Download/attach
4. repeat for 4, 5, 6
5. TTS
6. subtitle/render

## 4. Immediate Next Implementation Order

Review incorporation status: updated from `lmstudio-mcp-flow-runtime-diagnosis-plan-review.md`.

The review confirms the main diagnosis, but tightens the priority order: first prove which MCP code LM Studio is executing, then prove which API process owns `9001`, then resume Flow.

1. Implement `diagnose_newauto_runtime`.
2. Add `_debug_footer()` and append commit/PID/API PID to every `continue_stepwise_hpsl_video_workflow` return path.
3. Add `storage/runtime_diagnostics/latest.json` snapshot writer and expose it through `diagnose_newauto_runtime`.
4. Add process/port single-owner check for `9001`, but do not assume Python 3.10 is wrong until `scripts/resolve_omnivoice_python.ps1` output is captured and compared.
5. Add explicit failure codes around `_run_flow_desktop_control`.
6. Add single-step smoke tools:
   - `flow_generate_one_sentence(project_id, sentence_number)`
   - `flow_download_one_sentence(project_id, sentence_number)`
   - `flow_asset_coverage(project_id)`
7. Restart LM Studio MCP and verify the commit shown inside LM Studio.
8. Only then resume `ad246c22458f`.

## 4.1 Review-Added Implementation Details

### `diagnose_newauto_runtime` minimum payload

The first implementation must return enough information to prove runtime identity inside LM Studio:

```text
=== newauto MCP Runtime Diagnosis ===
mcp_script: C:\Users\petbl\newauto\scripts\newauto_mcp.py
mcp_file_hash: <hash>
git_commit: <short sha>
mcp_pid: <pid>
python_executable: <sys.executable>
cwd: C:\Users\petbl\newauto
BASE_URL: http://127.0.0.1:9001
FLOW_AUTOMATION_BACKEND: <env or default>
FLOW_MODE: <uivision|playwright>
api_server_ok: true|false
api_server_pid_9001: <pid>
resolved_omnivoice_python: <path from scripts/resolve_omnivoice_python.ps1>
stepwise_next_step: flow_generate
asset_coverage: 2/6 missing=[3, 4, 5, 6]
```

If this tool is unavailable in LM Studio, MCP is stale or not loaded.
If this tool returns an old commit, LM Studio is executing stale MCP code.
If this tool returns a different script path, LM Studio is wired to the wrong MCP command.

### Debug footer helper

Add a helper similar to:

```python
def _debug_footer(next_step_before: str = "", next_step_after: str = "") -> str:
    ...
```

The footer should be appended to all `continue_stepwise_hpsl_video_workflow` returns, including success, user-blocked, and failure states:

```text
---
mcp_commit: <short sha>
mcp_pid: <pid>
api_pid_9001: <pid>
step: flow_generate -> flow_wait_sentence
```

This is more important than another Flow click fix because it immediately shows whether LM Studio is running the expected code.

### `9001` runtime pinning nuance

The previous plan described Python 3.10 on `9001` as the "wrong" process. The review correctly narrows this:

- Python 3.10 is wrong only if it differs from the path returned by `scripts/resolve_omnivoice_python.ps1`.
- The code must record both:
  - current listener owner for port `9001`;
  - resolved intended Python from `resolve_omnivoice_python.ps1`.
- `run-newauto-9001.cmd` should fail fast or warn if `9001` is already owned by a different process before starting.

Acceptance:

```text
api_server_pid_9001 is single
api_server_python_path == resolved_omnivoice_python
```

or, if intentionally different:

```text
api_server_python_path is documented as the blessed runtime
```

### Flow coordinate and focus risks

The review adds that `flow_desktop_control.py` still has screen-coordinate fragility:

- `window.height - 90` and `window.height - 66` can drift with DPI/browser chrome height.
- `_ensure_project_prompt_view()` uses `Ctrl+L`, `Ctrl+C`, and `Esc`, which temporarily moves focus to the address bar.
- After `Alt+Left`, `time.sleep(1.8)` may be insufficient if Flow project reload is slow.

Planned mitigation after runtime identity is proven:

- Add a screenshot after `_ensure_project_prompt_view()`.
- Add a small wait loop that checks URL no longer contains `/edit/` or `/scene/`.
- Add a second prompt input focus click before typing.
- Save an explicit failure code if prompt typing happens while the address bar still has focus.

### MCP timeout distinction

The review highlights that subprocess timeout and MCP transport timeout are different.

Current subprocess limits:

```text
click-generate: 35s
download-attach: max(90, download_timeout_seconds + 35)
```

Plan update:

- `click-generate` remains fast and should return under 10 seconds.
- `download-attach` must avoid blocking beyond LM Studio's MCP transport limit.
- If download is not ready, prefer returning `FLOW_DOWNLOAD_NOT_READY` quickly over waiting long enough for MCP transport timeout.
- Add a failure code for cases where the subprocess was still running when LM Studio/tool transport timed out:

```text
MCP_TRANSPORT_TIMEOUT_SUSPECTED
```

## 4.2 No-Code Diagnostic Commands Before Implementation

Use these commands to confirm the review findings before and after restarting LM Studio MCP:

```powershell
# MCP process identity
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'newauto_mcp.py|run-newauto-mcp' } |
  Select-Object ProcessId,Name,CommandLine

# Port 9001 owner
$pid9001 = (Get-NetTCPConnection -LocalPort 9001 -State Listen -ErrorAction SilentlyContinue).OwningProcess
Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -eq $pid9001 } |
  Select-Object ProcessId,ExecutablePath,CommandLine

# Intended Python selected by run-newauto-9001
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\resolve_omnivoice_python.ps1

# Stepwise state
Get-Content .\storage\stepwise_workflows\ad246c22458f.json

# MCP script hash
Get-FileHash .\scripts\newauto_mcp.py -Algorithm MD5
```

## 4.3 Review-Adjusted Resume Gate

Do not resume the Flow workflow from LM Studio until all of these are true:

```text
diagnose_newauto_runtime exists in LM Studio
diagnose_newauto_runtime returns the current git commit
diagnose_newauto_runtime returns a live MCP PID
diagnose_newauto_runtime returns exactly one 9001 listener
stepwise_next_step == flow_generate
asset_coverage == 2/6 missing=[3,4,5,6]
```

If any line fails, the next action is runtime restart/config repair, not another `continue_stepwise_hpsl_video_workflow` call.

## 5. Expected User-Facing Behavior After Fix

When the user says `진행`, LM Studio should answer like this:

```text
4단계 진행: Flow Generate 클릭만 완료했어.

- project_id: ad246c22458f
- target sentence: 3
- coverage before: 2/6
- mcp_commit: <current>
- mcp_pid: <pid>
- api_pid_9001: <pid>

Flow 화면에 결과 이미지가 보이면 `진행`이라고 말해줘.
```

If it fails, it should answer like this:

```text
4단계 중단: Flow 창을 찾지 못했어.
- code: FLOW_WINDOW_NOT_FOUND
- expected: Chrome/Edge title containing Flow
- next action: Flow 로그인 창을 열고 인증 후 `진행`
```

No more generic:

```text
최종 단계에서 시간 초과...
Flow 웹 UI 문제...
권한/인증 필요...
```

That text is not actionable and should be treated as a broken MCP/runtime signal.
