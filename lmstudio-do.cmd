@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
if not defined SCRIPT_LLM_MODEL set "SCRIPT_LLM_MODEL=auto"
set "NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL=1"
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\lmstudio_direct_operator.py" %*
