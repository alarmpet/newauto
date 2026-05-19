from app.services.pipeline_manifest import (
    build_initial_pipeline_manifest,
    record_image_attempt,
    record_tts_artifact,
    record_visual_artifact,
    update_stage_status,
    validate_pipeline_manifest,
)


def test_pipeline_manifest_tracks_every_stage_for_each_sentence():
    manifest = build_initial_pipeline_manifest(
        project_id="p1",
        title="Genesis test",
        sentences=["Light appears.", "Waters divide."],
    )

    assert manifest["version"] == 1
    assert [item["sentence_idx"] for item in manifest["segments"]] == [0, 1]
    assert manifest["segments"][0]["script_text"] == "Light appears."
    assert manifest["segments"][0]["visual"] is None
    assert manifest["segments"][0]["image"] is None
    assert manifest["segments"][0]["tts"] is None
    validate_pipeline_manifest(manifest)


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
    manifest = update_stage_status(
        manifest,
        "visual",
        state="done",
        input_hash="script-1",
        output_hash="prompt-1",
    )

    segment = manifest["segments"][0]
    assert segment["visual"] is not None
    assert segment["visual"]["positive_prompt"] == "bright light"
    assert segment["image"] is not None
    assert segment["image"]["attempts"][0]["selected"] is True
    assert segment["tts"] is not None
    assert segment["tts"]["duration_sec"] == 2.0
    assert manifest["stage_status"]["visual"]["state"] == "done"
