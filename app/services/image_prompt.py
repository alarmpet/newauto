from __future__ import annotations

from dataclasses import dataclass

from ..types import VisualBrief

Z_IMAGE_DEFAULT_NEGATIVE_PROMPT = (
    "worst quality, low quality, lowres, blurry, out of focus, noisy, grainy, jpeg artifacts, "
    "compression artifacts, oversharpened, haloing, ringing, artifact, watermark, signature, text, "
    "logo, username, caption, frame, border, edge noise, vignette, lens dirt, deformed, disfigured, "
    "bad anatomy, extra limbs, mutated hands, poorly drawn hands, poorly drawn face, ugly, disgusting, "
    "mutated, duplicate, cropped, out of frame, off-center, aerial map, satellite map, city map, top-down map, "
    "road map, labels, captions, Korean letters, Hangul text, gibberish text, broken typography"
)


@dataclass(frozen=True)
class ImagePrompt:
    positive: str
    negative: str


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())


def _scene_prompt_from_sentence(sentence: str) -> str:
    lowered = sentence.lower()
    if any(token in sentence for token in ("젠슨", "엔비디아", "트럼프", "방중", "경제사절단")):
        return (
            "a white round-headed technology CEO character in a navy suit and red tie standing beside a simple private jet icon "
            "and small boarding stairs on a plain beige floor, a president figure calling on a phone from the side, AI semiconductor chip icon, "
            "small United States flag icon, small China flag icon, business delegation folder"
        )
    if any(token in lowered for token in ("ai", "semiconductor", "chip", "nvidia")) or any(
        token in sentence for token in ("반도체", "인공지능", "데이터센터")
    ):
        return (
            "a business character explaining an AI semiconductor chip, glowing network nodes, server building, "
            "money and investment arrows, simple editorial cartoon"
        )
    if any(token in sentence for token in ("전력", "인프라", "데이터센터")):
        return (
            "a worried business character beside an AI data center connected to power lines, warning sparks, "
            "simple infrastructure bottleneck symbol"
        )
    return (
        "a white round-headed business character explaining a news event with simple symbolic props, "
        "clear center composition"
    )


def build_z_image_prompt(
    sentence: str,
    *,
    visual_brief: VisualBrief | None = None,
    negative_prompt_override: str = "",
) -> ImagePrompt:
    clean_sentence = _clean_text(sentence)
    if not clean_sentence:
        clean_sentence = "뉴스 해설용 상징적 장면"

    hints: list[str] = []
    if visual_brief:
        for key in ("main_subject", "action", "scene", "emotion", "prompt_hint"):
            value = visual_brief.get(key)
            if isinstance(value, str) and value.strip():
                hints.append(_clean_text(value))
        must_show = visual_brief.get("must_show", [])
        if isinstance(must_show, list):
            hints.extend(_clean_text(item) for item in must_show if isinstance(item, str) and item.strip())

    unique_hints = list(dict.fromkeys(hints))
    hint_text = ", ".join(unique_hints[:6])
    scene_prompt = _scene_prompt_from_sentence(clean_sentence)
    positive = (
        "Create a flat YouTube news explainer cartoon, simple 2D vector illustration, beige background, "
        "thick black outlines, clean infographic composition. "
        f"Main scene: {scene_prompt}. "
        "Use large readable visual objects instead of written labels. "
        "Plain beige background with minimal shadow, no realistic location, no roads, no streets, no satellite texture. "
        "Camera view is straight-on eye-level, not top-down. "
        "No written words, no labels, no captions, no Hangul letters, no map, no road map, no city map, no aerial view."
    )
    if hint_text:
        positive = f"{positive} 핵심 시각 요소: {hint_text}."

    negative = _clean_text(negative_prompt_override) if negative_prompt_override.strip() else Z_IMAGE_DEFAULT_NEGATIVE_PROMPT
    return ImagePrompt(positive=positive, negative=negative)
