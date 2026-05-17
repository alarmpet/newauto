from typing import Literal, TypedDict, cast

from typing_extensions import NotRequired

from ..types import QualityMode
from .parse_utils import to_int

SeedPolicy = Literal["fixed", "spaced", "random", "variant_random"]
GenerationProfileName = Literal[
    "sdxl_fast",
    "sdxl_standard",
    "sdxl_quality",
    "sdxl_low_vram_lightning",
    "sdxl_style_reference",
    "sdxl_controlnet_depth",
]


class ImageGenerationProfile(TypedDict):
    profile_name: str
    sampler_name: str
    scheduler: str
    steps: int
    cfg: float
    denoise: float
    request_timeout_sec: int
    seed_policy: SeedPolicy
    score_version: str
    workflow_template: str
    requires_lightning_checkpoint: bool
    requires_ipadapter: bool
    requires_controlnet: bool
    micro_conditioning: NotRequired[dict[str, object]]


_PROFILES: dict[QualityMode, ImageGenerationProfile] = {
    "fast": {
        "profile_name": "sdxl_fast",
        "sampler_name": "euler",
        "scheduler": "normal",
        "steps": 20,
        "cfg": 5.5,
        "denoise": 1.0,
        "request_timeout_sec": 120,
        "seed_policy": "spaced",
        "score_version": "candidate_score_v2",
        "workflow_template": "txt2img_sdxl_basic",
        "requires_lightning_checkpoint": False,
        "requires_ipadapter": False,
        "requires_controlnet": False,
        "micro_conditioning": {
            "crop_w": 0,
            "crop_h": 0,
        },
    },
    "balanced": {
        "profile_name": "sdxl_standard",
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
        "steps": 30,
        "cfg": 5.8,
        "denoise": 1.0,
        "request_timeout_sec": 180,
        "seed_policy": "spaced",
        "score_version": "candidate_score_v2",
        "workflow_template": "txt2img_sdxl_basic",
        "requires_lightning_checkpoint": False,
        "requires_ipadapter": False,
        "requires_controlnet": False,
        "micro_conditioning": {
            "crop_w": 0,
            "crop_h": 0,
        },
    },
    "exhaustive": {
        "profile_name": "sdxl_quality",
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
        "steps": 34,
        "cfg": 6.0,
        "denoise": 1.0,
        "request_timeout_sec": 240,
        "seed_policy": "variant_random",
        "score_version": "candidate_score_v2",
        "workflow_template": "txt2img_sdxl_basic",
        "requires_lightning_checkpoint": False,
        "requires_ipadapter": False,
        "requires_controlnet": False,
        "micro_conditioning": {
            "crop_w": 0,
            "crop_h": 0,
        },
    },
}

_NAMED_PROFILES: dict[GenerationProfileName, ImageGenerationProfile] = {
    "sdxl_fast": _PROFILES["fast"],
    "sdxl_standard": _PROFILES["balanced"],
    "sdxl_quality": _PROFILES["exhaustive"],
    "sdxl_low_vram_lightning": {
        "profile_name": "sdxl_low_vram_lightning",
        "sampler_name": "euler",
        "scheduler": "sgm_uniform",
        "steps": 6,
        "cfg": 2.0,
        "denoise": 1.0,
        "request_timeout_sec": 90,
        "seed_policy": "variant_random",
        "score_version": "candidate_score_v2",
        "workflow_template": "txt2img_sdxl_lightning",
        "requires_lightning_checkpoint": True,
        "requires_ipadapter": False,
        "requires_controlnet": False,
        "micro_conditioning": {
            "crop_w": 0,
            "crop_h": 0,
        },
    },
    "sdxl_style_reference": {
        "profile_name": "sdxl_style_reference",
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
        "steps": 28,
        "cfg": 5.6,
        "denoise": 1.0,
        "request_timeout_sec": 210,
        "seed_policy": "fixed",
        "score_version": "candidate_score_v2",
        "workflow_template": "txt2img_sdxl_ipadapter_style",
        "requires_lightning_checkpoint": False,
        "requires_ipadapter": True,
        "requires_controlnet": False,
        "micro_conditioning": {
            "crop_w": 0,
            "crop_h": 0,
        },
    },
    "sdxl_controlnet_depth": {
        "profile_name": "sdxl_controlnet_depth",
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
        "steps": 28,
        "cfg": 5.5,
        "denoise": 1.0,
        "request_timeout_sec": 210,
        "seed_policy": "fixed",
        "score_version": "candidate_score_v2",
        "workflow_template": "txt2img_sdxl_controlnet_depth",
        "requires_lightning_checkpoint": False,
        "requires_ipadapter": False,
        "requires_controlnet": True,
        "micro_conditioning": {
            "crop_w": 0,
            "crop_h": 0,
        },
    },
}


