import unittest
from collections import namedtuple
from unittest.mock import patch

from app.workers.source_draft_worker import _run_job_with_heartbeat


GeneratedDraft = namedtuple(
    "GeneratedDraft",
    ["script", "previous_script", "warnings", "risk_score", "model", "mode"],
)


class SourceDraftWorkerTests(unittest.TestCase):
    def test_run_job_releases_stale_legacy_ollama_source_draft_lock(self) -> None:
        project = {
            "id": "project-001",
            "source_draft_options": {
                "tone": "informative",
                "target_minutes": 3,
                "language": "ko",
            },
            "source_draft_regenerate_mode": "",
            "source_draft_regenerate_note": "",
        }
        stale_status = {
            "locked": True,
            "resource": "ollama",
            "owner": "source-draft:stale-job",
            "stale": True,
        }
        unlocked_status = {"locked": False, "resource": "", "owner": "", "stale": False}

        with patch(
            "app.workers.source_draft_worker.db.get_project",
            return_value=project,
        ), patch(
            "app.workers.source_draft_worker.generate_script_draft",
            return_value=GeneratedDraft(
                script="new script",
                previous_script="",
                warnings=[],
                risk_score=0.0,
                model="gemma4:e4b",
                mode="",
            ),
        ), patch(
            "app.workers.source_draft_worker.gpu_guard.get_status",
            side_effect=[stale_status, unlocked_status],
        ) as get_status_mock, patch(
            "app.workers.source_draft_worker.gpu_guard.release",
            return_value=True,
        ) as release_mock, patch(
            "app.workers.source_draft_worker.gpu_guard.acquire",
            return_value=True,
        ), patch(
            "app.workers.source_draft_worker.db.touch_source_draft_heartbeat"
        ), patch(
            "app.workers.source_draft_worker.db.update_project"
        ) as update_project_mock:
            _run_job_with_heartbeat("project-001")

        self.assertGreaterEqual(get_status_mock.call_count, 1)
        release_mock.assert_any_call("source-draft:stale-job")
        release_mock.assert_any_call("source-draft:project-001")
        _, update_kwargs = update_project_mock.call_args
        self.assertEqual(update_kwargs["source_draft_state"], "done")
        self.assertEqual(update_kwargs["source_draft_script"], "new script")
