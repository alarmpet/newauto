# Naver Comment Final Image Audit And Recovery Plan

Project: `5717dcffbfb6`

Final output inspected:

- `C:\Users\petbl\newauto\storage\projects\5717dcffbfb6\output.mp4`
- Contact sheet: `C:\Users\petbl\newauto\storage\projects\5717dcffbfb6\diagnostic_contact_sheet.jpg`
- Generated images: `storage/projects/5717dcffbfb6/media/naver_comment_rebuild_scene_*.png`

## Current State

The final render is technically healthy:

- `preflight_ok=True`
- `visual_issues=0`
- `audio_consistency_passed=True`
- `duration_guard_passed=True`
- output duration: `84.76s`
- audio drift: `0.0s`
- max frame drift: `1`

However, the generated images still do not meet the user's actual quality target. They are cleaner than the earlier unrelated car/room images, but many scenes are still too abstract, too busy, or too weakly connected to the exact script sentence.

## Script To Image Audit

### Scene 0

Sentence:

`네이버가 대선을 앞두고 뉴스 댓글 관리 방식을 한 단계 더 바꾸기로 했습니다.`

Image issue:

- Looks like a generic dashboard radar/interface.
- Missing an immediately readable "news article + comment management update" composition.
- Election context is not visually obvious.

Expected:

- Large browser article card.
- Comment panel visibly changing from old mode to new mode.
- Small ballot/calendar/election icon as secondary context.

### Scene 1

Sentence:

`핵심은 특정 기사에서 공감이나 비공감이 비정상적으로 급증하면, 그 흐름을 자동으로 감지하는 기능입니다.`

Image issue:

- Too wide and too schematic.
- Like/dislike spike and automatic detection are not dominant.
- Main subject is scattered into tiny icons.

Expected:

- One central article card.
- Two large reaction counters rising sharply.
- Warning sensor or pulse detector attached to the counters.

### Scene 2

Sentence:

`네이버는 이런 이상 징후를 댓글을 운영하는 언론사에 바로 알리고, 필요한 경우 메일로도 받을 수 있게 했습니다.`

Image issue:

- This is one of the better scenes, but still reads as generic notification/mail.
- The "platform -> newsroom/media company" relationship is weak.

Expected:

- Left: platform monitor detecting abnormal reaction.
- Right: newsroom/media desk receives alert.
- Arrow plus envelope/bell icon.

### Scene 3

Sentence:

`알림을 받은 언론사는 해당 기사 댓글의 정렬 방식을 바꿔, 한쪽 반응이 댓글창을 빠르게 점령하는 상황에 대응할 수 있습니다.`

Image issue:

- Looks like a generic office monitor.
- Comment sorting is not visually central.
- One-sided takeover is almost absent.

Expected:

- Comment list with sort slider/dropdown as the dominant object.
- One side of reaction bubbles crowding in, then being filtered/reordered.

### Scene 4

Sentence:

`쉽게 말해, 짧은 시간 안에 공감 수가 몰리거나 비공감이 폭증하는 움직임을 그냥 두지 않겠다는 뜻입니다.`

Image issue:

- Generic analytics board.
- "Short time", "likes/dislikes", and "spike" are tiny or vague.

Expected:

- Timer icon plus large up/down reaction counters.
- Red/orange spike line and warning badge.

### Scene 5

Sentence:

`이번 조치는 선거를 앞두고 좌표찍기나 조직적 반응 몰이가 여론을 왜곡할 수 있다는 우려를 반영한 것으로 해석됩니다.`

Image issue:

- Abstract network diagram is directionally related, but the story is unclear.
- Public opinion distortion and coordinated targeting are not obvious.

Expected:

- Many small account nodes aiming arrows at one comment box.
- Public opinion scale bending under pressure.
- Election ballot/calendar as secondary context.

### Scene 6

Sentence:

`이용자 입장에서도 의미가 있습니다.`

Image issue:

- Image is visually strong but not sentence-specific.
- It shows a generic data machine, not a user perspective.

