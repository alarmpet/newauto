# Video Project Log

Project-level final verdicts and notable artifacts. Each project should end as `PASS`, `FAIL`, or `PARTIAL`.

## Summary

| Project ID | Verdict | Main artifact | Notes |
|---|---|---|---|
| `69ab599cc01a` | PASS | `storage/projects/69ab599cc01a/output_shorts.mp4` | Windows Studio MVP smoke sample: 3 sentences, 3 uploaded/sample scenes, TTS, subtitles, shorts render |
| `87b2c4f3d1a3` | PASS | `storage/projects/87b2c4f3d1a3/output_shorts.mp4` | Full shorts output succeeded; keep separate from older landscape QA failures on related runs |
| `15d29f514890` | PARTIAL | `storage/projects/15d29f514890/flow_generated/flow_s001_20260514T005830.jpeg` | Stopped after Flow image 1/6 due to MCP timeout and OpenRouter 429 |
| `9e25bd65f9d7` | PARTIAL | `storage/projects/9e25bd65f9d7/output.mp4` | Render completed, but artifact is landscape and QA notes remain |
| `46aece6b3c2f` | FAIL | `storage/projects/46aece6b3c2f/output.mp4` | Final render QA failure |

## `69ab599cc01a`

- Final verdict: PASS
- Main artifact: `storage/projects/69ab599cc01a/output_shorts.mp4`
- Format: `shorts`
- File size: 142,411 bytes
- Duration: 7.2 seconds
- Flow: 3 sentence script -> 3 scene images -> TTS/audio -> ASS subtitles -> render(shorts)
- Verification:
  - `render_report.json` status is `done`.
  - `duration_guard_passed=true`.
  - `output_duration_sec=7.2`.
  - `render_plan_segment_count=3`.
  - `subtitle_cue_count=3`.
  - `missing_render_plan_media_count=0`.
  - `fallback_used=false`.
- Remaining notes:
  - This is a Windows Studio MVP smoke sample, not a full Flow/ComfyUI generated video.
  - The first sentence in review artifacts shows a BOM/mojibake prefix (`癤퓆ewauto...`). Treat this as a sample input encoding cleanup item, not a render failure.

## `87b2c4f3d1a3`

- Final verdict: PASS
- Main artifact: `storage/projects/87b2c4f3d1a3/output_shorts.mp4`
- Format: `shorts`
- File size: about 3.8 MB
- Completed flow: source collection -> HPSL script -> script apply -> Flow image 6/6 -> TTS -> render(shorts)
- Notes:
  - Older records around the same effort include `output.mp4` landscape QA failures.
  - Final success is judged by `output_shorts.mp4`.
  - When citing this project, keep landscape failure/review records separate from the shorts success artifact.

## `9e25bd65f9d7`

- Final verdict: PARTIAL
- Artifact: `storage/projects/9e25bd65f9d7/output.mp4`
- Render report:
  - `status=done`
  - `audio_duration_sec=41.78`
  - `output_duration_sec=41.766667`
  - `duration_guard_passed=true`
  - `subtitle_cue_count=6`
  - `missing_render_plan_media_count=0`
  - `fallback_used=false`
- Remaining risks:
  - Artifact was recorded as landscape 1920x1080, so it is not a shorts PASS.
  - QA notes included subtitle overload, weak hook, title mismatch, visual relevance weakness, and failed asset dependency concerns.

## `46aece6b3c2f`

- Final verdict: FAIL
- Artifact: `storage/projects/46aece6b3c2f/output.mp4`
- Failure reasons:
  - Portrait-image-based work rendered as landscape 1920x1080.
  - Subtitle cues were long and overloaded.
  - TTS fallback used sentence mode and carried voice consistency risk.
  - Manual DB status edits were judged unsafe as a pass criterion.
- Operating rule:
  - Do not mark outputs as PASS unless they pass the QA gate.

## `15d29f514890`

- Final verdict: PARTIAL
- Artifact: `storage/projects/15d29f514890/flow_generated/flow_s001_20260514T005830.jpeg`
- Status:
  - Only the first image was generated.
  - `continue_video_workflow` hit an MCP timeout.
  - OpenRouter free model later hit a 429 rate limit.
- Next action:
  - Before resuming the same symptom, consult `incident_runbook.md` for OpenRouter rate-limit and Flow asset recovery guidance.

## Recording Template

```md
## `<PROJECT_ID>`

- Final verdict: PASS / FAIL / PARTIAL
- Input URL/keyword:
- Main artifact:
- Format:
- Verification:
- Failure/recovery:
- Remaining risks:
```
