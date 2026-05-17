from pathlib import Path

from ..config import COMFYUI_INSTALL_DIR, LLM_PROVIDER, SCRIPT_LLM_MODEL
from ..types import ModelStatus


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


def list_model_status() -> list[ModelStatus]:
    comfy_models_dir = COMFYUI_INSTALL_DIR / "models"
    checkpoints_dir = comfy_models_dir / "checkpoints"
    loras_dir = comfy_models_dir / "loras"
    checkpoints_count = _count_model_files(checkpoints_dir)
    loras_count = _count_model_files(loras_dir)
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
    ]
