# Model Profiles

This file defines model roles for the `newauto` agentic stack. A model can be added to real operation only after it passes the same smoke/eval path used by `scripts/agent_eval_smoke.py`.

## operator-fast

- Model: `qwen/qwen3.5-9b`
- Current runtime: LM Studio local
- Current context target: `131072`
- Quantization observed: `Q4_K_M`
- Hardware fit: usable on RTX 4060 Laptop 8GB only when Cline tasks stay compact
- Purpose:
  - Stepwise video workflow
  - Short diagnostics
  - Flow GUI orchestration
  - Web-search triage
- Simple Q&A policy:
  - Answer directly without tools.
  - Do not inspect files, create todos, or run MCP for identity/config/explanation questions.
- Required smoke:
  - `python scripts\agent_eval_smoke.py`

## planner-reviewer

- Candidate models:
  - Qwen3.5 9B `Q4_K_M`
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
  - Cases where the local LM Studio model cannot reliably reason or code
- Constraints:
  - Requires explicit API/provider setup
  - Do not send secrets, local credentials, or private tokens
  - Summarize local context instead of uploading raw large logs

## openrouter-reviewer

- Runtime: OpenRouter
- Role: fallback-cloud reviewer/planner/coder for cases where local LM Studio and Cline repeat failures or need external review.
- Key source:
  - Preferred: `OPENROUTER_API_KEY`
  - Fallback: first non-comment line of `C:\Users\petbl\newauto\openrouter.txt`
- Model policy:
  - Use `:free` models only.
  - Primary reviewer/debug/planner/code_patch model: `google/gemma-4-31b-it:free`.
  - Preferred fallback model: `google/gemma-4-26b-a4b-it:free`.
  - Last-resort fallback model: `openai/gpt-oss-20b:free`, kept as a safety net when the preferred Gemma free endpoints are rate-limited.
  - Vision fallback chain: `google/gemma-4-31b-it:free` -> `google/gemma-4-26b-a4b-it:free` -> `nvidia/nemotron-nano-12b-v2-vl:free` -> `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` -> `baidu/qianfan-ocr-fast:free` -> `openrouter/free`.
  - Configure mode-specific models with `OPENROUTER_MODEL_REVIEWER`, `OPENROUTER_MODEL_PLANNER`, `OPENROUTER_MODEL_DEBUGGER`, and `OPENROUTER_MODEL_CODER`.
  - Configure vision-specific models with `OPENROUTER_VISION_MODEL`, `OPENROUTER_VISION_FALLBACK_MODEL`, and `OPENROUTER_VISION_LAST_RESORT_MODEL` only if the verified free image-capable endpoints change.
  - Configure fallback with `OPENROUTER_FALLBACK_MODEL` only if the default Gemma 26B fallback should change.
  - Configure last-resort fallback with `OPENROUTER_LAST_RESORT_MODEL` only if the verified available free endpoint changes.
  - Do not import or share `music-auto` OpenRouter runtime state. Keep budget/config/cache local to `newauto`.
- Free-model quota:
  - `$10+ credits` account: 1000 requests/day.
  - Rate guard: 20 requests/minute.
  - Soft limit: 800/day for non-essential calls.
  - Hard guard: 950/day for non-essential calls.
- Required validation:
  - `python scripts\openrouter_subagent_harness.py --dry-run --mode review --task "smoke" --json-output`
  - For real Cline calls with Korean/multiline prompts, use `--task-stdin` or `--task-file`; reserve direct `--task "..."` for short smoke text only.
  - `python scripts\agent_eval_smoke.py --skip-openrouter` for local smoke without spending quota.
- Constraints:
  - No raw secrets.
  - No full repo or full log upload.
  - Results are advisory and must be verified locally before applying.
