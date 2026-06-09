# Installed Video Quality Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent installed `newauto Studio` from producing a final video when visuals are generic/mismatched or TTS is noisy/non-human, and restore the real script-to-image-to-voice-to-render workflow for the Genesis opening sample.

**Architecture:** Treat final render as a gated product, not a best-effort export. Autopilot must generate or attach one semantically valid visual per sentence, TTS must pass human-voice consistency checks, and render must refuse blocking preflight failures unless a deliberately named debug-only bypass is used. Existing durable artifacts (`pipeline_manifest`, `scene_visual_plan.json`, `tts_consistency_report.json`, `render_report.json`) become enforceable contracts.

**Tech Stack:** Python, FastAPI, SQLite-backed `app.db`, PyInstaller sidecar, Tauri desktop shell, ComfyUI/Z-Image worker, OmniVoice TTS, ffmpeg/ffprobe, pytest.

---

## Evidence From Failed Run

Project: `fb6c4ef0b663`

Output:
- `C:\Users\petbl\AppData\Local\com.newauto.studio\projects\fb6c4ef0b663\output.mp4`
- Duration: `26.27s`
- Render report: `status=done`

Observed failures:
- Visuals are abstract gradients/star fields and do not encode the sentence-specific meaning.
- `scene_visual_plan.json` says `source: d1_disabled_scaffold`, which means the visual plan came from the disabled-image-generation scaffold, not a real semantic image pipeline.
- `visual_mismatch_report.json` records empty `positive_prompt`, empty `selected_image`, `semantic_match_score: 0.0`, but still reports `diagnosis: pass` and `decision: warn` under `upload_only`.
- `final_scene_review.json` records empty `selected_image` and zero candidate scores for every sentence.
- `tts_consistency_report.json` records `audio_consistency_passed: false`, `max_rms_relative_drift: 0.3896`, `max_spectral_centroid_relative_drift: 0.1463`, and recommended mode `full_passage_or_reference_voice`.
- Autopilot correctly paused at `PREFLIGHT_TTS_CONSISTENCY`, but `POST /api/projects/{pid}/render` allowed rendering anyway because it only checks `tts_state == done` and media existence.

Root causes:
- Autopilot still pauses on `comfyui_auto` because `app/services/autopilot.py` treats automatic image generation as disabled, even though `app/workers/image_worker.py` now contains a Z-Image worker path.
- Upload-only fallback does not enforce one current, meaningful visual mapping per sentence before render.
- Render route bypasses blocking preflight checks.
- TTS quality report is advisory after TTS finishes; `tts_state` can be `done` even when audio consistency fails.
- Workflow status displays warnings, but warnings do not stop bad final exports.

---

## File Structure

- Modify `app/services/autopilot.py`: queue/wait for Z-Image generation in `comfyui_auto` and `hybrid`, retry TTS when consistency fails, and never proceed to render on blocking preflight failures.
- Modify `app/routers/render.py`: enforce render-blocking preflight checks before `render_state=queued`.
- Modify `app/services/preflight.py`: add blocking semantics to checks; distinguish local-render blockers from YouTube/OAuth upload blockers.
- Modify `app/services/visual_relevance.py`: make empty selected image, empty prompt, missing mapping, and zero semantic score blocking failures for render.
- Modify `app/services/scene_plan.py`: for `upload_only`, map `media_order[sentence_idx]` into `scene.media_path` only when image count covers every sentence; otherwise mark visual coverage incomplete.
- Modify `app/services/render_plan.py`: require scene media paths for sentence-based render plans and report missing paths as blocking failures.
- Modify `app/services/tts.py`: treat failed audio consistency as a failed TTS job or queue exactly one safer retry.
- Modify `app/workers/tts_worker.py`: preserve retry metadata and avoid marking `done` when final consistency still fails.
- Modify `app/static/app.js`: surface render blockers and disable render/start-complete controls when blockers exist.
- Create `tests/test_installed_quality_gates.py`: regression tests for the Genesis failure.
- Create `tests/test_autopilot_z_image_stage.py`: regression tests for automatic image generation queue/wait behavior.
- Create `tests/test_render_preflight_gate.py`: render route must reject bad TTS/visuals.
- Create `tests/test_tts_quality_gate.py`: failed final TTS consistency cannot be marked done.

---

### Task 1: Render Route Must Enforce Blocking Preflight

