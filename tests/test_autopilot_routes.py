import os
import unittest
from typing import ClassVar

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app


class AutopilotRouteTests(unittest.TestCase):
    client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        db.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def setUp(self) -> None:
        response = self.client.post("/api/projects", data={"title": "autopilot-test"})
        self.assertEqual(response.status_code, 200)
        self.project_id = str(response.json()["id"])

    def tearDown(self) -> None:
        self.client.delete(f"/api/projects/{self.project_id}")

    def test_start_autopilot_queues_project_and_writes_debug_files(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project_id}/autopilot/start",
            json={
                "input_mode": "script",
                "script": "첫 번째 문장입니다. 두 번째 문장입니다.",
                "image_count": "auto",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["project"]["autopilot_state"], "queued")
        self.assertEqual(payload["project"]["autopilot_phase"], "prepare_input")
        self.assertTrue(payload["project"]["autopilot_job_id"].startswith("auto_"))

        autopilot_dir = db.project_dir(self.project_id) / "autopilot"
        self.assertTrue((autopilot_dir / "events.jsonl").exists())
        self.assertTrue((autopilot_dir / "debug_snapshot.json").exists())

    def test_start_autopilot_records_pipeline_stage_boundaries(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project_id}/autopilot/start",
            json={
                "input_mode": "script",
                "script": "First sentence. Second sentence.",
                "image_count": "auto",
            },
        )
        self.assertEqual(response.status_code, 200)
        manifest = response.json()["project"]["pipeline_manifest"]
        expected = [
            "prepare_input",
            "script_compile",
            "visual_plan",
            "tts",
            "image",
            "render_plan",
            "preflight",
            "render",
        ]
        for stage in expected:
            self.assertIn(stage, manifest["stage_status"])
            status = manifest["stage_status"][stage]
            self.assertIn("input_hash", status)
            self.assertIn("output_hash", status)
            self.assertIn("state", status)
            self.assertIn("error_code", status)
            self.assertIn("recovery_hint", status)
        self.assertEqual(manifest["stage_status"]["prepare_input"]["state"], "queued")
        self.assertNotEqual(manifest["stage_status"]["prepare_input"]["input_hash"], "")
        self.assertEqual(manifest["stage_status"]["script_compile"]["state"], "idle")

    def test_start_autopilot_validates_required_input(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project_id}/autopilot/start",
            json={"input_mode": "url", "url": ""},
        )
        self.assertEqual(response.status_code, 400)

    def test_autopilot_pause_resume_cancel_flow(self) -> None:
        start = self.client.post(
            f"/api/projects/{self.project_id}/autopilot/start",
            json={"input_mode": "script", "script": "대본"},
        )
        self.assertEqual(start.status_code, 200)

        pause = self.client.post(f"/api/projects/{self.project_id}/autopilot/pause", data={})
        self.assertEqual(pause.status_code, 200)
        self.assertEqual(pause.json()["project"]["autopilot_state"], "paused")

        resume = self.client.post(f"/api/projects/{self.project_id}/autopilot/resume", data={})
        self.assertEqual(resume.status_code, 200)
        self.assertEqual(resume.json()["project"]["autopilot_state"], "queued")

        cancel = self.client.post(f"/api/projects/{self.project_id}/autopilot/cancel", data={})
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json()["project"]["autopilot_state"], "canceled")

    def test_autopilot_status_events_and_debug_routes_return_payloads(self) -> None:
        self.client.post(
            f"/api/projects/{self.project_id}/autopilot/start",
            json={"input_mode": "keyword", "keyword": "반도체 전망"},
        )

        status = self.client.get(f"/api/projects/{self.project_id}/autopilot/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["state"], "queued")
        self.assertEqual(status.json()["options"]["input_mode"], "keyword")

        events = self.client.get(f"/api/projects/{self.project_id}/autopilot/events?limit=10")
        self.assertEqual(events.status_code, 200)
        self.assertGreaterEqual(len(events.json()), 1)
        self.assertEqual(events.json()[-1]["event"], "queued")

        debug = self.client.get(f"/api/projects/{self.project_id}/autopilot/debug")
        self.assertEqual(debug.status_code, 200)
        self.assertEqual(debug.json()["state"], "queued")
        self.assertGreaterEqual(len(debug.json()["recent_events"]), 1)

    def test_project_status_route_exposes_autopilot_fields(self) -> None:
        db.update_project(
            self.project_id,
            autopilot_state="paused",
            autopilot_progress=42,
            autopilot_phase="image_wait",
            autopilot_last_log="Waiting for image worker.",
            autopilot_error="",
            autopilot_job_id="auto_test123",
            autopilot_started_at="2026-04-26T00:00:00+00:00",
            autopilot_heartbeat_at="2026-04-26T00:00:05+00:00",
            autopilot_last_error_code="",
            autopilot_debug_summary="Paused for test.",
            autopilot_wait_started_at="2026-04-26T00:00:03+00:00",
            autopilot_retry_count=1,
        )
        response = self.client.get(f"/api/projects/{self.project_id}/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["autopilot_state"], "paused")
        self.assertEqual(payload["autopilot_progress"], 42)
        self.assertEqual(payload["autopilot_phase"], "image_wait")

    def test_recover_interrupted_tasks_marks_running_autopilot_error(self) -> None:
        db.update_project(
            self.project_id,
            autopilot_state="running",
            autopilot_phase="tts_wait",
            autopilot_job_id="auto_test123",
        )
        summary = db.recover_interrupted_tasks()
        self.assertGreaterEqual(summary["autopilot"], 1)
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["autopilot_state"], "error")
        self.assertEqual(project["autopilot_last_error_code"], "SYSTEM_RESTART_INTERRUPTED")
