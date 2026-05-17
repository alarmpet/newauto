import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app import db
from app.services.diagnostics import collect_project_diagnostics


class DiagnosticsBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.project_ids: list[str] = []

    def tearDown(self) -> None:
        for project_id in self.project_ids:
            db.delete_project(project_id)

    def test_collect_project_diagnostics_writes_expected_bundle_files(self) -> None:
        project = db.create_project("diagnostics-test")
        project_id = project["id"]
        self.project_ids.append(project_id)
        project_dir = db.project_dir(project_id)
        media_dir = project_dir / "media"
        tts_dir = project_dir / "tts"
        media_dir.mkdir(parents=True, exist_ok=True)
        tts_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "output.mp4").write_bytes(b"video")
        (project_dir / "render_report.json").write_text('{"status":"done","outputs":[]}', encoding="utf-8")
        (tts_dir / "timings.json").write_text('[{"idx":0,"text":"hello","start":0,"end":1,"dur":1}]', encoding="utf-8")
        (tts_dir / "tts_run_manifest.json").write_text(
            json.dumps(
                {
                    "voice_preset": "default",
                    "sentences": [{"idx": 0, "text": "hello"}],
                }
            ),
            encoding="utf-8",
        )
        (media_dir / "scene0.png").write_bytes(b"image")
        db.update_project(
            project_id,
            sentences=["hello"],
            tts_state="done",
            media_order=["scene0.png"],
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene0.png",
                    "prompt": "simple image",
                    "selected_reason": "test",
                }
            ],
            render_state="done",
            render_formats=["landscape"],
        )

        def fake_run(command: list[str], **kwargs: object):
            class Result:
                returncode = 0
                stdout = '{"streams":[],"format":{"duration":"1.0"}}' if "ffprobe" in command[0] else ""
                stderr = "mean_volume: -8.0 dB\nmax_volume: -1.0 dB" if "ffmpeg" in command[0] else ""

            return Result()

        with patch("app.services.diagnostics.shutil.which", side_effect=lambda name: name), patch(
            "app.services.diagnostics.subprocess.run",
            side_effect=fake_run,
        ), patch(
            "app.services.preflight.probe_media_dimensions",
            return_value=(1920, 1080),
        ):
            manifest = collect_project_diagnostics(project_id)

        bundle_dir = Path(str(manifest["bundle_dir"]))
        self.assertTrue(bundle_dir.exists())
        expected_files = {
            "ffprobe_output.json",
            "audio_volumedetect.txt",
            "render_report.json",
            "preflight_report.json",
            "tts_manifest_excerpt.json",
            "visual_mismatch_report.md",
            "visual_mismatch_report.json",
            "final_scene_review.json",
            "operator_summary.json",
            "diagnostic_contact_sheet.jpg",
            "diagnostics_manifest.json",
        }
        self.assertTrue(expected_files.issubset(set(manifest["files"])))
        preflight = json.loads((bundle_dir / "preflight_report.json").read_text(encoding="utf-8"))
        self.assertIn("checks", preflight)
        volumedetect = (bundle_dir / "audio_volumedetect.txt").read_text(encoding="utf-8")
        self.assertIn("mean_volume", volumedetect)

    def test_collect_project_diagnostics_copies_hyperframes_overlay_artifacts(self) -> None:
        project = db.create_project("diag-hyperframes")
        project_id = project["id"]
        self.project_ids.append(project_id)
        project_dir = db.project_dir(project_id)
        overlay_dir = project_dir / "hyperframes_overlay"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        (overlay_dir / "index.html").write_text("<html></html>", encoding="utf-8")
        (overlay_dir / "overlay_plan.json").write_text("{}", encoding="utf-8")
        (overlay_dir / "overlay.mov").write_bytes(b"mov")
        (overlay_dir / "overlay_report.json").write_text(
            json.dumps({"ok": True, "overlay_path": str(overlay_dir / "overlay.mov")}),
            encoding="utf-8",
        )

        with patch("app.services.diagnostics.shutil.which", return_value=None), patch(
            "app.services.preflight.probe_media_dimensions",
            return_value=(0, 0),
        ):
            manifest = collect_project_diagnostics(project_id)

        bundle_dir = Path(str(manifest["bundle_dir"]))
        self.assertTrue((bundle_dir / "hyperframes_overlay" / "index.html").exists())
        self.assertTrue((bundle_dir / "hyperframes_overlay" / "overlay_plan.json").exists())
        self.assertTrue((bundle_dir / "hyperframes_overlay" / "overlay_report.json").exists())
        self.assertTrue((bundle_dir / "hyperframes_overlay" / "overlay.mov").exists())

    def test_collect_project_diagnostics_lists_stickman_evidence_files(self) -> None:
        project = db.create_project("diag-stickman-evidence")
        project_id = project["id"]
        self.project_ids.append(project_id)
        project_dir = db.project_dir(project_id)
        evidence_dir = project_dir / "diagnostics_bundle" / "stickman_evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "prompts_lora_on.json").write_text("{}", encoding="utf-8")
        (evidence_dir / "prompts_lora_off.json").write_text("{}", encoding="utf-8")
        (evidence_dir / "frame_reviews.json").write_text("{}", encoding="utf-8")

        with patch("app.services.diagnostics.shutil.which", return_value=None), patch(
            "app.services.preflight.probe_media_dimensions",
            return_value=(0, 0),
        ):
            manifest = collect_project_diagnostics(project_id)

        self.assertEqual(
            manifest["stickman_evidence_files"],
            [
                "stickman_evidence/frame_reviews.json",
                "stickman_evidence/prompts_lora_off.json",
                "stickman_evidence/prompts_lora_on.json",
            ],
        )


if __name__ == "__main__":
    unittest.main()
