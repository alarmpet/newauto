# TTS Gender Mismatch Fix Plan

## Goal

Fix the case where selecting a male preset such as `30~40대 남성` still produces a female-sounding sample or final TTS result.

Status: `[In Progress]`

## Confirmed Causes

1. Legacy male preset ids in the Step 3 dropdown were not resolved by the frontend preset logic.
2. The Step 3 form could keep stale values from a previous preset.
3. Preview and full TTS both reused the same stale form payload.
4. Frontend and backend had different preset definitions, so preview and render could diverge.
5. OmniVoice voice design itself is less stable for Korean than for Chinese or English.

## Implementation Status

### Phase 0. Single source of truth for preset content `[Done]`

- Added `/api/tts/presets`.
- Backend now exposes canonical preset order, labels, aliases, preset payloads, and sample text.
- Frontend no longer depends on its own hardcoded preset definitions.

### Phase 1. Deterministic frontend preset selection `[Done]`

- Step 3 now builds the voice dropdown from the backend preset catalog.
- Legacy ids are normalized to canonical ids before being used.
- Loading a project with a legacy male preset now resolves to the canonical male preset.

### Phase 2. Prevent stale form state from overriding preset selection `[Done]`

- Added `ttsFormDirtyAfterPreset` tracking.
- Selecting a preset rewrites all visible TTS controls from the canonical preset definition.
- Preview and full TTS now send the canonical preset id.
- When the user has not edited advanced controls after choosing a preset, the request no longer sends stale overrides.

### Phase 3. Effective profile visibility `[Done]`

- Added an effective profile panel in Step 3.
- Added a warning badge when advanced controls are overriding the chosen preset.

### Phase 4. Regression tests `[Done]`

- Added tests for:
  - preset catalog route
  - legacy male alias normalization
  - single-source preset catalog values
  - runtime Step 3 UI elements

### Phase 5. Korean voice-design ambiguity reduction `[Pending]`

- Deterministic app bugs are fixed first.
- Remaining work is model-quality tuning and evaluation for Korean male/female consistency.
- This still needs structured A/B listening or a reference-based clone workflow.

### Phase 6. Sample regeneration path `[Done]`

- Updated `scripts/generate_voice_samples.py` to use the canonical backend preset catalog and order.
- Regenerated samples can now follow the same preset definitions used by Step 3 and TTS generation.

## Delivered Outcome

- Male legacy presets no longer silently fall through the frontend.
- Male preset selection now rewrites the live form instead of keeping stale female settings.
- Sample preview and full TTS now use the same canonical preset path.
- The UI shows which effective TTS profile will actually be used.

## Remaining Scope

- Model-level Korean voice-design consistency is still a separate tuning task.
- If gender drift remains after these fixes, the next step should be controlled A/B evaluation or clone mode expansion.
