# HyperFrames Adoption Plan for newautostudio

Date: 2026-05-16

## Sources Checked

- GitHub: https://github.com/heygen-com/hyperframes
- Official docs: https://hyperframes.app/docs/1-startup/1-introduction
- Local inspected checkout: `%TEMP%\hyperframes-inspect`
- Inspected commit: `2355d505e125fac04357479d444bb11a489a2ed6`
- Release at inspected commit: `chore: release v0.6.12`
- License: Apache-2.0
- Opinion review: `docs/hyperframes-adoption-plan-opinion-2026-05-16.md`
- Local Superpowers skill docs loaded for review:
  - `writing-plans`
  - `systematic-debugging`
  - `verification-before-completion`
  - `test-driven-development`
- Local environment verified:
  - `node --version` => `v22.16.0`
  - `npx --version` => `10.9.2`
  - FFmpeg encoders include `libvpx-vp9` and `prores_ks`

## Review Status

The direction is valid, but this document is now treated as the adoption spec, not the executable implementation plan.

Accepted review corrections:

- Keep HyperFrames as an overlay sidecar, not a ComfyUI replacement.
- Do not add a second `libx264` encode pass.
- Integrate overlay composition into the existing `_mux()` FFmpeg call as a single-pass filter graph.
- Pin HyperFrames version instead of using `npx hyperframes@latest`.
- Vendor or bundle a deterministic Korean font through `@font-face`; do not rely on Chromium font fallback.
- Start with one combined `lower_third_keyword` template instead of six templates.
- Add HyperFrames runtime/preflight checks before render, not only in late diagnostics.
- Define exact `body_image_options` keys and keep them in existing JSON storage; no DB schema migration.
- Treat overlays as editorial motion graphics. They do not fix ComfyUI image/script semantic drift.

Rejected or deferred review suggestions:

- Moving this repo's plans into `docs/superpowers/...` is deferred. The current project convention is date-stamped plans under `docs/`, unless a deliberate repo-wide migration happens.
- Full backend migration remains deferred until overlay-only mode proves useful and stable.

## What HyperFrames Is

HyperFrames is an HTML-to-video rendering framework.

It lets an agent write:

- HTML for the visual structure
- CSS for typography/layout
- GSAP or other frame adapters for deterministic animation
- `data-*` timing attributes for image/video/audio tracks

Then it renders the page frame-by-frame through Chrome and FFmpeg into MP4, WebM, MOV, or PNG sequence.

Important verified traits:

- Requires Node.js >= 22 and FFmpeg.
- Uses Chrome/Puppeteer style capture.
- CLI supports non-interactive agent workflows.
- Supports `lint`, `inspect`, `preview`, `render`, `doctor`.
- Producer can render transparent WebM/MOV/PNG sequences with alpha.
- Registry includes usable overlay/effect blocks:
  - `yt-lower-third`
  - `instagram-follow`
  - `macos-notification`
  - `shimmer-sweep`
  - `texture-mask-text`
  - `vfx-text-cursor`
  - shader transitions and data/chart blocks

## Fit With newautostudio

HyperFrames should not replace the current ComfyUI image generation pipeline.

Best division of labor:

- ComfyUI: semantic image generation, LoRA use, scene illustration, caricature/news visuals.
- OmniVoice/TTS: narration.
- newautostudio render.py: final timeline assembly, audio compatibility, existing ASS captions.
- HyperFrames: premium motion graphics overlays generated from deterministic HTML.

The highest-value use is not "generate better images." It is:

- readable animated text on top of ComfyUI images
- lower-thirds for names/roles/sources
- keyword callouts tied to sentence timing
- transition slates between scenes
- simple data/quote cards for news explainers
- transparent WebM/MOV overlays that can be composited over existing visuals

## Why This Helps Our Current Problems

Recent user-visible issues:

- ComfyUI scenes sometimes match the script weakly.
- News visuals can look empty or generic.
- Subtitles alone do not create strong visual emphasis.
- Static images need editorial motion without making prompts more complex.
- Rendering quality needs deterministic verification.

HyperFrames helps because it adds editorial motion graphics and makes key facts more readable.

It does not fix image/script semantic drift at the source. That remains the responsibility of:

- ComfyUI prompt generation
- LoRA routing
- scene visual planning
- visual relevance gates
- prompt repair/retry behavior

Example:

Instead of asking ComfyUI to draw "Trump called Jensen Huang and added him to the China delegation" perfectly, ComfyUI can draw a simple caricature scene, while HyperFrames overlays:

- "Trump requests Jensen Huang"
- "China delegation"
- "Alaska stopover -> Beijing"
- a simple animated route arrow
- a source/date lower-third

This can make a scene more understandable when the illustration is intentionally simple, but it must not be used to hide a failed or irrelevant image.

## Recommended Architecture

### Option A: Overlay-Only Sidecar

Status: recommended first implementation.

Workflow:

1. newautostudio generates images with ComfyUI.
2. TTS produces timings.
3. A new HyperFrames overlay composer writes a small HTML project:
   - background transparent
   - one composition duration equal to video duration
   - per-sentence animated captions/callouts/lower-thirds
4. HyperFrames renders transparent WebM or MOV.
5. `render.py` overlays that transparent video inside the existing `_mux()` FFmpeg pass before ASS subtitles are burned in.

Pros:

- Minimal disruption.
- Keeps current ComfyUI and render pipeline.
- Lets us test quality without replacing renderer.
- Alpha overlay can be disabled if HyperFrames fails.

Cons:

- Adds Node/Chrome dependency.
- WebM alpha composition must be verified with FFmpeg on Windows.
- Text must use a vendored Korean font to avoid Chromium font fallback drift.

### Option B: Full HyperFrames Render Backend

Status: not recommended yet.

Workflow:

1. Convert every newautostudio scene into HTML:
   - `<img>` clips for ComfyUI images
   - `<audio>` narration
   - animated captions
   - transitions
2. Render the whole final video through HyperFrames.

Pros:

- More unified motion system.
- Better HTML typography and animation control.
- Potentially richer social/video templates.

Cons:

- Duplicates current render.py behavior.
- Increases migration risk.
- Requires revalidating audio mux, subtitle sync, duration drift, shorts/landscape handling.
- Current render.py already has many project-specific safety gates.

### Option C: HyperFrames Template Export Only

Status: useful later.

Generate a HyperFrames project beside each newautostudio project so the user can manually preview/edit motion graphics in HyperFrames Studio.

This is useful for expert users, but it should not be the default automated path.

## Proposed Feature: Editorial Overlay Composer

Create a new service:

```text
app/services/hyperframes_overlay.py
```

Create a CLI script:

```text
scripts/render_hyperframes_overlay.py
```

Project output:

```text
storage/projects/<project_id>/hyperframes_overlay/
  index.html
  assets/
    scene_000.png
    ...
  variables.json
  overlay.webm
  overlay_report.json
```

Initial generated overlay type:

- `lower_third_keyword`
  - one combined template covering lower-third identity/source text plus one short keyword callout
  - first target: Jensen/Nvidia script end-to-end
  - defer all other template types until this one proves useful

Deferred overlay types:

- `keyword_callout`
  - 1-3 Korean keywords from the current sentence.
  - short entrance, hold, exit.
- `name_lower_third`
  - person/company/source labels.
  - Jensen Huang / Nvidia / Trump style use case.
- `timeline_badge`
  - dates, "13일 현지시간", "알래스카 경유", "베이징행".
- `route_arrow`
  - simple line/arrow over a plain area.
- `quote_card`
  - for direct quote or source summary.
- `data_badge`
  - numbers, percentages, battery capacity, price, star count.

Exact project option keys:

```text
body_image_options["hyperframes_overlay_enabled"] -> bool, default false
body_image_options["hyperframes_overlay_required"] -> bool, default false
body_image_options["hyperframes_overlay_status"] -> "not_run" | "done" | "failed" | "skipped"
body_image_options["hyperframes_overlay_report_path"] -> string
```

Global strict-mode override:

```text
NEWAUTO_HYPERFRAMES_STRICT=1
```

No SQLite schema migration is needed for these keys because `body_image_options` already stores JSON.

## News/Tech Video Style Guide

Default visual style should be restrained and legible:

- flat editorial motion graphic
- white or black translucent text plates
- no decorative gradient blobs
- no fantasy/cinematic scenery
- no cluttered UI walls
- max 1 overlay cluster per scene
- max 12 Korean characters per callout line
- avoid covering faces/key objects
- use high contrast against image background
- prefer lower-third and side callout over full-screen text

