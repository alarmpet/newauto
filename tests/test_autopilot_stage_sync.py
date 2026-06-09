from app import db
from app.services import autopilot
from app.services.pipeline_runner import initialize_autopilot_stage_status


def test_runtime_updates_sync_pipeline_stage_status():
    db.init_db()
    project = db.create_project(title="stage-sync")
    pid = str(project["id"])
    try:
        initialize_autopilot_stage_status(pid, input_text="A sentence.")

        project = autopilot._update_runtime(
            pid,
            project=db.get_project(pid) or project,
            phase="tts_enqueue",
            progress=40,
            last_log="Queued TTS generation.",
            event="phase_start",
        )
        assert project["pipeline_manifest"]["stage_status"]["tts"]["state"] == "running"

        project = autopilot._update_runtime(
            pid,
            project=project,
            phase="tts_wait",
            progress=52,
            last_log="TTS generation completed.",
            event="wait_done",
        )
        assert project["pipeline_manifest"]["stage_status"]["tts"]["state"] == "done"

        project = autopilot._update_runtime(
            pid,
            project=project,
            phase="preflight",
            progress=84,
            last_log="Preflight failed.",
            error_code="PREFLIGHT_AUDIO",
            event="paused",
        )
        preflight = project["pipeline_manifest"]["stage_status"]["preflight"]
        assert preflight["state"] == "error"
        assert preflight["error_code"] == "PREFLIGHT_AUDIO"
    finally:
        db.delete_project(pid)


def test_prepare_input_stage_saves_script_and_marks_stage_done():
    db.init_db()
    project = db.create_project(title="prepare-stage")
    pid = str(project["id"])
    try:
        options = autopilot.normalize_options(
            {
                "input_mode": "script",
                "script": "First sentence. Second sentence.",
                "image_count": "auto",
            }
        )
        db.update_project(
            pid,
            autopilot_state="running",
            autopilot_phase="prepare_input",
            autopilot_job_id="auto_test",
            autopilot_options=options,
        )
        initialize_autopilot_stage_status(pid, input_text=options["script"])

        updated = autopilot._run_prepare_input_stage(pid, db.get_project(pid) or project, options)

        assert updated["script"] == "First sentence. Second sentence."
        assert updated["compiled_script"].strip()
        assert updated["sentences"]
        assert (db.project_dir(pid) / "script.txt").read_text(encoding="utf-8") == options["script"]
        prepare_status = updated["pipeline_manifest"]["stage_status"]["prepare_input"]
        assert prepare_status["state"] == "done"
        assert prepare_status["output_hash"] != ""
    finally:
        db.delete_project(pid)


def test_source_collection_stage_marks_prepare_done_and_queues_draft(monkeypatch):
    db.init_db()
    project = db.create_project(title="source-stage")
    pid = str(project["id"])
    try:
        options = autopilot.normalize_options(
            {
                "input_mode": "url",
                "url": "https://example.com/story",
                "image_count": "auto",
            }
        )
        db.update_project(
            pid,
            autopilot_state="running",
            autopilot_phase="prepare_input",
            autopilot_job_id="auto_test",
            autopilot_options=options,
        )
        initialize_autopilot_stage_status(pid, input_text=options["url"])

        def fake_collect_url_source(project_id: str, url: str):
            assert project_id == pid
            assert url == options["url"]
            return db.update_project(
                pid,
                source_draft_state="done",
                source_draft_progress=100,
                source_draft_input_mode="url",
                source_draft_query=url,
                source_draft_sources=[
                    {
                        "id": "s1",
                        "url": url,
                        "final_url": url,
                        "title": "Story",
                        "domain": "example.com",
                        "author": "",
                        "published_at": "",
                        "language": "en",
                        "excerpt": "fact",
                        "fetched_at": "2026-05-19T00:00:00+00:00",
                        "word_count": 1,
                    }
                ],
                source_draft_fact_notes=[{"source_id": "s1", "note": "fact"}],
                source_draft_warnings=[],
                source_draft_risk_score=0.0,
            )

        monkeypatch.setattr(autopilot, "_collect_url_source", fake_collect_url_source)

        updated = autopilot._run_source_collection_stage(pid, db.get_project(pid) or project, options)

        assert updated["source_draft_state"] == "queued"
        assert updated["source_draft_input_mode"] == "url"
        assert updated["source_draft_sources"]
        assert updated["pipeline_manifest"]["stage_status"]["prepare_input"]["state"] == "done"
        assert updated["pipeline_manifest"]["stage_status"]["script_compile"]["state"] == "running"
    finally:
        db.delete_project(pid)


