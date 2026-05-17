import io
import json
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

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
        self.assertIn("subtitle_cues", check_keys)
        self.assertIn("plan_sync", check_keys)

    def test_feature_settings_and_bgm_upload_persist(self) -> None:
        project_id = self.create_project()
        settings = self.client.put(
            f"/api/projects/{project_id}/features",
            json={
                "kenburns_enabled": True,
                "bgm_volume_db": -12,
                "bgm_ducking_enabled": False,
                "render_formats": ["landscape", "shorts"],
                "visual_source_mode": "comfyui_auto",
                "style_preset": "simple_diagram",
            },
        )
        self.assertEqual(settings.status_code, 200)
        self.assertTrue(settings.json()["project"]["kenburns_enabled"])
        self.assertEqual(settings.json()["project"]["render_formats"], ["landscape", "shorts"])
        self.assertEqual(settings.json()["project"]["visual_source_mode"], "comfyui_auto")
        self.assertEqual(settings.json()["project"]["body_image_options"]["style_preset"], "simple_diagram")

        upload = self.client.post(
            f"/api/projects/{project_id}/bgm",
            files={"file": ("bgm.mp3", io.BytesIO(b"fake-bgm"), "audio/mpeg")},
        )
        self.assertEqual(upload.status_code, 200)
        self.assertEqual(upload.json()["project"]["bgm_file"], "bgm.mp3")

        bgm = self.client.get(f"/api/projects/{project_id}/bgm")
        self.assertEqual(bgm.status_code, 200)
        self.assertEqual(bgm.content, b"fake-bgm")

    def test_feature_settings_reject_unknown_style_preset(self) -> None:
        project_id = self.create_project()
        settings = self.client.put(
            f"/api/projects/{project_id}/features",
            json={"style_preset": "unknown_style"},
        )
        self.assertEqual(settings.status_code, 400)
        self.assertIn("unsupported style_preset", settings.text)

    def test_feature_settings_accept_editorial_symbolic_style_preset(self) -> None:
        project_id = self.create_project()
        settings = self.client.put(
            f"/api/projects/{project_id}/features",
            json={"style_preset": "editorial_symbolic"},
        )
        self.assertEqual(settings.status_code, 200)
        self.assertEqual(settings.json()["project"]["body_image_options"]["style_preset"], "editorial_symbolic")

    def test_feature_settings_accept_stickman_business_style_preset(self) -> None:
        project_id = self.create_project()
        settings = self.client.put(
            f"/api/projects/{project_id}/features",
            json={"style_preset": "stickman_business"},
        )
        self.assertEqual(settings.status_code, 200)
        self.assertEqual(settings.json()["project"]["body_image_options"]["style_preset"], "stickman_business")

    def test_feature_settings_persist_hyperframes_overlay_options(self) -> None:
        project_id = self.create_project()

        settings = self.client.put(
            f"/api/projects/{project_id}/features",
            json={
                "hyperframes_overlay_enabled": True,
                "hyperframes_overlay_required": True,
            },
        )

        self.assertEqual(settings.status_code, 200)
        options = settings.json()["project"]["body_image_options"]
        self.assertTrue(options["hyperframes_overlay_enabled"])
        self.assertTrue(options["hyperframes_overlay_required"])

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
        self.assertIn("omnivoice_python_path", payload)
        self.assertIn("omnivoice_import_ok", payload)
        self.assertIn("disk_free_gb", payload)

    def test_output_route_supports_shorts_format(self) -> None:
        project_id = self.create_project()
        shorts_path = db.project_dir(project_id) / "output_shorts.mp4"
        shorts_path.write_bytes(b"shorts")
        response = self.client.get(f"/api/projects/{project_id}/output?format=shorts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"shorts")

    def test_output_route_auto_returns_existing_shorts_output(self) -> None:
        project_id = self.create_project()
        shorts_path = db.project_dir(project_id) / "output_shorts.mp4"
        shorts_path.write_bytes(b"shorts")
        response = self.client.get(f"/api/projects/{project_id}/output")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"shorts")

    def test_output_route_explicit_landscape_still_requires_landscape_output(self) -> None:
        project_id = self.create_project()
        shorts_path = db.project_dir(project_id) / "output_shorts.mp4"
        shorts_path.write_bytes(b"shorts")
        response = self.client.get(f"/api/projects/{project_id}/output?format=landscape")
        self.assertEqual(response.status_code, 404)

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

    def test_start_render_route_queues_render_job(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            sentences=["hello"],
            tts_state="done",
            media_order=["one.jpg"],
            media_upload_state="done",
        )
        response = self.client.post(f"/api/projects/{project_id}/render", data={})
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["render_state"], "queued")
        self.assertEqual(project["render_phase"], "queued")
        self.assertEqual(project["render_progress"], 0)

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

    def test_system_tools_reflects_lmstudio_provider(self) -> None:
        with patch("app.services.tool_registry.LLM_PROVIDER", "lmstudio"), patch(
            "app.services.tool_registry.LMSTUDIO_BASE_URL", "http://127.0.0.1:1234"
        ):
            response = self.client.get("/api/system/tools")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ollama_tool = next(item for item in payload if item["key"] == "ollama")
        self.assertEqual(ollama_tool["detail"], "LM Studio endpoint: http://127.0.0.1:1234")

    def test_list_tool_status_with_lmstudio_provider(self) -> None:
        with patch("app.services.tool_registry.LLM_PROVIDER", "lmstudio"), patch(
            "app.services.tool_registry.LMSTUDIO_BASE_URL", "http://127.0.0.1:1234"
        ), patch("app.services.tool_registry.OLLAMA_BASE_URL", "http://127.0.0.1:11434"):
            from app.services.tool_registry import list_tool_status

            tools = list_tool_status()
            ollama_tool = next(item for item in tools if item["key"] == "ollama")
            self.assertEqual(ollama_tool["detail"], "LM Studio endpoint: http://127.0.0.1:1234")
            self.assertEqual(ollama_tool["configured"], True)

    def test_usage_registry_list_contains_lmstudio_provider(self) -> None:
        with patch("app.services.usage_registry.LLM_PROVIDER", "lmstudio"):
            from app.services.usage_registry import list_usage_records

            with TemporaryDirectory() as temp_dir:
                records = list_usage_records(path=Path(temp_dir) / "providers.json")
            providers = [item["provider"] for item in records]
            self.assertIn("lmstudio", providers)
            self.assertNotIn("ollama", providers)

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
        self.assertTrue(check_map["tts_consistency"])
        self.assertTrue(check_map["media_metadata"])

    def test_preflight_reports_tts_consistency_failure(self) -> None:
        project_id = self.create_project()
        project_dir = db.project_dir(project_id)
        (project_dir / "media").mkdir(parents=True, exist_ok=True)
        (project_dir / "tts").mkdir(parents=True, exist_ok=True)
        (project_dir / "media" / "one.jpg").write_bytes(b"1")
        (project_dir / "tts" / "timings.json").write_text(
            '[{"idx":0,"text":"hello","start":0,"end":1,"dur":1}]',
            encoding="utf-8",
        )
        (project_dir / "tts" / "tts_consistency_report.json").write_text(
            json.dumps(
                {
                    "metadata_consistent": True,
                    "audio_consistency_checked": True,
                    "audio_consistency_passed": False,
                    "max_estimated_pitch_relative_drift": 0.53,
                    "max_spectral_centroid_relative_drift": 0.32,
                    "recommended_tts_mode": "full_passage_or_reference_voice",
                }
            ),
            encoding="utf-8",
        )
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
        check_map = {check["key"]: check for check in report["checks"]}
        self.assertFalse(check_map["tts_consistency"]["ok"])
        self.assertIn("pitch drift 0.53", check_map["tts_consistency"]["message"])

    def test_preflight_rejects_vertical_media_with_landscape_only_output(self) -> None:
        project_id = self.create_project()
        project_dir = db.project_dir(project_id)
        (project_dir / "media").mkdir(parents=True, exist_ok=True)
        (project_dir / "tts").mkdir(parents=True, exist_ok=True)
        (project_dir / "media" / "vertical.jpg").write_bytes(b"1")
        (project_dir / "tts" / "timings.json").write_text(
            '[{"idx":0,"text":"hello","start":0,"end":1,"dur":1}]',
            encoding="utf-8",
        )
        (project_dir / "tts" / "tts_run_manifest.json").write_text(
            json.dumps({"sentences": [{"idx": 0, "text": "hello"}]}),
            encoding="utf-8",
        )
        db.update_project(
            project_id,
            sentences=["hello"],
            media_order=["vertical.jpg"],
            tts_state="done",
            render_formats=["landscape"],
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        with patch("app.services.preflight.find_invalid_media_files", return_value=[]), patch(
            "app.services.preflight.probe_media_dimensions",
            return_value=(768, 1376),
        ):
            report = build_preflight_report(project)
        check_map = {check["key"]: check for check in report["checks"]}
        self.assertFalse(check_map["media_aspect"]["ok"])
        self.assertIn("vertical", check_map["media_aspect"]["message"])

    def test_preflight_rejects_sentence_mode_subtitles_for_shorts(self) -> None:
        project_id = self.create_project()
        project_dir = db.project_dir(project_id)
        (project_dir / "media").mkdir(parents=True, exist_ok=True)
        (project_dir / "tts").mkdir(parents=True, exist_ok=True)
        (project_dir / "media" / "vertical.jpg").write_bytes(b"1")
        (project_dir / "tts" / "timings.json").write_text(
            json.dumps(
                [
                    {
                        "idx": 0,
                        "text": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda",
                        "start": 0,
                        "end": 6,
                        "dur": 6,
                    }
                ]
            ),
            encoding="utf-8",
        )
        (project_dir / "tts" / "tts_run_manifest.json").write_text(
            json.dumps({"sentences": [{"idx": 0, "text": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"}]}),
            encoding="utf-8",
        )
        db.update_project(
            project_id,
            sentences=["alpha beta gamma delta epsilon zeta eta theta iota kappa lambda"],
            media_order=["vertical.jpg"],
            tts_state="done",
            render_formats=["shorts"],
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        with patch("app.services.preflight.find_invalid_media_files", return_value=[]), patch(
            "app.services.preflight.probe_media_dimensions",
            return_value=(768, 1376),
        ):
            report = build_preflight_report(project)
        check_map = {check["key"]: check for check in report["checks"]}
        self.assertFalse(check_map["subtitle_layout"]["ok"])
        self.assertIn("readable cue splitting", check_map["subtitle_layout"]["message"])

    def test_preflight_rejects_mojibake_tts_manifest_text(self) -> None:
        project_id = self.create_project()
        project_dir = db.project_dir(project_id)
        (project_dir / "media").mkdir(parents=True, exist_ok=True)
        (project_dir / "tts").mkdir(parents=True, exist_ok=True)
        (project_dir / "media" / "one.jpg").write_bytes(b"1")
        (project_dir / "tts" / "timings.json").write_text(
            '[{"idx":0,"text":"최근 소식입니다.","start":0,"end":1,"dur":1}]',
            encoding="utf-8",
        )
        (project_dir / "tts" / "tts_run_manifest.json").write_text(
            json.dumps(
                {
                    "sentences": [
                        {
                            "idx": 0,
                            "text": "理쒓렐 ?멸났吏?? 遺꾩빞??? 좊몢 二쇱옄濡??",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        db.update_project(
            project_id,
            sentences=["최근 소식입니다."],
            media_order=["one.jpg"],
            tts_state="done",
        )
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        with patch("app.services.preflight.find_invalid_media_files", return_value=[]):
            report = build_preflight_report(project)
        check_map = {check["key"]: check for check in report["checks"]}
        self.assertFalse(check_map["tts_manifest_text"]["ok"])
        self.assertIn("mojibake", check_map["tts_manifest_text"]["message"])

    def test_preflight_reports_stale_plan_or_missing_render_plan_media(self) -> None:
        project_id = self.create_project()
        project_dir = db.project_dir(project_id)
        (project_dir / "media").mkdir(parents=True, exist_ok=True)
        (project_dir / "tts").mkdir(parents=True, exist_ok=True)
        (project_dir / "media" / "one.jpg").write_bytes(b"1")
        (project_dir / "tts" / "timings.json").write_text('[{"idx":0,"text":"hello","start":0,"end":1,"dur":1}]', encoding="utf-8")
        db.update_project(
            project_id,
            sentences=["hello", "world"],
            media_order=["one.jpg"],
            tts_state="done",
            scene_plan={
                "version": 1,
                "format": "landscape",
                "total_duration": 1.0,
                "scenes": [
                    {
                        "idx": 1,
                        "sentence_idx": 0,
                        "text": "hello",
                        "region": "intro",
                        "duration_sec": 1.0,
                        "visual_intent": "hello",
                        "prompt": "p1",
                        "style": "doc",
                        "media_path": "missing.png",
                    }
                ],
            },
            render_plan={
                "version": 2,
                "total_duration": 1.0,
                "segments": [
                    {
                        "region": "intro",
                        "start": 0.0,
                        "end": 1.0,
                        "sentence_idx": 0,
                        "media": [{"path": "missing.png", "kind": "image"}],
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
        with patch("app.services.preflight.find_invalid_media_files", return_value=[]):
            report = build_preflight_report(project)
        check_map = {check["key"]: check for check in report["checks"]}
        self.assertFalse(check_map["plan_sync"]["ok"])
        self.assertFalse(check_map["render_plan_media"]["ok"])

    def test_recover_interrupted_tasks_clears_running_render_state(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            render_state="running",
            render_progress=70,
            render_phase="build_visual_landscape",
            render_phase_pct=25,
            render_progress_detail="25% | 1.10x | frame 1200 | elapsed 00:01:00",
            render_speed_x=1.1,
            render_eta_sec=120,
            render_last_log="",
            tts_state="running",
            upload_state="running",
            media_upload_state="running",
            media_upload_error="",
        )

        summary = db.recover_interrupted_tasks()
        self.assertIn("render", summary)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["render_state"], "error")
        self.assertEqual(project["render_phase"], "")
        self.assertEqual(project["render_phase_pct"], 0)
        self.assertEqual(project["render_progress_detail"], "")
        self.assertEqual(project["render_speed_x"], 0.0)
        self.assertEqual(project["render_eta_sec"], 0)
        self.assertIn("interrupted", project["render_last_log"])
        self.assertEqual(project["tts_state"], "error")
        self.assertEqual(project["upload_state"], "error")
        self.assertEqual(project["media_upload_state"], "error")

    def test_source_url_analyze_persists_source_draft(self) -> None:
        project_id = self.create_project()
        with patch("app.routers.projects.analyze_source_url") as mocked_analyze:
            mocked_analyze.return_value = type("ExtractedSourceStub", (), {
                "source": {
                    "id": "src123",
                    "url": "https://example.com/article",
                    "final_url": "https://example.com/article",
                    "title": "Example Title",
                    "domain": "example.com",
                    "author": "",
                    "published_at": "",
                    "language": "ko",
                    "excerpt": "요약 본문",
                    "fetched_at": "2026-04-24T18:00:00+00:00",
                    "word_count": 120,
                },
                "fact_notes": [
                    {"source_id": "src123", "note": "핵심 사실 1"},
                    {"source_id": "src123", "note": "핵심 사실 2"},
                ],
                "warnings": ["원문 직접 복사를 피하세요."],
                "sanitized_text": "요약 본문",
            })()
            response = self.client.post(
                f"/api/projects/{project_id}/source/url/analyze",
                data={"url": "https://example.com/article"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_draft_state"], "done")
        self.assertEqual(payload["source_draft_input_mode"], "url")
        self.assertEqual(payload["source_draft_query"], "https://example.com/article")
        self.assertEqual(payload["source_draft_sources"][0]["domain"], "example.com")
        self.assertEqual(len(payload["source_draft_fact_notes"]), 2)
        self.assertEqual(payload["source_draft_warnings"], ["원문 직접 복사를 피하세요."])

    def test_source_draft_clear_route_resets_fields(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            source_draft_state="done",
            source_draft_progress=100,
            source_draft_input_mode="url",
            source_draft_query="https://example.com/article",
            source_draft_sources=[{
                "id": "src123",
                "url": "https://example.com/article",
                "final_url": "https://example.com/article",
                "title": "Example Title",
                "domain": "example.com",
                "author": "",
                "published_at": "",
                "language": "ko",
                "excerpt": "요약 본문",
                "fetched_at": "2026-04-24T18:00:00+00:00",
                "word_count": 120,
            }],
            source_draft_fact_notes=[{"source_id": "src123", "note": "핵심 사실"}],
            source_draft_warnings=["주의"],
        )
        response = self.client.delete(f"/api/projects/{project_id}/source/draft")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_draft_state"], "idle")
        self.assertEqual(payload["source_draft_query"], "")
        self.assertEqual(payload["source_draft_sources"], [])
        self.assertEqual(payload["source_draft_fact_notes"], [])
        self.assertEqual(payload["source_draft_warnings"], [])

    def test_source_script_generate_persists_queue_metadata(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            source_draft_state="done",
            source_draft_input_mode="url",
            source_draft_query="https://example.com/article",
            source_draft_sources=[{
                "id": "src123",
                "url": "https://example.com/article",
                "final_url": "https://example.com/article",
                "title": "Example Title",
                "domain": "example.com",
                "author": "",
                "published_at": "",
                "language": "ko",
                "excerpt": "요약 본문",
                "fetched_at": "2026-04-24T18:00:00+00:00",
                "word_count": 120,
            }],
            source_draft_fact_notes=[{"source_id": "src123", "note": "핵심 사실"}],
        )
        response = self.client.post(
            f"/api/projects/{project_id}/source/script/generate",
            data={"tone": "설명형", "target_minutes": "3", "language": "ko", "mode": "hook", "note": "도입을 강하게"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        from app.routers import projects

        self.assertEqual(payload["source_draft_model"], projects.SCRIPT_LLM_MODEL)
        self.assertEqual(payload["source_draft_state"], "queued")
        self.assertEqual(payload["source_draft_phase"], "queued")
        self.assertEqual(payload["source_draft_regenerate_mode"], "hook")
        self.assertEqual(payload["source_draft_regenerate_note"], "도입을 강하게")

    def test_source_script_generate_blocks_when_running(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            source_draft_state="running",
        )
        response = self.client.post(
            f"/api/projects/{project_id}/source/script/generate",
            data={"tone": "설명형", "target_minutes": "3", "language": "ko"},
        )
        self.assertEqual(response.status_code, 409)

    def test_source_script_generate_returns_queued(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            source_draft_state="done",
            source_draft_sources=[{
                "id": "src123",
                "url": "https://example.com/article",
                "final_url": "https://example.com/article",
                "title": "Example Title",
                "domain": "example.com",
                "author": "",
                "published_at": "",
                "language": "ko",
                "excerpt": "요약 본문",
                "fetched_at": "2026-04-24T18:00:00+00:00",
                "word_count": 120,
            }],
            source_draft_fact_notes=[{"source_id": "src123", "note": "핵심 사실"}],
        )
        response = self.client.post(
            f"/api/projects/{project_id}/source/script/generate",
            data={"tone": "설명형", "target_minutes": "3", "language": "ko", "mode": "story"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_draft_state"], "queued")
        self.assertEqual(payload["source_draft_phase"], "queued")
        self.assertEqual(payload["source_draft_regenerate_mode"], "story")

    def test_source_script_apply_writes_project_script(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            source_draft_script="적용할 초안 문장입니다. 두 번째 문장입니다.",
        )
        response = self.client.post(f"/api/projects/{project_id}/source/script/apply", data={})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["content_mode"], "standard")
        self.assertEqual(payload["user_script"], "적용할 초안 문장입니다. 두 번째 문장입니다.")
        self.assertGreaterEqual(len(payload["sentences"]), 1)

    def test_restore_previous_swaps_script(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            source_draft_script="현재 초안",
            source_draft_previous_script="이전 초안",
        )
        response = self.client.post(f"/api/projects/{project_id}/source/script/restore-previous", data={})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_draft_script"], "이전 초안")
        self.assertEqual(payload["source_draft_previous_script"], "현재 초안")

    def test_source_keyword_collect_persists_sources(self) -> None:
        project_id = self.create_project()
        with patch("app.routers.projects.collect_sources_from_keyword") as mocked_collect, patch(
            "app.routers.projects.analyze_source_url"
        ) as mocked_analyze:
            mocked_collect.return_value = ([
                type("SearchResultStub", (), {
                    "title": "검색 결과 1",
                    "url": "https://example.com/one",
                    "description": "desc",
                })(),
                type("SearchResultStub", (), {
                    "title": "검색 결과 2",
                    "url": "https://example.com/two",
                    "description": "desc",
                })(),
            ], {"used": 12, "remaining": 988, "limit": 1000, "month": "2026-04"})
            mocked_analyze.side_effect = [
                type("ExtractedSourceStub", (), {
                    "source": {
                        "id": "src1",
                        "url": "https://example.com/one",
                        "final_url": "https://example.com/one",
                        "title": "기사 1",
                        "domain": "example.com",
                        "author": "",
                        "published_at": "",
                        "language": "ko",
                        "excerpt": "요약 1",
                        "fetched_at": "2026-04-24T18:00:00+00:00",
                        "word_count": 100,
                    },
                    "fact_notes": [{"source_id": "src1", "note": "사실 1"}],
                })(),
                type("ExtractedSourceStub", (), {
                    "source": {
                        "id": "src2",
                        "url": "https://example.com/two",
                        "final_url": "https://example.com/two",
                        "title": "기사 2",
                        "domain": "example.com",
                        "author": "",
                        "published_at": "",
                        "language": "ko",
                        "excerpt": "요약 2",
                        "fetched_at": "2026-04-24T18:00:00+00:00",
                        "word_count": 100,
                    },
                    "fact_notes": [{"source_id": "src2", "note": "사실 2"}],
                })(),
            ]
            response = self.client.post(
                f"/api/projects/{project_id}/source/keyword/collect",
                data={"keyword": "반도체 수출 전망"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_draft_input_mode"], "keyword")
        self.assertEqual(payload["source_draft_query"], "반도체 수출 전망")
        self.assertEqual(len(payload["source_draft_sources"]), 2)
        self.assertIn("Brave 무료 검색 사용량", payload["source_draft_warnings"][0])

    def test_brave_status_route_returns_usage(self) -> None:
        with patch("app.routers.projects.get_brave_usage_status", return_value={
            "month": "2026-04",
            "used": 10,
            "remaining": 990,
            "limit": 1000,
        }):
            response = self.client.get("/api/projects/_/source/brave/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["used"], 10)
        self.assertEqual(payload["remaining"], 990)

    def test_status_route_exposes_source_draft_fields(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            source_draft_state="running",
            source_draft_progress=44,
            source_draft_phase="generate",
            source_draft_last_log="Generating source draft...",
            source_draft_started_at="2026-04-26T00:00:00+00:00",
            source_draft_heartbeat_at="2026-04-26T00:00:05+00:00",
            source_draft_error="",
        )
        response = self.client.get(f"/api/projects/{project_id}/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_draft_state"], "running")
        self.assertEqual(payload["source_draft_progress"], 44)
        self.assertEqual(payload["source_draft_phase"], "generate")
        self.assertIn("Generating", payload["source_draft_last_log"])
