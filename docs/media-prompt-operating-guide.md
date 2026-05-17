# NewAuto Studio Media Prompt Operating Guide

Updated: 2026-05-16 KST  
Status: active single source of truth for Media prompt planning

## 0. External Research Sources

This guide now includes external ComfyUI/LoRA/SDXL research collected on 2026-05-16.

Use these sources as background evidence, not as separate runtime instructions for Gemma4.

- ComfyUI GitHub README: confirms ComfyUI is a node graph/API backend, generated PNG files can contain full workflow metadata, prompt emphasis syntax exists, and unchanged graph parts may be cached/reused.
  - https://github.com/comfy-org/ComfyUI
- ComfyUI Cloud/API docs: confirms workflows are API-format JSON graphs and jobs are submitted asynchronously through prompt submission, returning a `prompt_id`.
  - https://docs.comfy.org/development/cloud/overview
- ComfyUI Community Manual, Load LoRA: confirms Load LoRA modifies diffusion model and CLIP, has `lora_name`, `strength_model`, and `strength_clip`, and can chain multiple LoRAs.
  - https://blenderneko.github.io/ComfyUI-docs/Core%20Nodes/Loaders/LoadLoRA/
- ComfyUI Dev, Load LoRA guide: confirms LoRA use cases include character/style/scene/lighting and that trigger words from the LoRA author should be used when required.
  - https://comfyui.dev/docs/guides/nodes/load-lora/
- Tech Tactician SDXL ComfyUI workflow notes: confirms native-node SDXL workflows commonly use `CheckpointLoaderSimple`, `LoraLoader`, `CLIPTextEncodeSDXL`, `KSampler`, `VAEDecode`, and that LoRA nodes can be disabled by default in generic workflows.
  - https://techtactician.com/basic-comfyui-sdxl-workflows/
- Civitai Stickfigures SDXL LoRA model page: confirms the NewAuto Stickfigures LoRA is SDXL 1.0 and uses trigger words `Flipchartvisu` and `Stick figure`.
  - https://civitai.green/models/700803/stickfigures

## 1. Purpose

This document is the single operating guide for NewAuto Studio Media image prompt planning.

Gemma4 and NewAuto should use this document's rules to create sentence-matched image prompts, choose ComfyUI templates, decide LoRA policy, diagnose failures, and prevent repeated visual mismatch.

This document replaces scattered Media prompt guidance in older planning documents. Older docs may be archived for history, but they should not be used as runtime guidance once this guide is connected to the planner.

## 2. Non-Goals

Do not use this guide to:

- perform real-time web search during normal video generation
- choose arbitrary LoRA files
- change ComfyUI workflow templates without code/test updates
- treat old archive notes as active rules
- bypass prompt quality, visual relevance, preflight, or render checks

Gemma4 may suggest a visual plan, but NewAuto quality gates remain responsible for blocking unsafe or mismatched prompts.

## 3. Current Media Pipeline

The current pipeline is:

```text
script
-> sentence split
-> domain detection
-> Gemma4 visual planner
-> visual brief
-> SDXL prompt generation
-> prompt quality gate
-> ComfyUI generation
-> candidate scoring/selection
-> visual relevance report
-> scene/render plan
-> render
```

Relevant code paths:

- `app/services/domain_detection.py`
- `app/services/visual_planner.py`
- `app/services/image_prompting.py`
- `app/services/visual_brief.py`
- `app/services/prompt_compiler.py`
- `app/services/prompt_quality.py`
- `app/services/prompt_repair.py`
- `app/services/comfyui_pipeline.py`
- `app/workers/image_worker.py`
- `app/routers/image_gen.py`
- `app/services/visual_relevance.py`
- `app/services/preflight.py`

## 4. Model Policy

Default local LLM:

```text
LM Studio + google/gemma-4-e4b
```

Gemma4 should produce compact JSON visual plans. It should not output Markdown, long prose, or unstructured image prompts when structured visual planning is requested.

Qwen3.5 is not the default prompt model. In current tests it did not reliably return usable JSON in time.

## 5. Domain Taxonomy

Implemented domains:

- `tech`
- `ev_battery`
- `food_trend`
- `agriculture_environment`
- `science_materials`
- `news_explainer`
- `ai_policy_conflict`
- `essay`
- `generic`

Planned sub-strategies, not first-class code domains yet:

- `semiconductor_business_news`
- `political_business_delegation`
- `executive_travel_diplomacy`
- `finance_market_explainer`

Do not document a sub-strategy as an implemented domain until code and tests support it.

## 6. Sentence Analysis Rules

For every sentence, Gemma4 must identify:

- core event
- main subject
- action
- setting or environment
- people
- organizations
- places
- concrete visual objects
- abstract ideas that need visual translation
- `must_show`
- `avoid`

Rules:

