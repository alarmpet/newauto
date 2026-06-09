# Naver Comment Test Video Diagnosis Plan

## Scope

- Project: `5717dcffbfb6`
- Video: `C:\Users\petbl\newauto\storage\projects\5717dcffbfb6\output.mp4`
- Main failures:
  - Generated images do not explain the script's news/comment/election context.
  - The final render accepted image candidates that were already marked as retry-worthy.
  - OmniVoice uses the same preset and seed in metadata, but the final audio still sounds like the speaker changes per sentence.

## Confirmed Findings

### 1. Bad images were already detected, then bypassed

`body_image_mappings` shows all selected image candidates have low scores:

- Sentence 0: `candidate_score=0.3658`, `selected_reason=auto_score_v2:0.37:retry_recommended`
- Sentence 1: `candidate_score=0.2964`, `selected_reason=auto_score_v2:0.30:retry_recommended`
- Sentence 2: `candidate_score=0.2976`, `selected_reason=auto_score_v2:0.30:retry_recommended`
- Sentence 10: `candidate_score=0.2091`, `selected_reason=auto_score_v2:0.21:retry_recommended`

The render quality gate only blocks generated image mappings when `visual_source_mode == "comfyui_auto"`. This project was switched to `hybrid`, so `validate_generated_image_mappings()` returned no issues and the failed candidates were allowed into `output.mp4`.

Current code blind spot:

- `app/services/visual_relevance.py::validate_generated_image_mappings()` returns `[]` immediately when `project["visual_source_mode"] != "comfyui_auto"`.
- That means `hybrid` mode can contain ComfyUI-generated mappings but skip ComfyUI quality validation entirely.
- This is not just a weak prompt issue. It is a workflow gate issue: low-score generated images can become final render assets.

Root files:

- `app/services/visual_relevance.py`
- `app/services/render.py`
- `storage/projects/5717dcffbfb6/image_prompts_manifest.json`

### 2. LLM scene planning only succeeded for one sentence

`scene_visual_plan.json` has 11 entries, but only sentence 0 has a real `llm_repair` plan. Sentences 1-10 are `source=fallback`.

That means most prompts did not receive sentence-specific visual intent such as:

- article/comment interface
- like/dislike spike
- abnormal reaction detection
- media company alert
- mail notification
- comment sorting change
- coordinated reaction campaign
- public opinion distortion

Instead, fallback produced generic targets such as:

- `single everyday object in a quiet realistic room`
- `quiet realistic environment`
- `smartphone notifications, morning room`
- `compass on a folded map, quiet road fork`

This directly explains the attached screenshots:

- The "media company alert / email" sentence became abstract frames and a vague envelope-like geometry.
- The "like/dislike spike detection" sentence became a 3D object with no news/comment/detection relation.
- The "comment management change before election" sentence became a generic company/building/blueprint symbol, not a news comment interface.

Root files:

- `app/services/visual_planner.py`
- `app/services/image_prompting.py`
- `storage/projects/5717dcffbfb6/scene_visual_plan.json`

### 3. News/comment domain vocabulary is missing

`storage/visual_vocab/diagram.json` currently covers AI, model training, GPU, browser automation, comparison, path, schedule, effort, notification. It does not cover the actual article domain:

- news article
- comment section
- like/dislike reaction
- abnormal spike
- election context
- media company/editorial desk
- alert/email delivery
- comment sorting
- coordinated manipulation
- public opinion distortion

Because the vocabulary has no relevant concepts, `_apply_simple_diagram_brief()` falls back to generic diagram language.

Root files:

- `storage/visual_vocab/diagram.json`
- `app/services/image_prompting.py`
- `app/services/prompt_compiler.py`

### 4. Simple diagram prompt has style collisions

The project requested `simple_diagram`, but prompts still contain realistic/camera phrases such as:

- `medium wide shot`
- `35mm lens`
- `sharp focus`
- `natural color`
- `detailed real-world textures`

The quality report correctly flags `DIAGRAM_STYLE_COLLISION`, but repair does not converge before render. In several prompts, the negative prompt contains the very terms that the quality checker treats as avoid hits, producing noisy failure reports and making it hard to tell what matters.

Current code bug:

- `app/services/image_prompting.py::_repair_quality_issues()` adds `35mm lens, sharp focus, natural color, detailed real-world textures` whenever `MISSING_CAMERA_TECHNICAL_SLOT` is present.
- This happens even for `simple_diagram`.
- As a result, a user-selected flat explainer style can be repaired into a mixed prompt containing both diagram instructions and realistic camera/photo anchors.
- That collision increases the chance of abstract 3D shapes, vague interior objects, and non-explanatory geometry.

Root files:

- `app/services/prompt_compiler.py`
- `app/services/prompt_quality.py`
- `app/services/prompt_repair.py`

### 5. TTS metadata is consistent, audible voice is not guaranteed

`tts_run_manifest.json` shows every sentence uses:

- `voice_preset=male-announcer-40s-50s`
- `mode=design`
- `instruct=male, middle-aged, moderate pitch`
- `seed=1445487633`
- `seed_mode=fixed`
- same `num_step`, `guidance_scale`, `language`

So this is not the old "auto mode empty instruct" failure. The likely current failure is OmniVoice sentence-by-sentence independent generation: the same seed and instruction are applied per sentence, but there is no speaker embedding/reference lock or audible similarity check across generated clips.

Current implementation detail:

- `app/services/tts.py::run_tts_job()` loops over sentences and calls `_synthesize_one()` once per sentence.
- `_effective_sentence_profile()` correctly keeps the same seed when `seed_mode == "fixed"`.
- `_synthesize_one()` applies the seed and calls `model.generate(text=text, **kwargs)`.
- There is no audio-level check after each clip is generated, so metadata consistency is treated as enough even when the audible voice drifts.

Root files:

- `app/services/tts.py`
- `storage/projects/5717dcffbfb6/tts/tts_run_manifest.json`

## Fix Plan

### P0. Stop failed image candidates from becoming final video

1. Make render/preflight block `IMAGE_PROMPT_QUALITY_FAILED` and low `candidate_score` for all auto-generated image mappings, including `hybrid`, when the mapping was generated by ComfyUI.
2. Add a hard threshold:
   - fail render if selected candidate has `retry_recommended == true`
   - fail render if `candidate_score < 0.55`
   - allow override only through an explicit debug flag such as `allow_low_quality_generated_images=true`
3. Add render report fields:
   - `image_quality_gate_passed`
   - `blocked_sentence_indices`
   - `lowest_candidate_score`
   - `visual_source_mode_gate_reason`

Acceptance:

- The current project must fail preflight/render instead of producing a "done" video when the same low-score images are selected.
- `hybrid` mode should still allow user-uploaded images, but ComfyUI-generated mappings inside `hybrid` must be validated as generated assets.
- `validate_generated_image_mappings()` must no longer use `visual_source_mode` alone as the bypass condition.

Implementation notes:

- Detect generated mappings by metadata, not only project mode:
  - mapping has `prompt_id`
  - mapping has `candidate_score`
  - mapping has `manifest_sentence_hash`
  - mapping exists in `image_prompts_manifest.json`
- If a generated mapping is present, run the same prompt quality and candidate review checks used for `comfyui_auto`.
- Keep a narrow escape hatch for deliberate manual debugging only.

### P0. Add news/comment/election diagram vocabulary

Add `news_comment_policy` concepts to `storage/visual_vocab/diagram.json`:

- `news comment management`
  - keywords: news, article, comment, comments, 댓글, 기사, 뉴스, 댓글창
  - icon: browser news article card with comment bubbles
  - support: settings gear or policy update arrow
  - relation: news article comment panel changing to a safer management mode
- `reaction spike detection`
  - keywords: 공감, 비공감, like, dislike, spike, 급증, 폭증, 감지
  - icon: thumbs up and thumbs down counters rising sharply
  - support: warning sensor or anomaly detector icon
  - relation: abnormal reaction spike detected beside an article card
- `media company alert`
  - keywords: 언론사, 알림, 메일, notification, email, press, newsroom
  - icon: alert arrow from platform monitor to newsroom desk icon
  - support: envelope and bell icon
  - relation: platform sends abnormal comment alert to media operator
