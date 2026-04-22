@echo off
setlocal
REM Boot the dev server on http://127.0.0.1:8000
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\resolve_omnivoice_python.ps1"`) do set "OMNIVOICE_PYTHON=%%i"
if not defined OMNIVOICE_PYTHON (
    echo Failed to resolve a usable OmniVoice Python environment.
    exit /b 1
)

start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0scripts\open_browser.ps1"
"%OMNIVOICE_PYTHON%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