**Files:**
- Create: `tests/test_render_preflight_gate.py`
- Modify: `app/services/preflight.py`
- Modify: `app/routers/render.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render_preflight_gate.py`:

```python
import json
import unittest

from fastapi.testclient import TestClient

from app import db
from app.main import app


class RenderPreflightGateTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.client = TestClient(app)
        self.project = db.create_project("render gate")
        self.pid = self.project["id"]

    def tearDown(self) -> None:
        db.delete_project(self.pid)

    def _ready_project(self) -> None:
        project_dir = db.project_dir(self.pid)
        media_dir = project_dir / "media"
        tts_dir = project_dir / "tts"
        media_dir.mkdir(parents=True, exist_ok=True)
        tts_dir.mkdir(parents=True, exist_ok=True)
        (media_dir / "scene.png").write_bytes(b"fake image bytes")
        (tts_dir / "timings.json").write_text(
            json.dumps([{"idx": 0, "text": "문장입니다.", "start": 0.0, "end": 2.0, "dur": 2.0}]),
            encoding="utf-8",
        )
        (tts_dir / "tts_run_manifest.json").write_text(
            json.dumps({"sentences": [{"idx": 0, "text": "문장입니다."}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        db.update_project(
            self.pid,
            script="문장입니다.",
            compiled_script="문장입니다.",
            sentences=["문장입니다."],
            media_order=["scene.png"],
            tts_state="done",
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "sentence_hash": "",
                    "path": "scene.png",
                    "prompt": "문장입니다.",
                    "selected_reason": "test",
                }
            ],
        )

    def test_render_rejects_failed_tts_consistency(self) -> None:
        self._ready_project()
        tts_dir = db.project_dir(self.pid) / "tts"
        (tts_dir / "tts_consistency_report.json").write_text(
            json.dumps(
                {
                    "metadata_consistent": True,
                    "audio_consistency_checked": True,
                    "audio_consistency_passed": False,
                    "max_spectral_centroid_relative_drift": 0.1463,
                    "max_rms_relative_drift": 0.3896,
                    "recommended_tts_mode": "full_passage_or_reference_voice",
                }
            ),
            encoding="utf-8",
        )

        response = self.client.post(f"/api/projects/{self.pid}/render")

        self.assertEqual(response.status_code, 409)
        self.assertIn("tts_consistency", response.json()["detail"]["blocking_checks"])
        project = db.get_project(self.pid)
        assert project is not None
        self.assertEqual(project["render_state"], "idle")

    def test_render_allows_missing_oauth_for_local_render(self) -> None:
        self._ready_project()
        tts_dir = db.project_dir(self.pid) / "tts"
        (tts_dir / "tts_consistency_report.json").write_text(
            json.dumps(
                {
                    "metadata_consistent": True,
                    "audio_consistency_checked": True,
                    "audio_consistency_passed": True,
                }
            ),
            encoding="utf-8",
        )

        response = self.client.post(f"/api/projects/{self.pid}/render")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_render_preflight_gate.py -q
```

Expected: `test_render_rejects_failed_tts_consistency` fails because the render route currently queues render despite failed TTS consistency.

- [ ] **Step 3: Add blocking semantics to preflight checks**

In `app/services/preflight.py`, extend `PreflightCheck` construction so local-render blockers can be extracted without changing every consumer at once:

```python
LOCAL_RENDER_BLOCKING_CHECKS = {
    "script",
    "tts_state",
    "tts_manifest_text",
    "tts_consistency",
    "media",
    "render_plan",
    "visual_mapping",
    "visual_relevance",
}


def local_render_blockers(report: PreflightReport) -> list[PreflightCheck]:
    return [
        check
        for check in report["checks"]
        if not check["ok"] and check["key"] in LOCAL_RENDER_BLOCKING_CHECKS
    ]
```

Keep OAuth checks in the report, but do not include `"oauth"` in `LOCAL_RENDER_BLOCKING_CHECKS`.

- [ ] **Step 4: Enforce blockers in render route**

In `app/routers/render.py`, import `local_render_blockers` and reject render queueing:

```python
from ..services.preflight import local_render_blockers
```

Inside `start_render()` after the existing `media_upload_state` check and before `render_state` mutation:

