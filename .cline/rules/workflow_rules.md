# Workflow Rules

## Gate
- If there is no explicit workflow/action request, answer directly and do not run workflow tools.
- Simple questions never start or continue a workflow.

## Workflow Intent
- New workflow intent includes explicit requests for HPSL, Flow prompts, shorts/video creation, TTS, render, or full workflow execution.
- URL plus explicit video/workflow intent starts `start_video_workflow` exactly once.
- URL plus summarize/analyze/explain/fact-check intent is article reading, not video workflow.
- `진행`, `ok`, `다음`, or `continue` on an existing workflow runs `continue_video_workflow` exactly once.

## Workflow Documents
- Before explicit HPSL/Flow/video/shorts/TTS/render work, read `issue.md` for active unresolved issues.
- Use `ops_checklist.md` for current quality gates and completion criteria.
- Use `incident_runbook.md` when a known failure symptom appears.
- Use `project_log.md` to check prior project verdicts and record final `PASS / FAIL / PARTIAL`.
- Keep `issue.md` short. Move resolved incidents into `incident_runbook.md` or `project_log.md`.

## Project State
- Do not ask for `project_id` during a new workflow.
- Reuse the project id returned by workflow tools or resolve latest state through diagnostics.
- `project_id` means newauto project id, not Google Flow project id.

## Source And Script
- If `source_draft_state=done` but script/sentences are empty, apply the source draft before image generation.
- Do not generate images when sentence coverage is `0/0` because the script is empty.
- Keep HPSL/shorts default render format as `shorts` unless the user asks otherwise.

## TTS
- `scripts/run_tts_job.py` is project-based, not prompt-to-audio.
- Correct direct invocation:
  `python scripts/run_tts_job.py --project-id <PROJECT_ID>`
- If `--prompt` fails, the caller is wrong; do not patch `run_tts_job.py` just to add `--prompt`.
- Check runtime with `diagnose_runtime` or `forensic_diagnose` before broad guessing.

## Render And Completion
- For render output metadata, use render/report endpoints or filesystem checks.
- Do not parse video file responses as JSON.
- If output route returns 404 after render completion, inspect render report and requested format before retrying.
- A task is complete only when the requested artifact exists and has nonzero size or an API status proves success.

## ComfyUI
- `scripts/run_comfyui_detached.ps1` starts/checks ComfyUI; it is not a prompt-to-image command.
- For direct ComfyUI generation, use `scripts/run_comfyui_image.ps1` with prompt files for complex prompts.
- Verify the absolute output path before reporting success.
