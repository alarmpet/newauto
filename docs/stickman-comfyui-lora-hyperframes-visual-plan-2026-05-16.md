# Stickman Explainer Visual Generation Plan

Date: 2026-05-16

Goal: reproduce the attached business/AI explainer image style with a reliable pipeline that combines ComfyUI, a dedicated LoRA, deterministic prompt planning, and HyperFrames editorial motion overlays.

## Review Validation Update

Review source: `docs/stickman-lora-hyperframes-plan-review-2026-05-16.md`.

Status: accepted with corrections. The review file is partially mojibake, but its core engineering claims were checked against the current codebase.

Implementation progress:

- 2026-05-16: started Phase 1A/1B implementation.
- Added `stickman_business` style preset acceptance in project feature settings.
- Added three existing-LoRA business templates:
  - `machine_pipeline`
  - `infrastructure_bottleneck`
  - `scale_comparison`
- Routed `stickman_business` prompts through the existing `txt2img_sdxl_stickman_lora` path instead of creating a new LoRA route.
- Added first HyperFrames `label_plate` overlay item support while preserving `lower_third_keyword`.
- Added focused tests for prompt routing, feature-setting persistence, and label-plate overlay rendering.
- Added Phase 0 evidence bundle generation:
  - service: `app/services/stickman_evidence.py`
  - script: `scripts/build_stickman_business_evidence.py`
  - outputs: `prompts_lora_on.json`, `prompts_lora_off.json`, `frame_reviews.json`
- Diagnostics manifest now lists `stickman_evidence_files`.
- Smoke evidence bundle generated at `storage/projects/ce308c6cf835/diagnostics_bundle/stickman_evidence`.
- Generated real ComfyUI evidence project:
  - project: `storage/projects/5cdc8ccb0c24`
  - evidence: `storage/projects/5cdc8ccb0c24/diagnostics_bundle/stickman_evidence`
  - contact sheet: `comparison_contact_sheet.jpg`
  - LoRA-on images: recognizable suited stickmen, but weak business diagram/metaphor layout.
  - LoRA-off images: more generic diagram mood, but loses the round-head business character identity.
- Added deterministic layout-sketch generation:
  - service: `app/services/stickman_layout_sketch.py`
  - script: `scripts/build_stickman_layout_sketches.py`
  - outputs: `layout_sketches/*_layout_sketch.png`
  - purpose: provide composition guide images for the next ControlNet/lineart/scribble trial.

Validated existing capabilities:

- Stickfigures LoRA discovery already exists in `app/services/model_registry.py` through `_find_stickfigures_lora()`.
- Current trigger vocabulary is `Stick figure` / `Flipchartvisu`, not `na_stickbiz_style`.
- A Stickfigures SDXL LoRA workflow already exists at `app/workflow_templates/comfyui/txt2img_sdxl_stickman_lora.json`.
- The existing stickman prompt library already exists at `app/services/stickman_reference_library.py`, but it is generic/biblical/story oriented rather than business explainer oriented.
- Autopilot already contains stickman LoRA routing and blocking logic in `app/services/autopilot.py`, including fallback to basic SDXL when stickman LoRA is inappropriate.
- HyperFrames overlay support already exists, but the current production template is effectively `lower_third_keyword`; the proposed diagram/label overlay pack is new work.
- HyperFrames alpha MOV fallback and render-report fields already exist, so the plan should build on that path instead of designing a second overlay renderer from scratch.

Accepted review corrections:

- Do not start by training a new LoRA. First run an evidence bundle using the existing Stickfigures LoRA and prompt/template improvements.
- Do not introduce `na_stickbiz_style` as the first implementation trigger. Treat it as a future custom-LoRA trigger only after evidence shows the existing Stickfigures LoRA is insufficient.
- Add business explainer templates to the existing stickman/template path before creating a separate style system.
- Expand HyperFrames incrementally: `label_plate` first, then arrows/charts/money/network effects.
- Add TDD-style acceptance tests before broad implementation.
- Add a Phase 0 diagnostic/evidence step before the manual golden pipeline.
- Keep ControlNet/Scribble as opt-in. Existing code only verifies ControlNet Depth readiness; lineart/scribble workflows need capability checks before becoming a required path.

Evidence-based correction after the first real ComfyUI run:

- Existing Stickfigures LoRA alone is not sufficient for the target reference style.
- It should still remain in the pipeline because it preserves the suited stickman identity better than the base model.
- The next validation should add deterministic layout sketches and HyperFrames labels before deciding on custom LoRA training.
- Custom LoRA is still conditional: train only if layout-conditioned generation plus overlays cannot reach the reference style.

Rejected or deferred review suggestions:

- A full rewrite of `hyperframes_overlay.py` is deferred. The near-term change should extend the current overlay plan schema without breaking the working lower-third path.
- A brand-new LoRA dataset/training pipeline remains Phase 4+, conditional on existing-LoRA evidence.
- Automatic blank-label coordinate detection is deferred. The first version should use planned/template coordinates, because reliable CV detection is a separate hard problem.

## Target Style Summary

The reference images are not generic "cartoon illustrations." They are a very specific YouTube explainer visual language:

