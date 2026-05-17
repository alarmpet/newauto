@echo off
setlocal
cd /d "%~dp0"
set "NEWAUTO_API_PORT=9002"
set "NEWAUTO_BASE_URL=http://127.0.0.1:%NEWAUTO_API_PORT%"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
set "SCRIPT_LLM_MODEL=qwen/qwen3.5-9b"
set "LMSTUDIO_CONTEXT_TARGET=131072"
set "FLOW_AUTOMATION_BACKEND=playwright"
set "FLOW_MODE=playwright"
set "FLOW_BROWSER=edge"
set "FLOW_PROMPT_SUBMIT_DELAY_SECONDS=15"
set "FLOW_GENERATE_COOLDOWN_SECONDS=90"
if not defined OPENROUTER_API_KEY if exist "%~dp0openrouter.txt" for /f "usebackq tokens=* delims=" %%K in ("%~dp0openrouter.txt") do if not defined OPENROUTER_API_KEY if not "%%K"=="" set "OPENROUTER_API_KEY=%%K"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ensure_lmstudio_context.ps1" -Model "%SCRIPT_LLM_MODEL%" -ContextLength %LMSTUDIO_CONTEXT_TARGET%
if errorlevel 1 exit /b 1
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\newauto_mcp.py"
