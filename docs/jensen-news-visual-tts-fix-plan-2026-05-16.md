# Jensen/Nvidia Workflow Visual and TTS Fix Plan

Date: 2026-05-16

## Scope

Target output reviewed:

```text
C:\Users\petbl\newauto\storage\projects\14ec02ab8fc3\output.mp4
```

Diagnostic files:

```text
C:\Users\petbl\newauto\storage\projects\14ec02ab8fc3\diagnostic_contact_sheet.jpg
C:\Users\petbl\newauto\storage\projects\14ec02ab8fc3\final_scene_review.json
C:\Users\petbl\newauto\storage\projects\14ec02ab8fc3\visual_mismatch_report.md
C:\Users\petbl\Downloads\화면 캡처 2026-05-16 160248.png
```

## Confirmed Problems

### 1. Image Meaning Mismatch

The first scene shows a dark fantasy landscape and tiny figures. It does not communicate:

- Jensen Huang
- Nvidia
- Trump request
- China business delegation
- semiconductor industry news

The contact sheet confirms the same pattern:

- Scene 0: generic fantasy valley, not executive/business/news context
- Scene 1: abstract figure/clock style, not CNBC/official confirmation
- Scene 2: abstract warrior/cliff image, not phone-call request
- Scene 3: private jet boarding is closer, but still generic and low-confidence

`final_scene_review.json` confirms all 4 scenes still required operator review:

- `retry_recommended_count`: 4
- Scene 0 score: 0.616, borderline
- Scene 1 score: 0.573, retry recommended
- Scene 2 score: 0.505, retry recommended
- Scene 3 score: 0.401, retry recommended

### 2. Visual Planner Falls Back Too Generically

The latest run removed Stickfigures LoRA from actual queued ComfyUI items, but the visual plan still became generic/fallback for key scenes.

Observed causes:

- The script is business/news content, but there is no strong first-class visual domain for `political_business_delegation` or `semiconductor_business_news`.
- Generic fallback phrases such as `grounded editorial scene with one dominant real-world subject` are too vague.
- Fallback/replan can still create fantasy-like or symbolic compositions because the prompt lacks concrete visual nouns.
- The candidate scorer catches the mismatch, but the workflow still renders with warnings instead of producing a safer deterministic simple scene.

### 3. TTS Reads Korean and English Aliases

The TTS manifest showed:

```text
젠슨 황(Jensen Huang) 엔비디아(Nvidia) CEO...
```

This causes duplicated reading: Korean name/company first, then English alias again.

Required behavior:

```text
젠슨 황 엔비디아 CEO...
```

Implementation already added:

- `app/text.py`: `normalize_tts_reading_text`
- `app/services/tts.py`: TTS sentence normalization before synthesis and timing output
- Test: `tests/test_tts_pipeline.py::test_run_tts_job_removes_latin_alias_after_korean_text`

Verification:

```text
python -m pytest tests/test_tts_pipeline.py tests/test_tts_worker.py -q
25 passed
```

## Image Direction Change

For this news workflow, images should not be cinematic fantasy, dense editorial abstraction, or photorealistic stock scenes.

Preferred style:

- simple caricature news illustration
- clean 2D editorial cartoon
- 1-3 large subjects only
- clear props directly tied to the sentence
- bright neutral background
- no complex scenery
- no fantasy landscape
- no warrior/sword/cliff imagery
- no tiny distant people
- no readable text/logos

The goal is not exact celebrity likeness. The goal is simple, readable news meaning.

## Proposed Scene Templates

### Scene 0: Delegation Inclusion

Sentence meaning:

Jensen Huang/Nvidia CEO dramatically joins China business delegation after Trump request.

Simple prompt target:

```text
simple 2d caricature news illustration, middle-aged tech CEO character in black leather jacket,
green chip company badge without readable logo, standing beside a formal delegation line,
large handshake/request gesture from presidential figure silhouette, China travel cue with red flag color accent,
clean newsroom editorial cartoon, plain light background, no text
```

Avoid:

```text
fantasy valley, mountain, waterfall, medieval robe, tiny figures, dark cinematic landscape
```

### Scene 1: Official Confirmation

Sentence meaning:

CNBC/foreign media report officially confirms Nvidia CEO accompanies Trump China trip.

Simple prompt target:

