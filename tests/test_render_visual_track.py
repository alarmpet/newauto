import io
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db
from app.services.preflight import build_preflight_report
from app.services.render import (
    ProgressEvent,
    _build_visual_track,
    _format_progress_detail,
    _parse_progress_time,
    _phase_progress_callback,
    _run,
    _run_with_progress,
    _zoompan_filter,
)


class RenderVisualTrackTests(unittest.TestCase):
    def test_parse_progress_time_from_out_time(self) -> None:
        self.assertEqual(_parse_progress_time("out_time=00:01:30.50"), 90.5)

    def test_format_progress_detail_includes_eta(self) -> None:
        detail = _format_progress_detail(
            ProgressEvent(
                phase_pct=43,
                speed_x=1.31,
                frame=4921,
                fps=24.0,
                elapsed_sec=204.0,
                eta_sec=342,
                output_size_bytes=0,
            )
        )
        self.assertIn("43%", detail)
        self.assertIn("1.31x", detail)
        self.assertIn("frame 4921", detail)
        self.assertIn("ETA 00:05:42", detail)

    def test_phase_progress_callback_maps_global_progress(self) -> None:
        captured: dict[str, object] = {}

        def fake_update_project(pid: str, **fields: object) -> None:
            captured["pid"] = pid
            captured.update(fields)

        with patch("app.services.render.db.update_project", side_effect=fake_update_project):
            callback = _phase_progress_callback("pid123", "build_visual_landscape", 70, 12)
            callback(
                ProgressEvent(
                    phase_pct=50,
                    speed_x=1.2,
                    frame=100,
                    fps=24.0,
                    elapsed_sec=50.0,
                    eta_sec=20,
                    output_size_bytes=1024,
                )
            )

        self.assertEqual(captured["pid"], "pid123")
        self.assertEqual(captured["render_progress"], 76)
        self.assertEqual(captured["render_phase"], "build_visual_landscape")
        self.assertEqual(captured["render_phase_pct"], 50)
        self.assertIn("50%", str(captured["render_progress_detail"]))

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

    def test_run_with_progress_emits_events_from_out_time(self) -> None:
        class FakePopen:
            def __init__(self) -> None:
                self.stdout = io.BytesIO(
                    b"frame=25\nfps=24.0\nout_time=00:00:02.00\nspeed=1.50x\nprogress=continue\n"
                    b"frame=50\nfps=24.0\nout_time=00:00:04.00\nspeed=2.00x\nprogress=end\n"
                )
                self.stderr = io.BytesIO(b"")
                self.returncode = 0

            def poll(self) -> int | None:
                stdout_done = self.stdout.tell() >= len(self.stdout.getvalue())
                stderr_done = self.stderr.tell() >= len(self.stderr.getvalue())
                if stdout_done and stderr_done:
                    return self.returncode
                return None

            def wait(self) -> int:
                self.stdout.seek(len(self.stdout.getvalue()))
                self.stderr.seek(len(self.stderr.getvalue()))
                return self.returncode

        events: list[ProgressEvent] = []
        with patch("app.services.render.subprocess.Popen", return_value=FakePopen()):
            _run_with_progress(
                ["ffmpeg", "-i", "in.mp4", "out.mp4"],
                expected_duration_sec=4.0,
                on_progress=events.append,
            )

        self.assertGreaterEqual(len(events), 1)
        self.assertEqual(events[-1].phase_pct, 100)
        self.assertEqual(events[-1].frame, 50)
