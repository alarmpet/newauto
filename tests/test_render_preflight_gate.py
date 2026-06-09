import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.main import app


class RenderPreflightGateTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.client = TestClient(app)
        self.project = db.create_project("render gate")
        self.pid = self.project["id"]

    def tearDown(self) -> None:
        db.delete_project(self.pid)

    def _ready_project(self) -> None:
        db.update_project(
            self.pid,
            script="첫 문장입니다.",
            compiled_script="첫 문장입니다.",
            sentences=["첫 문장입니다."],
            media_order=["scene.png"],
            tts_state="done",
            render_state="idle",
        )

    def test_render_rejects_failed_tts_consistency(self) -> None:
        self._ready_project()
        report = {
            "ok": False,
            "checks": [
                {"key": "tts_consistency", "ok": False, "message": "TTS voice consistency failed."},
                {"key": "oauth", "ok": False, "message": "OAuth client secret is missing."},
            ],
        }

        with patch("app.routers.render.preflight_svc.build_preflight_report", return_value=report):
            response = self.client.post(f"/api/projects/{self.pid}/render")

        self.assertEqual(response.status_code, 409)
        self.assertIn("tts_consistency", response.json()["detail"]["blocking_checks"])
        project = db.get_project(self.pid)
        assert project is not None
        self.assertEqual(project["render_state"], "idle")

    def test_render_allows_missing_oauth_for_local_render(self) -> None:
        self._ready_project()
        report = {
            "ok": False,
            "checks": [
                {"key": "tts_consistency", "ok": True, "message": "ok"},
                {"key": "oauth", "ok": False, "message": "OAuth client secret is missing."},
            ],
        }

        with patch("app.routers.render.preflight_svc.build_preflight_report", return_value=report):
            response = self.client.post(f"/api/projects/{self.pid}/render")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

