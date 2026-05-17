import base64
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar, cast
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app


def _tiny_png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn0l1sAAAAASUVORK5CYII="
    )


class ComfyUiRouteTests(unittest.TestCase):
    client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        db.init_db()
        cls.ollama_ready_patcher = patch("app.services.visual_planner._quick_ollama_ready", return_value=False)
        cls.ollama_ready_patcher.start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.ollama_ready_patcher.stop()

    def setUp(self) -> None:
        self.project_ids: list[str] = []

    def tearDown(self) -> None:
        for project_id in self.project_ids:
            project = db.get_project(project_id)
            if project is not None:
                self.client.delete(f"/api/projects/{project_id}")

    def create_project(self, title: str = "comfy-route-test") -> str:
        response = self.client.post("/api/projects", data={"title": title})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_render_comfyui_workflow_returns_rendered_payload(self) -> None:
        project_id = self.create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/workflow/render",
            json={
                "checkpoint": "model.safetensors",
                "positive_prompt": "golden sunrise over city",
                "negative_prompt": "text, watermark",
                "width": 1024,
                "height": 576,
                "seed": 123,
                "filename_prefix": "scene001",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["workflow"]
        self.assertEqual(payload["4"]["inputs"]["ckpt_name"], "model.safetensors")
        self.assertEqual(payload["3"]["inputs"]["steps"], 30)
        self.assertEqual(payload["3"]["inputs"]["sampler_name"], "dpmpp_2m")
        self.assertEqual(payload["3"]["inputs"]["scheduler"], "karras")
        self.assertEqual(payload["5"]["inputs"]["width"], 1024)
        self.assertEqual(payload["6"]["inputs"]["text_g"], "golden sunrise over city")
        self.assertEqual(payload["6"]["inputs"]["target_width"], 1024)
        self.assertEqual(payload["9"]["inputs"]["filename_prefix"], "scene001")

    def test_render_comfyui_workflow_uses_lora_template_when_requested(self) -> None:
        project_id = self.create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/workflow/render",
            json={
                "checkpoint": "model.safetensors",
                "positive_prompt": "stick figure hero",
                "negative_prompt": "text",
                "width": 1024,
                "height": 576,
                "seed": 123,
                "filename_prefix": "scene001",
                "lora_name": "stickfigures.safetensors",
                "lora_strength": 0.7,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["workflow"]
        self.assertEqual(payload["10"]["inputs"]["lora_name"], "stickfigures.safetensors")
        self.assertEqual(payload["10"]["inputs"]["strength_model"], 0.7)
        self.assertEqual(payload["6"]["inputs"]["clip"][0], "10")

    def test_render_comfyui_workflow_uses_lightning_template_when_requested(self) -> None:
        project_id = self.create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/workflow/render",
            json={
                "checkpoint": "lightning.safetensors",
                "positive_prompt": "fast scene",
                "negative_prompt": "text",
                "generation_profile": "sdxl_low_vram_lightning",
                "steps": 6,
                "cfg": 2.0,
                "sampler_name": "euler",
                "scheduler": "sgm_uniform",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["workflow"]
        self.assertEqual(payload["4"]["inputs"]["ckpt_name"], "lightning.safetensors")
        self.assertEqual(payload["3"]["inputs"]["steps"], 6)
        self.assertEqual(payload["3"]["inputs"]["sampler_name"], "euler")
        self.assertEqual(payload["3"]["inputs"]["scheduler"], "sgm_uniform")

    def test_render_comfyui_workflow_uses_style_reference_template_when_requested(self) -> None:
        project_id = self.create_project()
        media_dir = db.project_dir(project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        reference_image = media_dir / "style_ref.png"
        reference_image.write_bytes(b"png")
        with patch(
            "app.routers.image_gen.get_style_reference_capability",
            return_value={
                "available": True,
                "custom_nodes_ready": True,
                "ipadapter_model_ready": True,
                "clip_vision_ready": True,
                "custom_node_path": "C:/ComfyUI/custom_nodes/IPAdapter",
                "ipadapter_model_path": "C:/ComfyUI/models/ipadapter/model.safetensors",
                "clip_vision_model_path": "C:/ComfyUI/models/clip_vision/model.safetensors",
                "detail": "custom_nodes=ok, ipadapter_model=ok, clip_vision=ok",
            },
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/workflow/render",
                json={
                    "checkpoint": "model.safetensors",
                    "positive_prompt": "quiet editorial room",
                    "negative_prompt": "text",
                    "generation_profile": "sdxl_style_reference",
                    "style_reference_image": "style_ref.png",
                    "style_reference_strength": 0.72,
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["workflow"]
        self.assertEqual(payload["10"]["inputs"]["image"], str(reference_image))
        self.assertEqual(payload["13"]["inputs"]["weight"], 0.72)

    def test_render_comfyui_workflow_uses_style_reference_lora_template_when_requested(self) -> None:
        project_id = self.create_project()
        media_dir = db.project_dir(project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        reference_image = media_dir / "style_ref.png"
        reference_image.write_bytes(b"png")
        with patch(
            "app.routers.image_gen.get_style_reference_capability",
            return_value={
                "available": True,
                "custom_nodes_ready": True,
                "ipadapter_model_ready": True,
                "clip_vision_ready": True,
                "custom_node_path": "C:/ComfyUI/custom_nodes/IPAdapter",
                "ipadapter_model_path": "C:/ComfyUI/models/ipadapter/model.safetensors",
                "clip_vision_model_path": "C:/ComfyUI/models/clip_vision/model.safetensors",
                "detail": "custom_nodes=ok, ipadapter_model=ok, clip_vision=ok",
            },
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/workflow/render",
                json={
                    "checkpoint": "model.safetensors",
                    "positive_prompt": "quiet editorial room",
                    "negative_prompt": "text",
                    "generation_profile": "sdxl_style_reference",
                    "style_reference_image": "style_ref.png",
                    "style_reference_strength": 0.72,
                    "lora_name": "stickfigures.safetensors",
                    "lora_strength": 0.7,
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["workflow"]
        self.assertEqual(payload["10"]["inputs"]["lora_name"], "stickfigures.safetensors")
        self.assertEqual(payload["11"]["inputs"]["image"], str(reference_image))
        self.assertEqual(payload["14"]["inputs"]["weight"], 0.72)

    def test_render_comfyui_workflow_rejects_style_reference_when_capability_missing(self) -> None:
        project_id = self.create_project()
        with patch(
            "app.routers.image_gen.get_style_reference_capability",
            return_value={
                "available": False,
                "custom_nodes_ready": False,
                "ipadapter_model_ready": True,
                "clip_vision_ready": True,
                "custom_node_path": "C:/ComfyUI/custom_nodes",
                "ipadapter_model_path": "C:/ComfyUI/models/ipadapter/model.safetensors",
                "clip_vision_model_path": "C:/ComfyUI/models/clip_vision/model.safetensors",
                "detail": "custom_nodes=missing, ipadapter_model=ok, clip_vision=ok",
            },
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/workflow/render",
                json={
                    "checkpoint": "model.safetensors",
                    "positive_prompt": "quiet editorial room",
                    "generation_profile": "sdxl_style_reference",
                    "style_reference_image": "style_ref.png",
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("IPAdapter style reference is not ready", response.text)

    def test_render_comfyui_workflow_uses_auto_style_reference_from_thumbnail(self) -> None:
        project_id = self.create_project()
        thumbnail_dir = db.project_dir(project_id) / "thumbnail"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_file = thumbnail_dir / "thumb.png"
        thumbnail_file.write_bytes(b"png")
        db.update_project(project_id, thumbnail_file="thumb.png")
        with patch(
            "app.routers.image_gen.get_style_reference_capability",
            return_value={
                "available": True,
                "custom_nodes_ready": True,
                "ipadapter_model_ready": True,
                "clip_vision_ready": True,
                "custom_node_path": "C:/ComfyUI/custom_nodes/IPAdapter",
                "ipadapter_model_path": "C:/ComfyUI/models/ipadapter/model.safetensors",
                "clip_vision_model_path": "C:/ComfyUI/models/clip_vision/model.safetensors",
                "detail": "custom_nodes=ok, ipadapter_model=ok, clip_vision=ok",
            },
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/workflow/render",
                json={
                    "checkpoint": "model.safetensors",
                    "positive_prompt": "quiet editorial room",
                    "negative_prompt": "text",
                    "generation_profile": "sdxl_style_reference",
                    "style_reference_strength": 0.5,
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["workflow"]
        self.assertEqual(payload["10"]["inputs"]["image"], str(thumbnail_file))

    def test_render_comfyui_workflow_uses_controlnet_depth_template_when_requested(self) -> None:
        project_id = self.create_project()
        media_dir = db.project_dir(project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        control_image = media_dir / "control_ref.png"
        control_image.write_bytes(b"png")
        with patch(
            "app.routers.image_gen.get_controlnet_depth_capability",
            return_value={
                "available": True,
                "custom_nodes_ready": True,
                "controlnet_model_ready": True,
                "preprocessor_ready": True,
                "custom_node_path": "C:/ComfyUI/custom_nodes/controlnet",
                "controlnet_model_path": "C:/ComfyUI/models/controlnet/controlnet-depth-sdxl.safetensors",
                "preprocessor_path": "C:/ComfyUI/custom_nodes/comfyui_controlnet_aux",
                "detail": "custom_nodes=ok, controlnet_model=ok, preprocessor=ok",
            },
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/workflow/render",
                json={
                    "checkpoint": "model.safetensors",
                    "positive_prompt": "quiet editorial room",
                    "negative_prompt": "text",
                    "generation_profile": "sdxl_controlnet_depth",
                    "control_image": "control_ref.png",
                    "control_strength": 0.81,
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["workflow"]
        self.assertEqual(payload["10"]["inputs"]["image"], str(control_image))
        self.assertEqual(payload["14"]["inputs"]["strength"], 0.81)

    def test_render_comfyui_workflow_rejects_controlnet_when_capability_missing(self) -> None:
        project_id = self.create_project()
        with patch(
            "app.routers.image_gen.get_controlnet_depth_capability",
            return_value={
                "available": False,
                "custom_nodes_ready": False,
                "controlnet_model_ready": True,
                "preprocessor_ready": False,
                "custom_node_path": "C:/ComfyUI/custom_nodes/controlnet",
                "controlnet_model_path": "C:/ComfyUI/models/controlnet/controlnet-depth-sdxl.safetensors",
                "preprocessor_path": "C:/ComfyUI/custom_nodes/comfyui_controlnet_aux",
                "detail": "custom_nodes=missing, controlnet_model=ok, preprocessor=missing",
            },
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/workflow/render",
                json={
                    "checkpoint": "model.safetensors",
                    "positive_prompt": "quiet editorial room",
                    "generation_profile": "sdxl_controlnet_depth",
                    "control_image": "control_ref.png",
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("ControlNet depth is not ready", response.text)

    def test_submit_comfyui_workflow_updates_body_image_state(self) -> None:
        project_id = self.create_project()
        with patch("app.routers.image_gen.ComfyUIClient.submit_workflow") as mocked_submit:
            mocked_submit.return_value = type(
                "SubmissionStub",
                (),
                {"prompt_id": "prompt-123", "number": 5, "node_errors": {}},
            )()
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/workflow/submit",
                json={
                    "checkpoint": "model.safetensors",
                    "positive_prompt": "golden sunrise over city",
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["prompt_id"], "prompt-123")
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "running")
        self.assertEqual(project["body_image_progress"], 10)

    def test_get_comfyui_history_returns_image_entries(self) -> None:
        project_id = self.create_project()
        with patch("app.routers.image_gen.ComfyUIClient.get_history") as mocked_history, patch(
            "app.routers.image_gen.ComfyUIClient.extract_image_results"
        ) as mocked_extract:
            mocked_history.return_value = {"prompt-123": {"outputs": {}}}
            mocked_extract.return_value = [
                type("ImageResultStub", (), {"filename": "image_0001.png", "subfolder": "", "type": "output"})()
            ]
            response = self.client.get(f"/api/projects/{project_id}/comfyui/history/prompt-123")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["images"][0]["filename"], "image_0001.png")

    def test_import_comfyui_history_image_copies_media_and_updates_mapping(self) -> None:
        project_id = self.create_project()
        with TemporaryDirectory() as temp_dir:
            comfy_dir = Path(temp_dir)
            output_dir = comfy_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            source_file = output_dir / "image_0001.png"
            source_file.write_bytes(_tiny_png_bytes())
            with patch("app.services.comfyui_pipeline.resolve_comfy_output_path", return_value=source_file), patch(
                "app.services.comfyui_pipeline.analyze_image_quality",
                return_value={
                    "score": 0.9,
                    "version": "test",
                    "reason": "ok",
                    "issue_codes": [],
                    "components": {},
                },
            ), patch(
                "app.routers.image_gen.ComfyUIClient.get_history",
                return_value={"prompt-123": {"outputs": {}}},
            ), patch(
                "app.routers.image_gen.ComfyUIClient.extract_image_results",
                return_value=[
                    type("ImageResultStub", (), {"filename": "image_0001.png", "subfolder": "", "type": "output"})()
                ],
            ):
                response = self.client.post(
                    f"/api/projects/{project_id}/comfyui/history/import",
                    json={
                        "prompt_id": "prompt-123",
                        "sentence_idx": 2,
                        "prompt": "golden sunrise over city",
                    },
                )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["imported_file"], "image_0001.png")
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "done")
        self.assertEqual(project["body_image_progress"], 100)
        self.assertEqual(project["body_image_mappings"][0]["sentence_idx"], 2)
        self.assertEqual(project["body_image_mappings"][0]["prompt"], "golden sunrise over city")
        self.assertIn("image_0001.png", project["media_order"])
        imported_path = db.project_dir(project_id) / "media" / "image_0001.png"
        self.assertTrue(imported_path.exists())

    def test_import_comfyui_history_image_keeps_batch_job_running(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_state="running",
            body_image_progress=35,
            body_image_phase="poll_history",
            body_image_last_log="Waiting for ComfyUI history 1/2...",
            body_image_options={
                "batch_items": [
                    {"sentence_idx": 0, "prompt": "first scene"},
                    {"sentence_idx": 1, "prompt": "second scene"},
                ]
            },
        )
        with TemporaryDirectory() as temp_dir:
            comfy_dir = Path(temp_dir)
            output_dir = comfy_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            source_file = output_dir / "image_0002.png"
            source_file.write_bytes(_tiny_png_bytes())
            with patch("app.services.comfyui_pipeline.resolve_comfy_output_path", return_value=source_file), patch(
                "app.services.comfyui_pipeline.analyze_image_quality",
                return_value={
                    "score": 0.9,
                    "version": "test",
                    "reason": "ok",
                    "issue_codes": [],
                    "components": {},
                },
            ), patch(
                "app.routers.image_gen.ComfyUIClient.get_history",
                return_value={"prompt-456": {"outputs": {}}},
            ), patch(
                "app.routers.image_gen.ComfyUIClient.extract_image_results",
                return_value=[
                    type("ImageResultStub", (), {"filename": "image_0002.png", "subfolder": "", "type": "output"})()
                ],
            ):
                response = self.client.post(
                    f"/api/projects/{project_id}/comfyui/history/import",
                    json={
                        "prompt_id": "prompt-456",
                        "sentence_idx": 1,
                        "prompt": "clean strategy diagram",
                    },
                )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "running")
        self.assertEqual(project["body_image_progress"], 35)
        self.assertEqual(project["body_image_phase"], "poll_history")
        self.assertEqual(project["body_image_mappings"][0]["sentence_idx"], 1)

    def test_prompt_suggestion_returns_stickman_prompt(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            sentences=["첫 문장", "둘째 문장"],
            body_image_options={"disable_llm_visual_planner": True},
            source_draft_fact_notes=[{"source_id": "src1", "note": "핵심 사실"}],
            source_draft_sources=[
                {
                    "id": "src1",
                    "url": "https://example.com/article",
                    "final_url": "https://example.com/article",
                    "title": "기사 제목",
                    "domain": "example.com",
                    "author": "",
                    "published_at": "",
                    "language": "ko",
                    "excerpt": "요약",
                    "fetched_at": "",
                    "word_count": 100,
                }
            ],
        )
        response = self.client.get(f"/api/projects/{project_id}/comfyui/prompt-suggestion?sentence_idx=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["sentence_idx"], 1)
        self.assertIn("Stick figure", payload["positive_prompt"])
        self.assertNotIn("기사 제목", payload["positive_prompt"])

    def test_batch_auto_job_queues_multiple_items(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            sentences=["첫 문장", "둘째 문장", "셋째 문장"],
            source_draft_fact_notes=[{"source_id": "src1", "note": "핵심 사실"}],
            source_draft_sources=[
                {
                    "id": "src1",
                    "url": "https://example.com/article",
                    "final_url": "https://example.com/article",
                    "title": "기사 제목",
                    "domain": "example.com",
                    "author": "",
                    "published_at": "",
                    "language": "ko",
                    "excerpt": "요약",
                    "fetched_at": "",
                    "word_count": 100,
                }
            ],
        )
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/job/batch-auto",
            json={
                "checkpoint": "model.safetensors",
                "start_idx": 0,
                "count": 2,
                "width": 1024,
                "height": 576,
                "seed_base": 100,
                "filename_prefix": "scene",
                "client_id": "newauto-test",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "queued")
        batch_items = cast(list[object], project["body_image_options"]["batch_items"])
        self.assertEqual(len(batch_items), 2)
        first_item = cast(dict[str, object], batch_items[0])
        self.assertIn("steps", first_item)
        self.assertIn("sampler_name", first_item)
        self.assertIn("generation_profile", first_item)
        manifest_path = Path(cast(str, project["body_image_options"]["image_prompts_manifest_path"]))
        self.assertTrue(manifest_path.exists())

    def test_batch_auto_job_blocks_ev_prompt_quality_failure(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["EV battery sentence"])
        bad_suggestion = {
            "sentence_idx": 0,
            "positive_prompt": "generic trophy and city skyline",
            "prompt_g": "generic trophy and city skyline",
            "prompt_l": "generic trophy and city skyline",
            "negative_prompt": "text, logo, watermark",
            "quality_mode": "fast",
            "generation_profile": "sdxl_standard",
            "visual_brief": {
                "domain": "ev_battery",
                "primary_prop": "market competition symbol",
                "must_show": ["market competition symbol"],
            },
            "visual_plan": {"domain": "ev_battery", "source": "llm"},
            "keyword_coverage": {
                "passed": False,
                "missing_must_show": [],
                "blocklist_hits": [],
                "issue_codes": ["EV_BATTERY_CORE_VISUAL_MISSING"],
            },
        }
        with patch("app.routers.image_gen.suggest_image_prompt_batch", return_value=[bad_suggestion]):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/job/batch-auto",
                json={
                    "checkpoint": "model.safetensors",
                    "start_idx": 0,
                    "count": 1,
                    "width": 1024,
                    "height": 576,
                    "seed_base": 100,
                    "filename_prefix": "scene",
                    "client_id": "newauto-test",
                },
            )

        self.assertEqual(response.status_code, 409)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "blocked")
        self.assertEqual(project["body_image_phase"], "prompt_quality_gate")
        self.assertIn("EV_BATTERY_PROMPT_QUALITY_FAILED", project["body_image_error"])

    def test_batch_auto_job_blocks_strict_domain_missing_must_show(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["EV battery sentence"])
        bad_suggestion = {
            "sentence_idx": 0,
            "positive_prompt": "LFP battery cell with safety shield",
            "prompt_g": "LFP battery cell with safety shield",
            "prompt_l": "LFP battery cell with safety shield",
            "negative_prompt": "text, logo, watermark",
            "quality_mode": "fast",
            "generation_profile": "sdxl_standard",
            "visual_brief": {
                "domain": "ev_battery",
                "primary_prop": "LFP battery cell",
                "must_show": ["LFP battery cell", "range indicator"],
            },
            "visual_plan": {"domain": "ev_battery", "source": "llm"},
            "keyword_coverage": {
                "passed": False,
                "missing_must_show": ["range indicator"],
                "blocklist_hits": [],
                "issue_codes": [],
            },
        }
        with patch("app.routers.image_gen.suggest_image_prompt_batch", return_value=[bad_suggestion]):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/job/batch-auto",
                json={
                    "checkpoint": "model.safetensors",
                    "start_idx": 0,
                    "count": 1,
                    "width": 1024,
                    "height": 576,
                    "seed_base": 100,
                    "filename_prefix": "scene",
                    "client_id": "newauto-test",
                },
            )

        self.assertEqual(response.status_code, 409)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertIn("STRICT_PROMPT_COVERAGE_FAILED", project["body_image_error"])

    def test_batch_auto_job_keeps_lora_settings(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["첫 문장"])
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/job/batch-auto",
            json={
                "checkpoint": "model.safetensors",
                "start_idx": 0,
                "count": 1,
                "width": 1024,
                "height": 576,
                "seed_base": 100,
                "filename_prefix": "scene",
                "client_id": "newauto-test",
                "lora_name": "stickfigures.safetensors",
                "lora_strength": 0.65,
            },
        )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        batch_items = cast(list[dict[str, object]], project["body_image_options"]["batch_items"])
        self.assertEqual(batch_items[0]["template_id"], "txt2img_sdxl_stickman_lora")
        self.assertEqual(batch_items[0]["lora_name"], "stickfigures.safetensors")

    def test_batch_auto_job_resets_existing_candidates_for_selected_sentences(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            sentences=["first", "second"],
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "old_scene0.png",
                    "prompt": "old",
                    "sentence_text": "first",
                    "sentence_hash": "oldhash",
                    "project_id": project_id,
                    "prompt_id": "old-prompt",
                    "manifest_sentence_hash": "oldhash",
                },
                {
                    "sentence_idx": 1,
                    "path": "old_scene1.png",
                    "prompt": "old",
                    "sentence_text": "second",
                    "sentence_hash": "oldhash1",
                    "project_id": project_id,
                    "prompt_id": "old-prompt1",
                    "manifest_sentence_hash": "oldhash1",
                },
            ],
            body_image_options={
                "candidate_groups": {"0": [{"path": "old_scene0.png"}], "1": [{"path": "old_scene1.png"}]},
                "candidate_reviews": {"0": {"best_path": "old_scene0.png"}, "1": {"best_path": "old_scene1.png"}},
            },
        )
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/job/batch-auto",
            json={
                "checkpoint": "model.safetensors",
                "start_idx": 0,
                "count": 1,
                "width": 1024,
                "height": 576,
                "seed_base": 100,
                "filename_prefix": "scene",
                "client_id": "newauto-test",
            },
        )

        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual([item["sentence_idx"] for item in project["body_image_mappings"]], [1])
        self.assertNotIn("0", cast(dict[str, object], project["body_image_options"].get("candidate_groups", {})))
        self.assertNotIn("0", cast(dict[str, object], project["body_image_options"].get("candidate_reviews", {})))
        self.assertIn("1", cast(dict[str, object], project["body_image_options"].get("candidate_groups", {})))

    def test_single_comfyui_job_preserves_existing_prompt_manifest_metadata(self) -> None:
        project_id = self.create_project()
        db.update_project(
            project_id,
            body_image_options={
                "image_prompts_manifest_path": "C:/tmp/manifest.json",
                "candidate_groups": {"0": [{"path": "scene0.png"}]},
            },
        )
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/job",
            json={
                "checkpoint": "model.safetensors",
                "positive_prompt": "financial strategy desk with quantum processor glow",
                "negative_prompt": "text, watermark",
                "width": 1024,
                "height": 576,
                "seed": 123,
                "filename_prefix": "scene001",
            },
        )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_options"]["image_prompts_manifest_path"], "C:/tmp/manifest.json")
        self.assertIn("candidate_groups", project["body_image_options"])
        self.assertEqual(project["body_image_options"]["checkpoint"], "model.safetensors")

    def test_batch_auto_job_expands_variants_per_scene(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["first", "second"])
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/job/batch-auto",
            json={
                "checkpoint": "model.safetensors",
                "start_idx": 0,
                "count": 2,
                "variants_per_scene": 3,
                "width": 1024,
                "height": 576,
                "seed_base": 100,
                "filename_prefix": "scene",
                "client_id": "newauto-test",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 6)
        self.assertEqual(payload["variants_per_scene"], 3)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        batch_items = cast(list[dict[str, object]], project["body_image_options"]["batch_items"])
        self.assertEqual(len(batch_items), 6)
        self.assertEqual(batch_items[0]["candidate_index"], 1)
        self.assertEqual(batch_items[0]["candidate_total"], 3)
        self.assertEqual(batch_items[2]["candidate_index"], 3)
        self.assertNotEqual(batch_items[0]["seed"], batch_items[1]["seed"])

    def test_batch_auto_job_selectively_expands_high_risk_variants(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["leaf film decomposes", "simple overview"])
        suggestions: list[dict[str, object]] = [
            {
                "sentence_idx": 0,
                "positive_prompt": "macro leaf film decomposition in soil",
                "prompt_g": "leaf film soil",
                "prompt_l": "macro material detail",
                "negative_prompt": "text",
                "visual_brief": {
                    "domain": "agriculture_environment",
                    "composition_template": "SoilDecomposition",
                    "must_show": ["leaf film", "soil"],
                },
                "sentence_hash": "hash-0",
            },
            {
                "sentence_idx": 1,
                "positive_prompt": "plain diagram overview",
                "prompt_g": "overview",
                "prompt_l": "simple",
                "negative_prompt": "text",
                "visual_brief": {
                    "domain": "essay",
                    "composition_template": "SimpleScene",
                    "must_show": ["overview"],
                },
                "sentence_hash": "hash-1",
            },
        ]
        with patch("app.routers.image_gen.suggest_image_prompt_batch", return_value=suggestions):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/job/batch-auto",
                json={
                    "checkpoint": "model.safetensors",
                    "start_idx": 0,
                    "count": 2,
                    "variants_per_scene": 1,
                    "selective_high_risk_variants": True,
                    "high_risk_variants": 2,
                    "seed_base": 100,
                    "filename_prefix": "scene",
                    "client_id": "newauto-test",
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        batch_items = cast(list[dict[str, object]], project["body_image_options"]["batch_items"])
        first_scene = [item for item in batch_items if item["sentence_idx"] == 0]
        second_scene = [item for item in batch_items if item["sentence_idx"] == 1]
        self.assertEqual(len(first_scene), 2)
        self.assertEqual(first_scene[0]["candidate_total"], 2)
        self.assertEqual(len(second_scene), 1)
        self.assertEqual(second_scene[0]["candidate_total"], 1)

    def test_batch_auto_job_supports_fixed_seed_policy(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["first"])
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/job/batch-auto",
            json={
                "checkpoint": "model.safetensors",
                "start_idx": 0,
                "count": 1,
                "variants_per_scene": 2,
                "seed_policy": "fixed",
                "seed_base": 321,
                "filename_prefix": "scene",
                "client_id": "newauto-test",
            },
        )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        batch_items = cast(list[dict[str, object]], project["body_image_options"]["batch_items"])
        self.assertEqual(batch_items[0]["seed"], batch_items[1]["seed"])
        self.assertEqual(batch_items[0]["seed_policy"], "fixed")

    def test_batch_auto_job_supports_lightning_profile(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["first"])
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/job/batch-auto",
            json={
                "checkpoint": "lightning.safetensors",
                "generation_profile": "sdxl_low_vram_lightning",
                "start_idx": 0,
                "count": 1,
                "variants_per_scene": 1,
                "seed_base": 321,
                "filename_prefix": "scene",
                "client_id": "newauto-test",
            },
        )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        batch_items = cast(list[dict[str, object]], project["body_image_options"]["batch_items"])
        self.assertEqual(batch_items[0]["template_id"], "txt2img_sdxl_lightning")
        self.assertEqual(batch_items[0]["generation_profile"], "sdxl_low_vram_lightning")
        self.assertEqual(batch_items[0]["steps"], 6)
        self.assertEqual(batch_items[0]["cfg"], 2.0)
        self.assertEqual(batch_items[0]["sampler_name"], "euler")
        self.assertEqual(batch_items[0]["requires_lightning_checkpoint"], True)

    def test_batch_auto_job_supports_style_reference_profile(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["first"])
        media_dir = db.project_dir(project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        reference_image = media_dir / "style_ref.png"
        reference_image.write_bytes(b"png")
        with patch(
            "app.routers.image_gen.get_style_reference_capability",
            return_value={
                "available": True,
                "custom_nodes_ready": True,
                "ipadapter_model_ready": True,
                "clip_vision_ready": True,
                "custom_node_path": "C:/ComfyUI/custom_nodes/IPAdapter",
                "ipadapter_model_path": "C:/ComfyUI/models/ipadapter/model.safetensors",
                "clip_vision_model_path": "C:/ComfyUI/models/clip_vision/model.safetensors",
                "detail": "custom_nodes=ok, ipadapter_model=ok, clip_vision=ok",
            },
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/job/batch-auto",
                json={
                    "checkpoint": "model.safetensors",
                    "generation_profile": "sdxl_style_reference",
                    "style_reference_image": "style_ref.png",
                    "style_reference_strength": 0.6,
                    "start_idx": 0,
                    "count": 1,
                    "variants_per_scene": 1,
                    "seed_base": 321,
                    "filename_prefix": "scene",
                    "client_id": "newauto-test",
                },
            )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        batch_items = cast(list[dict[str, object]], project["body_image_options"]["batch_items"])
        self.assertEqual(batch_items[0]["template_id"], "txt2img_sdxl_ipadapter_style")
        self.assertEqual(batch_items[0]["requires_ipadapter"], True)
        self.assertEqual(batch_items[0]["style_reference_image"], str(reference_image))
        self.assertEqual(batch_items[0]["style_reference_strength"], 0.6)

    def test_batch_auto_job_supports_style_reference_profile_with_lora(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["first"])
        media_dir = db.project_dir(project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        reference_image = media_dir / "style_ref.png"
        reference_image.write_bytes(b"png")
        with patch(
            "app.routers.image_gen.get_style_reference_capability",
            return_value={
                "available": True,
                "custom_nodes_ready": True,
                "ipadapter_model_ready": True,
                "clip_vision_ready": True,
                "custom_node_path": "C:/ComfyUI/custom_nodes/IPAdapter",
                "ipadapter_model_path": "C:/ComfyUI/models/ipadapter/model.safetensors",
                "clip_vision_model_path": "C:/ComfyUI/models/clip_vision/model.safetensors",
                "detail": "custom_nodes=ok, ipadapter_model=ok, clip_vision=ok",
            },
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/job/batch-auto",
                json={
                    "checkpoint": "model.safetensors",
                    "generation_profile": "sdxl_style_reference",
                    "style_reference_image": "style_ref.png",
                    "style_reference_strength": 0.6,
                    "lora_name": "stickfigures.safetensors",
                    "lora_strength": 0.75,
                    "start_idx": 0,
                    "count": 1,
                    "variants_per_scene": 1,
                    "seed_base": 321,
                    "filename_prefix": "scene",
                    "client_id": "newauto-test",
                },
            )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        batch_items = cast(list[dict[str, object]], project["body_image_options"]["batch_items"])
        self.assertEqual(batch_items[0]["template_id"], "txt2img_sdxl_ipadapter_style_lora")
        self.assertEqual(batch_items[0]["lora_name"], "stickfigures.safetensors")

    def test_batch_auto_job_supports_controlnet_depth_profile(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["first"])
        media_dir = db.project_dir(project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        control_image = media_dir / "control_ref.png"
        control_image.write_bytes(b"png")
        with patch(
            "app.routers.image_gen.get_controlnet_depth_capability",
            return_value={
                "available": True,
                "custom_nodes_ready": True,
                "controlnet_model_ready": True,
                "preprocessor_ready": True,
                "custom_node_path": "C:/ComfyUI/custom_nodes/controlnet",
                "controlnet_model_path": "C:/ComfyUI/models/controlnet/controlnet-depth-sdxl.safetensors",
                "preprocessor_path": "C:/ComfyUI/custom_nodes/comfyui_controlnet_aux",
                "detail": "custom_nodes=ok, controlnet_model=ok, preprocessor=ok",
            },
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/comfyui/job/batch-auto",
                json={
                    "checkpoint": "model.safetensors",
                    "generation_profile": "sdxl_controlnet_depth",
                    "control_image": "control_ref.png",
                    "control_strength": 0.7,
                    "start_idx": 0,
                    "count": 1,
                    "variants_per_scene": 1,
                    "seed_base": 321,
                    "filename_prefix": "scene",
                    "client_id": "newauto-test",
                },
            )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        batch_items = cast(list[dict[str, object]], project["body_image_options"]["batch_items"])
        self.assertEqual(batch_items[0]["template_id"], "txt2img_sdxl_controlnet_depth")
        self.assertEqual(batch_items[0]["requires_controlnet"], True)
        self.assertEqual(batch_items[0]["control_image"], str(control_image))
        self.assertEqual(batch_items[0]["control_strength"], 0.7)

    def test_simple_media_prompt_manifest_generates_all_and_records_lmstudio_unload(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["first scene", "second scene"])
        suggestions: list[dict[str, object]] = [
            {
                "sentence_idx": 0,
                "positive_prompt": "first visual prompt",
                "prompt_g": "first global",
                "prompt_l": "first local",
                "negative_prompt": "text",
                "sentence_hash": "hash-0",
            },
            {
                "sentence_idx": 1,
                "positive_prompt": "second visual prompt",
                "prompt_g": "second global",
                "prompt_l": "second local",
                "negative_prompt": "watermark",
                "sentence_hash": "hash-1",
            },
        ]
        with (
            patch("app.routers.image_gen.suggest_image_prompt_batch", return_value=suggestions),
            patch("app.routers.image_gen.loaded_lmstudio_models", side_effect=[["gemma"], []]),
            patch("app.routers.image_gen.unload_lmstudio_model", return_value={"ok": True, "model": "gemma"}),
        ):
            response = self.client.post(
                f"/api/projects/{project_id}/media-simple/prompt-manifest",
                json={"start_idx": 0, "count": 2, "unload_lmstudio_after": True},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["lmstudio_unload"]["ok"], True)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        options = project["body_image_options"]
        self.assertEqual(options["simple_media_prompt_state"], "done")
        self.assertEqual(options["simple_media_prompt_count"], 2)
        self.assertTrue(Path(cast(str, options["image_prompts_manifest_path"])).exists())

    def test_simple_media_comfyui_job_requires_lmstudio_unloaded(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["first scene"])
        suggestions: list[dict[str, object]] = [
            {
                "sentence_idx": 0,
                "positive_prompt": "first visual prompt",
                "prompt_g": "first global",
                "prompt_l": "first local",
                "negative_prompt": "text",
                "sentence_hash": "hash-0",
            }
        ]
        with (
            patch("app.routers.image_gen.suggest_image_prompt_batch", return_value=suggestions),
            patch("app.routers.image_gen.loaded_lmstudio_models", side_effect=[["gemma"], []]),
            patch("app.routers.image_gen.unload_lmstudio_model", return_value={"ok": True, "model": "gemma"}),
        ):
            manifest_response = self.client.post(
                f"/api/projects/{project_id}/media-simple/prompt-manifest",
                json={"start_idx": 0, "count": 1},
            )
        self.assertEqual(manifest_response.status_code, 200)
        with patch("app.routers.image_gen.loaded_lmstudio_models", return_value=["gemma"]):
            response = self.client.post(
                f"/api/projects/{project_id}/media-simple/comfyui/job",
                json={"checkpoint": "model.safetensors", "start_idx": 0, "count": 1},
            )
        self.assertEqual(response.status_code, 409)
        self.assertIn("LM Studio still has a model loaded", response.text)

    def test_simple_media_comfyui_job_queues_from_prompt_manifest(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["first scene"])
        suggestions: list[dict[str, object]] = [
            {
                "sentence_idx": 0,
                "positive_prompt": "first visual prompt",
                "prompt_g": "first global",
                "prompt_l": "first local",
                "negative_prompt": "text",
                "sentence_hash": "hash-0",
            }
        ]
        with (
            patch("app.routers.image_gen.suggest_image_prompt_batch", return_value=suggestions),
            patch("app.routers.image_gen.loaded_lmstudio_models", side_effect=[["gemma"], []]),
            patch("app.routers.image_gen.unload_lmstudio_model", return_value={"ok": True, "model": "gemma"}),
        ):
            manifest_response = self.client.post(
                f"/api/projects/{project_id}/media-simple/prompt-manifest",
                json={"start_idx": 0, "count": 1},
            )
        self.assertEqual(manifest_response.status_code, 200)
        with patch("app.routers.image_gen.loaded_lmstudio_models", return_value=[]):
            response = self.client.post(
                f"/api/projects/{project_id}/media-simple/comfyui/job",
                json={
                    "checkpoint": "model.safetensors",
                    "start_idx": 0,
                    "count": 1,
                    "variants_per_scene": 2,
                    "seed_base": 100,
                    "filename_prefix": "simple",
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["visual_source_mode"], "comfyui_auto")
        self.assertEqual(project["body_image_state"], "queued")
        batch_items = cast(list[dict[str, object]], project["body_image_options"]["batch_items"])
        self.assertEqual(batch_items[0]["positive_prompt"], "first visual prompt")
        self.assertEqual(batch_items[0]["candidate_total"], 2)

    def test_visual_diagnostics_regenerate_route_writes_report_and_contact_sheet(self) -> None:
        project_id = self.create_project()
        db.update_project(project_id, sentences=["diagnostic sentence"])
        response = self.client.post(f"/api/projects/{project_id}/visual-diagnostics/regenerate")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(Path(str(payload["visual_mismatch_report_json_path"])).exists())
        self.assertTrue(Path(str(payload["visual_mismatch_report_md_path"])).exists())
        self.assertTrue(Path(str(payload["diagnostic_contact_sheet_path"])).exists())

    def test_select_comfyui_candidate_updates_selected_mapping(self) -> None:
        project_id = self.create_project()
        sentence = "current sentence"
        db.update_project(
            project_id,
            sentences=[sentence],
            body_image_options={
                "candidate_groups": {
                    "0": [
                        {
                            "path": "cand_a.png",
                            "prompt": "prompt a",
                            "prompt_id": "prompt-a",
                            "sentence_hash": "hash-a",
                            "candidate_index": 1,
                            "candidate_total": 2,
                            "candidate_score": 100.0,
                            "selected": False,
                        },
                        {
                            "path": "cand_b.png",
                            "prompt": "prompt b",
                            "prompt_id": "prompt-b",
                            "sentence_hash": "hash-b",
                            "candidate_index": 2,
                            "candidate_total": 2,
                            "candidate_score": 200.0,
                            "selected": True,
                        },
                    ]
                }
            },
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "cand_b.png",
                    "prompt": "prompt b",
                    "selected_reason": "auto_score:200",
                }
            ],
        )
        response = self.client.post(
            f"/api/projects/{project_id}/comfyui/candidates/select",
            json={"sentence_idx": 0, "path": "cand_a.png"},
        )
        self.assertEqual(response.status_code, 200)
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_mappings"][0]["path"], "cand_a.png")
        self.assertEqual(project["body_image_mappings"][0]["selected_reason"], "manual_pick")


if __name__ == "__main__":
    unittest.main()
