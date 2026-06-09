from __future__ import annotations

from fastapi import HTTPException

IMAGE_GEN_DISABLED_CODE = "IMAGE_GEN_DISABLED_D1"
IMAGE_GEN_DISABLED_MESSAGE = "Image generation is disabled until D2 Z-Image backend lands."


def disabled_payload() -> dict[str, str]:
    return {
        "error": IMAGE_GEN_DISABLED_CODE,
        "message": IMAGE_GEN_DISABLED_MESSAGE,
    }


def raise_disabled() -> None:
    raise HTTPException(status_code=503, detail=disabled_payload())
