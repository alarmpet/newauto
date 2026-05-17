import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from fastapi import HTTPException

from app.services.comfyui_workflows import WorkflowPayload, load_workflow_template, render_workflow_template


class ComfyWorkflowTests(unittest.TestCase):
    def test_load_workflow_template_raises_404_for_missing_template(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(HTTPException) as captured:
                load_workflow_template("missing", Path(temp_dir))
        self.assertEqual(captured.exception.status_code, 404)

    def test_render_workflow_template_replaces_exact_and_embedded_placeholders(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            (base_dir / "sample.json").write_text(
                json.dumps(
                    {
                        "5": {"inputs": {"width": "__WIDTH__", "height": "__HEIGHT__"}},
                        "6": {"inputs": {"text": "scene __INDEX__ :: __POSITIVE_PROMPT__"}},
                        "7": {"inputs": {"text": "__NEGATIVE_PROMPT__"}},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            rendered = render_workflow_template(
                "sample",
                {
                    "__WIDTH__": 1024,
                    "__HEIGHT__": 576,
                    "__INDEX__": 3,
                    "__POSITIVE_PROMPT__": "golden sunrise",
                    "__NEGATIVE_PROMPT__": "text, watermark",
                },
                base_dir,
            )
        rendered_payload = cast(WorkflowPayload, rendered)
        node_5 = cast(dict[str, object], rendered_payload["5"])
        node_6 = cast(dict[str, object], rendered_payload["6"])
        node_7 = cast(dict[str, object], rendered_payload["7"])
        inputs_5 = cast(dict[str, object], node_5["inputs"])
        inputs_6 = cast(dict[str, object], node_6["inputs"])
        inputs_7 = cast(dict[str, object], node_7["inputs"])
        self.assertEqual(inputs_5["width"], 1024)
        self.assertEqual(inputs_5["height"], 576)
        self.assertEqual(inputs_6["text"], "scene 3 :: golden sunrise")
        self.assertEqual(inputs_7["text"], "text, watermark")

    def test_sdxl_basic_template_accepts_runtime_sampler_settings(self) -> None:
        rendered = render_workflow_template(
            "txt2img_sdxl_basic",
            {
                "__CHECKPOINT__": "model.safetensors",
                "__POSITIVE_PROMPT__": "cinematic scene",
                "__POSITIVE_PROMPT_G__": "wide cinematic scene",
                "__POSITIVE_PROMPT_L__": "sharp cinematic scene",
                "__NEGATIVE_PROMPT__": "text",
                "__NEGATIVE_PROMPT_G__": "text",
                "__NEGATIVE_PROMPT_L__": "text",
                "__WIDTH__": 1344,
                "__HEIGHT__": 768,
                "__SEED__": 123,
                "__STEPS__": 30,
                "__CFG__": 5.8,
                "__SAMPLER__": "dpmpp_2m",
                "__SCHEDULER__": "karras",
                "__DENOISE__": 1.0,
                "__ORIGINAL_WIDTH__": 1344,
                "__ORIGINAL_HEIGHT__": 768,
                "__TARGET_WIDTH__": 1344,
                "__TARGET_HEIGHT__": 768,
                "__CROP_W__": 0,
                "__CROP_H__": 0,
                "__FILENAME_PREFIX__": "scene",
            },
        )
        node_3 = cast(dict[str, object], rendered["3"])
        node_6 = cast(dict[str, object], rendered["6"])
        inputs_3 = cast(dict[str, object], node_3["inputs"])
        inputs_6 = cast(dict[str, object], node_6["inputs"])
        self.assertEqual(inputs_3["steps"], 30)
        self.assertEqual(inputs_3["cfg"], 5.8)
        self.assertEqual(inputs_3["sampler_name"], "dpmpp_2m")
        self.assertEqual(inputs_3["scheduler"], "karras")
        self.assertEqual(inputs_6["crop_w"], 0)
        self.assertEqual(inputs_6["target_width"], 1344)
        self.assertEqual(inputs_6["text_g"], "wide cinematic scene")
        self.assertEqual(inputs_6["text_l"], "sharp cinematic scene")

    def test_sdxl_lightning_template_accepts_runtime_sampler_settings(self) -> None:
        rendered = render_workflow_template(
            "txt2img_sdxl_lightning",
            {
                "__CHECKPOINT__": "lightning.safetensors",
                "__POSITIVE_PROMPT__": "fast cinematic scene",
                "__POSITIVE_PROMPT_G__": "fast wide cinematic scene",
                "__POSITIVE_PROMPT_L__": "fast crisp cinematic scene",
                "__NEGATIVE_PROMPT__": "text",
                "__NEGATIVE_PROMPT_G__": "text",
                "__NEGATIVE_PROMPT_L__": "text",
                "__WIDTH__": 1024,
                "__HEIGHT__": 576,
                "__SEED__": 321,
                "__STEPS__": 6,
                "__CFG__": 2.0,
                "__SAMPLER__": "euler",
                "__SCHEDULER__": "sgm_uniform",
                "__DENOISE__": 1.0,
                "__ORIGINAL_WIDTH__": 1024,
                "__ORIGINAL_HEIGHT__": 576,
                "__TARGET_WIDTH__": 1024,
                "__TARGET_HEIGHT__": 576,
                "__CROP_W__": 0,
                "__CROP_H__": 0,
                "__FILENAME_PREFIX__": "lightning_scene",
            },
        )
        node_3 = cast(dict[str, object], rendered["3"])
        node_6 = cast(dict[str, object], rendered["6"])
        inputs_3 = cast(dict[str, object], node_3["inputs"])
        inputs_6 = cast(dict[str, object], node_6["inputs"])
        self.assertEqual(inputs_3["steps"], 6)
        self.assertEqual(inputs_3["cfg"], 2.0)
        self.assertEqual(inputs_3["sampler_name"], "euler")
        self.assertEqual(inputs_3["scheduler"], "sgm_uniform")
        self.assertEqual(inputs_6["target_width"], 1024)
        self.assertEqual(inputs_6["text_g"], "fast wide cinematic scene")
        self.assertEqual(inputs_6["text_l"], "fast crisp cinematic scene")

    def test_sdxl_lora_template_accepts_generic_lora_placeholders(self) -> None:
        rendered = render_workflow_template(
            "txt2img_sdxl_lora",
            {
                "__CHECKPOINT__": "model.safetensors",
                "__POSITIVE_PROMPT__": "flat robot infographic",
                "__POSITIVE_PROMPT_G__": "flat robot infographic",
                "__POSITIVE_PROMPT_L__": "clean vector line art",
                "__NEGATIVE_PROMPT__": "text",
                "__NEGATIVE_PROMPT_G__": "text",
                "__NEGATIVE_PROMPT_L__": "text",
                "__WIDTH__": 1024,
                "__HEIGHT__": 576,
                "__SEED__": 123,
                "__STEPS__": 30,
                "__CFG__": 5.8,
                "__SAMPLER__": "dpmpp_2m",
                "__SCHEDULER__": "karras",
                "__DENOISE__": 1.0,
                "__ORIGINAL_WIDTH__": 1024,
                "__ORIGINAL_HEIGHT__": 576,
                "__TARGET_WIDTH__": 1024,
                "__TARGET_HEIGHT__": 576,
                "__CROP_W__": 0,
                "__CROP_H__": 0,
                "__LORA_NAME__": "example-style.safetensors",
                "__LORA_STRENGTH__": 0.7,
                "__FILENAME_PREFIX__": "lora_scene",
            },
        )
        node_3 = cast(dict[str, object], rendered["3"])
        node_10 = cast(dict[str, object], rendered["10"])
        inputs_3 = cast(dict[str, object], node_3["inputs"])
        inputs_10 = cast(dict[str, object], node_10["inputs"])
        self.assertEqual(inputs_3["model"], ["10", 0])
        self.assertEqual(inputs_10["lora_name"], "example-style.safetensors")
        self.assertEqual(inputs_10["strength_model"], 0.7)
        self.assertEqual(inputs_10["strength_clip"], 0.7)

    def test_sdxl_ipadapter_template_accepts_style_reference_placeholders(self) -> None:
        rendered = render_workflow_template(
            "txt2img_sdxl_ipadapter_style",
            {
                "__CHECKPOINT__": "model.safetensors",
                "__POSITIVE_PROMPT__": "quiet editorial interior",
                "__POSITIVE_PROMPT_G__": "quiet editorial interior",
                "__POSITIVE_PROMPT_L__": "quiet editorial interior",
                "__NEGATIVE_PROMPT__": "text",
                "__NEGATIVE_PROMPT_G__": "text",
                "__NEGATIVE_PROMPT_L__": "text",
                "__WIDTH__": 1024,
                "__HEIGHT__": 576,
                "__SEED__": 999,
                "__STEPS__": 28,
                "__CFG__": 5.6,
                "__SAMPLER__": "dpmpp_2m",
                "__SCHEDULER__": "karras",
                "__DENOISE__": 1.0,
                "__ORIGINAL_WIDTH__": 1024,
                "__ORIGINAL_HEIGHT__": 576,
                "__TARGET_WIDTH__": 1024,
                "__TARGET_HEIGHT__": 576,
                "__CROP_W__": 0,
                "__CROP_H__": 0,
                "__STYLE_REFERENCE_IMAGE__": "C:/style/ref.png",
                "__STYLE_REFERENCE_STRENGTH__": 0.65,
                "__FILENAME_PREFIX__": "style_scene",
            },
        )
        node_10 = cast(dict[str, object], rendered["10"])
        node_13 = cast(dict[str, object], rendered["13"])
        inputs_10 = cast(dict[str, object], node_10["inputs"])
        inputs_13 = cast(dict[str, object], node_13["inputs"])
        self.assertEqual(inputs_10["image"], "C:/style/ref.png")
        self.assertEqual(inputs_13["weight"], 0.65)

    def test_sdxl_ipadapter_lora_template_accepts_style_and_lora_placeholders(self) -> None:
        rendered = render_workflow_template(
            "txt2img_sdxl_ipadapter_style_lora",
            {
                "__CHECKPOINT__": "model.safetensors",
                "__POSITIVE_PROMPT__": "quiet editorial interior",
                "__POSITIVE_PROMPT_G__": "quiet editorial interior",
                "__POSITIVE_PROMPT_L__": "quiet editorial interior",
                "__NEGATIVE_PROMPT__": "text",
                "__NEGATIVE_PROMPT_G__": "text",
                "__NEGATIVE_PROMPT_L__": "text",
                "__WIDTH__": 1024,
                "__HEIGHT__": 576,
                "__SEED__": 999,
                "__STEPS__": 28,
                "__CFG__": 5.6,
                "__SAMPLER__": "dpmpp_2m",
                "__SCHEDULER__": "karras",
                "__DENOISE__": 1.0,
                "__ORIGINAL_WIDTH__": 1024,
                "__ORIGINAL_HEIGHT__": 576,
                "__TARGET_WIDTH__": 1024,
                "__TARGET_HEIGHT__": 576,
                "__CROP_W__": 0,
                "__CROP_H__": 0,
                "__STYLE_REFERENCE_IMAGE__": "C:/style/ref.png",
                "__STYLE_REFERENCE_STRENGTH__": 0.65,
                "__LORA_NAME__": "stickfigures.safetensors",
                "__LORA_STRENGTH__": 0.7,
                "__FILENAME_PREFIX__": "style_scene",
            },
        )
        node_10 = cast(dict[str, object], rendered["10"])
        node_11 = cast(dict[str, object], rendered["11"])
        node_14 = cast(dict[str, object], rendered["14"])
        inputs_10 = cast(dict[str, object], node_10["inputs"])
        inputs_11 = cast(dict[str, object], node_11["inputs"])
        inputs_14 = cast(dict[str, object], node_14["inputs"])
        self.assertEqual(inputs_10["lora_name"], "stickfigures.safetensors")
        self.assertEqual(inputs_11["image"], "C:/style/ref.png")
        self.assertEqual(inputs_14["weight"], 0.65)

    def test_sdxl_controlnet_depth_template_accepts_control_placeholders(self) -> None:
        rendered = render_workflow_template(
            "txt2img_sdxl_controlnet_depth",
            {
                "__CHECKPOINT__": "model.safetensors",
                "__POSITIVE_PROMPT__": "quiet architectural scene",
                "__POSITIVE_PROMPT_G__": "quiet architectural scene",
                "__POSITIVE_PROMPT_L__": "quiet architectural scene",
                "__NEGATIVE_PROMPT__": "text",
                "__NEGATIVE_PROMPT_G__": "text",
                "__NEGATIVE_PROMPT_L__": "text",
                "__WIDTH__": 1024,
                "__HEIGHT__": 576,
                "__SEED__": 777,
                "__STEPS__": 28,
                "__CFG__": 5.5,
                "__SAMPLER__": "dpmpp_2m",
                "__SCHEDULER__": "karras",
                "__DENOISE__": 1.0,
                "__ORIGINAL_WIDTH__": 1024,
                "__ORIGINAL_HEIGHT__": 576,
                "__TARGET_WIDTH__": 1024,
                "__TARGET_HEIGHT__": 576,
                "__CROP_W__": 0,
                "__CROP_H__": 0,
                "__CONTROL_IMAGE__": "C:/style/control.png",
                "__CONTROL_STRENGTH__": 0.75,
                "__FILENAME_PREFIX__": "control_scene",
            },
        )
        node_10 = cast(dict[str, object], rendered["10"])
        node_14 = cast(dict[str, object], rendered["14"])
        inputs_10 = cast(dict[str, object], node_10["inputs"])
        inputs_14 = cast(dict[str, object], node_14["inputs"])
        self.assertEqual(inputs_10["image"], "C:/style/control.png")
        self.assertEqual(inputs_14["strength"], 0.75)