Expected:

- Simple user icon in front of a news comment panel.
- Question mark/thinking bubble: "Can I trust this reaction?"
- Keep text unreadable, use icons only.

### Scene 7

Sentence:

`눈앞의 인기 댓글이 정말 자연스러운 반응인지, 아니면 순간적으로 부풀려진 흐름인지 한 번 더 의심해 볼 계기가 생기기 때문입니다.`

Image issue:

- Generic connected document/icon composition.
- Popular comment, inflated reaction flow, and suspicion are not visually separable.

Expected:

- One large popular comment bubble inflating like a balloon.
- User/magnifier/question mark checking whether it is natural.
- Reaction bubbles clustered too quickly around it.

### Scene 8

Sentence:

`다만 이 기능이 모든 조작을 자동으로 막아주는 만능 해법은 아닙니다.`

Image issue:

- Generic monitor/dashboard.
- "Not a perfect blocker" is not clear.
- This should be a limitation metaphor, not another dashboard.

Expected:

- Shield with a few gaps or cracks.
- Some suspicious reaction dots still slipping through.
- Avoid literal readable labels.

### Scene 9

Sentence:

`감지 기준을 얼마나 정교하게 다듬고, 언론사가 실제로 얼마나 빠르게 대응하느냐가 성패를 가를 가능성이 큽니다.`

Image issue:

- Looks like abstract laptop/radar.
- Detection tuning and media response speed are not concrete.

Expected:

- Detection threshold knobs/sliders.
- Fast arrow from alert panel to newsroom response button.
- Stopwatch or speed icon.

### Scene 10

Sentence:

`결국 이번 변화는 댓글을 없애는 방향이 아니라, 댓글 공간의 이상 징후를 더 빨리 드러내고 대응 속도를 높이려는 시도라고 볼 수 있습니다.`

Image issue:

- The strongest direct "comment panel" layout, but still too abstract.
- It does not clearly show "not removing comments, revealing abnormal signs faster".
- Candidate score is only `0.633`, the weakest selected image.

Expected:

- Comment panel remains visible.
- Abnormal signal highlighted early.
- Response-speed arrow moves toward media/operator icon.

## Root Causes

### 1. The gate is text-prompt based, not image-content based

`app/services/comfyui_pipeline.py` scores candidate images mostly from prompt coverage:

- `coverage_pass`
- `must_show_coverage`
- `issue_free`
- `keyword_hits`
- `file_sanity`

This proves the prompt mentioned the right concepts. It does not prove the generated image actually contains those concepts. This is why abstract diagrams pass even when the visual message is weak.

### 2. The current pass threshold is too low for final quality

`app/services/visual_relevance.py` uses:

- `GENERATED_IMAGE_MIN_CANDIDATE_SCORE = 0.55`

The final selected scores were:

- `0.718, 0.717, 0.728, 0.742, 0.724, 0.722, 0.704, 0.700, 0.704, 0.725, 0.633`

Several were marked `borderline`, but preflight still passed. For production, `borderline` should not silently become final.

### 3. Prompt compiler repeats generic diagram scaffolding too heavily

Many prompts repeat:

- `wide centered explainer diagram shot`
- `simple centered explainer icon composition`
- `large browser news article card with comment bubbles clearly visible`
- `policy update arrow and settings gear icon`

This causes scene 0, 1, 6, 7, and 8 to collapse into similar generic dashboards instead of sentence-specific visuals.

### 4. News-explainer visual vocabulary is not role/action structured enough

The current vocab provides nouns and icons, but the prompt needs a strict visual grammar:

- actor
- object
- action
- contrast
- camera/layout
- forbidden alternatives

Example:

Bad:

- `browser news article card with comment bubbles, policy update arrow`

Better:

- `one large news article card on the left, comment list in the center, old sorting icon crossed out, new sorting slider highlighted on the right`

### 5. Simple diagram style still lacks composition constraints

The desired reference style is not just "simple diagram".

It needs:

