from pathlib import Path
from typing import TypedDict

from ..config import COMFYUI_INSTALL_DIR


class StyleReferenceCapability(TypedDict):
    available: bool
    custom_nodes_ready: bool
    ipadapter_model_ready: bool
    clip_vision_ready: bool
    custom_node_path: str
    ipadapter_model_path: str
    clip_vision_model_path: str
    detail: str


class ControlNetCapability(TypedDict):
    available: bool
    custom_nodes_ready: bool
    controlnet_model_ready: bool
    preprocessor_ready: bool
    custom_node_path: str
    controlnet_model_path: str
    preprocessor_path: str
    detail: str


def _find_matching_file(directory: Path, needles: tuple[str, ...]) -> Path | None:
    if not directory.exists():
        return None
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        lowered = path.name.lower()
        if any(needle in lowered for needle in needles):
            return path
    return None


def _find_matching_dir(directory: Path, needles: tuple[str, ...]) -> Path | None:
    if not directory.exists():
        return None
    for path in directory.rglob("*"):
        if not path.is_dir():
            continue
        lowered = path.name.lower()
        if any(needle in lowered for needle in needles):
            return path
    return None


def get_style_reference_capability(install_dir: Path = COMFYUI_INSTALL_DIR) -> StyleReferenceCapability:
    custom_nodes_dir = install_dir / "custom_nodes"
    ipadapter_models_dir = install_dir / "models" / "ipadapter"
    clip_vision_dir = install_dir / "models" / "clip_vision"

    custom_node = _find_matching_dir(custom_nodes_dir, ("ipadapter", "ipadapter_plus", "comfyui_ipadapter_plus"))
    ipadapter_model = _find_matching_file(ipadapter_models_dir, (".bin", ".safetensors", ".pth"))
    clip_vision_model = _find_matching_file(clip_vision_dir, (".safetensors", ".bin", ".pt"))

    custom_nodes_ready = custom_node is not None
    ipadapter_model_ready = ipadapter_model is not None
    clip_vision_ready = clip_vision_model is not None
    available = custom_nodes_ready and ipadapter_model_ready and clip_vision_ready

    detail_parts: list[str] = []
    detail_parts.append(
        f"custom_nodes={'ok' if custom_nodes_ready else 'missing'}"
    )
    detail_parts.append(
        f"ipadapter_model={'ok' if ipadapter_model_ready else 'missing'}"
    )
    detail_parts.append(
        f"clip_vision={'ok' if clip_vision_ready else 'missing'}"
    )

    return {
        "available": available,
        "custom_nodes_ready": custom_nodes_ready,
        "ipadapter_model_ready": ipadapter_model_ready,
        "clip_vision_ready": clip_vision_ready,
        "custom_node_path": str(custom_node or custom_nodes_dir),
        "ipadapter_model_path": str(ipadapter_model or ipadapter_models_dir),
        "clip_vision_model_path": str(clip_vision_model or clip_vision_dir),
        "detail": ", ".join(detail_parts),
    }


def get_controlnet_depth_capability(install_dir: Path = COMFYUI_INSTALL_DIR) -> ControlNetCapability:
    custom_nodes_dir = install_dir / "custom_nodes"
    controlnet_models_dir = install_dir / "models" / "controlnet"

    custom_node = _find_matching_dir(custom_nodes_dir, ("controlnet", "comfyui_controlnet_aux", "controlnet_aux"))
    controlnet_model = _find_matching_file(controlnet_models_dir, ("depth", ".safetensors", ".pth"))
    preprocessor = _find_matching_dir(custom_nodes_dir, ("controlnet_aux", "comfyui_controlnet_aux", "depthanything"))

    custom_nodes_ready = custom_node is not None
    controlnet_model_ready = controlnet_model is not None
    preprocessor_ready = preprocessor is not None
    available = custom_nodes_ready and controlnet_model_ready and preprocessor_ready

    detail_parts: list[str] = []
    detail_parts.append(f"custom_nodes={'ok' if custom_nodes_ready else 'missing'}")
    detail_parts.append(f"controlnet_model={'ok' if controlnet_model_ready else 'missing'}")
    detail_parts.append(f"preprocessor={'ok' if preprocessor_ready else 'missing'}")

    return {
        "available": available,
        "custom_nodes_ready": custom_nodes_ready,
        "controlnet_model_ready": controlnet_model_ready,
        "preprocessor_ready": preprocessor_ready,
        "custom_node_path": str(custom_node or custom_nodes_dir),
        "controlnet_model_path": str(controlnet_model or controlnet_models_dir),
        "preprocessor_path": str(preprocessor or custom_nodes_dir),
        "detail": ", ".join(detail_parts),
    }
