# Pipeline Manifest Artifact Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the pipeline manifest record real visual prompt, selected image attempt, and TTS timing artifacts so Studio can inspect the current production contract instead of only raw worker state.

**Architecture:** Extend `app/services/pipeline_manifest.py` with small pure update helpers, then call those helpers from prompt manifest generation, image import, and TTS artifact sync points. Keep DB persistence centralized through `db.update_project(..., pipeline_manifest=...)` and expose the recorded artifacts through existing `/workflow-status`.

**Tech Stack:** Python 3.10, FastAPI, SQLite JSON fields, static JS, pytest, Superpowers TDD.

---

## File Map

Modify:

- `app/services/pipeline_manifest.py`  
  Add pure helpers for stage status, visual artifacts, image attempts, and TTS artifacts.

- `app/services/prompt_director_manifest.py`  
  Add project-level manifest builder that records each visual prompt into `pipeline_manifest`.

- `app/services/comfyui_pipeline.py`  
  Record selected image prompt id, seed, score, issue codes, and selected state into the matching manifest segment.

- `app/services/tts.py`  
  Add a file-based sync helper for `tts_run_manifest.json` and `timings.json`; call it after TTS output succeeds.

- `app/static/app.js`  
  Fetch `/workflow-status` and render stage cards into `#workflow-stage-cards`.

Create/modify tests:

- `tests/test_pipeline_manifest.py`
- `tests/test_prompt_contract.py`
- `tests/test_character_workflow_contract.py`
- `tests/test_tts_pipeline.py`
- `tests/test_static_workflow_ui.py`

---

## Task 1: Add Pure Manifest Update Helpers

**Files:**

- Modify: `app/services/pipeline_manifest.py`
- Test: `tests/test_pipeline_manifest.py`

- [ ] **Step 1: Write the failing tests**

Add tests that call helpers directly:

```python
def test_pipeline_manifest_records_visual_image_and_tts_artifacts():
    manifest = build_initial_pipeline_manifest("p1", "Title", ["Light appears."])
    manifest = record_visual_artifact(
        manifest,
        sentence_idx=0,
        positive_prompt="bright light",
        negative_prompt="text",
        preset_id="genesis",
        domain="bible",
        required_props=["light"],
        visual_intent="literal light",
        prompt_hash="prompt-1",
    )
    manifest = record_image_attempt(
        manifest,
        sentence_idx=0,
        path="scene.png",
        prompt_id="prompt-1",
        attempt=1,
        seed=8,
        prompt_hash="prompt-1",
        candidate_score=0.91,
        issue_codes=[],
        selected=True,
    )
    manifest = record_tts_artifact(
        manifest,
        sentence_idx=0,
        wav_path="0000.wav",
        start=0.0,
        end=2.0,
        duration_sec=2.0,
        seed=123,
        issue_codes=[],
    )

    segment = manifest["segments"][0]
    assert segment["visual"]["positive_prompt"] == "bright light"
    assert segment["image"]["attempts"][0]["selected"] is True
    assert segment["tts"]["duration_sec"] == 2.0
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
python -m pytest tests/test_pipeline_manifest.py -q
```

Expected: fail because the record helpers do not exist.

- [ ] **Step 3: Implement the helpers**

Add helper functions:

```python
def update_stage_status(manifest, stage, *, state, error_code="", recovery_hint="", input_hash="", output_hash=""): ...
def record_visual_artifact(manifest, *, sentence_idx, positive_prompt, negative_prompt, preset_id, domain, required_props, visual_intent, prompt_hash): ...
def record_image_attempt(manifest, *, sentence_idx, path, prompt_id, attempt, seed, prompt_hash, candidate_score, issue_codes, selected): ...
def record_tts_artifact(manifest, *, sentence_idx, wav_path, start, end, duration_sec, seed, issue_codes): ...
```

Each helper must copy the manifest shallowly, update `updated_at`, mutate only the target segment, and return the updated manifest.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_pipeline_manifest.py -q
```

Expected: pass.

---

## Task 2: Sync Prompt Manifest Into Pipeline Manifest

**Files:**

- Modify: `app/services/prompt_director_manifest.py`
- Test: `tests/test_prompt_contract.py`

- [ ] **Step 1: Write the failing test**

Add:

```python
def test_write_prompt_manifest_records_visual_artifacts(sample_project):
    payload = write_prompt_director_manifest(sample_project)
    project = db.get_project(sample_project["id"])
    visual = project["pipeline_manifest"]["segments"][0]["visual"]
    assert payload["prompts"][0]["prompt_hash"] == visual["prompt_hash"]
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
python -m pytest tests/test_prompt_contract.py -q
```

Expected: fail because `write_prompt_director_manifest()` does not exist.

- [ ] **Step 3: Implement project-level writer**

Create `build_prompt_director_manifest(project)` and `write_prompt_director_manifest(project)`. The writer should:

1. Build one prompt item per project sentence.
2. Write `image_prompts_manifest.json` under the project directory.
3. Record each prompt into `pipeline_manifest.segments[idx].visual`.
4. Set visual stage status to `done`.
5. Persist both `body_image_options["image_prompts_manifest_path"]` and `pipeline_manifest`.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_prompt_contract.py tests/test_pipeline_manifest.py -q
```

Expected: pass.

---

## Task 3: Record Selected Image Attempts

**Files:**

- Modify: `app/services/comfyui_pipeline.py`
- Test: `tests/test_character_workflow_contract.py`

