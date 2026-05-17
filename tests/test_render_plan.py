import os
import unittest
from typing import ClassVar

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app
from app.services.render_plan import build_render_plan


class RenderPlanTests(unittest.TestCase):
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
        response = self.client.post("/api/projects", data={"title": "render-plan-test"})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_build_render_plan_from_scene_plan(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            scene_plan={
                "version": 1,
                "format": "landscape",
                "total_duration": 5.5,
                "scenes": [
                    {
                        "idx": 1,
                        "sentence_idx": 0,
                        "text": "첫 문장",
                        "region": "intro",
                        "duration_sec": 2.0,
                        "visual_intent": "첫 문장",
                        "prompt": "prompt one",
                        "style": "documentary cinematic",
                        "media_path": "scene0.png",
                    },
                    {
                        "idx": 2,
                        "sentence_idx": 1,
                        "text": "둘째 문장",
                        "region": "body",
                        "duration_sec": 3.5,
                        "visual_intent": "둘째 문장",
                        "prompt": "prompt two",
                        "style": "documentary cinematic",
                        "media_path": "scene1.png",
                    },
                ],
            },
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        render_plan = build_render_plan(project)
        self.assertEqual(render_plan["version"], 2)
        self.assertEqual(len(render_plan["segments"]), 2)
        self.assertEqual(render_plan["segments"][0]["start"], 0.0)
        self.assertEqual(render_plan["segments"][0]["end"], 2.0)
        self.assertEqual(render_plan["segments"][0]["sentence_idx"], 0)
        self.assertEqual(render_plan["segments"][1]["media"][0]["path"], "scene1.png")
        self.assertEqual(render_plan["segments"][0]["caption_style"], "emphasis")
        self.assertEqual(render_plan["segments"][0]["motion"], "still_locked")
        self.assertEqual(render_plan["segments"][1]["motion"], "still_locked")

    def test_build_render_plan_locks_still_when_only_one_unique_image_exists(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            scene_plan={
                "version": 1,
                "format": "landscape",
                "total_duration": 6.0,
                "scenes": [
                    {
                        "idx": 1,
                        "sentence_idx": 0,
                        "text": "첫 문장",
                        "region": "body",
                        "duration_sec": 3.0,
                        "visual_intent": "첫 문장",
                        "prompt": "prompt one",
                        "style": "documentary cinematic",
                        "media_path": "shared.png",
                    },
                    {
                        "idx": 2,
                        "sentence_idx": 1,
                        "text": "둘째 문장",
                        "region": "body",
                        "duration_sec": 3.0,
                        "visual_intent": "둘째 문장",
                        "prompt": "prompt two",
                        "style": "documentary cinematic",
                        "media_path": "shared.png",
                    },
                ],
            },
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        render_plan = build_render_plan(project)
        self.assertEqual(render_plan["segments"][0]["motion"], "still_locked")
        self.assertEqual(render_plan["segments"][1]["motion"], "still_locked")

    def test_build_render_plan_uses_micro_motion_for_environmental_science_images(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            scene_plan={
                "version": 1,
                "format": "landscape",
                "total_duration": 3.2,
                "scenes": [
                    {
                        "idx": 1,
                        "sentence_idx": 0,
                        "text": "leaf film decomposes in soil",
                        "region": "body",
                        "duration_sec": 3.2,
                        "visual_intent": "leaf film in soil",
                        "prompt": "editorial macro photo of biodegradable leaf film in soil",
                        "style": "environmental science editorial",
                        "media_path": "scene0.png",
                        "domain": "agriculture_environment",
                    }
                ],
            },
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        render_plan = build_render_plan(project)
        self.assertEqual(render_plan["segments"][0]["motion"], "micro_motion_locked")

    def test_build_render_plan_keeps_diagrams_still_locked(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            scene_plan={
                "version": 1,
                "format": "landscape",
                "total_duration": 3.2,
                "scenes": [
                    {
                        "idx": 1,
                        "sentence_idx": 0,
                        "text": "leaf film comparison",
                        "region": "body",
                        "duration_sec": 3.2,
                        "visual_intent": "comparison chart",
                        "prompt": "simple_diagram comparison chart",
                        "style": "simple_diagram",
                        "media_path": "scene0.png",
                        "domain": "agriculture_environment",
                    }
                ],
            },
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        render_plan = build_render_plan(project)
        self.assertEqual(render_plan["segments"][0]["motion"], "still_locked")

    def test_render_plan_build_route_persists_plan(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            scene_plan={
                "version": 1,
                "format": "landscape",
                "total_duration": 2.0,
                "scenes": [
                    {
                        "idx": 1,
                        "sentence_idx": 0,
                        "text": "한 문장",
                        "region": "body",
                        "duration_sec": 2.0,
                        "visual_intent": "한 문장",
                        "prompt": "prompt",
                        "style": "documentary cinematic",
                        "media_path": "scene0.png",
                    }
                ],
            },
        )
        response = self.client.post(f"/api/projects/{project_id}/render-plan/build")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 2)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertIsNotNone(project["render_plan"])
        assert project["render_plan"] is not None
        self.assertEqual(project["render_plan"]["segments"][0]["media"][0]["path"], "scene0.png")
        self.assertEqual(project["render_plan"]["segments"][0]["effect"], "none")

    def test_build_render_plan_photos_only_fallback_uses_nonzero_segments(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            sentences=["첫 문장입니다.", "두 번째 문장입니다."],
            media_order=["one.jpg", "two.jpg"],
            scene_plan={},
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None

        render_plan = build_render_plan(project)

        self.assertEqual(render_plan["version"], 1)
        self.assertGreater(render_plan["total_duration"], 0.0)
        self.assertEqual(len(render_plan["segments"]), 2)
        self.assertEqual(render_plan["segments"][0]["start"], 0.0)
        self.assertGreater(render_plan["segments"][0]["end"], render_plan["segments"][0]["start"])
        self.assertEqual(render_plan["segments"][1]["start"], render_plan["segments"][0]["end"])
        self.assertEqual(render_plan["segments"][1]["end"], render_plan["total_duration"])

    def test_build_render_plan_photos_only_fallback_uses_tts_duration_when_present(self) -> None:
        project_id = self.create_project()
        project_dir = db.project_dir(project_id)
        tts_dir = project_dir / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)
        (tts_dir / "timings.json").write_text(
            '[{"idx":0,"text":"a","start":0,"end":1.5,"dur":1.5},'
            '{"idx":1,"text":"b","start":1.5,"end":4.0,"dur":2.5}]',
            encoding="utf-8",
        )
        db.update_project(
            project_id,
            sentences=["a", "b"],
            media_order=["one.jpg", "two.jpg"],
            scene_plan={},
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None

        render_plan = build_render_plan(project)

        self.assertEqual(render_plan["total_duration"], 4.0)
        self.assertEqual(render_plan["segments"][0]["end"], 2.0)
        self.assertEqual(render_plan["segments"][1]["start"], 2.0)


if __name__ == "__main__":
    unittest.main()
