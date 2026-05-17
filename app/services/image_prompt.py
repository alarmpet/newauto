from __future__ import annotations

from dataclasses import dataclass

from ..types import VisualBrief

Z_IMAGE_DEFAULT_NEGATIVE_PROMPT = (
    "worst quality, low quality, lowres, blurry, out of focus, noisy, grainy, jpeg artifacts, "
    "compression artifacts, oversharpened, haloing, ringing, artifact, watermark, signature, text, "
    "logo, username, caption, frame, border, edge noise, vignette, lens dirt, deformed, disfigured, "
    "bad anatomy, extra limbs, mutated hands, poorly drawn hands, poorly drawn face, ugly, disgusting, "
    "mutated, duplicate, cropped, out of frame, off-center"
)


@dataclass(frozen=True)
class ImagePrompt:
    positive: str
    negative: str


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())


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
    positive = (
        f"{clean_sentence}. 한국어 문장의 의미를 직접 반영한 뉴스 해설용 일러스트, "
        "명확한 주제, 단순하고 읽기 쉬운 구도, 자연스러운 색감, 고품질."
    )
    if hint_text:
        positive = f"{positive} 핵심 시각 요소: {hint_text}."

    negative = _clean_text(negative_prompt_override) if negative_prompt_override.strip() else Z_IMAGE_DEFAULT_NEGATIVE_PROMPT
    return ImagePrompt(positive=positive, negative=negative)