- `must_show` must contain imageable objects, actions, or scene cues.
- `main_subject` must not be generic.
- Named people, companies, institutions, or locations must be preserved when visually relevant.
- Avoid vague placeholders such as `concrete visual subject tied to the sentence`.
- Avoid repeated generic defaults such as empty offices, dashboards, signposts, roads, or abstract city buildings unless the sentence requires them.

## 7. Gemma4 Visual Plan Schema

Use a small JSON schema:

```json
{
  "sentence_idx": 0,
  "domain": "tech",
  "sub_strategy": "semiconductor_business_news",
  "visual_mode": "editorial_scene",
  "core_meaning": "",
  "main_subject": "",
  "action": "",
  "environment": "",
  "must_show": [],
  "avoid": [],
  "composition": "",
  "template_hint": "txt2img_sdxl_basic",
  "lora_policy": "none",
  "rationale": ""
}
```

Allowed `lora_policy` values:

- `none`
- `stickman_allowed`
- `style_reference_allowed`
- `controlnet_allowed`

Allowed `template_hint` values:

- empty string
- `txt2img_sdxl_basic`
- `txt2img_sdxl_lora`
- `txt2img_sdxl_stickman_lora`
- `txt2img_sdxl_lightning`
- `txt2img_sdxl_ipadapter_style`
- `txt2img_sdxl_ipadapter_style_lora`
- `txt2img_sdxl_controlnet_depth`

## 8. Domain Strategies

### 8.1 EV Battery

Use for:

- LFP
- NCM
- solid-state batteries
- electric vehicles
- battery cost
- fire safety
- range
- charging
- energy density
- K-battery strategy

Default policy:

- template: `txt2img_sdxl_basic`
- LoRA: none
- visual mode: `simple_explainer`, `data_diagram`, or controlled editorial scene
- stickfigure style: blocked

Must show:

- EV, battery cell/pack, or battery comparison object
- the specific concept in the sentence, such as price, fire safety, range, density, charging, LFP/NCM, or solid-state

Avoid:

- generic showroom
- unrelated server room
- isolated glossy battery product render
- stick figure
- cartoon mascot
- Flipchartvisu style

### 8.2 News Explainer

Use for:

- news mechanisms
- comments/reactions/public opinion
- press confirmation
- media company process
- notification or article flow

Default policy:

- template: `txt2img_sdxl_basic`
- LoRA: none unless manually justified
- visual mode: `editorial_scene`, `simple_explainer`, or `symbolic_concept`

Must show:

- the mechanism or institution in the sentence
- article, newsroom, official confirmation, public reaction, or timeline cue when relevant

Avoid:

- dense dashboards
- random airport or stock display unless the sentence requires travel
- generic UI screens with no news mechanism

### 8.3 AI Policy Conflict

Use for:

- AI company versus government
- regulation
- national security
- restriction
- hearing
- lawsuit
- policy intervention

Default policy:

- template: `txt2img_sdxl_basic`
- LoRA: none
- visual mode: `editorial_scene` or `symbolic_concept`

Must show:

- institution, policy object, conflict marker, restriction marker, or security cue

Avoid:

- generic robot brain
- decorative server wall
- dense analytics UI

### 8.4 Tech

Use for:

- AI
- GPU
- chips
- semiconductor
- data centers
- automation
- model training
- browser/agent technology

Default policy:

- template: `txt2img_sdxl_basic`
- LoRA: none by default

For named semiconductor business news, use sub-strategy:

```text
semiconductor_business_news
```

This sub-strategy should preserve:

- named executive proxy
- company cue
- chip or AI infrastructure cue
- business or government context
- travel, delegation, meeting, or official request when relevant

Avoid:

- empty conference building
- generic city
- unrelated server room
- abstract tech background with no event

### 8.5 Political Business Delegation

This is currently a sub-strategy, not an implemented domain.

Use under `tech`, `news_explainer`, or `essay` when a sentence combines:

- named executive
- government leader
- official request
- business delegation
- diplomatic travel
- aircraft or summit context

Must show:

- delegation or official travel context
- invitation/request cue
- named executive proxy or business leader figure
- government/business setting

Avoid:

- empty government building
- generic airport display
- unrelated cityscape

### 8.6 Food Trend

Use for:

- food product
- beverage
- dessert
- cafe
- bakery
- supermarket
- retail food trend

Default policy:

- template: `txt2img_sdxl_basic`
- LoRA: none unless manually justified

Must show:

- product or food item as dominant subject
- retail/cafe/bakery context when relevant

Avoid:

- empty interior
- generic industry metaphor
- non-food scene

### 8.7 Agriculture Environment And Science Materials

Use for:

- soil
- farm
- crop
- biodegradable film
- polymer
- cellulose
- materials lab

Default policy:

