@echo off
setlocal
cd /d "%~dp0"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
set "SCRIPT_LLM_MODEL=google/gemma-4-e4b"
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\resolve_omnivoice_python.ps1"`) do set "OMNIVOICE_PYTHON=%%i"
if not defined OMNIVOICE_PYTHON (
    echo Failed to resolve a usable OmniVoice Python environment.
    exit /b 1
)
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort 9001 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)"`) do set "PORT_9001_PID=%%p"
if defined PORT_9001_PID (
    echo Port 9001 is already in use by PID %PORT_9001_PID%.
    powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter 'ProcessId=%PORT_9001_PID%' | Select-Object ProcessId,ExecutablePath,CommandLine | Format-List"
    echo Stop that process first, or keep using the already-running server intentionally.
    exit /b 1
)
"%OMNIVOICE_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 9001