- Simple stickman business characters with round white heads, minimal facial expressions, navy suits, red ties, and clean black outlines.
- Flat editorial metaphors: castles, factories, roads, scales, pipes, cloud signs, charts, money streams, data centers, AI buildings, and network graphs.
- Muted beige/gray background, low saturation, soft shadows, and very controlled accent colors.
- Thick readable line art, almost no texture, no photorealism, no cinematic depth, no painterly lighting.
- Korean or English labels embedded inside the image as diagram labels, but with a high risk of AI text errors.
- Video presentation relies on black subtitle bars at the bottom and sometimes YouTube controls in screenshots, but those controls are not part of the desired generated image.

This style is best treated as an "editorial metaphor diagram" generator, not a scene illustration generator.

## Screenshot Analysis

### Image 1: Meta Strategy Machine

Visual structure:

- Central mechanical pipeline/factory machine.
- Top sign reads "메타 전략."
- Left chamber shows gears and cash flow, labeled as ad revenue engine.
- Right chamber shows glowing network nodes, labeled developer ecosystem/standardization engine.
- Output on the far right expands into a connected developer/network ecosystem.
- Red upward arrow on the left communicates growth.

Style traits:

- Strong black outlines with gray-blue machinery.
- Beige flat background.
- Money bills and glowing network dots are the only busy elements.
- The metaphor is extremely concrete: "strategy" becomes a machine with input/output engines.

Production note:

- ComfyUI can generate the machine and stick-diagram layout.
- HyperFrames should generate Korean labels, arrows, glow dots, and subtitle bars because native diffusion text will be unreliable.

### Image 2: Building vs Crumbling Moat

Visual structure:

- Split-screen before/after comparison.
- Left: clean castle with water moat, workers building brick wall, smiling business figures.
- Right: cracked castle, broken bridge, distressed figures, muddy/desaturated scene.

Style traits:

- Vertical divider creates a clear contrast frame.
- Small workers and props communicate "defense/business moat."
- Right side is intentionally less saturated and more broken.

Production note:

- This should be a reusable `split_comparison` scene template.
- ComfyUI should draw two sides but HyperFrames can add a dividing line, side labels, and subtle before/after highlight.

### Image 3: Market Outperformance and AI Cash Machine

Visual structure:

- Business stickman holds stacks of cash.
- Chart on left shows ROIC and market outperformance arrows.
- Glass building on right receives flowing money and gold bars.
- AI symbol appears on building facade.

Style traits:

- One smiling figure at center-left.
- High-level financial concept represented by simple chart plus money stream.
- Blue glass building is stylized, not realistic.

Production note:

- Good LoRA training sample because it combines character, chart, money, building, and label-like shapes.
- HyperFrames should draw chart labels and animated money arrows for video.

### Image 4: Low Efficiency / Low Valuation Factory

Visual structure:

- Old cracked factory with sign "LOW EFFICIENCY."
- Hanging tag says "LOW VALUATION."
- Stickman inspects a small glowing plant with a magnifying glass.
- Background has abandoned industrial buildings.

Style traits:

- More narrative than diagrammatic.
- Muted industrial palette.
- The green glowing plant is the key visual contrast.

Production note:

- The prompt planner must preserve the core metaphor: distressed asset + close inspection + hidden value.
- HyperFrames can add clean Korean labels instead of relying on English signs.

### Image 5: Microsoft Strategic Crossroads

Visual structure:

- Microsoft logo in center.
- Copilot icon on left, Azure cloud on right.
- Large green and red arrows point inward/outward.
- Question mark above center.
- Thinking business figures around the scene.
- Road/path converges toward center.

Style traits:

- Balanced symmetric composition.
- Concept map, not a literal office scene.
- Brand-like logos appear, but generated versions may be legally/visually inconsistent.

Production note:

- For real production, use "four-color square logo-like tile" or deterministic vector overlay for brand labels.
- HyperFrames should own logo-like labels, arrows, question mark, and Korean captions.

### Image 6: AI Empire vs Platform Empire / Meta Money

Visual structure:

- Left half: uncertain stickman at road fork with signs "AI Empire" and "Platform Empire."
- Right half: confident stickman carrying a money bag labeled Meta money, while pointing hands and judging eyes surround him.

Style traits:

- Split narrative in one frame.
- Same character in different emotional states.
- Simple eyes/fingers symbolize public scrutiny.

Production note:

- Needs character consistency across split panels.
- LoRA must learn round head + suit body proportions.
- HyperFrames can animate sign arrows, pointing hands, and judgment eyes with small motions.

### Image 7: Power Grid Bottleneck

Visual structure:

- Electric grid lines from left enter a funnel/bottleneck.
- Output sparks and smoke as it approaches AI data center on right.
- Worried stickman in foreground.

Style traits:

- Excellent example of a single strong metaphor.
- Fewer labels, more shape logic.
- Thick cable lines and simple smoke/spark icons.

Production note:

- This is a high-priority template: `infrastructure_bottleneck`.
- ComfyUI draws base scene; HyperFrames can animate sparks and line pulses.

### Image 8: Copilot vs Competition Scale

Visual structure:

- Two stickmen sit on opposite sides of a balance scale.
- Left label: Copilot. Right label: competition model.
- Different amounts of glowing blue blocks represent value/capability.

Style traits:

- Centered scale creates instantly readable comparison.
- Korean title labels are large and bold.
- Glow is subtle and symbolic.

Production note:

