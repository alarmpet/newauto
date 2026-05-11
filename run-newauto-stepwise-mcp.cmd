@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
set "SCRIPT_LLM_MODEL=google/gemma-4-e4b"
set "OPENROUTER_MODEL_REVIEWER=qwen/qwen3-32b:free"
set "OPENROUTER_MODEL_PLANNER=qwen/qwen3-32b:free"
set "OPENROUTER_MODEL_DEBUGGER=qwen/qwen3-32b:free"
set "OPENROUTER_MODEL_CODER=qwen/qwen3-32b:free"
set "OPENROUTER_FALLBACK_MODEL=deepseek/deepseek-chat-v3-0324:free"
set "OPENROUTER_LAST_RESORT_MODEL=openai/gpt-oss-20b:free"
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\newauto_stepwise_mcp.py"