- template: `txt2img_sdxl_basic`
- LoRA: none

Must show:

- material, lab, field, crop, soil, film, or sample object tied to the sentence

Avoid:

- AI brain
- server rack
- unrelated office

### 8.8 Essay And Generic

Use only when no stronger domain applies.

Default policy:

- template: `txt2img_sdxl_basic`
- LoRA: none unless the user explicitly chose a style

Avoid:

- repeated checklist
- road fork
- signpost
- empty office
- generic dashboard
- decorative cityscape

## 9. ComfyUI Template Policy

External research confirms that ComfyUI workflows are graph/node JSON structures and can be submitted through API-style prompt execution. NewAuto should keep workflow templates deterministic and versioned locally instead of asking Gemma4 to invent workflow JSON.

### `txt2img_sdxl_basic`

Default for most generated Media images.

Use for:

- news
- tech
- EV battery
- food trend
- editorial symbolic scenes
- general explainers

### `txt2img_sdxl_lora`

Use only when a specific LoRA is intentionally selected and documented.

Required:

- `lora_name` must match a local file under the ComfyUI LoRA directory.
- `strength_model` and `strength_clip` must be set intentionally.
- trigger words must be added only if the LoRA documentation requires them.
- domain policy must allow the LoRA.

### `txt2img_sdxl_stickman_lora`

Allowed for:

- simple educational metaphor
- non-real-person character action
- simple concept explainer

Blocked for:

- EV battery
- named real executives
- political/diplomatic/business delegation news
- semiconductor business news
- realistic news scenes

### `txt2img_sdxl_lightning`

Use for faster drafts only when lower quality is acceptable.

### `txt2img_sdxl_ipadapter_style`

Use only when a valid style reference image exists and capability checks pass.

### `txt2img_sdxl_ipadapter_style_lora`

Use only when both style reference and LoRA are intentionally required.

### `txt2img_sdxl_controlnet_depth`

Use only when a control image exists and ControlNet capability checks pass.

## 10. LoRA Policy

LoRA use must be explicit.

External research confirms:

- LoRA changes both the diffusion model and CLIP conditioning path in ComfyUI.
- `strength_model` controls how strongly the LoRA modifies the model.
- `strength_clip` controls how strongly the LoRA affects text interpretation.
- LoRA authors often define required trigger words.
- LoRA is suited for specific style, character, outfit, scene, or lighting behavior, not for generic factual grounding.

Each LoRA entry must define:

- file name
- trigger words
- expected style
- allowed domains
- blocked domains
- recommended strength
- compatible templates
- known failures

Current known LoRA:

```text
Stickfigures-000005.safetensors
```

Stickfigures policy:

- source: Civitai Stickfigures SDXL LoRA
- base model: SDXL 1.0
- trigger words: `Flipchartvisu`, `Stick figure`
- useful for simple stick-figure educational scenes
- default autopilot strength when used: `0.8`
- blocked for EV battery
- blocked for named-person news
- blocked for semiconductor executive news
- blocked for political/business delegation scenes

Critical rule:

If `Flipchartvisu` or `Stick figure` appears in a prompt for a blocked domain or blocked sub-strategy, the prompt must be treated as a LoRA policy failure and must not be submitted to ComfyUI.

For NewAuto's current news and business explainers, the safe default is:

```text
lora_policy = none
template_hint = txt2img_sdxl_basic
lora_name = ""
lora_strength = 0.0
```

## 10.1 SDXL Dual Prompt Policy

NewAuto uses SDXL-capable templates with prompt G/L fields in several paths.

Operating rule:

- `prompt_g` should carry the global scene description, composition, environment, and visual intent.
- `prompt_l` should carry local subject details, specific objects, style, and camera/framing detail.
- If Gemma4 cannot reliably split the prompt, duplicate a concise stable prompt into both fields rather than inventing conflicting G/L content.
- Do not let LoRA trigger words appear in either field unless LoRA policy allows them.

## 11. Prompt Compilation Rules

A final SDXL prompt must preserve:

- `main_subject`
- action
- environment
- all concrete `must_show` terms, where feasible
- domain core object
- composition intent

Negative prompt should include:

- domain-specific forbidden objects
- readable text, watermark, logo, unwanted UI text unless specifically needed
- known drift risks from the selected domain

Do not allow:

- generic placeholder text
- raw Korean glue words as image subjects
- style terms that conflict with the chosen visual mode
- LoRA trigger words when LoRA is blocked

## 12. Prompt Quality Gate Rules

Current blocking issue codes include:

- `EV_BATTERY_CORE_VISUAL_MISSING`
- `EV_BATTERY_STICKFIGURE_STYLE_BLOCKED`
- `GENERIC_FALLBACK_IN_MUST_SHOW`
- `GENERIC_FALLBACK_IN_PROMPT`

Strict domains currently include:

