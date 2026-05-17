# LM Studio MCP Flow Runtime Diagnosis Plan — 코드베이스 기반 검증 의견

> 분석 기준일: 2026-05-07  
> 대상 문서: `lmstudio-mcp-flow-runtime-diagnosis-plan.md`  
> 분석 범위: 계획서 + `newauto_mcp.py` (1,672줄), `flow_desktop_control.py` (364줄), `run-newauto-mcp.cmd`, `run-newauto-9001.cmd` 교차 검증

---

## 1. 전체 평가

계획서의 핵심 진단인 **"LM Studio가 최신 MCP 코드를 실행하지 않고 있다"**는 코드를 보면 **이미 상당 부분 해결된 상태**이다. 특히 이전 분석 의견서들에서 "미구현"으로 분류했던 항목들이 대부분 구현되어 있음을 확인했다.

그러나 계획서가 제안한 **Phase 0~7 중 핵심 관찰/진단 인프라(Phase 0, 1, 2)가 아직 코드에 없다**. 이미 기능이 잘 구현된 상태에서, 정작 "지금 어떤 코드가 실행되고 있는가"를 LM Studio 안에서 직접 확인할 수단이 없다는 것이 가장 큰 남은 문제다.

---

## 2. 계획서 각 Finding — 현재 코드 상태 검증

### Finding A: "LM Studio 출력이 최신 MCP 코드와 다르다" → **해결됨**

계획서는 LM Studio가 `flow_generate` 단계에서 옛날 문구("최종 단계에서 시간 초과...")를 반환한다고 했다. 현재 코드에는 `flow_generate`와 `flow_wait_sentence`가 모두 구현되어 있으며 올바른 한국어 응답 문구가 존재한다:

```python
# newauto_mcp.py:919-927 — flow_generate 성공 응답
return (
    "4단계 진행: Flow Generate 클릭만 완료했어.\n\n"
    f"- project_id: {pid}\n"
    f"- target sentence: {sentence_number}\n"
    ...
    "이 호출에서는 다운로드/attach를 기다리지 않았어. "
    "Flow 화면에 결과 이미지가 보이면 `진행`이라고 말해줘."
)
```

**단, 이 코드가 LM Studio에서 실제로 실행되고 있는지 확인할 방법이 여전히 없다.** 계획서의 핵심 우려가 여기에 있다.

---

### Finding B: "newauto_mcp.py 프로세스가 없다" → **구조적 원인 확인**

```cmd
# run-newauto-mcp.cmd
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\newauto_mcp.py"
```

MCP 프로세스는 LM Studio가 tool을 호출할 때마다 짧게 실행되고 종료하는 구조가 아니라, `fastmcp` 서버로 상시 실행되어야 한다. LM Studio가 이 cmd를 실행하면 프로세스가 살아 있어야 하는데, 만약 프로세스가 없다면:

1. LM Studio MCP 설정이 `run-newauto-mcp.cmd`를 가리키지 않는 경우
2. MCP 서버가 시작 직후 오류로 종료된 경우 (import 오류, 포트 충돌 등)
3. LM Studio가 MCP 서버를 재시작하지 않고 캐시된 tool 목록을 사용하는 경우

> [!WARNING]
> `run-newauto-mcp.cmd`는 `cd /d "%~dp0"` 후 바로 `python.exe scripts\newauto_mcp.py`를 실행한다. 만약 `mcp` 패키지가 `C:\Users\petbl\local-rag\.venv`에 설치되어 있지 않거나, `newauto_mcp.py`의 import 중 오류가 나면 **MCP 서버가 즉시 종료**된다. 이때 LM Studio는 오류 없이 stale tool 목록으로 계속 동작할 수 있다.

---

### Finding C: "Port 9001이 잘못된 Python 프로세스를 서비스한다" → **구조적 위험 지속**

```cmd
# run-newauto-9001.cmd
for /f ... %%i in (`powershell ... resolve_omnivoice_python.ps1`) do set "OMNIVOICE_PYTHON=%%i"
"%OMNIVOICE_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 9001
```

