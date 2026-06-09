from app import db
from app.services.pipeline_runner import (
    first_incomplete_stage,
    initialize_autopilot_stage_status,
    mark_stage_done,
    mark_stage_error,
    mark_stage_running,
)


def test_stage_transition_helpers_preserve_manifest_artifacts():
    db.init_db()
    project = db.create_project(title="runner")
    pid = str(project["id"])
    try:
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
        failed = mark_stage_error(
            pid,
            "visual_plan",
            error_code="PROMPT_EMPTY",
            recovery_hint="Regenerate prompts.",
        )

        assert running["stage_status"]["script_compile"]["state"] == "running"
        assert done["stage_status"]["script_compile"]["state"] == "done"
        assert failed["stage_status"]["visual_plan"]["state"] == "error"
        assert failed["stage_status"]["visual_plan"]["error_code"] == "PROMPT_EMPTY"
        assert failed["segments"][0]["visual"] == {"positive_prompt": "x"}
    finally:
        db.delete_project(pid)


def test_first_incomplete_stage_returns_next_non_done_stage():
    db.init_db()
    project = db.create_project(title="runner")
    pid = str(project["id"])
    try:
        initialize_autopilot_stage_status(pid, input_text="A sentence.")
        mark_stage_done(pid, "prepare_input", output_text="A sentence.")
        mark_stage_done(pid, "script_compile", output_text="compiled")
        project = db.get_project(pid)

        assert project is not None
        assert first_incomplete_stage(project) == "visual_plan"
    finally:
        db.delete_project(pid)
