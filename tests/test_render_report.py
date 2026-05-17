import json
import os
import unittest
from typing import ClassVar
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app
from app.services import render_report
from app.services.flow_prompting import generate_flow_prompt_manifest
from app.services.operator_summary import operator_summary_path
from app.services.render_report import build_render_report, load_render_report, save_render_report
from app.services.visual_relevance import write_final_scene_review


class RenderReportTests(unittest.TestCase):
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

    def create_project(self, title: str = "render-report-test") -> str:
        response = self.client.post("/api/projects", data={"title": title})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_render_report_roundtrip_and_route(self) -> None:
        project_id = self.create_project()
        project_dir = db.project_dir(project_id)
        (project_dir / "output.mp4").write_bytes(b"video")
        overlay_dir = project_dir / "hyperframes_overlay"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        overlay_path = overlay_dir / "overlay.mov"
        overlay_path.write_bytes(b"overlay")
        (overlay_dir / "overlay_report.json").write_text(
            json.dumps({"ok": True, "overlay_path": str(overlay_path), "ffprobe": {"pix_fmt": "yuva444p12le"}}),
            encoding="utf-8",
        )
        (project_dir / "media").mkdir(parents=True, exist_ok=True)
        (project_dir / "media" / "scene0.png").write_bytes(b"img")
        db.update_project(
            project_id,
            autopilot_state="done",
            autopilot_phase="done",
            autopilot_job_id="auto_render_001",
            autopilot_options={"input_mode": "keyword"},
            body_image_options={
                "hyperframes_overlay_enabled": True,
                "hyperframes_overlay_status": "done",
                "hyperframes_overlay_report_path": str(overlay_dir / "overlay_report.json"),
            },
            render_started_at="2026-04-26T07:00:00+00:00",
            render_formats=["landscape"],
            render_plan={
                "version": 2,
                "total_duration": 2.0,
                "segments": [
                    {
                        "region": "intro",
                        "start": 0.0,
                        "end": 2.0,
                        "sentence_idx": 0,
                        "media": [{"path": "scene0.png", "kind": "image"}],
                        "motion": "slow_zoom_in",
                        "effect": "fade",
                        "caption_style": "emphasis",
                    }
                ],
            },
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        write_final_scene_review(project)

        with patch.object(
            render_report,
            "_probe_audio_stream",
            return_value={
                "audio_codec": "aac",
                "audio_sample_rate": 48000,
                "audio_channels": 2,
                "audio_bitrate": 192000,
                "audio_profile_ok": True,
            },
        ), patch.object(
            render_report,
            "_probe_audio_volume",
            return_value={
                "audio_mean_volume_db": -8.1,
                "audio_max_volume_db": -0.9,
                "audio_audibility_ok": True,
            },
        ):
            report = build_render_report(
                project,
                status="done",
                audio_duration_sec=2.0,
                audio_raw_duration_sec=2.3,
                audio_normalized_duration_sec=2.1,
                subtitle_cue_count=1,
                fallback_used=False,
                ffmpeg_log_tail="mux ok",
            )
        save_render_report(report)
        loaded = load_render_report(project_id)

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["status"], "done")
        self.assertEqual(loaded["autopilot_job_id"], "auto_render_001")
        self.assertEqual(loaded["autopilot_input_mode"], "keyword")
        self.assertEqual(loaded["subtitle_cue_count"], 1)
        self.assertEqual(loaded["audio_raw_duration_sec"], 2.3)
        self.assertEqual(loaded["audio_normalized_duration_sec"], 2.1)
        self.assertEqual(loaded["segments"][0]["caption_style"], "emphasis")
        self.assertTrue(loaded["final_scene_review_exists"])
        self.assertTrue(loaded["final_scene_review_path"].endswith("final_scene_review.json"))

        response = self.client.get(f"/api/projects/{project_id}/render-report")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "done")
        self.assertEqual(payload["autopilot_state"], "done")
        self.assertEqual(payload["outputs"][0]["format"], "landscape")
        self.assertEqual(payload["outputs"][0]["audio_sample_rate"], 48000)
        self.assertEqual(payload["outputs"][0]["audio_channels"], 2)
        self.assertTrue(payload["outputs"][0]["audio_profile_ok"])
        self.assertTrue(payload["outputs"][0]["audio_audibility_ok"])
        self.assertEqual(payload["outputs"][0]["hyperframes_overlay_status"], "done")
        self.assertTrue(payload["outputs"][0]["hyperframes_overlay_path"].endswith("overlay.mov"))
        self.assertEqual(payload["outputs"][0]["hyperframes_overlay_pix_fmt"], "yuva444p12le")
        self.assertTrue(payload["final_scene_review_exists"])

        review_response = self.client.get(f"/api/projects/{project_id}/final-scene-review")
        self.assertEqual(review_response.status_code, 200)
        review_payload = review_response.json()
        self.assertEqual(review_payload["project_id"], project_id)
        self.assertIn("entries", review_payload)

    def test_render_report_route_returns_404_when_missing(self) -> None:
        project_id = self.create_project()
        response = self.client.get(f"/api/projects/{project_id}/render-report")
        self.assertEqual(response.status_code, 404)
        review_response = self.client.get(f"/api/projects/{project_id}/final-scene-review")
        self.assertEqual(review_response.status_code, 404)

    def test_operator_summary_route_reports_flow_coverage(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            script="첫 문장입니다. 둘째 문장입니다.",
            sentences=["첫 문장입니다.", "둘째 문장입니다."],
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "flow_assets/scene_001.png",
                    "prompt": "first scene",
                }
            ],
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        generate_flow_prompt_manifest(project)

        response = self.client.get(f"/api/projects/{project_id}/operator-summary")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["project_id"], project_id)
        self.assertEqual(payload["current_stage"], "flow")
        self.assertEqual(payload["recommended_next_tool"], "continue_video_workflow")
        self.assertEqual(payload["next_autonomous_action"], "generate_missing_flow_images")
        self.assertEqual(payload["script_sentence_count"], 2)
        self.assertEqual(payload["flow_prompt_count"], 2)
        self.assertEqual(payload["generated_image_count"], 1)
        self.assertEqual(payload["asset_coverage"]["missing"], [2])
        self.assertFalse(payload["human_intervention_required"])
        self.assertTrue(operator_summary_path(project_id).exists())


if __name__ == "__main__":
    unittest.main()