For our Jensen/Nvidia example:

- Scene 0:
  - image: simple caricature of Jensen Huang and delegation table
  - overlay: "경제사절단 합류"
  - lower-third: "Jensen Huang / Nvidia CEO"
- Scene 1:
  - image: official confirmation/news desk
  - overlay: "엔비디아 공식 확인"
  - badge: "13일 현지시간"
- Scene 2:
  - image: Trump phone call split composition
  - overlay: "트럼프 직접 요청"
- Scene 3:
  - image: Alaska stopover / plane route
  - overlay: "알래스카 경유 -> 베이징"

## Integration Points

### Render Pipeline

Current render path:

```text
ComfyUI images -> _build_visual_track() -> subtitles.ass -> _mux()
```

Proposed overlay path:

```text
ComfyUI images -> _build_visual_track()
TTS timings -> HyperFrames overlay.webm
silent_video + overlay.webm + audio + subtitles.ass -> _mux() single-pass final output.mp4
```

Implementation note:

- Keep existing ASS subtitles for now.
- HyperFrames overlays should supplement subtitles, not replace them.
- The overlay step should run only if `body_image_options["hyperframes_overlay_enabled"] == true`.

### FFmpeg Composition

Expected composition command shape:

Do not create a separate `composited_visual.mp4`.

`app/services/render.py::_mux()` should grow an optional `overlay_path` argument and switch from `-vf ass=...` to a single `-filter_complex` when an overlay exists.

Expected command shape:

```text
ffmpeg -y \
  -i _visual_landscape.mp4 \
  -c:v libvpx-vp9 -i overlay.webm \
  -i audio.wav \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto:shortest=1[base];[base]ass='subtitles.ass'[v]" \
  -map "[v]" -map 2:a:0 \
  -c:v libx264 -pix_fmt yuv420p -r 30 \
  -c:a aac -ar 48000 -ac 2 -b:a 192k \
  -shortest output.mp4
```

Fallback command shape for ProRes 4444 overlay:

```text
ffmpeg -y \
  -i _visual_landscape.mp4 \
  -i overlay.mov \
  -i audio.wav \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto:shortest=1[base];[base]ass='subtitles.ass'[v]" \
  -map "[v]" -map 2:a:0 ...
```

Need to test:

- VP9 alpha WebM overlay on Windows FFmpeg.
- ProRes 4444 MOV fallback if WebM alpha fails.
- Duration drift with overlay stream.

Required alpha assertions:

```text
ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of default=nw=1:nk=1 overlay.webm
expected: yuva420p
```

If VP9 output does not expose alpha, fallback to:

```text
overlay.mov
codec: prores_ks
pix_fmt: yuva444p10le
profile: 4444
```

Required duration assertion:

```text
abs(ffprobe_duration(overlay) - total_duration) <= 0.1
```

If the overlay duration fails this check, disable the overlay for that render unless strict mode is enabled.

### Subtitle And Overlay Zone Contract

ASS subtitles and HyperFrames lower-thirds must not occupy the same screen strip.

Initial rule:

- `lower_third_keyword` overlays may use the lower-left/lower-right area.
- Existing ASS subtitles remain bottom/lower.
- The overlay planner must avoid active subtitle windows for lower-third overlays whenever possible.
- If overlap cannot be avoided, place the keyword callout in the upper side area instead of the lower-third strip.

Future strict rule:

- Add a planner check that no lower-third overlay interval overlaps an ASS cue interval in the same region.

### Font Determinism Contract

HyperFrames overlay HTML must use a vendored font.

Requirements:

- Add a project-local font under the overlay project, for example:

```text
hyperframes_overlay/assets/fonts/Pretendard-Regular.woff2
hyperframes_overlay/assets/fonts/Pretendard-Bold.woff2
```

- Use explicit `@font-face`.
- Use `font-display: block`.
- Do not load Google Fonts or remote font CSS.
- If the font file is missing, preflight must fail overlay generation or disable overlay fallback.

Licensing note:

- Do not copy Windows `Malgun Gothic` into the repo unless licensing is confirmed.
- Prefer a redistributable Korean font such as Pretendard or Noto Sans KR if licensing is acceptable.

### Data Source

Use existing artifacts:

- `project["sentences"]`
- `tts/timings.json`
- `tts/timings_words.json`
- `scene_visual_plan.json`
- `image_prompts_manifest.json`
- `body_image_mappings`
- `render_plan`

