import os
import unittest
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.workers.worker_lock import _pid_exists

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app
from app.services import gpu_guard
from app.services.usage_registry import get_provider_usage, reserve_provider_usage


class SystemOperatorTests(unittest.TestCase):
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

    def create_project(self, title: str = "operator-test") -> str:
        response = self.client.post("/api/projects", data={"title": title})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_pid_exists_treats_windows_system_error_as_dead_pid(self) -> None:
        with patch("app.workers.worker_lock.os.kill", side_effect=SystemError("invalid pid")):
            self.assertFalse(_pid_exists(999999))

    def test_tools_route_returns_registry(self) -> None:
        response = self.client.get("/api/system/tools")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        keys = {item["key"] for item in payload}
        self.assertIn("ffmpeg", keys)
        self.assertIn("ollama", keys)
        self.assertIn("comfyui", keys)

    def test_tools_route_reflects_lmstudio_provider_when_configured(self) -> None:
        with patch("app.services.tool_registry.LLM_PROVIDER", "lmstudio"), patch(
            "app.services.tool_registry.LMSTUDIO_BASE_URL", "http://127.0.0.1:1234"
        ):
            response = self.client.get("/api/system/tools")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ollama_item = next(item for item in payload if item["key"] == "ollama")
        self.assertEqual(ollama_item["detail"], "LM Studio endpoint: http://127.0.0.1:1234")
        self.assertFalse(ollama_item["version"])

    def test_operator_route_usage_shows_selected_llm_provider(self) -> None:
        with patch("app.services.usage_registry.LLM_PROVIDER", "lmstudio"):
            response = self.client.get("/api/system/operator")

        self.assertEqual(response.status_code, 200)
        usage_providers = {item["provider"] for item in response.json()["usage"]}
        self.assertIn("lmstudio", usage_providers)

    def test_operator_route_returns_queue_gpu_and_usage(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            source_draft_state="queued",
            render_state="running",
            tts_state="running",
            autopilot_state="running",
            autopilot_phase="render_wait",
            autopilot_progress=96,
            autopilot_job_id="auto_active_001",
            autopilot_started_at="2026-04-26T07:30:00+00:00",
        )
        paused_project_id = self.create_project("operator-paused")
        db.update_project(
            paused_project_id,
            autopilot_state="paused",
            autopilot_phase="source_apply",
            autopilot_progress=35,
            autopilot_job_id="auto_paused_001",
            autopilot_last_error_code="COPY_USER_SCRIPT_OVERWRITE",
            autopilot_started_at="2026-04-26T07:20:00+00:00",
        )
        report_path = db.project_dir(project_id) / "render_report.json"
        report_path.write_text(
            '{"project_id":"%s","title":"operator-test","status":"done","created_at":"2026-04-26T07:40:00+00:00","autopilot_job_id":"auto_active_001","autopilot_input_mode":"script","autopilot_state":"done","autopilot_phase":"done","render_started_at":"","render_finished_at":"","audio_duration_sec":1.0,"subtitle_cue_count":1,"render_plan_segment_count":1,"missing_render_plan_media_count":0,"fallback_used":false,"outputs":[],"segments":[],"ffmpeg_log_tail":"","error":""}'
            % project_id,
            encoding="utf-8",
        )
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "gpu_guard.json"
            self.assertTrue(gpu_guard.acquire("ollama", "source-worker", path=lock_path))
            with patch("app.services.system_health.get_gpu_status", return_value=gpu_guard.get_status(lock_path)):
                response = self.client.get("/api/system/operator")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("source_draft_queued", payload["queue"])
        self.assertIn("autopilot_paused", payload["queue"])
        self.assertIn("render_running", payload["queue"])
        self.assertIn("tts_running", payload["queue"])
        self.assertTrue(payload["gpu"]["locked"])
        self.assertGreaterEqual(payload["render_metrics"]["total"], 1)
        self.assertGreaterEqual(payload["render_metrics"]["success"], 1)
        self.assertGreaterEqual(payload["autopilot_metrics"]["total"], 2)
        self.assertGreaterEqual(payload["autopilot_metrics"]["paused"], 1)
        self.assertGreaterEqual(len(payload["recent_autopilot_runs"]), 2)
        providers = {item["provider"] for item in payload["usage"]}
        self.assertIn("brave_search", providers)

    def test_usage_registry_migrates_legacy_brave_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            usage_path = Path(temp_dir) / "providers.json"
            legacy_path = Path(temp_dir) / "brave_usage.json"
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            legacy_path.write_text(f'{{"month":"{current_month}","count":999}}', encoding="utf-8")
            record = get_provider_usage("brave_search", month_limit=1000, path=usage_path, legacy_path=legacy_path)
            self.assertEqual(record["month_count"], 999)
            updated = reserve_provider_usage(
                "brave_search",
                month_limit=1000,
                path=usage_path,
                legacy_path=legacy_path,
            )
            self.assertEqual(updated["month_count"], 1000)
            self.assertTrue(usage_path.exists())
            self.assertIn('"count": 1000', legacy_path.read_text(encoding="utf-8"))

    def test_gpu_guard_rejects_other_owner_until_release(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "gpu_guard.json"
            self.assertTrue(gpu_guard.acquire("ollama", "worker-a", path=lock_path))
            self.assertFalse(gpu_guard.acquire("comfyui", "worker-b", path=lock_path))
            self.assertFalse(gpu_guard.release("worker-b", path=lock_path))
            self.assertTrue(gpu_guard.release("worker-a", path=lock_path))
            self.assertFalse(gpu_guard.get_status(lock_path)["locked"])

    def test_gpu_guard_stale_owner_is_auto_cleared_when_acquired(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "gpu_guard.json"
            stale_payload = {
                "locked": True,
                "owner": "tts:stale-project",
                "resource": "tts",
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds"),
                "owner_pid": 999999,
                "owner_project_id": "stale-project",
                "owner_job_type": "tts",
            }
            lock_path.write_text(json.dumps(stale_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            stale_status = gpu_guard.get_status(lock_path)
            self.assertTrue(stale_status["locked"])
            self.assertTrue(stale_status["stale"])
            self.assertTrue(gpu_guard.acquire("tts", "tts-worker", path=lock_path))
            status = gpu_guard.get_status(lock_path)
            self.assertTrue(status["locked"])
            self.assertEqual(status["owner"], "tts-worker")
            self.assertEqual(status["owner_job_type"], "tts-worker")
