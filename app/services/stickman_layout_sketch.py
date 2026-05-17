from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from PIL import Image, ImageDraw

from .. import db
from ..types import ProjectRecord


class StickmanLayoutSketch(TypedDict):
    template_key: str
    path: str
    width: int
    height: int
    note: str


BACKGROUND = (214, 209, 195)
INK = (28, 31, 33)
GUIDE = (126, 134, 135)
BLUE = (146, 188, 208)
NAVY = (35, 73, 108)
RED = (206, 63, 49)
GREEN = (112, 161, 105)
GOLD = (218, 169, 66)
WHITE = (244, 246, 244)


def _line(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], *, fill=INK, width: int = 5) -> None:
    draw.line(points, fill=fill, width=width, joint="curve")


def _stickman_business(draw: ImageDraw.ImageDraw, x: int, y: int, *, worried: bool = False) -> None:
    draw.ellipse((x - 28, y - 92, x + 28, y - 36), fill=WHITE, outline=INK, width=4)
    draw.line((x - 32, y - 28, x + 32, y - 28), fill=INK, width=4)
    draw.polygon([(x - 28, y - 28), (x + 28, y - 28), (x + 20, y + 60), (x - 20, y + 60)], fill=NAVY, outline=INK)
    draw.polygon([(x - 7, y - 26), (x + 7, y - 26), (x + 4, y + 28), (x - 4, y + 28)], fill=RED, outline=INK)
    draw.line((x - 20, y + 60, x - 36, y + 104), fill=INK, width=5)
    draw.line((x + 20, y + 60, x + 36, y + 104), fill=INK, width=5)
    draw.line((x - 24, y, x - 56, y + 30), fill=INK, width=5)
    draw.line((x + 24, y, x + 56, y + 30), fill=INK, width=5)
    draw.ellipse((x - 13, y - 70, x - 7, y - 62), fill=INK)
    draw.ellipse((x + 7, y - 70, x + 13, y - 62), fill=INK)
    if worried:
        draw.arc((x - 14, y - 58, x + 14, y - 38), 200, 340, fill=INK, width=3)
        draw.arc((x - 17, y - 81, x - 1, y - 70), 205, 330, fill=INK, width=3)
        draw.arc((x + 1, y - 81, x + 17, y - 70), 210, 335, fill=INK, width=3)
    else:
        draw.arc((x - 14, y - 62, x + 14, y - 44), 20, 160, fill=INK, width=3)


