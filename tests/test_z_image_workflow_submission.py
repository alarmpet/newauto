import unittest
from unittest.mock import patch

from app.services.comfyui_client import ComfyImageResult, ComfyPromptSubmission, ComfyUIClient
from app.services.comfyui_pipeline import submit_z_image_workflow
from app.services.z_image_workflow import (
    CLIP_NODE_ID,
    DEFAULT_CLIP_NAME,
    DEFAULT_UNET_NAME,
    LATENT_NODE_ID,
    NEGATIVE_NODE_ID,
    POSITIVE_NODE_ID,
    SAVE_NODE_ID,
    UNET_NODE_IDS,
    load_z_image_workflow,
)


class ZImageWorkflowTests(unittest.TestCase):
    def test_loads_workflow_with_korean_positive_prompt(self) -> None:
        workflow = load_z_image_workflow(
            positive_prompt="젠슨 황 방중 경제사절단 합류 장면",
            negative_prompt="저품질",
            aspect_ratio="9:16",
            filename_prefix="smoke",
        )
        positive = workflow[str(POSITIVE_NODE_ID)]["inputs"]["text"]
        negative = workflow[str(NEGATIVE_NODE_ID)]["inputs"]["text"]
        latent = workflow[str(LATENT_NODE_ID)]["inputs"]
        save = workflow[str(SAVE_NODE_ID)]["inputs"]["filename_prefix"]
        self.assertEqual(positive, "젠슨 황 방중 경제사절단 합류 장면")
        self.assertEqual(negative, "저품질")
        self.assertEqual(workflow[str(UNET_NODE_IDS[0])]["inputs"]["unet_name"], DEFAULT_UNET_NAME)
        self.assertEqual(workflow[str(CLIP_NODE_ID)]["inputs"]["clip_name"], DEFAULT_CLIP_NAME)
        self.assertEqual(latent["width"], 768)
        self.assertEqual(latent["height"], 1344)
        self.assertEqual(save, "smoke")
        self.assertNotIn("199", workflow)

    def test_loads_workflow_with_custom_seed(self) -> None:
        workflow = load_z_image_workflow(
            positive_prompt="primordial darkness",
            negative_prompt="text",
            seed=12345,
        )

        self.assertEqual(workflow["106"]["inputs"]["seed"], 12345)

    def test_submit_accepts_legacy_worker_seed_argument(self) -> None:
        client = ComfyUIClient()
        captured: dict[str, object] = {}

        def fake_submit(workflow: dict[str, object]) -> ComfyPromptSubmission:
            captured["workflow"] = workflow
            return ComfyPromptSubmission(prompt_id="pid-seed", number=1, node_errors={})

        with (
            patch.object(client, "submit_workflow", side_effect=fake_submit),
            patch.object(client, "get_history", return_value={"pid-seed": {"outputs": {"228": {"images": [{
                "filename": "out.png",
                "subfolder": "",
                "type": "output",
            }]}}}}),
        ):
            prompt_id, _results = submit_z_image_workflow(
                client,
                positive_prompt="primordial darkness",
                negative_prompt="text",
                timeout_sec=1,
                seed=77,
            )

        workflow = captured["workflow"]
        assert isinstance(workflow, dict)
        self.assertEqual(workflow["106"]["inputs"]["seed"], 77)
        self.assertEqual(prompt_id, "pid-seed")

    def test_submits_with_korean_positive_prompt(self) -> None:
        client = ComfyUIClient()
        captured: dict[str, object] = {}

        def fake_submit(workflow: dict[str, object]) -> ComfyPromptSubmission:
            captured["workflow"] = workflow
            return ComfyPromptSubmission(prompt_id="pid-1", number=1, node_errors={})

        with (
            patch.object(client, "submit_workflow", side_effect=fake_submit),
            patch.object(client, "get_history", return_value={"pid-1": {"outputs": {"228": {"images": [{
                "filename": "out.png",
                "subfolder": "",
                "type": "output",
            }]}}}}),
        ):
            prompt_id, results = submit_z_image_workflow(
                client,
                positive_prompt="한국어 프롬프트 그대로",
                negative_prompt="저품질",
                timeout_sec=1,
            )

        workflow = captured["workflow"]
        assert isinstance(workflow, dict)
        self.assertEqual(workflow[str(POSITIVE_NODE_ID)]["inputs"]["text"], "한국어 프롬프트 그대로")
        self.assertEqual(prompt_id, "pid-1")
        self.assertEqual(results, [ComfyImageResult(filename="out.png", subfolder="", type="output")])


if __name__ == "__main__":
    unittest.main()
