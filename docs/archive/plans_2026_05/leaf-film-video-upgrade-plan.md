# Leaf Film Article Video Upgrade Plan

Project: `28ce3f120c69`

Final video:

- `C:\Users\petbl\newauto\storage\projects\28ce3f120c69\output.mp4`

Diagnostic assets:

- Contact sheet: `C:\Users\petbl\newauto\storage\projects\28ce3f120c69\diagnostic_contact_sheet_leaf_film.jpg`
- Prompt manifest: `C:\Users\petbl\newauto\storage\projects\28ce3f120c69\image_prompts_manifest.json`
- Render report: `C:\Users\petbl\newauto\storage\projects\28ce3f120c69\render_report.json`
- Visual mismatch report: `C:\Users\petbl\newauto\storage\projects\28ce3f120c69\visual_mismatch_report.json`

## Current Result Summary

The image quality improved because this run used manually authored, sentence-specific prompts instead of the automatic prompt suggestion path. The output is technically stable:

- Duration: `108.76s`
- Audio drift: `0.0s`
- Sentence / subtitle cue count: `12`
- Render segments: `12`
- Motion: `still_locked` for every scene
- TTS: `full_passage`, fixed seed, one consistent male announcer voice

The important caveat is that the final render required this project option:

- `body_image_options.allow_low_quality_generated_images = True`

That means the video was completed successfully, but the automatic image quality gate still does not understand this agriculture / environmental science article well enough.

## Script And Image Audit

### Scene 0

Sentence:

`버려지던 낙엽이 이제는 토양 오염을 줄이는 농업용 비닐 대체재로 주목받고 있습니다.`

Image:

- Strong natural mood and autumn leaves.
- The black rolls can be read as hay bales, pipe, or film rolls.
- The transformation from leaf to biodegradable film is not explicit enough.

Upgrade target:

- Use a clear before-to-after composition: fallen leaves -> thin translucent mulch film -> soil-covered crop row.
- Add one dominant film sheet/roll, not small ambiguous rolls in the distance.

### Scene 1

Sentence:

`KAIST 연구진은 캠퍼스와 하천 주변에서 모은 낙엽으로, 땅속에서 분해되는 멀칭 필름을 만들었습니다.`

Image:

- Good: people collecting leaves near campus.
- Weak: biodegradable film sample is too small or absent.
- KAIST / research context is generic campus, but acceptable.

Upgrade target:

- Put one researcher holding a transparent film sample in the foreground.
- Keep leaf collection and campus background secondary.

### Scene 2

Sentence:

`멀칭 필름은 잡초를 막고 흙의 수분을 붙잡아 두는 농업용 덮개지만, 기존 제품은 대부분 플라스틱이라 수거와 폐기가 어렵습니다.`

Image:

- Strong agricultural rows and mulch roll.
- It communicates "mulch film" well.
- It does not show the disposal / collection problem.

Upgrade target:

- Use split composition: left clean mulch covering crop rows, right worker struggling with leftover plastic film.
- Or show the same field with one visible loose plastic edge being hard to remove.

### Scene 3

Sentence:

`특히 밭에 남은 비닐 조각은 시간이 지나며 미세플라스틱으로 바뀔 수 있어 농업 현장의 오랜 골칫거리였습니다.`

Image:

- The image looks like muddy or wet soil.
- Plastic fragments and microplastic transition are not readable.
- This is one of the weakest semantic matches.

Upgrade target:

- Show torn white/black plastic fragments embedded in soil, breaking into tiny particles.
- Use a close ground-level view with a small magnifier or cutaway soil layer.

### Scene 4

Sentence:

`연구진은 낙엽에서 나노셀룰로오스를 추출한 뒤 생분해성 고분자와 결합해 새로운 복합 필름을 만들었고, 공정에도 유해한 용매 대신 물을 사용했습니다.`

Image:

- Good lab atmosphere.
- Too generic: bottles and glassware are visible, but leaf fibers, water-based process, and film formation are not explicit.

Upgrade target:

- Add leaf fibers entering a clear beaker, water droplet symbol, and a thin film sheet coming out.
- Avoid generic lab shelves as the main subject.

### Scene 5

Sentence:

`이렇게 만든 낙엽 필름은 자외선을 잘 막으면서도, 14일 동안 토양 수분 손실을 약 5퍼센트 수준으로 억제하는 보습 성능을 보였습니다.`

Image:

