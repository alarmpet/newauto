import json
import os
import unittest
from datetime import datetime, timedelta, timezone
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
        self.assertEqual(manifest["tts_profile"]["seed_mode"], "per_sentence")
        self.assertEqual(len(manifest["sentences"]), 2)
        seed = project["tts_profile"]["seed"]
        self.assertIsNotNone(seed)
        assert seed is not None
        self.assertEqual(manifest["sentences"][0]["seed"], seed)
        self.assertEqual(
            manifest["sentences"][1]["seed"],
            seed + 1,
        )

    def test_save_audio_file_removes_large_dc_offset_before_writing(self) -> None:
        with patch("soundfile.write") as write_mock:
            tts.save_audio_file([0.45, 0.5, 0.55], db.PROJECTS_DIR / "dc-test.wav")

        written = write_mock.call_args.args[1]
        self.assertAlmostEqual(float(sum(written)) / len(written), 0.0, places=5)
        self.assertLessEqual(max(abs(float(value)) for value in written), 0.98)

    def test_run_tts_job_keeps_same_seed_in_fixed_mode(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            script="Sentence one. Sentence two.",
            sentences=["Sentence one.", "Sentence two."],
            voice_preset="male-deep-calm",
            tts_profile={"seed_mode": "fixed", "seed": 321},
            tts_state="running",
            tts_progress=0,
        )
        fake_model = FakeOmniVoiceModel()

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ), patch("soundfile.write"):
            tts.run_tts_job(project_id)

        manifest_path = db.project_dir(project_id) / "tts" / "tts_run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["tts_profile"]["seed_mode"], "fixed")
        self.assertEqual(manifest["sentences"][0]["seed"], 321)
        self.assertEqual(manifest["sentences"][1]["seed"], 321)
        consistency_path = db.project_dir(project_id) / "tts" / "tts_consistency_report.json"
        consistency = json.loads(consistency_path.read_text(encoding="utf-8"))
        self.assertTrue(consistency["metadata_consistent"])
        self.assertFalse(consistency["audio_consistency_checked"])
        self.assertIn("max_estimated_pitch_relative_drift", consistency)

    def test_sync_tts_artifacts_records_pipeline_manifest_segments(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            compiled_script="Sentence one.",
            sentences=["Sentence one."],
        )
        output_dir = db.project_dir(project_id) / "tts"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "timings.json").write_text(
            json.dumps([{"idx": 0, "text": "Sentence one.", "start": 0.0, "end": 1.25, "dur": 1.25}]),
            encoding="utf-8",
        )
        (output_dir / "tts_run_manifest.json").write_text(
            json.dumps(
                {
                    "voice_preset": "male-deep-calm",
                    "tts_profile": {"seed_mode": "fixed"},
                    "sentences": [{"idx": 0, "text": "Sentence one.", "seed": 321}],
                }
            ),
            encoding="utf-8",
        )

        tts.sync_tts_artifacts_to_pipeline_manifest(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        artifact = project["pipeline_manifest"]["segments"][0]["tts"]
        self.assertIsNotNone(artifact)
        assert artifact is not None
        self.assertEqual(artifact["wav_path"], "tts/0000.wav")
        self.assertEqual(artifact["duration_sec"], 1.25)
        self.assertEqual(artifact["seed"], 321)
        self.assertEqual(project["pipeline_manifest"]["stage_status"]["tts"]["state"], "done")

    def test_run_tts_job_removes_latin_alias_after_korean_text(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            script="placeholder",
            sentences=[
                "젠슨 황(Jensen Huang) 엔비디아(Nvidia) CEO가 합류했다.",
                "CNBC 등 외신은 공식 확인했다.",
            ],
            voice_preset="male-deep-calm",
            tts_state="running",
            tts_progress=0,
        )
        fake_model = FakeOmniVoiceModel()

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ), patch("soundfile.write"):
            tts.run_tts_job(project_id)

        self.assertEqual(
            fake_model.seen,
            ["젠슨 황 엔비디아 CEO가 합류했다.", "CNBC 등 외신은 공식 확인했다."],
        )
        timings_path = db.project_dir(project_id) / "tts" / "timings.json"
        timings = json.loads(timings_path.read_text(encoding="utf-8"))
        self.assertEqual(timings[0]["text"], "젠슨 황 엔비디아 CEO가 합류했다.")

    def test_run_tts_job_full_passage_synthesizes_once_and_splits(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            script="Sentence one. Sentence two.",
            sentences=["Sentence one.", "Sentence two."],
            voice_preset="male-deep-calm",
            tts_profile={"synthesis_mode": "full_passage", "seed_mode": "fixed", "seed": 321},
            tts_state="running",
            tts_progress=0,
        )
        fake_model = FakeOmniVoiceModel()

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ) as seed_mock, patch("soundfile.write") as write_mock:
            tts.run_tts_job(project_id)

        self.assertEqual(fake_model.seen, ["Sentence one.\nSentence two."])
        self.assertEqual(seed_mock.call_count, 1)
        self.assertEqual(write_mock.call_count, 2)
        manifest_path = db.project_dir(project_id) / "tts" / "tts_run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["tts_profile"]["synthesis_mode"], "full_passage")
        self.assertEqual(manifest["sentences"][0]["seed"], 321)
        self.assertEqual(manifest["sentences"][1]["seed"], 321)
        timings_path = db.project_dir(project_id) / "tts" / "timings.json"
        timings = json.loads(timings_path.read_text(encoding="utf-8"))
        self.assertEqual(len(timings), 2)
        self.assertEqual(timings[0]["end"], timings[1]["start"])

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

    def test_run_tts_job_applies_bible_region_speed_override(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            script="placeholder",
            compiled_script="Intro sentence.\nBible sentence.",
            sentences=["Intro sentence.", "Bible sentence."],
            regional_sentences=[
                {"idx": 0, "text": "Intro sentence.", "region": "intro"},
                {"idx": 1, "text": "Bible sentence.", "region": "bible"},
            ],
            voice_preset="male-deep-calm",
            tts_state="running",
            tts_progress=0,
        )
        fake_model = FakeOmniVoiceModel()

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ), patch("soundfile.write"):
            tts.run_tts_job(project_id)

        self.assertEqual(fake_model.seen, ["Intro sentence.", "Bible sentence."])
        self.assertEqual(fake_model.kwargs_seen[1]["speed"], 0.90)
        timings_path = db.project_dir(project_id) / "tts" / "timings.json"
        timings = json.loads(timings_path.read_text(encoding="utf-8"))
        self.assertEqual([entry["region"] for entry in timings], ["intro", "bible"])
        manifest_path = db.project_dir(project_id) / "tts" / "tts_run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual([entry["region"] for entry in manifest["sentences"]], ["intro", "bible"])
        self.assertEqual(manifest["sentences"][1]["effective_profile"]["speed"], 0.90)

    def test_run_tts_job_cleans_generation_memory_every_five_sentences(self) -> None:
        project_id = self.create_project()
        sentences = [f"Sentence {index}." for index in range(10)]
        db.update_project(
            project_id,
            script=" ".join(sentences),
            sentences=sentences,
            voice_preset="male-deep-calm",
            tts_state="running",
            tts_progress=0,
        )
        fake_model = FakeOmniVoiceModel()

        with patch("app.services.tts._get_model", return_value=fake_model), patch(
            "app.services.tts._apply_seed"
        ), patch("app.services.tts._cleanup_generation_memory") as cleanup_mock, patch("soundfile.write"):
            tts.run_tts_job(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "done")
        self.assertEqual(cleanup_mock.call_count, 2)

    def test_trim_trailing_silence_keeps_short_tail_and_trims_long_tail(self) -> None:
        kept = tts._trim_trailing_silence([0.0, 0.2, -0.2, 0.0])
        trimmed = tts._trim_trailing_silence([0.0, 0.3, -0.3] + ([0.0] * 4000))

        self.assertEqual(len(kept), 4)
        self.assertLess(len(trimmed), 4003)
        self.assertGreater(len(trimmed), 3)

    def test_unload_model_clears_cached_model(self) -> None:
        fake_model = FakeOmniVoiceModel()
        tts._model = fake_model

        tts.unload_model()

        self.assertIsNone(tts._model)

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
        self.assertEqual(project["tts_profile"]["seed_mode"], "per_sentence")
        self.assertEqual(project["tts_state"], "queued")
        self.assertEqual(project["tts_progress"], 0)
        self.assertEqual(project["tts_error"], "")

    def test_start_tts_route_persists_fixed_seed_mode(self) -> None:
        project_id = self.create_project()
        save_response = self.client.put(
            f"/api/projects/{project_id}/script",
            data={
                "title": "tts fixed seed mode",
                "script": "First sentence. Second sentence.",
            },
        )
        self.assertEqual(save_response.status_code, 200)

        with patch("app.services.tts.run_tts_job"):
            response = self.client.post(
                f"/api/projects/{project_id}/tts",
                json={
                    "voice_preset": "female-bright-clear",
                    "tts_profile": {
                        "seed_mode": "fixed",
                        "seed": 777,
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_profile"]["seed_mode"], "fixed")
        self.assertEqual(project["tts_profile"]["seed"], 777)

    def test_claim_next_queued_tts_sets_running_metadata(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, tts_state="queued", tts_progress=0)

        claimed = db.claim_next_queued_tts()

        self.assertEqual(claimed, project_id)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "running")
        self.assertNotEqual(project["tts_job_id"], "")
        self.assertNotEqual(project["tts_started_at"], "")
        self.assertNotEqual(project["tts_heartbeat_at"], "")

    def test_recover_stale_tts_jobs_marks_error_and_clears_metadata(self) -> None:
        project_id = self.create_project()
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="seconds")
        db.update_project(
            project_id,
            tts_state="running",
            tts_progress=72,
            tts_error="",
            tts_job_id="ttsjob123",
            tts_started_at=stale_time,
            tts_heartbeat_at=stale_time,
        )

        recovered = db.recover_stale_tts_jobs(stale_after_sec=60, max_runtime_sec=120)

        self.assertEqual(recovered, 1)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "error")
        self.assertEqual(project["tts_progress"], 0)
        self.assertEqual(project["tts_job_id"], "")
        self.assertEqual(project["tts_started_at"], "")
        self.assertEqual(project["tts_heartbeat_at"], "")
        self.assertIn("heartbeat expired", project["tts_error"])

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

    def test_tts_preview_route_returns_409_when_gpu_is_busy(self) -> None:
        project_id = self.create_project()
        with patch(
            "app.services.tts.synthesize_preview_with_profile",
            side_effect=RuntimeError("GPU is busy with source-draft:test"),
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/tts/preview",
                json={"voice_preset": "male-deep-calm", "sample_text": "test"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("GPU is busy", response.text)

    def test_run_tts_job_marks_error_when_gpu_is_busy(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            script="placeholder",
            sentences=["첫 문장입니다."],
            voice_preset="male-deep-calm",
            tts_state="running",
            tts_progress=0,
        )

        with patch(
            "app.services.tts._acquire_tts_gpu",
            side_effect=RuntimeError("GPU is busy with source-draft:test"),
        ):
            tts.run_tts_job(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["tts_state"], "error")

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
