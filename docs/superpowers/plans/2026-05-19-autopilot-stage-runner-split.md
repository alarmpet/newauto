# Autopilot Stage Runner Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract reusable autopilot stage status helpers so each pipeline phase can be retried, resumed, and shown in the operator console without relying on one large implicit worker flow.

**Architecture:** Keep durable artifact data in `pipeline_manifest.stage_status`, and expose small helpers in `app/services/pipeline_runner.py` for stage transitions. Wire `app/services/autopilot.py` to those helpers incrementally so existing behavior stays stable while later tasks can split the worker into real stage functions.

**Tech Stack:** Python, FastAPI project services, SQLite-backed `app.db`, pytest/unittest route tests.

---

## File Structure

- Modify `app/services/pipeline_runner.py`: stage metadata, stage result type, status transition helpers, first incomplete stage lookup.
- Modify `app/services/autopilot.py`: call the new transition helper when starting an autopilot run.
- Modify `tests/test_pipeline_runner.py`: direct unit tests for helper behavior.
- Modify `tests/test_autopilot_routes.py`: route-level coverage that start uses the helper contract.

---

### Task 1: Stage Status Helper API

**Files:**
- Create: `tests/test_pipeline_runner.py`
- Modify: `app/services/pipeline_runner.py`

- [x] **Step 1: Write the failing tests**

```python
from app import db
from app.services.pipeline_runner import (
    first_incomplete_stage,
    initialize_autopilot_stage_status,
    mark_stage_done,
    mark_stage_error,
    mark_stage_running,
)


def test_stage_transition_helpers_preserve_manifest_artifacts(tmp_path):
    db.init_db()
    project = db.create_project(title="runner")
    pid = str(project["id"])
    manifest = dict(project["pipeline_manifest"])
    manifest["segments"] = [
        {
            "sentence_idx": 0,
            "script_text": "A sentence.",
            "script_hash": "hash",
            "region": "body",
            "visual": {"positive_prompt": "x"},
            "image": None,
            "tts": None,
        }
    ]
    db.update_project(pid, pipeline_manifest=manifest)

    initialize_autopilot_stage_status(pid, input_text="A sentence.")
    running = mark_stage_running(pid, "script_compile", input_text="A sentence.")
    done = mark_stage_done(pid, "script_compile", output_text="compiled sentence")
    failed = mark_stage_error(pid, "visual_plan", error_code="PROMPT_EMPTY", recovery_hint="Regenerate prompts.")

    assert running["stage_status"]["script_compile"]["state"] == "running"
    assert done["stage_status"]["script_compile"]["state"] == "done"
    assert failed["stage_status"]["visual_plan"]["state"] == "error"
    assert failed["stage_status"]["visual_plan"]["error_code"] == "PROMPT_EMPTY"
    assert failed["segments"][0]["visual"] == {"positive_prompt": "x"}
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline_runner.py::test_stage_transition_helpers_preserve_manifest_artifacts -q`

Expected: FAIL with missing `mark_stage_running`, `mark_stage_done`, or `mark_stage_error`.

- [x] **Step 3: Write minimal implementation**

Add helpers to `app/services/pipeline_runner.py`:

```python
from typing import Literal, TypedDict

from ..types import PipelineManifest

AutopilotStage = Literal[
    "prepare_input",
    "script_compile",
    "visual_plan",
    "tts",
    "image",
    "render_plan",
    "preflight",
    "render",
]


class StageResult(TypedDict):
    stage: AutopilotStage
    state: str
    input_hash: str
    output_hash: str
    error_code: str
    recovery_hint: str
```