`resolve_omnivoice_python.ps1`이 `C:\Users\petbl\AppData\Local\Programs\Python\Python310\python.exe`를 반환하고 있다. 계획서는 이것이 `omnivoice_env`의 Python이 아닌 시스템 Python이라고 진단했다.

현재 코드를 보면 이 문제가 **여전히 잠재적으로 존재**한다:
- `resolve_omnivoice_python.ps1`이 어떤 기준으로 Python을 선택하는지 하드코딩이 없다
- "blessed Python"이 무엇인지 코드 어디에도 명시되지 않아, 환경마다 결과가 다를 수 있다

> [!IMPORTANT]
> MCP(`local-rag\.venv` Python)와 API 서버(`Python310` 또는 `omnivoice_env` Python)가 다른 환경을 쓰면, MCP에서 호출하는 `_json_request()`는 동일 데이터베이스를 바라보지만, API 서버의 `app/` 코드가 다른 버전일 수 있다. 특히 최근 코드 변경이 많았으므로 이 위험은 실질적이다.

---

### Finding D: "Korean mojibake" → **계획서 Phase 6 대응 확인**

계획서 Phase 6은 mojibake 프로젝트 복구를 다루며, 이것이 "runtime stabilization을 블록하지 않지만 production rendering은 블록해야 한다"고 올바르게 판단했다. 현재 코드에 encoding 복구 유틸리티는 없다.

---

### Finding E: "직접 Python 호출은 동작한다" → **핵심 판단 근거**

이것이 계획서에서 가장 중요한 발견이다: 함수 자체는 올바르게 동작한다. 문제는 LM Studio를 통해 MCP로 호출될 때의 **runtime wiring**이다. 이 판단은 코드를 봐도 지지된다.

---

## 3. 계획서 Phase별 구현 상태 검증

### Phase 0 (Runtime Snapshot) — ❌ 미구현

계획서가 요구하는 `storage/runtime_diagnostics/latest.json`이 없다. MCP 프로세스, API 서버 PID, Flow 창, asset coverage를 한 번에 확인할 수 있는 진단 스냅샷이 없다.

### Phase 1 (`diagnose_newauto_runtime` 도구) — ❌ 미구현

가장 중요한 도구인 `diagnose_newauto_runtime`이 `newauto_mcp.py`에 없다. 현재 `get_newauto_status`가 project coverage만 보여주지만, MCP 자체의 버전·환경을 알려주지 않는다.

> [!CAUTION]
> 이것이 없으면 "LM Studio가 어떤 코드를 실행하고 있는가"를 증명할 방법이 없다. 계획서가 "first thing to implement"로 명시한 이유가 정확하다.

**권장 구현 (최소 버전)**:
```python
@mcp.tool()
def diagnose_newauto_runtime(project_id: str = "") -> str:
    """Return MCP runtime identity: version, PID, Python, env vars, API server health, stepwise state, project coverage."""
    import hashlib
    
    mcp_script = Path(__file__)
    mcp_hash = hashlib.md5(mcp_script.read_bytes()).hexdigest()[:8]
    
    # git commit
    try:
        git_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=5
        )
        git_commit = git_result.stdout.strip() or "unknown"
    except Exception:
        git_commit = "git-not-available"
    
    # API server health
    api_ok = _health_ok()
    
    # API server PID on port 9001
    try:
        pid_result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-NetTCPConnection -LocalPort 9001 -State Listen -ErrorAction SilentlyContinue).OwningProcess"],
            capture_output=True, text=True, timeout=5
        )
        api_pid = pid_result.stdout.strip() or "unknown"
    except Exception:
        api_pid = "unknown"
    
    # stepwise state
    stepwise = "none"
    coverage = "unknown"
    try:
        state = _load_stepwise_state(project_id)
        stepwise = str(state.get("next_step") or "?")
        if project_id.strip():
            project = _json_request("GET", f"/api/projects/{project_id.strip()}", timeout=10)
            sc, ac, missing = _project_sentence_asset_status(project)
            coverage = f"{ac}/{sc} missing={missing}"
    except Exception as exc:
        stepwise = f"error: {exc}"
    
    return (
        f"=== newauto MCP Runtime Diagnosis ===\n"
        f"mcp_script: {mcp_script}\n"
        f"mcp_file_hash: {mcp_hash}\n"
        f"git_commit: {git_commit}\n"
        f"mcp_pid: {os.getpid()}\n"
        f"python_executable: {sys.executable}\n"
        f"cwd: {ROOT_DIR}\n"
        f"BASE_URL: {BASE_URL}\n"
        f"FLOW_AUTOMATION_BACKEND: {os.environ.get('FLOW_AUTOMATION_BACKEND', 'uivision (default)')}\n"
        f"FLOW_MODE: {_flow_mode()}\n"
        f"api_server_ok: {api_ok}\n"
        f"api_server_pid_9001: {api_pid}\n"
        f"stepwise_next_step: {stepwise}\n"
        f"asset_coverage: {coverage}\n"
    )
```