- Strong: field and film cover are visible.
- Weak: UV shielding and moisture retention are implied but not visually encoded.

Upgrade target:

- Use sunlight rays blocked by film plus moist soil underneath.
- Add water droplets under the film; no readable numbers needed.

### Scene 6

Sentence:

`실제 재배 실험에서는 이 필름을 사용한 호밀풀이, 필름이 없을 때보다 더 좋은 생장 상태를 나타냈습니다.`

Image:

- Clear comparison layout.
- Strong match overall.
- Could be more concrete if the film-covered plot is visibly protected by mulch film.

Upgrade target:

- Keep split-screen comparison.
- Make film-covered plot and bare-soil plot visually distinct.

### Scene 7

Sentence:

`분해 속도도 빨라서 토양 조건 실험에서 약 115일 만에 34.4퍼센트가 분해됐고, 기존 생분해 필름보다 빠른 편이었습니다.`

Image:

- Looks like dry cracked land.
- It does not show biodegradable film decomposing.
- The core idea "film breaks down in soil over time" is missing.

Upgrade target:

- Show layered soil with film strips gradually fragmenting into organic material.
- Use a subtle time-sequence strip: intact film -> partially broken film -> blended soil.

### Scene 8

Sentence:

`더 중요한 점은 분해 과정에서 식물 독성이 거의 나타나지 않아, 호밀풀과 다채의 발아와 초기 생장을 해치지 않았다는 사실입니다.`

Image:

- Strong, clean sprout image.
- Good match to safe growth.
- Missing the relation to decomposing film residue.

Upgrade target:

- Keep sprouts foreground.
- Add small harmless decomposing film pieces in the soil layer.

### Scene 9

Sentence:

`결국 이번 연구는 쓸모없이 버려지던 낙엽을 고부가가치 농업 소재로 바꾸며, 지속가능한 농업용 플라스틱 대체 기술의 가능성을 보여줬습니다.`

Image:

- Circular economy symbol is visually strong.
- It is more symbolic than literal.
- Good for summary scene, but it could include farm material/film more clearly.

Upgrade target:

- Keep circular leaf motif.
- Add visible thin mulch film or crop rows inside the circular composition.

### Scene 10

Sentence:

`버려지는 잎이 비닐을 대신하는 순간, 친환경 농업은 폐기물 처리와 토양 보전이라는 두 가지 문제를 동시에 풀 수 있게 됩니다.`

Image:

- Beautiful farm future image.
- Weak direct link to waste treatment and soil preservation.
- It could pass as generic clean agriculture.

Upgrade target:

- Show two problem streams converging: leaf waste pile -> mulch film -> healthy protected soil.
- Keep the landscape but make the process visible.

### Scene 11

Sentence:

`작은 낙엽 한 장이 농업의 미래를 바꾸는 소재가 될 수 있다는 점이, 이번 연구의 가장 인상적인 반전입니다.`

Image:

- Strong symbolic close-up.
- The leaf in hand is clear and memorable.
- It does not show film transformation, but as a closing metaphor this is acceptable.

Upgrade target:

- Add the leaf edge subtly becoming a transparent film sheet.

## Codebase Findings

### 1. Domain detection misclassifies science/agriculture as tech

Relevant files:

- `app/services/domain_detection.py`
- `app/services/visual_brief.py`
- `app/services/image_prompting.py`

The current `TECH_NEEDLES` includes broad terms such as `research` and `model`. This caused the KAIST leaf-film article to drift into `tech_documentary` during automatic prompt suggestion. In the preview check, several automatic prompts became "technology interface", "AI brain", or "neural network dashboard" despite the article being about agriculture and environmental materials.

Impact:

- Automatic prompt generation is not reliable for science/environment articles.
- The successful final video depended on manual prompts, not the current automated planner.

Recommendation:

- Split domains more carefully:
  - `tech` for software, AI, GPU, browser, chip, datacenter.
  - `science_materials` for lab process, material transformation, chemistry.
  - `agriculture_environment` for soil, crops, plastic waste, biodiversity, water, field experiments.
- Do not simply delete every broad term. Convert broad needles such as `research`, `model`, and `training` into weighted or co-occurrence rules:
  - `research` + (`ai`, `llm`, `gpu`, `model training`, `inference`) => `tech`
  - `research` + (`soil`, `crop`, `leaf`, `film`, `polymer`) => `agriculture_environment` or `science_materials`
  - `research` alone => neutral/default, not `tech`
