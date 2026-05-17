@echo off
setlocal
cd /d "%~dp0"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
set "SCRIPT_LLM_MODEL=google/gemma-4-e4b"
if not defined NEWAUTO_API_PORT set "NEWAUTO_API_PORT=9002"
set "NEWAUTO_BASE_URL=http://127.0.0.1:%NEWAUTO_API_PORT%"
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\resolve_omnivoice_python.ps1"`) do set "OMNIVOICE_PYTHON=%%i"
if not defined OMNIVOICE_PYTHON (
    echo Failed to resolve a usable OmniVoice Python environment.
    exit /b 1
)
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort %NEWAUTO_API_PORT% -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)"`) do set "NEWAUTO_API_PORT_PID=%%p"
if defined NEWAUTO_API_PORT_PID (
    echo Port %NEWAUTO_API_PORT% is already in use by PID %NEWAUTO_API_PORT_PID%.
    powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter 'ProcessId=%NEWAUTO_API_PORT_PID%' | Select-Object ProcessId,ExecutablePath,CommandLine | Format-List"
    echo Stop that process first, or keep using the already-running server intentionally.
    exit /b 1
)
echo Starting newauto API on %NEWAUTO_BASE_URL%
"%OMNIVOICE_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %NEWAUTO_API_PORT%
