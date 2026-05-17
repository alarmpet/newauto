# HyperFrames Adoption Plan — Independent Opinion

Date: 2026-05-16
Reviewer: Claude (Opus 4.7)
Plan under review: `docs/hyperframes-adoption-plan-2026-05-16.md`
Lens applied: Superpowers skills (`brainstorming`, `writing-plans`, `verification-before-completion`, `systematic-debugging`).

## Verification Note

Before writing this opinion, the following were inspected directly:

- `docs/hyperframes-adoption-plan-2026-05-16.md` (full read)
- `app/services/render.py` (render path, `_build_visual_track`, `_mux`, drift guards)
- `app/services/subtitle.py` (ASS style defaults, Korean font handling)
- `app/services/system_health.py` (SystemHealth contract)
- `app/db.py` (schema, `body_image_options` storage)
- `app/types.py` (TypedDict surface for project options and visual modes)
- `app/main.py` (worker spawn / log path conventions)
- `app/routers/flow.py` (current external-asset attach pattern)
- `docs/archive/legacy_logs/research.md` (Flow assisted history, OmniVoice/CUDA, FFmpeg presence)
- `docs/superpowers-adoption-plan-2026-05-16.md` (companion adoption plan)
- `node -v` → `v22.16.0` (HyperFrames Node >= 22 requirement satisfied)
- `ffmpeg -encoders` → `libvpx-vp9` and `prores_ks` confirmed available locally

## Overall Verdict

The strategic direction is correct: **HyperFrames as an overlay sidecar, not a renderer replacement.** Option A is the right first bet, and the labor split between ComfyUI (semantic image) and HyperFrames (editorial motion graphics) matches where this project actually hurts.

But the plan in its current form **would not pass a Superpowers `writing-plans` review**. It is a strategy/scoping document mislabeled as a plan. It lacks bite-sized steps, exact file diffs, TDD red/green cycles, and several technical risks are glossed over. Treat it as the *spec*, then write the actual plan against this critique.

Three concrete things to fix before implementation:

1. **Re-frame as spec → plan.** Promote the current doc to `docs/superpowers/specs/2026-05-16-hyperframes-overlay-design.md` and produce a real implementation plan with 2–5 minute steps, exact paths, code snippets, and `pytest …::test_name` commands per the `writing-plans` skill.
2. **Fix the architectural cost of "overlay before mux."** As drawn, the plan adds an extra x264 re-encode pass. Collapse overlay composition into the existing `_mux` ffmpeg call.
3. **Cut scope ruthlessly (YAGNI).** Ship one overlay type end-to-end (lower-third + keyword callout combined) before building six.

## What the Plan Gets Right

- **Correct division of labor.** ComfyUI keeps semantic image generation; HyperFrames does deterministic typography/motion. This matches the actual failure modes seen in the project.
- **Option A first, Option B deferred.** The "sidecar over full backend" sequencing is correct.
- **Reuse of existing artifacts.** Naming `timings.json`, `timings_words.json`, `scene_visual_plan.json`, `image_prompts_manifest.json`, `body_image_mappings`, `render_plan` is exactly the right inputs and avoids re-deriving semantics in JS.
- **Apache-2.0, pinned commit recorded.** Inspected commit `2355d505e125…` and release version are captured. This is good supply-chain hygiene.
- **Failure fallback is non-blocking by default.** `hyperframes_overlay_status=failed` → continue with existing render path. This is the right safety stance for early rollout.
- **Local FFmpeg + Node 22 confirmed available.** Verified independently: `node -v` = `v22.16.0`, `libvpx-vp9` and `prores_ks` encoders present. The Windows-runtime risk is real but not blocking.

## Problems and Improvements

### 1. Brainstorming gate not satisfied — only one approach evaluated

Per the `brainstorming` skill, 2–3 approaches should be compared with tradeoffs before locking in. The plan presents A/B/C as **HyperFrames-only variants**, not as alternatives to HyperFrames.

Genuine alternatives that deserve a one-paragraph comparison:

- **Extended ASS** — the project already burns ASS via libass in `_mux`. ASS supports `\pos`, `\move`, `\fad`, `\t`, `\frx`, `\fry`, `\frz`, `\clip`, animated `\bord/\shad`, multi-line karaoke. A lower-third + keyword callout can be expressed in ASS with zero new runtime dependency. Determinism guarantee is stronger than headless Chromium.
- **FFmpeg `drawtext` + `drawbox` + `xfade` filter graph** — purely native, no Node, no Chrome. Lower expressiveness than HyperFrames, but composable into the existing filter chain.
- **MoviePy / Manim / Remotion** — also HTML/JS-like but heavier; mentioned only for completeness, not recommended.

The plan should answer: *"Why does an animated lower-third in Korean text justify adding Node + Chromium + Puppeteer to a project that today has only Python + FFmpeg + CUDA?"* The answer may still be HyperFrames, but the question should be asked.

### 2. Architecture: extra x264 pass is silently expensive

The plan diagram is:

```
silent_video.mp4 + overlay.webm  ->  composited_visual.mp4
composited_visual.mp4 + audio + subtitles.ass  ->  final output.mp4
```

That is **two** libx264 encodes of the final video resolution. Current `_mux` already does one. For a 90-second 1080p render the second pass costs ~15–25s of CPU on a laptop and stacks generation-loss artifacts.

Recommended: **single-pass mux**. Add overlay as a third input to the existing `_mux` ffmpeg call and chain it inside the same `-filter_complex` that already applies `ass=`:

```
ffmpeg -y \
  -i _visual_landscape.mp4 \
  -c:v libvpx-vp9 -i overlay.webm \
  -i audio.wav \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto:shortest=1[base];[base]ass='subtitles.ass'[v]" \
  -map "[v]" -map 2:a:0 ...
```

This keeps the file count and re-encode count unchanged from today. `app/services/render.py` line `818` (`_mux`) is the function to extend; do **not** introduce a second composite stage.

### 3. VP9 alpha decode is not as automatic as "format=auto" suggests

`overlay=0:0:format=auto` only preserves alpha if the upstream decoder emits an alpha-aware pixel format. For VP9 alpha you need an explicit decoder hint and to confirm the output format:

```
-c:v libvpx-vp9 -i overlay.webm
```

and the overlay filter should target `format=yuva420p` explicitly, with the final video output forced back to `yuv420p` for x264. The plan calls for testing this but does not specify the fallback (ProRes 4444 MOV) trigger or the exact ffprobe assertion. Validation gate should be:

```
ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt overlay.webm
# expected: yuva420p
```

If `yuva420p` is missing, fall back to ProRes 4444 (`-c:v prores_ks -pix_fmt yuva444p10le -profile:v 4444`).

### 4. Korean font determinism is the actual quality risk

The current subtitle stack uses `Malgun Gothic` (see `app/services/subtitle.py:8`). HyperFrames runs Chromium and will resolve fonts through the Chromium font stack. On Windows that may pick up `Malgun Gothic`; on a different machine it might pick up `Noto Sans CJK`, `Gulim`, or a fallback emoji font. The "deterministic typography" pitch evaporates the moment text rendering depends on whichever Chromium grabbed at runtime.

**Required, not optional:** bundle one explicit `@font-face` reference inside the overlay project pointing at a vendored Korean font file (e.g. `Pretendard-Regular.woff2` or `MalgunGothic.ttf` copied from Windows fonts where licensing permits), and forbid network font loading. Without this, "no external web fonts" is necessary but not sufficient.

### 5. Subtitle/lower-third occupy the same screen real estate

ASS subtitles in `subtitle.py` default to `position: lower` with computed `margin_v`. HyperFrames `name_lower_third` and `data_badge` overlays target the same lower-third strip. Without an exclusion contract they will overlap during the high-emphasis moments where both fire together.

The plan should specify:

- ASS subtitle position is **pinned upper or middle** while a HyperFrames lower-third is on screen, OR
- HyperFrames lower-third only fires during sentence gaps where no ASS cue is rendered, OR
- ASS cue and overlay never coexist within the same time window (planner deduplicates).

This is a planner decision, not a renderer decision, and the plan must own it.

### 6. Duration anchoring is hand-waved

Current renderer enforces `AUDIO_DURATION_DRIFT_TOLERANCE_SEC = 1.0` and terminates if generated video exceeds expected timeline by 1.5x (`render.py:312`). Introducing a second video stream (overlay.webm) adds a second duration source. The plan should specify:

- Overlay total duration is computed from the same `total_duration` used by `_build_visual_track`.
- An ffprobe check on overlay.webm must match within ±100ms.
- Drift outside tolerance demotes overlay to disabled, not a hard failure (matches existing fallback policy).

### 7. SystemHealth contract change is missing

The plan says "Add node version, npx availability, hyperframes doctor, Chrome availability to system diagnostics." But `SystemHealth` is a `TypedDict` declared in `app/types.py` and consumed by the UI. Adding fields requires:

- New fields on `SystemHealth` in `app/types.py`
- Population in `app/services/system_health.py:get_system_health`
- Frontend rendering in `app/static/app.js` health card
- A preflight check (not just a diagnostics dump) so a missing Chrome surfaces *before* render kicks off when `hyperframes_overlay_enabled=true`

P4 in the plan puts diagnostics last. Move the preflight piece to **P0** so failures are caught before users wait for a render.

### 8. DB schema + body_image_options typing

The plan mentions `body_image_options["hyperframes_overlay_enabled"]` and `hyperframes_overlay_required`. But:

- `body_image_options` is a `dict[str, object]` with no typed access — fine, but the plan should still enumerate the exact keys it introduces (`hyperframes_overlay_enabled`, `hyperframes_overlay_required`, `hyperframes_overlay_status`, `hyperframes_overlay_report_path`).
- If a top-level render report field is wanted (status visible in render_report.json), `RenderReport` in `app/types.py` needs an additive field. Plan omits this.
- No migration is needed if all new fields stay inside `body_image_options` JSON, but the plan should state that explicitly so a future reader does not add SCHEMA columns by accident.

### 9. Strict mode location is ambiguous

`hyperframes_overlay_required=true` — is this per-project (inside `body_image_options`), global (env var), or both? Recommended: per-project default = false, env var `NEWAUTO_HYPERFRAMES_STRICT=1` to flip the global default. Plan should pick one and write it down.

### 10. P0–P5 are phases, not steps

The Superpowers `writing-plans` skill requires steps that are 2–5 minutes each, with:

- exact file paths to create/modify with line ranges where modifying,
- complete code blocks (no "implement minimal code"),
- exact pytest commands with `::test_name` and expected output,
- exact `git commit -m` strings.

P0 of the existing plan is closer to a sprint goal than a step list. Rewrite each P-level as a sequence of bite-sized tasks. Example expansion of P0:

- **Step P0.1:** Add `app/services/hyperframes_probe.py` with `probe_node()` and `probe_doctor()` returning typed status (write file, show full code).
- **Step P0.2:** Write `tests/test_hyperframes_probe.py::test_probe_node_returns_version_string` failing test, show full code, run `pytest tests/test_hyperframes_probe.py -v`, expect FAIL.
- **Step P0.3:** Implement minimum probe to make P0.2 pass, run test, expect PASS.
- **Step P0.4:** Commit `feat: add hyperframes runtime probes`.
- … and so on for each gate.

### 11. TDD red/green discipline absent

No regression test, no "revert fix, run test, confirm RED, restore, confirm GREEN" cycle. For a renderer-adjacent feature this matters because pixel-level regressions are hard to spot.

Concrete acceptance gates that should appear in the plan:

- Pixel SSIM ≥ 0.95 between `_visual_landscape.mp4` and `output.mp4` in the **subtitle-free zones** (i.e. overlay should not bleed into image regions it does not own).
- Hash equality of `overlay.webm` frames between two consecutive runs of the same project (determinism gate — this is HyperFrames' main pitch).
- `ffprobe` overlay duration within ±100ms of timeline duration.

### 12. `npx hyperframes@latest` is non-deterministic

The plan recommends `npx hyperframes@latest` for early prototyping. `@latest` re-resolves on every run, so a patch release upstream will silently change overlay rendering. For a project that prides itself on deterministic gates this is contradictory. Either pin `npx hyperframes@0.6.12` from day one, or run only behind `tools/hyperframes/package.json` with a lockfile.

### 13. YAGNI: cut 6 templates to 1

P3 lists six templates: `news_lower_third`, `keyword_callout`, `source_badge`, `route_arrow`, `quote_card`, `number_badge`. Build **one** template that does lower-third + keyword callout in a single block, ship it end-to-end, render the Jensen/Nvidia script, judge quality, *then* decide which of the remaining five are still worth building. Most likely 2–3 of them will be obsoleted by feedback before code is written.

### 14. Honest framing of what this fixes

The recommendation says HyperFrames "directly addresses the user's complaint that images can be weird or semantically weak." This conflates two distinct failure modes:

- **Image–script semantic drift** — root cause is ComfyUI prompt/LoRA/visual_brief routing. Overlays do not fix it; they paper over it.
- **Lack of editorial motion graphics** — root cause is "we have no overlay engine." HyperFrames legitimately fixes this.

Be explicit that this is the second problem only. The first one belongs to a different plan (prompt_repair, visual_relevance gates, scene_plan tuning).

### 15. Process: where this plan came from

If this was generated from a spec, link the spec. If not, run it back through `brainstorming` first. The current document is mid-way between spec and plan and would benefit from being split:

- **Spec** (problem statement, decision, scope, gates, what-not-to-do) → `docs/superpowers/specs/2026-05-16-hyperframes-overlay-design.md`
- **Plan** (bite-sized tasks with code) → `docs/superpowers/plans/2026-05-16-hyperframes-overlay.md`

This is exactly the split the `brainstorming` → `writing-plans` skill chain enforces.

## Recommended Minimal Next-Step Plan (Sketch)

Not a substitute for a real `writing-plans` pass, but a sketch of what the first slice should look like:

1. **Probe** (`app/services/hyperframes_probe.py`) — detect node, npx, hyperframes doctor, Chrome. Surface as four fields on `SystemHealth`.
2. **Spec one template** — a single combined "lower-third + keyword" block. Vendored Korean font. Transparent WebM output, 1080p only first (shorts later).
3. **Planner** (`app/services/hyperframes_overlay.py`) — produce `overlay_plan.json` deterministically from `timings.json` + `body_image_mappings` + `scene_visual_plan.json`. Pure function. No HTTP. Tested with golden files.
4. **HTML generator** — emit `index.html` from the plan. Pure function. Tested with golden HTML comparison.
5. **CLI wrapper** (`scripts/render_hyperframes_overlay.py`) — call `npx hyperframes render --format webm`. Pinned version. Capture exit code and ffprobe.
6. **Single-pass mux integration** in `_mux` — extra `-i overlay.webm` with `overlay=` filter chained before `ass=`. Behind `body_image_options["hyperframes_overlay_enabled"]`. Strict mode opt-in.
7. **Determinism test** — render Jensen/Nvidia script twice, hash `overlay.webm` frames, assert equality.
8. **SSIM regression test** — between `_visual_landscape.mp4` and `output.mp4` in subtitle-free zones, assert SSIM ≥ 0.95.
9. **Document strict-mode and the kill switch.**

Each of these expands into 4–8 actual 2–5 minute steps when written out in the `writing-plans` format.

## What Not to Do (additions to the plan's existing list)

- Do not run two libx264 passes when one will do.
- Do not rely on Chromium's default Korean font cascade.
- Do not pin to `@latest`; pin to a SHA or version.
- Do not let ASS subtitles and HyperFrames lower-thirds occupy the same screen zone at the same time.
- Do not build six overlay templates before validating one.
- Do not treat overlay generation cost as free — measure wall-clock added per project and surface it in `render_report.json`.
- Do not claim the feature is "verified" until determinism + SSIM + duration-drift tests have all run green in a fresh shell.

## Bottom Line

Direction: right.
Document type: spec-shaped, mislabeled as plan.
Hidden risks: Korean font determinism, extra encode pass, subtitle/overlay zone collision, `@latest` non-determinism.
Process: needs a real `writing-plans` pass with TDD discipline before code is touched.

Adopt HyperFrames as proposed, but split this document into a spec + a real plan, fix the single-pass mux architecture, vendor the Korean font, and ship one template end-to-end before any of the other five.

---

**Saved at:** `C:\Users\petbl\newauto\docs\hyperframes-adoption-plan-opinion-2026-05-16.md`