```python
    report = preflight_svc.build_preflight_report(project)
    blockers = local_render_blockers(report)
    if blockers:
        raise HTTPException(
            409,
            {
                "message": "render preflight has blocking failures",
                "blocking_checks": [check["key"] for check in blockers],
                "checks": blockers,
            },
        )
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_render_preflight_gate.py -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```powershell
git add app/services/preflight.py app/routers/render.py tests/test_render_preflight_gate.py
git commit -m "Block render on failed local preflight"
```

---

### Task 2: Upload-Only Visual Coverage Must Be Explicit And Complete

**Files:**
- Create: `tests/test_installed_quality_gates.py`
- Modify: `app/services/scene_plan.py`
- Modify: `app/services/render_plan.py`
- Modify: `app/services/preflight.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_installed_quality_gates.py`:

```python
import unittest

from app import db
from app.services.preflight import build_preflight_report, local_render_blockers
from app.services.render_plan import build_render_plan
from app.services.scene_plan import build_scene_plan


class InstalledQualityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.project = db.create_project("genesis quality gate")
        self.pid = self.project["id"]

    def tearDown(self) -> None:
        db.delete_project(self.pid)

    def test_upload_only_scene_plan_maps_one_media_per_sentence(self) -> None:
        project = db.update_project(
            self.pid,
            script="첫 문장. 둘째 문장.",
            compiled_script="첫 문장. 둘째 문장.",
            sentences=["첫 문장.", "둘째 문장."],
            media_order=["one.png", "two.png"],
            visual_source_mode="upload_only",
        )
        assert project is not None

        scene_plan = build_scene_plan(project)

        self.assertEqual([scene["media_path"] for scene in scene_plan["scenes"]], ["one.png", "two.png"])
        self.assertEqual(scene_plan["scenes"][0]["visual_intent"], "첫 문장.")

    def test_upload_only_incomplete_media_blocks_render(self) -> None:
        project = db.update_project(
            self.pid,
            script="첫 문장. 둘째 문장.",
            compiled_script="첫 문장. 둘째 문장.",
            sentences=["첫 문장.", "둘째 문장."],
            media_order=["one.png"],
            visual_source_mode="upload_only",
            tts_state="done",
        )
        assert project is not None
        report = build_preflight_report(project)

        blockers = local_render_blockers(report)

        self.assertIn("visual_mapping", [check["key"] for check in blockers])

    def test_render_plan_keeps_sentence_media_paths(self) -> None:
        project = db.update_project(
            self.pid,
            script="첫 문장. 둘째 문장.",
            compiled_script="첫 문장. 둘째 문장.",
            sentences=["첫 문장.", "둘째 문장."],
            media_order=["one.png", "two.png"],
            visual_source_mode="upload_only",
        )
        assert project is not None
        scene_plan = build_scene_plan(project)
        project = db.update_project(self.pid, scene_plan=scene_plan)
        assert project is not None

        render_plan = build_render_plan(project)

        self.assertEqual(render_plan["segments"][0]["media"], [{"path": "one.png", "kind": "image"}])
        self.assertEqual(render_plan["segments"][1]["media"], [{"path": "two.png", "kind": "image"}])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_installed_quality_gates.py -q
```

Expected: first and third tests fail because `scene_plan` currently leaves `media_path` blank unless `body_image_mappings` exist.

- [ ] **Step 3: Map upload-only media by sentence**

In `app/services/scene_plan.py`, inside `build_scene_plan()`, after checking `body_image_mappings`, add upload-only mapping:

```python
        elif project["visual_source_mode"] == "upload_only" and sentence_idx < len(project["media_order"]):
            media_path = project["media_order"][sentence_idx]
            prompt = visual_plan_entry["core_meaning"] if visual_plan_entry is not None else sentence
```

Also add metadata:

```python
        if project["visual_source_mode"] == "upload_only":
            scene["visual_source_mode"] = "upload_only"
            scene["uploaded_media_index"] = sentence_idx if sentence_idx < len(project["media_order"]) else -1
```

- [ ] **Step 4: Add visual mapping preflight check**

In `app/services/preflight.py`, add a check that local render blocks when sentence coverage is incomplete:

```python
def _visual_mapping_summary(project: ProjectRecord) -> tuple[bool, str]:
    sentence_count = len(project["sentences"])
    if sentence_count == 0:
        return (False, "No compiled sentences are available.")
    if project["visual_source_mode"] == "upload_only":
        if len(project["media_order"]) < sentence_count:
            return (
                False,
                f"Upload-only visual coverage is incomplete: {len(project['media_order'])}/{sentence_count} media files.",
            )
        return (True, "Upload-only media covers every sentence.")
    mappings = project["body_image_mappings"]
    if len(mappings) < sentence_count:
        return (False, f"Generated visual mappings are incomplete: {len(mappings)}/{sentence_count}.")
    return (True, "Visual mappings cover every sentence.")
