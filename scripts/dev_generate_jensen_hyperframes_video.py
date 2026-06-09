from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.services.render import run_render_job


SCRIPT = (
    "당초 명단 제외설이 돌며 반도체 업계를 술렁이게 했던 젠슨 황(Jensen Huang) "
    "엔비디아(Nvidia) CEO가 도널드 트럼프 대통령의 직접적인 요청으로 방중 경제사절단에 극적으로 합류했다.\n\n"
    "13일(현지시간) CNBC 등 주요 외신에 따르면, 엔비디아는 젠슨 황 CEO가 트럼프 대통령의 "
    "방중 일정에 동행한다는 사실을 공식 확인했다. 소식통에 따르면 트럼프 대통령은 젠슨 황의 "
    "사절단 제외 소식을 다룬 소식을 접한 뒤 직접 그에게 전화를 걸어 합류를 요청한 것으로 알려졌다. "
    "이에 따라 젠슨 황은 에어포스원이 중간 기착한 알래스카에서 전격 탑승해 베이징행에 몸을 실었다."
)

SENTENCES = [
    "당초 명단 제외설이 돌며 반도체 업계를 술렁이게 했던 젠슨 황 엔비디아 CEO가 도널드 트럼프 대통령의 직접적인 요청으로 방중 경제사절단에 극적으로 합류했다.",
    "13일 현지시간 CNBC 등 주요 외신에 따르면, 엔비디아는 젠슨 황 CEO가 트럼프 대통령의 방중 일정에 동행한다는 사실을 공식 확인했다.",
    "소식통에 따르면 트럼프 대통령은 젠슨 황의 사절단 제외 소식을 다룬 보도를 접한 뒤 직접 그에게 전화를 걸어 합류를 요청한 것으로 알려졌다.",
    "이에 따라 젠슨 황은 에어포스원이 중간 기착한 알래스카에서 전격 탑승해 베이징행에 몸을 실었다.",
]

SCENES = [
    {
        "title": "젠슨 황, 방중 경제사절단 합류",
        "kicker": "NVIDIA CEO",
        "body": "제외설 이후\n트럼프 직접 요청",
        "accent": (110, 231, 183),
    },
    {
        "title": "엔비디아 공식 확인",
        "kicker": "CNBC · 주요 외신",
        "body": "방중 일정 동행\n공식 발표",
        "accent": (96, 165, 250),
    },
    {
        "title": "직접 통화로 합류 요청",
        "kicker": "White House Call",
        "body": "보도 확인 뒤\n전화 요청",
        "accent": (251, 191, 36),
    },
    {
        "title": "알래스카 경유, 베이징행",
        "kicker": "Air Force One",
        "body": "중간 기착지에서\n전격 탑승",
        "accent": (248, 113, 113),
    },
]


ID_FILE = ROOT / "storage" / "projects" / "_latest_jensen_hyperframes_id.txt"
FONT_PATH = Path("C:/Windows/Fonts/NotoSansKR-VF.ttf")
FALLBACK_FONT_PATH = Path("C:/Windows/Fonts/malgun.ttf")


def _font(size: int) -> ImageFont.FreeTypeFont:
    path = FONT_PATH if FONT_PATH.exists() else FALLBACK_FONT_PATH
    return ImageFont.truetype(str(path), size=size)


def _wrap(text: str, width: int) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        lines.extend(textwrap.wrap(raw_line, width=width) or [""])
    return "\n".join(lines)


