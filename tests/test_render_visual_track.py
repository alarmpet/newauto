import io
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import db
from app.services.preflight import build_preflight_report
from app.services import render
from app.services.render import (
    ProgressEvent,
    _build_visual_track,
    _caption_style_map_from_render_plan,
    _concat_audio,
    _duration_guard_tolerance,
    _format_progress_detail,
    _hyperframes_required,
    _hyperframes_overlay_path,
    _prepare_hyperframes_overlay,
    _mux,
    _normalize_audio,
    _micro_motion_locked_filter,
    _parse_progress_time,
    _plan_visual_segment_frames,
    _phase_progress_callback,
    _resolve_visual_segments,
    _run,
    _run_with_progress,
    _segment_effect_filter,
    _validate_output_duration,
    _validate_audio_duration_alignment,
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
        self.assertIn("trim=end_frame=90", filter_graph)
        self.assertIn("setpts=N/(30*TB)", filter_graph)

    def test_zoompan_filter_includes_explicit_shorts_output_size(self) -> None:
        filter_graph = _zoompan_filter(0, 3.0, 1080, 1920)
        self.assertIn("s=1080x1920", filter_graph)
        self.assertNotIn("720x1280", filter_graph)
        self.assertIn("trim=end_frame=90", filter_graph)

    def test_zoompan_filter_supports_zoom_out_motion(self) -> None:
        filter_graph = _zoompan_filter(0, 3.0, 1920, 1080, "slow_zoom_out")
        self.assertIn("1.10-on/1200", filter_graph)

    def test_micro_motion_locked_filter_uses_locked_frame_count(self) -> None:
        filter_graph = _micro_motion_locked_filter(0, 90, 1920, 1080)
        self.assertIn("zoompan", filter_graph)
        self.assertIn("d=90", filter_graph)
        self.assertIn("trim=end_frame=90", filter_graph)
        self.assertIn("setpts=N/(30*TB)", filter_graph)
        self.assertIn("s=1920x1080", filter_graph)

    def test_segment_effect_filter_adds_fade_when_requested(self) -> None:
        filter_graph = _segment_effect_filter(3.0, "fade")
        self.assertIn("fade=t=in", filter_graph)
        self.assertIn("fade=t=out", filter_graph)

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

    def test_build_visual_track_uses_segment_motion_and_effect(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            commands.append(command)
            return ""

        segments = [
            render.VisualSegment(
                path=Path("alpha.png"),
                duration_sec=2.0,
                motion="slow_zoom_out",
                effect="fade",
            ),
            render.VisualSegment(
                path=Path("beta.jpg"),
                duration_sec=1.5,
                motion="none",
                effect="none",
            ),
        ]

        with patch("app.services.render._run", side_effect=fake_run), patch(
            "app.services.render._ffmpeg",
            return_value="ffmpeg",
        ):
            _build_visual_track(
                [Path("alpha.png"), Path("beta.jpg")],
                3.5,
                Path("out.mp4"),
                "landscape",
                False,
                segments=segments,
            )

        filter_graph = commands[0][commands[0].index("-filter_complex") + 1]
        self.assertIn("1.10-on/1200", filter_graph)
        self.assertIn("fade=t=in", filter_graph)
        self.assertIn("trim=end_frame=45", filter_graph)

    def test_build_visual_track_omits_image_t_flag_when_kenburns_is_enabled(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            commands.append(command)
            return ""

        with patch("app.services.render._run", side_effect=fake_run), patch(
            "app.services.render._ffmpeg",
            return_value="ffmpeg",
        ):
            _build_visual_track(
                [Path("alpha.png"), Path("beta.jpg")],
                6.0,
                Path("out.mp4"),
                "landscape",
                True,
            )

        self.assertEqual(len(commands), 1)
        command = commands[0]
        image_input_segment = command[2:8]
        self.assertEqual(image_input_segment[:4], ["-loop", "1", "-framerate", "1"])
        self.assertNotIn("-t", image_input_segment)

    def test_build_visual_track_uses_micro_motion_locked_frame_plan(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            commands.append(command)
            return ""

        segments = [
            render.VisualSegment(
                path=Path("alpha.png"),
                duration_sec=3.0,
                motion="micro_motion_locked",
                effect="none",
            )
        ]

        with patch("app.services.render._run", side_effect=fake_run), patch(
            "app.services.render._ffmpeg",
            return_value="ffmpeg",
        ):
            _build_visual_track(
                [Path("alpha.png")],
                3.0,
                Path("out.mp4"),
                "landscape",
                False,
                segments=segments,
            )

        filter_graph = commands[0][commands[0].index("-filter_complex") + 1]
        self.assertIn("zoompan", filter_graph)
        self.assertIn("d=90", filter_graph)
        self.assertIn("trim=end_frame=90", filter_graph)

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

    def test_concat_audio_inserts_gap_files_between_sentences(self) -> None:
        with TemporaryDirectory() as tmp:
            tts_dir = Path(tmp)
            (tts_dir / "0000.wav").write_bytes(b"a")
            (tts_dir / "0001.wav").write_bytes(b"b")
            captured: dict[str, str] = {}

            def fake_run(command: list[str]) -> str:
                concat_path = Path(command[command.index("-i") + 1])
                captured["concat_text"] = concat_path.read_text(encoding="utf-8")
                return ""

            with patch("app.services.render._run", side_effect=fake_run), patch(
                "app.services.render._ffmpeg",
                return_value="ffmpeg",
            ):
                _concat_audio(
                    tts_dir,
                    [
                        {"idx": 0, "text": "one", "start": 0.0, "end": 1.0, "dur": 1.0},
                        {"idx": 1, "text": "two", "start": 1.3, "end": 2.3, "dur": 1.0},
                    ],
                    tts_dir / "out.wav",
                )

            concat_text = captured["concat_text"]
            self.assertIn("0000.wav", concat_text)
            self.assertIn("0001.wav", concat_text)
            self.assertIn("gap_0000.wav", concat_text)

    def test_normalize_audio_forces_pcm_24k_mono(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            commands.append(command)
            return ""

        with patch("app.services.render._run", side_effect=fake_run), patch(
            "app.services.render._ffmpeg",
            return_value="ffmpeg",
        ):
            _normalize_audio(Path("in.wav"), Path("out.wav"))

        command = commands[0]
        self.assertIn("-af", command)
        self.assertIn("highpass=f=80,loudnorm=I=-14:TP=-1.5:LRA=11", command)
        self.assertIn("-ar", command)
        self.assertIn("24000", command)
        self.assertIn("-ac", command)
        self.assertIn("1", command)
        self.assertIn("-c:a", command)
        self.assertIn("pcm_s16le", command)

    def test_mux_forces_player_compatible_aac_48k_stereo(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            commands.append(command)
            return ""

        with patch("app.services.render._run", side_effect=fake_run), patch(
            "app.services.render._ffmpeg",
            return_value="ffmpeg",
        ):
            _mux(Path("visual.mp4"), Path("audio.wav"), Path("subtitles.ass"), Path("out.mp4"))

        command = commands[0]
        self.assertIn("-c:a", command)
        self.assertIn("aac", command)
        self.assertIn("-ar", command)
        self.assertIn("48000", command)
        self.assertIn("-ac", command)
        self.assertIn("2", command)
        self.assertIn("-b:a", command)
        self.assertIn("192k", command)

    def test_mux_composites_overlay_before_subtitles_in_single_filter_complex(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> str:
            commands.append(command)
            return ""

        with patch("app.services.render._run", side_effect=fake_run), patch(
            "app.services.render._ffmpeg",
            return_value="ffmpeg",
        ):
            _mux(
                Path("visual.mp4"),
                Path("audio.wav"),
                Path("subtitles.ass"),
                Path("out.mp4"),
                overlay_path=Path("overlay.webm"),
            )

        command = commands[0]
        self.assertIn("-filter_complex", command)
        filter_graph = command[command.index("-filter_complex") + 1]
        self.assertIn("[0:v][1:v]overlay=0:0:format=auto:shortest=1[base]", filter_graph)
        self.assertIn("[base]ass=", filter_graph)
        self.assertNotIn("-vf", command)
        self.assertEqual(command[command.index("-map") + 1], "[v]")
        self.assertIn("2:a:0", command)

    def test_hyperframes_required_honors_project_option(self) -> None:
        self.assertTrue(_hyperframes_required({"hyperframes_overlay_required": True}, env={}))

    def test_hyperframes_required_honors_strict_env(self) -> None:
        self.assertTrue(_hyperframes_required({}, env={"NEWAUTO_HYPERFRAMES_STRICT": "1"}))

    def test_hyperframes_required_defaults_false(self) -> None:
        self.assertFalse(_hyperframes_required({}, env={}))

    def test_hyperframes_overlay_path_prefers_report_path_when_alpha_fallback_is_mov(self) -> None:
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            overlay_dir = project_dir / "hyperframes_overlay"
            overlay_dir.mkdir()
            overlay_mov = overlay_dir / "overlay.mov"
            overlay_mov.write_bytes(b"mov")
            (overlay_dir / "overlay_report.json").write_text(
                json.dumps({"ok": True, "overlay_path": str(overlay_mov)}),
                encoding="utf-8",
            )

            self.assertEqual(_hyperframes_overlay_path(project_dir), overlay_mov)

    def test_hyperframes_overlay_path_accepts_report_path_relative_to_cwd(self) -> None:
        project_dir = Path("storage/projects/hyperframes_smoke")
        overlay_dir = project_dir / "hyperframes_overlay"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        overlay_mov = overlay_dir / "overlay.mov"
        overlay_mov.write_bytes(b"mov")
        (overlay_dir / "overlay_report.json").write_text(
            json.dumps({"ok": True, "overlay_path": str(overlay_mov)}),
            encoding="utf-8",
        )

        self.assertEqual(_hyperframes_overlay_path(project_dir), overlay_mov)

    def test_hyperframes_overlay_path_falls_back_to_webm_then_mov(self) -> None:
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            overlay_dir = project_dir / "hyperframes_overlay"
            overlay_dir.mkdir()
            overlay_mov = overlay_dir / "overlay.mov"
            overlay_mov.write_bytes(b"mov")

            self.assertEqual(_hyperframes_overlay_path(project_dir), overlay_mov)

    def test_prepare_hyperframes_overlay_generates_and_renders_when_enabled(self) -> None:
        with TemporaryDirectory() as tmp, patch("app.services.render.write_overlay_project") as write_project, patch(
            "app.services.render.render_hyperframes_overlay"
        ) as render_overlay:
            project_dir = Path(tmp)
            overlay_mov = project_dir / "hyperframes_overlay" / "overlay.mov"
            overlay_mov.parent.mkdir()
            overlay_mov.write_bytes(b"mov")
            render_overlay.return_value = {"ok": True, "overlay_path": str(overlay_mov)}

            result = _prepare_hyperframes_overlay(
                project_dir,
                [{"idx": 0, "text": "엔비디아", "start": 0.0, "end": 3.0, "dur": 3.0}],
                {"hyperframes_overlay_enabled": True},
                render_format="landscape",
            )

            self.assertEqual(result.overlay_path, overlay_mov)
            self.assertEqual(result.status, "done")
            write_project.assert_called_once()
            render_overlay.assert_called_once()

    def test_prepare_hyperframes_overlay_skips_when_disabled(self) -> None:
        with TemporaryDirectory() as tmp, patch("app.services.render.write_overlay_project") as write_project:
            result = _prepare_hyperframes_overlay(
                Path(tmp),
                [{"idx": 0, "text": "엔비디아", "start": 0.0, "end": 3.0, "dur": 3.0}],
                {},
                render_format="landscape",
            )

            self.assertIsNone(result.overlay_path)
            self.assertEqual(result.status, "skipped")
            write_project.assert_not_called()

    def test_prepare_hyperframes_overlay_reports_failed_render(self) -> None:
        with TemporaryDirectory() as tmp, patch("app.services.render.write_overlay_project"), patch(
            "app.services.render.render_hyperframes_overlay"
        ) as render_overlay:
            render_overlay.return_value = {"ok": False, "validation": {"error": "missing alpha"}}

            result = _prepare_hyperframes_overlay(
                Path(tmp),
                [{"idx": 0, "text": "엔비디아", "start": 0.0, "end": 3.0, "dur": 3.0}],
                {"hyperframes_overlay_enabled": True},
                render_format="landscape",
            )

            self.assertIsNone(result.overlay_path)
            self.assertEqual(result.status, "failed")
            self.assertIn("missing alpha", result.log)

    def test_validate_audio_duration_alignment_raises_on_large_drift(self) -> None:
        with patch("app.services.render._probe_duration", side_effect=[10.0, 11.5]):
            with self.assertRaisesRegex(RuntimeError, "Normalized audio drift is too large"):
                _validate_audio_duration_alignment(Path("raw.wav"), Path("norm.wav"))

    def test_plan_visual_segment_frames_absorbs_rounding_drift_in_last_segment(self) -> None:
        segments = [
            render.VisualSegment(path=Path("alpha.png"), duration_sec=1.02, motion="still_locked", effect="none"),
            render.VisualSegment(path=Path("beta.png"), duration_sec=1.02, motion="still_locked", effect="none"),
            render.VisualSegment(path=Path("gamma.png"), duration_sec=1.02, motion="still_locked", effect="none"),
        ]
        plan = _plan_visual_segment_frames(segments, 3.0)
        self.assertEqual(sum(item.frame_count for item in plan), 90)
        self.assertLess(plan[-1].drift_frames, 0)

    def test_duration_guard_tolerance_uses_half_second_for_short_outputs(self) -> None:
        self.assertEqual(_duration_guard_tolerance(30.0), 0.5)

    def test_validate_output_duration_removes_failed_output_file(self) -> None:
        with TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "output.mp4"
            output_path.write_bytes(b"video")
            with patch("app.services.render._probe_duration", return_value=47.0):
                with self.assertRaisesRegex(RuntimeError, "Final output duration drift is too large"):
                    _validate_output_duration(
                        output_path,
                        expected_audio_duration_sec=118.0,
                        expected_timeline_duration_sec=118.0,
                    )
            self.assertFalse(output_path.exists())

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

    def test_resolve_visual_segments_uses_render_plan_durations(self) -> None:
        db.init_db()
        project = db.create_project("render-segments")
        project_id = project["id"]
        media_dir = db.project_dir(project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        (media_dir / "scene0.png").write_bytes(b"img")
        (media_dir / "scene1.png").write_bytes(b"img")
        db.update_project(
            project_id,
            render_plan={
                "version": 2,
                "total_duration": 4.5,
                "segments": [
                    {
                        "region": "intro",
                        "start": 0.0,
                        "end": 1.5,
                        "sentence_idx": 0,
                        "media": [{"path": "scene0.png", "kind": "image"}],
                        "motion": "slow_zoom_out",
                        "effect": "fade",
                        "caption_style": "emphasis",
                    },
                    {
                        "region": "body",
                        "start": 1.5,
                        "end": 4.5,
                        "sentence_idx": 1,
                        "media": [{"path": "scene1.png", "kind": "image"}],
                        "motion": "none",
                        "effect": "none",
                        "caption_style": "plain",
                    },
                ],
            },
        )
        updated = db.get_project(project_id)
        self.assertIsNotNone(updated)
        assert updated is not None

        segments = _resolve_visual_segments(updated, media_dir, 4.5)
        style_map = _caption_style_map_from_render_plan(updated)

        self.assertEqual([round(item.duration_sec, 2) for item in segments], [1.5, 3.0])
        self.assertEqual(segments[0].motion, "slow_zoom_out")
        self.assertEqual(style_map, {0: "emphasis", 1: "plain"})
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

    def test_run_with_progress_stops_runaway_duration(self) -> None:
        class FakePopen:
            def __init__(self) -> None:
                self.stdout = io.BytesIO(
                    b"frame=100\nfps=24.0\nout_time=00:00:20.00\nspeed=1.00x\nprogress=continue\n"
                )
                self.stderr = io.BytesIO(b"")
                self.returncode = 255
                self.terminated = False
                self.killed = False

            def poll(self) -> int | None:
                if self.terminated or self.killed:
                    return self.returncode
                stdout_done = self.stdout.tell() >= len(self.stdout.getvalue())
                if stdout_done:
                    return None
                return None

            def wait(self, timeout: float | None = None) -> int:
                self.stdout.seek(len(self.stdout.getvalue()))
                self.stderr.seek(len(self.stderr.getvalue()))
                return self.returncode

            def terminate(self) -> None:
                self.terminated = True

            def kill(self) -> None:
                self.killed = True

        popen = FakePopen()
        with patch("app.services.render.subprocess.Popen", return_value=popen):
            with self.assertRaisesRegex(RuntimeError, "generated video duration exceeded"):
                _run_with_progress(
                    ["ffmpeg", "-i", "in.mp4", "out.mp4"],
                    expected_duration_sec=10.0,
                    on_progress=lambda event: None,
                )
        self.assertTrue(popen.terminated or popen.killed)