```

Append this check in `build_preflight_report()`:

```python
    visual_mapping_ok, visual_mapping_message = _visual_mapping_summary(project)
    checks.append(
        {
            "key": "visual_mapping",
            "ok": visual_mapping_ok,
            "message": visual_mapping_message,
        }
    )
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_installed_quality_gates.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```powershell
git add app/services/scene_plan.py app/services/render_plan.py app/services/preflight.py tests/test_installed_quality_gates.py
git commit -m "Require complete sentence visual coverage"
```

---

### Task 3: Restore Autopilot Z-Image Generation Instead Of Disabled Scaffold

**Files:**
- Create: `tests/test_autopilot_z_image_stage.py`
- Modify: `app/services/autopilot.py`
- Modify: `app/workers/image_worker.py`
- Modify: `app/services/image_prompt.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_autopilot_z_image_stage.py`:

```python
from app import db
from app.services import autopilot
from app.services.pipeline_runner import initialize_autopilot_stage_status


def test_visual_asset_stage_queues_z_image_and_waits(monkeypatch):
    db.init_db()
    project = db.create_project(title="z image autopilot")
    pid = str(project["id"])
    try:
        options = autopilot.normalize_options(
            {
                "input_mode": "script",
                "script": "땅이 혼돈하고 공허합니다.",
                "visual_source_mode": "comfyui_auto",
                "image_count": "auto",
            }
        )
        db.update_project(
            pid,
            autopilot_state="running",
            autopilot_phase="tts_wait",
            autopilot_job_id="auto_test",
            autopilot_options=options,
            script="땅이 혼돈하고 공허합니다.",
            compiled_script="땅이 혼돈하고 공허합니다.",
            sentences=["땅이 혼돈하고 공허합니다."],
        )
        initialize_autopilot_stage_status(pid, input_text=options["script"])

        def fake_wait_for_state(project_id: str, **kwargs):
            assert project_id == pid
            assert kwargs["field"] == "body_image_state"
            assert kwargs["phase"] == "image_wait"
            db.update_project(
                pid,
                body_image_state="done",
                body_image_mappings=[
                    {
                        "sentence_idx": 0,
                        "sentence_hash": "",
                        "path": "generated.png",
                        "prompt": "primordial earth, chaos, void, darkness over the deep",
                        "selected_reason": "z_image_turbo_korean",
                    }
                ],
            )
            return autopilot._update_runtime(
                pid,
                project=db.get_project(pid) or project,
                phase="image_wait",
                progress=72,
                last_log="Image generation completed.",
                event="wait_done",
            )

        monkeypatch.setattr(autopilot, "_wait_for_state", fake_wait_for_state)

        updated = autopilot._run_visual_asset_stage(pid, db.get_project(pid) or project, options)

        assert updated["body_image_state"] == "done"
        assert updated["pipeline_manifest"]["stage_status"]["image"]["state"] == "done"
    finally:
        db.delete_project(pid)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m pytest tests/test_autopilot_z_image_stage.py -q
```

Expected: FAIL because `_run_visual_asset_stage()` pauses with `IMAGE_GEN_DISABLED_D1`.

- [ ] **Step 3: Queue body image generation in autopilot**

In `app/services/autopilot.py`, replace the `IMAGE_GEN_DISABLED_D1` branch in `_run_visual_asset_stage()`:

```python
    if options["visual_source_mode"] in {"comfyui_auto", "hybrid"}:
        project = _update_runtime(
            pid,
            project=project,
            phase="image_enqueue",
            progress=62,
            last_log="Queued Z-Image generation.",
            debug_summary="Waiting for image worker.",
            event="phase_start",
        )
        db.update_project(
            pid,
            body_image_state="queued",
            body_image_progress=0,
            body_image_error="",
            body_image_phase="queued",
            body_image_last_log="Z-Image Turbo image job queued.",
            body_image_job_id="",
            body_image_started_at="",
            body_image_heartbeat_at="",
        )
        return _wait_for_state(
            pid,
            field="body_image_state",
            done_value="done",
            phase="image_wait",
            progress=72,
            message="Waiting for Z-Image worker to complete.",
            state_label="Image generation",
        )
```