- [ ] **Step 1: Write the failing test**

Add a test that monkeypatches image copying and asserts `import_history_image()` records an image attempt in the pipeline manifest:

```python
mapping = import_history_image(project, result=fake_result, prompt="prompt", prompt_id="pid", sentence_idx=0, candidate_score=0.8)
updated = db.get_project(project["id"])
attempt = updated["pipeline_manifest"]["segments"][0]["image"]["attempts"][0]
assert attempt["prompt_hash"]
assert attempt["candidate_score"] == 0.8
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
python -m pytest tests/test_character_workflow_contract.py -q
```

Expected: fail because `import_history_image()` does not record image attempts.

- [ ] **Step 3: Implement the image artifact record**

Extend `import_history_image()` with optional `seed`, `candidate_score`, `issue_codes`, and `character_descriptor_applied`. After `body_image_mappings` persists, call `record_image_attempt()` and persist the updated pipeline manifest.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_character_workflow_contract.py tests/test_visual_relevance.py -q
```

Expected: pass.

---

## Task 4: Sync TTS Timing Artifacts Into Pipeline Manifest

**Files:**

- Modify: `app/services/tts.py`
- Test: `tests/test_tts_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add a test that writes `timings.json` and `tts_run_manifest.json`, calls `sync_tts_artifacts_to_pipeline_manifest(pid)`, and asserts `pipeline_manifest.segments[0].tts` contains wav path, timing, duration, and seed.

- [ ] **Step 2: Run the failing test**

Run:

```powershell
python -m pytest tests/test_tts_pipeline.py -q
```

Expected: fail because the sync helper does not exist.

- [ ] **Step 3: Implement sync helper**

Implement `sync_tts_artifacts_to_pipeline_manifest(pid)`. It should read:

- `tts/timings.json`
- `tts/tts_run_manifest.json`

For each timing row, record:

- `wav_path`: `tts/{idx:04d}.wav`
- `start`
- `end`
- `duration_sec`
- `seed`
- `issue_codes`: empty list for now

Set TTS stage status to `done` after sync.

- [ ] **Step 4: Call sync after successful TTS**

In `run_tts_job()`, call `sync_tts_artifacts_to_pipeline_manifest(pid)` after `save_tts_consistency_report()` and before setting `tts_state="done"`.

- [ ] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_tts_pipeline.py tests/test_pipeline_manifest.py -q
```

Expected: pass.

---

## Task 5: Render Workflow Stage Cards In The Static UI

**Files:**

- Modify: `app/static/app.js`
- Test: `tests/test_static_workflow_ui.py`

- [ ] **Step 1: Write the failing static test**

Assert `app/static/app.js` contains:

```javascript
fetch(`/api/projects/${currentProject.id}/workflow-status`)
workflow-stage-cards
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
python -m pytest tests/test_static_workflow_ui.py -q
node --check app/static/app.js
```

Expected: fail because the UI does not fetch workflow status yet.

- [ ] **Step 3: Implement UI rendering**

Add:

```javascript
async function refreshWorkflowStatus() {
  if (!currentProject) return;
  const payload = await api(`/api/projects/${currentProject.id}/workflow-status`);
  renderStageCards(payload.stage_cards || []);
}
```

Call it from `openProject()` and `refreshCurrentProject()`.

- [ ] **Step 4: Verify**

Run:

```powershell
python -m pytest tests/test_static_workflow_ui.py tests/test_workflow_status.py -q
node --check app/static/app.js
```

Expected: pass.

---

## Verification Commands

Focused:

```powershell
python -m pytest tests/test_pipeline_manifest.py tests/test_prompt_contract.py tests/test_character_workflow_contract.py tests/test_tts_pipeline.py tests/test_static_workflow_ui.py tests/test_workflow_status.py -q
node --check app/static/app.js
```

Full recovery slice:

```powershell
python -m pytest tests/test_pipeline_manifest.py tests/test_prompt_contract.py tests/test_character_workflow_contract.py tests/test_image_prompt.py tests/test_visual_relevance.py tests/test_image_quality.py tests/test_tts_pipeline.py tests/test_tts_worker.py tests/test_tts_presets.py tests/test_autopilot_routes.py tests/test_workflow_status.py tests/test_static_workflow_ui.py tests/test_installed_pipeline_quality_smoke.py tests/test_preset_text_health.py tests/test_korean_longform_script_integrity.py tests/test_script_compile.py tests/test_z_image_workflow_submission.py -q
node --check app/static/app.js
```

---

## Acceptance Criteria

- Prompt generation records visual artifacts in `pipeline_manifest`.
- Selected image imports record at least one selected attempt with prompt hash, score, seed, and issue codes.
- TTS timing sync records per-segment wav timing and seed into `pipeline_manifest`.
- Workflow status API and static UI can display manifest-backed stage cards.
- Existing focused recovery tests still pass.

---

## Self-Review

Spec coverage:

- Covers the remaining vertical slice that turns the previously added manifest into a real artifact sink.
- Does not attempt the full autopilot function split in this pass; that remains a later plan because it is a larger refactor.

Placeholder scan:

- No `TBD`, `TODO`, or “write tests later” placeholders are present.

Type consistency:

- Uses existing `PipelineVisualArtifact`, `PipelineImageArtifact`, `PipelineImageAttempt`, and `PipelineTtsArtifact` names from `app/types.py`.
- All persistence goes through the existing `pipeline_manifest` project field.
