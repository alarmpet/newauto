import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.services.preflight import build_preflight_report
from app.services.render import (
    _build_visual_track,
    _run,
    _zoompan_filter,
)


class RenderVisualTrackTests(unittest.TestCase):
    def test_zoompan_filter_includes_explicit_landscape_output_size(self) -> None:
        filter_graph = _zoompan_filter(0, 3.0, 1920, 1080)
        self.assertIn("s=1920x1080", filter_graph)
        self.assertNotIn("1280x720", filter_graph)

    def test_zoompan_filter_includes_explicit_shorts_output_size(self) -> None:
        filter_graph = _zoompan_filter(0, 3.0, 1080, 1920)
        self.assertIn("s=1080x1920", filter_graph)
        self.assertNotIn("720x1280", filter_graph)

    def test_build_visual_track_uses_uniform_landscape_size_for_mixed_media(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            commands.append(command)
            return ""

        with patch("app.services.render._run", side_effect=fake_run), patch(
            "app.services.render._ffmpeg",
            return_value="ffmpeg",
        ):
            _build_visual_track(
                [Path("alpha.png"), Path("beta.mp4"), Path("gamma.jpg")],
                9.0,
                Path("out.mp4"),
                "landscape",
                True,
            )

        self.assertEqual(len(commands), 1)
        filter_graph = commands[0][commands[0].index("-filter_complex") + 1]
        self.assertIn("s=1920x1080", filter_graph)
        self.assertIn("pad=1920:1080", filter_graph)
        self.assertIn("concat=n=3:v=1:a=0[vout]", filter_graph)

    def test_run_preserves_utf8_korean_stderr(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["ffmpeg"],
            returncode=1,
            stdout=b"",
            stderr="ffmpeg input error: 다운로드_2_.png\n".encode("utf-8"),
        )
        with patch("app.services.render.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "다운로드_2_.png"):
                _run(["ffmpeg"])

    def test_preflight_reports_invalid_media_metadata(self) -> None:
        db.init_db()
        project = db.create_project("render-preflight")
        project_id = project["id"]
        project_dir = db.project_dir(project_id)
        media_dir = project_dir / "media"
        tts_dir = project_dir / "tts"
        media_dir.mkdir(parents=True, exist_ok=True)
        tts_dir.mkdir(parents=True, exist_ok=True)
        (media_dir / "broken.mp4").write_bytes(b"broken")
        (tts_dir / "timings.json").write_text("[]", encoding="utf-8")
        db.update_project(
            project_id,
            sentences=["hello"],
            media_order=["broken.mp4"],
            tts_state="done",
        )
        fetched_project = db.get_project(project_id)
        self.assertIsNotNone(fetched_project)
        assert fetched_project is not None
        with patch("app.services.preflight.find_invalid_media_files", return_value=["broken.mp4 (video stream metadata unavailable)"]):
            report = build_preflight_report(fetched_project)
        check_map = {check["key"]: check for check in report["checks"]}
        self.assertIn("media_metadata", check_map)
        self.assertFalse(check_map["media_metadata"]["ok"])
        self.assertIn("broken.mp4", check_map["media_metadata"]["message"])
        db.delete_project(project_id)
