# Superpowers Adoption Plan for newautostudio

Date: 2026-05-16

## Sources Checked

- GeekNews summary: https://news.hada.io/topic?id=29552
- Maily article: https://maily.so/makersnote/posts/1do1dwqlox6
- Superpowers repository: https://github.com/obra/superpowers
- Superpowers marketplace metadata: `C:\Users\petbl\.codex\.tmp\marketplaces\superpowers-marketplace\.claude-plugin\marketplace.json`
- Local inspected plugin checkout: `%TEMP%\superpowers-inspect`
- Review document: `docs/superpowers-adoption-review-2026-05-16.md`

## Superpowers Skills Loaded For Review

The Superpowers plugin is not active as a first-class skill in this session yet, so the local inspected Superpowers `v5.1.0` skill files were loaded directly.

Reviewed skills:

- `systematic-debugging`
- `verification-before-completion`
- `writing-plans`
- `test-driven-development`

Relevant principles:

- Find root cause before fixes.
- Gather evidence at every component boundary.
- Write plans/specs before multi-file implementation.
- Use failing tests before behavior changes.
- Do not claim completion without fresh artifact verification.

## Installation Status

Completed:

```powershell
codex plugin marketplace add obra/superpowers-marketplace
codex plugin marketplace upgrade superpowers-marketplace
```

Current Codex config includes:

```toml
[marketplaces.superpowers-marketplace]
source = "https://github.com/obra/superpowers-marketplace.git"
```

Limitation:

- Current Codex CLI exposes `codex plugin marketplace add/upgrade/remove`.
- It does not expose a non-interactive `codex plugin install superpowers...` command.
- The Superpowers README points users to Codex App plugin installation or interactive `/plugins`.
- Therefore the marketplace is registered, but the `superpowers` plugin itself still needs activation in Codex App/interactive plugin UI unless a later CLI adds non-interactive install.

Recommended manual completion:

```text
Codex App -> Plugins -> Coding -> Superpowers -> + install
```

or in interactive Codex:

```text
/plugins
search: superpowers
Install Plugin
```

## What Superpowers Is

Superpowers is a workflow and skills framework for coding agents, not a direct ComfyUI/TTS/video generator.

Core behaviors:

- Ask clarifying questions before implementation when requirements are unclear.
- Save specs and plans as files so intent survives session resets.
- Use implementation plans before multi-file code changes.
- Use TDD for behavior changes.
- Use systematic debugging before fixes.
- Use review stages for spec compliance and code quality.
- Use evidence before claiming completion.

For newautostudio, the value is mainly process discipline and enforceable gates.

## Verified Codebase Facts

These claims from the review document were verified against the codebase.

### Existing Systems We Should Reuse

The project already has several Superpowers-style systems:

- Prompt quality gates:
  - `app/workers/image_worker.py`
  - `_BLOCKING_PROMPT_QUALITY_CODES`
- Generic fallback issue detection:
  - `app/services/prompt_quality.py`
  - `GENERIC_FALLBACK_IN_MUST_SHOW`
  - `GENERIC_FALLBACK_IN_PROMPT`
- Visual relevance reports and artifacts:
  - `app/services/visual_relevance.py`
  - `write_final_scene_review`
  - `write_visual_contact_sheet`
  - `write_visual_mismatch_report`
- Render reports:
  - `app/services/render_report.py`
  - `build_render_report`
- Preflight checks:
  - `app/services/preflight.py`
- Operator summaries:
  - `app/services/operator_summary.py`

Plan implication:

- Do not duplicate these systems.
- Extend them where gates are missing.

### Missing Or Weak Systems

These are real gaps:

- Internal render WAV normalization is still 24kHz mono:
  - `app/services/render.py`
  - `AUDIO_SAMPLE_RATE = 24000`
  - `AUDIO_CHANNELS = 1`
- Final MP4 mux now forces player-compatible AAC 48kHz stereo.
- `render_report.py` now records final output audio sample rate, channel count, codec, bitrate, and volume/audibility metrics.
- `ffmpeg volumedetect` is now part of render report generation for existing outputs.
- `operator_intervention_required` now blocks render by default unless the explicit visual override flag is set.
- `scripts/collect_project_diagnostics.py` now exists and writes a project diagnostics bundle.
- `app/services/diagnostics.py` now exists as a thin wrapper over existing reports/artifacts.
- `docs/superpowers/` does not exist.

