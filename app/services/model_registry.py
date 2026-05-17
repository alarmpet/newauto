from pathlib import Path

from ..config import COMFYUI_INSTALL_DIR, LLM_PROVIDER, SCRIPT_LLM_MODEL
from ..types import ModelStatus
from .comfyui_capabilities import get_controlnet_depth_capability, get_style_reference_capability


def _model(
    *,
    key: str,
    label: str,
    available: bool,
    source: str,
    path: str,
    detail: str,
) -> ModelStatus:
    return {
        "key": key,
        "label": label,
        "available": available,
        "source": source,
        "path": path,
        "detail": detail,
    }


def _count_model_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.rglob("*") if path.is_file())


def _find_stickfigures_lora(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        lowered = path.name.lower()
        if "stickfigure" in lowered or "stickfigures" in lowered:
            return path
    return None


def list_model_status() -> list[ModelStatus]:
    comfy_models_dir = COMFYUI_INSTALL_DIR / "models"
    checkpoints_dir = comfy_models_dir / "checkpoints"
    loras_dir = comfy_models_dir / "loras"
    checkpoints_count = _count_model_files(checkpoints_dir)
    loras_count = _count_model_files(loras_dir)
    stickfigures_lora = _find_stickfigures_lora(loras_dir)
    style_reference = get_style_reference_capability(COMFYUI_INSTALL_DIR)
    controlnet_depth = get_controlnet_depth_capability(COMFYUI_INSTALL_DIR)

    return [
        _model(
            key="script_llm",
            label="Script LLM",
            available=bool(SCRIPT_LLM_MODEL.strip()),
            source=LLM_PROVIDER,
            path=SCRIPT_LLM_MODEL,
            detail="Article and research based script generation model.",
        ),
        _model(
            key="omnivoice",
            label="OmniVoice",
            available=True,
            source="huggingface",
            path="k2-fsa/OmniVoice",
            detail="Lazy-loaded TTS voice model.",
        ),
        _model(
            key="comfyui_checkpoints",
            label="ComfyUI Checkpoints",
            available=checkpoints_count > 0,
            source="filesystem",
            path=str(checkpoints_dir),
            detail=f"Checkpoint files: {checkpoints_count}",
        ),
        _model(
            key="comfyui_loras",
            label="ComfyUI LoRAs",
            available=loras_count > 0,
            source="filesystem",
            path=str(loras_dir),
            detail=f"LoRA files: {loras_count}",
        ),
        _model(
            key="comfyui_stickfigures_lora",
            label="Stickfigures LoRA",
            available=stickfigures_lora is not None,
            source="filesystem",
            path=str(stickfigures_lora or loras_dir),
            detail=(
                f"Ready: {stickfigures_lora.name} | trigger words Flipchartvisu, Stick figure"
                if stickfigures_lora is not None
                else "Missing. Install a Stickfigures LoRA file to make stickman prompts more stable."
            ),
        ),
        _model(
            key="comfyui_ipadapter_style_reference",
            label="IPAdapter Style Reference",
            available=style_reference["available"],
            source="filesystem",
            path=style_reference["custom_node_path"],
            detail=(
                f"Ready. {style_reference['detail']}"
                if style_reference["available"]
                else f"Missing pieces. {style_reference['detail']}"
            ),
        ),
        _model(
            key="comfyui_controlnet_depth",
            label="ControlNet Depth",
            available=controlnet_depth["available"],
            source="filesystem",
            path=controlnet_depth["custom_node_path"],
            detail=(
                f"Ready. {controlnet_depth['detail']}"
                if controlnet_depth["available"]
                else f"Missing pieces. {controlnet_depth['detail']}"
            ),
        ),
    ]
