import json
import unittest
from typing import ClassVar
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.services import tts
from app.text import split_sentences


class FakeOmniVoiceModel:
    def __init__(self, empty_text: str | None = None) -> None:
        self.empty_text = empty_text
        self.seen: list[str] = []

    def generate(self, text: str, **kwargs: object) -> list[list[float]]:
        del kwargs
        self.seen.append(text)
        if text == self.empty_text:
            return [[]]
        return [[0.0, 0.25, -0.25, 0.0]]


class TtsPipelineTests(unittest.TestCase):
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

    def create_project(self, title: str = "tts-test") -> str:
        response = self.client.post("/api/projects", data={"title": title})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_split_sentences_filters_punctuation_only_segments(self) -> None:
        script = (
            "첫 문장입니다.\n"
            ".\n"
            "--------------------------------------------------------------------------------\n"
            "둘째 문장입니다?\n"
        )
        self.assertEqual(split_sentences(script), ["첫 문장입니다.", "둘째 문장입니다?"])

    def test_run_tts_job_filters_existing_invalid_segments(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            script="placeholder",
            sentences=["첫 문장입니다.", ".", "둘째 문장입니다?", "--------------------"],
            voice_preset="male-30s-40s-lowmid",
            tts_state="running",
            tts_progress=0,
        )
        fake_model = FakeOmniVoiceModel()

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "soundfile.write"
        ) as write_mock:
            tts.run_tts_job(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "done")
        self.assertEqual(project["tts_progress"], 100)
        self.assertEqual(project["sentences"], ["첫 문장입니다.", "둘째 문장입니다?"])
        self.assertEqual(fake_model.seen, ["첫 문장입니다.", "둘째 문장입니다?"])
        self.assertEqual(write_mock.call_count, 2)

        timings_path = db.project_dir(project_id) / "tts" / "timings.json"
        timings = json.loads(timings_path.read_text(encoding="utf-8"))
        self.assertEqual(len(timings), 2)
        self.assertEqual([entry["text"] for entry in timings], fake_model.seen)

    def test_run_tts_job_clears_stale_outputs_after_empty_audio_error(self) -> None:
        project_id = self.create_project()
        output_dir = db.project_dir(project_id) / "tts"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "0000.wav").write_bytes(b"stale")
        (output_dir / "timings.json").write_text("[]", encoding="utf-8")
        db.update_project(
            project_id,
            script="placeholder",
            sentences=["정상 문장입니다."],
            voice_preset="male-30s-40s-lowmid",
            tts_state="running",
            tts_progress=0,
        )
        fake_model = FakeOmniVoiceModel(empty_text="정상 문장입니다.")

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "soundfile.write"
        ):
            tts.run_tts_job(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "error")
        self.assertFalse((output_dir / "0000.wav").exists())
        self.assertFalse((output_dir / "timings.json").exists())