### Adjusted Findings

The review document is directionally right, but these adjustments are important:

- Superpowers plugin activation is not the immediate fix. The immediate fix is to implement the missing gates in code.
- The plan should acknowledge existing gates instead of describing all artifact evidence as new work.
- The official Superpowers `writing-plans` skill recommends `docs/superpowers/plans/`, but this repository currently uses date-stamped plans under `docs/`. Continue using the current `docs/` convention unless the plugin is fully activated and the repository intentionally migrates.
- A diagnostics bundle should be a thin wrapper over existing reports, not a parallel reporting subsystem.

## Best-Fit Superpowers Practices For newautostudio

### 1. systematic-debugging

Use whenever a generated video has a defect.

Mandatory evidence before fixes:

- `ffprobe` stream report
- `ffmpeg volumedetect`
- `render_report.json`
- `preflight_report.json`
- `tts/timings.json`
- `tts/tts_run_manifest.json`
- `final_scene_review.json`
- `visual_mismatch_report.md`
- `diagnostic_contact_sheet.jpg`

This is especially important because recent output had an audio complaint even though the MP4 contained an AAC audio stream and measurable volume.

### 2. verification-before-completion

Use before saying a video is complete.

Completion claims must require fresh evidence:

- final MP4 exists
- ffprobe confirms video and audio streams
- audio is 48kHz stereo AAC, or an explicit exception is documented
- volume is not near-silent
- render duration drift is acceptable
- TTS timings match normalized script
- contact sheet is manually reviewed
- no blocking visual relevance issues remain unless a user-requested override is recorded

### 3. writing-plans

Use for multi-file changes:

- render audio compatibility
- post-render audio verification
- Media prompt pipeline changes
- visual relevance scoring fixes
- image worker retry/fallback behavior
- TTS normalization

Plan file convention for this repo:

```text
docs/YYYY-MM-DD-<issue>-implementation-plan.md
```

### 4. test-driven-development

Use for behavior changes:

- Korean-plus-English alias normalization
- final MP4 48kHz stereo mux
- post-render audibility metrics
- render blocking on `operator_intervention_required`
- no automatic Stickfigures LoRA upgrade
- deterministic scene templates

Required pattern:

1. Write failing test.
2. Run it and confirm the expected failure.
3. Implement minimal fix.
4. Run targeted tests.
5. Run artifact verification commands.

## Priority Plan

### P0. Correct The Process Model

Status: in progress.

Actions:

- Treat Superpowers as workflow discipline, not a magic runtime dependency.
- Keep using existing `docs/` plan style for now.
- Reuse existing `preflight`, `render_report`, `visual_relevance`, `operator_summary`, and prompt-quality systems.
- Avoid final "complete" claims unless fresh evidence is included in the same response.

### P1. Add Missing Render Completion Gates

Goal:

Prevent "rendered but user cannot hear it" and "rendered despite operator review required" failures.

Status: implemented and targeted-tested on 2026-05-16.

Files:

- Modify: `app/services/render.py`
- Modify: `app/services/render_report.py`
- Modify: `app/services/preflight.py`
- Test: `tests/test_render_visual_track.py`
- Test: `tests/test_render_report.py`
- Add or modify: render/preflight tests for `operator_intervention_required`

Required behavior:

- Done: Final MP4 mux targets AAC 48kHz stereo at about 192k.
- Done: Render report includes final output audio stream codec, sample rate, channel count, bitrate, and profile pass/fail.
- Done: Render report includes audibility metrics from `ffmpeg volumedetect`.
- Done: Render blocks by default if any selected scene has `operator_intervention_required=true`.
- Done: Render may proceed only with the explicit visual warning override flag, and the override is written to the ffmpeg log tail.

Existing tests to update:

- Kept `tests/test_render_visual_track.py::test_normalize_audio_forces_pcm_24k_mono` because it covers the internal WAV normalization stage.
- Added mux-level coverage for final AAC 48kHz stereo compatibility.

Verification:

- `python -m pytest tests/test_render_visual_track.py tests/test_render_report.py tests/test_visual_relevance.py -q` => 51 passed.
- `python -m pytest tests/test_render_visual_track.py tests/test_render_report.py tests/test_tts_pipeline.py tests/test_autopilot_worker.py -q` => 58 passed.

### P2. Add A Thin Diagnostics Bundle

Goal:

Collect one evidence bundle per problematic project without creating a parallel reporting architecture.

Status: implemented and verified on 2026-05-16.

Create:

```text
scripts/collect_project_diagnostics.py
```

Implemented:

```text
app/services/diagnostics.py
scripts/collect_project_diagnostics.py
tests/test_diagnostics.py
```

Output:

```text
storage/projects/<project_id>/diagnostics_bundle/
```

Contents:

- `ffprobe_output.json`
- `audio_volumedetect.txt`
- `render_report.json`
- `preflight_report.json`
- `tts_manifest_excerpt.json`
- `visual_mismatch_report.md`
- `visual_mismatch_report.json`
- `final_scene_review.json`
- `operator_summary.json`
- `diagnostic_contact_sheet.jpg`
- `diagnostics_manifest.json`

Implementation note:

- Reuse existing services and files.
- Do not duplicate scoring or report generation logic.

Verification:

- `python -m pytest tests/test_diagnostics.py tests/test_render_report.py tests/test_visual_relevance.py -q` => 28 passed.
- `python -m pytest tests/test_diagnostics.py tests/test_render_visual_track.py tests/test_render_report.py tests/test_visual_relevance.py tests/test_tts_pipeline.py tests/test_autopilot_worker.py -q` => 83 passed on rerun.
- Real bundle smoke:
  - `python scripts\collect_project_diagnostics.py 066827c044eb`
  - Output: `storage/projects/066827c044eb/diagnostics_bundle/`
  - The old sample output still reports AAC 24kHz mono because it was rendered before the P1 mux fix. Regenerate to verify new AAC 48kHz stereo output.

### P3. Tighten News Caricature Visual Quality

Goal:

Stop "simple caricature" prompts from producing cluttered or generic images.

Files:

- Modify: `app/services/image_prompting.py`
- Modify as needed: `app/services/prompt_quality.py`
- Test: `tests/test_image_prompting.py`

Required prompt constraints:

- max 2-4 characters
- one large prop
- plain bright background
- no dense meeting room
- no wall of documents
- no dense diagram
- no tiny distant people

Acceptance:

- Scene 0 delegation prompt cannot generate a meeting-room crowd.
- Scene 2 phone-call prompt must include a split phone-call composition and not just generic portraits.
- Render should not auto-ship if selected visual review remains blocked.

### P4. Use Superpowers Plugin If Activation Becomes Available

Action:

- Install `superpowers` from Codex App/interactive `/plugins` when available.
- After activation, check whether Superpowers skills appear in the session skill list.
- If official skill path becomes active, consider moving future multi-step implementation plans to `docs/superpowers/plans/` only after updating repository convention.

## Immediate Next Implementation Plan

Create:

```text
docs/2026-05-16-output-audio-visual-quality-implementation-plan.md
```

Plan tasks:

1. Add failing tests for final MP4 audio compatibility.
2. Change mux/audio pipeline to output 48kHz stereo AAC.
3. Add post-render ffprobe and volumedetect metrics to render report.
4. Add render block for `operator_intervention_required` unless explicit override is set.
5. Tighten news caricature prompt templates and tests.
6. Add diagnostics bundle script.
7. Re-run Jensen/Nvidia workflow and verify:
   - final MP4 audio stream is AAC 48kHz stereo
   - volume is non-silent
   - scene 0 is not cluttered
   - scene 2 is a phone-call request scene
   - no render proceeds through blocking visual review without override

## Recommendation

Adopt Superpowers principles immediately, even before full plugin activation.

For newautostudio, the highest value is:

- root cause before fixes
- TDD before behavior changes
- evidence bundle before implementation
- artifact verification before completion claims
- render gates that prevent low-quality outputs from being treated as finished

The review document is mostly valid after correcting for existing systems and repository conventions. The plan now reflects only the verified, useful parts.
