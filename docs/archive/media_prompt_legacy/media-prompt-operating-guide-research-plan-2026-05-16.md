# Media Prompt Operating Guide Research Plan

Updated: 2026-05-16 KST  
Status: superseded by `docs/media-prompt-operating-guide.md`  
Primary goal: make this the single planning source for NewAuto Studio Media prompt guidance.

> Superseded: the active single source of truth is now `docs/media-prompt-operating-guide.md`. Keep this file only as implementation history until legacy Media docs are archived.

## 1. Review Result

The previous draft had the right direction, but it was not safe to use as the single guide because parts of it were corrupted and several statements were either too broad or out of sync with the current code.

This version keeps only the parts verified against the current codebase and changes the plan so that the final operating guide can stand alone.

## 2. Verified Current State

The current NewAuto Media pipeline is:

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

Verified code paths:

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

Verified ComfyUI workflow templates:

- `txt2img_sdxl_basic`
- `txt2img_sdxl_lora`
- `txt2img_sdxl_stickman_lora`
- `txt2img_sdxl_lightning`
- `txt2img_sdxl_ipadapter_style`
- `txt2img_sdxl_ipadapter_style_lora`
- `txt2img_sdxl_controlnet_depth`

Verified domain families currently present in code:

- `tech`
- `ev_battery`
- `food_trend`
- `agriculture_environment`
- `science_materials`
- `news_explainer`
- `ai_policy_conflict`
- `essay`
- `generic`

Important correction: `semiconductor_business`, `politics_diplomacy`, and `finance_market` are useful future domain names, but they are not first-class domains in the current code. They must not be documented as already implemented. For now they should be handled as sub-strategies under `tech`, `news_explainer`, or `essay` until code support is added.

## 3. What Was Valid

The following ideas from the prior draft are valid and should remain:

- Gemma4 should use a stable internal operating guide instead of improvising every prompt.
- The guide should be built from local docs, code, real project outputs, prompt manifests, and failure reports.
- Real-time web search should not be part of normal video generation.
- LoRA use must be policy-driven, not automatic.
- `must_show`, `avoid`, `domain`, `visual_mode`, and template choice should be explicitly structured.
- Failures should be classified and used to update docs, quality gates, and tests.
- Jensen/Nvidia and EV/LFP failures are useful seed cases for the guide.
- Long Korean scripts need readable subtitle splitting before render.

## 4. What Was Not Valid Or Must Be Changed

These items are removed or changed:

- Do not claim `semiconductor_business`, `politics_diplomacy`, or `finance_market` are implemented domains. They are planned sub-strategies only.
- Do not instruct Gemma4 to reference many separate docs during prompt generation. That risks conflicting guidance.
- Do not make `media-image-generation-master-guide-plan.md` and `media-simplification-plan-2026-05-15.md` co-equal runtime references. Their useful content must be merged into one final guide.
- Do not list guessed API endpoints as operational truth unless verified. The guide should prefer service/code behavior and only list tested routes later.
- Do not say generic prompt blocking is missing. Current code already blocks `GENERIC_FALLBACK_IN_MUST_SHOW` and `GENERIC_FALLBACK_IN_PROMPT` in `image_worker.py`, and strict domains add `STRICT_PROMPT_COVERAGE_FAILED` when coverage fails.
- Do not use corrupted Korean text from older docs as source material without re-reading or re-encoding it.
- Do not physically delete historical documents before the final guide is complete and reviewed.

## 5. Single-Document Policy

The final source of truth must be:

```text
docs/media-prompt-operating-guide.md
```

After that guide is complete, all Media prompt guidance should point to it.

The current research plan is temporary. Its purpose is to produce the final guide and define what to do with older documents.

### 5.1 Runtime Rule

Gemma4 visual planning must not be told to read multiple planning documents.

Allowed runtime reference:

```text
docs/media-prompt-operating-guide.md
```

Disallowed runtime references after consolidation:

- `docs/media-image-generation-master-guide-plan.md`
- `docs/media-simplification-plan-2026-05-15.md`
- scattered archive plans
- ad hoc notes in `issue.md`
- old corrupted or mojibake documents

### 5.2 Existing Document Cleanup Direction

The user preference is to end with one document and remove confusion from old docs. The safe cleanup path is:

1. Extract valid content from older docs into `media-prompt-operating-guide.md`.
2. Add a short deprecation banner to older related docs.
3. Move older related docs into `docs/archive/media_prompt_legacy/`.
4. Delete only duplicated scratch plans after confirming nothing links to them.

Candidates for archive/deprecation after the final guide exists:

- `docs/media-image-generation-master-guide-plan.md`
- `docs/media-simplification-plan-2026-05-15.md`
- Media-related archive plans that are already superseded
- this research plan, once `media-prompt-operating-guide.md` is complete

Documents that should not be deleted as part of this Media cleanup:

- `docs/newauto-windows-studio-master-plan-2026-05-15.md`, unless a separate product-wide consolidation happens
- `docs/windows-app-architecture.md`
- LM Studio operator setup/audit docs, unless a separate operator-doc cleanup is requested

## 6. Final Guide Structure

`docs/media-prompt-operating-guide.md` should contain everything Gemma4 and NewAuto need for the Media step.

Required sections:

1. Purpose and non-goals
2. Current NewAuto Media pipeline
3. Domain taxonomy
4. Sentence analysis rules
5. Visual plan JSON schema
6. Domain strategies
7. ComfyUI template policy
8. LoRA policy
9. Prompt compilation rules
10. Prompt quality gate rules
11. Candidate selection and retry rules
12. Visual relevance/preflight rules
13. Failure classification
14. Failure analysis record format
15. Regression test matrix
16. Known case studies
17. Deprecated old-doc mapping

## 7. Domain Strategy Plan

### 7.1 Implemented Domains

The final guide must describe only implemented domains as implemented.

#### `ev_battery`

Use for LFP/NCM/solid-state, EV batteries, driving range, fire safety, energy density, charging, K-battery topics.

Current policy:

- Default template: `txt2img_sdxl_basic`
- LoRA: none by default
- Stickfigure style: blocked
- Required visual anchors: EV, battery cell/pack, LFP/NCM/solid-state, price/safety/range/energy density when relevant
- Known failure: image drifts into showroom, server room, or isolated glossy battery product render

#### `news_explainer`

Use for news/comment/reaction/public opinion/media-system explainers.

Current policy:

- Prefer simple explainer or editorial symbolic compositions
- Avoid dense dashboards and generic UI screens
- Must keep the news mechanism visible

Known gap:

- Jensen/Nvidia business delegation news may be detected as `tech` or generic news context, but it lacks a dedicated sub-strategy for named executive + diplomacy/business delegation scenes.

#### `ai_policy_conflict`

Use for AI company/government/regulation/security/conflict stories.

Current policy:

- Prefer symbolic editorial composition
- Keep institution, conflict, restriction, or policy object visible

#### `tech`

Use for AI, GPU, semiconductor, chip, datacenter, automation, model training, and related technology topics.

Needed extension:

- Add a `semiconductor_business_news` sub-strategy inside the final guide.
- This should cover Nvidia, Jensen Huang, CEO, delegation, chip diplomacy, export controls, data centers, and business-government relations without adding a new code domain immediately.

#### `food_trend`

Use for products, beverages, dessert, cafe, bakery, supermarket, retail food trends.

Current policy:

- Product or food item must dominate
- Avoid empty interiors and generic industry scenes

#### `agriculture_environment` and `science_materials`

Use for soil, farms, biodegradable film, crop, polymer, nanocellulose, laboratory/materials topics.

#### `essay` and `generic`

Use only when no specific domain applies.

Current risk:

- Generic fallback can produce repeated symbolic scenes. The guide must discourage checklist/road/signpost/office defaults unless explicitly relevant.

### 7.2 Planned Sub-Strategies

These are guide-level strategies first, not code domains yet:

- `semiconductor_business_news`
- `political_business_delegation`
- `executive_travel_diplomacy`
- `finance_market_explainer`

They can be encoded later as first-class domains only after tests prove value.

## 8. Gemma4 Visual Plan Schema

The final guide should require a small schema. Large schemas slow Gemma4 and increase malformed JSON risk.

Recommended schema:

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

Rules:

- `must_show` must be concrete and imageable.
- `main_subject` must not be a generic phrase.
- `avoid` must include known drift risks.
- `template_hint` must be one of the verified templates or empty.
- `lora_policy` must be `none`, `stickman_allowed`, `style_reference_allowed`, or `controlnet_allowed`.
- The planner must not output Markdown.
- The planner must not output placeholder text such as `concrete visual subject tied to the sentence`.

## 9. ComfyUI Template Policy

The final guide must map templates to use cases:

### `txt2img_sdxl_basic`

Default for:

- news explainer
- tech/semiconductor/business news
- EV battery
- food trend
- editorial symbolic scenes

### `txt2img_sdxl_lora`

Use only when a specific LoRA is intentionally chosen and documented.

### `txt2img_sdxl_stickman_lora`

Allowed for:

- simple educational metaphor
- simple character action
- non-real-person explainer

Blocked for:

- EV battery strict domain
- named real executives
- political/diplomatic/business delegation news
- semiconductor business news
- realistic news scenes

### `txt2img_sdxl_lightning`

Use for faster drafts only if quality tradeoff is acceptable.

### `txt2img_sdxl_ipadapter_style`

Use only when style reference image capability and a valid reference image exist.

### `txt2img_sdxl_ipadapter_style_lora`

