import os
import unittest
from typing import ClassVar

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app


class SceneCardRouteTests(unittest.TestCase):
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
        response = self.client.post("/api/projects", data={"title": "scene-card-test"})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_scene_cards_are_built_from_sentences_and_media_without_scene_plan(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            sentences=["첫 문장입니다.", "두 번째 문장입니다."],
            media_order=["one.jpg"],
        )

        response = self.client.get(f"/api/projects/{project_id}/scene-cards")

        self.assertEqual(response.status_code, 200)
        cards = response.json()
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["scene_id"], "scene-001")
        self.assertEqual(cards[0]["visual_asset_path"], "one.jpg")
        self.assertIn("voice_missing", cards[0]["warnings"])
        self.assertEqual(cards[1]["visual_asset_path"], "")
        self.assertIn("visual_missing", cards[1]["warnings"])

    def test_patch_scene_card_persists_locked_subtitle_and_motion(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            sentences=["첫 문장입니다.", "두 번째 문장입니다."],
            media_order=["one.jpg", "two.jpg"],
            render_plan={
                "version": 1,
                "total_duration": 4.0,
                "segments": [
                    {
                        "region": "body",
                        "start": 0.0,
                        "end": 2.0,
                        "media": [{"path": "one.jpg", "kind": "image"}],
                        "sentence_idx": 0,
                        "motion": "none",
                        "effect": "none",
                        "caption_style": "plain",
                    },
                    {
                        "region": "body",
                        "start": 2.0,
                        "end": 4.0,
                        "media": [{"path": "two.jpg", "kind": "image"}],
                        "sentence_idx": 1,
                        "motion": "none",
                        "effect": "none",
                        "caption_style": "plain",
                    },
                ],
            },
        )

        response = self.client.patch(
            f"/api/projects/{project_id}/scene-cards/1",
            json={
                "locked": True,
                "motion": "pan_left",
                "subtitle_override": {
                    "font_size": 64,
                    "primary_color": "#FFEE00",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        card = response.json()
        self.assertTrue(card["locked"])
        self.assertEqual(card["motion"], "pan_left")
        self.assertEqual(card["subtitle_override"]["font_size"], 64)
        self.assertEqual(card["subtitle_override"]["primary_color"], "#FFEE00")

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertIsNotNone(project["scene_plan"])
        self.assertIsNotNone(project["render_plan"])
        assert project["scene_plan"] is not None
        assert project["render_plan"] is not None
        self.assertTrue(project["scene_plan"]["scenes"][1]["locked"])
        self.assertEqual(project["render_plan"]["segments"][1]["motion"], "pan_left")


if __name__ == "__main__":
    unittest.main()
