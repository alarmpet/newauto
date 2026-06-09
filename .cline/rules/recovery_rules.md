# Recovery Rules

## Gate
- If there is no explicit action request, answer directly and do not run recovery tools.
- Simple questions never trigger diagnostics, memory, OpenRouter, or repair.

## LM Studio
- On `Please check the LM Studio developer logs`, `load the model with a larger context length`, `Auto-Retry Failed`, invalid/empty assistant message, or repeated timeout, stop retrying the same Cline task.
- First check:
  `C:\Users\petbl\local-rag\.venv\Scripts\python.exe C:\Users\petbl\newauto\scripts\check_cline_lmstudio_health.py --json-output`
- Expected model: `qwen/qwen3.5-9b`.
- Expected context: `131072`.
- If context is low or runtime is stuck, reload through LM Studio CLI or `scripts/ensure_lmstudio_context.ps1`.

## Compact Recovery
- Use a fresh compact task after bloated context, screenshots, full repo lists, or multi-MB history.
- Include only: project id, current step, concise latest error, and requested next action.
- Do not paste browser screenshots, full diagnostics JSON, full logs, or `issue.md`.

## Local Recovery Loop
- On workflow/server/state failure, call `diagnose_runtime` first.
- If unclear, call `forensic_diagnose`.
- If diagnostics report stale worker, expired heartbeat, missing subprocess, or missing artifact, run the specific repair once.
- If repair succeeds, call `continue_video_workflow` exactly once.
- If the same blocker remains after 3 local attempts, ask OpenRouter once with a concise redacted facts packet.

## Reporting
- Report the confirmed cause and next concrete command/action briefly.
- Do not ask broad option questions when local diagnosis already identifies the blocker.
- Treat encoding-damaged notes as unreliable; verify from live code, logs, API, tests, or git before acting.