Use only when both reference style and LoRA are intentionally needed.

### `txt2img_sdxl_controlnet_depth`

Use only when a control image exists and ControlNet capability check passes.

## 10. LoRA Policy

LoRA must be explicit and documented.

Minimum fields for each LoRA in the final guide:

- file name
- trigger words
- expected visual style
- allowed domains
- blocked domains
- recommended strength
- template compatibility
- known failure modes
- sample project or contact sheet if available

Current known LoRA:

- `Stickfigures-000005.safetensors`

Current policy for Stickfigures:

- Default strength in autopilot path is `0.8` when used.
- It is useful for simple stick-figure educational scenes.
- It should not be used for EV battery, named-person news, semiconductor executive news, or diplomatic/business delegation scenes.

## 11. Failure Classification

Every failed or low-quality Media result should be classified.

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

## 12. Failure Analysis Record

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

## 13. Recurrence Prevention Rule

The final guide must enforce this policy:

```text
First occurrence:
- write failure analysis
- add case note to media-prompt-operating-guide.md

Second similar occurrence:
- add or tighten prompt_quality / visual_relevance gate
- add regression test

Third similar occurrence:
- change visual planner schema, domain strategy, retry policy, or template selection
```

## 14. Verified Case Studies To Include

### Jensen Huang / Nvidia delegation

Project:

```text
C:\Users\petbl\newauto\storage\projects\f4b97ca049c8
```

Result:

- Video rendered successfully.
- TTS and subtitle sync were acceptable after readable subtitle split.
- Scene 2 matched the phone-call request relatively well.
- Scene 0, 1, and 3 were weak or generic.

Guide lessons:

- Named executive + company + diplomatic/business travel needs a specific visual strategy.
- Generic conference building or airport display is not enough.
- Must show named executive proxy, business delegation cue, official request/confirmation, Air Force One or boarding action when relevant.
- This should be handled as `tech` with `semiconductor_business_news` or `political_business_delegation` sub-strategy until a first-class domain exists.

### EV/LFP battery

Project:

```text
C:\Users\petbl\newauto\storage\projects\726788fd6c3b
```

Result:

- Stickfigure/LoRA contamination was fixed.
- Some semantic mismatch remained.

Guide lessons:

- EV battery should default to `txt2img_sdxl_basic` and LoRA none.
- Isolated battery product renders are often insufficient.
- Price/safety/range/energy-density comparison must appear when the sentence needs it.

### Long Korean subtitle preflight

Result:

- `subtitle_layout` can fail with long Korean sentences when cue splitting remains sentence-based.

Guide lesson:

- Korean script workflows should default to `cue_split_mode=readable` before render.

## 15. Implementation Plan

### P0. Build the final single guide

Create:

```text
docs/media-prompt-operating-guide.md
```

It must include all operational rules needed by Gemma4 and NewAuto. It must not require the user or the model to open other Media planning docs.

### P1. Deprecate older Media docs

After P0:

- Add a deprecation banner to old Media docs.
- Move superseded docs to `docs/archive/media_prompt_legacy/`.
- Keep only links from `issue.md` and any app help text to `docs/media-prompt-operating-guide.md`.

### P2. Connect guide rules to Gemma4 planner

Update:

- `app/services/visual_planner.py`
- possibly `app/services/image_prompting.py`

Rules:

- Do not inject the whole guide every time.
- Extract compact domain/sub-strategy rules.
- Keep the JSON schema small.
- Use `google/gemma-4-e4b` as the fixed LM Studio model.

### P3. Strengthen strict domain gates

Update:

- `app/services/prompt_quality.py`
- `app/services/visual_relevance.py`
- `app/services/comfyui_pipeline.py`
- `app/workers/image_worker.py`

Focus:

- strict semantic mismatch must not pass silently
- `retry_recommended` in strict domains should become block/retry unless explicitly allowed
- `must_show` must survive into prompt and candidate selection

### P4. Add failure analysis automation

Add:

```text
app/services/failure_analysis.py
scripts/analyze_media_failure.py
```

The script should read project outputs and generate `failure_analysis.md/json`.

### P5. Add regression tests

Add or update tests for:

- Jensen/Nvidia visual plan strategy
- EV/LFP no-LoRA and must-show preservation
- generic placeholder blocking
- readable subtitle split for Korean script render
- strict-domain retry/block when `semantic_match_score` is zero or candidate review recommends retry

## 16. Completion Criteria

This consolidation is complete when:

- `docs/media-prompt-operating-guide.md` exists and is the only active Media prompt guide.
- Older Media planning docs are archived or explicitly deprecated.
- `issue.md` links only to the final guide for Media prompt rules.
- Gemma4 planner follows the final guide's compact schema/rules.
- Jensen/Nvidia and EV/LFP representative workflows no longer repeat the known visual failures.
- New failures produce a structured failure analysis file.
