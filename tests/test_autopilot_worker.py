import unittest
from pathlib import Path
from fastapi import HTTPException
from unittest.mock import patch

from app import db
from app.services import autopilot as autopilot_svc
from app.types import ProjectRecord


class AutopilotWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        db.init_db()
        self.project = db.create_project("autopilot-worker-test")

    def tearDown(self) -> None:
        db.delete_project(self.project["id"])

    def test_claim_next_queued_autopilot_marks_running(self) -> None:
        db.update_project(self.project["id"], autopilot_state="queued")
        claimed = db.claim_next_queued_autopilot()
        self.assertEqual(claimed, self.project["id"])
        updated = db.get_project(self.project["id"])
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["autopilot_state"], "running")

    def test_run_autopilot_job_completes_script_mode(self) -> None:
        options = autopilot_svc.default_options()
        options["input_mode"] = "script"
        options["script"] = "첫 문장입니다. 둘째 문장입니다."
        started = autopilot_svc.start(self.project["id"], options)
        self.assertEqual(started["autopilot_state"], "queued")
        db.claim_next_queued_autopilot()

        def fake_wait(
            pid: str,
            *,
            field: str,
            done_value: str,
            error_value: str = "error",
            phase: str,
            progress: int,
            message: str,
            state_label: str,
        ) -> ProjectRecord:
            if field == "tts_state":
                db.update_project(pid, tts_state="done", tts_progress=100, tts_error="")
            elif field == "body_image_state":
                db.update_project(
                    pid,
                    body_image_state="done",
                    body_image_progress=100,
                    body_image_mappings=[{"sentence_idx": 0, "path": "image0.png", "prompt": "prompt"}],
                    media_order=["image0.png"],
                )
            elif field == "render_state":
                db.update_project(pid, render_state="done", render_progress=100)
            project = db.get_project(pid)
            assert project is not None
            return project

        with patch("app.services.autopilot.suggest_image_prompt_batch",
            return_value=[{"sentence_idx": 0, "positive_prompt": "prompt", "negative_prompt": ""}],
        ), patch(
            "app.services.autopilot._wait_for_state",
            side_effect=fake_wait,
        ), patch(
            "app.services.autopilot.build_scene_plan",
            return_value={"version": 1, "format": "landscape", "total_duration": 2.0, "scenes": []},
        ), patch(
            "app.services.autopilot.build_render_plan",
            return_value={"version": 1, "total_duration": 2.0, "segments": []},
        ), patch(
            "app.services.autopilot.build_preflight_report",
            return_value={"ok": True, "checks": []},
        ), patch(
            "app.services.autopilot.load_render_report",
            return_value={
                "project_id": self.project["id"],
                "title": "x",
                "status": "done",
                "created_at": "",
                "render_started_at": "",
                "render_finished_at": "",
                "audio_duration_sec": 1.0,
                "subtitle_cue_count": 1,
                "render_plan_segment_count": 0,
                "missing_render_plan_media_count": 0,
                "fallback_used": False,
                "outputs": [{"format": "landscape", "path": "out.mp4", "exists": True, "size_bytes": 1, "duration_sec": 1.0}],
                "segments": [],
                "ffmpeg_log_tail": "",
                "error": "",
            },
        ):
            autopilot_svc.run_autopilot_job(self.project["id"])

        updated = db.get_project(self.project["id"])
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["autopilot_state"], "done")
        self.assertEqual(updated["visual_source_mode"], "comfyui_auto")
        self.assertEqual(updated["autopilot_phase"], "done")
        self.assertEqual(updated["autopilot_progress"], 100)
        self.assertEqual(updated["voice_preset"], "male-announcer-40s-50s")
        self.assertEqual(updated["tts_profile"]["mode"], "design")
        self.assertEqual(updated["tts_profile"]["seed_mode"], "fixed")
        self.assertEqual(updated["tts_profile"]["synthesis_mode"], "full_passage")
        self.assertEqual(updated["tts_profile"]["instruct"], "male, middle-aged, moderate pitch")

    def test_run_autopilot_job_pauses_on_preflight_failure(self) -> None:
        options = autopilot_svc.default_options()
        options["input_mode"] = "script"
        options["script"] = "첫 문장입니다."
        autopilot_svc.start(self.project["id"], options)
        db.claim_next_queued_autopilot()

        def fake_wait(
            pid: str,
            *,
            field: str,
            done_value: str,
            error_value: str = "error",
            phase: str,
            progress: int,
            message: str,
            state_label: str,
        ) -> ProjectRecord:
            if field == "tts_state":
                db.update_project(pid, tts_state="done", tts_progress=100, tts_error="")
            elif field == "tts_state":
                db.update_project(pid, tts_state="done", tts_progress=100, tts_error="")
            elif field == "body_image_state":
                db.update_project(pid, body_image_state="done", body_image_progress=100)
            project = db.get_project(pid)
            assert project is not None
            return project

        with patch("app.services.autopilot.suggest_image_prompt_batch",
            return_value=[{"sentence_idx": 0, "positive_prompt": "prompt", "negative_prompt": ""}],
        ), patch(
            "app.services.autopilot._wait_for_state",
            side_effect=fake_wait,
        ), patch(
            "app.services.autopilot.build_scene_plan",
            return_value={"version": 1, "format": "landscape", "total_duration": 1.0, "scenes": []},
        ), patch(
            "app.services.autopilot.build_render_plan",
            return_value={"version": 1, "total_duration": 1.0, "segments": []},
        ), patch(
            "app.services.autopilot.build_preflight_report",
            return_value={"ok": False, "checks": [{"key": "media", "ok": False, "message": "Upload media first."}]},
        ):
            autopilot_svc.run_autopilot_job(self.project["id"])

        updated = db.get_project(self.project["id"])
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["autopilot_state"], "paused")
        self.assertEqual(updated["autopilot_last_error_code"], "PREFLIGHT_MEDIA")

    def test_run_autopilot_job_url_mode_applies_source_draft(self) -> None:
        options = autopilot_svc.default_options()
        options["input_mode"] = "url"
        options["url"] = "https://example.com/article"
        autopilot_svc.start(self.project["id"], options)
        db.claim_next_queued_autopilot()

        def fake_collect_url(pid: str, url: str) -> ProjectRecord:
            updated = db.update_project(
                pid,
                source_draft_input_mode="url",
                source_draft_query=url,
                source_draft_sources=[{
                    "id": "src1",
                    "url": url,
                    "final_url": url,
                    "title": "Example",
                    "domain": "example.com",
                    "author": "",
                    "published_at": "",
                    "language": "ko",
                    "excerpt": "기사 요약",
                    "fetched_at": "",
                    "word_count": 100,
                }],
                source_draft_fact_notes=[{"source_id": "src1", "note": "사실 노트"}],
            )
            assert updated is not None
            return updated

        def fake_wait(
            pid: str,
            *,
            field: str,
            done_value: str,
            error_value: str = "error",
            phase: str,
            progress: int,
            message: str,
            state_label: str,
        ) -> ProjectRecord:
            if field == "source_draft_state":
                db.update_project(
                    pid,
                    source_draft_state="done",
                    source_draft_script="자동 생성 초안입니다.",
                    source_draft_risk_score=0.1,
                    source_draft_regenerate_mode="",
                )
            elif field == "body_image_state":
                db.update_project(pid, body_image_state="done", body_image_progress=100)
            elif field == "render_state":
                db.update_project(pid, render_state="done", render_progress=100)
            project = db.get_project(pid)
            assert project is not None
            return project

        with patch("app.services.autopilot._collect_url_source", side_effect=fake_collect_url), patch(
            "app.services.autopilot._wait_for_state",
            side_effect=fake_wait,
        ), patch(
            "app.services.autopilot.suggest_image_prompt_batch",
            return_value=[{"sentence_idx": 0, "positive_prompt": "prompt", "negative_prompt": ""}],
        ), patch(
            "app.services.autopilot.build_scene_plan",
            return_value={"version": 1, "format": "landscape", "total_duration": 1.0, "scenes": []},
        ), patch(
            "app.services.autopilot.build_render_plan",
            return_value={"version": 1, "total_duration": 1.0, "segments": []},
        ), patch(
            "app.services.autopilot.build_preflight_report",
            return_value={"ok": True, "checks": []},
        ), patch(
            "app.services.autopilot.load_render_report",
            return_value=None,
        ):
            autopilot_svc.run_autopilot_job(self.project["id"])

        updated = db.get_project(self.project["id"])
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["autopilot_state"], "done")
        self.assertEqual(updated["user_script"], "자동 생성 초안입니다.")
        manifest_path_value = updated["body_image_options"].get("image_prompts_manifest_path")
        self.assertIsInstance(manifest_path_value, str)
        assert isinstance(manifest_path_value, str)
        self.assertTrue(Path(manifest_path_value).exists())

    def test_run_autopilot_job_pauses_when_user_script_would_be_overwritten(self) -> None:
        options = autopilot_svc.default_options()
        options["input_mode"] = "url"
        options["url"] = "https://example.com/article"
        autopilot_svc.start(self.project["id"], options)
        db.claim_next_queued_autopilot()
        db.update_project(self.project["id"], user_script="기존 사용자가 직접 쓴 대본")

        def fake_collect_url(pid: str, url: str) -> ProjectRecord:
            updated = db.update_project(
                pid,
                source_draft_input_mode="url",
                source_draft_query=url,
                source_draft_sources=[{
                    "id": "src1",
                    "url": url,
                    "final_url": url,
                    "title": "Example",
                    "domain": "example.com",
                    "author": "",
                    "published_at": "",
                    "language": "ko",
                    "excerpt": "기사 요약",
                    "fetched_at": "",
                    "word_count": 100,
                }],
                source_draft_fact_notes=[{"source_id": "src1", "note": "사실 노트"}],
            )
            assert updated is not None
            return updated

        def fake_wait(
            pid: str,
            *,
            field: str,
            done_value: str,
            error_value: str = "error",
            phase: str,
            progress: int,
            message: str,
            state_label: str,
        ) -> ProjectRecord:
            db.update_project(
                pid,
                source_draft_state="done",
                source_draft_script="자동 생성 초안입니다.",
                source_draft_risk_score=0.1,
                source_draft_regenerate_mode="",
            )
            project = db.get_project(pid)
            assert project is not None
            return project

        with patch("app.services.autopilot._collect_url_source", side_effect=fake_collect_url), patch(
            "app.services.autopilot._wait_for_state",
            side_effect=fake_wait,
        ):
            autopilot_svc.run_autopilot_job(self.project["id"])

        updated = db.get_project(self.project["id"])
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["autopilot_state"], "paused")
        self.assertEqual(updated["autopilot_last_error_code"], "COPY_USER_SCRIPT_OVERWRITE")
        self.assertTrue((db.project_dir(self.project["id"]) / "autopilot" / "pre_apply_backup.txt").exists())

    def test_run_autopilot_job_keyword_mode_pauses_on_brave_limit(self) -> None:
        options = autopilot_svc.default_options()
        options["input_mode"] = "keyword"
        options["keyword"] = "반도체 전망"
        autopilot_svc.start(self.project["id"], options)
        db.claim_next_queued_autopilot()

        with patch(
            "app.services.autopilot._collect_keyword_sources",
            side_effect=HTTPException(429, "Brave limit reached"),
        ):
            autopilot_svc.run_autopilot_job(self.project["id"])

        updated = db.get_project(self.project["id"])
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated["autopilot_state"], "paused")
        self.assertEqual(updated["autopilot_last_error_code"], "BRAVE_RATE_LIMIT")

    def test_build_image_batch_items_does_not_auto_upgrade_to_stickman_lora(self) -> None:
        options = autopilot_svc.default_options()
        db.update_project(
            self.project["id"],
            sentences=["첫 장면입니다.", "둘째 장면입니다."],
            visual_source_mode="comfyui_auto",
        )
        project = db.get_project(self.project["id"])
        self.assertIsNotNone(project)
        assert project is not None

        with patch(
            "app.services.autopilot.suggest_image_prompt_batch",
            return_value=[
                {"sentence_idx": 0, "positive_prompt": "scene one", "negative_prompt": "", "sentence_hash": "h1"},
                {"sentence_idx": 1, "positive_prompt": "scene two", "negative_prompt": "", "sentence_hash": "h2"},
            ],
        ), patch(
            "app.services.autopilot._find_stickfigures_lora_name",
            return_value="Stickfigures-000005.safetensors",
        ):
            items = autopilot_svc._build_image_batch_items(project, options)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["template_id"], "txt2img_sdxl_basic")
        self.assertEqual(items[0]["lora_name"], "")
        self.assertEqual(items[0]["lora_strength"], 0.0)

    def test_build_image_batch_items_uses_explicit_stickman_lora_when_allowed(self) -> None:
        options = autopilot_svc.default_options()
        db.update_project(
            self.project["id"],
            sentences=["simple symbolic explainer scene"],
            visual_source_mode="comfyui_auto",
        )
        project = db.get_project(self.project["id"])
        self.assertIsNotNone(project)
        assert project is not None

        with patch(
            "app.services.autopilot.suggest_image_prompt_batch",
            return_value=[
                {
                    "sentence_idx": 0,
                    "positive_prompt": "Flipchartvisu, Stick figure, one helper points at one oversized idea bulb",
                    "negative_prompt": "",
                    "sentence_hash": "h1",
                    "template_id": "txt2img_sdxl_stickman_lora",
                    "visual_brief": {"domain": "generic_explainer"},
                    "visual_plan": {"domain": "generic_explainer", "lora_policy": "stickman"},
                },
            ],
        ), patch(
            "app.services.autopilot._find_stickfigures_lora_name",
            return_value="Stickfigures-000005.safetensors",
        ):
            items = autopilot_svc._build_image_batch_items(project, options)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["template_id"], "txt2img_sdxl_stickman_lora")
        self.assertEqual(items[0]["lora_name"], "Stickfigures-000005.safetensors")

    def test_build_image_batch_items_blocks_stickman_for_named_executive_news(self) -> None:
        options = autopilot_svc.default_options()
        db.update_project(
            self.project["id"],
            sentences=["Jensen Huang joined the Nvidia China delegation after a Trump request."],
            visual_source_mode="comfyui_auto",
        )
        project = db.get_project(self.project["id"])
        self.assertIsNotNone(project)
        assert project is not None

        with patch(
            "app.services.autopilot.suggest_image_prompt_batch",
            return_value=[
                {
                    "sentence_idx": 0,
                    "sentence": "Jensen Huang joined the Nvidia China delegation after a Trump request.",
                    "positive_prompt": "Flipchartvisu, Stick figure, Jensen Huang, Nvidia, Trump, business delegation",
                    "negative_prompt": "",
                    "sentence_hash": "h1",
                    "template_id": "txt2img_sdxl_stickman_lora",
                    "visual_brief": {"domain": "tech"},
                    "visual_plan": {
                        "domain": "tech",
                        "sub_strategy": "semiconductor_business_news",
                        "lora_policy": "none",
                    },
                },
            ],
        ), patch(
            "app.services.autopilot._find_stickfigures_lora_name",
            return_value="Stickfigures-000005.safetensors",
        ):
            items = autopilot_svc._build_image_batch_items(project, options)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["template_id"], "txt2img_sdxl_basic")
        self.assertEqual(items[0]["lora_name"], "")
        self.assertEqual(items[0]["lora_strength"], 0.0)
        self.assertNotIn("Flipchartvisu", items[0]["positive_prompt"])
        self.assertNotIn("Stick figure", items[0]["positive_prompt"])

    def test_auto_image_count_matches_sentence_count(self) -> None:
        options = autopilot_svc.default_options()
        self.assertEqual(autopilot_svc._resolve_image_count(options, 9), 9)
        self.assertEqual(autopilot_svc._resolve_image_count(options, 40), 24)
