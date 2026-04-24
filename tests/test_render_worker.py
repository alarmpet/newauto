import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app import db
from app.workers.worker_lock import single_instance_lock


class RenderWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.project_ids: list[str] = []

    def tearDown(self) -> None:
        for project_id in self.project_ids:
            if db.get_project(project_id) is not None:
                db.delete_project(project_id)

    def create_project(self, title: str = "worker-test") -> str:
        project = db.create_project(title)
        self.project_ids.append(project["id"])
        return project["id"]

    def test_claim_next_queued_render_sets_running_metadata(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, render_state="queued")

        claimed_id = db.claim_next_queued_render()

        self.assertEqual(claimed_id, project_id)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["render_state"], "running")
        self.assertNotEqual(project["render_job_id"], "")
        self.assertNotEqual(project["render_started_at"], "")
        self.assertNotEqual(project["render_heartbeat_at"], "")

    def test_recover_stale_render_jobs_marks_error_and_clears_metadata(self) -> None:
        project_id = self.create_project()
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="seconds")
        db.update_project(
            project_id,
            render_state="running",
            render_progress=72,
            render_phase="build_visual_landscape",
            render_job_id="job123",
            render_started_at=stale_time,
            render_heartbeat_at=stale_time,
        )

        recovered = db.recover_stale_render_jobs(stale_after_sec=60, max_runtime_sec=120)

        self.assertEqual(recovered, 1)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["render_state"], "error")
        self.assertEqual(project["render_progress"], 0)
        self.assertEqual(project["render_phase"], "")
        self.assertEqual(project["render_job_id"], "")
        self.assertEqual(project["render_started_at"], "")
        self.assertEqual(project["render_heartbeat_at"], "")
        self.assertIn("heartbeat expired", project["render_last_log"])

    def test_single_instance_lock_reuses_stale_pid_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "render_worker.lock"
            lock_path.write_text("999999", encoding="utf-8")

            with single_instance_lock(lock_path) as acquired:
                self.assertTrue(acquired)
                self.assertTrue(lock_path.exists())
                self.assertEqual(lock_path.read_text(encoding="utf-8").strip(), str(os.getpid()))

            self.assertFalse(lock_path.exists())