def test_source_draft_apply_stage_marks_script_compile_done():
    db.init_db()
    project = db.create_project(title="apply-stage")
    pid = str(project["id"])
    try:
        options = autopilot.normalize_options(
            {
                "input_mode": "url",
                "url": "https://example.com/story",
                "image_count": "auto",
            }
        )
        db.update_project(
            pid,
            autopilot_state="running",
            autopilot_phase="source_generate",
            autopilot_job_id="auto_test",
            autopilot_options=options,
            source_draft_state="done",
            source_draft_regenerate_mode="",
            source_draft_risk_score=0.0,
            source_draft_script="Generated first sentence. Generated second sentence.",
        )
        initialize_autopilot_stage_status(pid, input_text=options["url"])

        updated = autopilot._run_source_draft_apply_stage(pid, db.get_project(pid) or project, options)

        assert updated["script"] == "Generated first sentence. Generated second sentence."
        assert updated["compiled_script"].strip()
        assert updated["sentences"]
        assert (db.project_dir(pid) / "compiled_script.txt").read_text(encoding="utf-8").strip()
        script_status = updated["pipeline_manifest"]["stage_status"]["script_compile"]
        assert script_status["state"] == "done"
        assert script_status["output_hash"] != ""
    finally:
        db.delete_project(pid)


def test_tts_stage_applies_autopilot_profile_and_queues_tts(monkeypatch):
    db.init_db()
    project = db.create_project(title="tts-stage")
    pid = str(project["id"])
    try:
        options = autopilot.normalize_options(
            {
                "input_mode": "script",
                "script": "First sentence. Second sentence.",
                "image_count": "auto",
            }
        )
        db.update_project(
            pid,
            autopilot_state="running",
            autopilot_phase="source_apply",
            autopilot_job_id="auto_test",
            autopilot_options=options,
            script="First sentence. Second sentence.",
            compiled_script="First sentence. Second sentence.",
            sentences=["First sentence.", "Second sentence."],
            voice_preset="auto",
            tts_profile={},
        )
        initialize_autopilot_stage_status(pid, input_text=options["script"])

        def fake_wait_for_state(project_id: str, **kwargs):
            assert project_id == pid
            assert kwargs["field"] == "tts_state"
            assert kwargs["phase"] == "tts_wait"
            db.update_project(pid, tts_state="done")
            return autopilot._update_runtime(
                pid,
                project=db.get_project(pid) or project,
                phase="tts_wait",
                progress=kwargs["progress"],
                last_log="TTS generation completed.",
                event="wait_done",
            )

        monkeypatch.setattr(autopilot, "_wait_for_state", fake_wait_for_state)

        updated = autopilot._run_tts_stage(pid, db.get_project(pid) or project)

        assert updated["tts_state"] == "done"
        assert updated["voice_preset"] == autopilot.AUTOPILOT_DEFAULT_VOICE_PRESET
        assert updated["tts_profile"]["synthesis_mode"] == "full_passage"
        assert updated["pipeline_manifest"]["stage_status"]["tts"]["state"] == "done"
    finally:
        db.delete_project(pid)