- [ ] **Step 4: Ensure image prompts carry Genesis semantics**

In `app/services/image_prompt.py`, add a deterministic prompt contract for biblical/cosmic language:

```python
GENESIS_VISUAL_TERMS = {
    "혼돈": "formless chaos, swirling primordial matter",
    "공허": "vast empty void",
    "흑암": "deep darkness",
    "깊음": "abyssal deep waters",
    "빛": "first light breaking through darkness",
    "창세": "Genesis creation prologue",
    "성경": "ancient Korean Bible page, sacred manuscript",
}
```

In `build_z_image_prompt()`, merge matched terms into the positive prompt:

```python
    semantic_terms = [value for key, value in GENESIS_VISUAL_TERMS.items() if key in sentence]
    if semantic_terms:
        positive_parts.insert(0, ", ".join(semantic_terms))
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_autopilot_z_image_stage.py tests/test_image_prompt.py tests/test_z_image_workflow_submission.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/services/autopilot.py app/services/image_prompt.py tests/test_autopilot_z_image_stage.py tests/test_image_prompt.py
git commit -m "Queue semantic Z-Image generation in autopilot"
```

---

### Task 4: Failed TTS Consistency Must Not Produce `tts_state=done`

**Files:**
- Create: `tests/test_tts_quality_gate.py`
- Modify: `app/services/tts.py`
- Modify: `app/workers/tts_worker.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tts_quality_gate.py`:

```python
import json
import unittest
from unittest.mock import patch

from app import db
from app.services import tts


class TtsQualityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.project = db.create_project("tts quality")
        self.pid = self.project["id"]

    def tearDown(self) -> None:
        db.delete_project(self.pid)

    def test_failed_final_consistency_marks_tts_error(self) -> None:
        project_dir = db.project_dir(self.pid)
        tts_dir = project_dir / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)
        db.update_project(
            self.pid,
            script="문장 하나. 문장 둘.",
            compiled_script="문장 하나. 문장 둘.",
            sentences=["문장 하나.", "문장 둘."],
            tts_state="running",
            tts_profile={"synthesis_mode": "full_passage", "_consistency_retry_attempted": True},
        )

        def fake_save_report(output_dir, manifest):
            path = output_dir / "tts_consistency_report.json"
            path.write_text(
                json.dumps(
                    {
                        "metadata_consistent": True,
                        "audio_consistency_checked": True,
                        "audio_consistency_passed": False,
                        "recommended_tts_mode": "full_passage_or_reference_voice",
                    }
                ),
                encoding="utf-8",
            )
            return path

        with patch("app.services.tts._synthesize_manifest", return_value=None), patch(
            "app.services.tts.save_tts_consistency_report",
            side_effect=fake_save_report,
        ):
            with self.assertRaises(RuntimeError):
                tts._raise_if_final_tts_quality_failed(self.pid, tts_dir)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m pytest tests/test_tts_quality_gate.py -q
```

Expected: FAIL because `_raise_if_final_tts_quality_failed()` does not exist.

- [ ] **Step 3: Add final TTS quality gate**

In `app/services/tts.py`, add:

```python
def _load_tts_consistency_report(output_dir: Path) -> dict[str, object]:
    report_path = output_dir / "tts_consistency_report.json"
    if not report_path.exists():
        return {}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _raise_if_final_tts_quality_failed(pid: str, output_dir: Path) -> None:
    payload = _load_tts_consistency_report(output_dir)
    if payload.get("audio_consistency_checked") is not True:
        return
    if payload.get("audio_consistency_passed") is True and payload.get("metadata_consistent") is True:
        return
    project = db.get_project(pid)
    retry_attempted = bool((project or {}).get("tts_profile", {}).get("_consistency_retry_attempted"))
    if not retry_attempted:
        return
    raise RuntimeError(
        "TTS quality gate failed after retry; refusing to mark TTS done. "
        f"recommended={payload.get('recommended_tts_mode') or 'full_passage_or_reference_voice'}"
    )
```

After `save_tts_consistency_report(output_dir, manifest)` in `run_tts_job()`, call:

```python
        _raise_if_final_tts_quality_failed(pid, output_dir)
```

