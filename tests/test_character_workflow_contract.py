from app.workers import image_worker
from app import db
from app.services.comfyui_pipeline import import_history_image


class FakeComfyImageResult:
    filename = "out.png"
    subfolder = ""
    type = "output"


def test_image_worker_passes_character_descriptor_to_z_image(monkeypatch):
    captured: dict[str, object] = {}
    project = {
        "id": "p1",
        "sentences": ["Mina walks through a bright studio."],
        "body_image_options": {},
        "body_image_mappings": [],
    }

    monkeypatch.setattr(image_worker.db, "get_project", lambda pid: project)
    monkeypatch.setattr(image_worker.db, "update_project", lambda *args, **kwargs: project)
    monkeypatch.setattr(image_worker.db, "touch_body_image_heartbeat", lambda pid: None)
    monkeypatch.setattr(image_worker, "import_history_image", lambda *args, **kwargs: None)
    monkeypatch.setattr(image_worker, "load_character_descriptor", lambda pid: {"name": "Mina"})

    def fake_submit(client, **kwargs):
        captured.update(kwargs)
        return "prompt-1", [FakeComfyImageResult()]

    monkeypatch.setattr(image_worker, "submit_z_image_workflow", fake_submit)

    image_worker._process_project("p1")

    assert captured["character_descriptor"]["name"] == "Mina"


def test_import_history_image_records_selected_attempt_in_pipeline_manifest(monkeypatch, tmp_path):
    db.init_db()
    project = db.create_project("image-attempt-test")
    source = tmp_path / "out.png"
    source.write_bytes(b"png")
    try:
        project = db.update_project(
            project["id"],
            compiled_script="Mina enters.",
            sentences=["Mina enters."],
        )
        assert project is not None
        monkeypatch.setattr("app.services.comfyui_pipeline.resolve_comfy_output_path", lambda result: source)

        import_history_image(
            project,
            result=FakeComfyImageResult(),
            prompt="prompt",
            prompt_id="pid",
            sentence_idx=0,
            candidate_score=0.8,
            seed=42,
            issue_codes=["LOW_CONTRAST"],
            character_descriptor_applied=True,
        )

        updated = db.get_project(project["id"])
        assert updated is not None
        image = updated["pipeline_manifest"]["segments"][0]["image"]
        assert image is not None
        attempt = image["attempts"][0]
        assert attempt["prompt_hash"]
        assert attempt["candidate_score"] == 0.8
        assert attempt["seed"] == 42
        assert attempt["issue_codes"] == ["LOW_CONTRAST"]
        assert updated["body_image_mappings"][0]["character_descriptor_applied"] is True
    finally:
        db.delete_project(project["id"])
