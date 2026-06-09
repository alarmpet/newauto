from __future__ import annotations

from pathlib import Path

from ..config import COMFYUI_INSTALL_DIR
from .z_image_workflow import DEFAULT_CLIP_NAME, DEFAULT_UNET_NAME, DEFAULT_VAE_NAME

Z_IMAGE_REQUIRED_FILES = {
    "unet": Path("models/unet") / DEFAULT_UNET_NAME,
    "clip": Path("models/clip") / DEFAULT_CLIP_NAME,
    "vae": Path("models/vae") / DEFAULT_VAE_NAME,
    "rgthree": Path("custom_nodes/rgthree-comfy/__init__.py"),
}


def z_image_readiness(install_dir: Path = COMFYUI_INSTALL_DIR) -> dict[str, object]:
    checks = {
        name: {
            "path": str(install_dir / relative),
            "ok": (install_dir / relative).exists(),
        }
        for name, relative in Z_IMAGE_REQUIRED_FILES.items()
    }
    return {
        "ok": all(bool(item["ok"]) for item in checks.values()),
        "checks": checks,
    }