Use `update_stage_status()` and `text_hash()` to write the status back through `db.update_project()`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline_runner.py::test_stage_transition_helpers_preserve_manifest_artifacts -q`

Expected: PASS.

---

### Task 2: First Incomplete Stage Lookup

**Files:**
- Modify: `tests/test_pipeline_runner.py`
- Modify: `app/services/pipeline_runner.py`

- [x] **Step 1: Write the failing test**

```python
def test_first_incomplete_stage_returns_next_non_done_stage():
    db.init_db()
    project = db.create_project(title="runner")
    pid = str(project["id"])
    initialize_autopilot_stage_status(pid, input_text="A sentence.")
    mark_stage_done(pid, "prepare_input", output_text="A sentence.")
    mark_stage_done(pid, "script_compile", output_text="compiled")
    project = db.get_project(pid)

    assert project is not None
    assert first_incomplete_stage(project) == "visual_plan"
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline_runner.py::test_first_incomplete_stage_returns_next_non_done_stage -q`

Expected: FAIL with missing or wrong `first_incomplete_stage`.

- [x] **Step 3: Write minimal implementation**

Inspect `project["pipeline_manifest"]["stage_status"]` in `AUTOPILOT_STAGES` order. Return the first stage whose `state` is not `done`; return `None` when every stage is done.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline_runner.py::test_first_incomplete_stage_returns_next_non_done_stage -q`

Expected: PASS.

---

### Task 3: Autopilot Start Uses Stage Helper

**Files:**
- Modify: `tests/test_autopilot_routes.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing route assertion**

Extend `test_start_autopilot_records_pipeline_stage_boundaries`:

```python
self.assertEqual(manifest["stage_status"]["prepare_input"]["state"], "queued")
self.assertNotEqual(manifest["stage_status"]["prepare_input"]["input_hash"], "")
self.assertEqual(manifest["stage_status"]["script_compile"]["state"], "idle")
```

- [x] **Step 2: Run test to verify behavior**

Run: `python -m pytest tests/test_autopilot_routes.py::AutopilotRouteTests::test_start_autopilot_records_pipeline_stage_boundaries -q`

Expected: PASS if Task 1 initialization already covers this; otherwise FAIL and wire start to the helper contract.

- [x] **Step 3: Keep implementation minimal**

Ensure `start()` calls `initialize_autopilot_stage_status(pid, input_text=options.get("script", ""))` after queueing and then reloads the project before returning.

- [x] **Step 4: Run route test**

Run: `python -m pytest tests/test_autopilot_routes.py::AutopilotRouteTests::test_start_autopilot_records_pipeline_stage_boundaries -q`

Expected: PASS.

---

### Task 4: Focused Regression Verification

**Files:**
- Test only.

- [x] **Step 1: Run runner and route tests**

Run: `python -m pytest tests/test_pipeline_runner.py tests/test_autopilot_routes.py tests/test_workflow_status.py -q`

Expected: PASS.

- [x] **Step 2: Run previous recovery suite**

Run: `python -m pytest tests/test_pipeline_manifest.py tests/test_prompt_contract.py tests/test_character_workflow_contract.py tests/test_image_prompt.py tests/test_visual_relevance.py tests/test_image_quality.py tests/test_tts_pipeline.py tests/test_tts_worker.py tests/test_tts_presets.py tests/test_autopilot_routes.py tests/test_workflow_status.py tests/test_static_workflow_ui.py tests/test_installed_pipeline_quality_smoke.py tests/test_preset_text_health.py tests/test_korean_longform_script_integrity.py tests/test_script_compile.py tests/test_z_image_workflow_submission.py tests/test_pipeline_runner.py -q`

Expected: PASS.

---

### Task 5: Runtime Event To Stage Sync

**Files:**
- Create: `tests/test_autopilot_stage_sync.py`
- Modify: `app/services/pipeline_runner.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing test**

`tests/test_autopilot_stage_sync.py` calls `_update_runtime()` with `phase_start`, `wait_done`, and `paused` events, then asserts `pipeline_manifest.stage_status` moves to `running`, `done`, and `error`.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: FAIL because `tts` stayed `idle` after a `tts_enqueue` runtime update.

- [x] **Step 3: Write minimal implementation**

Added `stage_for_autopilot_phase()` and phase-stage mapping in `pipeline_runner.py`, then had `_update_runtime()` call `_sync_pipeline_stage_status()` after recording the runtime event.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: PASS.

---

### Task 12: Preflight Stage Extraction

**Files:**
- Modify: `tests/test_autopilot_stage_sync.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing test**

Added `test_preflight_stage_marks_done_and_error()` with fake `build_preflight_report()` success and failure reports. The test asserts `_run_preflight_stage()` marks `preflight` done on success and error on failure.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autopilot_stage_sync.py::test_preflight_stage_marks_done_and_error -q`