Do not ask HyperFrames to infer script semantics from scratch.

The overlay planner should be deterministic and small:

```json
{
  "sentence_idx": 0,
  "start": 0.0,
  "end": 5.2,
  "overlay_type": "keyword_callout",
  "text": "경제사절단 합류",
  "secondary": "Nvidia CEO",
  "position": "lower_left"
}
```

## Validation Gates

HyperFrames overlay generation must pass:

1. `npx hyperframes lint --json`
2. `npx hyperframes inspect --json --samples 15`
3. `npx hyperframes render --format webm --output overlay.webm`
4. `ffprobe` confirms overlay duration within tolerance.
5. FFmpeg alpha composite smoke succeeds.
6. Contact sheet or frame thumbnails show no text overflow.
7. Repeated overlay render from the same inputs is deterministic enough for the selected gate.
8. Overlay does not create visible changes outside its owned regions except intentional animated text/graphics.

If any gate fails:

- Do not block the whole video by default during early rollout.
- Log `hyperframes_overlay_status=failed`.
- Continue with the existing render path.
- Add the failure to diagnostics bundle.

After the feature proves stable, allow strict mode:

```text
hyperframes_overlay_required=true
```

## Dependency Plan

Do not vendor the HyperFrames monorepo.

Recommended:

- Pin the HyperFrames version from the first smoke. Do not use `@latest` in repeatable workflows.
- Use a small tool manifest:

```text
tools/hyperframes/package.json
tools/hyperframes/package-lock.json
```

Initial pinned version candidate:

```text
hyperframes@0.6.12
```

Minimum runtime checks:

- Node.js >= 22
- FFmpeg available
- `npx hyperframes doctor` passes

Add to system diagnostics:

- node version
- npx availability
- hyperframes doctor status
- Chrome availability from HyperFrames

Typed surfaces to update when implementing:

- `app/types.py::SystemHealth`
- `app/services/system_health.py::get_system_health`
- `app/static/app.js` system health panel
- `app/services/preflight.py` when `hyperframes_overlay_enabled=true`
- `app/types.py::RenderReport` if overlay status/path/duration are top-level report fields

## What Not To Do

- Do not use HyperFrames to generate semantic scene images.
- Do not replace ComfyUI or LoRA with HyperFrames.
- Do not render the entire video through HyperFrames in the first phase.
- Do not add busy template overlays to every scene.
- Do not put long Korean paragraphs into animated text boxes.
- Do not rely on external web fonts at render time.
- Do not allow text overlays to cover faces or the core object.
- Do not duplicate the current subtitle engine until overlay quality is proven.
- Do not run two full-resolution `libx264` passes when one `_mux()` pass can do it.
- Do not rely on Chromium's default Korean font cascade.
- Do not pin to `@latest`.
- Do not let ASS subtitles and lower-thirds occupy the same screen zone at the same time.
- Do not build six templates before validating one end-to-end.
- Do not claim this fixes ComfyUI semantic image drift.

## Priority Plan

### P0. Environment Smoke

Goal:

Confirm HyperFrames can run on this Windows machine.

Tasks:

- Check Node.js version.
- Check npx version.
- Check FFmpeg encoders for `libvpx-vp9` and `prores_ks`.
- Run `npx hyperframes doctor`.
- Create a minimal transparent overlay project.
- Render 3 seconds of `overlay.webm`.
- Composite over one existing ComfyUI image.
- Add runtime/preflight probes before render integration.

Acceptance:

- Node is >= 22. Verified locally: `v22.16.0`.
- FFmpeg has `libvpx-vp9` and `prores_ks`. Verified locally.
- `overlay.webm` renders.
- `ffprobe` sees alpha-capable `pix_fmt`.
- FFmpeg preserves alpha in composite.
- Resulting MP4 plays locally.

### P1. Overlay HTML Generator

Goal:

Generate deterministic HTML overlay projects from newautostudio project data.

Files:

- Add `app/services/hyperframes_overlay.py`
- Add `scripts/render_hyperframes_overlay.py`
- Add tests under `tests/test_hyperframes_overlay.py`

Required behavior:

- Uses existing `timings.json`.
- Writes valid `index.html`.
- Writes `overlay_plan.json`.
- Escapes Korean text safely.
- Uses vendored Korean font through `@font-face`.
- Produces no network dependency.
- Produces exactly one initial template: `lower_third_keyword`.