- few objects
- very large icons
- one central metaphor
- clear arrows
- no dense dashboard panels
- no tiny UI marks
- no abstract radar/circuit compositions

Current negative prompt blocks text and photorealism, but does not strongly block:

- abstract radar dashboard
- dense analytics board
- tiny scattered icons
- generic circuit/network diagram
- decorative UI blueprint

### 6. The audit report has mojibake sentence text

`visual_mismatch_report.md` shows corrupted Korean while the DB project text is normal. This makes review harder and should be fixed so reports always write sentence text from the current project record, not only from stale/corrupted manifest payloads.

## Recovery Plan

### P0: Automate borderline retry before final render

Do not only block borderline images. A block-only policy makes autopilot stop too often. The pipeline should first try one automatic stricter regeneration, then block only if the stricter retry still fails.

- [x] Keep the old `0.55` as a low-quality worker retry threshold.
- [x] Add a stricter final threshold for generated images:
  - `0.72` for `simple_diagram` / `news_explainer`
  - configurable per `quality_mode`
- [x] Treat `selected_reason` containing `borderline` as `needs_strict_retry`.
- [x] Add `app/services/prompt_strictifier.py`.
- [x] The strictifier should:
  - remove abstract/global scaffold phrases
  - keep only the core sentence nouns and actions
  - force one dominant subject
  - force max two secondary icon groups
  - prepend the selected composition template
  - add dense-dashboard and abstract-interface negatives
- [x] In `image_worker.py`, before accepting a borderline selected candidate:
  - run one strict prompt retry
  - store `strict_retry_attempted=True`
  - store `strict_retry_reason=borderline_candidate`
  - store original and strict prompts in `candidate_reviews`
- [x] Add `FINAL_IMAGE_SCORE_TOO_LOW` only after the strict retry/final strict gate fails.

Acceptance:

- Scene 10 with score `0.633` triggers strict retry automatically.
- Any generated image selected as `auto_score_v2:*:borderline` cannot silently render in balanced/exhaustive mode.
- If strict retry succeeds with score >= strict threshold and no diagram QA issue, render may continue.
- If strict retry fails, preflight blocks with `FINAL_IMAGE_SCORE_TOO_LOW`.

### P0: Add structured composition templates for news explainer

- [x] Add `storage/visual_vocab/news_explainer.json`.
- [x] Store each concept as structured fields:
  - `subject`
  - `action`
  - `layout`
  - `must_show`
  - `avoid`
  - `composition_template`
- [x] Add a small set of visual grammar templates:
  - `AlertFlow`: source monitor -> arrow -> newsroom/media receiver
  - `SpikeDetection`: article card + large counters + warning detector
  - `SortingControl`: comment list + sort slider + reordered reaction flow
  - `CoordinationPressure`: many account nodes -> one target comment + bent public opinion scale
  - `UserView`: user icon -> comment panel + question/magnifier
  - `LimitationShield`: imperfect shield + suspicious dots slipping through
  - `SpeedResponse`: tuning knobs/threshold + stopwatch + response arrow
  - `PreserveAndReveal`: comment space remains + abnormal signal highlighted
- [x] Make `visual_planner.py` output `composition_template` for `news_explainer`.
- [x] Make `image_prompting.py` compile template-specific layouts before style suffixes.
- [x] Cover at least:
  - news comment management update
  - abnormal like/dislike spike
  - media company alert
  - comment sorting change
  - coordinated reaction campaign
  - user suspicion
  - not a perfect blocker
  - detection tuning and response speed
  - comment space preserved

Acceptance:

- Sentence 6 no longer gets a generic platform/dashboard prompt.
- Sentence 8 gets shield/gap/slipping dots, not a monitor dashboard.
- Sentence 10 gets comment space preserved + abnormal signal + fast response.
- Each news scene has one explicit template name in `scene_visual_plan.json`.

### P0: Reduce generic scaffold repetition

