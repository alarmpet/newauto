@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
set "SCRIPT_LLM_MODEL=qwen/qwen3.5-9b"
set "LMSTUDIO_CONTEXT_TARGET=131072"
set "OPENROUTER_MODEL_REVIEWER=google/gemma-4-31b-it:free"
set "OPENROUTER_MODEL_PLANNER=google/gemma-4-31b-it:free"
set "OPENROUTER_MODEL_DEBUGGER=google/gemma-4-31b-it:free"
set "OPENROUTER_MODEL_CODER=google/gemma-4-31b-it:free"
set "OPENROUTER_FALLBACK_MODEL=google/gemma-4-26b-a4b-it:free"
set "OPENROUTER_LAST_RESORT_MODEL=openai/gpt-oss-20b:free"
if not defined OPENROUTER_API_KEY if exist "%~dp0openrouter.txt" for /f "usebackq tokens=* delims=" %%K in ("%~dp0openrouter.txt") do if not defined OPENROUTER_API_KEY if not "%%K"=="" set "OPENROUTER_API_KEY=%%K"
set "NEWAUTO_API_PORT=9002"
set "NEWAUTO_BASE_URL=http://127.0.0.1:%NEWAUTO_API_PORT%"
set "FLOW_AUTOMATION_BACKEND=playwright"
set "FLOW_MODE=playwright"
set "FLOW_BROWSER=edge"
set "FLOW_PROMPT_SUBMIT_DELAY_SECONDS=15"
set "FLOW_GENERATE_COOLDOWN_SECONDS=90"
if /i not "%NEWAUTO_ALLOW_DUPLICATE_MCP%"=="1" (
  for /f "usebackq delims=" %%p in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\find_mcp_process.ps1" -ScriptName "newauto_stepwise_mcp.py"`) do set "EXISTING_MCP_PID=%%p"
  if defined EXISTING_MCP_PID (
    echo newauto-stepwise MCP already appears to be running as PID !EXISTING_MCP_PID!.
    echo Stop the stale process first, or set NEWAUTO_ALLOW_DUPLICATE_MCP=1 if this duplicate is intentional.
    exit /b 1
  )
)
if /i not "%NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL%"=="1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\ensure_lmstudio_context.ps1" -Model "%SCRIPT_LLM_MODEL%" -ContextLength %LMSTUDIO_CONTEXT_TARGET%
  if errorlevel 1 exit /b 1
)
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\newauto_stepwise_mcp.py" %*