```text
simple 2d news desk caricature illustration, TV news camera and reporter silhouette,
large check mark document, tech CEO character and presidential figure shown as simple icons,
airplane and China route cue in background, clean editorial cartoon, no readable text
```

Avoid:

```text
abstract clock, empty landscape, faceless fashion figure, unreadable newsroom wall
```

### Scene 2: Direct Phone Call Request

Sentence meaning:

Trump directly calls Jensen Huang and asks him to join.

Simple prompt target:

```text
simple 2d caricature split-screen phone call, presidential figure on one side holding phone,
tech CEO character on the other side surprised and nodding, delegation invitation document icon between them,
clean light background, large phone receiver, no readable text
```

Avoid:

```text
warrior, sword, cliff, battle pose, fantasy danger scene
```

### Scene 3: Boarding From Alaska To Beijing

Sentence meaning:

Jensen Huang boards aircraft at Alaska stop and heads to Beijing.

Simple prompt target:

```text
simple 2d caricature airport boarding scene, tech CEO character climbing airplane stairs,
snowy Alaska cue, airplane with official blue stripe but no readable markings,
small Beijing direction arrow icon without text, clean editorial cartoon, no readable text
```

Avoid:

```text
generic private jet stock photo, luxury travel ad, empty runway, tiny subject
```

## Implementation Plan

### Phase 1. TTS Alias Normalization

Status: done.

Rules:

- Remove Latin parenthetical aliases directly after Korean text.
- Keep standalone English acronyms such as `CNBC`, `CEO`, `LFP`, `NCM`.
- Apply before OmniVoice synthesis and before TTS timings/subtitles are written.

Regression:

- `젠슨 황(Jensen Huang) 엔비디아(Nvidia) CEO` becomes `젠슨 황 엔비디아 CEO`.
- `CNBC 등 외신` remains unchanged.

### Phase 2. Add News Caricature Visual Domain

Add a first-class domain or strategy:

```text
political_business_delegation
semiconductor_business_news
```

Required output fields:

- `visual_mode`: `simple_news_caricature`
- `template_hint`: `txt2img_sdxl_basic`
- `lora_policy`: `none`
- `style_hint`: simple 2D caricature news illustration

Never use:

- Stickfigures LoRA
- fantasy cinematic landscape
- warrior/battle/cliff metaphor
- abstract symbolic scenery

### Phase 3. Deterministic Scene Template Selection

Before generic fallback, detect concrete news actions:

- `합류`, `사절단`, `요청`: delegation inclusion scene
- `공식 확인`, `CNBC`, `외신`: official confirmation scene
- `전화`, `직접`, `요청`: phone-call request scene
- `에어포스원`, `알래스카`, `탑승`, `베이징`: airport boarding scene

When matched, bypass generic fallback and produce one of the four templates above.

### Phase 4. Hard Negative Prompt Expansion

For this domain, always add:

```text
fantasy landscape, mountain valley, waterfall, medieval, warrior, sword, cliff, dark scenery,
tiny distant people, abstract fashion figure, surreal symbolic scene, photorealistic stock photo,
readable text, logo, watermark
```

### Phase 5. Gate Behavior

If all candidates remain below threshold:

- Do not silently render as acceptable.
- Save the best candidate, but mark the scene as failed visual relevance.
- Surface `operator_review_required` in the UI with the sentence, selected image, and exact missing anchors.

### Phase 6. Re-run Verification

Use the same Jensen/Nvidia script and verify:

- TTS manifest has no `Jensen Huang` or `Nvidia` inside Korean-alias parentheses.
- Final subtitles do not show duplicate alias text.
- Contact sheet scene 0 has CEO/delegation/request cue.
- Scene 1 has media confirmation cue.
- Scene 2 has phone-call request cue.
- Scene 3 has airport boarding cue.
- `visual_mismatch_report.md` has no fantasy/warrior/cliff/stickman contamination.

## Acceptance Criteria

- TTS no longer reads Korean plus English aliases redundantly.
- All four scenes are simple, readable news caricature/explainer images.
- No scene uses fantasy landscape, warrior, sword, cliff, or abstract unrelated imagery.
- All ComfyUI jobs use `txt2img_sdxl_basic`, no LoRA.
- Candidate review has no `operator_intervention_required` for obvious template matches.
