import json
import unittest
from typing import cast
from unittest.mock import patch

from fastapi import HTTPException

from app.services.comfyui_client import ComfyImageResult, ComfyPromptSubmission, ComfyUIClient


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class ComfyClientTests(unittest.TestCase):
    def test_submit_workflow_returns_prompt_submission(self) -> None:
        client = ComfyUIClient(base_url="http://127.0.0.1:8188")
        with patch("app.services.comfyui_client.urlopen", return_value=_FakeResponse({
            "prompt_id": "abc123",
            "number": 7,
            "node_errors": {},
        })):
            submission = client.submit_workflow({"1": {"class_type": "SaveImage"}})
        self.assertEqual(
            submission,
            ComfyPromptSubmission(prompt_id="abc123", number=7, node_errors={}),
        )

    def test_extract_image_results_reads_history_outputs(self) -> None:
        client = ComfyUIClient()
        history = {
            "abc123": {
                "outputs": {
                    "9": {
                        "images": [
                            {
                                "filename": "image_0001.png",
                                "subfolder": "",
                                "type": "output",
                            }
                        ]
                    }
                }
            }
        }
        self.assertEqual(
            client.extract_image_results(cast(dict[str, object], history), "abc123"),
            [ComfyImageResult(filename="image_0001.png", subfolder="", type="output")],
        )

    def test_get_history_raises_for_invalid_json_shape(self) -> None:
        client = ComfyUIClient(base_url="http://127.0.0.1:8188")
        with patch("app.services.comfyui_client.urlopen", return_value=_FakeResponse(["bad"])):
            with self.assertRaises(HTTPException) as captured:
                client.get_history("abc123")
        self.assertEqual(captured.exception.status_code, 502)

    def test_extract_execution_error_reads_history_status(self) -> None:
        client = ComfyUIClient()
        history = {
            "abc123": {
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
                }
            }
        }
        self.assertEqual(
            client.extract_execution_error(cast(dict[str, object], history), "abc123"),
            "ComfyUI KSampler failed: [Errno 22] Invalid argument",
        )
