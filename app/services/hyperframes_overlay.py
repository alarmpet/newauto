import html
import json
import shutil
from pathlib import Path
from typing import Any, TypedDict

OVERLAY_DIR_NAME = "hyperframes_overlay"
OVERLAY_PLAN_NAME = "overlay_plan.json"
OVERLAY_WEBM_NAME = "overlay.webm"
OVERLAY_REPORT_NAME = "overlay_report.json"


class OverlayWritePaths(TypedDict):
    index_html: Path
    overlay_plan: Path


def _keyword_for_text(text: str) -> str:
    if "경제사절단" in text or "사절단" in text:
        return "경제사절단 합류"
    if "엔비디아" in text or "Nvidia" in text:
        return "엔비디아 공식 확인"
    if "직접 요청" in text or "요청" in text:
        return "직접 요청"
    if "알래스카" in text or "베이징" in text:
        return "알래스카 경유"
    compact = "".join(str(text).split())
    return compact[:12] or "뉴스 요약"


def _normalize_overlay_item(raw: dict[str, Any]) -> dict[str, Any]:
    overlay_type = str(raw.get("overlay_type") or "").strip()
    if overlay_type != "label_plate":
        return dict(raw)
    raw_box = raw.get("box")
    box = raw_box if isinstance(raw_box, list) and len(raw_box) == 4 else [96, 96, 480, 120]
    return {
        "sentence_idx": int(raw.get("sentence_idx", 0) or 0),
        "start": float(raw.get("start", 0.0) or 0.0),
        "end": float(raw.get("end", 1.0) or 1.0),
        "overlay_type": "label_plate",
        "text": str(raw.get("text", "") or ""),
        "box": [int(float(value)) for value in box],
        "font_weight": int(raw.get("font_weight", 800) or 800),
        "fit": str(raw.get("fit", "shrink_to_box") or "shrink_to_box"),
    }


