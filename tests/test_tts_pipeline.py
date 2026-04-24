import json
import os
import unittest
from typing import ClassVar
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app
from app.services import tts
from app.text import split_sentences


class FakeOmniVoiceModel:
    def __init__(self, empty_text: str | None = None) -> None:
        self.empty_text = empty_text
        self.seen: list[str] = []
        self.kwargs_seen: list[dict[str, object]] = []

    def generate(self, text: str, **kwargs: object) -> list[list[float]]:
        self.seen.append(text)
        self.kwargs_seen.append(dict(kwargs))
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
            "두 번째 문장입니다.\n"
        )
        self.assertEqual(split_sentences(script), ["첫 문장입니다.", "두 번째 문장입니다."])

    def test_run_tts_job_filters_existing_invalid_segments(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            script="placeholder",
            sentences=["첫 문장입니다.", ".", "두 번째 문장입니다.", "--------------------"],
            voice_preset="male-deep-calm",
            tts_state="running",
            tts_progress=0,
        )
        fake_model = FakeOmniVoiceModel()

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ) as seed_mock, patch("soundfile.write") as write_mock:
            tts.run_tts_job(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "done")
        self.assertEqual(project["tts_progress"], 100)
        self.assertEqual(project["sentences"], ["첫 문장입니다.", "두 번째 문장입니다."])
        self.assertEqual(fake_model.seen, ["첫 문장입니다.", "두 번째 문장입니다."])
        self.assertEqual(write_mock.call_count, 2)
        self.assertEqual(project["tts_profile"]["language"], "ko")
        self.assertEqual(project["tts_profile"]["mode"], "design")
        self.assertIsNotNone(project["tts_profile"]["seed"])
        self.assertEqual(seed_mock.call_count, 2)
        first_kwargs = fake_model.kwargs_seen[0]
        self.assertEqual(first_kwargs["language"], "ko")
        self.assertEqual(first_kwargs["speed"], 0.96)
        generation_config = first_kwargs["generation_config"]
        self.assertEqual(getattr(generation_config, "num_step"), 36)
        self.assertEqual(getattr(generation_config, "guidance_scale"), 2.9)

        timings_path = db.project_dir(project_id) / "tts" / "timings.json"
        timings = json.loads(timings_path.read_text(encoding="utf-8"))
        self.assertEqual(len(timings), 2)
        self.assertEqual([entry["text"] for entry in timings], fake_model.seen)

        manifest_path = db.project_dir(project_id) / "tts" / "tts_run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["voice_preset"], "male-deep-calm")
        self.assertEqual(len(manifest["sentences"]), 2)
        seed = project["tts_profile"]["seed"]
        self.assertIsNotNone(seed)
        assert seed is not None
        self.assertEqual(manifest["sentences"][0]["seed"], seed)
        self.assertEqual(
            manifest["sentences"][1]["seed"],
            seed + 1,
        )

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
            voice_preset="male-deep-calm",
            tts_state="running",
            tts_progress=0,
        )
        fake_model = FakeOmniVoiceModel(empty_text="정상 문장입니다.")

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ), patch("soundfile.write"):
            tts.run_tts_job(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "error")
        self.assertFalse((output_dir / "0000.wav").exists())
        self.assertFalse((output_dir / "timings.json").exists())
        self.assertFalse((output_dir / "tts_run_manifest.json").exists())

    def test_start_tts_route_persists_profile_payload(self) -> None:
        project_id = self.create_project()
        save_response = self.client.put(
            f"/api/projects/{project_id}/script",
            data={
                "title": "tts profile",
                "script": "첫 문장입니다. 두 번째 문장입니다.",
            },
        )
        self.assertEqual(save_response.status_code, 200)

        with patch("app.services.tts.run_tts_job"):
            response = self.client.post(
                f"/api/projects/{project_id}/tts",
                json={
                    "voice_preset": "female-bright-clear",
                    "tts_profile": {
                        "mode": "design",
                        "language": "ko",
                        "instruct": "female, high pitch",
                        "speed": 1.05,
                        "num_step": 42,
                        "guidance_scale": 3.4,
                        "denoise": True,
                        "postprocess_output": True,
                    },
                },
            )
        self.assertEqual(response.status_code, 200)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["voice_preset"], "female-bright-clear")
        self.assertEqual(project["tts_profile"]["language"], "ko")
        self.assertEqual(project["tts_profile"]["speed"], 1.05)
        self.assertEqual(project["tts_profile"]["num_step"], 42)
        self.assertIsInstance(project["tts_profile"]["seed"], int)

    def test_tts_preset_catalog_route_exposes_aliases(self) -> None:
        response = self.client.get("/api/tts/presets")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["aliases"]["male-30s-40s-lowmid"], "male-deep-calm")
        self.assertEqual(
            payload["presets"]["male-mid-clear"]["instruct"],
            "male, moderate pitch",
        )
        self.assertIn("male-60s-low", payload["order"])

    def test_tts_preview_route_generates_audio_file_and_lock(self) -> None:
        project_id = self.create_project()
        preview_path = db.project_dir(project_id) / "tts_preview.wav"
        fake_model = FakeOmniVoiceModel()

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ) as seed_mock, patch("soundfile.write") as write_mock:
            response = self.client.post(
                f"/api/projects/{project_id}/tts/preview",
                json={
                    "voice_preset": "female-bright-clear",
                    "sample_text": "샘플 음성을 들어봅니다.",
                    "tts_profile": {
                        "mode": "design",
                        "language": "ko",
                        "instruct": "female, high pitch",
                        "speed": 1.04,
                        "num_step": 38,
                        "guidance_scale": 3.1,
                        "denoise": True,
                        "postprocess_output": True,
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["preview_url"], f"/api/projects/{project_id}/tts-preview")
        self.assertEqual(payload["sample_text"], "샘플 음성을 들어봅니다.")
        self.assertEqual(payload["voice_preset"], "female-bright-clear")
        self.assertEqual(payload["tts_profile"]["num_step"], 38)
        self.assertIsInstance(payload["tts_profile"]["seed"], int)
        self.assertEqual(payload["preview_lock"]["voice_preset"], "female-bright-clear")
        self.assertEqual(
            payload["preview_lock"]["tts_profile"]["seed"],
            payload["tts_profile"]["seed"],
        )
        self.assertEqual(fake_model.seen, ["샘플 음성을 들어봅니다."])
        self.assertEqual(seed_mock.call_args.args[0], payload["tts_profile"]["seed"])
        self.assertEqual(write_mock.call_count, 1)
        self.assertEqual(write_mock.call_args.args[0], preview_path)

    def test_tts_preview_route_returns_400_for_invalid_preview_profile(self) -> None:
        project_id = self.create_project()
        with patch(
            "app.services.tts.synthesize_preview_with_profile",
            side_effect=ValueError("Unsupported instruct items"),
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/tts/preview",
                json={"voice_preset": "male-deep-calm", "sample_text": "test"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported instruct items", response.text)

    def test_start_tts_reuses_preview_lock_seed(self) -> None:
        project_id = self.create_project()
        self.client.put(
            f"/api/projects/{project_id}/script",
            data={"title": "seed lock", "script": "첫 문장입니다."},
        )
        fake_model = FakeOmniVoiceModel()
        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ), patch("soundfile.write"):
            preview_response = self.client.post(
                f"/api/projects/{project_id}/tts/preview",
                json={
                    "voice_preset": "male-60s-low",
                    "sample_text": "미리듣기 샘플입니다.",
                },
            )
        self.assertEqual(preview_response.status_code, 200)
        preview_payload = preview_response.json()

        with patch("app.services.tts.run_tts_job"):
            response = self.client.post(
                f"/api/projects/{project_id}/tts",
                json={
                    "voice_preset": "male-60s-low",
                    "preview_lock": preview_payload["preview_lock"],
                },
            )

        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_profile"]["seed"], preview_payload["tts_profile"]["seed"])

    def test_start_tts_rejects_changed_profile_after_preview(self) -> None:
        project_id = self.create_project()
        self.client.put(
            f"/api/projects/{project_id}/script",
            data={"title": "seed lock", "script": "첫 문장입니다."},
        )
        fake_model = FakeOmniVoiceModel()
        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ), patch("soundfile.write"):
            preview_response = self.client.post(
                f"/api/projects/{project_id}/tts/preview",
                json={
                    "voice_preset": "male-60s-low",
                    "sample_text": "미리듣기 샘플입니다.",
                },
            )
        preview_payload = preview_response.json()

        with patch("app.services.tts.run_tts_job"):
            response = self.client.post(
                f"/api/projects/{project_id}/tts",
                json={
                    "voice_preset": "male-60s-low",
                    "tts_profile": {"speed": 1.05},
                    "preview_lock": preview_payload["preview_lock"],
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("generate a new sample first", response.text)