def _draw_machine_pipeline(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    cy = height // 2 + 10
    draw.rounded_rectangle((width * 0.35, 35, width * 0.65, 95), radius=8, fill=WHITE, outline=INK, width=5)
    draw.rectangle((width * 0.47, 95, width * 0.53, 150), fill=GUIDE, outline=INK, width=4)
    draw.rounded_rectangle((60, cy - 95, width * 0.47, cy + 95), radius=32, fill=(188, 208, 213), outline=INK, width=6)
    draw.rounded_rectangle((width * 0.53, cy - 95, width - 70, cy + 95), radius=32, fill=(188, 208, 213), outline=INK, width=6)
    draw.rectangle((width * 0.46, cy - 45, width * 0.54, cy + 45), fill=GUIDE, outline=INK, width=5)
    for gx, gy, r in [(210, cy - 24, 38), (285, cy + 42, 32), (350, cy - 15, 30)]:
        draw.ellipse((gx - r, gy - r, gx + r, gy + r), outline=INK, width=5)
        draw.ellipse((gx - 10, gy - 10, gx + 10, gy + 10), outline=INK, width=4)
    draw.pieslice((10, 55, 160, 205), 205, 315, fill=RED, outline=INK, width=5)
    draw.polygon([(135, 53), (177, 116), (104, 111)], fill=RED, outline=INK)
    for nx, ny in [(550, cy - 35), (620, cy - 70), (690, cy - 30), (585, cy + 25), (660, cy + 40), (735, cy + 5)]:
        draw.ellipse((nx - 8, ny - 8, nx + 8, ny + 8), fill=GOLD, outline=INK, width=3)
    for a, b in [((550, cy - 35), (620, cy - 70)), ((550, cy - 35), (585, cy + 25)), ((620, cy - 70), (690, cy - 30)), ((690, cy - 30), (735, cy + 5)), ((585, cy + 25), (660, cy + 40)), ((660, cy + 40), (735, cy + 5))]:
        _line(draw, [a, b], fill=GUIDE, width=3)
    draw.rounded_rectangle((95, height - 88, 345, height - 38), radius=4, fill=WHITE, outline=INK, width=4)
    draw.rounded_rectangle((width - 365, height - 88, width - 95, height - 38), radius=4, fill=WHITE, outline=INK, width=4)


def _draw_infrastructure_bottleneck(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    cy = height // 2
    for y in [110, 165, 220, 275]:
        _line(draw, [(0, y), (310, cy - 55 + (y - 110) // 2), (435, cy - 20 + (y - 110) // 6)], width=5)
    draw.polygon([(360, cy - 105), (535, cy - 42), (535, cy + 42), (360, cy + 105)], fill=(194, 216, 226), outline=INK)
    draw.polygon([(535, cy - 42), (640, cy - 18), (640, cy + 18), (535, cy + 42)], fill=(185, 204, 214), outline=INK)
    for y in [cy - 28, cy, cy + 28]:
        _line(draw, [(640, y), (width - 230, y - 45)], width=5)
        draw.line((width - 250, y - 56, width - 230, y - 45, width - 252, y - 34), fill=GOLD, width=4)
    draw.rectangle((width - 185, 105, width - 50, height - 78), fill=BLUE, outline=INK, width=5)
    for x in range(width - 165, width - 65, 35):
        draw.line((x, 110, x, height - 84), fill=GUIDE, width=2)
    for y in range(135, height - 95, 48):
        draw.line((width - 184, y, width - 51, y), fill=GUIDE, width=2)
    draw.text((width - 142, 190), "AI", fill=GUIDE)
    _stickman_business(draw, 140, height - 108, worried=True)
    draw.rounded_rectangle((width - 365, 40, width - 95, 88), radius=4, fill=WHITE, outline=INK, width=4)


def _draw_scale_comparison(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    cx = width // 2
    base_y = height - 88
    draw.rectangle((cx - 38, base_y - 135, cx + 38, base_y), fill=(186, 202, 208), outline=INK, width=5)
    draw.rounded_rectangle((cx - 120, base_y, cx + 120, base_y + 30), radius=5, fill=(188, 208, 213), outline=INK, width=5)
    _line(draw, [(cx - 305, base_y - 150), (cx + 305, base_y - 190)], width=5)
    draw.ellipse((cx - 18, base_y - 170, cx + 18, base_y - 134), fill=WHITE, outline=INK, width=4)
    for tray_cx, tray_y, high in [(cx - 305, base_y - 110, False), (cx + 305, base_y - 150, True)]:
        draw.arc((tray_cx - 120, tray_y - 16, tray_cx + 120, tray_y + 42), 0, 180, fill=INK, width=5)
        draw.line((tray_cx - 118, tray_y + 13, tray_cx + 118, tray_y + 13), fill=INK, width=5)
        _stickman_business(draw, tray_cx - 55, tray_y + 25)
        blocks = 3 if not high else 9
        for i in range(blocks):
            bx = tray_cx + 12 + (i % 3) * 28
            by = tray_y - 22 - (i // 3) * 26
            draw.rectangle((bx, by, bx + 24, by + 22), fill=BLUE if i % 2 == 0 else GOLD, outline=INK, width=3)
        draw.rounded_rectangle((tray_cx - 95, 42, tray_cx + 95, 86), radius=4, fill=WHITE, outline=INK, width=4)


DRAWERS = {
    "machine_pipeline": _draw_machine_pipeline,
    "infrastructure_bottleneck": _draw_infrastructure_bottleneck,
    "scale_comparison": _draw_scale_comparison,
}


def build_stickman_layout_sketches(
    project: ProjectRecord,
    *,
    template_keys: list[str] | None = None,
    width: int = 768,
    height: int = 432,
) -> list[StickmanLayoutSketch]:
    selected = template_keys or list(DRAWERS)
    output_dir = db.project_dir(project["id"]) / "diagnostics_bundle" / "stickman_evidence" / "layout_sketches"
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[StickmanLayoutSketch] = []
    for template_key in selected:
        drawer = DRAWERS.get(template_key)
        if drawer is None:
            continue
        image = Image.new("RGB", (width, height), BACKGROUND)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, height - 58, width, height), fill=(190, 186, 174))
        draw.line((0, height - 58, width, height - 58), fill=GUIDE, width=3)
        drawer(draw, width, height)
        path = output_dir / f"{template_key}_layout_sketch.png"
        image.save(path)
        results.append(
            {
                "template_key": template_key,
                "path": str(path),
                "width": width,
                "height": height,
                "note": "Deterministic composition guide for ControlNet/layout-conditioned stickman business generation.",
            }
        )
    manifest_path = output_dir / "layout_sketches_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "project_id": project["id"],
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "items": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return results
