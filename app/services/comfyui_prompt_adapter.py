from ..services.image_generation_profiles import micro_conditioning_values, profile_for_request
from ..types import SdxlDualPrompt
from .comfyui_workflows import PlaceholderMap


def normalize_dual_prompt(value: object) -> SdxlDualPrompt:
    if isinstance(value, dict):
        prompt_g = str(value.get("prompt_g") or "").strip()
        prompt_l = str(value.get("prompt_l") or "").strip()
        combined = str(value.get("combined") or "").strip()
        if not combined:
            combined = ", ".join(part for part in (prompt_g, prompt_l) if part)
        if not prompt_g:
            prompt_g = combined
        if not prompt_l:
            prompt_l = combined
        return {
            "prompt_g": prompt_g,
            "prompt_l": prompt_l,
            "combined": combined,
        }
    text = str(value or "").strip()
    return {
        "prompt_g": text,
        "prompt_l": text,
        "combined": text,
    }


def build_prompt_placeholders(
    *,
    positive_prompt: object,
    negative_prompt: str,
) -> PlaceholderMap:
    dual_prompt = normalize_dual_prompt(positive_prompt)
    return {
        "__POSITIVE_PROMPT__": dual_prompt["combined"],
        "__POSITIVE_PROMPT_G__": dual_prompt["prompt_g"],
        "__POSITIVE_PROMPT_L__": dual_prompt["prompt_l"],
        "__NEGATIVE_PROMPT__": negative_prompt,
        "__NEGATIVE_PROMPT_G__": negative_prompt,
        "__NEGATIVE_PROMPT_L__": negative_prompt,
    }


def apply_micro_conditioning_placeholders(
    *,
    placeholders: PlaceholderMap,
    generation_profile: str,
    width: int,
    height: int,
    original_width: int | None,
    original_height: int | None,
    target_width: int | None,
    target_height: int | None,
    crop_w: int | None,
    crop_h: int | None,
) -> PlaceholderMap:
    updated = dict(placeholders)
    updated.update(
        micro_conditioning_values(
            profile=profile_for_request(quality_mode="balanced", generation_profile=generation_profile),
            width=width,
            height=height,
            original_width=original_width,
            original_height=original_height,
            target_width=target_width,
            target_height=target_height,
            crop_w=crop_w,
            crop_h=crop_h,
        )
    )
    return updated