- Update `_domain_for_project()` priority so specific editorial domains are evaluated before broad tech fallback:
  - `bible_longform -> news_explainer -> agriculture_environment -> science_materials -> tech -> essay`
- Keep a strong-tech override for explicit AI/GPU/browser/chip clusters so agriculture articles mentioning AI are not lost once co-occurrence scoring is in place.

### 2. Candidate scoring is too prompt-coverage-centric and domain-biased

Relevant file:

- `app/services/comfyui_pipeline.py`

All 12 selected images scored below `0.55`, even though several are visually and semantically decent. The scoring function currently rewards:

- prompt coverage
- `visual_plan` non-fallback metadata
- essay negative vocabulary
- file size sanity
- light vision QA

Manual prompts did not carry rich `visual_plan` metadata and were not in the essay/news domains, so they lost many points. The result was:

- `retry_recommended_selected_images: 12`
- `below_threshold_selected_images: 12`
- render blocked unless `allow_low_quality_generated_images=True`

Impact:

- Good manual/editorial images can be blocked.
- Repair retries can be triggered for the wrong reason.
- The quality score becomes less useful as a real quality indicator.

Recommendation:

- Add score profiles per domain/style:
  - `editorial_science_v1`
  - `agriculture_environment_v1`
  - `simple_diagram_v1`
  - `essay_editorial_v1`
- For manual/article prompts, score `must_show` coverage, image file sanity, and vision QA more heavily.
- For `manual_art_directed` prompts, raise Vision QA contribution from the current light weighting to `0.50+`, because planner metadata is intentionally incomplete or irrelevant.
- Normalize `file_sanity` by domain/style. Editorial science images can be visually valid even when compression and smooth natural surfaces produce smaller files than dense diagram images.
- Detect manual art direction by an explicit source flag or project policy, not only by `visual_plan` absence. This prevents accidental manual mode for broken automatic prompts.
- Do not require essay/news-specific metadata for unrelated domains.

### 3. Low-score repair can make already-good prompts worse

Relevant files:

- `app/workers/image_worker.py`
- `app/services/prompt_repair.py`
- `app/services/prompt_strictifier.py`

Several selected images are `_repair_1` outputs. But the low score often came from scoring metadata gaps, not actual visual failure. In those cases, repair retry can mutate a carefully written manual prompt unnecessarily.

Impact:

- Extra GPU time is spent on low-value retries.
- Manual/art-directed prompts can be diluted.
- The selected result may be worse or only accidentally better.

Recommendation:

- Add retry reasons:
  - `metadata_score_low`
  - `vision_qa_failed`
  - `prompt_coverage_failed`
  - `manual_prompt_needs_review`
- Only auto-repair when there is a concrete prompt or vision issue.
- If score is low only because metadata is missing, store a warning but do not regenerate automatically.
- Change `repair_prompts()` fallback behavior: when `issue_codes` is empty, it should return `should_retry=False` instead of prepending generic text such as `clear visual metaphor`.
- Add a `_is_manual_art_directed_item()` guard in the same spirit as `_is_heavy_retry_item()`. Manual/art-directed prompts should skip automatic repair and record the skip reason in `candidate_reviews`.

### 4. Agriculture / environmental science lacks visual vocabulary

Relevant directories:

- `storage/visual_vocab/`
- `app/services/visual_vocab.py`
- `app/services/visual_planner.py`

The current vocab has strong work for `tech`, `essay`, and `news_explainer`, but this article needed a new visual language:

- leaf waste
- biodegradable mulch film
- soil moisture
- microplastic fragments
- nanocellulose extraction
- water-based process
- seed germination
- plant toxicity
- field comparison
- circular economy

Recommendation:

- Add `storage/visual_vocab/agriculture_environment.json`.
- Add `storage/visual_vocab/science_materials.json`.
- Use these as LLM planner context and as fallback rules.
- Extend the current flat vocab shape with composition fields that the prompt adapter can consume:
  - `concept`
  - `keywords`
  - `icon`
  - `support`
  - `relation`
  - `composition_template`
  - `layout`
  - `avoid`
- Update `_diagram_vocab_matches()` / vocab matching code so `composition_template` and `layout` are not ignored. These fields should drive concrete structures such as `left_to_right_before_after`, `split_comparison`, and `process_flow`.

### 5. The current final image gate has an unsafe manual bypass

Relevant file:

- `app/services/visual_relevance.py`

This video rendered because `allow_low_quality_generated_images=True` was set for the project. That is fine for a supervised test run, but not a healthy production default.

Impact:

- It can hide real mismatches.
- It makes final render quality dependent on operator judgment.

Recommendation:

- Replace this broad bypass with `manual_art_directed=true`.
- Replace the boolean validation decision with an explicit policy result:
  - `strict_generated`
  - `manual_light`
  - `upload_only`
  - `skip_legacy`
- In `manual_light` mode, require a lighter but explicit checklist:
  - image exists
  - sentence hash matches
  - no stale prompt
  - image dimensions valid
  - no vision QA hard fail such as `LOW_RESOLUTION` or `EXTREME_EXPOSURE`
  - skip metadata-only score failures
  - skip strict `must_show` coverage when it is not backed by reliable vision/object detection
- Keep `allow_low_quality_generated_images` only as a temporary legacy migration flag, and make reports label it as `skip_legacy` instead of silently passing.

### 6. Motion is stable but visually static

Relevant files:

- `app/services/render.py`
- `app/services/render_plan.py`
- `app/services/scene_plan.py`

All segments used `still_locked`. This avoided shaking and solved the earlier jitter problem, but the final video can feel more like a slideshow.

Recommendation:

- Keep `still_locked` as the default for generated images.
- Add opt-in `micro_motion_locked`:
  - sub-2% slow push-in
  - integer-frame sampling
  - no per-frame zoompan drift
  - disabled for detail-critical diagrams
- Implement `micro_motion_locked` in `render.py`'s FFmpeg visual filter chain using the existing fixed frame-count strategy. Do not reintroduce the old free-running `zoompan` path that caused shake.
- Account for `render_plan.py` currently using `lock_still=bool(media_path)`, which makes every generated image `still_locked`. Motion selection needs an explicit domain/style override rather than relying on global `kenburns_enabled`.
- Enable micro motion only for photo/editorial agriculture and science scenes; keep `simple_diagram` locked because icon positions and labels are composition-critical.
- Do not return to global `kenburns_enabled` forcing motion over scene intent.

### 7. Diagnostics are close, but not reviewer-friendly enough

Relevant files:

- `app/services/visual_relevance.py`
- `render_report.json`
- `visual_mismatch_report.json`

The report records useful values, but for this case it marked every low-score scene as `diagnosis: pass` because validation was bypassed. The report should still say "manual gate bypassed" and show why the score is low.

Recommendation:

- Add `validation_policy` to each report row:
  - `strict_generated`
  - `manual_light`
  - `upload_only`
  - `skip_legacy`
- Add `score_component_summary` so we can tell whether the issue was prompt coverage, metadata, or vision QA.
- Add a contact-sheet generator as a first-class diagnostic artifact.
- Include sentence text first 40 characters, `candidate_score`, `issue_codes`, and `selected_reason` directly on the contact sheet or adjacent Markdown.

## Upgrade Plan

### P0: Add Agriculture / Science Domain Support

- [x] Add `agriculture_environment` and `science_materials` to domain detection.
- [x] Replace broad single-word tech triggers with co-occurrence or weighted rules for `research`, `model`, and `training`.
- [x] Add explicit tests that `research` alone is not tech, while `research + AI/GPU/model training` is tech.
- [x] Update `_domain_for_project()` priority:
  - `bible_longform`
  - `news_explainer`
  - `agriculture_environment`
  - `science_materials`
  - `tech`
  - `essay`
- [x] Preserve strong-tech override for explicit AI/GPU/browser/chip clusters.
- [x] Add `storage/visual_vocab/agriculture_environment.json`.
- [x] Add `storage/visual_vocab/science_materials.json`.
- [x] Teach `visual_planner.py` to output domain-specific visual templates:
  - `WasteToMaterial`
  - `FieldMulchFunction`
  - `PollutionFragment`
  - `LabExtraction`
  - `MoistureShield`
  - `GrowthComparison`
  - `SoilDecomposition`
  - `NonToxicSprout`
  - `CircularUpcycling`
  - `FutureFarm`

Acceptance:

- The KAIST leaf-film article no longer generates `AI brain`, `neural network dashboard`, or generic `technology interface` prompts.
- Automatic prompts for all 12 sentences contain concrete agriculture/science objects.

### P0: Replace Broad Low-Quality Bypass With Manual Art-Directed Mode