- Use a deterministic overlay for top labels.
- ComfyUI can generate scale and figures without text, then HyperFrames adds labels.

### Image 9: Cloud to CAPEX

Visual structure:

- Dim sign on left: cloud.
- Large arrow points right toward spotlighted sign "CAPEX."
- Coins and factory/building elements at far right.

Style traits:

- Stage-light metaphor.
- Very simple, with strong spatial hierarchy.
- The label is the image.

Production note:

- This is not worth asking diffusion to spell correctly.
- Generate blank signs with ComfyUI; render Korean/English labels using HyperFrames or Pillow.

### Image 10: Valuation/Efficiency Matrix

Visual structure:

- 2x2 quadrant chart.
- Top-right highlighted quadrant contains NVIDIA and an upward mini chart.
- Tooltip says "buy gradually during correction."
- Axes show valuation high/low.

Style traits:

- Diagram-first frame.
- Most value is in clean typography and layout.
- Diffusion image generation is the wrong tool for the chart itself.

Production note:

- Build this with HyperFrames/SVG/HTML directly, not ComfyUI.
- ComfyUI can supply only decorative background or small character cutouts if needed.

### Image 11: Copilot Subscription Price Tablet

Visual structure:

- Tablet or phone frame.
- Friendly robot at top.
- Large label: monthly 30 dollars.
- Upward chart below.

Style traits:

- Minimal centered layout.
- Device frame acts as the scene container.
- Robot is simple and friendly.

Production note:

- Hybrid approach: ComfyUI generates tablet + robot without text; HyperFrames inserts price and chart.

## Style DNA

### Composition

- 16:9 landscape.
- Main object centered or split into two clear panels.
- One metaphor per frame.
- Large empty beige/gray regions are acceptable.
- Foreground character often sits at lower-left or center.
- Background is shallow and flat, with no photoreal depth.
- Most frames use three zones:
  - metaphor object or machine
  - stickman character reaction
  - label/chart/arrow explanatory layer

### Character Design

- Round white head, black outline, no ears, no nose.
- Dot eyes or simple eyebrow expressions.
- Small mouth, usually one stroke.
- Navy suit, white shirt, red tie.
- Short simple hands, no detailed fingers except pointing hands in Image 6.
- Body proportions: head large, torso compact, legs short.
- Emotional range: smile, worry, suspicion, confidence, confusion.

### Line and Render Style

- Thick black outlines, roughly 3-6 px at 1280 width.
- Flat fills.
- Minimal gradients.
- Soft oval ground shadows.
- Consistent cartoon vector feel.
- No watercolor, no oil paint, no anime rendering, no 3D plastic toy look.

### Palette

- Background: warm gray/beige, roughly `#c9c1b2`, `#d7d4ca`, `#bfb9ad`.
- Line: near black `#111111` or dark slate.
- Suit: navy `#1f3f5f`.
- Accent red: arrows/ties `#ef3b2d`.
- Accent green: growth arrows/money `#6aa56a`.
- Accent blue: glass/cloud/AI `#88b7d7`.
- Warning: orange/yellow sparks and highlights.

### Text Treatment

- Large bold Korean labels are crucial.
- Diffusion-generated text is unacceptable for final output.
- Native image prompt should request "blank sign panels" or "empty label plates."
- HyperFrames or Pillow should render all final Korean text using Noto Sans KR or Pretendard.

### Motion Potential

- Arrows can slide or pulse.
- Money can flow through pipes.
- Network nodes can glow sequentially.
- Sparks can flicker.
- Chart lines can draw on.
- Split panels can wipe/reveal.
- Labels can pop in with small scale animation.

## Why Current Simple Generated Images Fail This Target

The earlier regenerated test video produced visible images, but those images were generic editorial cards. They lacked the reference style because:

- No trained stickman character identity.
- No concrete metaphor objects like castles, machines, scales, funnels, and charts.
- Typography and subtitles competed with scene content.
- HyperFrames was used only as a lower-third, not as a diagram/label layer.
- Prompting did not enforce "blank-sign plus deterministic label overlay" separation.

The fix is not just "better prompt." The system needs a style-specific visual planner and a two-layer image strategy.

## Evidence Bundle First

Before implementing new training or large template systems, collect a small evidence bundle from the current code path.

Evidence tasks:

- Generate 4-6 business explainer frames with the existing Stickfigures LoRA workflow.
- Generate the same prompts with LoRA disabled.
- Save prompt metadata, seed, workflow template id, LoRA name, and LoRA strength.
- Classify failures into:
  - wrong visual style
  - missing round-head business character
  - weak metaphor object
  - fake/gibberish text
  - cluttered layout
  - blank or generic card
  - subtitle/label collision risk
- Test whether blank signboards survive prompt-only generation.
- Test whether deterministic HyperFrames labels can land in pre-planned boxes on those frames.

Artifacts:

```text
storage/projects/<pid>/diagnostics_bundle/stickman_evidence/
  prompts.json
  lora_on/
  lora_off/
  frame_reviews.json
  overlay_box_reviews.json
```

Decision gate:

- If the existing Stickfigures LoRA can produce acceptable style in at least 60% of evidence prompts, improve prompts/templates first and defer custom LoRA training.
- If it cannot preserve the target business style or blank panels, start the custom LoRA dataset plan.

