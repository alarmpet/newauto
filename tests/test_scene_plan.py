import json
import os
import unittest
from typing import ClassVar
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app
from app.services.scene_plan import build_scene_plan
from app.services.visual_relevance import sentence_hash


class ScenePlanTests(unittest.TestCase):
    client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        db.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def setUp(self) -> None:
        self.project_ids: list[str] = []

    def tearDown(self) -> None:
        for project_id in self.project_ids:
            project = db.get_project(project_id)
            if project is not None:
                self.client.delete(f"/api/projects/{project_id}")

    def create_project(self) -> str:
        response = self.client.post("/api/projects", data={"title": "scene-plan-test"})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_build_scene_plan_uses_timings_mappings_and_visual_metadata(self) -> None:
        project_id = self.create_project()
        first_sentence = "브라우저 자동화를 설명하는 첫 문장"
        second_sentence = "두 번째 문장"
        db.update_project(
            project_id,
            sentences=[first_sentence, second_sentence],
            body_image_options={"disable_llm_visual_planner": True},
            regional_sentences=[
                {"idx": 0, "text": first_sentence, "region": "intro"},
                {"idx": 1, "text": second_sentence, "region": "body"},
            ],
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene0.png",
                    "prompt": "prompt zero",
                    "sentence_text": first_sentence,
                    "sentence_hash": sentence_hash(first_sentence),
                    "project_id": project_id,
                    "prompt_id": "prompt-0",
                },
            ],
            source_draft_fact_notes=[{"source_id": "src1", "note": "browser automation fact"}],
            source_draft_sources=[{
                "id": "src1",
                "url": "https://example.com/a",
                "final_url": "https://example.com/a",
                "title": "Article title",
                "domain": "example.com",
                "author": "",
                "published_at": "",
                "language": "ko",
                "excerpt": "summary",
                "fetched_at": "",
                "word_count": 100,
            }],
        )
        tts_dir = db.project_dir(project_id) / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)
        (tts_dir / "timings.json").write_text(
            json.dumps([
                {"idx": 0, "text": first_sentence, "start": 0.0, "end": 2.0, "dur": 2.0, "region": "intro"},
                {"idx": 1, "text": second_sentence, "start": 2.0, "end": 5.5, "dur": 3.5, "region": "body"},
            ], ensure_ascii=False),
            encoding="utf-8",
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        plan = build_scene_plan(project)
        self.assertEqual(plan["version"], 2)
        self.assertEqual(len(plan["scenes"]), 2)
        self.assertEqual(plan["scenes"][0]["duration_sec"], 2.0)
        self.assertEqual(plan["scenes"][0]["media_path"], "scene0.png")
        self.assertEqual(plan["scenes"][1]["region"], "body")
        self.assertIn("key_concept", plan["scenes"][0])
        self.assertIn("subject", plan["scenes"][0])
        self.assertIn("props", plan["scenes"][0])

    def test_build_scene_plan_assigns_silence_gap_to_current_scene(self) -> None:
        project_id = self.create_project()
        first_sentence = "첫 문장"
        second_sentence = "두 번째 문장"
        db.update_project(
            project_id,
            sentences=[first_sentence, second_sentence],
            body_image_options={"disable_llm_visual_planner": True},
            regional_sentences=[
                {"idx": 0, "text": first_sentence, "region": "body"},
                {"idx": 1, "text": second_sentence, "region": "body"},
            ],
        )
        tts_dir = db.project_dir(project_id) / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)
        (tts_dir / "timings.json").write_text(
            json.dumps([
                {"idx": 0, "text": first_sentence, "start": 0.0, "end": 2.0, "dur": 2.0, "region": "body"},
                {"idx": 1, "text": second_sentence, "start": 2.7, "end": 5.5, "dur": 2.8, "region": "body"},
            ], ensure_ascii=False),
            encoding="utf-8",
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        plan = build_scene_plan(project)
        self.assertEqual(plan["scenes"][0]["duration_sec"], 2.7)
        self.assertEqual(plan["scenes"][1]["duration_sec"], 2.8)
        self.assertEqual(plan["total_duration"], 5.5)

    def test_build_scene_plan_ignores_stale_generated_mapping(self) -> None:
        project_id = self.create_project()
        current_sentence = "현재 문장"
        stale_sentence = "예전 문장"
        db.update_project(
            project_id,
            visual_source_mode="comfyui_auto",
            body_image_options={"disable_llm_visual_planner": True},
            sentences=[current_sentence],
            regional_sentences=[{"idx": 0, "text": current_sentence, "region": "body"}],
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "old.png",
                    "prompt": "old prompt",
                    "sentence_text": stale_sentence,
                    "sentence_hash": sentence_hash(stale_sentence),
                    "project_id": project_id,
                    "prompt_id": "old-prompt",
                },
            ],
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        plan = build_scene_plan(project)
        self.assertEqual(plan["scenes"][0]["media_path"], "")
        self.assertNotEqual(plan["scenes"][0]["prompt"], "old prompt")

    def test_scene_plan_build_route_persists_plan(self) -> None:
        project_id = self.create_project()
        sentence = "한 문장"
        db.update_project(
            project_id,
            sentences=[sentence],
            body_image_options={"disable_llm_visual_planner": True},
            regional_sentences=[{"idx": 0, "text": sentence, "region": "body"}],
            source_draft_fact_notes=[{"source_id": "src1", "note": "fact"}],
            source_draft_sources=[{
                "id": "src1",
                "url": "https://example.com/a",
                "final_url": "https://example.com/a",
                "title": "Article title",
                "domain": "example.com",
                "author": "",
                "published_at": "",
                "language": "ko",
                "excerpt": "summary",
                "fetched_at": "",
                "word_count": 100,
            }],
        )
        response = self.client.post(f"/api/projects/{project_id}/scene-plan/build?render_format=landscape")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["format"], "landscape")
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertIsNotNone(project["scene_plan"])
        assert project["scene_plan"] is not None
        self.assertEqual(project["scene_plan"]["version"], 2)
        self.assertEqual(project["scene_plan"]["scenes"][0]["sentence_idx"], 0)

    def test_build_scene_plan_uses_visual_plan_core_meaning(self) -> None:
        project_id = self.create_project()
        sentence = "속도보다 방향이 중요합니다."
        db.update_project(
            project_id,
            body_image_options={"disable_llm_visual_planner": True},
            sentences=[sentence],
            regional_sentences=[{"idx": 0, "text": sentence, "region": "body"}],
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        with patch(
            "app.services.scene_plan.build_scene_visual_plan",
            return_value=[
                {
                    "sentence_idx": 0,
                    "sentence": sentence,
                    "core_meaning": "빠름보다 방향 설정이 먼저라는 뜻",
                    "primary_keywords": ["direction", "pace"],
                    "secondary_keywords": ["clock"],
                    "visual_metaphor": "compass on a desk map",
                    "subject_modes": ["environment", "object_metaphor"],
                    "must_show": ["compass on a map"],
                    "may_show": ["clock"],
                    "avoid": ["two similar people"],
                    "prompt_hint": "medium wide shot",
                    "vocab_refs": ["direction and life choice"],
                    "domain": "essay",
                    "source": "llm",
                }
            ],
        ):
            plan = build_scene_plan(project)
        self.assertEqual(plan["scenes"][0]["visual_intent"], "빠름보다 방향 설정이 먼저라는 뜻")
        self.assertEqual(plan["scenes"][0]["core_meaning"], "빠름보다 방향 설정이 먼저라는 뜻")
        self.assertEqual(plan["scenes"][0]["domain"], "essay")


if __name__ == "__main__":
    unittest.main()
