import unittest

from app import db


class SourceWorkerDbTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.project = db.create_project("source-worker-test")

    def tearDown(self) -> None:
        db.delete_project(self.project["id"])

    def test_claim_next_queued_source_draft_marks_running(self) -> None:
        db.update_project(self.project["id"], source_draft_state="queued")
        claimed = db.claim_next_queued_source_draft()
        self.assertEqual(claimed, self.project["id"])
        updated = db.get_project(self.project["id"])
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["source_draft_state"], "running")
        self.assertTrue(updated["source_draft_job_id"])

    def test_recover_interrupted_tasks_marks_source_draft_error(self) -> None:
        db.update_project(
            self.project["id"],
            source_draft_state="running",
            source_draft_phase="generate",
        )
        summary = db.recover_interrupted_tasks()
        self.assertGreaterEqual(summary["source_draft"], 1)
        updated = db.get_project(self.project["id"])
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["source_draft_state"], "error")