Observed: FAIL with `AttributeError: module 'app.services.autopilot' has no attribute '_run_preflight_stage'`.

- [x] **Step 3: Write minimal implementation**

Added `_run_preflight_stage(pid, project)` in `app/services/autopilot.py`. It records `preflight`, builds the report, marks `preflight` done on pass, and pauses with explicit `preflight` stage error on failure.

- [x] **Step 4: Wire `run_autopilot_job()` to the stage helper**

Replaced the inline preflight block with `_run_preflight_stage()` and preserved early return when autopilot pauses.

- [x] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: PASS.

---

### Task 13: Render Stage Extraction

**Files:**
- Modify: `tests/test_autopilot_stage_sync.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing test**

Added `test_render_stage_queues_waits_and_completes_autopilot()` with fake `_wait_for_state()` and `load_render_report()` functions. The test asserts `_run_render_stage()` queues render state, waits for completion, marks `render` done, and completes autopilot with the render output summary.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autopilot_stage_sync.py::test_render_stage_queues_waits_and_completes_autopilot -q`

Observed: FAIL with `AttributeError: module 'app.services.autopilot' has no attribute '_run_render_stage'`.

- [x] **Step 3: Write minimal implementation**

Added `_run_render_stage(pid, project)` in `app/services/autopilot.py`. It records `render_enqueue`, queues render worker state, waits for `render_state=done`, loads the render report, and records the final autopilot `done` event.

- [x] **Step 4: Wire `run_autopilot_job()` to the stage helper**

Replaced the inline render enqueue/wait/final summary block with `_run_render_stage()`.

- [x] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: PASS.

---

### Task 11: Render Plan Stage Extraction

**Files:**
- Modify: `tests/test_autopilot_stage_sync.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing test**

Added `test_render_plan_stage_persists_scene_and_render_plan()` with fake `build_scene_plan()` and `build_render_plan()` functions. The test asserts `_run_render_plan_stage()` persists both plans and marks `render_plan` done.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autopilot_stage_sync.py::test_render_plan_stage_persists_scene_and_render_plan -q`

Observed: FAIL with `AttributeError: module 'app.services.autopilot' has no attribute '_run_render_plan_stage'`.

- [x] **Step 3: Write minimal implementation**

Added `_run_render_plan_stage(pid, project)` in `app/services/autopilot.py`. It records `plan_refresh`, builds and persists `scene_plan` and `render_plan`, and marks `render_plan` done.

- [x] **Step 4: Wire `run_autopilot_job()` to the stage helper**

Replaced the inline `plan_refresh` block with `_run_render_plan_stage()`.

- [x] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: PASS.

---

### Task 10: Visual Asset Gate Extraction

**Files:**
- Modify: `tests/test_autopilot_stage_sync.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing test**

Added `test_visual_asset_stage_marks_image_error_when_generation_disabled()` to call a desired `_run_visual_asset_stage()` API for `comfyui_auto`.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autopilot_stage_sync.py::test_visual_asset_stage_marks_image_error_when_generation_disabled -q`

Observed: FAIL first with missing `_run_visual_asset_stage`, then exposed that `image` stage stayed `idle` because pause handling used the previous `tts_wait` phase.

- [x] **Step 3: Write minimal implementation**

Added `_run_visual_asset_stage(pid, project, options)` in `app/services/autopilot.py`. It handles disabled automatic image generation and missing upload media, pauses autopilot with the existing error codes, and explicitly marks `image` stage as `error`.

- [x] **Step 4: Wire `run_autopilot_job()` to the stage helper**

Replaced the inline visual asset gate with `_run_visual_asset_stage()` and preserved the paused/error/canceled early return behavior.

- [x] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: PASS.

---

### Task 9: TTS Stage Extraction

**Files:**
- Modify: `tests/test_autopilot_stage_sync.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing test**

Added `test_tts_stage_applies_autopilot_profile_and_queues_tts()` with a fake `_wait_for_state()` so the test covers TTS stage orchestration without waiting for a worker.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autopilot_stage_sync.py::test_tts_stage_applies_autopilot_profile_and_queues_tts -q`