## Recommended Architecture

### Layer 1: ComfyUI Base Illustration

ComfyUI generates the no-text base frame:

- character poses
- machines/buildings/castles/roads/scales/funnels
- blank signboards
- blank chart boards
- empty labels
- money, gears, clouds, blocks, factories
- consistent stickman explainer art style

Output:

```text
storage/projects/<pid>/media/scene_000_base.png
storage/projects/<pid>/media/scene_001_base.png
```

### Layer 2: Deterministic Label and Diagram Overlay

HyperFrames generates:

- Korean labels
- English acronyms like CAPEX/ROIC only when needed
- chart axes and chart lines
- arrows
- tooltip boxes
- glow effects
- lower-third/source tags
- animated callouts

Output:

```text
storage/projects/<pid>/hyperframes_overlay/overlay.mov
```

Final render composites:

```text
base image/video + HyperFrames overlay + ASS narration subtitles
```

### Layer 3: Subtitle Discipline

For this visual style, subtitles must not cover the core diagram.

Rules:

- Use black bottom caption bar only.
- Prefer readable short subtitle chunks.
- Keep subtitle text under 1-2 lines.
- Reserve the center and upper regions for diagrams.
- If a frame has important bottom content, move subtitles to top or use a smaller bar.

## ComfyUI Strategy

### Base Model

Recommended starting points:

- SDXL or Pony/Illustrious-style checkpoint if local environment already supports it.
- Prefer a clean 2D illustration checkpoint over photoreal checkpoints.
- Avoid models that strongly produce anime, painterly fantasy, or 3D toy rendering.

Required workflow nodes:

- CheckpointLoaderSimple
- CLIPTextEncode positive/negative
- EmptyLatentImage at 1344x768 or 1536x864
- KSampler
- VAE Decode
- SaveImage
- Optional ControlNet
- Optional IP-Adapter/reference image conditioning
- Optional LoRA loader

### Resolution

Generate at:

- `1344x768` for fast iteration
- upscale/crop to `1920x1080` for final

Use 16:9 consistently. Avoid square generation.

### Prompt Template

Base positive prompt:

```text
flat vector cartoon explainer illustration, simple round white stickman business character, navy suit and red tie, thick black outlines, muted beige background, clean 2D line art, editorial business metaphor diagram, blank signboards, blank chart panels, simple geometric props, soft oval shadows, limited palette, high readability, youtube finance explainer style, no realistic texture
```

Scene-specific append:

```text
central mechanical strategy machine with two transparent chambers, gears in left chamber, glowing network nodes in right chamber, money flowing out, upward red arrow, blank title plate at top, blank label plates under chambers
```

Negative prompt:

```text
photorealistic, realistic human face, anime, manga, 3d render, glossy plastic, detailed skin, complex background, cinematic lighting, painterly, watercolor, oil painting, tiny unreadable text, gibberish text, distorted letters, clutter, horror, extra limbs, malformed hands, noisy texture, low contrast, cropped subject, black subtitle bar, youtube controls
```

### Prompt Contract

Every image prompt must declare:

- scene template type
- main metaphor object
- character count and emotion
- blank-label surfaces
- forbidden text
- overlay labels to be added later

Example structured prompt payload:

```json
{
  "template": "machine_pipeline",
  "metaphor": "AI strategy engine",
  "characters": [
    {"role": "business_stickman", "emotion": "confident", "position": "lower_left"}
  ],
  "props": ["gears", "money bills", "network nodes", "red growth arrow"],
  "blank_labels": [
    {"id": "title_plate", "position": "top_center"},
    {"id": "left_engine_label", "position": "bottom_left"},
    {"id": "right_engine_label", "position": "bottom_right"}
  ],
  "overlay_text": {
    "title_plate": "메타 전략",
    "left_engine_label": "광고 수익 엔진",
    "right_engine_label": "개발자 생태계 엔진"
  }
}
```

## LoRA Strategy

### Why LoRA Is Needed

Prompt-only generation will vary too much:

- character face shape changes
- suit proportions drift
- line thickness changes
- background palette drifts
- diagrams become too realistic or too messy
- repeated characters are inconsistent across scenes

A dedicated LoRA should teach:

- stickman business character identity
- flat vector explainer line art
- common metaphor props
- muted palette
- clean diagram composition
- blank sign/chart surfaces

### Dataset Requirements

Target dataset size:

- Minimum proof: 40-60 curated images.
- Useful LoRA: 120-250 images.
- Strong style LoRA: 300-600 images, including generated and hand-cleaned variants.

Dataset categories:

- 30% character-only or simple character scenes.
- 30% business metaphor scenes: money, factories, castles, roads, scales.
- 20% AI/cloud/data scenes: data centers, networks, robots, chips, cloud signs.
- 20% diagram/chart scenes: 2x2 matrices, arrows, tablet charts, split panels.

Important:

- Remove YouTube UI controls and black subtitle bars from training crops.
- Avoid training on screenshots with existing Korean subtitles at bottom.
- If labels are present in reference, either mask/blur them or caption as "blank signboard" only when training desired output.
- Use clean crops at original image area, not full video screenshot including player UI.

### Captioning

Use the existing trigger tokens while testing the current Stickfigures LoRA:

```text
Stick figure, Flipchartvisu
```

