import os
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app
from app.workers import image_worker


class ImageWorkerTests(unittest.TestCase):
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

    def create_project(self, title: str = "image-worker-test") -> str:
        response = self.client.post("/api/projects", data={"title": title})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def mark_body_image_running(self, project_id: str) -> None:
        updated = db.update_project(
            project_id,
            body_image_state="running",
            body_image_job_id=f"test-job-{uuid4().hex}",
            body_image_started_at="2026-05-04T00:00:00+00:00",
            body_image_heartbeat_at="2026-05-04T00:00:00+00:00",
        )
        self.assertIsNotNone(updated)

    def test_claim_next_queued_body_image_marks_running(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, body_image_state="queued")
        self.mark_body_image_running(project_id)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "running")
        self.assertTrue(project["body_image_job_id"])

    def test_enqueue_comfyui_job_persists_options(self) -> None:
        project_id = self.create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/job",
            json={
                "checkpoint": "model.safetensors",
                "positive_prompt": "golden sunrise over city",
                "negative_prompt": "text, watermark",
                "sentence_idx": 1,
                "prompt": "scene prompt",
            },
        )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "queued")
        self.assertEqual(project["body_image_phase"], "queued")
        self.assertEqual(project["body_image_options"]["sentence_idx"], 1)

    def test_build_repair_suggestion_adds_controlnet_and_lora_policy_hints(self) -> None:
        suggestion = image_worker._build_repair_suggestion(
            {
                "positive_prompt": "generic diagram",
                "negative_prompt": "text, watermark",
                "prompt_g": "generic diagram",
                "prompt_l": "simple flat explainer illustration",
                "control_image": "C:/control/depth.png",
                "lora_name": "Stickfigures-000005.safetensors",
                "visual_brief": {
                    "mode": "keyword_image",
                    "main_subject": "simple centered explainer icon composition",
                    "action": "generic diagram",
                    "primary_prop": "central icon",
                    "secondary_prop": "",
                    "scene": "plain background",
                    "emotion": "clear and direct",
                    "must_show": ["server stack"],
                    "avoid": [],
                    "rationale": "style_preset=simple_diagram",
                },
            },
            issue_codes=["RAW_TEXT_VISUAL_TARGET"],
            attempt=1,
        )
        self.assertIn("follow control composition strictly", suggestion["repaired_prompt_g"])
        self.assertIn("preserve lora-driven character/style consistency", suggestion["repaired_prompt_l"])
        self.assertIn("layout drift", suggestion["repaired_negative_prompt"])
        self.assertIn("preserve_control_layout", suggestion["repair_reason"])
        self.assertIn("preserve_lora_style", suggestion["repair_reason"])

    def test_manual_art_directed_item_is_detected_for_repair_guard(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, body_image_options={"manual_art_directed": True})
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertTrue(image_worker._is_manual_art_directed_item(project, {"positive_prompt": "leaf film"}))
        self.assertTrue(
            image_worker._is_manual_art_directed_item(
                project,
                {"template_key": "manual_article_editorial"},
            )
        )

    def test_build_regenerated_prompt_item_switches_visual_mode_and_prompts(self) -> None:
        project_id = self.create_project()
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        db.update_project(
            project_id,
            title="quantum finance article",
            compiled_script="앞으로 어떤 방향으로 기술 개발과 투자가 이루어질지 귀추가 주목됩니다.",
            sentences=["앞으로 어떤 방향으로 기술 개발과 투자가 이루어질지 귀추가 주목됩니다."],
        )
        manifest_path = db.project_dir(project_id) / "image_prompts_manifest.json"
        manifest_path.write_text(
            """
            {
              "prompts": [
                {
                  "sentence_idx": 0,
                  "visual_plan": {
                    "sentence_idx": 0,
                    "sentence": "앞으로 어떤 방향으로 기술 개발과 투자가 이루어질지 귀추가 주목됩니다.",
                    "core_meaning": "future direction is under attention",
                    "primary_keywords": ["future direction", "investment outlook"],
                    "secondary_keywords": [],
                    "visual_metaphor": "forward direction concept",
                    "subject_modes": ["environment", "object_metaphor"],
                    "must_show": ["future direction marker", "investment outlook line"],
                    "may_show": [],
                    "avoid": [],
                    "prompt_hint": "medium wide shot",
                    "vocab_refs": [],
                    "domain": "essay",
                    "source": "fallback",
                    "visual_mode": "symbolic_concept",
                    "semantic_anchor_type": "future_outlook",
                    "semantic_anchor_tokens": ["future direction marker", "investment outlook line"]
                  }
                }
              ]
            }
            """,
            encoding="utf-8",
        )
        project = db.update_project(project_id, body_image_options={"image_prompts_manifest_path": str(manifest_path)})
        self.assertIsNotNone(project)
        assert project is not None
        with patch(
            "app.workers.image_worker.suggest_image_prompt",
            return_value={
                "positive_prompt": "regenerated roadmap explainer",
                "negative_prompt": "text, watermark",
                "prompt_g": "regenerated roadmap explainer",
                "prompt_l": "clean roadmap explainer background",
                "visual_brief": {"visual_mode": "simple_explainer", "semantic_anchor_type": "future_outlook"},
                "visual_plan": {"visual_mode": "simple_explainer", "semantic_anchor_type": "future_outlook"},
                "template_id": "txt2img_sdxl_basic",
                "generation_profile": "sdxl_fast",
                "steps": 20,
                "cfg": 5.5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        ):
            regenerated = image_worker._build_regenerated_prompt_item(
                project,
                {
                    "positive_prompt": "old prompt",
                    "negative_prompt": "text, watermark",
                    "template_id": "txt2img_sdxl_basic",
                },
                sentence_idx=0,
            )
        self.assertIsNotNone(regenerated)
        assert regenerated is not None
        self.assertEqual(regenerated["positive_prompt"], "regenerated roadmap explainer")
        self.assertEqual(regenerated["visual_plan"]["visual_mode"], "simple_explainer")
        self.assertEqual(regenerated["visual_plan"]["scene_anchor"], "plain warm roadmap explainer background")

    def test_build_fallback_downgraded_prompt_item_uses_safe_mode(self) -> None:
        project_id = self.create_project()
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        db.update_project(
            project_id,
            title="quantum finance article",
            compiled_script="?욎쑝濡??대뼡 諛⑺뼢?쇰줈 湲곗닠 媛쒕컻怨??ъ옄媛 ?대（?댁쭏吏 洹異붽? 二쇰ぉ?⑸땲??",
            sentences=["?욎쑝濡??대뼡 諛⑺뼢?쇰줈 湲곗닠 媛쒕컻怨??ъ옄媛 ?대（?댁쭏吏 洹異붽? 二쇰ぉ?⑸땲??"],
        )
        manifest_path = db.project_dir(project_id) / "image_prompts_manifest.json"
        manifest_path.write_text(
            """
            {
              "prompts": [
                {
                  "sentence_idx": 0,
                  "visual_plan": {
                    "sentence_idx": 0,
                    "sentence": "?욎쑝濡??대뼡 諛⑺뼢?쇰줈 湲곗닠 媛쒕컻怨??ъ옄媛 ?대（?댁쭏吏 洹異붽? 二쇰ぉ?⑸땲??",
                    "core_meaning": "future direction is under attention",
                    "primary_keywords": ["future direction", "investment outlook"],
                    "secondary_keywords": [],
                    "visual_metaphor": "forward direction concept",
                    "subject_modes": ["environment", "object_metaphor"],
                    "must_show": ["future direction marker", "investment outlook line"],
                    "may_show": [],
                    "avoid": [],
                    "prompt_hint": "medium wide shot",
                    "vocab_refs": [],
                    "domain": "essay",
                    "source": "fallback",
                    "visual_mode": "editorial_scene",
                    "semantic_anchor_type": "future_outlook",
                    "semantic_anchor_tokens": ["future direction marker", "investment outlook line"]
                  }
                }
              ]
            }
            """,
            encoding="utf-8",
        )
        project = db.update_project(project_id, body_image_options={"image_prompts_manifest_path": str(manifest_path)})
        self.assertIsNotNone(project)
        assert project is not None
        with patch(
            "app.workers.image_worker.suggest_image_prompt",
            return_value={
                "positive_prompt": "fallback roadmap explainer",
                "negative_prompt": "text, watermark",
                "prompt_g": "fallback roadmap explainer",
                "prompt_l": "clean roadmap explainer background",
                "visual_brief": {"visual_mode": "simple_explainer", "semantic_anchor_type": "future_outlook"},
                "visual_plan": {"visual_mode": "simple_explainer", "semantic_anchor_type": "future_outlook"},
                "template_id": "txt2img_sdxl_basic",
                "generation_profile": "sdxl_fast",
                "steps": 20,
                "cfg": 5.5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        ):
            downgraded = image_worker._build_fallback_downgraded_prompt_item(
                project,
                {
                    "positive_prompt": "old prompt",
                    "negative_prompt": "text, watermark",
                    "template_id": "txt2img_sdxl_basic",
                },
                sentence_idx=0,
            )
        self.assertIsNotNone(downgraded)
        assert downgraded is not None
        self.assertEqual(downgraded["positive_prompt"], "fallback roadmap explainer")
        self.assertEqual(downgraded["visual_plan"]["visual_mode"], "simple_explainer")
        self.assertEqual(downgraded["visual_plan"]["scene_anchor"], "plain warm roadmap explainer background")
        self.assertTrue(downgraded["_fallback_downgraded"])

    def test_image_worker_runs_submit_and_import_flow(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            sentences=["첫 문장입니다."],
            regional_sentences=[{"idx": 0, "text": "첫 문장입니다.", "region": "intro"}],
            body_image_options={
                "template_id": "txt2img_sdxl_basic",
                "checkpoint": "model.safetensors",
                "positive_prompt": "golden sunrise over city",
                "negative_prompt": "",
                "width": 1024,
                "height": 576,
                "seed": 7,
                "filename_prefix": "scene001",
                "client_id": "newauto",
                "sentence_idx": 2,
                "prompt": "scene prompt",
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.submit_template",
            return_value="prompt-123",
        ), patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            return_value={"prompt-123": {"outputs": {}}},
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            return_value=[object()],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            def fake_import(*args: object, **kwargs: object) -> tuple[object, str, str]:
                updated = db.update_project(
                    project_id,
                    body_image_mappings=[
                        {
                            "sentence_idx": 0,
                            "path": "image_0001.png",
                            "prompt": "scene prompt",
                        }
                    ],
                )
                assert updated is not None
                return updated, "image_0001.png", "C:/temp/image_0001.png"

            mocked_import.side_effect = fake_import
            image_worker._run_job_with_heartbeat(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "done")
        self.assertEqual(project["body_image_phase"], "done")
        self.assertIsNotNone(project["scene_plan"])
        self.assertIsNotNone(project["render_plan"])

    def test_image_worker_runs_batch_flow(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_basic",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "scene one",
                        "negative_prompt": "",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "scene one",
                    },
                    {
                        "template_id": "txt2img_sdxl_basic",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "scene two",
                        "negative_prompt": "",
                        "width": 1024,
                        "height": 576,
                        "seed": 12,
                        "filename_prefix": "scene_002",
                        "client_id": "newauto",
                        "sentence_idx": 1,
                        "prompt": "scene two",
                        "lora_name": "Stickfigures-000005.safetensors",
                        "lora_strength": 0.75,
                    },
                ]
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.submit_template",
            side_effect=["prompt-1", "prompt-2"],
        ), patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            side_effect=[{"prompt-1": {"outputs": {}}}, {"prompt-2": {"outputs": {}}}],
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            side_effect=[[object()], [object()]],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            mocked_import.side_effect = [
                (db.get_project(project_id), "image_0001.png", "C:/temp/image_0001.png"),
                (db.get_project(project_id), "image_0002.png", "C:/temp/image_0002.png"),
            ]
            image_worker._run_job_with_heartbeat(project_id)

        self.assertEqual(mocked_import.call_count, 2)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "done")

    def test_image_worker_passes_style_reference_placeholders(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_ipadapter_style",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "scene one",
                        "negative_prompt": "",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "scene one",
                        "style_reference_image": "C:/style/ref.png",
                        "style_reference_strength": 0.77,
                    }
                ]
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.submit_template",
            return_value="prompt-1",
        ) as mocked_submit, patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            return_value={"prompt-1": {"outputs": {}}},
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            return_value=[object()],
        ), patch(
            "app.workers.image_worker.import_history_image",
            return_value=(db.get_project(project_id), "image_0001.png", "C:/temp/image_0001.png"),
        ):
            image_worker._run_job_with_heartbeat(project_id)

        placeholders = mocked_submit.call_args.kwargs["placeholders"]
        self.assertEqual(placeholders["__STYLE_REFERENCE_IMAGE__"], "C:/style/ref.png")
        self.assertEqual(placeholders["__STYLE_REFERENCE_STRENGTH__"], 0.77)

    def test_image_worker_passes_controlnet_placeholders(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_controlnet_depth",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "scene one",
                        "negative_prompt": "",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "scene one",
                        "control_image": "C:/control/ref.png",
                        "control_strength": 0.82,
                    }
                ]
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.submit_template",
            return_value="prompt-1",
        ) as mocked_submit, patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            return_value={"prompt-1": {"outputs": {}}},
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            return_value=[object()],
        ), patch(
            "app.workers.image_worker.import_history_image",
            return_value=(db.get_project(project_id), "image_0001.png", "C:/temp/image_0001.png"),
        ):
            image_worker._run_job_with_heartbeat(project_id)

        placeholders = mocked_submit.call_args.kwargs["placeholders"]
        self.assertEqual(placeholders["__CONTROL_IMAGE__"], "C:/control/ref.png")
        self.assertEqual(placeholders["__CONTROL_STRENGTH__"], 0.82)

    def test_image_worker_surfaces_retry_recommendation_in_log(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_basic",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "scene one",
                        "negative_prompt": "",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "scene one",
                    }
                ]
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.submit_template",
            return_value="prompt-1",
        ), patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            return_value={"prompt-1": {"outputs": {}}},
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            return_value=[object()],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            def fake_import(*args: object, **kwargs: object) -> tuple[object, str, str]:
                updated = db.update_project(
                    project_id,
                    body_image_options={
                        "candidate_reviews": {
                            "0": {
                                "best_path": "image_0001.png",
                                "best_score": 0.41,
                                "score_version": "candidate_score_v2",
                                "retry_recommended": True,
                                "retry_reason": "low_candidate_score",
                                "selection_reason": "auto_score_v2:0.41:retry_recommended",
                            }
                        }
                    },
                )
                assert updated is not None
                return updated, "image_0001.png", "C:/temp/image_0001.png"

            mocked_import.side_effect = fake_import
            image_worker._run_job_with_heartbeat(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertIn("recommends retry", project["body_image_last_log"])

    def test_image_worker_can_skip_auto_plan_refresh(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            sentences=["첫 문장입니다."],
            regional_sentences=[{"idx": 0, "text": "첫 문장입니다.", "region": "intro"}],
            body_image_options={
                "template_id": "txt2img_sdxl_basic",
                "checkpoint": "model.safetensors",
                "positive_prompt": "golden sunrise over city",
                "negative_prompt": "",
                "width": 1024,
                "height": 576,
                "seed": 7,
                "filename_prefix": "scene001",
                "client_id": "newauto",
                "sentence_idx": 0,
                "prompt": "scene prompt",
                "auto_build_plans_after_image": False,
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.submit_template",
            return_value="prompt-123",
        ), patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            return_value={"prompt-123": {"outputs": {}}},
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            return_value=[object()],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            def fake_import(*args: object, **kwargs: object) -> tuple[object, str, str]:
                updated = db.update_project(
                    project_id,
                    body_image_mappings=[
                        {
                            "sentence_idx": 0,
                            "path": "image_0001.png",
                            "prompt": "scene prompt",
                        }
                    ],
                )
                assert updated is not None
                return updated, "image_0001.png", "C:/temp/image_0001.png"

            mocked_import.side_effect = fake_import
            image_worker._run_job_with_heartbeat(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "done")
        self.assertIsNone(project["scene_plan"])
        self.assertIsNone(project["render_plan"])

    def test_image_worker_runs_single_repair_retry_when_candidate_review_requests_it(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_basic",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "generic diagram",
                        "negative_prompt": "text, watermark",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "generic diagram",
                        "repair_retry_limit": 1,
                        "visual_brief": {
                            "mode": "keyword_image",
                            "main_subject": "simple centered explainer icon composition",
                            "action": "generic diagram",
                            "primary_prop": "central icon",
                            "secondary_prop": "",
                            "scene": "plain background",
                            "emotion": "clear and direct",
                            "must_show": ["server stack"],
                            "avoid": [],
                            "rationale": "style_preset=simple_diagram",
                        },
                    }
                ]
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.gpu_guard.get_status",
            return_value={"locked": True, "owner": f"image-job:{project_id}", "resource": "comfyui", "expires_at": ""},
        ), patch(
            "app.workers.image_worker.submit_template",
            side_effect=["prompt-1", "prompt-2"],
        ) as mocked_submit, patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            side_effect=[{"prompt-1": {"outputs": {}}}, {"prompt-2": {"outputs": {}}}],
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            side_effect=[[object()], [object()]],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            def fake_import(*args: object, **kwargs: object) -> tuple[object, str, str]:
                prompt_id = str(kwargs["prompt_id"])
                if prompt_id == "prompt-1":
                    updated = db.update_project(
                        project_id,
                        body_image_options={
                            "candidate_reviews": {
                                "0": {
                                    "best_path": "image_0001.png",
                                    "best_score": 0.41,
                                    "score_version": "candidate_score_v2",
                                    "retry_recommended": True,
                                    "retry_reason": "low_candidate_score",
                                    "selection_reason": "auto_score_v2:0.41:retry_recommended",
                                    "vision_qa_issue_codes": ["RAW_TEXT_VISUAL_TARGET"],
                                }
                            }
                        },
                    )
                else:
                    updated = db.update_project(
                        project_id,
                        body_image_options={
                            "candidate_reviews": {
                                "0": {
                                    "best_path": "image_0002.png",
                                    "best_score": 0.78,
                                    "score_version": "candidate_score_v2",
                                    "retry_recommended": False,
                                    "retry_reason": "",
                                    "selection_reason": "auto_score_v2:0.78:accepted",
                                    "vision_qa_issue_codes": [],
                                }
                            }
                        },
                    )
                assert updated is not None
                return updated, "image_0001.png", "C:/temp/image_0001.png"

            mocked_import.side_effect = fake_import
            image_worker._run_job_with_heartbeat(project_id)

        self.assertEqual(mocked_submit.call_count, 2)
        second_placeholders = mocked_submit.call_args_list[1].kwargs["placeholders"]
        self.assertIn("server stack", second_placeholders["__POSITIVE_PROMPT__"])
        self.assertIn("server stack", second_placeholders["__POSITIVE_PROMPT_G__"])
        self.assertNotIn("server stack", second_placeholders["__POSITIVE_PROMPT_L__"])
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertIn("Repair retry queued", project["body_image_last_log"])
        candidate_reviews = project["body_image_options"].get("candidate_reviews", {})
        self.assertIsInstance(candidate_reviews, dict)
        assert isinstance(candidate_reviews, dict)
        review = candidate_reviews.get("0")
        self.assertIsInstance(review, dict)
        assert isinstance(review, dict)
        self.assertTrue(review.get("repair_attempted"))
        self.assertEqual(review.get("repair_reason"), "must_show_reinforced")
        self.assertEqual(review.get("repair_issue_codes"), ["RAW_TEXT_VISUAL_TARGET"])

    def test_image_worker_runs_scene_plan_regeneration_before_prompt_repair(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            title="quantum finance article",
            compiled_script="앞으로 어떤 방향으로 기술 개발과 투자가 이루어질지 귀추가 주목됩니다.",
            sentences=["앞으로 어떤 방향으로 기술 개발과 투자가 이루어질지 귀추가 주목됩니다."],
        )
        manifest_path = db.project_dir(project_id) / "image_prompts_manifest.json"
        manifest_path.write_text(
            """
            {
              "prompts": [
                {
                  "sentence_idx": 0,
                  "visual_plan": {
                    "sentence_idx": 0,
                    "sentence": "앞으로 어떤 방향으로 기술 개발과 투자가 이루어질지 귀추가 주목됩니다.",
                    "core_meaning": "future direction is under attention",
                    "primary_keywords": ["future direction", "investment outlook"],
                    "secondary_keywords": [],
                    "visual_metaphor": "forward direction concept",
                    "subject_modes": ["environment", "object_metaphor"],
                    "must_show": ["future direction marker", "investment outlook line"],
                    "may_show": [],
                    "avoid": [],
                    "prompt_hint": "medium wide shot",
                    "vocab_refs": [],
                    "domain": "essay",
                    "source": "fallback",
                    "visual_mode": "symbolic_concept",
                    "semantic_anchor_type": "future_outlook",
                    "semantic_anchor_tokens": ["future direction marker", "investment outlook line"]
                  }
                }
              ]
            }
            """,
            encoding="utf-8",
        )
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "image_prompts_manifest_path": str(manifest_path),
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_basic",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "generic diagram",
                        "negative_prompt": "text, watermark",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "generic diagram",
                        "repair_retry_limit": 1,
                        "plan_retry_limit": 1,
                        "visual_brief": {
                            "mode": "keyword_image",
                            "main_subject": "editorial symbolic concept scene",
                            "action": "generic diagram",
                            "primary_prop": "future direction marker",
                            "secondary_prop": "",
                            "scene": "plain background",
                            "emotion": "clear and direct",
                            "must_show": ["future direction marker"],
                            "avoid": [],
                            "rationale": "template=essay_symbolic; domain=essay",
                        },
                    }
                ],
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.gpu_guard.get_status",
            return_value={"locked": True, "owner": f"image-job:{project_id}", "resource": "comfyui", "expires_at": ""},
        ), patch(
            "app.workers.image_worker.submit_template",
            side_effect=["prompt-1", "prompt-2"],
        ) as mocked_submit, patch(
            "app.workers.image_worker.suggest_image_prompt",
            return_value={
                "positive_prompt": "regenerated roadmap explainer",
                "negative_prompt": "text, watermark",
                "prompt_g": "regenerated roadmap explainer",
                "prompt_l": "clean roadmap explainer background",
                "visual_brief": {"visual_mode": "simple_explainer", "semantic_anchor_type": "future_outlook"},
                "visual_plan": {"visual_mode": "simple_explainer", "semantic_anchor_type": "future_outlook"},
                "template_id": "txt2img_sdxl_basic",
                "generation_profile": "sdxl_fast",
                "steps": 20,
                "cfg": 5.5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        ), patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            side_effect=[{"prompt-1": {"outputs": {}}}, {"prompt-2": {"outputs": {}}}],
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            side_effect=[[object()], [object()]],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            def fake_import(*args: object, **kwargs: object) -> tuple[object, str, str]:
                prompt_id = str(kwargs["prompt_id"])
                if prompt_id == "prompt-1":
                    updated = db.update_project(
                        project_id,
                        body_image_options={
                            "image_prompts_manifest_path": str(manifest_path),
                            "candidate_reviews": {
                                "0": {
                                    "best_path": "image_0001.png",
                                    "best_score": 0.41,
                                    "score_version": "candidate_score_v2",
                                    "retry_recommended": True,
                                    "retry_reason": "low_candidate_score",
                                    "selection_reason": "auto_score_v2:0.41:retry_recommended",
                                    "vision_qa_issue_codes": ["RAW_TEXT_VISUAL_TARGET"],
                                }
                            },
                        },
                    )
                else:
                    updated = db.update_project(
                        project_id,
                        body_image_options={
                            "image_prompts_manifest_path": str(manifest_path),
                            "candidate_reviews": {
                                "0": {
                                    "best_path": "image_0002.png",
                                    "best_score": 0.79,
                                    "score_version": "candidate_score_v2",
                                    "retry_recommended": False,
                                    "retry_reason": "",
                                    "selection_reason": "auto_score_v2:0.79",
                                    "vision_qa_issue_codes": [],
                                }
                            },
                        },
                    )
                    self.assertIsInstance(kwargs.get("prompt_item_override"), dict)
                assert updated is not None
                return updated, "image_0001.png", "C:/temp/image_0001.png"

            mocked_import.side_effect = fake_import
            image_worker._run_job_with_heartbeat(project_id)

        self.assertEqual(mocked_submit.call_count, 2)
        second_placeholders = mocked_submit.call_args_list[1].kwargs["placeholders"]
        self.assertIn("regenerated roadmap explainer", second_placeholders["__POSITIVE_PROMPT__"])
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertIn("Scene-plan regeneration queued", project["body_image_last_log"])

    def test_image_worker_marks_operator_review_after_fallback_downgrade_still_fails(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            title="quantum finance article",
            compiled_script="?욎쑝濡??대뼡 諛⑺뼢?쇰줈 湲곗닠 媛쒕컻怨??ъ옄媛 ?대（?댁쭏吏 洹異붽? 二쇰ぉ?⑸땲??",
            sentences=["?욎쑝濡??대뼡 諛⑺뼢?쇰줈 湲곗닠 媛쒕컻怨??ъ옄媛 ?대（?댁쭏吏 洹異붽? 二쇰ぉ?⑸땲??"],
        )
        manifest_path = db.project_dir(project_id) / "image_prompts_manifest.json"
        manifest_path.write_text(
            """
            {
              "prompts": [
                {
                  "sentence_idx": 0,
                  "visual_plan": {
                    "sentence_idx": 0,
                    "sentence": "?욎쑝濡??대뼡 諛⑺뼢?쇰줈 湲곗닠 媛쒕컻怨??ъ옄媛 ?대（?댁쭏吏 洹異붽? 二쇰ぉ?⑸땲??",
                    "core_meaning": "future direction is under attention",
                    "primary_keywords": ["future direction", "investment outlook"],
                    "secondary_keywords": [],
                    "visual_metaphor": "forward direction concept",
                    "subject_modes": ["environment", "object_metaphor"],
                    "must_show": ["future direction marker", "investment outlook line"],
                    "may_show": [],
                    "avoid": [],
                    "prompt_hint": "medium wide shot",
                    "vocab_refs": [],
                    "domain": "essay",
                    "source": "fallback",
                    "visual_mode": "symbolic_concept",
                    "semantic_anchor_type": "future_outlook",
                    "semantic_anchor_tokens": ["future direction marker", "investment outlook line"]
                  }
                }
              ]
            }
            """,
            encoding="utf-8",
        )
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "image_prompts_manifest_path": str(manifest_path),
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_basic",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "generic diagram",
                        "negative_prompt": "text, watermark",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "generic diagram",
                        "repair_retry_limit": 1,
                        "plan_retry_limit": 0,
                        "fallback_downgrade_limit": 1,
                        "visual_brief": {
                            "mode": "keyword_image",
                            "main_subject": "editorial symbolic concept scene",
                            "action": "generic diagram",
                            "primary_prop": "future direction marker",
                            "secondary_prop": "",
                            "scene": "plain background",
                            "emotion": "clear and direct",
                            "must_show": ["future direction marker"],
                            "avoid": [],
                            "rationale": "template=essay_symbolic; domain=essay",
                        },
                    }
                ],
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.gpu_guard.get_status",
            return_value={"locked": True, "owner": f"image-job:{project_id}", "resource": "comfyui", "expires_at": ""},
        ), patch(
            "app.workers.image_worker.submit_template",
            side_effect=["prompt-1", "prompt-2"],
        ) as mocked_submit, patch(
            "app.workers.image_worker.suggest_image_prompt",
            return_value={
                "positive_prompt": "fallback roadmap explainer",
                "negative_prompt": "text, watermark",
                "prompt_g": "fallback roadmap explainer",
                "prompt_l": "clean roadmap explainer background",
                "visual_brief": {"visual_mode": "simple_explainer", "semantic_anchor_type": "future_outlook"},
                "visual_plan": {"visual_mode": "simple_explainer", "semantic_anchor_type": "future_outlook"},
                "template_id": "txt2img_sdxl_basic",
                "generation_profile": "sdxl_fast",
                "steps": 20,
                "cfg": 5.5,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        ), patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            side_effect=[{"prompt-1": {"outputs": {}}}, {"prompt-2": {"outputs": {}}}],
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            side_effect=[[object()], [object()]],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            def fake_import(*args: object, **kwargs: object) -> tuple[object, str, str]:
                prompt_id = str(kwargs["prompt_id"])
                if prompt_id == "prompt-1":
                    updated = db.update_project(
                        project_id,
                        body_image_options={
                            "image_prompts_manifest_path": str(manifest_path),
                            "candidate_reviews": {
                                "0": {
                                    "best_path": "image_0001.png",
                                    "best_score": 0.41,
                                    "score_version": "candidate_score_v2",
                                    "retry_recommended": True,
                                    "retry_reason": "low_candidate_score",
                                    "selection_reason": "auto_score_v2:0.41:retry_recommended",
                                    "vision_qa_issue_codes": ["RAW_TEXT_VISUAL_TARGET"],
                                }
                            },
                        },
                    )
                else:
                    updated = db.update_project(
                        project_id,
                        body_image_options={
                            "image_prompts_manifest_path": str(manifest_path),
                            "candidate_reviews": {
                                "0": {
                                    "best_path": "image_0002.png",
                                    "best_score": 0.43,
                                    "score_version": "candidate_score_v2",
                                    "retry_recommended": True,
                                    "retry_reason": "low_candidate_score",
                                    "selection_reason": "auto_score_v2:0.43:retry_recommended",
                                    "vision_qa_issue_codes": ["RAW_TEXT_VISUAL_TARGET"],
                                }
                            },
                        },
                    )
                    self.assertIsInstance(kwargs.get("prompt_item_override"), dict)
                assert updated is not None
                return updated, "image_0001.png", "C:/temp/image_0001.png"

            mocked_import.side_effect = fake_import
            image_worker._run_job_with_heartbeat(project_id)

        self.assertEqual(mocked_submit.call_count, 2)
        second_placeholders = mocked_submit.call_args_list[1].kwargs["placeholders"]
        self.assertIn("fallback roadmap explainer", second_placeholders["__POSITIVE_PROMPT__"])
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_phase"], "done_with_operator_warning")
        self.assertIn("Operator review required", project["body_image_last_log"])
        candidate_reviews = project["body_image_options"].get("candidate_reviews", {})
        self.assertIsInstance(candidate_reviews, dict)
        assert isinstance(candidate_reviews, dict)
        review = candidate_reviews.get("0")
        self.assertIsInstance(review, dict)
        assert isinstance(review, dict)
        self.assertTrue(review.get("fallback_downgrade_applied"))
        self.assertEqual(
            review.get("fallback_downgrade_reason"),
            "fallback_downgrade:future_outlook:symbolic_concept->simple_explainer",
        )
        self.assertTrue(review.get("operator_intervention_required"))
        self.assertEqual(review.get("operator_intervention_reason"), "operator_review_required:low_candidate_score")
        self.assertEqual(review.get("repair_reason"), "retry_limit_reached:low_candidate_score")

    def test_image_worker_skips_repair_retry_for_heavy_style_path(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_ipadapter_style",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "generic diagram",
                        "negative_prompt": "text, watermark",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "generic diagram",
                        "repair_retry_limit": 1,
                        "visual_brief": {
                            "mode": "keyword_image",
                            "main_subject": "simple centered explainer icon composition",
                            "action": "generic diagram",
                            "primary_prop": "central icon",
                            "secondary_prop": "",
                            "scene": "plain background",
                            "emotion": "clear and direct",
                            "must_show": ["server stack"],
                            "avoid": [],
                            "rationale": "style_preset=simple_diagram",
                        },
                        "style_reference_image": "C:/style/ref.png",
                    }
                ]
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.submit_template",
            return_value="prompt-1",
        ) as mocked_submit, patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            return_value={"prompt-1": {"outputs": {}}},
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            return_value=[object()],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            def fake_import(*args: object, **kwargs: object) -> tuple[object, str, str]:
                updated = db.update_project(
                    project_id,
                    body_image_options={
                        "candidate_reviews": {
                            "0": {
                                "best_path": "image_0001.png",
                                "best_score": 0.41,
                                "score_version": "candidate_score_v2",
                                "retry_recommended": True,
                                "retry_reason": "low_candidate_score",
                                "selection_reason": "auto_score_v2:0.41:retry_recommended",
                                "vision_qa_issue_codes": ["RAW_TEXT_VISUAL_TARGET"],
                            }
                        }
                    },
                )
                assert updated is not None
                return updated, "image_0001.png", "C:/temp/image_0001.png"

            mocked_import.side_effect = fake_import
            image_worker._run_job_with_heartbeat(project_id)

        self.assertEqual(mocked_submit.call_count, 1)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertIn("Skipped repair retry", project["body_image_last_log"])
        candidate_reviews = project["body_image_options"].get("candidate_reviews", {})
        self.assertIsInstance(candidate_reviews, dict)
        assert isinstance(candidate_reviews, dict)
        review = candidate_reviews.get("0")
        self.assertIsInstance(review, dict)
        assert isinstance(review, dict)
        self.assertFalse(review.get("repair_attempted"))
        self.assertEqual(review.get("repair_reason"), "repair_retry_skipped_heavy_path")
        self.assertEqual(review.get("repair_issue_codes"), ["RAW_TEXT_VISUAL_TARGET"])
        self.assertEqual(review.get("suggested_repair_reason"), "must_show_reinforced, preserve_style_reference")
        self.assertIn("generic diagram", str(review.get("suggested_positive_prompt")))
        self.assertIn("server stack", str(review.get("suggested_positive_prompt")))
        self.assertIn("server stack", str(review.get("suggested_prompt_g")))
        self.assertEqual(review.get("current_negative_prompt"), "text, watermark")

    def test_image_worker_marks_retry_limit_exit_in_candidate_review(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_basic",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "generic diagram",
                        "negative_prompt": "text, watermark",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "generic diagram",
                        "repair_retry_limit": 0,
                        "visual_brief": {
                            "mode": "keyword_image",
                            "main_subject": "simple centered explainer icon composition",
                            "action": "generic diagram",
                            "primary_prop": "central icon",
                            "secondary_prop": "",
                            "scene": "plain background",
                            "emotion": "clear and direct",
                            "must_show": ["server stack"],
                            "avoid": [],
                            "rationale": "style_preset=simple_diagram",
                        },
                    }
                ]
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.submit_template",
            return_value="prompt-1",
        ) as mocked_submit, patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            return_value={"prompt-1": {"outputs": {}}},
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            return_value=[object()],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            def fake_import(*args: object, **kwargs: object) -> tuple[object, str, str]:
                updated = db.update_project(
                    project_id,
                    body_image_options={
                        "candidate_reviews": {
                            "0": {
                                "best_path": "image_0001.png",
                                "best_score": 0.39,
                                "score_version": "candidate_score_v2",
                                "retry_recommended": True,
                                "retry_reason": "low_candidate_score",
                                "selection_reason": "auto_score_v2:0.39:retry_recommended",
                                "vision_qa_issue_codes": ["RAW_TEXT_VISUAL_TARGET"],
                            }
                        }
                    },
                )
                assert updated is not None
                return updated, "image_0001.png", "C:/temp/image_0001.png"

            mocked_import.side_effect = fake_import
            image_worker._run_job_with_heartbeat(project_id)

        self.assertEqual(mocked_submit.call_count, 1)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        candidate_reviews = project["body_image_options"].get("candidate_reviews", {})
        self.assertIsInstance(candidate_reviews, dict)
        assert isinstance(candidate_reviews, dict)
        review = candidate_reviews.get("0")
        self.assertIsInstance(review, dict)
        assert isinstance(review, dict)
        self.assertFalse(review.get("repair_attempted"))
        self.assertEqual(review.get("repair_reason"), "retry_limit_reached:low_candidate_score")
        self.assertEqual(review.get("repair_issue_codes"), ["RAW_TEXT_VISUAL_TARGET"])
        self.assertEqual(review.get("suggested_repair_reason"), "must_show_reinforced")
        self.assertIn("server stack", str(review.get("suggested_prompt_g")))
        self.assertEqual(review.get("current_negative_prompt"), "text, watermark")

    def test_image_worker_stores_repair_suggestion_when_gpu_busy(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "batch_items": [
                    {
                        "template_id": "txt2img_sdxl_basic",
                        "checkpoint": "model.safetensors",
                        "positive_prompt": "generic diagram",
                        "negative_prompt": "text, watermark",
                        "width": 1024,
                        "height": 576,
                        "seed": 11,
                        "filename_prefix": "scene_001",
                        "client_id": "newauto",
                        "sentence_idx": 0,
                        "prompt": "generic diagram",
                        "repair_retry_limit": 1,
                        "visual_brief": {
                            "mode": "keyword_image",
                            "main_subject": "simple centered explainer icon composition",
                            "action": "generic diagram",
                            "primary_prop": "central icon",
                            "secondary_prop": "",
                            "scene": "plain background",
                            "emotion": "clear and direct",
                            "must_show": ["server stack"],
                            "avoid": [],
                            "rationale": "style_preset=simple_diagram",
                        },
                    }
                ]
            },
        )
        self.mark_body_image_running(project_id)

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.gpu_guard.get_status",
            return_value={"locked": True, "owner": "other-worker", "resource": "comfyui", "expires_at": ""},
        ), patch(
            "app.workers.image_worker.submit_template",
            return_value="prompt-1",
        ) as mocked_submit, patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            return_value={"prompt-1": {"outputs": {}}},
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            return_value=[object()],
        ), patch(
            "app.workers.image_worker.import_history_image"
        ) as mocked_import:
            def fake_import(*args: object, **kwargs: object) -> tuple[object, str, str]:
                updated = db.update_project(
                    project_id,
                    body_image_options={
                        "candidate_reviews": {
                            "0": {
                                "best_path": "image_0001.png",
                                "best_score": 0.41,
                                "score_version": "candidate_score_v2",
                                "retry_recommended": True,
                                "retry_reason": "low_candidate_score",
                                "selection_reason": "auto_score_v2:0.41:retry_recommended",
                                "vision_qa_issue_codes": ["RAW_TEXT_VISUAL_TARGET"],
                            }
                        }
                    },
                )
                assert updated is not None
                return updated, "image_0001.png", "C:/temp/image_0001.png"

            mocked_import.side_effect = fake_import
            image_worker._run_job_with_heartbeat(project_id)

        self.assertEqual(mocked_submit.call_count, 1)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        candidate_reviews = project["body_image_options"].get("candidate_reviews", {})
        self.assertIsInstance(candidate_reviews, dict)
        assert isinstance(candidate_reviews, dict)
        review = candidate_reviews.get("0")
        self.assertIsInstance(review, dict)
        assert isinstance(review, dict)
        self.assertFalse(review.get("repair_attempted"))
        self.assertEqual(review.get("repair_reason"), "repair_retry_skipped_gpu_busy")
        self.assertEqual(review.get("suggested_repair_reason"), "must_show_reinforced")
        self.assertIn("server stack", str(review.get("suggested_prompt_g")))
        self.assertEqual(review.get("current_negative_prompt"), "text, watermark")

    def test_image_worker_surfaces_comfyui_execution_error(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="queued",
            body_image_options={
                "template_id": "txt2img_sdxl_basic",
                "checkpoint": "model.safetensors",
                "positive_prompt": "scene one",
                "negative_prompt": "",
                "width": 1024,
                "height": 576,
                "seed": 11,
                "filename_prefix": "scene_001",
                "client_id": "newauto",
                "sentence_idx": 0,
                "prompt": "scene one",
            },
        )
        claimed = db.claim_next_queued_body_image()
        self.assertEqual(claimed, project_id)

        history_payload = {
            "prompt-1": {
                "status": {
                    "status_str": "error",
                    "messages": [
                        [
                            "execution_error",
                            {
                                "node_type": "KSampler",
                                "exception_message": "[Errno 22] Invalid argument\n",
                            },
                        ]
                    ],
                },
                "outputs": {},
            }
        }

        with patch("app.workers.image_worker.gpu_guard.acquire", return_value=True), patch(
            "app.workers.image_worker.submit_template",
            return_value="prompt-1",
        ), patch(
            "app.workers.image_worker.ComfyUIClient.get_history",
            return_value=history_payload,
        ), patch(
            "app.workers.image_worker.ComfyUIClient.extract_image_results",
            return_value=[],
        ):
            image_worker._run_job_with_heartbeat(project_id)

        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "error")
        self.assertIn("ComfyUI KSampler failed", project["body_image_error"])