Observed: FAIL with `AttributeError: module 'app.services.autopilot' has no attribute '_run_tts_stage'`.

- [x] **Step 3: Write minimal implementation**

Added `_run_tts_stage(pid, project)` in `app/services/autopilot.py`. It applies the autopilot voice preset/profile, records `tts_enqueue`, queues the TTS worker state, and waits for `tts_state=done`.

- [x] **Step 4: Wire `run_autopilot_job()` to the stage helper**

Replaced the inline TTS profile/enqueue/wait block with `_run_tts_stage()`.

- [x] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: PASS.

---

### Task 8: Source Draft Apply Stage Extraction

**Files:**
- Modify: `tests/test_autopilot_stage_sync.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing test**

Added `test_source_draft_apply_stage_marks_script_compile_done()` to call a desired `_run_source_draft_apply_stage()` API after a source draft worker has produced `source_draft_script`.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autopilot_stage_sync.py::test_source_draft_apply_stage_marks_script_compile_done -q`

Observed: FAIL with `AttributeError: module 'app.services.autopilot' has no attribute '_run_source_draft_apply_stage'`.

- [x] **Step 3: Write minimal implementation**

Added `_run_source_draft_apply_stage(pid, project, options)` in `app/services/autopilot.py`. It preserves the copy-risk and user-script overwrite guards, records `source_apply`, applies the draft through `_apply_source_draft()`, and marks `script_compile` done using the compiled script.

- [x] **Step 4: Wire `run_autopilot_job()` to the stage helper**

After URL/keyword source draft generation completes, `run_autopilot_job()` now calls `_run_source_draft_apply_stage()` before moving to TTS.

- [x] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: PASS.

---

### Task 7: Source Collection Stage Extraction

**Files:**
- Modify: `tests/test_autopilot_stage_sync.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing test**

Added `test_source_collection_stage_marks_prepare_done_and_queues_draft()` with a fake URL collector. The test asserts `_run_source_collection_stage()` queues source draft generation and marks `prepare_input` done for URL input.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autopilot_stage_sync.py::test_source_collection_stage_marks_prepare_done_and_queues_draft -q`

Observed: FAIL with `AttributeError: module 'app.services.autopilot' has no attribute '_run_source_collection_stage'`.

- [x] **Step 3: Write minimal implementation**

Added `_run_source_collection_stage(pid, project, options)` in `app/services/autopilot.py`. It handles URL and keyword source collection, marks `prepare_input` done using the collected query, queues source draft generation, and records the `source_generate` runtime phase.

- [x] **Step 4: Wire `run_autopilot_job()` to the stage helper**

Replaced duplicated URL and keyword source collection blocks with `_run_source_collection_stage()`, leaving `_wait_for_state()` and source apply extraction for later tasks.

- [x] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: PASS.

---

### Task 6: Prepare Input Stage Extraction

**Files:**
- Modify: `tests/test_autopilot_stage_sync.py`
- Modify: `app/services/autopilot.py`

- [x] **Step 1: Write the failing test**

Added `test_prepare_input_stage_saves_script_and_marks_stage_done()` to call a desired `_run_prepare_input_stage()` API for script input.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autopilot_stage_sync.py::test_prepare_input_stage_saves_script_and_marks_stage_done -q`

Observed: FAIL with `AttributeError: module 'app.services.autopilot' has no attribute '_run_prepare_input_stage'`.

- [x] **Step 3: Write minimal implementation**

Added `_run_prepare_input_stage(pid, project, options)` in `app/services/autopilot.py`. It records the `prepare_input` runtime start, saves script input through the existing `_save_script_input()` helper, marks `prepare_input` done with the compiled script hash, and returns the reloaded project.

- [x] **Step 4: Wire `run_autopilot_job()` to the stage helper**

Replaced the initial inline `prepare_input` update and script-save block with `_run_prepare_input_stage()`, leaving URL/keyword source collection behavior in place for later extraction.

- [x] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_autopilot_stage_sync.py -q`

Observed: PASS.