- `ev_battery`
- `food_trend`
- `news_explainer`
- `ai_policy_conflict`

For strict domains, failed keyword coverage should block or force repair before ComfyUI submission.

Planned strengthening:

- Add strict behavior for named semiconductor/business delegation sub-strategies.
- Treat persistent `retry_recommended` as block/retry in strict domains unless explicitly overridden.
- Ensure `must_show` survives into prompt and candidate selection.

## 13. Candidate Selection And Retry

Candidate scoring should not reward metadata alone when the image is semantically wrong.

Retry or block when:

- strict domain semantic mismatch remains
- selected image lacks the main subject
- `must_show` is not visually represented
- candidate score is low and the reason is semantic, not just edge/detail quality
- generic fallback image wins over a more relevant candidate

For EV battery, semantic mismatch must force retry even when candidate score is high.

## 14. Visual Relevance And Preflight

Before render:

- generated image mappings must match current sentence hashes
- selected media files must exist
- render plan media must be available
- visual relevance hard failures must not pass silently
- Korean long-form subtitles should use readable cue splitting

Known rule:

```text
cue_split_mode=readable
```

should be applied for long Korean scripts before render.

## 15. Failure Classification

Allowed failure classes:

- `planning_failure`
- `domain_detection_failure`
- `prompt_compilation_failure`
- `template_selection_failure`
- `lora_policy_failure`
- `generation_failure`
- `candidate_selection_failure`
- `visual_relevance_failure`
- `subtitle_preflight_failure`
- `render_failure`

## 16. Failure Analysis Record

For each meaningful failure, create:

```text
failure_analysis.md
failure_analysis.json
```

Required fields:

- project id
- script title
- sentence index
- sentence text
- detected domain
- planned sub-strategy
- selected image
- prompt
- negative prompt
- template id
- LoRA name
- candidate score
- selected reason
- visual mismatch issue codes
- failure class
- direct cause
- recurrence prevention action
- document update needed
- code update needed
- test update needed

## 17. Recurrence Prevention

Use this rule:

```text
First occurrence:
- write failure analysis
- add case note to this guide

Second similar occurrence:
- add or tighten prompt_quality / visual_relevance gate
- add regression test

Third similar occurrence:
- change visual planner schema, domain strategy, retry policy, or template selection
```

## 18. Case Study: Jensen Huang / Nvidia Delegation

Project:

```text
C:\Users\petbl\newauto\storage\projects\f4b97ca049c8
C:\Users\petbl\newauto\storage\projects\14ec02ab8fc3
```

Result:

- Video rendered successfully.
- TTS and subtitle sync were acceptable after readable subtitle split.
- Stickfigures LoRA and trigger-word contamination were removed from the actual queued ComfyUI items in the latest run.
- Latest run still produced weak generic fallback images for several scenes.
- Scene 3 matched the airport/boarding cue better than the other scenes.
- Scene 0, 1, and 2 still need stronger named-executive/business-delegation visual planning.

Lessons:

- Named executive + company + official request + travel needs a specific strategy.
- Generic conference building is not enough.
- Generic airport display is not enough.
- Airplane scene must show boarding/travel action when sentence says boarding.
- Use `tech` with sub-strategy `semiconductor_business_news` or `political_business_delegation` until a first-class domain exists.
- Do not let `generic` fallback use Stickfigures or generic stickman poster templates for business/news scripts.
- If all retry/replan/fallback attempts remain below the candidate threshold, mark the scene for operator review instead of silently accepting it as clean.

Required anchors for similar scripts:

- Jensen Huang or business executive proxy
- Nvidia/company cue
- Trump/government request cue when relevant
- delegation/business travel cue
- Air Force One/airport/boarding cue when relevant

## 19. Case Study: EV/LFP Battery

Project:

```text
C:\Users\petbl\newauto\storage\projects\726788fd6c3b
```

Result:

- Stickfigure/LoRA contamination was fixed.
- Some semantic mismatch remained.

Lessons:

- Default to `txt2img_sdxl_basic`.
- Use no LoRA by default.
- Avoid isolated glossy battery render.
- Price/safety/range/energy-density comparison must appear when the sentence requires it.

## 20. Deprecated Document Mapping

This is the active Media prompt guide.

Older Media prompt docs have been archived after their valid content was absorbed:

- `docs/archive/media_prompt_legacy/media-image-generation-master-guide-plan.md`
- `docs/archive/media_prompt_legacy/media-simplification-plan-2026-05-15.md`
- `docs/archive/media_prompt_legacy/media-prompt-operating-guide-research-plan-2026-05-16.md`
- Media-related archive plans already superseded by this guide

Target archive directory:

```text
docs/archive/media_prompt_legacy/
```

Do not delete broader product or architecture docs as part of this Media prompt cleanup.
