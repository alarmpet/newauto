from app.services.prompt_director_manifest import build_directed_prompt_for_sentence
from app import db
from app.services.prompt_director_manifest import write_prompt_director_manifest


def test_prompt_director_outputs_sentence_specific_visual_contract():
    project = {
        "id": "p1",
        "title": "창세기 창조 이야기",
        "script": "빛이 나타났습니다.\n바다와 새가 등장했습니다.",
        "sentences": ["빛이 나타났습니다.", "바다와 새가 등장했습니다."],
    }

    first, first_item = build_directed_prompt_for_sentence(project, 0)
    second, second_item = build_directed_prompt_for_sentence(project, 1)

    assert first.positive != second.positive
    assert first_item["sentence_hash"] != second_item["sentence_hash"]
    assert first_item["visual_brief"]["must_show"]
    assert "positive_prompt" in first_item
    assert first_item["visual_plan"]["sentence"] == project["sentences"][0]


def test_write_prompt_manifest_records_visual_artifacts():
    db.init_db()
    project = db.create_project("창세기 창조 이야기")
    try:
        project = db.update_project(
            project["id"],
            script="빛이 나타났습니다.\n바다와 새가 등장했습니다.",
            sentences=["빛이 나타났습니다.", "바다와 새가 등장했습니다."],
        )
        assert project is not None

        payload = write_prompt_director_manifest(project)
        updated = db.get_project(project["id"])
        assert updated is not None

        visual = updated["pipeline_manifest"]["segments"][0]["visual"]
        assert visual is not None
        assert payload["prompts"][0]["prompt_hash"] == visual["prompt_hash"]
        assert updated["pipeline_manifest"]["stage_status"]["visual"]["state"] == "done"
    finally:
        db.delete_project(project["id"])
