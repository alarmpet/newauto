import json
import unittest
from pathlib import Path

from app import db
from app.services import tts


class TtsQualityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.project = db.create_project("tts quality")
        self.pid = self.project["id"]

    def tearDown(self) -> None:
        db.delete_project(self.pid)

    def _write_report(self, output_dir: Path, *, passed: bool) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "tts_consistency_report.json").write_text(
            json.dumps(
                {
                    "metadata_consistent": True,
                    "audio_consistency_checked": True,
                    "audio_consistency_passed": passed,
                    "recommended_tts_mode": "full_passage_or_reference_voice",
                }
            ),
            encoding="utf-8",
        )

    def test_first_consistency_failure_waits_for_worker_retry(self) -> None:
        output_dir = db.project_dir(self.pid) / "tts"
        db.update_project(
            self.pid,
            tts_profile={"synthesis_mode": "sentence", "_consistency_retry_attempted": False},
        )
        self._write_report(output_dir, passed=False)

        tts._raise_if_final_tts_quality_failed(self.pid, output_dir)

    def test_failed_final_consistency_marks_tts_error(self) -> None:
        output_dir = db.project_dir(self.pid) / "tts"
        db.update_project(
            self.pid,
            tts_profile={"synthesis_mode": "full_passage", "_consistency_retry_attempted": True},
        )
        self._write_report(output_dir, passed=False)

        with self.assertRaises(RuntimeError):
            tts._raise_if_final_tts_quality_failed(self.pid, output_dir)