- `comment sorting control`
  - keywords: 정렬, sorting, 댓글 정렬, 대응, 관리 방식
  - icon: comment list with sort slider
  - support: filter funnel and direction arrow
  - relation: media operator changes comment sorting to reduce one-sided takeover
- `coordinated reaction manipulation`
  - keywords: 좌표찍기, 조직적, 여론, 왜곡, manipulation, coordinated, election
  - icon: many small nodes pointing at one comment panel
  - support: public opinion scale bending under pressure
  - relation: coordinated reaction flow pushing public opinion off balance

Acceptance:

- For this 11-sentence script, every sentence must get at least one domain-specific `must_show` item instead of `single everyday object in a quiet realistic room`.
- The attached screenshot cases should map to visible concepts:
  - media alert/email sentence -> newsroom or press desk icon plus bell/envelope alert
  - reaction spike sentence -> like/dislike counters plus anomaly sensor
  - comment management sentence -> article card/comment panel plus update arrow

### P0. Repair the scene planner count and fallback behavior

1. In `visual_planner.py`, treat partial LLM output as incomplete, not successful:
   - if parsed JSON item count is less than sentence count, run a targeted repair prompt for missing indices
   - if still incomplete, use domain-aware fallback, not generic essay fallback
2. Add a new project domain path:
   - `news_explainer`
   - triggered by Korean/English terms such as `뉴스`, `기사`, `댓글`, `언론사`, `공감`, `비공감`, `선거`, `여론`, `정렬`
3. For `news_explainer`, load the diagram/news vocabulary and prefer `simple_diagram` by default.
4. Add a project-level quality report issue:
   - `VISUAL_PLAN_PARTIAL_LLM_OUTPUT`
   - `VISUAL_PLAN_FALLBACK_RATE_HIGH`
   - `NEWS_DOMAIN_VOCAB_MISSING`

Acceptance:

- `scene_visual_plan.json` source distribution should show 11 non-generic entries or clearly identify failed indices before image generation starts.
- Fallback for `news_explainer` must be domain-aware, not essay fallback.
- Fallback must never emit `single everyday object in a quiet realistic room` for a sentence containing news/comment/election terms.

Implementation notes:

- Add `is_news_explainer_domain(project, text)` in `app/services/domain_detection.py` or extend the current domain helper cleanly.
- Update `_domain_for_project()` in `app/services/visual_planner.py` to return `news_explainer` before defaulting to `essay`.
- Add a news-specific fallback token function:
  - comments -> article card with comment bubbles
  - 공감/비공감/급증 -> like/dislike spike counters
  - 언론사/메일/알림 -> alert arrow to newsroom/envelope
  - 정렬/대응 -> comment sort slider
  - 여론/좌표찍기/조직적 -> coordinated nodes pushing a public opinion scale

### P0. Remove diagram style collisions

1. In `prompt_compiler.py`, do not append camera/photo terms when `_is_simple_diagram_brief()` is true.
2. In `image_prompting.py`, `_repair_quality_issues()` must not add `35mm lens`, `sharp focus`, `natural color`, or `detailed real-world textures` for simple diagram mode.
3. In `prompt_quality.py`, separate true negative-prompt omissions from expected negative terms so `avoid_hits` does not drown out the useful failure reason.
4. Add a diagram-safe technical anchor set:
   - allowed: `flat vector icon`, `clean outline`, `centered composition`, `large simple symbols`, `plain background`
   - banned: `35mm lens`, `sharp focus`, `natural color`, `detailed real-world textures`, `cinematic editorial photography`

Acceptance:

- Simple diagram prompts must not contain `35mm lens`, `photorealistic`, `natural color`, `detailed real-world textures`, or `realistic room`.
- `DIAGRAM_STYLE_COLLISION` should be zero for this project after prompt generation.
- `_repair_quality_issues()` must branch by style before applying camera/technical repair.

Implementation notes:

- If `_is_simple_diagram_brief()` and `MISSING_CAMERA_TECHNICAL_SLOT` appears, do not add camera anchors.
- Either ignore that issue for simple diagrams or replace it with `DIAGRAM_LAYOUT_ANCHOR_MISSING`.
- For simple diagrams, repair with:
  - `flat icon diagram`
  - `few objects only`
  - `one central symbol and two supporting icons`
  - `no realistic lighting`