Use the custom trigger token only if a new dedicated business-explainer LoRA is trained:

```text
na_stickbiz_style
```

Caption examples:

```text
na_stickbiz_style, flat vector cartoon, round white stickman businessman in navy suit and red tie, worried expression, electric grid bottleneck funnel, AI data center, muted beige background, thick black outlines, blank label areas
```

```text
na_stickbiz_style, split screen business moat comparison, left side clean castle and workers building wall, right side cracked castle and distressed people, flat 2D line art, muted beige background, no readable text
```

Do not caption exact Korean text unless the training objective includes text, which is not recommended.

### Training Settings

Starting SDXL LoRA settings:

- Network rank: 16 or 32.
- Alpha: same as rank or half rank.
- Learning rate: `1e-4` for UNet, `5e-5` for text encoder if training TE.
- Batch size: as GPU allows.
- Resolution buckets: include 1024x576, 1152x648, 1344x768.
- Epoch target: enough for 2,000-6,000 total steps depending dataset size.
- Save every 250-500 steps.

Selection criteria:

- Best checkpoint is not the one with strongest style. It is the one that preserves clean layout and blank labels.
- Reject overfit checkpoints that reproduce exact screenshot compositions too often.
- Reject checkpoints that draw fake text into blank panels.

### LoRA Routing

Near-term route:

```text
visual_style = "stickman_business"
template_id = "txt2img_sdxl_stickman_lora"
lora_trigger = "Stick figure, Flipchartvisu"
```

Future custom-LoRA route, only if the evidence bundle proves the existing LoRA is insufficient:

```text
visual_style = "stickman_business_explainer"
```

When the existing route is selected:

- use the current Stickfigures LoRA discovered by model registry
- add business explainer prompt fragments from the new template library
- keep existing blocked-domain and `lora_policy = "none"` safeguards
- request blank label panels and no readable text
- force final text into HyperFrames overlays

When the future custom route is selected:

- apply `na_stickbiz_style` trigger
- load the stickman LoRA
- use diagram/metaphor prompt templates
- disable photoreal prompt fragments
- force deterministic text overlay mode

## ControlNet and Reference Conditioning

### ControlNet Line/Scribble

Best for:

- split panels
- machines
- chart/tablet layouts
- scales
- funnels
- roads

Generate a rough layout sketch from code:

- black outlines on white
- blank rectangles for signs
- circles for heads
- simple arrows

Then use ControlNet scribble/lineart to lock composition.

### IP-Adapter / Style Reference

Use the attached images as style references only if local rights and workflow allow it.

Best use:

- low to medium style strength
- combine 2-3 reference images by template category
- avoid forcing exact scene duplication

Do not rely on IP-Adapter alone for production consistency. It helps, but LoRA plus structured prompts is more stable.

### Segmentation Masks

For final quality:

- generate base illustration without text
- mask blank sign panels
- inpaint panel surfaces if text artifacts appear
- overlay crisp text later

## HyperFrames Strategy

HyperFrames should become the deterministic "diagram and label compositor."

Near-term constraint: the current working overlay path is `lower_third_keyword`. Extend it carefully rather than replacing it.

First schema extension:

```json
{
  "version": 2,
  "template": "stickman_explainer_overlay",
  "items": [
    {
      "overlay_type": "label_plate",
      "start": 0.0,
      "end": 4.0,
      "text": "CAPEX",
      "box": [1180, 210, 420, 160],
      "font_weight": 800,
      "fit": "shrink_to_box"
    }
  ]
}
```

Implementation rule:

- Keep `lower_third_keyword` rendering unchanged.
- Add `label_plate` as the first new overlay type.
- Add visual tests for auto-fit Korean text in fixed boxes.
- Add arrows/charts/money/network effects only after label placement is verified.

### Templates To Build

1. `label_plate`
   - Korean label inside a blank sign or machine plate.
   - Supports font size fitting and stroke/shadow.

2. `black_caption_bar`
   - YouTube-explainer style bottom caption band.
   - Must avoid player UI look.

3. `growth_arrow`
   - Red/green arrow with slight entrance and pulse.

4. `money_flow`
   - Repeating money icons moving through pipe or toward building.

5. `network_glow`
   - Dots and lines pulsing in sequence.

6. `split_compare_labels`
   - Left/right labels, divider, before/after tint.

7. `chart_draw`
   - ROIC/valuation line charts, axes, 2x2 matrix, highlighted quadrant.

8. `tooltip_callout`
   - Small rounded labels like "시장 조정 시 분할 매수."

9. `question_mark_glow`
   - Center uncertainty marker.

10. `spark_flicker`
    - Small warning sparks around grid/data-center scenes.

### Overlay Data Model

```json
{
  "composition": "stickman_explainer_overlay",
  "duration": 37.156,
  "scenes": [
    {
      "start": 0.0,
      "end": 10.551,
      "template": "machine_pipeline",
      "labels": [
        {"id": "title_plate", "text": "메타 전략", "box": [720, 60, 480, 110]},
        {"id": "left_engine", "text": "광고 수익 엔진", "box": [520, 760, 330, 90]},
        {"id": "right_engine", "text": "생태계 장악 엔진", "box": [1120, 760, 420, 90]}
      ],
      "effects": [
        {"type": "money_flow", "path": "left_pipe"},
        {"type": "network_glow", "target": "right_nodes"},
        {"type": "growth_arrow", "direction": "up_right"}
      ]
    }
  ]
}
```