- [ ] **Step 4: Add retry behavior for first failure**

In `run_tts_job()`, after saving the consistency report and before marking `done`, if report failed and `_consistency_retry_attempted` is false, update project:

```python
        report = _load_tts_consistency_report(output_dir)
        if (
            report.get("audio_consistency_checked") is True
            and report.get("audio_consistency_passed") is not True
            and not profile.get("_consistency_retry_attempted")
        ):
            retry_profile = dict(profile)
            retry_profile["synthesis_mode"] = "full_passage"
            retry_profile["seed_mode"] = "fixed"
            retry_profile["_consistency_retry_attempted"] = True
            db.update_project(
                pid,
                tts_profile=retry_profile,
                tts_state="queued",
                tts_progress=0,
                tts_error="",
                tts_job_id="",
                tts_started_at="",
                tts_heartbeat_at="",
            )
            return
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_tts_quality_gate.py tests/test_tts_worker.py tests/test_tts_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/services/tts.py app/workers/tts_worker.py tests/test_tts_quality_gate.py
git commit -m "Fail TTS jobs that remain non-human after retry"
```

---

### Task 5: Visual Mismatch Report Must Block Empty/Generic Visuals

**Files:**
- Modify: `tests/test_visual_relevance.py`
- Modify: `app/services/visual_relevance.py`
- Modify: `app/services/preflight.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_visual_relevance.py`:

```python
def test_upload_only_empty_visual_selection_blocks_render_preflight(self):
    project = db.create_project("visual blocker")
    pid = project["id"]
    try:
        updated = db.update_project(
            pid,
            script="땅이 혼돈하고 공허합니다.",
            compiled_script="땅이 혼돈하고 공허합니다.",
            sentences=["땅이 혼돈하고 공허합니다."],
            media_order=["abstract.png"],
            visual_source_mode="upload_only",
            tts_state="done",
        )
        assert updated is not None

        report = build_preflight_report(updated)
        failed = {check["key"]: check for check in report["checks"] if not check["ok"]}

        self.assertIn("visual_relevance", failed)
        self.assertIn("semantic", failed["visual_relevance"]["message"].lower())
    finally:
        db.delete_project(pid)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m pytest tests/test_visual_relevance.py::VisualRelevanceTests::test_upload_only_empty_visual_selection_blocks_render_preflight -q
```

Expected: FAIL because upload-only empty semantic evidence currently becomes warn/pass.

- [ ] **Step 3: Add blocking visual relevance summary**

In `app/services/visual_relevance.py`, add:

```python
def render_blocking_visual_issues(project: ProjectRecord) -> list[str]:
    issues: list[str] = []
    sentence_count = len(project["sentences"])
    if project["visual_source_mode"] == "upload_only":
        if len(project["media_order"]) < sentence_count:
            issues.append(f"upload_only media coverage is incomplete: {len(project['media_order'])}/{sentence_count}")
        if not project["body_image_mappings"]:
            issues.append("upload_only visuals have no sentence-level semantic mapping")
        return issues
    mappings = project["body_image_mappings"]
    if len(mappings) < sentence_count:
        issues.append(f"generated visual mappings are incomplete: {len(mappings)}/{sentence_count}")
    for mapping in mappings:
        if not str(mapping.get("prompt") or "").strip():
            issues.append(f"sentence {mapping.get('sentence_idx')} has empty visual prompt")
        if not str(mapping.get("path") or "").strip():
            issues.append(f"sentence {mapping.get('sentence_idx')} has no selected image")
    return issues
```

- [ ] **Step 4: Wire visual relevance into preflight**

In `app/services/preflight.py`, import and call:

```python
from .visual_relevance import render_blocking_visual_issues
```

Append check:

```python
    visual_issues = render_blocking_visual_issues(project)
    checks.append(
        {
            "key": "visual_relevance",
            "ok": not visual_issues,
            "message": "Visual relevance evidence is sufficient." if not visual_issues else "; ".join(visual_issues),
        }
    )
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_visual_relevance.py tests/test_installed_quality_gates.py tests/test_render_preflight_gate.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/services/visual_relevance.py app/services/preflight.py tests/test_visual_relevance.py
git commit -m "Block render on missing visual relevance evidence"
```

---

### Task 6: Installed Genesis Workflow Smoke Must Fail Before Fixes And Pass After

