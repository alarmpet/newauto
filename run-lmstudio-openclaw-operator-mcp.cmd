@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
if not defined SCRIPT_LLM_MODEL set "SCRIPT_LLM_MODEL=qwen/qwen3.5-9b"
set "NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL=1"
set "LMSTUDIO_OPENCLAW_OPERATOR=1"
if /i not "%NEWAUTO_ALLOW_DUPLICATE_MCP%"=="1" (
  for /f "usebackq delims=" %%p in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\find_mcp_process.ps1" -ScriptName "lmstudio_openclaw_operator_mcp.py"`) do set "EXISTING_MCP_PID=%%p"
  if defined EXISTING_MCP_PID (
    echo openclaw operator MCP already appears to be running as PID !EXISTING_MCP_PID!.
    echo Stop the stale process first, or set NEWAUTO_ALLOW_DUPLICATE_MCP=1 if this duplicate is intentional.
    exit /b 1
  )
)
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\lmstudio_openclaw_operator_mcp.py"
