# ComfyUI SDXL Integration Roadmap

Status: Draft, reviewed and updated 2026-04-29  
Sources: `comfyui.txt`, `sdxl.txt`, current code inspection, `C:\Users\petbl\.gemini\antigravity\brain\3c437077-0e8c-4452-8bc6-73f8e20a38e5\comfyui-sdxl-roadmap-review.md`  
Goal: Use the ComfyUI and SDXL research notes to improve image relevance, consistency, render stability, and operator control in the current autopilot video pipeline.

## 0. Review Update

The external review agrees with the overall direction, but it changes the practical execution order. The fastest visible improvement is not the full prompt-slot refactor. It is first connecting `quality_mode` and workflow profiles to actual ComfyUI KSampler parameters.

Current highest-priority confirmed issues:

- `txt2img_sdxl_basic.json` still hardcodes `euler`, `normal`, `20 steps`, `cfg 7`, and `denoise 1`.
- `image_worker.py`, `image_gen.py`, and the workflow payload path do not yet pass `steps`, `cfg`, `sampler`, `scheduler`, or `denoise` through to the template.
- `quality_mode` is currently close to dead code for image generation quality because it does not change the KSampler settings.
- `visual_brief.py` can still fall back to checklist-style imagery when LLM planning fails.
- Candidate scoring needs score normalization and `score_version`; the current scoring can exceed a clean 0-1 scale.
- `comfyui_client.py` has a short hardcoded request timeout risk for heavier SDXL jobs.
- SDXL micro-conditioning and dual CLIP-G/CLIP-L prompt strategy are missing from the current roadmap and should be tracked.

Roadmap policy after review: P0 must focus on the smallest code changes that can immediately affect output quality, then proceed to prompt structure and quality gates.

## 0.1 Implementation Progress

Updated 2026-04-29:

- Completed P0 Phase 1 core plumbing:
  - Added `app/services/image_generation_profiles.py`.
  - Replaced hardcoded KSampler values in both SDXL ComfyUI templates with placeholders.
  - Wired `steps`, `cfg`, `sampler_name`, `scheduler`, `denoise`, `generation_profile`, `request_timeout_sec`, `seed_policy`, and `score_version` through prompt suggestions, batch queue items, manual workflow payloads, and `image_worker.py`.
  - `quality_mode` now affects actual ComfyUI runtime parameters.
- Completed the fallback-safety part of P0 Phase 2:
  - Generic `visual_brief.py` fallback no longer emits checklist imagery by default.
  - Utility consolidation remains pending.
- Completed P0 Phase 6:
  - Candidate scores are now clamped to 0-1.
  - Candidate entries and mappings record `candidate_score_version`.
  - Candidate entries record score components for debugging.
- Completed P0 Phase 7 coverage for the implemented pieces:
  - Workflow placeholder substitution.
  - Route-rendered KSampler parameters.
  - Batch queue profile metadata.
  - Spaced candidate seeds.
  - Non-checklist generic fallback.
  - Candidate score clamp.

Verified with:

`python -m unittest tests.test_comfyui_workflows tests.test_visual_brief tests.test_candidate_selection tests.test_comfyui_routes tests.test_image_prompting`

Updated 2026-04-29 02:40:

- Completed P0 Phase 3 first pass:
  - Essay prompts now compile through safer SDXL-style slots: subject, action, environment, framing, lighting/style, and camera/technical anchors.
  - Essay positive prompts now add `35mm lens`, `sharp focus`, `natural color`, `detailed real-world textures`, `medium wide shot`, and `no readable text`.
  - Raw Hangul visual targets are filtered from essay positive prompts and replaced with neutral visible anchors.
- Completed P0 Phase 4 first pass:
  - Expanded essay global avoid vocabulary with car/vehicle drift, compass/map/checklist symbols, graph/coin/seedling drift, text risks, and closeup/cropped-limb risks.
  - Essay negative prompts now include SDXL text/framing/artifact controls.
- Completed P0 Phase 5 first pass:
  - Added quality issue detection for `RAW_TEXT_VISUAL_TARGET`, `GENERIC_SYMBOL_WITHOUT_ALLOW`, `BOOK_TEXT_RISK`, `CLOSEUP_RISK`, `MISSING_FRAMING_SLOT`, and `MISSING_CAMERA_TECHNICAL_SLOT`.
  - Project quality reports now count and surface the new issue codes.