### P2. Render Pipeline Integration

Goal:

Optional overlay inside final mux.

Files:

- Modify `app/services/render.py`
- Modify `app/types.py` if options/status fields are needed.
- Add render tests.

Required behavior:

- Disabled by default.
- Enabled via project option.
- Failure falls back to current render path.
- Strict mode can fail render.
- Render report includes overlay status/path/duration.
- `_mux()` remains a single final encode pass.
- Overlay filter is chained before ASS subtitle burn-in.

### P3. News Templates

Goal:

Create one reusable editorial overlay template for tech/news scripts.

Templates:

- `lower_third_keyword`

Deferred until after Jensen/Nvidia evaluation:

- `source_badge`
- `route_arrow`
- `quote_card`
- `number_badge`

Acceptance:

- Jensen/Nvidia script produces 4 clear scene overlays.
- Overlay text is readable at 1920x1080 and 1080x1920.
- No text overflow in HyperFrames inspect.
- No subtitle/lower-third collision in the sample.

### P4. Diagnostics Bundle Integration

Goal:

Make HyperFrames failures debuggable.

Add to diagnostics bundle:

- `hyperframes_overlay/index.html`
- `hyperframes_overlay/overlay_plan.json`
- `hyperframes_overlay/overlay_report.json`
- `hyperframes_overlay_lint.json`
- `hyperframes_overlay_inspect.json`
- `hyperframes_overlay_ffprobe.json`
- node/npx/hyperframes doctor output
- overlay alpha/duration assertion result

### P5. Full Backend Evaluation

Goal:

After overlay-only path is stable, compare full HyperFrames rendering with current render.py.

Run on 3 projects:

- Jensen/Nvidia news script
- EV/LFP battery explainer
- generic shorts script

Compare:

- duration drift
- audio profile
- caption sync
- render speed
- visual readability
- failure recovery

Only consider full migration if it clearly improves quality without weakening existing gates.

## Recommendation

Adopt HyperFrames as a motion-graphics overlay engine, not as the main image generator or immediate render replacement.

This is the best fit for newautostudio because:

- ComfyUI remains responsible for image semantics.
- HyperFrames adds deterministic, readable editorial graphics.
- Existing render/audio/TTS gates remain intact.
- Failures can gracefully fall back to the current pipeline.
- The feature directly addresses the user's complaint that images can be weird or semantically weak by making the scene meaning explicit through overlays.
- The feature directly addresses the lack of editorial motion graphics and readable visual emphasis.
- It does not directly fix image/script semantic drift; that remains a separate ComfyUI/prompt/visual relevance problem.

## Executable Plan Requirement

Before code implementation, write a separate Superpowers-style implementation plan with bite-sized TDD tasks.

Recommended path:

```text
docs/hyperframes-overlay-implementation-plan-2026-05-16.md
```

Status:

- Written: `docs/hyperframes-overlay-implementation-plan-2026-05-16.md`
- Scope: overlay-only sidecar, one `lower_third_keyword` template, pinned `hyperframes@0.6.12`, health/preflight/diagnostics gates, optional single-pass `_mux()` integration.
- Execution mode should be chosen before code changes:
  - subagent-driven task execution, or
  - inline task execution with a checkpoint after each task.

The implementation plan must include:

- exact files to create/modify
- failing tests first
- commands with expected RED/GREEN output
- one combined `lower_third_keyword` template only
- pinned HyperFrames version
- vendored Korean font setup
- single-pass `_mux()` integration
- diagnostics/preflight gates in P0/P1, not deferred to the end

## 2026-05-16 HyperFrames Overlay P0/P1 Implementation Smoke

- Implemented initial overlay sidecar pieces:
  - `app/services/hyperframes_probe.py`
  - `app/services/hyperframes_overlay.py`
  - `scripts/render_hyperframes_overlay.py`
  - `tools/hyperframes/package.json`
  - `tools/hyperframes/package-lock.json`
