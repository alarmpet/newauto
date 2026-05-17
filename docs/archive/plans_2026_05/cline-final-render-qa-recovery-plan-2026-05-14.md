# Cline Final Render QA Recovery Plan - 2026-05-14

## Scope

Project checked: `46aece6b3c2f`

Final artifact checked:

- `storage/projects/46aece6b3c2f/output.mp4`
- `storage/projects/46aece6b3c2f/render_report.json`
- `storage/projects/46aece6b3c2f/subtitles.ass`
- `storage/projects/46aece6b3c2f/tts/tts_run_manifest.json`
- `storage/projects/46aece6b3c2f/tts/tts_consistency_report.json`

This render must not be treated as a successful deliverable. It only proves FFmpeg can mux the available assets.

## Verified Problems

### 1. Wrong Final Aspect Ratio

Evidence:

- `ffprobe output.mp4`: `width=1920`, `height=1080`, DAR `16:9`
- All Flow images in `media/`: `768x1376`, ratio `0.558`, intended vertical `9:16`
- Project DB: `render_formats=["landscape"]`
- No `output_shorts.mp4` was produced.
- Extracted QA frames show heavy black side bars:
  - frame 1 non-black bbox starts near `x=324`
  - left/right black ratio around `0.97`

Root cause:

- Stepwise HPSL shorts workflow creates a project with DB default `render_formats=["landscape"]`.
- The workflow never forces `render_formats=["shorts"]`.
- Render then pads vertical Flow images inside a landscape canvas.

Required fix:

- For HPSL shorts / Flow vertical workflows, set `render_formats=["shorts"]` at project creation or immediately after source collection starts.
- Scene plan and render plan must be built for `render_format="shorts"`.
- Final expected artifact must be `output_shorts.mp4`, not `output.mp4`.
- Preflight must hard-fail if all attached Flow assets are vertical but render format is only landscape.

Acceptance:

- `ffprobe output_shorts.mp4` reports `1080x1920`.
- `render_report.json.outputs[0].format == "shorts"`.
- No landscape-only output is accepted for a shorts workflow.

### 2. Subtitle Layout Is Still Bad

Evidence:

- `subtitles.ass` uses `PlayResX=1920`, `PlayResY=1080`, matching the wrong landscape render.
- Project DB: `subtitle_style={}` so defaults are used.
- Default subtitle style has `cue_split_mode="sentence"` and `max_line_chars=26`.
- Actual ASS cue lengths:
  - cue 1: 120 chars, displayed for 13.92s, split as `[25, 94]`
  - cue 2: 114 chars, displayed for 14.42s, split as `[23, 90]`
  - cue 3: 83 chars, displayed for 10.33s, split as `[22, 60]`
- UTF-8 source text itself is valid. The visible problem is not primarily encoding; it is cue segmentation and layout.

Root cause:

- Source script is long-form article narration, not HPSL shorts narration.
- Subtitle default stays in sentence-level cue mode.
- `_smart_wrap()` forces long text into two lines instead of splitting long narration into multiple shorter cues.
- Shorts-specific subtitle defaults are not applied in `apply_source_script`.

Required fix:

- For shorts workflows, force subtitle style:
  - `cue_split_mode="readable"`
  - `max_cue_sec=2.2` to `2.8`
  - `max_line_chars=14` to `18`
  - `max_lines=2`
  - font/margin tuned for `1080x1920`
- Add a subtitle QA check before render:
  - fail if any final cue has more than 2 lines
  - fail if any line exceeds the shorts max char budget
  - fail if any cue duration exceeds `max_cue_sec + tolerance`
- Render report must include subtitle QA fields, not just `subtitle_cue_count`.

Acceptance:

- `subtitles.ass` for shorts uses 1080x1920 coordinate basis or render-format-aware margins.
- No cue contains a 60+ or 90+ char second line.
- Long narration is split into multiple readable cues.

### 3. TTS Voice Changes Between Sentences

Evidence:

- `tts_run_manifest.json`:
  - `synthesis_mode="sentence"`
  - `seed_mode="per_sentence"`
  - sentence seeds differ: `1757417077` through `1757417082`