### Text Rendering Rules

- Use bundled Korean font:
  - first choice: Noto Sans KR
  - second choice: Pretendard
  - fallback: Malgun Gothic
- Use auto-fit:
  - measure text
  - reduce font size until it fits
  - max 2 lines for diagram labels
- Never allow diffusion-generated labels as final labels.

## Scene Template Library

### `machine_pipeline`

Used for:

- platform strategy
- monetization engine
- ecosystem engine
- AI factory

Core objects:

- central machine
- pipes/tubes
- left chamber
- right chamber
- gears/money/network nodes
- top title plate

Overlay:

- chamber labels
- money flow
- network glow
- upward arrow

### `split_moat_comparison`

Used for:

- incumbent moat vs disruption
- current business vs future business
- protected castle vs crumbling castle

Core objects:

- vertical split
- left strong castle
- right cracked castle
- workers/defenders

Overlay:

- left/right headers
- divider wipe
- warning cracks emphasis

### `valuation_efficiency_matrix`

Used for:

- stock analysis
- valuation/efficiency explanation
- quadrant investing logic

Core objects:

- mostly deterministic chart
- optional character sticker

Overlay:

- chart entirely HyperFrames/SVG
- highlighted quadrant
- tooltip
- mini line chart

### `infrastructure_bottleneck`

Used for:

- power grid limit
- GPU supply limit
- compute bottleneck
- data center constraints

Core objects:

- left supply lines
- central funnel
- right AI building
- worried character

Overlay:

- line pulses
- sparks
- bottleneck label

### `strategic_crossroads`

Used for:

- Microsoft/Copilot/Azure style choice
- platform direction
- capital allocation

Core objects:

- center brand tile
- road split
- left/right symbols
- thinking characters

Overlay:

- arrows
- question mark
- labels

### `scale_comparison`

Used for:

- product comparison
- model comparison
- valuation comparison

Core objects:

- balance scale
- two characters
- stacked blocks or coins

Overlay:

- title labels
- glow on winning side
- numeric tags

### `spotlight_label`

Used for:

- CAPEX
- hidden cost
- key concept reveal

Core objects:

- left dim source
- right spotlighted sign
- arrow

Overlay:

- clean large text
- spotlight gradient
- coin fall

## NewAuto Implementation Plan

### Phase 0: Evidence Bundle and Current Path Audit

Use the existing Stickfigures LoRA, current ComfyUI workflow, and current HyperFrames overlay path before building new training infrastructure.

Tasks:

- Add three business explainer prompt templates to the existing stickman template library:
  - `machine_pipeline`
  - `infrastructure_bottleneck`
  - `scale_comparison`
- Run LoRA on/off prompt grids for 4-6 representative sentences.
- Save generated frames, prompts, seeds, workflow template ids, and LoRA settings.
- Record failures using the categories in `Evidence Bundle First`.
- Verify whether the current HyperFrames overlay can be extended without breaking `lower_third_keyword`.

Acceptance:

- Evidence bundle is saved under project diagnostics.
- Each generated frame is classified.
- The decision to train or defer a custom LoRA is backed by frame evidence, not assumption.

Tests to add first:

- `test_stickman_business_templates_are_registered()`
- `test_autopilot_keeps_existing_stickman_lora_safeguards_for_business_style()`
- `test_stickman_evidence_bundle_records_lora_on_off_metadata()`

### Phase 1A: Existing Stickfigures LoRA Business Template Trial

Improve the existing prompt route before introducing a new LoRA.

Tasks:

- Extend `app/services/stickman_reference_library.py` with business/metaphor templates.
- Route `stickman_business` style prompts through `txt2img_sdxl_stickman_lora` when model registry reports a Stickfigures LoRA.
- Keep `lora_policy = "none"` and blocked-domain safeguards.
- Strength-test LoRA values around `0.55`, `0.7`, and `0.85`.
- Prefer `1024x576` for compatibility, then test `1344x768` if the local workflow handles it.

Acceptance:

- At least 3 template prompts generate nonblank frames.
- Generated frames contain a round-head stickman or a clearly usable business diagram.
- Fake text is confined to blank panels that can be covered by HyperFrames.

Tests to add first:

- `test_business_stickman_prompt_uses_existing_trigger_words()`
- `test_business_stickman_prompt_requests_blank_label_panels()`
- `test_business_stickman_route_falls_back_when_lora_blocked()`

### Phase 1B: HyperFrames `label_plate` Overlay

Add one deterministic label overlay type before building the full diagram overlay pack.

Tasks:

- Extend `build_overlay_plan()` to accept explicit overlay items when supplied in `body_image_options` or a sidecar plan.
- Implement `overlay_type = "label_plate"` with `box`, `text`, `font_weight`, and auto-fit.
- Preserve the existing `lower_third_keyword` behavior.
- Render Korean text with the existing local Korean font copy path.
- Validate alpha MOV fallback remains intact.

Acceptance:

- A label plate renders inside a fixed box.
- Long Korean text shrinks or wraps instead of overflowing.
- Existing lower-third overlay tests continue to pass.
- Render report still records overlay status/path/pix_fmt.

Tests to add first:

- `test_hyperframes_label_plate_renders_korean_in_box()`
- `test_hyperframes_overlay_preserves_lower_third_items()`
- `test_hyperframes_label_plate_autofits_long_text()`

### Phase 2: Manual Golden Pipeline

Create one end-to-end manual project using the attached target style.

Tasks:

- Add or reuse the `stickman_business` visual style option.
- Create 4-6 prompt templates manually.
- Generate base images with ComfyUI using blank signs.
- Render Korean labels with HyperFrames.
- Produce a test video with real TTS and no beep fallback.
- Save frame samples at 2s, 8s, 14s, and final scene.

Acceptance:

- 4 scenes have visible metaphor images.
- No generated gibberish text is visible.
- Korean labels are crisp.
- Subtitles do not cover the main diagram.
- Render report says HyperFrames overlay status is `done`.

Tests to add first:

- `test_manual_stickman_pipeline_requires_real_tts_outputs()`
- `test_render_report_includes_stickman_overlay_fields()`
- `test_subtitle_bar_does_not_overlap_planned_label_boxes()`

### Phase 3: Template-Aware Visual Planner

Extend visual planning so each sentence maps to a metaphor template.

Add fields:

```json
{
  "visual_style": "stickman_business_explainer",
  "template": "infrastructure_bottleneck",
  "metaphor": "power supply bottleneck",
  "base_prompt": "...",
  "overlay_labels": [],
  "overlay_effects": []
}
```

Planner rules:

- financial metric sentence -> chart or matrix
- market/business moat sentence -> castle/moat split
- infrastructure limit sentence -> bottleneck/funnel
- strategy/platform sentence -> machine/crossroads
- comparison sentence -> scale/split comparison
- price/subscription sentence -> tablet/chart

Acceptance:

- Planner output includes template and overlay plan for every sentence.
- ComfyUI prompts explicitly request blank labels.
- HyperFrames overlay receives all final text.

Tests to add first:

- `test_visual_planner_maps_sentence_to_metaphor_template()`
- `test_visual_planner_emits_overlay_labels_for_blank_panels()`
- `test_visual_planner_uses_chart_template_for_metric_sentences()`

### Phase 4: ComfyUI Workflow Pack

Add a ComfyUI workflow variant:

```text
workflows/stickman_business_explainer_sdxl.json
```

Inputs:

- positive prompt
- negative prompt
- LoRA strength
- optional ControlNet sketch
- seed
- width/height

Outputs:

- base image
- optional preview
- prompt metadata

Acceptance:

- Workflow can be called by existing image worker.
- Seeded generation is repeatable.
- Prompt metadata records LoRA, checkpoint, and template.

Note: this phase should reuse the existing `txt2img_sdxl_stickman_lora` workflow if it is sufficient. Create `stickman_business_explainer_sdxl.json` only if template-specific placeholders cannot be expressed with the current workflow.

Tests to add first:

- `test_comfyui_workflow_accepts_stickman_business_placeholders()`
- `test_comfyui_workflow_records_lora_name_strength_and_template()`
- `test_comfyui_workflow_can_disable_lora_for_diagram_only_scene()`

### Phase 5: Custom LoRA Dataset and Training

Create dataset folder:

```text
datasets/stickman_business_explainer/
  images/
  captions/
  masks_optional/
  README.md
```

Prepare:

- remove UI controls/subtitle bars
- crop to image area
- clean captions
- tag template categories

Train:

- first LoRA with 60-100 images
- evaluate at fixed prompts
- expand to 200+ images if promising

Acceptance:

- Fixed prompt grid shows consistent stickman style.
- At least 80% of generated frames have correct round-head business character.
- At least 80% preserve blank sign panels when requested.
- Fake text frequency is low enough to mask/overlay cleanly.

Gate: do this only if Phase 0 and Phase 1A show the existing Stickfigures LoRA cannot hit the target style reliably.

Tests/evaluation to add first:

- `test_lora_evaluation_grid_scores_round_head_business_character()`
- `test_lora_checkpoint_preserves_blank_panels()`
- `test_lora_checkpoint_rejects_fake_text_overfit()`

### Phase 6: HyperFrames Diagram Overlay Pack

Add:

```text
app/services/stickman_overlay_plan.py
app/services/hyperframes_stickman_templates.py
```

Or fold into existing `hyperframes_overlay.py` if the abstraction remains small.

Artifacts:

```text
storage/projects/<pid>/hyperframes_overlay/
  index.html
  overlay_plan.json
  assets/fonts/NotoSansKR-Regular.ttf
  overlay.mov
```

Acceptance:

- Labels auto-fit within boxes.
- Text is crisp in Korean.
- Overlay alpha is validated as `yuva444p12le` MOV when WebM alpha fails.
- Render report includes overlay path and pix_fmt.

Tests to add first:

- `test_hyperframes_money_flow_uses_scene_timing()`
- `test_hyperframes_chart_draw_renders_svg_axes_and_labels()`
- `test_hyperframes_network_glow_respects_alpha_output()`

### Phase 7: Quality Gates

Add automated checks:

- no blank image: frame luminance/edge-density check
- no unreadable text: generated base image should not contain OCR-like dense glyph noise in label areas
- overlay label present: compare overlay plan labels with rendered frame OCR if available
- subtitle overlap: inspect bounding boxes of subtitle area vs planned diagram boxes
- visual relevance: ensure template matches sentence category