def _draw_scene(path: Path, scene: dict[str, object], index: int) -> None:
    width, height = 1920, 1080
    image = Image.new("RGB", (width, height), (10, 14, 22))
    draw = ImageDraw.Draw(image)
    accent = scene["accent"]
    assert isinstance(accent, tuple)

    for y in range(height):
        shade = int(18 + y / height * 24)
        draw.line([(0, y), (width, y)], fill=(shade, shade + 4, shade + 12))

    draw.rectangle((84, 78, 1836, 1002), outline=(52, 65, 85), width=4)
    draw.rectangle((118, 112, 1802, 968), fill=(15, 23, 42), outline=(71, 85, 105), width=2)
    draw.rectangle((118, 112, 1802, 230), fill=(20, 30, 50))
    draw.rectangle((118, 230, 1802, 238), fill=accent)

    draw.text((152, 142), str(scene["kicker"]), fill=accent, font=_font(44))
    draw.text((152, 286), str(scene["title"]), fill=(248, 250, 252), font=_font(82))
    draw.multiline_text((152, 430), _wrap(str(scene["body"]), 15), fill=(226, 232, 240), font=_font(68), spacing=18)

    card_x, card_y = 1160, 360
    draw.rounded_rectangle((card_x, card_y, card_x + 500, card_y + 420), radius=28, fill=(30, 41, 59), outline=accent, width=5)
    draw.ellipse((card_x + 72, card_y + 72, card_x + 220, card_y + 220), fill=(51, 65, 85), outline=accent, width=5)
    draw.rectangle((card_x + 285, card_y + 92, card_x + 430, card_y + 132), fill=accent)
    draw.rectangle((card_x + 285, card_y + 166, card_x + 430, card_y + 206), fill=(148, 163, 184))
    draw.line((card_x + 160, card_y + 270, card_x + 405, card_y + 330), fill=accent, width=12)
    draw.polygon([(card_x + 405, card_y + 330), (card_x + 358, card_y + 298), (card_x + 370, card_y + 362)], fill=accent)
    draw.text((card_x + 72, card_y + 300), f"SCENE {index + 1}", fill=(203, 213, 225), font=_font(40))

    draw.text((152, 888), "HyperFrames editorial overlay test", fill=(148, 163, 184), font=_font(34))
    image.save(path)


def create_project() -> str:
    db.init_db()
    created = db.create_project("jensen-nvidia-hyperframes-regenerated")
    pid = created["id"]
    project_dir = db.project_dir(pid)
    media_dir = project_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    media_order = []
    mappings = []
    for index, scene in enumerate(SCENES):
        name = f"scene{index}.png"
        _draw_scene(media_dir / name, scene, index)
        media_order.append(name)
        mappings.append({"sentence_idx": index, "path": name, "source": "dev_generated"})
    db.update_project(
        pid,
        script=SCRIPT,
        compiled_script="\n".join(SENTENCES),
        regional_sentences=[{"idx": i, "text": sentence, "region": "body"} for i, sentence in enumerate(SENTENCES)],
        sentences=SENTENCES,
        media_order=media_order,
        body_image_mappings=mappings,
        render_formats=["landscape"],
        kenburns_enabled=True,
        body_image_options={
            "hyperframes_overlay_enabled": True,
            "hyperframes_overlay_required": True,
            "allow_visual_relevance_warnings_for_render": True,
        },
    )
    ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    ID_FILE.write_text(pid, encoding="utf-8")
    print(pid)
    return pid


def _pid(value: str | None) -> str:
    if value:
        return value
    return ID_FILE.read_text(encoding="utf-8").strip()


def finalize_and_render(pid: str) -> None:
    db.init_db()
    project_dir = db.project_dir(pid)
    timings = json.loads((project_dir / "tts" / "timings.json").read_text(encoding="utf-8-sig"))
    segments = []
    for index, timing in enumerate(timings):
        media_name = f"scene{index}.png"
        segments.append(
            {
                "region": "body",
                "start": float(timing["start"]),
                "end": float(timing["end"]),
                "sentence_idx": index,
                "media": [{"path": media_name, "kind": "image"}],
                "motion": "micro_motion_locked",
                "effect": "none",
                "caption_style": "emphasis" if index in {0, 3} else "default",
            }
        )
    db.update_project(
        pid,
        render_plan={
            "version": 2,
            "total_duration": float(timings[-1]["end"]) if timings else 0.0,
            "segments": segments,
        },
    )
    run_render_job(pid)
    project = db.get_project(pid)
    if project is None:
        raise RuntimeError(f"Project disappeared: {pid}")
    if project["render_state"] != "done":
        raise RuntimeError(project["render_error"] or "render did not complete")
    print(project_dir / "output.mp4")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "render"])
    parser.add_argument("--project-id")
    args = parser.parse_args()
    if args.action == "create":
        create_project()
    else:
        finalize_and_render(_pid(args.project_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