- [x] Replace `allow_low_quality_generated_images` with `manual_art_directed` or narrower equivalent.
- [x] Replace boolean validation gating with an explicit validation policy:
  - `strict_generated`
  - `manual_light`
  - `upload_only`
  - `skip_legacy`
- [x] In `manual_light` mode, keep stale/hash/media checks active.
- [x] Do not block only because candidate score is low when the score is low due to missing planner metadata.
- [x] Still block hard image failures:
  - missing media
  - stale prompt
  - invalid dimensions
  - severe vision QA issue
  - hard prompt/image domain mismatch if detected by reliable text/vision evidence
- [x] Keep `allow_low_quality_generated_images` only as a temporary legacy migration path and report it as `skip_legacy`.

Acceptance:

- This project can render without a broad "allow low quality" escape hatch.
- Reports clearly say whether manual-art-directed validation was used.

### P0: Add Repair Retry Guardrails

- [x] Change `repair_prompts()` so empty `issue_codes` returns `should_retry=False`.
- [x] Add `_is_manual_art_directed_item()` and skip automatic prompt repair for manual/art-directed images.
- [x] Record skipped repair reasons in `candidate_reviews`:
  - `manual_art_directed_skip`
  - `metadata_score_only_skip`
  - `empty_issue_codes_skip`
- [x] Only retry when the failure reason is concrete:
  - `vision_qa_failed`
  - `prompt_coverage_failed`
  - `style_policy_failed`

Acceptance:

- A carefully written manual prompt is not mutated only because metadata score is low.
- Empty issue code retry no longer prepends generic phrases like `clear visual metaphor`.

### P0: Rework Candidate Scoring By Domain

- [x] Add a score profile field to prompt manifest or visual brief.
- [x] Implement `agriculture_environment_v1` candidate score.
- [x] Add a `manual_art_directed_v1` score profile with Vision QA weighted at `0.50+`.
- [x] Normalize `file_sanity` thresholds by domain/style.
- [x] Detect manual art direction via explicit source/policy flags, not only missing `visual_plan`.
- [x] Separate score penalties by reason:
  - `prompt_coverage`
  - `planner_metadata`
  - `vision_qa`
  - `file_sanity`
  - `style_consistency`
- [x] Do not trigger repair retry for `planner_metadata` alone.
- [x] Store score component summaries in `candidate_reviews`.

Acceptance:

- Good manual agriculture images no longer score around `0.24-0.41` solely because they lack essay/news metadata.
- Low scores point to a meaningful fix.

### P1: Add Science/Agriculture Prompt Compiler Templates

- [x] Create prompt templates for environmental science article videos.
- [x] Add an `agriculture_environment` branch to `compile_positive_prompt()`.
- [x] Force sentence-specific first object in the first 20 words.
- [x] Use `before -> after`, `split comparison`, or `process flow` templates where appropriate.
- [x] Use an editorial science base style:
  - `medium wide shot`
  - `natural daylight`
  - `editorial documentary photography`
  - `clean agricultural photography`
  - `soil texture`
  - `natural material closeup`
- [x] Add negative prompt policy:
  - no generic lab shelf
  - no dry desert unless drought is the topic
  - no hay bales when the concept is film roll
  - no unreadable labels
  - no random campus when the sentence is about soil or film
  - no abstract dashboard
  - no circuit diagram
  - no cartoon character
  - no tiny icons

Acceptance:

- Scene 3 produces visible plastic fragments in soil.
- Scene 7 produces visible film decomposition, not generic dry cracked ground.
- Scene 4 shows leaf fibers/water/film output, not only bottles.

### P1: Extend Visual Vocab Composition Fields

- [x] Extend agriculture/science vocab entries with:
  - `composition_template`
  - `layout`
  - `avoid`
- [x] Update vocab matching so these fields are injected into planner/prompt context, not only stored in JSON.
- [x] Add concrete composition templates:
  - `WasteToMaterial`
  - `FieldMulchFunction`
  - `PollutionFragment`
  - `LabExtraction`
  - `SoilDecomposition`
  - `CircularUpcycling`

Acceptance:

- A leaf-waste sentence can produce a left-to-right before/after composition.
- A decomposition sentence can produce a time-sequence or soil-layer composition.

### P1: Add Lightweight Vision QA For Editorial Science Images

