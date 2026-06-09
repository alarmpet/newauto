# LM Studio Direct Operator Plan

## Purpose

This plan defines how to use LM Studio directly, without Cline, so a locally loaded model can handle practical local tasks such as:

- installing normal programs with `winget`
- installing Python packages with `pip`
- setting non-secret user environment variables
- creating or editing project files
- checking local services such as ComfyUI and OmniVoice
- diagnosing and repairing the existing `newauto` workflow

The main target models are:

- `google/gemma-4-e4b`
- `qwen/qwen3.5-9b`

The important design decision is this: do not build a separate duplicate automation product. Use the existing `newauto` services, workers, health checks, and MCP workflow code wherever possible. The direct LM Studio operator is the local execution bridge.

## Desired User Experience

The user should not need to know or type internal runner names such as:

- `run-lmstudio-direct-gemma4.cmd`
- `run-lmstudio-direct-qwen35.cmd`
- `scripts/lmstudio_direct_operator.py`

The intended interaction is natural language:

```text
7zip 설치해
PROJECT_ROOT 환경변수 설정해
ComfyUI 상태 확인하고 꺼져 있으면 켜
필요한 Python 패키지 설치하고 확인해
```

The operator layer should decide:

1. which loaded LM Studio model to use
2. which command runner to call
3. which tool to execute
4. how to verify the result
5. what to report back in Korean

Internal command names may exist, but they are implementation details. The user-facing goal is: "요청하면 알아서 직접 설치하고 설정하고 검증한다."

## Current Direct Operator

Existing entrypoint for Gemma4:

```bat
cd C:\Users\petbl\newauto
run-lmstudio-direct-gemma4.cmd "요청 내용"
```

Current files:

- `run-lmstudio-direct-gemma4.cmd`
- `scripts/lmstudio_direct_operator.py`
- `scripts/lmstudio_openclaw_operator_mcp.py`

The direct operator sends the user request to LM Studio, receives JSON tool-call instructions from the model, then executes local tools:

- `run_powershell`
- `read_text_file`
- `write_text_file`
- `list_directory`
- `open_target`

The direct operator already proved the intended path works:

- `google/gemma-4-e4b` responded through LM Studio.
- `winget search 7zip` worked.
- `7zip.7zip` was installed successfully.
- user environment variable write/read was verified.

## Required Update: Qwen Direct Runner

Gemma4 is not the only intended model. Add a qwen runner with the same direct operator:

```bat
run-lmstudio-direct-qwen35.cmd
```

Expected contents:

```bat
@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
set "SCRIPT_LLM_MODEL=qwen/qwen3.5-9b"
set "NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL=1"
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\lmstudio_direct_operator.py" %*
```

This gives two direct local operators:

```bat
run-lmstudio-direct-gemma4.cmd "winget으로 설치 가능 여부 확인하고 설치 진행해"
run-lmstudio-direct-qwen35.cmd "사용자 환경 변수 PROJECT_ROOT 설정하고 확인해"
```

## Required Update: Natural Language Dispatcher

Add one user-facing dispatcher:

```bat
lmstudio-do.cmd
```

Expected use:

```bat
lmstudio-do.cmd "7zip 설치해"
lmstudio-do.cmd "PROJECT_ROOT 환경변수 설정해"
lmstudio-do.cmd "ComfyUI 상태 확인하고 필요하면 실행해"
```

The dispatcher should:

1. check LM Studio `/v1/models`
2. prefer a loaded model in this order:
   - `qwen/qwen3.5-9b` for precise local setup, command execution, and step-by-step repair
   - `google/gemma-4-e4b` for planning, summarizing, and broader reasoning
3. allow override through `SCRIPT_LLM_MODEL`
4. call `scripts/lmstudio_direct_operator.py`
5. hide all internal runner details from the user

Expected `lmstudio-do.cmd`:

```bat
@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
if not defined SCRIPT_LLM_MODEL set "SCRIPT_LLM_MODEL=auto"
set "NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL=1"
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\lmstudio_direct_operator.py" %*
```

`scripts/lmstudio_direct_operator.py` should support `SCRIPT_LLM_MODEL=auto` by choosing a currently loaded model from LM Studio.

## Core Operating Rule

When the user asks for setup, install, environment variables, diagnostics, or local repair, the model should not answer with "I cannot access your computer."

Instead, through `scripts/lmstudio_direct_operator.py`, it should:

1. inspect the local state with safe commands
2. run the needed install or setup command
3. verify the result
4. report exactly what changed

