# Cline + Qwen3.5 Final Render Recovery Plan - 2026-05-13

## Purpose

Next run must finish the HPSL shorts workflow through actual video rendering, not stop after script, Flow images, and TTS. The previous Cline/Qwen3.5 run produced usable assets for project `bf39e524191b`, but did not queue or execute the final render.

## What Actually Happened

Project:

- ID: `bf39e524191b`
- Topic: Naver News article about AI-powered Googlebook
- Current stepwise state: `next_step = "render"`
- Current DB render state: `idle`
- Current DB render plan: `{}`
- Output video: missing

Generated assets that exist:

- Script: `storage/projects/bf39e524191b/script.txt`
- Compiled script: `storage/projects/bf39e524191b/compiled_script.txt`
- HPSL JSON: `storage/projects/bf39e524191b/hpsl_script.json`
- Flow prompts: `storage/projects/bf39e524191b/flow_prompts.json`
- Flow images:
  - `storage/projects/bf39e524191b/media/flow_sentence_001.jpeg`
  - `storage/projects/bf39e524191b/media/flow_sentence_002.jpeg`
  - `storage/projects/bf39e524191b/media/flow_sentence_003.jpeg`
  - `storage/projects/bf39e524191b/media/flow_sentence_004.jpeg`
  - `storage/projects/bf39e524191b/media/flow_sentence_005.jpeg`
  - `storage/projects/bf39e524191b/media/flow_sentence_006.jpeg`
- TTS:
  - `storage/projects/bf39e524191b/tts/0000.wav`
  - `storage/projects/bf39e524191b/tts/0001.wav`
  - `storage/projects/bf39e524191b/tts/0002.wav`
  - `storage/projects/bf39e524191b/tts/0003.wav`
  - `storage/projects/bf39e524191b/tts/0004.wav`
  - `storage/projects/bf39e524191b/tts/0005.wav`
  - `storage/projects/bf39e524191b/tts/timings.json`
  - `storage/projects/bf39e524191b/tts/timings_words.json`

The API log shows repeated project/status polling, Flow asset attachment, and TTS start, but no clear final render POST for this project after TTS. The stepwise state file stayed at render:

`storage/stepwise_workflows/bf39e524191b.json`

```json
{
  "project_id": "bf39e524191b",
  "next_step": "render"
}
```

## Main Failure Pattern

The agent switched from workflow execution to repository verification:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\petbl\newauto\scripts\final_verification.ps1
```

That script runs broad typechecks. It failed on many pre-existing Python typing issues in unrelated files. These type errors are not proof that rendering cannot run.

Do not use `scripts/final_verification.ps1` as the next action when the workflow is waiting at `next_step = "render"`. It is a repository health gate, not a render command.

Antigravity review confirmed the same root cause: the agent confused broad repository validation with the workflow's current execution state. When the persisted workflow says `next_step = "render"`, the only valid next action is render preflight or rendering, not global typecheck.

## Important Rendering Path Rule

The renderer resolves media paths relative to:

`storage/projects/{pid}/media/`

Expected DB values:

- `media_order`: bare filenames only, e.g. `flow_sentence_001.jpeg`
- `body_image_mappings[].path`: bare filenames only, e.g. `flow_sentence_001.jpeg`
- `scene_plan[].media_path`: bare filenames only, e.g. `flow_sentence_001.jpeg`
- `render_plan[].segments[].media[].path`: bare filenames only, e.g. `flow_sentence_001.jpeg`

Do not put these in DB render/media fields:

- `storage/projects/bf39e524191b/media/flow_sentence_001.jpeg`
- `media/flow_sentence_001.jpeg`
- absolute Windows paths

Reason: `app/services/render.py` uses `media_dir / media["path"]`. A stored path that already includes `storage/projects/.../media/` or `media/` can resolve to a non-existent nested path.

For `bf39e524191b`, the DB currently has the correct bare filenames in `media_order` and `body_image_mappings`.

## Immediate Recovery Procedure For This Project

1. Confirm server is running.

```powershell
Invoke-RestMethod http://127.0.0.1:9002/health
```

2. Confirm project is ready for render.

```powershell
@'
import sqlite3, json, pathlib
pid = "bf39e524191b"
root = pathlib.Path("storage/projects") / pid
conn = sqlite3.connect("storage/app.db")
conn.row_factory = sqlite3.Row
row = conn.execute("select media_order, body_image_mappings, render_state, render_plan from projects where id=?", (pid,)).fetchone()
print("render_state:", row["render_state"])
print("render_plan:", row["render_plan"])
print("media_order:", row["media_order"])
for name in json.loads(row["media_order"]):
    print(name, (root / "media" / name).exists())
print("timings:", (root / "tts" / "timings.json").exists())
'@ | python -
```

Expected:

- `render_state: idle` or `error`, not `running`
- six media filenames
- each media file exists
- `timings.json` exists

3. Run render preflight.

```powershell
Invoke-RestMethod http://127.0.0.1:9002/api/projects/bf39e524191b/preflight | ConvertTo-Json -Depth 8
```

Continue only if the report does not show blocking TTS/media/render readiness issues. Preflight is allowed here because it checks render prerequisites; `final_verification.ps1` is not allowed here because it checks unrelated repository health.

4. Queue render through the app API.

The actual endpoint is defined in `app/routers/render.py`:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:9002/api/projects/bf39e524191b/render
```

This endpoint requires:

- `tts_state == "done"`
- non-empty `media_order`
- `media_upload_state != "running"`
- `render_state` not already `queued` or `running`

It sets `render_state = "queued"`. The background `render_worker` must then claim and execute the job.

5. Poll status until render finishes.

