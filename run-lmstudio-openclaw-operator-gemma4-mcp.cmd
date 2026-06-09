@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
set "SCRIPT_LLM_MODEL=google/gemma-4-e4b"
set "NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL=1"
set "LMSTUDIO_OPENCLAW_OPERATOR=1"
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\lmstudio_openclaw_operator_mcp.py"