Acceptance:

- Render fails or warns when image is blank.
- Render warns when caption covers planned core object.
- Diagnostics bundle includes base image, overlay plan, final frame captures, and render report.

Tests to add first:

- `test_quality_gate_rejects_blank_stickman_frame()`
- `test_quality_gate_flags_text_artifacts_in_label_area()`
- `test_quality_gate_warns_on_subtitle_label_overlap()`

## Prompt Examples

### Jensen/Nvidia Scene: Delegation Inclusion

ComfyUI base prompt:

```text
na_stickbiz_style, flat vector cartoon explainer illustration, round white stickman businessman in navy suit and red tie stepping into an airplane boarding gate, another suited stickman points to a blank invitation card, simple airplane silhouette in background, muted beige airport tarmac, thick black outlines, blank signboard above gate, editorial business news metaphor, no readable text
```

HyperFrames labels:

- title: `경제사절단 합류`
- callout: `직접 요청`
- route tag: `알래스카 → 베이징`

### Nvidia Growth / Market Outperformance

ComfyUI base prompt:

```text
na_stickbiz_style, flat vector cartoon explainer illustration, smiling round white stickman businessman holding money stack, blue glass AI building receiving money stream, blank chart board on left with empty axes, muted beige office background, thick black outlines, no readable text
```

HyperFrames labels:

- chart: `ROIC`
- chart: `시장 초과 성과`
- building label: `AI 투자`

### Power Constraint

ComfyUI base prompt:

```text
na_stickbiz_style, flat vector cartoon explainer illustration, worried round white stickman businessman, electric grid cables entering a narrow funnel bottleneck, sparks near a blue AI data center building, muted beige background, thick black outlines, no readable text
```

HyperFrames labels:

- `전력 인프라 한계`
- animated sparks
- line pulse from grid to data center

## ComfyUI + HyperFrames Division of Labor

Use ComfyUI for:

- characters
- props
- scene metaphor
- base lighting/color
- rough diagram objects

Use HyperFrames for:

- Korean text
- charts
- arrows
- callout boxes
- glow animations
- subtitle-safe lower thirds
- scene transition motion

Use LoRA for:

- consistent visual style
- character identity
- line art discipline
- recurring business metaphor vocabulary

Use ControlNet for:

- exact layout
- split screens
- charts/sign placement
- preventing objects from drifting out of frame

## Immediate Next Build Recommendation

The next implementation should not try to solve every template or train a new LoRA first.

Immediate order:

1. Build the Phase 0 evidence bundle with current Stickfigures LoRA.
2. Add three business templates to the existing stickman template library.
3. Add HyperFrames `label_plate` overlay while preserving `lower_third_keyword`.
4. Generate deterministic layout sketches for the three templates.
5. Run the next ComfyUI trial using layout sketches as composition guides once lineart/scribble ControlNet support is verified.
6. Render one manual golden video with real TTS and planned label boxes.
7. Decide whether custom LoRA training is truly necessary.

Start with three templates:

1. `machine_pipeline`
2. `infrastructure_bottleneck`
3. `scale_comparison`

These cover most AI/business explainer use cases and test all hard parts:

- character consistency
- props
- blank labels
- deterministic Korean overlays
- simple animation
- subtitle coexistence

Then add:

4. `split_moat_comparison`
5. `valuation_efficiency_matrix`
6. `strategic_crossroads`

## Test Script for First Real Trial

Use a 4-sentence script:

```text
엔비디아의 강점은 단순히 GPU 판매량이 아니라, 개발자 생태계를 장악하는 구조에 있습니다.
하지만 전력 인프라와 데이터센터 비용은 성장 속도를 제한하는 병목으로 작용합니다.
투자자는 높은 효율과 높은 밸류에이션이 동시에 존재한다는 점을 분리해서 봐야 합니다.
결국 핵심은 기술 경쟁력이 실제 현금흐름으로 얼마나 오래 이어질 수 있느냐입니다.
```

Scene mapping:

- sentence 1 -> `machine_pipeline`
- sentence 2 -> `infrastructure_bottleneck`
- sentence 3 -> `valuation_efficiency_matrix`
- sentence 4 -> `money_flow` or `scale_comparison`

## Risks

- LoRA overfits exact screenshot layout and loses flexibility.
- Diffusion model keeps inventing fake text.
- HyperFrames labels may not align with ComfyUI blank plates unless layout boxes are planned.
- Subtitles may cover important diagram regions.
- Brand logos can become legally/visually messy; prefer generic logo-like tiles unless exact brand use is required.
- Training from video screenshots includes compression artifacts and player UI if not cleaned.

## Success Definition

This project succeeds when a generated frame is recognizable as the same visual language before reading any subtitle:

- round-head suited stickman
- muted beige explainer background
- thick black vector outlines
- concrete metaphor object
- crisp Korean labels
- simple chart/arrow/callout overlays
- no gibberish diffusion text
- no blank cards masquerading as images

The strongest version is a collaboration:

- ComfyUI creates the illustrated metaphor.
- LoRA makes the style consistent.
- ControlNet locks composition.
- HyperFrames makes the message readable and animated.
- newautostudio render assembles narration, images, overlay, and subtitles into a final video.