**Files:**
- Modify: `scripts/smoke_installed_longform_workflow.py`
- Modify: `tests/test_installed_pipeline_quality_smoke.py`

- [ ] **Step 1: Extend smoke result contract**

In `scripts/smoke_installed_longform_workflow.py`, make the smoke write a JSON result with:

```python
{
    "project_id": pid,
    "script_contains_korean": True,
    "sentence_count": 6,
    "visual_mapping_count": 6,
    "render_plan_media_count": 6,
    "tts_consistency_passed": True,
    "blocking_preflight_checks": [],
    "render_state": "done",
    "output_path": "...output.mp4",
    "output_exists": True,
}
```

- [ ] **Step 2: Write unit test for result validator**

In `tests/test_installed_pipeline_quality_smoke.py`, add:

```python
from scripts.smoke_installed_longform_workflow import validate_installed_smoke_result


def test_installed_smoke_result_requires_visual_and_tts_quality():
    bad = {
        "script_contains_korean": True,
        "sentence_count": 6,
        "visual_mapping_count": 0,
        "render_plan_media_count": 0,
        "tts_consistency_passed": False,
        "blocking_preflight_checks": ["tts_consistency", "visual_relevance"],
        "render_state": "done",
        "output_exists": True,
    }

    issues = validate_installed_smoke_result(bad)

    assert "visual_mapping_count 0 does not match sentence_count 6" in issues
    assert "tts_consistency_passed is false" in issues
    assert "blocking preflight checks remain: tts_consistency, visual_relevance" in issues
```

- [ ] **Step 3: Implement validator**

In `scripts/smoke_installed_longform_workflow.py`, add:

```python
def validate_installed_smoke_result(result: dict[str, object]) -> list[str]:
    issues: list[str] = []
    sentence_count = int(result.get("sentence_count") or 0)
    visual_mapping_count = int(result.get("visual_mapping_count") or 0)
    render_plan_media_count = int(result.get("render_plan_media_count") or 0)
    if result.get("script_contains_korean") is not True:
        issues.append("script_contains_korean is false")
    if visual_mapping_count != sentence_count:
        issues.append(f"visual_mapping_count {visual_mapping_count} does not match sentence_count {sentence_count}")
    if render_plan_media_count != sentence_count:
        issues.append(f"render_plan_media_count {render_plan_media_count} does not match sentence_count {sentence_count}")
    if result.get("tts_consistency_passed") is not True:
        issues.append("tts_consistency_passed is false")
    blockers = result.get("blocking_preflight_checks")
    if isinstance(blockers, list) and blockers:
        issues.append("blocking preflight checks remain: " + ", ".join(str(item) for item in blockers))
    if result.get("render_state") != "done":
        issues.append(f"render_state is {result.get('render_state')!r}")
    if result.get("output_exists") is not True:
        issues.append("output_exists is false")
    return issues
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_installed_pipeline_quality_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Run installed smoke manually**

Run after rebuilding/reinstalling:

```powershell
python scripts/smoke_installed_longform_workflow.py --base-url http://127.0.0.1:<installed-port> --script-preset genesis-opening --require-quality
```

Expected:
- Generates or maps 6 sentence visuals.
- TTS consistency passes.
- No local-render blocking preflight failures.
- Render output exists.

- [ ] **Step 6: Commit**

```powershell
git add scripts/smoke_installed_longform_workflow.py tests/test_installed_pipeline_quality_smoke.py
git commit -m "Add installed workflow quality smoke gates"
```

---

### Task 7: UI Must Show Hard Blockers And Stop Render Actions

**Files:**
- Modify: `app/static/app.js`
- Modify: `app/static/index.html`
- Modify: `app/static/style.css`
- Modify: `tests/test_static_workflow_ui.py`

- [ ] **Step 1: Write UI contract test**

In `tests/test_static_workflow_ui.py`, add expected strings:

```python
def test_static_ui_contains_render_blocker_controls():
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")

    assert "render-blockers-panel" in html
    assert "renderBlockers" in js
    assert "blocking_checks" in js
    assert "Render blocked" in js
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m pytest tests/test_static_workflow_ui.py -q
```

Expected: FAIL until UI strings exist.

- [ ] **Step 3: Add blockers panel**

In `app/static/index.html`, add:

```html
<section id="render-blockers-panel" class="status-panel" hidden>
  <h2>Render blocked</h2>
  <ul id="render-blockers-list"></ul>