- [x] Add image QA issue codes:
  - `MISSING_DOMINANT_FILM_OBJECT`
  - `SOIL_WITHOUT_PLASTIC_FRAGMENT`
  - `LAB_WITHOUT_PROCESS_FLOW`
  - `GENERIC_FIELD_ONLY`
  - `DECOMPOSITION_NOT_VISIBLE`
  - `SYMBOLIC_ONLY_WHEN_LITERAL_REQUIRED`
- [x] Start with text-prompt + image heuristics.
- [x] Stage the QA rollout:
  - V1: text-prompt + image heuristics only. Implemented as the default path.
  - V2: lightweight CLIP image-prompt similarity, CPU or after GPU release. Deferred as an opt-in upgrade, not required for the current automation baseline.
  - V3: opt-in Vision LLM review only for selected candidates. Deferred as an opt-in upgrade, not required for the current automation baseline.
- [x] Avoid semantic object-detection promises in V1 because current `image_quality.py` only measures resolution, entropy, contrast, edge detail, and exposure.

Acceptance:

- Scene 3 and Scene 7 are flagged in V1.
- Scene 6 and Scene 11 pass as acceptable.

### P1: Add Contact Sheet And Audit Report Workflow

- [x] Generate `diagnostic_contact_sheet.jpg` after image generation.
- [x] Add selected sentence first 40 characters, must_show, candidate score, issue codes, and selected_reason to the sheet or adjacent Markdown.
- [x] Add a route or script to regenerate this report on demand.

Acceptance:

- We can inspect all sentence-image pairs without manually opening 12 files.
- Report makes bypassed/low-score decisions obvious.

### P1: Controlled Motion Upgrade

- [x] Add `micro_motion_locked` segment motion.
- [x] Implement it in `render.py`'s FFmpeg filter chain using the existing fixed frame-count render path.
- [x] Keep integer-frame sampling and last-segment duration correction.
- [x] Keep `still_locked` for diagrams and dense text-like imagery.
- [x] Enable only for photo/editorial agriculture and science scenes.
- [x] Add render test to ensure no duration drift and no frame jitter.

Acceptance:

- Generated image videos feel less static without reintroducing zoompan shake.

### P2: Optional Multi-Candidate Selection For Important Scenes

- [x] Generate 2 variants for weak/high-risk scene templates:
  - pollution fragment
  - lab extraction
  - decomposition
  - split comparison
- [x] Select using domain score plus vision QA.
- [x] Keep single candidate for easy scenes to save GPU time.

Acceptance:

- Hard scenes improve without doubling total generation time for every sentence.

## Proposed Implementation Order

1. P0 domain co-occurrence rules and `_domain_for_project()` priority.
2. P0 `repair_prompts()` empty-issue/manual-art guard.
3. P0 `manual_art_directed` light validation policy.
4. P0 candidate scoring profiles, including `manual_art_directed_v1`.
5. P0/P1 agriculture/science vocab plus composition fields.
6. P1 prompt compiler templates for agriculture/environment science.
7. P1 diagnostic contact sheet/report automation.
8. P1 controlled motion.
9. P2 selective multi-candidate generation.

## Regression Tests To Add

- `tests/test_domain_detection.py`
  - `test_research_alone_is_not_tech`
  - `test_research_with_ai_is_tech`
  - KAIST leaf-film article is `agriculture_environment`, not `tech`.
  - AI/GPU/browser articles still resolve as `tech`.
- `tests/test_visual_planner.py`
  - leaf -> mulch film sentence gets `WasteToMaterial`.
  - microplastic sentence gets `PollutionFragment`.
  - decomposition sentence gets `SoilDecomposition`.
- `tests/test_candidate_selection.py`
  - manual-art-directed low metadata score does not auto-repair.
  - true vision QA failure still blocks or retries.
- `tests/test_prompt_repair.py`
  - empty issue codes return `should_retry=False`.
  - manual-art-directed items skip repair and record the skip reason.
- `tests/test_visual_relevance.py`
  - broad low-quality bypass is no longer needed.
  - report row includes `validation_policy`.
  - `manual_light` still blocks missing/stale/invalid image assets.
- `tests/test_render_visual_track.py`
  - `micro_motion_locked` has no duration drift and stable frame count.

## Expected Outcome

The next version should keep the improved image quality from this manual run, but make it automatic. The goal is not simply prettier images; it is a pipeline that can read a science/environment article, choose the right visual grammar, score it fairly, and explain exactly why a generated scene should pass, retry, or fail.
