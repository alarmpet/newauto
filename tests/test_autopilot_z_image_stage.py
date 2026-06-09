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
                "script": "땅이 혼돈하고 공허하며 흑암이 깊음 위에 있습니다.",
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
            script=options["script"],
            compiled_script=options["script"],
            sentences=["땅이 혼돈하고 공허하며 흑암이 깊음 위에 있습니다."],
        )
        initialize_autopilot_stage_status(pid, input_text=options["script"])

        def fake_wait_for_state(project_id: str, **kwargs):
            assert project_id == pid
            assert kwargs["field"] == "body_image_state"
            assert kwargs["phase"] == "image_wait"
            queued = db.get_project(pid)
            assert queued is not None
            assert queued["body_image_state"] == "queued"
            assert queued["body_image_options"]["image_backend_version"] == "v1"
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