```powershell
while ($true) {
  $s = Invoke-RestMethod http://127.0.0.1:9002/api/projects/bf39e524191b/status
  $s | ConvertTo-Json -Depth 6
  if ($s.render_state -in @("done", "error")) { break }
  Start-Sleep -Seconds 5
}
```

If status remains `queued` for more than 30 seconds, check whether the API process spawned `app.workers.render_worker` or whether a stale `storage/render_worker.lock` is blocking worker startup.

6. Verify output files.

For default landscape render:

```powershell
Test-Path storage/projects/bf39e524191b/output.mp4
Test-Path storage/projects/bf39e524191b/render_report.json
```

If shorts format is desired, first set or confirm `render_formats` includes `shorts`, then expect:

```powershell
storage/projects/bf39e524191b/output_shorts.mp4
```

7. Inspect final report.

```powershell
Get-Content -Raw storage/projects/bf39e524191b/render_report.json
```

Report only after the output mp4 and render report exist.

## If Render Fails With Missing Media

1. Check DB path fields.

```powershell
@'
import sqlite3, json
pid = "bf39e524191b"
conn = sqlite3.connect("storage/app.db")
conn.row_factory = sqlite3.Row
row = conn.execute("select media_order, body_image_mappings, scene_plan, render_plan from projects where id=?", (pid,)).fetchone()
for key in ("media_order", "body_image_mappings", "scene_plan", "render_plan"):
    print("==", key, "==")
    print(row[key])
'@ | python -
```

2. Normalize paths to bare filenames only.

Valid:

```json
["flow_sentence_001.jpeg", "flow_sentence_002.jpeg"]
```

Invalid:

```json
["media/flow_sentence_001.jpeg"]
```

Invalid:

```json
["storage/projects/bf39e524191b/media/flow_sentence_001.jpeg"]
```

3. Rebuild or clear `render_plan`.

If `render_plan` contains bad media paths, clear it to `{}` or rebuild it from correct `media_order`. With no scene plan, renderer can fall back to `media_order`.

If `scene_plan` contains bad `media_path` values, normalize them too or clear `scene_plan` before rebuilding `render_plan`. `run_render_job()` rebuilds a render plan when `project["scene_plan"]` exists, so a bad scene plan can reintroduce bad render plan paths.

4. Requeue render.

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:9002/api/projects/bf39e524191b/render
```

## What The Next Agent Should Not Do

- Do not run `scripts/final_verification.ps1` before rendering.
- Do not treat mypy/typecheck failures as render failures.
- Do not regenerate Flow images if all six `media/flow_sentence_###.jpeg` files exist.
- Do not regenerate TTS if `tts/0000.wav` through `0005.wav` and `tts/timings.json` exist.
- Do not report “Task Completed” until an output mp4 exists.
- Do not store full or `media/`-prefixed paths in `media_order`, `body_image_mappings`, or render plan media entries.

Recommended `.clinerules` guardrail:

```text
When a newauto stepwise workflow state has next_step="render", do not run scripts/final_verification.ps1, mypy, pytest, or broad repository verification as the next action. First run render preflight if needed, then call POST /api/projects/{pid}/render or the equivalent MCP render step. Continue polling until render_state is done or error. Completion may only be reported after output.mp4/output_shorts.mp4 and render_report.json exist.
```

## Future Workflow Checklist

Use this checklist for every Cline/Qwen HPSL Flow run:

1. Source collection complete.
2. HPSL script saved.
3. Flow prompts saved.
4. Flow images attached to both `media/` and `flow_assets/`.
5. DB `media_order` contains bare filenames.
6. DB `body_image_mappings[].path` contains bare filenames.
7. TTS WAV files exist.
8. `tts/timings.json` exists.
9. Queue render through API or stepwise MCP render step.
10. Poll `render_state`.
11. Verify `output.mp4` or `output_shorts.mp4`.
12. Verify `render_report.json`.
13. Only then report completion.

## Recommended Code Hardening

Add a small path normalizer to render/media plan handling so future bad stored paths do not break rendering:

- Input examples:
  - `flow_sentence_001.jpeg`
  - `media/flow_sentence_001.jpeg`
  - `storage/projects/{pid}/media/flow_sentence_001.jpeg`
  - absolute path ending in `media/flow_sentence_001.jpeg`
- Output:
  - `flow_sentence_001.jpeg`

Suggested helper behavior:

```python
def normalize_media_filename(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    return text.rsplit("/", 1)[-1]
```

This is intentionally stricter than general path handling. Renderer-owned media references should be filenames inside `storage/projects/{pid}/media`, not arbitrary paths.

Apply this normalizer before writing:

- Flow local attach result
- `media_order`
- `body_image_mappings`
- `scene_plan[].media_path`
- `render_plan[].segments[].media[].path`

Also apply it defensively while reading in:

- `app/services/render.py::_media_files_from_render_plan`
- `app/services/render.py::_resolve_visual_segments`
- `app/services/render.py::_visual_plan_report`
- `app/services/render_plan.py::build_render_plan`

This makes existing bad rows recoverable while the write paths are being fixed.

Also add a render preflight that fails early with a clear message:

```text
Missing media for render: flow_sentence_001.jpeg
Checked directory: storage/projects/{pid}/media
Stored path must be a bare filename, not a full path.
```

Preflight should reject media references that contain `/` or `\` after normalization is considered, and it should list both the stored value and the file it attempted to check. That makes the next failure self-explanatory instead of turning into a late FFmpeg or "no valid media files" error.

## Minimal Acceptance Criteria

The next successful run is complete only when all are true:

- `storage/projects/{pid}/output.mp4` or `output_shorts.mp4` exists.
- `storage/projects/{pid}/render_report.json` exists.
- DB `render_state` is `done`.
- `render_last_log` is empty or non-fatal.
- The agent reports the actual output path and does not merely list intermediate assets.
