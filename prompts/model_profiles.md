# Model Profiles

This file defines model roles for the `newauto` agentic stack. A model can be added to real operation only after it passes the same smoke/eval path used by `scripts/agent_eval_smoke.py`.

## operator-fast

- Model: `google/gemma-4-e4b`
- Current runtime: LM Studio local
- Current context target: `72000`
- Quantization observed: `Q4_K_M`
- Hardware fit: good for RTX 4060 Laptop 8GB at the current operating profile
- Purpose:
  - Stepwise video workflow
  - Short diagnostics
  - Flow GUI orchestration
  - Web-search triage
- Required smoke:
  - `python scripts\agent_eval_smoke.py`

## planner-reviewer

- Candidate models:
  - Gemma4 26B `Q4_K_S`
  - Gemma4 26B `IQ4_XS`
- Hardware fit:
  - RTX 4060 Laptop 8GB cannot reliably full-offload 26B at long context.
  - Use shorter context and partial offload, or run remotely.
- Purpose:
  - Plan review
  - Architecture critique
  - Complex failure analysis
  - Large document synthesis
- Required evidence:
  - Same prompt set as `operator-fast`
  - Latency and memory observation
  - Tool-call correctness compared to E4B

## coding-worker

- Candidate model family:
  - Qwen/DeepSeek-Coder/Codestral-style coding models
- Hardware fit:
  - Prefer smaller quantized local models or remote runtime.
- Purpose:
  - Larger code edits
  - Refactors
  - Test repair
- Required evidence:
  - Focused code-edit task
  - `py_compile`, `mypy`, and relevant pytest pass

## fallback-cloud

- Candidate:
  - API/OpenRouter/remote LM Studio model selected per task
- Purpose:
  - Cases where local Gemma4 cannot reliably reason or code
- Constraints:
  - Requires explicit API/provider setup
  - Do not send secrets, local credentials, or private tokens
  - Summarize local context instead of uploading raw large logs

## openrouter-reviewer

- Runtime: OpenRouter
- Role: fallback-cloud reviewer/planner/coder for cases where local Gemma4 and Cline repeat failures or need external review.
- Key source:
  - Preferred: `OPENROUTER_API_KEY`
  - Fallback: first non-comment line of `C:\Users\petbl\newauto\openrouter.txt`
- Model policy:
  - Use `:free` models only.
  - Primary reviewer/debug/planner/code_patch model: `google/gemma-4-31b-it:free`.
  - Preferred fallback model: `google/gemma-4-26b-a4b-it:free`.
  - Last-resort fallback model: `openai/gpt-oss-20b:free`, kept as a safety net when the preferred Google Gemma free endpoints are rate-limited.
  - Configure mode-specific models with `OPENROUTER_MODEL_REVIEWER`, `OPENROUTER_MODEL_PLANNER`, `OPENROUTER_MODEL_DEBUGGER`, and `OPENROUTER_MODEL_CODER`.
  - Configure fallback with `OPENROUTER_FALLBACK_MODEL` only if the default DeepSeek fallback should change.
  - Configure last-resort fallback with `OPENROUTER_LAST_RESORT_MODEL` only if the verified available free endpoint changes.
  - Do not import or share `music-auto` OpenRouter runtime state. Keep budget/config/cache local to `newauto`.
- Free-model quota:
  - `$10+ credits` account: 1000 requests/day.
  - Rate guard: 20 requests/minute.
  - Soft limit: 800/day for non-essential calls.
  - Hard guard: 950/day for non-essential calls.
- Required validation:
  - `python scripts\openrouter_subagent_harness.py --dry-run --mode review --task "smoke" --json-output`
  - `python scripts\agent_eval_smoke.py --skip-openrouter` for local smoke without spending quota.
- Constraints:
  - No raw secrets.
  - No full repo or full log upload.
  - Results are advisory and must be verified locally before applying.
