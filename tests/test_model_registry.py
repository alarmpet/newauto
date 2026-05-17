import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.services.model_registry import list_model_status


class ModelRegistryTests(unittest.TestCase):
    def test_list_model_status_reports_missing_stickfigures_lora(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "models" / "loras").mkdir(parents=True, exist_ok=True)
            (root / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
            with patch("app.services.model_registry.COMFYUI_INSTALL_DIR", root):
                items = list_model_status()

        stickfigures = next(item for item in items if item["key"] == "comfyui_stickfigures_lora")
        self.assertFalse(stickfigures["available"])
        self.assertIn("Missing", stickfigures["detail"])

    def test_list_model_status_reports_installed_stickfigures_lora(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lora_dir = root / "models" / "loras"
            checkpoint_dir = root / "models" / "checkpoints"
            lora_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            installed = lora_dir / "Stickfigures-000005.safetensors"
            installed.write_bytes(b"stub")
            with patch("app.services.model_registry.COMFYUI_INSTALL_DIR", root):
                items = list_model_status()

        stickfigures = next(item for item in items if item["key"] == "comfyui_stickfigures_lora")
        self.assertTrue(stickfigures["available"])
        self.assertIn(installed.name, stickfigures["detail"])
        self.assertIn("Stick figure", stickfigures["detail"])

    def test_list_model_status_reports_ipadapter_style_reference_readiness(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "models" / "loras").mkdir(parents=True, exist_ok=True)
            (root / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
            (root / "models" / "ipadapter").mkdir(parents=True, exist_ok=True)
            (root / "models" / "clip_vision").mkdir(parents=True, exist_ok=True)
            (root / "custom_nodes" / "ComfyUI_IPAdapter_plus").mkdir(parents=True, exist_ok=True)
            (root / "models" / "ipadapter" / "ip-adapter_sdxl_vit-h.safetensors").write_bytes(b"stub")
            (root / "models" / "clip_vision" / "sigclip_vision_patch14_384.safetensors").write_bytes(b"stub")
            with patch("app.services.model_registry.COMFYUI_INSTALL_DIR", root):
                items = list_model_status()

        ipadapter = next(item for item in items if item["key"] == "comfyui_ipadapter_style_reference")
        self.assertTrue(ipadapter["available"])
        self.assertIn("custom_nodes=ok", ipadapter["detail"])

    def test_list_model_status_reports_controlnet_depth_readiness(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "models" / "loras").mkdir(parents=True, exist_ok=True)
            (root / "models" / "checkpoints").mkdir(parents=True, exist_ok=True)
            (root / "models" / "controlnet").mkdir(parents=True, exist_ok=True)
            (root / "custom_nodes" / "comfyui_controlnet_aux").mkdir(parents=True, exist_ok=True)
            (root / "custom_nodes" / "controlnet").mkdir(parents=True, exist_ok=True)
            (root / "models" / "controlnet" / "controlnet-depth-sdxl.safetensors").write_bytes(b"stub")
            with patch("app.services.model_registry.COMFYUI_INSTALL_DIR", root):
                items = list_model_status()

        controlnet = next(item for item in items if item["key"] == "comfyui_controlnet_depth")
        self.assertTrue(controlnet["available"])
        self.assertIn("controlnet_model=ok", controlnet["detail"])