def build_overlay_plan(
    timings: list[dict[str, Any]],
    *,
    overlay_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for raw in timings:
        start = float(raw.get("start", 0.0))
        end = float(raw.get("end", start + 1.0))
        text = str(raw.get("text", ""))
        sentence_idx = int(raw.get("sentence_idx", len(items)))
        items.append(
            {
                "sentence_idx": sentence_idx,
                "start": start,
                "end": end,
                "overlay_type": "lower_third_keyword",
                "text": _keyword_for_text(text),
                "secondary": "NewAuto Studio",
                "position": "upper_left" if sentence_idx % 2 else "lower_left",
            }
        )
    if overlay_items:
        items.extend(_normalize_overlay_item(raw) for raw in overlay_items)
    duration = max((float(item["end"]) for item in items), default=0.0)
    template = "stickman_explainer_overlay" if overlay_items else "lower_third_keyword"
    version = 2 if overlay_items else 1
    return {"version": version, "template": template, "duration_sec": duration, "items": items}


def _copy_local_korean_font(font_dir: Path) -> None:
    source = resolve_korean_font_source()
    font_dir.mkdir(parents=True, exist_ok=True)
    target = font_dir / "NotoSansKR-Regular.ttf"
    if target.exists():
        return
    shutil.copy2(source, target)


def resolve_korean_font_source() -> Path:
    source_candidates = [
        Path("C:/Windows/Fonts/NotoSansKR-VF.ttf"),
        Path("C:/Windows/Fonts/malgun.ttf"),
    ]
    for source in source_candidates:
        if source.exists():
            return source
    raise FileNotFoundError("No local Korean font found for HyperFrames overlay rendering")


def _render_html(plan: dict[str, Any], *, width: int, height: int) -> str:
    blocks = []
    for item in plan["items"]:
        duration = max(0.1, float(item["end"]) - float(item["start"]))
        overlay_type = str(item.get("overlay_type") or "")
        if overlay_type == "label_plate":
            box = item.get("box")
            if not isinstance(box, list) or len(box) != 4:
                box = [96, 96, 480, 120]
            left, top, box_width, box_height = [int(float(value)) for value in box]
            font_weight = int(item.get("font_weight", 800) or 800)
            blocks.append(
                (
                    f'<div id="overlay-label-{int(item["sentence_idx"])}" class="clip label-plate" '
                    f'data-start="{float(item["start"]):.3f}" data-duration="{duration:.3f}" data-track-index="2" '
                    f'style="left:{left}px; top:{top}px; width:{box_width}px; height:{box_height}px;">'
                    f'<div class="label-fit" style="font-weight:{font_weight};">{html.escape(str(item["text"]))}</div>'
                    "</div>"
                )
            )
            continue
        blocks.append(
            (
                f'<div id="overlay-{int(item["sentence_idx"])}" class="clip overlay {html.escape(str(item["position"]))}" '
                f'data-start="{float(item["start"]):.3f}" data-duration="{duration:.3f}" data-track-index="1">'
                f'<div class="keyword">{html.escape(str(item["text"]))}</div>'
                f'<div class="secondary">{html.escape(str(item["secondary"]))}</div>'
                "</div>"
            )
        )
    duration_sec = max(0.1, float(plan["duration_sec"]))
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    @font-face {{
      font-family: 'PretendardLocal';
      src: url('assets/fonts/NotoSansKR-Regular.ttf') format('truetype');
      font-weight: 400;
      font-display: block;
    }}
    @font-face {{
      font-family: 'PretendardLocal';
      src: url('assets/fonts/NotoSansKR-Regular.ttf') format('truetype');
      font-weight: 700;
      font-display: block;
    }}
    html, body {{ margin: 0; width: {width}px; height: {height}px; background: transparent; overflow: hidden; }}
    body {{ font-family: 'PretendardLocal', sans-serif; }}
    .overlay {{ position: absolute; max-width: 520px; padding: 18px 22px; background: rgba(0,0,0,.68); color: white; border-left: 6px solid #58c4ff; }}
    .lower_left {{ left: 72px; bottom: 190px; }}
    .upper_left {{ left: 72px; top: 92px; }}
    .keyword {{ font-size: 42px; font-weight: 700; line-height: 1.12; }}
    .secondary {{ margin-top: 8px; font-size: 22px; opacity: .86; }}
    .label-plate {{ position: absolute; display: flex; align-items: center; justify-content: center; padding: 10px 18px; box-sizing: border-box; color: #111827; background: rgba(255,255,255,.92); border: 4px solid #111827; border-radius: 10px; }}
    .label-fit {{ max-width: 100%; max-height: 100%; overflow-wrap: anywhere; text-align: center; line-height: 1.08; font-size: clamp(22px, 4.2vw, 72px); }}
  </style>
</head>
<body>
  <div id="stage" data-composition-id="newauto-overlay" data-start="0" data-duration="{duration_sec:.3f}" data-width="{width}" data-height="{height}">
    {"".join(blocks)}
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    window.__timelines["newauto-overlay"] = {{
      duration: () => {duration_sec:.3f},
      pause: () => window.__timelines["newauto-overlay"],
      seek: () => window.__timelines["newauto-overlay"],
      time: () => 0
    }};
  </script>
</body>
</html>
"""


def write_overlay_project(
    out_dir: Path,
    timings: list[dict[str, Any]],
    *,
    width: int,
    height: int,
    overlay_items: list[dict[str, Any]] | None = None,
) -> OverlayWritePaths:
    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = out_dir / "assets"
    _copy_local_korean_font(assets_dir / "fonts")
    plan = build_overlay_plan(timings, overlay_items=overlay_items)
    overlay_plan = out_dir / OVERLAY_PLAN_NAME
    index_html = out_dir / "index.html"
    overlay_plan.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    index_html.write_text(_render_html(plan, width=width, height=height), encoding="utf-8")
    return {"index_html": index_html, "overlay_plan": overlay_plan}
