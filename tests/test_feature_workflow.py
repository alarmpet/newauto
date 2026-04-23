import io
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.services.preflight import build_preflight_report
from app.services.render import _run, _tail_lines
from app.services.stock import search_stock_media
from app.services.subtitle import DEFAULT_SUBTITLE_STYLE, write_ass
from app.services.transcribe import build_word_timings
from app.types import SubtitleStyle, TimingEntry


class FeatureWorkflowTests(unittest.TestCase):
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

    def create_project(self, title: str = "feature-test") -> str:
        response = self.client.post("/api/projects", data={"title": title})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_preflight_reports_missing_steps(self) -> None:
        project_id = self.create_project()
        report = self.client.get(f"/api/projects/{project_id}/preflight")
        self.assertEqual(report.status_code, 200)
        payload = report.json()
        self.assertFalse(payload["ok"])
        check_keys = {check["key"] for check in payload["checks"]}
        self.assertIn("script", check_keys)
        self.assertIn("ffmpeg", check_keys)

    def test_feature_settings_and_bgm_upload_persist(self) -> None:
        project_id = self.create_project()
        settings = self.client.put(
            f"/api/projects/{project_id}/features",
            json={
                "kenburns_enabled": True,
                "bgm_volume_db": -12,
                "bgm_ducking_enabled": False,
                "render_formats": ["landscape", "shorts"],
            },
        )
        self.assertEqual(settings.status_code, 200)
        self.assertTrue(settings.json()["project"]["kenburns_enabled"])
        self.assertEqual(settings.json()["project"]["render_formats"], ["landscape", "shorts"])

        upload = self.client.post(
            f"/api/projects/{project_id}/bgm",
            files={"file": ("bgm.mp3", io.BytesIO(b"fake-bgm"), "audio/mpeg")},
        )
        self.assertEqual(upload.status_code, 200)
        self.assertEqual(upload.json()["project"]["bgm_file"], "bgm.mp3")

        bgm = self.client.get(f"/api/projects/{project_id}/bgm")
        self.assertEqual(bgm.status_code, 200)
        self.assertEqual(bgm.content, b"fake-bgm")

    def test_clone_project_copies_selected_assets(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            script="hello",
            sentences=["hello"],
            voice_preset="narrator",
            kenburns_enabled=True,
            render_formats=["landscape", "shorts"],
        )
        media_dir = db.project_dir(project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        (media_dir / "one.jpg").write_bytes(b"1")
        db.update_project(project_id, media_order=["one.jpg"])
        clone = self.client.post(
            f"/api/projects/{project_id}/clone?include_script=true&include_media=true",
        )
        self.assertEqual(clone.status_code, 200)
        cloned = clone.json()["project"]
        self.project_ids.append(str(cloned["id"]))
        self.assertEqual(cloned["script"], "hello")
        self.assertEqual(cloned["media_order"], ["one.jpg"])
        self.assertTrue((db.project_dir(cloned["id"]) / "media" / "one.jpg").exists())

    def test_system_health_route_returns_status(self) -> None:
        response = self.client.get("/api/system/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("ffmpeg_available", payload)
        self.assertIn("disk_free_gb", payload)

    def test_output_route_supports_shorts_format(self) -> None:
        project_id = self.create_project()
        shorts_path = db.project_dir(project_id) / "output_shorts.mp4"
        shorts_path.write_bytes(b"shorts")
        response = self.client.get(f"/api/projects/{project_id}/output?format=shorts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"shorts")

    def test_status_route_exposes_render_phase_and_log(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            render_state="running",
            render_progress=38,
            render_phase="normalize_audio",
            render_phase_pct=45,
            render_progress_detail="45% | 1.10x | frame 0 | elapsed 00:00:12",
            render_speed_x=1.1,
            render_eta_sec=4,
            render_last_log="ffmpeg started",
        )
        response = self.client.get(f"/api/projects/{project_id}/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["render_phase"], "normalize_audio")
        self.assertEqual(payload["render_phase_pct"], 45)
        self.assertEqual(payload["render_speed_x"], 1.1)
        self.assertEqual(payload["render_eta_sec"], 4)
        self.assertIn("45%", payload["render_progress_detail"])
        self.assertEqual(payload["render_last_log"], "ffmpeg started")

    def test_render_tail_lines_handles_none(self) -> None:
        self.assertEqual(_tail_lines(None), "")

    def test_render_tail_lines_handles_empty_text(self) -> None:
        self.assertEqual(_tail_lines("   "), "")

    def test_render_run_handles_success_with_none_stderr(self) -> None:
        completed = subprocess.CompletedProcess(args=["ffmpeg"], returncode=0, stdout="", stderr=None)
        with patch("app.services.render.subprocess.run", return_value=completed):
            self.assertEqual(_run(["ffmpeg"]), "")

    def test_render_run_handles_failure_with_none_stderr(self) -> None:
        completed = subprocess.CompletedProcess(args=["ffmpeg"], returncode=1, stdout="", stderr=None)
        with patch("app.services.render.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "no stderr output"):
                _run(["ffmpeg"])

    def test_word_timing_builder_and_karaoke_render(self) -> None:
        timings: list[TimingEntry] = [
            {"idx": 0, "text": "alpha beta", "start": 0.0, "end": 1.0, "dur": 1.0}
        ]
        word_timings = build_word_timings(timings)
        self.assertGreaterEqual(len(word_timings), 2)
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "karaoke.ass"
            style: SubtitleStyle = {**DEFAULT_SUBTITLE_STYLE, "effect": "karaoke"}
            write_ass(timings, output_path, style, word_timings)
            content = output_path.read_text(encoding="utf-8")
        self.assertIn(r"{\k", content)

    def test_stock_search_uses_available_providers(self) -> None:
        with patch("app.services.stock._search_pexels", return_value=[{
            "provider": "pexels",
            "title": "asset",
            "media_url": "https://example.com/full.jpg",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "attribution_url": "https://example.com/page",
        }]), patch("app.services.stock._search_pixabay", return_value=[]):
            response = search_stock_media("city skyline")
        self.assertEqual(response["query"], "city skyline")
        self.assertEqual(len(response["results"]), 1)

    def test_youtube_stats_route_uses_service(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, youtube_id="video123")
        with patch("app.services.yt_upload.fetch_video_stats", return_value={
            "video_id": "video123",
            "view_count": 12,
            "like_count": 3,
            "comment_count": 1,
        }):
            response = self.client.get(f"/api/projects/{project_id}/stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["view_count"], 12)

    def test_preflight_service_passes_ready_project(self) -> None:
        project_id = self.create_project()
        project_dir = db.project_dir(project_id)
        (project_dir / "media").mkdir(parents=True, exist_ok=True)
        (project_dir / "tts").mkdir(parents=True, exist_ok=True)
        (project_dir / "media" / "one.jpg").write_bytes(b"1")
        (project_dir / "tts" / "timings.json").write_text("[]", encoding="utf-8")
        db.update_project(
            project_id,
            sentences=["hello"],
            media_order=["one.jpg"],
            tts_state="done",
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        with patch("app.services.preflight.find_invalid_media_files", return_value=[]):
            report = build_preflight_report(project)
        check_map = {check["key"]: check["ok"] for check in report["checks"]}
        self.assertTrue(check_map["script"])
        self.assertTrue(check_map["tts_state"])
        self.assertTrue(check_map["media_metadata"])