### Phase 2 (debug footer) — ❌ 미구현

모든 `continue_stepwise_hpsl_video_workflow` 응답에 `mcp_commit`, `mcp_pid`, `api_pid_9001`을 붙이는 것이 계획서의 요구사항이다. 현재 응답 문자열에 이것이 없다.

**구현 방법**: `_debug_footer()` 헬퍼 함수를 만들어 모든 stepwise 응답 끝에 붙인다:

```python
def _debug_footer(next_step_before: str = "", next_step_after: str = "") -> str:
    try:
        git = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=3)
        commit = git.stdout.strip() or "?"
    except Exception:
        commit = "?"
    try:
        pid_ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-NetTCPConnection -LocalPort 9001 -State Listen).OwningProcess"],
            capture_output=True, text=True, timeout=3)
        api_pid = pid_ps.stdout.strip() or "?"
    except Exception:
        api_pid = "?"
    parts = [
        f"\n---",
        f"mcp_commit: {commit}",
        f"mcp_pid: {os.getpid()}",
        f"api_pid_9001: {api_pid}",
    ]
    if next_step_before:
        parts.append(f"step: {next_step_before} → {next_step_after}")
    return "\n".join(parts)
```

> [!IMPORTANT]
> debug footer에 git commit을 붙이는 것은 "Gemma4가 stale MCP 코드를 실행하고 있다"는 상황을 즉시 드러낸다. commit hash가 예상 값과 다르면 LM Studio MCP를 재시작해야 한다는 명확한 신호가 된다. 이것만 추가해도 계획서 Finding A의 재발을 즉시 탐지할 수 있다.

### Phase 3 (Runtime pin) — ✅ 구조 존재, 절차 미문서화

`run-newauto-9001.cmd`와 `run-newauto-mcp.cmd`가 존재한다. 그러나 "single blessed process" 보장 로직(기존 프로세스 kill, port 점유 확인)이 cmd 파일에 없다. 수동 절차로만 동작한다.

### Phase 4 (Typed failure codes) — ⚠️ 부분 구현

현재 코드에 에러 문구는 있지만 **구조화된 failure code**가 없다. 예를 들어:

```python
# 현재 (newauto_mcp.py:899-906)
return (
    "4단계 중단: Flow Generate 클릭 전에 사용자 확인이 필요해.\n\n"
    f"- reason: {exc}\n\n"
    ...
)
```

계획서가 요구하는 `FLOW_WINDOW_NOT_FOUND`, `FLOW_GENERATE_CLICK_FAILED` 등의 코드가 없다. Gemma4가 응답 파싱 시 "어떤 종류의 실패인가"를 코드로 구분할 수 없다.

### Phase 5 (Single-step smoke tools) — ❌ 미구현