</section>
```

- [ ] **Step 4: Render blockers in JavaScript**

In `app/static/app.js`, add:

```javascript
function renderBlockers(detail) {
  const panel = document.getElementById("render-blockers-panel");
  const list = document.getElementById("render-blockers-list");
  if (!panel || !list) return;
  const checks = detail?.blocking_checks || [];
  panel.hidden = checks.length === 0;
  list.innerHTML = checks.map((key) => `<li>${escapeHtml(key)}</li>`).join("");
}
```

When render start receives HTTP `409`, parse the JSON and call:

```javascript
renderBlockers(errorPayload.detail || errorPayload);
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest tests/test_static_workflow_ui.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/static/app.js app/static/index.html app/static/style.css tests/test_static_workflow_ui.py
git commit -m "Show render blockers in installed UI"
```

---

### Task 8: Full Verification And Reinstall

**Files:**
- Test/build only.

- [ ] **Step 1: Run focused quality tests**

```powershell
python -m pytest tests/test_render_preflight_gate.py tests/test_installed_quality_gates.py tests/test_autopilot_z_image_stage.py tests/test_tts_quality_gate.py tests/test_visual_relevance.py tests/test_static_workflow_ui.py -q
```

Expected: PASS.

- [ ] **Step 2: Run recovery suite**

```powershell
python -m pytest tests/test_desktop_packaging.py tests/test_pipeline_manifest.py tests/test_prompt_contract.py tests/test_character_workflow_contract.py tests/test_image_prompt.py tests/test_visual_relevance.py tests/test_image_quality.py tests/test_tts_pipeline.py tests/test_tts_worker.py tests/test_tts_presets.py tests/test_autopilot_routes.py tests/test_autopilot_stage_sync.py tests/test_workflow_status.py tests/test_static_workflow_ui.py tests/test_installed_pipeline_quality_smoke.py tests/test_preset_text_health.py tests/test_korean_longform_script_integrity.py tests/test_script_compile.py tests/test_z_image_workflow_submission.py tests/test_pipeline_runner.py tests/test_render_preflight_gate.py tests/test_installed_quality_gates.py tests/test_autopilot_z_image_stage.py tests/test_tts_quality_gate.py -q
```

Expected: PASS.

- [ ] **Step 3: Build sidecar**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_pyinstaller_sidecar.ps1
```

Expected: `dist\newauto-sidecar\newauto-sidecar.exe` exists.

- [ ] **Step 4: Build installer**

```powershell
npm.cmd run tauri:build
```

Expected: `src-tauri\target\release\bundle\nsis\newauto Studio_0.1.0_x64-setup.exe` exists.

- [ ] **Step 5: Reinstall**

```powershell
$installer = "src-tauri\target\release\bundle\nsis\newauto Studio_0.1.0_x64-setup.exe"
$p = Start-Process -FilePath $installer -ArgumentList "/S" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "installer failed: $($p.ExitCode)" }
```

Expected: `ExitCode=0`.

- [ ] **Step 6: Run installed Genesis smoke**

```powershell
python scripts/smoke_installed_longform_workflow.py --script-preset genesis-opening --require-quality
```

Expected:
- output exists,
- generated/mapped visual count equals sentence count,
- render plan media count equals sentence count,
- TTS consistency passes,
- no local render blockers.

- [ ] **Step 7: Commit final verification notes**

```powershell
git add docs/superpowers/plans/2026-05-19-installed-video-quality-recovery.md
git commit -m "Plan installed video quality recovery"
```

---

## Self-Review

Spec coverage:
- Image mismatch is covered by Tasks 2, 3, and 5.
- TTS noise/non-human output is covered by Tasks 1 and 4.
- Bad render despite failed preflight is covered by Task 1.
- Installed app workflow verification is covered by Task 6 and Task 8.
- UI feedback is covered by Task 7.

No placeholders:
- The plan contains exact files, test names, commands, and code snippets.
- There is no `TBD` or “write tests later” step.

Residual risks:
- Real Z-Image quality still depends on ComfyUI availability and model quality. The plan makes that dependency explicit and blocks render when generated mappings or semantic evidence are missing.
- Objective “human voice” validation is limited by signal metrics. A later enhancement can add ASR transcription similarity, but this plan already blocks the exact failed consistency path observed in `fb6c4ef0b663`.