### P0. Build a sentence-image mismatch audit for generated projects

Create a report that maps each sentence to:

- sentence text
- core meaning
- must_show
- final positive prompt
- selected image path
- candidate score
- issue codes
- selected reason
- one-line human-readable diagnosis

For this project, expected diagnoses include:

- "comment/reaction/news terms missing from prompt"
- "fallback generic object used"
- "candidate selected despite retry recommendation"
- "diagram style collision"

Acceptance:

- A single JSON or Markdown report can explain why each attached screenshot is unrelated without manually opening the DB.
- The report should be generated automatically after image generation and again after render.
- The report should include project-level summary counts:
  - total sentences
  - fallback scene plans
  - retry-recommended selected images
  - below-threshold selected images
  - diagram style collisions
  - domain vocab misses

Proposed output:

- `storage/projects/{project_id}/visual_mismatch_report.md`
- `storage/projects/{project_id}/visual_mismatch_report.json`

### P1. Improve image repair loop

1. When `candidate_score < threshold`, generate a repair prompt using issue-specific rules:
   - `NEWS_COMMENT_DOMAIN_MISSING`: prepend article card/comment panel/reaction counter terms
   - `ABSTRACT_SHAPE_DRIFT`: add "not abstract architecture, not decorative geometry"
   - `DIAGRAM_STYLE_COLLISION`: remove camera/photo terms, reinforce flat icons
   - `CORE_OBJECT_MISSING`: prepend `must_show` as first slots in `prompt_g`
2. Increase repair retry only for lightweight prompt-only ComfyUI jobs.
3. Stop after retry and mark the project as image generation failed if no candidate passes threshold.

Acceptance:

- The worker should not leave `retry_recommended=true` as a soft warning only. It must either repair successfully or block final render.

### P1. Voice consistency guard for OmniVoice

1. Keep the existing manifest-level policy guard:
   - all sentences must share `voice_preset`
   - `mode == design`
   - `instruct` is non-empty
   - `seed_mode == fixed`
   - same `seed`, `language`, `num_step`, `guidance_scale`
2. Add a second, audio-level consistency check:
   - run a short 3-sentence test
   - compute speaker similarity with a lightweight speaker embedding model if available
   - if unavailable, at least report spectral/pitch summary drift per sentence
3. Add an OmniVoice consistency mode:
   - Preferred: synthesize the full narration as one passage, then split by timings if OmniVoice handles long Korean text reliably.
   - Fallback: generate one anchor/reference voice clip and use the closest available OmniVoice clone/reference path for each sentence.
   - Last resort: keep sentence-by-sentence generation but fail if audio-level drift exceeds a threshold.

Acceptance:

- A project can no longer pass as "voice consistent" based only on equal seed/instruct metadata.
- The first implementation can be pitch/spectral drift reporting if speaker embedding is too heavy for the local environment.
- Full-passage synthesis should be tested behind an option before becoming default because long Korean narration may create timing or memory issues.

Implementation notes:

- Add `tts_consistency_report.json` beside `tts_run_manifest.json`.
- Include per-sentence:
  - duration
  - mean pitch estimate or `null`
  - spectral centroid estimate
  - relative drift against sentence 0 or an anchor clip
  - pass/fail reason
- Add project-level fields:
  - `metadata_consistent`
  - `audio_consistency_checked`
  - `audio_consistency_passed`
  - `recommended_tts_mode`

### P1. Regenerate the Naver article video after fixes

Regeneration criteria:

- Use `visual_source_mode=comfyui_auto` or another strict auto-generated mode, not `hybrid` bypass.
- Use `style_preset=simple_diagram`.
- Require no `IMAGE_PROMPT_QUALITY_FAILED`.
- Require candidate score >= 0.55 for every selected image.
- Require a passed TTS consistency report.
- Produce a fresh `output.mp4` only after all gates pass.

## Expected Visual Direction For This Article

The target style should be simple and explanatory, not cinematic or symbolic room scenes:

- Scene 0: news article card with comment panel, policy update arrow, election ballot icon in background.
- Scene 1: thumbs-up/thumbs-down counters sharply rising beside an anomaly detector.
- Scene 2: platform monitor sends alert arrow to newsroom desk and envelope icon.
- Scene 3: comment list with sort slider changing order, one-sided reaction wave being reduced.
- Scene 4: short timer plus reaction counters surging, warning badge.
- Scene 5: coordinated nodes targeting one comment panel, public opinion scale bending.
- Scene 6: user icon viewing comment panel with a small question mark bubble.
- Scene 7: popular comment bubble inflating, user checks whether it is natural.
- Scene 8: shield with gaps: "not a perfect blocker" visualized without readable text.
- Scene 9: tuning knobs for detection threshold plus fast response arrow to newsroom.
- Scene 10: abnormal signal revealed early, response speed arrow, comment space preserved.

## Priority

1. Block low-quality generated images from render in `hybrid`.
2. Fix partial LLM visual planner output and add `news_explainer` domain vocabulary.
3. Remove simple diagram style collisions.
4. Add image mismatch audit report.
5. Add audio-level OmniVoice consistency guard.
6. Regenerate this video only after the gates pass.

## Updated Implementation Order

### Step 1: Gate correctness

- [x] Fix `validate_generated_image_mappings()` so generated mappings are validated in both `comfyui_auto` and `hybrid`.
- [x] Add low-score and `retry_recommended` selected image blocking.
- [x] Add regression tests around `hybrid` with generated mappings.

### Step 2: Prompt/style correctness

- [x] Fix simple diagram repair so camera/photo anchors are never inserted.
- [x] Add tests for simple diagram prompt repair behavior through `suggest_image_prompt()`.
- [x] Add prompt-quality tests proving `DIAGRAM_STYLE_COLLISION` is resolved.

### Step 3: News visual planning

- [x] Add `news_explainer` domain detection.
- [x] Extend `diagram.json` with news/comment/election concepts.
- [x] Add domain-aware fallback entries for missing LLM planner output.
- [x] Add unit tests for news/comment domain detection and fallback.

### Step 4: Debuggability

- [x] Generate `visual_mismatch_report`.
- [x] Write `visual_mismatch_report.json` and `visual_mismatch_report.md` during preflight/render validation.

### Step 5: Voice consistency

- [x] Add TTS metadata consistency check first.
- [x] Add lightweight audio drift report.
- [x] Add estimated pitch drift to the lightweight audio report so obvious sentence-level voice shifts no longer pass on spectral/RMS data alone.
- [x] Add full-passage OmniVoice synthesis behind an option.

### Step 6: Regeneration

- [x] Rebuild image prompts.
- [x] Regenerate images without quality-gate bypass.
- [x] Run preflight.
- [ ] Generate final video only if image and TTS gates pass.

## Implementation Result 2026-04-30

- `hybrid` no longer bypasses generated image validation when mappings contain ComfyUI metadata.
- Selected images below `0.55` now raise `IMAGE_CANDIDATE_SCORE_LOW`.
- Selected images marked `retry_recommended` now raise `IMAGE_CANDIDATE_RETRY_RECOMMENDED`.
- User-uploaded `hybrid` mappings without generated-image metadata are not blocked.
- `simple_diagram` prompt repair no longer injects photo/camera anchors for missing camera technical slots.
- `news_explainer` domain detection and fallback tokens now cover news article comments, reaction spike detection, media alerts, comment sorting, and coordinated manipulation.
- `visual_mismatch_report.json` and `visual_mismatch_report.md` are generated for project audits.
- `tts_consistency_report.json` is generated beside the TTS manifest with metadata consistency and lightweight RMS/spectral drift fields.
- Existing failed project `5717dcffbfb6` now produces 33 visual relevance issues instead of passing silently.

Verification:

- `python -m unittest tests.test_visual_relevance tests.test_image_prompting tests.test_prompt_compiler tests.test_prompt_quality tests.test_domain_detection tests.test_visual_planner tests.test_tts_pipeline`
- `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## Follow-up Result 2026-05-01

- Raised `scene_visual_plan.json` cache version to `3`, so existing generic fallback plans are invalidated after introducing `news_explainer`.
- Rebuilt project `5717dcffbfb6` prompt manifest with `style_preset=simple_diagram`.
- New prompt manifest result:
  - `11/11` prompts generated
  - `11/11` keyword coverage checks pass
  - all prompts use `news_explainer` domain
- Existing selected images still fail, as intended:
  - `11` x `IMAGE_CANDIDATE_SCORE_LOW`
  - `11` x `IMAGE_CANDIDATE_RETRY_RECOMMENDED`
- Preflight now fails on visual relevance instead of allowing final render.
- TTS consistency report now includes `estimated_pitch_hz` and `max_estimated_pitch_relative_drift`.
- Existing `5717dcffbfb6` TTS report now flags:
  - `metadata_consistent=True`
  - `audio_consistency_checked=True`
  - `audio_consistency_passed=False`
  - `max_estimated_pitch_relative_drift=0.5293`
  - `recommended_tts_mode=full_passage_or_reference_voice`

Generated/updated project artifacts:

- `storage/projects/5717dcffbfb6/image_prompts_manifest.json`
- `storage/projects/5717dcffbfb6/prompt_quality_report.json`
- `storage/projects/5717dcffbfb6/visual_mismatch_report.json`
- `storage/projects/5717dcffbfb6/visual_mismatch_report.md`
- `storage/projects/5717dcffbfb6/tts/tts_consistency_report.json`

Verification:

- `python -m unittest tests.test_visual_relevance tests.test_image_prompting tests.test_prompt_compiler tests.test_prompt_quality tests.test_domain_detection tests.test_visual_planner tests.test_tts_pipeline`
- `.\omnivoice_env\Scripts\python.exe -m mypy app tests`

## Follow-up Result 2026-05-01 Final Pass

- Regenerated the `5717dcffbfb6` ComfyUI image batch with:
  - `template_id=txt2img_sdxl_basic`
  - `style_preset=simple_diagram`
  - `lora_name=""`
  - `lora_strength=0.0`
- New generated image validation result:
  - `11/11` mappings present in `body_image_mappings`
  - selected candidate scores: `0.718, 0.717, 0.728, 0.742, 0.724, 0.722, 0.704, 0.700, 0.704, 0.725, 0.633`
  - `validate_generated_image_mappings()` reports `0` issues
- Rebuilt `scene_plan` and `render_plan` from the regenerated image mappings.
- Fixed scene timing so inter-sentence silence is assigned to the current scene instead of accumulating on the final segment:
  - `scene_plan.total_duration=87.671`
  - `render_plan.total_duration=87.671`
  - final render max frame drift is `1` frame
- Re-rendered diagnostic output:
  - `C:\Users\petbl\newauto\storage\projects\5717dcffbfb6\output.mp4`
  - duration `87.666667s`
  - duration guard passed with `0.004333s` drift
  - render report uses `naver_comment_rebuild_scene_*.png` media
- Added `tts_consistency` to preflight so sentence-level voice drift is visible before render:
  - current project fails this check
  - reason: `pitch drift 0.53`, `spectral drift 0.33`
  - recommended mode remains `full_passage_or_reference_voice`

Important status:

- Image mismatch and render timing issues are fixed for this diagnostic pass.
- TTS was regenerated with `synthesis_mode=full_passage`, so OmniVoice is called once for the whole narration and then split into sentence clips.
- The final output is now fully gated: preflight passes, visual relevance passes, and TTS consistency passes.

Final validation:

- `preflight_ok=True`
- `visual_issues=0`
- `audio_consistency_passed=True`
- `recommended_tts_mode=full_passage`
- `output_duration_sec=84.76`
- `audio_duration_sec=84.76`
- `duration_drift_sec=0.0`
- `max_abs_drift_frames=1`
- final output: `C:\Users\petbl\newauto\storage\projects\5717dcffbfb6\output.mp4`

Verification:

- `python -m unittest tests.test_scene_plan tests.test_render_plan tests.test_render_visual_track tests.test_visual_relevance`
- `python -m unittest tests.test_feature_workflow tests.test_scene_plan tests.test_visual_relevance tests.test_tts_pipeline`
- `python -m unittest tests.test_tts_pipeline tests.test_tts_presets tests.test_feature_workflow`
- `python -m unittest tests.test_render_visual_track tests.test_feature_workflow tests.test_tts_pipeline`
- `.\omnivoice_env\Scripts\python.exe -m mypy app tests`