`flow_generate_one_sentence`, `flow_download_one_sentence`, `flow_asset_coverage` MCP 도구가 없다. 현재 `get_newauto_status`가 asset coverage는 알려주지만, 단건 Generate/Download 도구는 없다.

### Phase 6 (Mojibake repair) — ❌ 미구현

encoding 복구 유틸리티 없음.

### Phase 7 (Resume criteria) — 절차적 의존

코드로 강제할 수 없고 사용자 운영 절차다.

---

## 4. 추가 발견된 문제

### 4.1 `_run_flow_desktop_control()` timeout 계산 재확인

```python
# newauto_mcp.py:446
timeout=35 if mode == "click-generate" else max(90, download_timeout_seconds + 35),
```

`click-generate` 모드는 35초 subprocess timeout. `flow_desktop_control.py`의 `click_generate()`는:
- `_activate_flow_window()` → 0.3초
- `_dismiss_browser_overlays()` → 0.6초  
- `_ensure_project_prompt_view()` → URL 복사/붙여넣기 + 최대 1.8초 대기
- 프롬프트 입력 + 클릭 → ~2초
- 스크린샷 2장

총 최대 ~6초. 35초 여유로 보임. **그러나** `_ensure_project_prompt_view()`가 `alt+left`로 브라우저 뒤로가기를 한 뒤 `time.sleep(1.8)`만 기다리는데, 페이지 로딩이 느리면 Flow 입력창이 준비되기 전에 클릭이 실행될 수 있다.

### 4.2 `click_generate()`의 좌표가 비율 기반으로 개선됨 — 단 한계 있음

```python
# flow_desktop_control.py:248-252
pyautogui.click(window.left + int(window.width * 0.44), window.top + window.height - 90)
...
pyautogui.click(window.left + int(window.width * 0.69), window.top + window.height - 66)
```

이전 분석에서 지적한 절대좌표 문제가 비율 기반으로 개선되었다. 단 `window.height - 90`과 `window.height - 66`은 픽셀 절대값이다. Chrome의 toolbar height(약 75px)가 포함된 `window.height`에서 90을 빼면 Flow 입력창의 실제 위치는 DPI scaling에 따라 달라질 수 있다.

> [!TIP]
> `pyautogui.FAILSAFE = True`가 설정되어 있지 않으면 화면 밖으로 마우스가 이동해도 예외가 발생하지 않는다. 비율 기반이더라도 계산 결과가 음수이거나 화면 밖이면 조용히 실패한다.

### 4.3 `_ensure_project_prompt_view()`의 URL 복사 side effect

```python
# flow_desktop_control.py:127-132
def _ensure_project_prompt_view() -> None:
    url = _current_browser_url()  # Ctrl+L, Ctrl+C, Esc
    if "/edit/" in url or "/scene/" in url:
        pyautogui.hotkey("alt", "left")
        time.sleep(1.8)
```

`_current_browser_url()`은 `Ctrl+L` → `Ctrl+C`로 URL을 클립보드에 복사한다. 이후 `_enter_prompt_text()`에서 프롬프트가 ASCII가 아니면 클립보드에 프롬프트를 복사해서 `Ctrl+V`로 붙여넣는다. 그런데 Flow 입력창을 클릭하기 전에 `Ctrl+L`이 실행되면 **포커스가 주소창으로 이동**하므로, 이후 `pyautogui.click(입력창 좌표)`로 다시 입력창을 클릭해야 한다. 순서가 맞는지 확인 필요.

### 4.4 MCP transport timeout vs subprocess timeout — 동시성 문제 잔존

```python
# newauto_mcp.py:446
timeout=35 if mode == "click-generate" else max(90, download_timeout_seconds + 35),
# download_timeout_seconds 기본값 = 45 → subprocess timeout = 80초
```

`download-attach` 모드에서 subprocess timeout이 80초인데, LM Studio의 MCP tool call timeout이 이보다 짧으면 이전 분석에서 지적한 **"MCP가 먼저 포기하고 subprocess는 계속 실행"** 상황이 여전히 가능하다.

