from __future__ import annotations

from typing import TypedDict


class LegacyImageCapability(TypedDict):
    available: bool
    detail: str
    custom_node_path: str


def disabled_image_capability() -> LegacyImageCapability:
    return {
        "available": False,
        "detail": "Legacy image generation capability disabled during D1.",
        "custom_node_path": "",
    }
