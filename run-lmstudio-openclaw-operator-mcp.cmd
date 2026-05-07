@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LMSTUDIO_OPENCLAW_OPERATOR=1"
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\lmstudio_openclaw_operator_mcp.py"
