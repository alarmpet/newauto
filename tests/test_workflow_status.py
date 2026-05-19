import os
import unittest
from typing import ClassVar

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app


class WorkflowStatusTests(unittest.TestCase):
    client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        db.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def setUp(self) -> None:
        response = self.client.post("/api/projects", data={"title": "workflow-status-test"})
        self.assertEqual(response.status_code, 200)
        self.project_id = str(response.json()["id"])

    def tearDown(self) -> None:
        self.client.delete(f"/api/projects/{self.project_id}")

    def test_workflow_status_returns_pipeline_manifest_and_stage_cards(self) -> None:
        response = self.client.get(f"/api/projects/{self.project_id}/workflow-status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("pipeline_manifest", payload)
        self.assertIn("stage_cards", payload)
        self.assertGreaterEqual(len(payload["stage_cards"]), 5)
        first = payload["stage_cards"][0]
        self.assertIn("stage", first)
        self.assertIn("state", first)
        self.assertIn("issues", first)
        self.assertIn("primary_action", first)
