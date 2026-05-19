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
        self.assertEqual(scene_plan["scenes"][1]["uploaded_media_index"], 1)

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

