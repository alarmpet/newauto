import json
import subprocess
import unittest
from unittest.mock import patch

from app import db
from app.workers import tts_worker


class TtsWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.project = db.create_project("tts-worker-test")

    def tearDown(self) -> None:
        if db.get_project(self.project["id"]) is not None:
            db.delete_project(self.project["id"])

    def test_run_job_with_heartbeat_marks_error_when_subprocess_fails(self) -> None:
        pid = self.project["id"]
        db.update_project(pid, tts_state="running", tts_progress=0, tts_error="")

        with patch(
            "app.workers.tts_worker.resolve_omnivoice_python_with_probes",
            return_value=(
                {
                    "resolved": True,
                    "python_path": r"C:\omnivoice_env\Scripts\python.exe",
                    "omnivoice_import_ok": True,
                    "torch_import_ok": True,
                    "cuda_available": True,
                    "error": "",
                },
                [
                    {
                        "resolved": False,
                        "python_path": r"C:\bad\python.exe",
                        "omnivoice_import_ok": False,
                        "torch_import_ok": False,
                        "cuda_available": False,
                        "error": "bad python",
                    },
                    {
                        "resolved": True,
                        "python_path": r"C:\omnivoice_env\Scripts\python.exe",
                        "omnivoice_import_ok": True,
                        "torch_import_ok": True,
                        "cuda_available": True,
                        "error": "",
                    },
                ],
            ),
        ), patch(
            "app.workers.tts_worker.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["python"],
                returncode=1,
                stdout="",
                stderr="subprocess import failed",
            ),
        ):
            tts_worker._run_job_with_heartbeat(pid)

        project = db.get_project(pid)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "error")
        self.assertIn("subprocess import failed", project["tts_error"])
        output_dir = db.project_dir(pid) / "tts"
        probe_path = output_dir / "omnivoice_runtime_probe.json"
        payload = json.loads(probe_path.read_text(encoding="utf-8"))
        self.assertTrue(payload["success"] is False)
        self.assertEqual(payload["selected_python_path"], r"C:\omnivoice_env\Scripts\python.exe")
        self.assertEqual(len(payload["candidates"]), 2)
        self.assertEqual(payload["final_error"], "subprocess import failed")

    def test_run_job_with_heartbeat_marks_error_when_python_resolver_fails(self) -> None:
        pid = self.project["id"]
        db.update_project(pid, tts_state="running", tts_progress=0, tts_error="")

        with patch(
            "app.workers.tts_worker.resolve_omnivoice_python_with_probes",
            return_value=(
                {
                    "resolved": False,
                    "python_path": "",
                    "omnivoice_import_ok": False,
                    "torch_import_ok": False,
                    "cuda_available": False,
                    "error": "No usable OmniVoice Python environment found.",
                },
                [
                    {
                        "resolved": False,
                        "python_path": r"C:\bad\python.exe",
                        "omnivoice_import_ok": False,
                        "torch_import_ok": False,
                        "cuda_available": False,
                        "error": "No usable OmniVoice Python environment found.",
                    }
                ],
            ),
        ):
            tts_worker._run_job_with_heartbeat(pid)

        project = db.get_project(pid)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "error")
        self.assertIn("No usable OmniVoice Python", project["tts_error"])
        output_dir = db.project_dir(pid) / "tts"
        probe_path = output_dir / "omnivoice_runtime_probe.json"
        payload = json.loads(probe_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["selected_python_path"], "")
        self.assertTrue(payload["success"] is False)
        self.assertIn("No usable OmniVoice Python environment found.", payload["final_error"])

    def test_run_job_retries_full_passage_abort_with_sentence_mode(self) -> None:
        pid = self.project["id"]
        db.update_project(
            pid,
            tts_state="running",
            tts_progress=0,
            tts_error="",
            tts_profile={"synthesis_mode": "full_passage"},
        )

        def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            fake_run.calls += 1
            if fake_run.calls == 1:
                return subprocess.CompletedProcess(
                    args=["python"],
                    returncode=3221225477,
                    stdout="",
                    stderr="Loading weights: 100%|##########| 313/313 [00:00<00:00, 1268.29it/s]",
                )
            db.update_project(pid, tts_state="done", tts_progress=100, tts_error="")
            return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

        fake_run.calls = 0

        with patch(
            "app.workers.tts_worker.resolve_omnivoice_python_with_probes",
            return_value=(
                {
                    "resolved": True,
                    "python_path": r"C:\omnivoice_env\Scripts\python.exe",
                    "omnivoice_import_ok": True,
                    "torch_import_ok": True,
                    "cuda_available": True,
                    "error": "",
                },
                [],
            ),
        ), patch("app.workers.tts_worker.subprocess.run", side_effect=fake_run):
            tts_worker._run_job_with_heartbeat(pid)

        project = db.get_project(pid)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "done")
        self.assertEqual(project["tts_profile"]["synthesis_mode"], "sentence")
        self.assertEqual(project["tts_profile"]["seed_mode"], "fixed")
        self.assertIsInstance(project["tts_profile"]["seed"], int)
        self.assertEqual(fake_run.calls, 2)

    def test_run_job_retries_success_without_outputs_with_sentence_mode(self) -> None:
        pid = self.project["id"]
        db.update_project(
            pid,
            tts_state="running",
            tts_progress=0,
            tts_error="",
            tts_profile={"synthesis_mode": "full_passage"},
        )

        def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            fake_run.calls += 1
            if fake_run.calls == 2:
                db.update_project(pid, tts_state="done", tts_progress=100, tts_error="")
            return subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")

        fake_run.calls = 0

        with patch(
            "app.workers.tts_worker.resolve_omnivoice_python_with_probes",
            return_value=(
                {
                    "resolved": True,
                    "python_path": r"C:\omnivoice_env\Scripts\python.exe",
                    "omnivoice_import_ok": True,
                    "torch_import_ok": True,
                    "cuda_available": True,
                    "error": "",
                },
                [],
            ),
        ), patch("app.workers.tts_worker.subprocess.run", side_effect=fake_run):
            tts_worker._run_job_with_heartbeat(pid)

        project = db.get_project(pid)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "done")
        self.assertEqual(project["tts_profile"]["synthesis_mode"], "sentence")
        self.assertEqual(project["tts_profile"]["seed_mode"], "fixed")
        self.assertIsInstance(project["tts_profile"]["seed"], int)
        self.assertEqual(fake_run.calls, 2)