- `tts_consistency_report.json`:
  - `metadata_consistent=false`
  - `recommended_tts_mode="full_passage_or_reference_voice"`
  - RMS drift up to `0.5452`
  - spectral centroid drift up to `0.2102`
  - pitch drift up to `0.1192`
- Previous log: `Retrying TTS with sentence synthesis after full_passage subprocess abort.`

Root cause:

- Stepwise workflow asks for `synthesis_mode="full_passage"` but does not force `seed_mode="fixed"`.
- If full-passage TTS aborts, `tts_worker._retry_with_sentence_mode()` changes only `synthesis_mode` to `sentence`.
- The fallback keeps per-sentence generation behavior, so each sentence uses a different seed and can sound like a different voice.

Required fix:

- `_enqueue_tts()` must request:
  - `synthesis_mode="full_passage"`
  - `seed_mode="fixed"`
  - one fixed seed for the whole project
- If full-passage aborts, fallback must be:
  - `synthesis_mode="sentence"`
  - `seed_mode="fixed"`
  - same seed for all sentence chunks
- TTS consistency report must become a gate:
  - fail pre-render if `metadata_consistent=false`
  - fail if RMS/spectral/pitch drift exceeds thresholds
  - require regeneration before render

Acceptance:

- `tts_run_manifest.json` shows same seed for every sentence when sentence fallback is used.
- `tts_consistency_report.json.metadata_consistent == true`
- `recommended_tts_mode` is not `full_passage_or_reference_voice` after final TTS.

### 4. Render Was Started Outside The Correct Owner Workflow

What happened:

- The project was in `render_state=idle`.
- TTS and assets existed, so Codex manually queued render.
- FFmpeg completed successfully.

Why this is wrong:

- It bypassed Cline/newauto workflow responsibility.
- It allowed a technically complete but QA-failing render to be produced.
- The workflow should have detected:
  - landscape output for vertical assets
  - missing shorts output
  - bad subtitle cue lengths
  - TTS inconsistency
  - empty render/scene plan

Required fix:

- Codex/manual debugging may diagnose and propose patches, but final render must be triggered by Cline workflow tools after all preflight QA gates pass.
- `continue_video_workflow` / `_enqueue_render()` must own final render.
- Render endpoint should reject render if `final_output_qa.ok != true`.

Acceptance:

- Cline can call `continue_video_workflow` and reach render without manual DB mutation.
- If QA fails, Cline receives actionable failure details instead of rendering anyway.
- If QA passes, Cline produces `output_shorts.mp4` directly.

## Implementation Plan

## 2026-05-14 Implementation Status

Applied changes:

- Stepwise HPSL Flow projects now force `render_formats=["shorts"]` and a shorts-readable subtitle style when the project is created and again after source script apply.
- The subtitle style API now accepts `cue_split_mode`, `max_cue_sec`, and `max_lines`, so Cline can set the actual readable cue policy instead of only font/margin fields.
- TTS enqueue now requests `synthesis_mode="full_passage"`, `seed_mode="fixed"`, and one stable project seed.
- TTS worker fallback from full-passage to sentence mode now preserves fixed-seed behavior instead of drifting into per-sentence voices.
- Preflight now blocks:
  - vertical media with landscape-only render formats
  - unreadable subtitle cue layout
  - existing TTS consistency failures

Current project `46aece6b3c2f` still correctly fails preflight:

- `subtitle_layout`: long sentence-mode cues, including a 94-character line.
- `tts_consistency`: voice consistency failed; report recommends full passage or reference voice.
- `media_aspect`: all media are `768x1376` vertical but project render format is `["landscape"]`.
- `plan_sync`: scene/render plans are stale.

Verification:

- `python -m py_compile app\services\subtitle.py app\services\preflight.py app\routers\projects.py app\workers\tts_worker.py scripts\newauto_mcp.py tests\test_feature_workflow.py tests\test_subtitle_rendering.py tests\test_tts_worker.py`
- `python -m pytest tests/test_feature_workflow.py::FeatureWorkflowTests::test_preflight_rejects_vertical_media_with_landscape_only_output tests/test_feature_workflow.py::FeatureWorkflowTests::test_preflight_rejects_sentence_mode_subtitles_for_shorts tests/test_feature_workflow.py::FeatureWorkflowTests::test_preflight_service_passes_ready_project tests/test_subtitle_rendering.py tests/test_tts_worker.py -q`
- Result: `27 passed`.