def normalize_quality_mode(value: object) -> QualityMode:
    if value in {"fast", "balanced", "exhaustive"}:
        return cast(QualityMode, value)
    return "fast"


def profile_for_quality_mode(value: object) -> ImageGenerationProfile:
    profile = _PROFILES[normalize_quality_mode(value)]
    return _copy_profile(profile)


def _copy_profile(profile: ImageGenerationProfile) -> ImageGenerationProfile:
    copied: ImageGenerationProfile = {
        "profile_name": profile["profile_name"],
        "sampler_name": profile["sampler_name"],
        "scheduler": profile["scheduler"],
        "steps": profile["steps"],
        "cfg": profile["cfg"],
        "denoise": profile["denoise"],
        "request_timeout_sec": profile["request_timeout_sec"],
        "seed_policy": profile["seed_policy"],
        "score_version": profile["score_version"],
        "workflow_template": profile["workflow_template"],
        "requires_lightning_checkpoint": profile["requires_lightning_checkpoint"],
        "requires_ipadapter": profile["requires_ipadapter"],
        "requires_controlnet": profile["requires_controlnet"],
    }
    if "micro_conditioning" in profile:
        copied["micro_conditioning"] = dict(profile["micro_conditioning"])
    return copied


def normalize_generation_profile_name(value: object) -> GenerationProfileName | None:
    if value in _NAMED_PROFILES:
        return cast(GenerationProfileName, value)
    return None


def profile_for_request(*, quality_mode: object, generation_profile: object = "") -> ImageGenerationProfile:
    normalized_name = normalize_generation_profile_name(generation_profile)
    if normalized_name is not None:
        return _copy_profile(_NAMED_PROFILES[normalized_name])
    return profile_for_quality_mode(quality_mode)


def profile_placeholders(profile: ImageGenerationProfile) -> dict[str, str | int | float | bool]:
    return {
        "__STEPS__": profile["steps"],
        "__CFG__": profile["cfg"],
        "__SAMPLER__": profile["sampler_name"],
        "__SCHEDULER__": profile["scheduler"],
        "__DENOISE__": profile["denoise"],
    }


def micro_conditioning_values(
    *,
    profile: ImageGenerationProfile,
    width: int,
    height: int,
    original_width: int | None = None,
    original_height: int | None = None,
    target_width: int | None = None,
    target_height: int | None = None,
    crop_w: int | None = None,
    crop_h: int | None = None,
) -> dict[str, int]:
    config = profile.get("micro_conditioning", {})
    original_w = original_width if original_width is not None else width
    original_h = original_height if original_height is not None else height
    target_w = target_width if target_width is not None else width
    target_h = target_height if target_height is not None else height
    resolved_crop_w = crop_w if crop_w is not None else to_int(config.get("crop_w", 0), 0)
    resolved_crop_h = crop_h if crop_h is not None else to_int(config.get("crop_h", 0), 0)
    return {
        "__ORIGINAL_WIDTH__": original_w,
        "__ORIGINAL_HEIGHT__": original_h,
        "__TARGET_WIDTH__": target_w,
        "__TARGET_HEIGHT__": target_h,
        "__CROP_W__": resolved_crop_w,
        "__CROP_H__": resolved_crop_h,
    }


def normalize_seed_policy(value: object, default: SeedPolicy = "spaced") -> SeedPolicy:
    if value in {"fixed", "spaced", "random", "variant_random"}:
        return cast(SeedPolicy, value)
    return default