Example:

```bat
lmstudio-do.cmd "winget으로 7zip 설치 가능한지 확인하고 설치 진행해"
```

Correct behavior:

1. `winget search 7zip`
2. choose `7zip.7zip`
3. `winget install --id 7zip.7zip --exact --accept-package-agreements --accept-source-agreements`
4. verify `C:\Program Files\7-Zip\7z.exe`
5. final Korean summary

## Security Policy

The operator has broad local authority, but not blind authority.

Allowed:

- normal program installs through `winget`
- Python package installs through `pip`
- project file creation/editing under `C:\Users\petbl\newauto`
- non-secret user environment variables using `[Environment]::SetEnvironmentVariable`
- process and service health checks
- starting local project services when a known script exists

Blocked:

- payment, billing, purchase actions
- commands that expose credentials, tokens, cookies, API keys, or passwords
- destructive disk/account operations such as `diskpart`, `format-volume`, `net user`, account password changes

Approval required:

- destructive file operations such as `Remove-Item`, `rmdir`, `git clean`, `git reset`, force push, or moving large paths

Existing enforcement lives in:

```text
scripts/lmstudio_openclaw_operator_mcp.py
```

Important functions:

- `_command_policy()`
- `_redact()`
- `read_text_file(..., redact_secrets=True)`
- `recent_operator_logs()`

The plan must reuse these instead of inventing another security layer.

## Phase 0: Model And Operator Health

Before doing real work, the direct operator must verify:

```powershell
Invoke-RestMethod http://127.0.0.1:1234/v1/models
```

Expected for Gemma4:

```text
google/gemma-4-e4b
```

Expected for Qwen:

```text
qwen/qwen3.5-9b
```

Verify the operator Python environment:

```powershell
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" -c "from scripts import lmstudio_openclaw_operator_mcp; print('operator-import-ok')"
```

Verify direct operator compilation:

```powershell
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" -m py_compile C:\Users\petbl\newauto\scripts\lmstudio_direct_operator.py
```

If these fail, fix the Python path or install missing packages before continuing.

## Phase 1: Environment And Dependency Setup

Check project root:

```powershell
Test-Path C:\Users\petbl\newauto
Test-Path C:\Users\petbl\newauto\requirements.txt
```

Check Python and pip:

```powershell
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" --version
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" -m pip --version
```

Install baseline dependencies:

```powershell
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "C:\Users\petbl\local-rag\.venv\Scripts\pip.exe" install -r C:\Users\petbl\newauto\requirements.txt
```

Install direct-producer helper dependencies only if missing:

```powershell
& "C:\Users\petbl\local-rag\.venv\Scripts\pip.exe" install openai playwright beautifulsoup4 requests python-dotenv
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" -m playwright install chromium
```

## Phase 2: `.env` And User Environment Variables

The operator may create `.env` if it is missing, but it must not invent secrets.

Template:

```env
PROJECT_ROOT=C:\Users\petbl\newauto
LMSTUDIO_BASE_URL=http://127.0.0.1:1234
SCRIPT_LLM_MODEL=google/gemma-4-e4b
COMFYUI_BASE_URL=http://127.0.0.1:8188
OMNIVOICE_BASE_URL=http://127.0.0.1:8000
OPENAI_API_KEY=
PEXELS_API_KEY=
PIXABAY_API_KEY=
```

Set non-secret user variables:

```powershell
[Environment]::SetEnvironmentVariable("PROJECT_ROOT","C:\Users\petbl\newauto","User")
[Environment]::SetEnvironmentVariable("LMSTUDIO_BASE_URL","http://127.0.0.1:1234","User")
[Environment]::SetEnvironmentVariable("SCRIPT_LLM_MODEL","google/gemma-4-e4b","User")
```

Verify with:

```powershell
[Environment]::GetEnvironmentVariable("PROJECT_ROOT","User")
[Environment]::GetEnvironmentVariable("LMSTUDIO_BASE_URL","User")
[Environment]::GetEnvironmentVariable("SCRIPT_LLM_MODEL","User")
```

Do not verify newly persisted variables with `$env:NAME`, because new user environment variables do not automatically appear in the current process.

## Phase 3: Prefer Existing Workflow Over A New Pipeline

The previous plan centered on creating a new `main_auto_producer.py`. The audit correctly points out that this risks duplicating existing `newauto` logic.

Preferred approach:

- keep `main_auto_producer.py` as a thin entrypoint only if the user wants a single file command
- delegate workflow logic to existing modules and scripts
- avoid duplicating article extraction, storyboard, image generation, TTS, and rendering if existing `app/services` or worker code already covers it

Existing code to reuse:

- `scripts/newauto_stepwise_mcp.py`
- `scripts/newauto_mcp.py`
- `app/services/autopilot.py`
- `app/services/operator_summary.py`
- `app/services/preflight.py`
- `app/services/render_plan.py`
- `app/services/scene_plan.py`
- `app/services/source_draft.py`
- `app/services/visual_relevance.py`
- `app/services/image_quality.py`
- `app/services/tts.py`

If `main_auto_producer.py` is created, it should first be a wrapper:

```text
main_auto_producer.py
  --check        run environment/service checks
  --diagnose     run forensic diagnostics
  --workflow     call existing newauto workflow entrypoint
```

It should not initially implement a separate end-to-end video generator.

## Phase 4: Diagnostics First

For broad local diagnosis, use existing diagnostics before writing new checks.

Run:

```powershell
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" C:\Users\petbl\newauto\scripts\forensic_doctor.py
```

Also use:

```powershell
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" C:\Users\petbl\newauto\scripts\check_comfyui_smoke.py
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" C:\Users\petbl\newauto\scripts\check_omnivoice_health.py
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" C:\Users\petbl\newauto\scripts\check_browser_smoke.py
& "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" C:\Users\petbl\newauto\scripts\check_encoding.py
```

If ComfyUI is down and a start script exists:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\petbl\newauto\scripts\run_comfyui_detached.ps1
```

Then re-run the smoke check.

For OmniVoice:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\petbl\newauto\scripts\resolve_omnivoice_python.ps1
```

If no reliable OmniVoice start command exists, report the exact missing startup requirement instead of claiming success.

## Phase 5: Existing State APIs

When the newauto FastAPI server is running, use existing state APIs instead of creating duplicate state logic.

Important APIs:

```text
GET /api/projects/{project_id}/preflight
GET /api/projects/{project_id}/operator-summary
GET /api/system/health
GET /api/system/tools
```

Existing modules:

- `app/services/preflight.py`
- `app/services/operator_summary.py`
- `app/services/system_health.py`

The direct LM Studio operator should use these APIs for status decisions when possible.

## Phase 6: User-Facing Direct Commands

Gemma4:

```bat
cd C:\Users\petbl\newauto
run-lmstudio-direct-gemma4.cmd "winget으로 필요한 프로그램을 확인하고 설치한 뒤 검증해"
```

Qwen:

```bat
cd C:\Users\petbl\newauto
run-lmstudio-direct-qwen35.cmd "PROJECT_ROOT 사용자 환경 변수를 설정하고 검증해"
```

Preferred user-facing command:

```bat
cd C:\Users\petbl\newauto
lmstudio-do.cmd "필요한 프로그램 설치하고 환경변수 설정해"
```

Full setup prompt:

```bat
cd C:\Users\petbl\newauto
lmstudio-do.cmd "docs\lmstudio-gemma4-direct-operator-plan.md 계획에 따라 Phase 0부터 실행해. Cline은 사용하지 않는다. LM Studio에 로드된 google/gemma-4-e4b 또는 qwen/qwen3.5-9b 중 적절한 모델을 자동 선택해서 로컬 도구 실행 루프를 통해 설치, 환경 변수 설정, 파일 생성, 서비스 진단을 직접 처리해. 기존 newauto 서비스와 진단 스크립트를 우선 재사용하고, 비밀키는 만들거나 출력하지 말고 누락 항목으로 보고해."
```

## Success Criteria

The plan is successful when:

- LM Studio model responds through `/v1/chat/completions`.
- The direct operator can run PowerShell and verify results.
- The user can use `lmstudio-do.cmd "자연어 요청"` without knowing model-specific runner names.
- `SCRIPT_LLM_MODEL=auto` chooses a currently loaded LM Studio model.
- Normal install requests can be completed through `winget`.
- Non-secret user environment variables can be set and verified.
- Missing Python packages can be installed.
- Existing `newauto` diagnostics are run before new scaffolds are created.
- `.env` exists with non-secret defaults if needed.
- Secrets are never printed or fabricated.
- If `main_auto_producer.py` is created, it is a thin wrapper over existing workflow code, not a duplicate system.
- The final Korean report lists:
  - installed items
  - changed environment variables
  - created or modified files
  - services confirmed running
  - services still requiring manual action