- Completed the low-risk utility part of P0 Phase 2:
  - Added `app/services/parse_utils.py`.
  - Replaced duplicated number parsing helpers in image route, image worker, and ComfyUI pipeline.
  - Domain-detection consolidation remains intentionally pending because it touches planner fallback behavior more broadly.

Verified with:

`python -m unittest tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker`

`powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

Updated 2026-04-29 02:55:

- Completed the practical first pass of the remaining P0 utility cleanup:
  - Added `app/services/domain_detection.py`.
  - `visual_planner.py` and `image_prompting.py` now share the same project-level tech-domain helper instead of maintaining separate logic.
  - `visual_brief.py` still keeps local token-based fallback detection for generic no-project contexts; full consolidation there remains optional, not blocking.
- Connected prompt quality gates to auto-repair in `suggest_image_prompt()`:
  - If coverage detects missing framing, missing technical anchors, or book/text risk, the prompt pipeline now performs one additional safe repair pass.
  - The repair pass can inject framing, camera/technical anchors, and readable-text protection into the prompt pair before returning.

Verified with:

`python -m unittest tests.test_domain_detection tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker tests.test_visual_planner`

`powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

Updated 2026-04-29 03:11:

- Completed the first practical slice of P1 candidate handling:
  - Added candidate review decisions in `app/services/comfyui_pipeline.py`.
  - Best candidates are now labeled as strong, borderline, or retry-recommended using the normalized score.
  - Project `body_image_options` now stores per-sentence `candidate_reviews` with best score, score version, retry flag, retry reason, and selection reason.
  - Worker logs now preserve retry recommendations instead of losing them behind later plan-refresh logs.
- Completed the first explicit seed-policy path:
  - Batch image generation now supports `fixed`, `spaced`, `random`, and `variant_random` seed policies.
  - Queue items now store the resolved `seed_policy`.
  - Manual batch input can override the profile default seed policy.

Verified with:

`python -m unittest tests.test_domain_detection tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker tests.test_visual_planner`

`powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

Updated 2026-04-29 03:26:

- Completed the first opt-in implementation of the low-VRAM Lightning path:
  - Added `txt2img_sdxl_lightning.json`.
  - Added named generation-profile resolution in `app/services/image_generation_profiles.py`.
  - Added `sdxl_low_vram_lightning` with:
    - workflow `txt2img_sdxl_lightning`
    - sampler `euler`
    - scheduler `sgm_uniform`
    - steps `6`
    - cfg `2.0`
    - `requires_lightning_checkpoint=True`
  - Batch generation now accepts `generation_profile` explicitly and honors profile sampler/step/cfg values when the profile is requested.
  - Manual workflow render/submit now switches to the Lightning workflow when `generation_profile=sdxl_low_vram_lightning` is requested and no LoRA override is in play.
- Safety policy remains conservative:
  - No automatic global switch to Lightning.
  - Lightning stays opt-in so existing standard SDXL flows do not silently change.

Verified with:

`python -m unittest tests.test_domain_detection tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker tests.test_visual_planner`

`powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

Updated 2026-04-29 03:41:

- Completed the first practical micro-conditioning pass:
  - SDXL workflows now use `CLIPTextEncodeSDXL` instead of the generic text encoder.
  - Added runtime placeholders for:
    - `__ORIGINAL_WIDTH__`
    - `__ORIGINAL_HEIGHT__`
    - `__TARGET_WIDTH__`
    - `__TARGET_HEIGHT__`
    - `__CROP_W__`
    - `__CROP_H__`
  - Added profile-level micro-conditioning defaults with zero crop.
  - Manual workflow payloads, prompt suggestions, batch queue items, and worker execution now carry the micro-conditioning values end to end.
- Current policy is conservative:
  - Default crop is `(0,0)`.
  - Original and target sizes default to the requested render dimensions unless explicitly overridden.
  - No experimental non-zero crop presets are enabled yet.

Verified with:

`python -m unittest tests.test_domain_detection tests.test_prompt_compiler tests.test_prompt_quality tests.test_image_prompting tests.test_candidate_selection tests.test_comfyui_workflows tests.test_visual_brief tests.test_comfyui_routes tests.test_image_worker tests.test_visual_planner`

`powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

Updated 2026-04-29 04:18:

- Completed the first opt-in IPAdapter style-reference slice:
  - Added `app/services/comfyui_capabilities.py` to detect local readiness from:
    - `custom_nodes/*ipadapter*`
    - `models/ipadapter/*`
    - `models/clip_vision/*`
  - Added model-registry visibility for `comfyui_ipadapter_style_reference`.
  - Added named generation profile `sdxl_style_reference` with:
    - workflow `txt2img_sdxl_ipadapter_style`
    - sampler `dpmpp_2m`
    - scheduler `karras`
    - steps `28`
    - cfg `5.6`
    - `requires_ipadapter=True`
    - conservative `seed_policy=fixed`
  - Added `txt2img_sdxl_ipadapter_style.json`.
  - Added manual and batch payload support for:
    - `style_reference_image`
    - `style_reference_strength`
  - Added route-side validation:
    - fail fast when IPAdapter prerequisites are missing
    - require a valid reference image path
    - reject LoRA + style-reference combination for now
  - Worker execution now forwards:
    - `__STYLE_REFERENCE_IMAGE__`
    - `__STYLE_REFERENCE_STRENGTH__`
- Current policy remains conservative:
  - style reference is opt-in only
  - no silent switch from standard SDXL to IPAdapter
  - no LoRA blending in this first pass

Verified with:

`python -m unittest tests.test_model_registry tests.test_comfyui_workflows tests.test_comfyui_routes tests.test_image_worker`

`powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`

Updated 2026-04-29 05:02:

- Completed the first usability pass for style reference:
  - Step 2 now exposes:
    - `generation_profile`
    - `seed_policy`
    - `style_reference_image`
    - `style_reference_strength`
  - Added an automatic reference-image selection policy:
    - project thumbnail first
    - then first uploaded image media
    - then first generated image mapping
  - Style-reference UI now pre-fills sensible defaults when the style-reference profile is selected.
  - Batch image generation can now send explicit seed-policy values from the UI.
- Current scope:
  - backend opt-in path is implemented
  - UI path is implemented
  - reference auto-selection is implemented
  - LoRA + style-reference mixed workflow still remained pending at this stage

Updated 2026-04-29 05:38:

- Completed the first mixed `LoRA + IPAdapter style-reference` workflow:
  - Added `txt2img_sdxl_ipadapter_style_lora.json`
  - Route-level profile resolution now supports:
    - standard style reference
    - style reference + LoRA
  - Batch-auto template resolution now follows the same mixed-template logic as manual workflow render/submit.
- Current result:
  - `sdxl_style_reference` can now run with or without LoRA
  - style-reference backend and Step 2 UI are aligned
  - mixed-template support is no longer a remaining blocker

Updated 2026-04-29 06:02:

- Completed the first `cross-scene style consistency scoring` slice:
  - candidate reviews now record adjacent-scene style consistency using text/profile metadata
  - stored fields now include:
    - `style_consistency_score`
    - `style_consistency_version`
    - `style_consistency_reason`
    - `style_consistency_components`
  - current V1 inputs are:
    - generation profile match
    - template match
    - style-reference image match
    - LoRA match
    - aspect-ratio match
- This is intentionally metadata-based, not vision-model-based. It gives the autopilot a cheap first-pass signal before adding CLIP/VLM QA later.

Updated 2026-04-29 06:28:

- Completed the first backend `ControlNet` slice:
  - added local readiness detection for ControlNet Depth
  - added model-registry visibility for `comfyui_controlnet_depth`
  - added named profile `sdxl_controlnet_depth`
  - added `txt2img_sdxl_controlnet_depth.json`
  - added route payload support for:
    - `control_image`
    - `control_strength`
  - added worker placeholder forwarding for:
    - `__CONTROL_IMAGE__`
    - `__CONTROL_STRENGTH__`
- Current scope:
  - backend opt-in only
  - Depth mode only
  - fail-fast when ControlNet prerequisites are missing
  - no Step 2 UI exposure yet

Updated 2026-04-29 06:54:

- Completed `vision QA V1`:
  - added `app/services/image_quality.py`
  - candidate import now analyzes the actual generated image file
  - candidate entries and candidate reviews now record:
    - `vision_qa_score`
    - `vision_qa_version`
    - `vision_qa_reason`
    - `vision_qa_issue_codes`
    - `vision_qa_components`
- Current V1 checks are low-cost and file-based:
  - resolution
  - entropy
  - contrast
  - edge detail
  - exposure extremes
  - near-duplicate previous scene image
- Candidate score now blends:
  - existing text/prompt score
  - lightweight image QA score

## 1. Current Diagnosis

The current pipeline already has useful building blocks: `visual_planner.py` extracts richer visual intent, `prompt_compiler.py` compiles domain prompts, `prompt_quality.py` catches several obvious failures, and `comfyui_pipeline.py` can generate and select candidate images.

The main gap is that ComfyUI and SDXL are still being used through a very basic fixed workflow. `txt2img_sdxl_basic.json` currently uses fixed KSampler values such as `euler`, `normal`, `20 steps`, and `cfg 7`, and the template has no first-class concept of quality mode, VRAM profile, sampler policy, Tiled VAE, IPAdapter, ControlNet, or candidate QA.

The second gap is prompt structure. The code has improved since the earlier failures, but the prompt compiler still does not consistently force SDXL-friendly slots such as subject, action, environment, framing, lighting, camera, and forbidden objects. This is why generic symbols can still dominate: cars for journeys, roads for direction, blank modern rooms for abstract emotion, books with fake text for reflection, or close-up body parts when the sentence needed a broader scene.

The third gap is verification. Current candidate scoring is mostly prompt and metadata based. It can reject some obvious text-level problems, but it does not yet confirm whether the generated image actually contains or avoids the expected visual objects. Historical candidate manifests may also mix score scales, so scoring needs a versioned 0-1 format before it becomes reliable as an autopilot decision signal.

## 2. Principles From The Documents

1. Context first, not keyword first.
   The image should represent the sentence meaning or core metaphor, not merely the most obvious noun. For example, a sentence about "direction" should not default to a car, road, compass, or map unless the planner explicitly allows those objects.

2. Use sentence type routing.
   Concrete sentences should prefer literal physical scenes. Abstract sentences should use LLM-generated visual analogues. Similes should be decomposed into source, target, and meaning, then visualized according to the intended meaning.

3. Compile prompts as slots.
   SDXL behaves better when the prompt contains clear slots: subject, action, environment, framing, lighting, atmosphere, style, camera, and technical quality anchors.

4. Use strong negative prompts.
   The documents repeatedly warn against generic drift objects and SDXL artifacts: cars, compass, maps, checklists, clipboards, clocks, trophies, readable text, watermarks, cropped limbs, hand-only closeups, fake writing, plastic skin, generic stock-photo composition, and 3D-render drift.

5. Separate fast mode from high-quality mode.
   An 8GB VRAM environment should not always run heavy multi-candidate or ControlNet/IPAdapter workflows. Quality modes need to be explicit.

6. Add QA in layers.
   V1 should use cheap text-based checks. V2 can add CLIP or aesthetic scoring. V3 can add lightweight VLM checks such as Moondream or Florence-2, but only as opt-in because GPU memory and runtime are real constraints.

## 3. Target Architecture

Add an image generation profile layer between visual planning and ComfyUI execution.

Recommended profile fields:

- `profile_name`: `sdxl_standard`, `sdxl_low_vram_lightning`, `sdxl_style_reference`, `sdxl_controlnet`, `flux_high_quality`
- `workflow_template`: ComfyUI template filename
- `model_family`: `sdxl`, `sdxl_lightning`, `flux`
- `sampler_name`, `scheduler`, `steps`, `cfg`, `denoise`
- `width`, `height`
- `vae_mode`: `standard` or `tiled`
- `style_reference_enabled`
- `control_mode`: `none`, `depth`, `canny`, `openpose`
- `variants_per_scene`
- `qa_mode`: `text`, `clip`, `vlm`
- `request_timeout_sec`
- `seed_policy`: `fixed`, `spaced`, `random`, or `variant_random`
- `micro_conditioning`: optional SDXL `original_size`, `target_size`, and `crop_coords_top_left`

The planner should continue to own semantic interpretation. The compiler should own SDXL prompt syntax. ComfyUI templates should only execute the selected profile.

## 4. P0 Implementation Plan

P0 avoids new custom-node dependencies and focuses on fixes that can be implemented with the current SDXL template style.

### Phase 1. Workflow Profile Plumbing

This phase now comes first because it is the smallest change with the largest immediate effect.

Update `app/workflow_templates/comfyui/txt2img_sdxl_basic.json` and the worker/router payload path so KSampler values are not hardcoded.

Add placeholders:

- `__STEPS__`
- `__CFG__`
- `__SAMPLER__`
- `__SCHEDULER__`
- `__DENOISE__`

Wire these through:

- `app/routers/image_gen.py`
- `app/workers/image_worker.py`
- `app/services/comfyui_workflows.py`
- `app/services/image_prompting.py`

Default `sdxl_standard` profile:

- Sampler: `dpmpp_2m`
- Scheduler: `karras`
- Steps: `30`
- CFG: `5.5` to `6.0`
- Denoise: `1.0`

Add `request_timeout_sec` to the profile or ComfyUI client config. A 30-step SDXL job can exceed a 30 second submit or history wait path depending on server state and queue load.

Acceptance for this phase:

- `quality_mode` changes actual KSampler parameters.
- The image manifest records profile, sampler, scheduler, steps, cfg, and denoise.
- Existing basic workflow still runs when no profile is supplied.

### Phase 2. Fallback Safety And Utility Cleanup

Prevent planner failures from producing generic checklist imagery.

Update `visual_brief.py` fallback behavior:

- Replace the default non-tech `large checklist with three bold check marks` with a neutral environment/object fallback.
- Prefer context-neutral physical anchors such as `quiet interior with a single everyday object`, `empty path through soft natural light`, or `person interacting with a simple real-world object`, depending on the sentence type.
- Keep tech fallback separate.

Add small cleanup tasks while touching the image path:

- Consolidate repeated `_is_tech_domain()` logic into one helper.
- Consolidate repeated `_as_int()` / `_to_int()` parsing helpers used by image router, worker, and pipeline.
- Keep these as small support refactors only; do not block the profile plumbing on broad cleanup.

### Phase 3. SDXL Slot Prompt Compiler

Update `app/services/prompt_compiler.py` so every essay/image prompt is built from explicit slots:

- Subject: specific noun or visible scene anchor
- Action/state: what is happening
- Environment: where it happens
- Framing: wide shot, medium shot, over-the-shoulder, top-down, etc.
- Lighting/atmosphere: morning light, quiet interior, overcast street, etc.
- Style: cinematic editorial still, realistic photography, documentary still
- Camera/technical: 35mm lens, sharp focus, natural color, detailed textures
- Forbidden: objects and compositions that must not appear

Important policy changes:

- Do not pass raw Korean abstract phrases as visual targets.
- For essay scenes, require an English visible object or scene anchor.
- For book/notebook scenes, prefer `blank notebook`, `closed book`, or `pages without readable text`; add negative text policy.
- For similes such as "running on sand", allow literal visualization when it makes sense: a person actually running on sand is better than a generic symbolic room.

Add SDXL technical anchors:

- Natural color
- Sharp focus
- 35mm or 50mm lens
- Documentary/editorial photography
- Detailed real-world textures
- Wide or medium shot unless close-up is explicitly required

Track CLIP-G / CLIP-L as a future extension. P0 should emulate separation with clean prompt slot ordering, while P2 can introduce an advanced ComfyUI workflow that uses separate global and local text encoders if the required nodes are available.

### Phase 4. Generic Drift Object Policy

Expand the forbidden object system in `storage/visual_vocab/essay.json` and the compiler.

Default global avoid list:

- car, automobile, truck, bus, road trip vehicle
- compass, map, signpost
- checklist, clipboard, magnifying glass
- clock, calendar
- trophy, medal
- graph, chart, coins, seedling
- readable text, letters, watermark, signature
- hand-only closeup, phone-only closeup, cropped limbs

Add an `allow_objects` escape hatch so these objects can appear only when the visual planner explicitly marks them as literal and necessary.

### Phase 5. Prompt Quality Gates

Extend `app/services/prompt_quality.py` with issue codes:

- `RAW_TEXT_VISUAL_TARGET`: raw Korean or abstract sentence text leaked into the visual target
- `GENERIC_SYMBOL_WITHOUT_ALLOW`: car, compass, map, checklist, graph, etc. used without explicit allow
- `BOOK_TEXT_RISK`: book/notebook scene lacks no-readable-text controls
- `MISSING_SUBJECT_SLOT`
- `MISSING_ENVIRONMENT_SLOT`
- `MISSING_FRAMING_SLOT`
- `CLOSEUP_RISK`: hand-only, phone-only, cropped limb, or extreme macro risk

Autopilot should retry prompt compilation before image generation when these fail.

### Phase 6. Candidate Score Normalization

Normalize candidate scoring in `app/services/comfyui_pipeline.py`.

Requirements:

- Candidate scores must be clamped to 0-1.
- The manifest must include `score_version`.
- The score must expose components such as prompt compliance, forbidden-object penalty, required-anchor coverage, repetition penalty, and file sanity.
- Avoid using raw file size as a dominant quality proxy. If retained, it should be a tiny sanity component only.

### Phase 7. Tests

Add or update tests for:

- Slot prompt compilation
- Essay negative prompt policy
- Generic object blocking and `allow_objects`
- Book/no-readable-text handling
- Workflow placeholder substitution
- SDXL standard profile values
- Candidate manifest records `profile_name`, sampler, scheduler, steps, cfg, and score version
- `quality_mode` affects the actual workflow payload
- Fallback brief no longer emits checklist as a generic default
- Candidate score is clamped to 0-1

## 5. P1 Implementation Plan

P1 adds quality modes and better candidate selection, but still avoids forcing heavy custom-node workflows on every run.

### Phase 6. Low-VRAM SDXL Lightning Profile

Add an optional `sdxl_low_vram_lightning` profile:

- Workflow: `txt2img_sdxl_lightning.json`
- Sampler: `euler` or `dpmpp_2m`
- Scheduler: `sgm_uniform` or profile-specific supported scheduler
- Steps: `4` to `8`
- CFG: `1.5` to `3.0`
- Tiled VAE if available

This should be opt-in or automatically selected only when the configured checkpoint exists.

Before selecting this profile, validate checkpoint compatibility. A Lightning checkpoint with standard 30-step SDXL settings can look wrong, and a normal SDXL checkpoint with Lightning settings can also degrade quality.

### Phase 7. Candidate Scoring V2

After P0 normalization, add stronger candidate reranking.

Suggested score components:

- Prompt compliance text score
- Forbidden object penalty
- Required visual anchor coverage
- Repetition penalty across adjacent scenes
- Optional file/image sanity checks

Retry policy:

1. Seed reroll
2. Prompt mutation emphasizing `must_show`
3. Fallback to environment/object scene if people or hands keep failing

The manifest should record `score_version`, `score_components`, and `retry_reason`.

### Phase 7.5. Seed Policy

Improve seed handling for variants.

Current linear seed offsets can produce overly similar candidates. Add profile-level seed policy:

- `fixed`: deterministic repeatability
- `spaced`: deterministic but separated by a large offset
- `random`: random seed per scene
- `variant_random`: fixed scene seed with random candidate variants

For candidate generation, prefer `spaced` or `variant_random` over simple `seed_base + variant_index`.

### Phase 7.6. SDXL Micro-Conditioning

Track SDXL micro-conditioning support:

- `original_size`
- `target_size`
- `crop_coords_top_left=(0,0)`

This is important for reducing unwanted closeups, cropping, and composition drift. It may require a more advanced ComfyUI SDXL node graph, so keep it P1 unless the current template can support it cleanly.

### Phase 8. Style Reference Profile

Add optional IPAdapter-style reference support only after confirming the required ComfyUI custom nodes are installed.

Use cases:

- Essay visual consistency
- Abstract scenes
- Maintaining a coherent photographic style without forcing the same character into every scene

This should be project-level opt-in: `style_reference_image` plus `style_reference_strength`.

Status 2026-04-29: first pass completed.

- Done:
  - local readiness detection for custom nodes, IPAdapter weights, and CLIP-Vision weights
  - opt-in profile and dedicated workflow template
  - manual and batch route plumbing
  - worker placeholder forwarding
  - fail-fast validation when prerequisites are missing
- Not done yet:
  - richer manual image picker UI for choosing among uploaded/generated reference images
  - vision-based style consistency scoring
  - ControlNet UI exposure
  - additional ControlNet modes such as Canny/OpenPose
  - CLIP/VLM semantic relevance QA

### Phase 9. Model Inventory And Profile Selection

Add a small local inventory check for ComfyUI checkpoints and custom nodes.

Recommended mapping:

- 8GB VRAM: SDXL Lightning or reduced SDXL standard, Tiled VAE, fewer variants
- 12GB VRAM: RealVisXL or Juggernaut XL standard SDXL, 1-2 LoRAs
- 16GB+ VRAM: Flux/advanced profile, IPAdapter, higher resolution, more variants

The UI or autopilot config should expose `quality_mode`: `fast`, `balanced`, `quality`, `exhaustive`.

The profile selector should also check GPU constraints through `gpu_guard.py` where possible. If a profile requires more VRAM than is available, it should downgrade or fail early with a clear reason.

## 6. P2 Implementation Plan

P2 requires custom nodes or heavier local models, so it should come after P0/P1 are stable.

### Phase 10. ControlNet Templates

Add separate workflow templates:

- `sdxl_controlnet_depth`: object and environment composition
- `sdxl_controlnet_canny`: structure-preserving scenes
- `sdxl_controlnet_openpose`: person-centered scenes

Use ControlNet only when the planner says composition is critical. Do not use it for every essay sentence.

### Phase 10.5. Dual Text Encoder Workflow

Add an advanced SDXL workflow that can use the dual text encoder strategy described in `sdxl.txt`.

Target behavior:

- CLIP-G or equivalent global prompt path: layout, composition, lighting, atmosphere, style
- CLIP-L or equivalent local prompt path: subject, object details, physical attributes, action

This should be experimental until the exact ComfyUI nodes are confirmed locally.

### Phase 11. Vision QA

Add optional post-generation QA:

- Lightweight VLM checks for forbidden objects
- CLIP score for text-image relevance
- Aesthetic predictor for low-quality filtering

Because this can add major runtime and VRAM pressure, run it as an opt-in second pass or only for key scenes.

### Phase 12. Upscale And Refiner

Add high-quality finishing only after prompt relevance is solved:

- Tiled upscale
- SDXL refiner or dedicated upscaler
- Flux profile for high-end environments

Do not prioritize upscaling before object relevance and prompt compliance are reliable.

## 7. Acceptance Criteria

P0 is complete when:

- Essay prompts contain explicit subject, action, environment, framing, lighting/style, and camera/technical slots.
- Default negative prompts include text, framing, artifact, and generic drift object controls.
- Cars, compasses, maps, checklists, clocks, graphs, and trophies do not appear unless explicitly allowed.
- Book and notebook scenes avoid readable fake text.
- ComfyUI workflow manifests record sampler, scheduler, steps, cfg, profile, and score version.
- Prompt quality gates can block or retry bad prompts before image generation.
- Existing 1-2 minute test video generation completes with duration guard passing.

P1 is complete when:

- `fast`, `balanced`, and `quality` image profiles are selectable.
- Candidate scores use a normalized 0-1 scale.
- Failed candidates trigger seed reroll or prompt mutation before accepting weak images.
- Style reference can be enabled without breaking non-style-reference runs.

Current status 2026-04-29:

- Runtime profile paths now exist for `fast`, `balanced`, `exhaustive`, `sdxl_low_vram_lightning`, and `sdxl_style_reference`.
- Style reference is now available through both backend and Step 2 UI, but it still lacks mixed-template support and cross-scene consistency scoring.
- Style reference is now available through both backend and Step 2 UI, including LoRA mixing, but it still lacks cross-scene consistency scoring.
- Style reference is now available through both backend and Step 2 UI, including LoRA mixing, candidate reviews include metadata-based adjacent-scene consistency scoring, ControlNet Depth is available as a backend opt-in path, and generated images now pass through lightweight file-based vision QA.

P2 is complete when:

- ControlNet templates are available and selected only for suitable scene types.
- Vision QA can catch forbidden objects or missing anchors.
- High-quality upscale/refiner flow is optional and profile-driven.

## 8. Risks And Guardrails

- Strong negative prompts can suppress legitimate objects. Use `allow_objects` for literal scenes.
- IPAdapter and ControlNet depend on ComfyUI custom nodes. Never assume they are installed.
- More candidates increase runtime and GPU pressure. Keep `variants_per_scene=1` in fast mode.
- Vision QA can compete with OmniVoice and ComfyUI for VRAM. Run it as a separate optional phase.
- Lightning settings are checkpoint-specific. Do not use Lightning CFG/steps with a normal SDXL checkpoint.
- Fake text is common in SDXL. For books, documents, phones, posters, and screens, default to blank or unreadable surfaces.
- Ollama readiness checks can be too short during cold model load. If visual planning falls back too often, image quality will regress even if ComfyUI settings are improved.
- ComfyUI request and queue timeouts must scale with heavier profiles.
- GPU guard and profile selection can disagree unless profile VRAM expectations are explicit.

## 9. Suggested Execution Order

1. P0 Phase 1: workflow parameter placeholders, profile plumbing, and `quality_mode` connection
2. P0 Phase 2: fallback safety and small shared-helper cleanup
3. P0 Phase 3: slot-based SDXL prompt compiler
4. P0 Phase 4: global avoid and allow-object policy
5. P0 Phase 5: prompt quality gate expansion
6. P0 Phase 6: candidate score normalization and `score_version`
7. P0 Phase 7: tests
8. P1 Phase 6: low-VRAM Lightning profile, only if checkpoint exists
9. P1 Phase 7: stronger candidate reranking and retry
10. P1 Phase 7.5: seed policy
11. P1 Phase 7.6: SDXL micro-conditioning
12. P1 Phase 8: IPAdapter style reference, only if custom nodes exist
13. P2 ControlNet, dual text encoder workflow, VLM QA, upscale/refiner

## 10. Primary Files To Change

- `app/services/prompt_compiler.py`
- `app/services/image_prompting.py`
- `app/services/prompt_quality.py`
- `app/services/comfyui_pipeline.py`
- `app/services/comfyui_workflows.py`
- `app/services/comfyui_client.py`
- `app/services/visual_brief.py`
- `app/routers/image_gen.py`
- `app/workers/image_worker.py`
- `app/workflow_templates/comfyui/txt2img_sdxl_basic.json`
- `storage/visual_vocab/essay.json`
- `tests/test_prompt_compiler.py`
- `tests/test_prompt_quality.py`
- `tests/test_comfyui_workflows.py`
- `tests/test_comfyui_pipeline.py`
- `tests/test_image_worker.py`
- `tests/test_comfyui_routes.py`

Potential new files:

- `app/services/image_generation_profiles.py`
- `app/services/prompt_slots.py`
- `app/services/domain_detection.py`
- `app/services/parse_utils.py`
- `app/workflow_templates/comfyui/txt2img_sdxl_lightning.json`

## 11. Quick Wins From Review

These can be implemented before the full prompt-slot refactor:

1. Replace hardcoded KSampler values in `txt2img_sdxl_basic.json` with placeholders.
2. Pass profile values from `quality_mode` to `image_worker.py` and the ComfyUI workflow renderer.
3. Change the non-tech fallback prop away from checklist imagery.
4. Clamp candidate scores to 0-1 and write `score_version`.
5. Increase or profile-control ComfyUI request timeout for heavier SDXL jobs.
6. Space or randomize candidate variant seeds instead of simple adjacent increments.

## 12. 2026-04-29 Final UI Pass

Completed:

- Step 2 now exposes `sdxl_controlnet_depth`.
- Manual and batch image generation can submit `control_image` and `control_strength`.
- Style/control reference inputs reuse a shared image picker fed by thumbnail, uploaded media, and generated mappings.
- Generated mapping cards now surface candidate score, vision QA, style consistency, and QA summary reason.

Current status:

- Core backend roadmap items are complete.
- Remaining items are optional upgrades rather than blockers:
  - richer semantic QA with CLIP/VLM
  - extra ControlNet modes like Canny/OpenPose
  - deeper visual style consistency using image embeddings