def test_visual_asset_stage_queues_z_image_generation(monkeypatch):
    db.init_db()
    project = db.create_project(title="visual-stage")
    pid = str(project["id"])
    try:
        options = autopilot.normalize_options(
            {
                "input_mode": "script",
                "script": "First sentence.",
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
            visual_source_mode="comfyui_auto",
            script="First sentence.",
            compiled_script="First sentence.",
            sentences=["First sentence."],
        )
        initialize_autopilot_stage_status(pid, input_text=options["script"])

        def fake_wait_for_state(project_id: str, **kwargs):
            assert project_id == pid
            assert kwargs["field"] == "body_image_state"
            db.update_project(
                pid,
                body_image_state="done",
                body_image_mappings=[
                    {
                        "sentence_idx": 0,
                        "sentence_hash": "",
                        "path": "generated.png",
                        "prompt": "First sentence visual",
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

        assert updated["autopilot_state"] == "running"
        assert updated["body_image_state"] == "done"
        image_status = updated["pipeline_manifest"]["stage_status"]["image"]
        assert image_status["state"] == "done"
    finally:
        db.delete_project(pid)


def test_render_plan_stage_persists_scene_and_render_plan(monkeypatch):
    db.init_db()
    project = db.create_project(title="render-plan-stage")
    pid = str(project["id"])
    try:
        options = autopilot.normalize_options(
            {
                "input_mode": "script",
                "script": "First sentence.",
                "visual_source_mode": "upload_only",
                "image_count": "auto",
            }
        )
        db.update_project(
            pid,
            autopilot_state="running",
            autopilot_phase="tts_wait",
            autopilot_job_id="auto_test",
            autopilot_options=options,
            script="First sentence.",
            compiled_script="First sentence.",
            sentences=["First sentence."],
            media_order=["scene.png"],
        )
        initialize_autopilot_stage_status(pid, input_text=options["script"])

        scene_plan = {
            "version": 1,
            "format": "landscape",
            "total_duration": 2.0,
            "scenes": [],
        }
        render_plan = {
            "version": 1,
            "total_duration": 2.0,
            "segments": [],
        }
        monkeypatch.setattr(autopilot, "build_scene_plan", lambda project, render_format: scene_plan)
        monkeypatch.setattr(autopilot, "build_render_plan", lambda project: render_plan)

        updated = autopilot._run_render_plan_stage(pid, db.get_project(pid) or project)

        assert updated["scene_plan"] == scene_plan
        assert updated["render_plan"] == render_plan
        status = updated["pipeline_manifest"]["stage_status"]["render_plan"]
        assert status["state"] == "done"
        assert status["output_hash"] != ""
    finally:
        db.delete_project(pid)


def test_preflight_stage_marks_done_and_error(monkeypatch):
    db.init_db()
    project = db.create_project(title="preflight-stage")
    pid = str(project["id"])
    try:
        db.update_project(
            pid,
            autopilot_state="running",
            autopilot_phase="plan_refresh",
            autopilot_job_id="auto_test",
        )
        initialize_autopilot_stage_status(pid, input_text="First sentence.")

        monkeypatch.setattr(
            autopilot,
            "build_preflight_report",
            lambda project: {"ok": True, "checks": [{"key": "audio", "ok": True, "message": "ok"}]},
        )
        updated = autopilot._run_preflight_stage(pid, db.get_project(pid) or project)
        status = updated["pipeline_manifest"]["stage_status"]["preflight"]
        assert status["state"] == "done"
        assert status["output_hash"] != ""

        monkeypatch.setattr(
            autopilot,
            "build_preflight_report",
            lambda project: {"ok": False, "checks": [{"key": "audio", "ok": False, "message": "audio missing"}]},
        )
        failed = autopilot._run_preflight_stage(pid, db.get_project(pid) or project)
        failed_status = failed["pipeline_manifest"]["stage_status"]["preflight"]
        assert failed["autopilot_state"] == "paused"
        assert failed_status["state"] == "error"
        assert failed_status["error_code"] == "PREFLIGHT_AUDIO"
    finally:
        db.delete_project(pid)


def test_render_stage_queues_waits_and_completes_autopilot(monkeypatch):
    db.init_db()
    project = db.create_project(title="render-stage")
    pid = str(project["id"])
    try:
        db.update_project(
            pid,
            autopilot_state="running",
            autopilot_phase="preflight",
            autopilot_job_id="auto_test",
        )
        initialize_autopilot_stage_status(pid, input_text="First sentence.")

        def fake_wait_for_state(project_id: str, **kwargs):
            assert project_id == pid
            assert kwargs["field"] == "render_state"
            assert kwargs["phase"] == "render_wait"
            db.update_project(pid, render_state="done")
            return autopilot._update_runtime(
                pid,
                project=db.get_project(pid) or project,
                phase="render_wait",
                progress=kwargs["progress"],
                last_log="Render completed.",
                event="wait_done",
            )

        monkeypatch.setattr(autopilot, "_wait_for_state", fake_wait_for_state)
        monkeypatch.setattr(autopilot, "load_render_report", lambda project_id: {"outputs": ["out.mp4"]})

        updated = autopilot._run_render_stage(pid, db.get_project(pid) or project)

        assert updated["autopilot_state"] == "done"
        assert updated["autopilot_phase"] == "done"
        assert updated["render_state"] == "done"
        status = updated["pipeline_manifest"]["stage_status"]["render"]
        assert status["state"] == "done"
        assert status["output_hash"] != ""
        assert updated["autopilot_last_log"] == "Render completed with 1 output(s)."
    finally:
        db.delete_project(pid)