- [x] In `image_prompting.py`, cap repeated global scaffold phrases to one short style suffix.
- [x] Move sentence-specific `must_show` to the first 20 words of `prompt_g`.
- [x] For `simple_diagram`, enforce:
  - one dominant subject
  - max three icon groups
  - no dense dashboard
  - no tiny icon grid
- [x] Add blocklist phrases:
  - `abstract radar dashboard`
  - `dense analytics dashboard`
  - `tiny scattered icons`
  - `decorative circuit board`
  - `generic blueprint interface`
  - `complex infographic grid`

Acceptance:

- The positive prompt for each scene begins with its unique subject/action, not the shared style phrase.
- Repeated primary terms in `prompt_quality_report.json` are treated as issue codes for news explainer projects.

### P1: Add text-based composition QA before image generation

- [x] Extend `prompt_quality.py` with news-specific issue codes:
  - `NEWS_DIAGRAM_TOO_GENERIC`
  - `NEWS_COMMENT_PANEL_MISSING`
  - `REACTION_SPIKE_NOT_DOMINANT`
  - `USER_VIEWPOINT_MISSING`
  - `LIMITATION_METAPHOR_MISSING`
  - `DENSE_DASHBOARD_RISK`
- [x] Fail prompts that contain repeated generic scaffolding but lack sentence-specific nouns/actions.
- [x] Add unit coverage for the news-specific prompt quality path.

Acceptance:

- Current scene 6, 8, and 10 prompt patterns fail before generation.

### P1: Add lightweight post-generation image QA

V1 should not require a heavy vision LLM by default.

- [x] Add diagram-specific computer-vision heuristics in `image_quality.py`.
- [x] Existing photo-oriented checks should not be reused blindly; diagram mode needs inverted logic:
  - edge density too high -> dense dashboard risk
  - too many tiny connected components -> tiny icon clutter
  - dominant object area too small -> weak focal subject
  - too much blank UI framing without central object -> generic dashboard risk
- [x] Add simple thresholds per style:
  - `simple_diagram`: high edge density is bad when spread across the full frame
  - `simple_diagram`: a central object should occupy a minimum normalized area
  - `simple_diagram`: many small components should reduce score
  - non-diagram/photo modes keep the current detail/contrast logic
- [x] Add `vision_qa_issue_codes`:
  - `DENSE_DIAGRAM_CLUTTER`
  - `DOMINANT_SUBJECT_TOO_SMALL`
  - `ABSTRACT_UI_NO_CLEAR_SUBJECT`
  - `TINY_ICON_GRID`
  - `GENERIC_DASHBOARD_LAYOUT`
- [x] Lower final score when these issue codes appear.

Acceptance:

- Scene 0/1/4/5/7/9 style abstract dashboards are flagged as clutter or weak focal subject.

### P1: Optional vision LLM review for final candidates

- [ ] Add opt-in `quality_mode=exhaustive` review:
  - input: image + sentence + must_show
  - output: `matches_sentence`, `missing_core_objects`, `plain_language_reason`
- [ ] Only run for selected candidates, not every candidate.
- [ ] Use it after image generation and before render.

Acceptance:

- If an image is a generic dashboard, the review says the core sentence object is missing and triggers regeneration.

### P1: Improve retry and candidate strategy

- [x] Generate a strict retry candidate for `news_explainer`/`simple_diagram` when the selected score is below strict final threshold.
- [x] Retry with a stricter prompt:
  - remove all generic scaffold phrases
  - use one sentence-specific composition template
  - add dense-dashboard negatives
- [x] Store retry reason in `candidate_reviews`.

Acceptance:

- Borderline images are regenerated automatically instead of becoming final.

### P2: Fix audit report encoding/source

- [x] In `visual_mismatch_report`, always prefer `project["sentences"][idx]` for sentence text.
- [x] Fall back to manifest sentence only when project sentence is missing.
- [x] Write Markdown reports with explicit UTF-8 and avoid reusing any mojibake text from stale prompt manifests.
- [x] Add a `sentence_source` field in JSON rows:
  - `project_record`
  - `manifest_fallback`
- [x] Add regression test with Korean text.

Acceptance:

- `visual_mismatch_report.md` shows readable Korean for all scenes.
- `naver-comment-final-image-audit-plan.md` and future audit docs should use Project Record sentences for review tables.

## Regeneration Criteria

Only regenerate the final video after these checks pass:

- [ ] `visual_relevance` passes.
- [ ] `tts_consistency` passes.
- [ ] no selected image remains `borderline` after strict retry.
- [ ] every selected image score >= strict threshold.
- [ ] prompt quality report has no news-specific issue code.
- [ ] diagram-specific image QA has no dense-dashboard / tiny-icon / weak-subject issue.
- [ ] visual mismatch report shows readable Korean and no stale/missing mappings.

## Updated Implementation Order

### Phase 1: Report source fix

- [x] Fix `visual_mismatch_report` to use `project["sentences"]`.
- [x] Add Korean regression test.
- [x] Regenerate the report for `5717dcffbfb6`.

Reason:

- This is small, low risk, and makes all later debugging trustworthy.

### Phase 2: Composition templates and strict prompt compiler

- [x] Add `storage/visual_vocab/news_explainer.json`.
- [x] Add `composition_template` to the news visual plan path.
- [x] Add template rendering in `image_prompting.py`.
- [x] Add strictifier service for borderline retry prompts.

Reason:

- Prompt quality must improve before regenerating more images, otherwise ComfyUI simply produces cleaner versions of the same abstract dashboard problem.

### Phase 3: Borderline retry automation

- [x] Add strict final threshold by style/domain.
- [x] Wire `borderline -> strict_retry -> accept/block` into `image_worker.py`.
- [x] Persist retry metadata in `candidate_reviews`.
- [x] Add tests proving `borderline` no longer silently reaches final render.

Reason:

- This preserves autopilot behavior while preventing bad final outputs.

### Phase 4: Diagram Vision QA V1

- [x] Add diagram-specific heuristics to `image_quality.py`.
- [x] Penalize dense dashboards, tiny icon grids, and weak central subjects.
- [x] Feed these issues into candidate score and final gate.

Reason:

- Text-based prompt coverage alone cannot distinguish a good diagram from a generic UI blueprint.

### Phase 5: Regenerate target video

- [ ] Rebuild prompts for all 11 scenes.
- [ ] Regenerate images with strict retry enabled.
- [ ] Verify no `borderline` selections remain.
- [ ] Re-render final video only after visual and TTS gates pass.

## Immediate Manual Prompt Targets

If regenerating before all code changes, use these scene prompts as the target direction:

1. `one large browser news article card with a comment panel, old comment management icon turning into a new safer mode, small ballot calendar icon in the corner, simple flat explainer diagram, no text`
2. `one article card with two giant reaction counters, thumbs up and thumbs down bars shooting upward, warning sensor circle detecting abnormal spike, simple flat diagram, no text`
3. `platform monitor detects abnormal comments and sends alert arrow to newsroom desk, envelope and bell icons, simple flat diagram, no text`
4. `large comment list with sort slider highlighted, one-sided reaction bubbles crowding the list then being reordered, media operator icon, simple flat diagram, no text`
5. `timer icon beside giant thumbs up and thumbs down counters spiking suddenly, warning badge, article card in background, simple flat diagram, no text`
6. `many small account nodes aiming arrows at one comment box, public opinion scale bending under pressure, small ballot icon, simple flat diagram, no text`
7. `single user icon looking at a news comment panel with a question mark bubble, trust and doubt symbols, simple flat diagram, no text`
8. `popular comment bubble inflating like a balloon while user checks it with magnifier, reaction bubbles clustering too fast, simple flat diagram, no text`
9. `shield with small gaps, suspicious reaction dots slipping through, automatic blocker icon crossed out, simple flat diagram, no text`
10. `detection threshold knobs and stopwatch, alert arrow moving quickly to newsroom response button, simple flat diagram, no text`
11. `comment panel remains visible while abnormal signal is highlighted early, fast response arrow to media operator, simple flat diagram, no text`