**계획서 Phase 4의 `MCP_TRANSPORT_TIMEOUT` 코드가 이 상황을 정확히 식별할 수 있다.** 구현하면 Gemma4가 이 경우를 일반 실패와 구분할 수 있다.

---

## 5. 구현 우선순위 재정렬

계획서의 "Immediate Next Implementation Order"를 코드 현황에 맞게 조정한다:

| 우선순위 | 항목 | 이유 |
|---------|------|------|
| 🔴 1 | `diagnose_newauto_runtime` MCP 도구 구현 | 없으면 어떤 코드가 실행되는지 증명 불가 |
| 🔴 2 | `_debug_footer()` + 모든 stepwise 응답에 commit/pid 추가 | Gemma4 stale code 즉시 탐지 |
| 🟡 3 | `run-newauto-9001.cmd`에 port 점유 확인 + kill 로직 추가 | blessed process 단일화 자동 보장 |
| 🟡 4 | typed failure codes (`FLOW_WINDOW_NOT_FOUND` 등) | Gemma4가 실패 종류를 구분해서 적절한 안내 가능 |
| 🟢 5 | `flow_generate_one_sentence`, `flow_download_one_sentence` smoke tools | 수동 진단용. Phase 1 안정화 후 |
| 🟢 6 | mojibake repair utility | production 전에만 필요 |

---

## 6. 즉시 사용 가능한 진단 절차 (코드 변경 없이)

계획서 구현 전에 현재 코드로 확인할 수 있는 가장 빠른 진단:

```powershell
# 1. MCP 프로세스 확인
Get-Process python | Where-Object { $_.MainWindowTitle -eq "" } |
    Select-Object Id, CPU, StartTime, @{N="Cmd";E={(Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine}}

# 2. Port 9001 소유자 확인
(Get-NetTCPConnection -LocalPort 9001 -State Listen).OwningProcess |
    ForEach-Object { (Get-Process -Id $_).Path }

# 3. Stepwise state 확인
Get-Content "C:\Users\petbl\newauto\storage\stepwise_workflows\latest.json" | ConvertFrom-Json

# 4. MCP 최신 파일 hash 확인
(Get-FileHash "C:\Users\petbl\newauto\scripts\newauto_mcp.py" -Algorithm MD5).Hash
```

LM Studio MCP를 재시작한 후 `diagnose_newauto_runtime`이 구현되기 전까지 이 PowerShell 명령으로 동일한 정보를 수동으로 확인할 수 있다.

---

## 7. 최종 권장 사항

1. **`diagnose_newauto_runtime`을 가장 먼저 구현하라.** 계획서의 판단이 정확하다. 이것 없이는 LM Studio가 최신 코드를 실행하는지 확인할 방법이 없고, 앞으로도 같은 종류의 혼란이 반복된다.

2. **debug footer를 모든 stepwise 응답에 붙여라.** git commit hash 한 줄이 "어떤 MCP 코드가 실행됐는가"를 즉시 증명한다. Gemma4가 generic error를 만들어도 최소한 어떤 코드 버전에서 나온 것인지 알 수 있다.

3. **`run-newauto-9001.cmd`에 port 9001 선점 확인을 추가하라.** 현재는 두 uvicorn 인스턴스가 동시에 뜰 수 있는 구조다. 자동 kill + 재시작 로직 1~2줄이면 Finding C를 구조적으로 차단할 수 있다.

4. **`flow_desktop_control.py`의 `_ensure_project_prompt_view()` Ctrl+L 포커스 이동 부작용을 검증하라.** URL 복사 후 입력창 포커스를 다시 잡는 명시적 클릭이 있는지 코드 흐름 트레이스가 필요하다.

5. **mojibake 프로젝트는 runtime 안정화 후 새 프로젝트로 재시작하는 것이 가장 빠르다.** DB 수준 repair는 부작용 위험이 있다.