- Added typed system health fields for HyperFrames runtime status.
- Added preflight warning/pass gate when `body_image_options["hyperframes_overlay_enabled"]` is true.
- Added optional `_mux(..., overlay_path=...)` support with a single `filter_complex` pass.
- Added diagnostics bundle copying for `hyperframes_overlay/index.html`, `overlay_plan.json`, and `overlay_report.json`.
- Windows runtime fixes:
  - Resolve `node`, `npx`, and `ffmpeg` through `shutil.which()` before `subprocess.run()` so `.cmd` wrappers work.
  - Decode subprocess output as UTF-8 with replacement to avoid cp949 reader failures.
  - Treat HyperFrames `doctor` as ready when Chrome is available and the only remaining failed check is Docker running, because overlay rendering uses local Chrome/FFmpeg.
- Real environment probe:
  - Node: `v22.16.0`
  - npx: `10.9.2`
  - HyperFrames doctor: ready after running `npx hyperframes browser ensure`
  - FFmpeg alpha encoders: `libvpx-vp9` and `prores_ks` available
- Real smoke project:
  - Overlay dir: `storage/projects/hyperframes_smoke/hyperframes_overlay`
  - `npx hyperframes lint --json`: `ok=true`, `warningCount=0`
  - `npx hyperframes inspect --json --samples 15`: `ok=true`
  - WebM render completed but ffprobe returned `pix_fmt=yuv420p`, so alpha validation correctly rejected it.
  - MOV fallback render completed and ffprobe returned `pix_fmt=yuva444p12le`, `duration_sec=3.0`.
  - Final overlay selected: `storage/projects/hyperframes_smoke/hyperframes_overlay/overlay.mov`
  - FFmpeg composite smoke completed:
    `storage/projects/hyperframes_smoke/composite_smoke.mp4`
- Follow-up integration hardening:
  - `render.py` now reads `hyperframes_overlay/overlay_report.json` and uses the selected `overlay_path`, so the real MOV alpha fallback can be passed into `_mux()` instead of only looking for `overlay.webm`.
  - If no report is present, render falls back to `overlay.webm` and then `overlay.mov`.
  - Diagnostics bundle now copies `overlay.webm` and `overlay.mov` in addition to HTML, plan, and report files.
  - The wrapper now writes separate debugging artifacts:
    - `hyperframes_overlay_lint.json`
    - `hyperframes_overlay_inspect.json`
    - `hyperframes_overlay_ffprobe.json`
  - Focused verification after hardening: `48 passed`.
- Automatic overlay generation integration:
  - `render.py` now has `_prepare_hyperframes_overlay()` to write an overlay HTML project from TTS timings, run the HyperFrames wrapper, and return the selected alpha overlay path.
  - `run_render_job()` calls this helper when `body_image_options["hyperframes_overlay_enabled"]` is true.
  - Overlay generation failure falls back to normal render by default; `hyperframes_overlay_required` or `NEWAUTO_HYPERFRAMES_STRICT=1` fails render.
  - Preflight now checks both HyperFrames runtime readiness and Korean font availability.
  - Fixed a report path bug where `overlay_report.json` could point to a cwd-relative `storage/projects/.../overlay.mov`; render now respects that path before falling back.
  - Real helper smoke:
    - Project dir: `storage/projects/hyperframes_auto_smoke`
    - Status: `done`
    - Selected overlay: `storage/projects/hyperframes_auto_smoke/hyperframes_overlay/overlay.mov`
  - Focused verification after automatic generation integration: `54 passed`.
  - Regression verification: `59 passed, 2 warnings`.
- User-facing controls and reporting:
  - `/api/projects/{pid}/features` now accepts:
    - `hyperframes_overlay_enabled`
    - `hyperframes_overlay_required`
  - Step 4 render settings UI now has:
    - `Editorial Overlay`
    - `Require Overlay`
  - The required toggle is disabled unless overlay generation is enabled, and disabling overlay clears required mode.
  - Render report output rows now include:
    - `hyperframes_overlay_status`
    - `hyperframes_overlay_path`
    - `hyperframes_overlay_report_path`
    - `hyperframes_overlay_pix_fmt`
  - Render report UI displays overlay status and alpha pixel format beside each output.
  - Verification after controls/reporting:
    - `node --check app/static/app.js`
    - `59 passed, 2 warnings`
- Current implementation note:
  - The overlay writer uses a local Korean font copied from `C:/Windows/Fonts/NotoSansKR-VF.ttf` into the per-project overlay assets directory as `NotoSansKR-Regular.ttf`.
  - For production redistribution, this should be replaced with a repo-managed, license-checked font asset or an installer-managed font provisioning step.