### Phase 1 - Lock Shorts Workflow Defaults

Files:

- `scripts/newauto_mcp.py`
- `app/routers/projects.py`
- `app/services/preflight.py`

Tasks:

1. When starting a stepwise HPSL Flow shorts workflow, immediately update the project:
   - `render_formats=["shorts"]`
   - `subtitle_style` normalized for shorts/readable cues
2. When applying source draft script, preserve or enforce shorts settings if workflow source is HPSL shorts.
3. Add preflight check:
   - vertical Flow assets plus landscape-only render is hard fail.

Tests:

- New test: stepwise project defaults to `["shorts"]`.
- New test: vertical media + landscape-only preflight fails.

### Phase 2 - Make Subtitle QA Render-Blocking

Files:

- `app/services/subtitle.py`
- `app/services/preflight.py`
- `app/services/render_report.py`
- `tests/test_subtitle_rendering.py`
- `tests/test_render_report.py`

Tasks:

1. Add render-format-aware subtitle layout values.
2. Add function that computes final display cue stats:
   - cue count
   - max line count
   - max line length
   - max cue duration
   - offending cue samples
3. Preflight must reject unreadable subtitles.
4. Render report must include subtitle QA.

Tests:

- Long Korean sentence is split into several readable cues.
- Any second line longer than shorts threshold fails QA.

### Phase 3 - Fix TTS Consistency Fallback

Files:

- `scripts/newauto_mcp.py`
- `app/workers/tts_worker.py`
- `app/services/tts.py`
- `app/services/preflight.py`
- `tests/test_tts_worker.py`
- `tests/test_tts_pipeline.py`

Tasks:

1. Stepwise `_enqueue_tts()` must set fixed seed mode explicitly.
2. Full-passage fallback must keep fixed seed mode.
3. TTS consistency report must be pre-render blocking when it recommends full passage/reference voice.
4. If full-passage fails, sentence fallback should not produce mixed-seed voices.

Tests:

- Full-passage abort fallback keeps `seed_mode="fixed"`.
- Manifest sentence seeds are identical after fixed fallback.
- Render preflight fails on `metadata_consistent=false`.

### Phase 4 - Cline-Owned Render Completion

Files:

- `scripts/newauto_mcp.py`
- `app/routers/render.py`
- `app/services/preflight.py`
- `tests/test_render_report.py`
- `tests/test_autopilot_routes.py` or stepwise MCP tests

Tasks:

1. `_enqueue_render()` must run all QA checks and refuse render on failure.
2. Do not build empty render plans as success.
3. Only call `/api/projects/{pid}/render` after:
   - TTS consistency pass
   - subtitle QA pass
   - render format / media aspect pass
   - expected output path is known
4. Return clear Cline-facing message:
   - problem
   - file/field evidence
   - next action

Acceptance:

- Cline directly produces final `output_shorts.mp4` when checks pass.
- No manual DB queueing is needed.
- `render_report.json.status="done"` is not enough; QA fields must also pass.

## Re-Run Procedure After Fix

1. Create or reuse project only after clearing bad outputs.
2. Ensure:
   - `render_formats=["shorts"]`
   - `subtitle_style.cue_split_mode="readable"`
   - `tts_profile.seed_mode="fixed"`
3. Regenerate TTS, do not reuse the current WAVs.
4. Rebuild scene/render plan for shorts.
5. Run `continue_video_workflow` from Cline, not manual DB mutation.
6. Verify:
   - `output_shorts.mp4` exists
   - `ffprobe`: `1080x1920`
   - TTS consistency pass
   - subtitle QA pass
   - no large side bars

## Current Artifact Verdict

`storage/projects/46aece6b3c2f/output.mp4` is rejected.

It is a technically completed FFmpeg render, but it fails final deliverable QA because:

- wrong aspect ratio
- vertical images padded into landscape
- unreadable subtitle segmentation
- inconsistent TTS generation mode
- render was manually queued instead of completed by Cline workflow after QA gates
