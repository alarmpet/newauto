# Render And Subtitle Fixes Plan

## Goal

Fix the render progress freeze perception around `35%`, broken UI text, overly long subtitle lines that clip at the sides, and the mismatch between preview and rendered `lower` subtitle placement.

Status: `[Done]`

## Confirmed Issues

1. Render progress used coarse fixed milestones, so long FFmpeg steps such as audio normalization or muxing looked stuck.
2. Default subtitle length was too wide, which made long lines fill the frame and clip near the left and right edges.
3. The preview and ASS render paths did not place `lower` subtitles using the same visual rule.
4. Some user-facing strings in the static UI were mojibake.

## Completed Work

### Phase 1. Render phase tracking `[Done]`

- Added `render_phase` and `render_last_log` to project persistence.
- Updated render jobs to publish named phases through the pipeline.
- Exposed phase and recent log text through the status API and UI.

### Phase 2. Shorter default subtitle policy `[Done]`

- Reduced the default `max_line_chars` from `40` to `26`.
- Tightened the editable UI range to `16..40`.
- Preserved existing saved project values.

### Phase 3. Width-aware line safety `[Done]`

- Added an effective line-length cap based on `font_size`, `margin_h`, and frame width.
- Improved `_smart_wrap()` so long lines split more evenly.
- Applied the same safer wrapping policy to both SRT and ASS output.

### Phase 4. `lower` placement correction `[Done]`

- Rebalanced preview and ASS layout rules so `lower` sits closer to the intended lower-third area.
- Adjusted `upper` and `lower` positioning to better match real rendered output.

### Phase 5. UI encoding cleanup `[Done]`

- Rewrote the main static HTML entry as clean UTF-8 content.
- Replaced remaining critical mojibake strings in `app/static/app.js`.
- Added `scripts/check_encoding.py` and wired it into `scripts/typecheck.ps1`.

### Phase 6. Validation `[Done]`

- Updated tests for subtitle layout defaults, wrapping behavior, placement, and render status exposure.
- Re-ran:
  - `scripts/typecheck.ps1`
  - `node --check app/static/app.js`
  - `omnivoice_env\Scripts\python.exe -m unittest discover -s tests -v`

## User-Facing Result

- Render status now shows the current stage instead of looking frozen at one percentage for long stretches.
- New subtitle defaults target roughly 20 to 30 visible characters per screen.
- `lower` placement is visually lower and closer to the expected lower-third area.
- Key render, upload, thumbnail, and OAuth UI text no longer appears broken.

## Follow-up Checks

- Observe a long real-world render to confirm the phase transitions feel natural.
- Gather feedback on whether the new 26-character default should be even stricter for some formats.
