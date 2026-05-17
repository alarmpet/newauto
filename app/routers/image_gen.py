import json
from pathlib import Path
from collections.abc import Mapping

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .. import db
from ..services.comfyui_client import ComfyUIClient
from ..services.comfyui_capabilities import get_controlnet_depth_capability, get_style_reference_capability
from ..services.comfyui_pipeline import import_history_image, submit_template
from ..services.comfyui_prompt_adapter import apply_micro_conditioning_placeholders, build_prompt_placeholders
from ..services.image_prompting import (
    save_image_prompt_manifest,
    suggest_image_prompt,
    suggest_image_prompt_batch,
)
from ..services.image_generation_profiles import (
    micro_conditioning_values,
    normalize_generation_profile_name,
    normalize_seed_policy,
    profile_for_request,
)
from ..services.parse_utils import clamp_float, to_float, to_int
from ..services.prompt_quality import build_prompt_quality_report
from ..services.visual_relevance import sentence_hash, write_visual_contact_sheet, write_visual_mismatch_report
from ..services.comfyui_workflows import PlaceholderMap, render_workflow_template
from ..services.lmstudio_runtime import loaded_lmstudio_models, unload_lmstudio_model
from ..types import ProjectRecord, QualityMode

router = APIRouter(prefix="/api/projects", tags=["image-gen"])

_BLOCKING_PROMPT_QUALITY_CODES = {
    "EV_BATTERY_PROMPT_QUALITY_FAILED",
    "GENERIC_FALLBACK_BLOCKED",
    "GENERIC_MUST_SHOW_REPEATED",
    "FOOD_TREND_PROMPT_QUALITY_FAILED",
    "NEWS_EXPLAINER_PROMPT_QUALITY_FAILED",
}


class ComfyWorkflowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = "txt2img_sdxl_basic"
    checkpoint: str = Field(min_length=1, max_length=200)
    positive_prompt: str = Field(min_length=1, max_length=2000)
    positive_prompt_g: str = Field(default="", max_length=2000)
    positive_prompt_l: str = Field(default="", max_length=2000)
    negative_prompt: str = Field(default="", max_length=1000)
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=576, ge=256, le=2048)
    seed: int = Field(default=1, ge=0, le=2147483647)
    steps: int = Field(default=30, ge=1, le=150)
    cfg: float = Field(default=5.8, ge=0.0, le=30.0)
    sampler_name: str = Field(default="dpmpp_2m", min_length=1, max_length=80)
    scheduler: str = Field(default="karras", min_length=1, max_length=80)
    denoise: float = Field(default=1.0, ge=0.0, le=1.0)
    generation_profile: str = Field(default="sdxl_standard", max_length=100)
    score_version: str = Field(default="candidate_score_v2", max_length=80)
    request_timeout_sec: int = Field(default=180, ge=1, le=3600)
    style_reference_image: str = Field(default="", max_length=400)
    style_reference_strength: float = Field(default=0.65, ge=0.0, le=2.0)
    control_image: str = Field(default="", max_length=400)
    control_strength: float = Field(default=0.75, ge=0.0, le=2.0)
    original_width: int | None = Field(default=None, ge=256, le=4096)
    original_height: int | None = Field(default=None, ge=256, le=4096)
    target_width: int | None = Field(default=None, ge=256, le=4096)
    target_height: int | None = Field(default=None, ge=256, le=4096)
    crop_w: int | None = Field(default=None, ge=0, le=4096)
    crop_h: int | None = Field(default=None, ge=0, le=4096)
    filename_prefix: str = Field(default="newauto")
    client_id: str = Field(default="newauto", min_length=1, max_length=100)
    lora_name: str = Field(default="", max_length=200)
    lora_strength: float = Field(default=0.8, ge=0.0, le=2.0)

    def placeholders(self) -> PlaceholderMap:
        placeholders: PlaceholderMap = {
            "__CHECKPOINT__": self.checkpoint,
            "__WIDTH__": self.width,
            "__HEIGHT__": self.height,
            "__SEED__": self.seed,
            "__STEPS__": self.steps,
            "__CFG__": self.cfg,
            "__SAMPLER__": self.sampler_name,
            "__SCHEDULER__": self.scheduler,
            "__DENOISE__": self.denoise,
            "__FILENAME_PREFIX__": self.filename_prefix,
            "__LORA_NAME__": self.lora_name,
            "__LORA_STRENGTH__": self.lora_strength,
            "__STYLE_REFERENCE_IMAGE__": self.style_reference_image,
            "__STYLE_REFERENCE_STRENGTH__": self.style_reference_strength,
            "__CONTROL_IMAGE__": self.control_image,
            "__CONTROL_STRENGTH__": self.control_strength,
        }
        prompt_payload: object
        if self.positive_prompt_g.strip() or self.positive_prompt_l.strip():
            prompt_payload = {
                "prompt_g": self.positive_prompt_g or self.positive_prompt,
                "prompt_l": self.positive_prompt_l or self.positive_prompt,
                "combined": self.positive_prompt,
            }
        else:
            prompt_payload = self.positive_prompt
        placeholders.update(
            build_prompt_placeholders(
                positive_prompt=prompt_payload,
                negative_prompt=self.negative_prompt,
            )
        )
        return apply_micro_conditioning_placeholders(
            placeholders=placeholders,
            generation_profile=self.generation_profile,
            width=self.width,
            height=self.height,
            original_width=self.original_width,
            original_height=self.original_height,
            target_width=self.target_width,
            target_height=self.target_height,
            crop_w=self.crop_w,
            crop_h=self.crop_h,
        )


def _require(pid: str) -> None:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")


def _require_project(pid: str) -> ProjectRecord:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


class ComfyImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str = Field(min_length=1, max_length=200)
    sentence_idx: int = Field(default=0, ge=0, le=99999)
    prompt: str = Field(default="", max_length=2000)
    manifest_sentence_hash: str = Field(default="", max_length=128)


class ComfyJobPayload(ComfyWorkflowPayload):
    sentence_idx: int = Field(default=0, ge=0, le=99999)
    prompt: str = Field(default="", max_length=2000)
    auto_build_plans_after_image: bool = True


class ComfyBatchJobPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint: str = Field(min_length=1, max_length=200)
    start_idx: int = Field(default=0, ge=0, le=99999)
    count: int = Field(default=3, ge=1, le=12)
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=576, ge=256, le=2048)
    seed_base: int = Field(default=1, ge=0, le=2147483647)
    filename_prefix: str = Field(default="newauto")
    client_id: str = Field(default="newauto", min_length=1, max_length=100)
    auto_build_plans_after_image: bool = True
    lora_name: str = Field(default="", max_length=200)
    lora_strength: float = Field(default=0.8, ge=0.0, le=2.0)
    variants_per_scene: int = Field(default=1, ge=1, le=5)
    quality_mode: QualityMode = "balanced"
    generation_profile: str = Field(default="", max_length=100)
    seed_policy: str = Field(default="spaced", pattern="^(fixed|spaced|random|variant_random)$")
    style_reference_image: str = Field(default="", max_length=400)
    style_reference_strength: float = Field(default=0.65, ge=0.0, le=2.0)
    control_image: str = Field(default="", max_length=400)
    control_strength: float = Field(default=0.75, ge=0.0, le=2.0)
    selective_high_risk_variants: bool = True
    high_risk_variants: int = Field(default=2, ge=1, le=5)


class PromptManifestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_idx: int = Field(default=0, ge=0, le=99999)
    count: int | None = Field(default=None, ge=1, le=48)
    unload_lmstudio_after: bool = True


class ComfyCandidateSelectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentence_idx: int = Field(ge=0, le=99999)
    path: str = Field(min_length=1, max_length=255)


def _resolve_template_id(template_id: str, lora_name: str) -> str:
    normalized = template_id.strip() or "txt2img_sdxl_basic"
    if lora_name.strip() and normalized == "txt2img_sdxl_basic":
        return "txt2img_sdxl_stickman_lora"
    return normalized


def _resolve_template_for_profile(template_id: str, lora_name: str, generation_profile: str) -> str:
    normalized_profile = normalize_generation_profile_name(generation_profile)
    if normalized_profile == "sdxl_style_reference" and template_id.strip() in {"", "txt2img_sdxl_basic", "txt2img_sdxl_ipadapter_style"}:
        if lora_name.strip():
            return "txt2img_sdxl_ipadapter_style_lora"
        return "txt2img_sdxl_ipadapter_style"
    if normalized_profile == "sdxl_controlnet_depth" and template_id.strip() in {"", "txt2img_sdxl_basic"}:
        return "txt2img_sdxl_controlnet_depth"
    if normalized_profile == "sdxl_low_vram_lightning" and not lora_name.strip() and template_id.strip() in {"", "txt2img_sdxl_basic"}:
        return "txt2img_sdxl_lightning"
    return _resolve_template_id(template_id, lora_name)


def _default_style_reference_path(project: ProjectRecord) -> str:
    if project["thumbnail_file"].strip():
        thumbnail_path = db.project_dir(project["id"]) / "thumbnail" / project["thumbnail_file"]
        if thumbnail_path.is_file():
            return str(thumbnail_path)
    for media_name in project["media_order"]:
        media_path = db.project_dir(project["id"]) / "media" / media_name
        if media_path.is_file() and media_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            return str(media_path)
    for mapping in project["body_image_mappings"]:
        mapped_name = str(mapping.get("path") or "").strip()
        if not mapped_name:
            continue
        mapped_path = db.project_dir(project["id"]) / "media" / mapped_name
        if mapped_path.is_file():
            return str(mapped_path)
    return ""


def _resolve_style_reference_path(project: ProjectRecord, style_reference_image: str) -> str:
    raw = style_reference_image.strip()
    if not raw or raw == "__auto__":
        return _default_style_reference_path(project)
    candidate = Path(raw)
    if candidate.is_file():
        return str(candidate)
    media_candidate = db.project_dir(project["id"]) / "media" / candidate.name
    if media_candidate.is_file():
        return str(media_candidate)
    raise HTTPException(400, f"Style reference image not found: {style_reference_image}")


def _resolve_control_image_path(project: ProjectRecord, control_image: str) -> str:
    raw = control_image.strip()
    if not raw or raw == "__auto__":
        return _default_style_reference_path(project)
    candidate = Path(raw)
    if candidate.is_file():
        return str(candidate)
    media_candidate = db.project_dir(project["id"]) / "media" / candidate.name
    if media_candidate.is_file():
        return str(media_candidate)
    raise HTTPException(400, f"Control image not found: {control_image}")


def _require_style_reference_ready(*, generation_profile: str, style_reference_image: str, lora_name: str) -> None:
    normalized_profile = normalize_generation_profile_name(generation_profile)
    if normalized_profile != "sdxl_style_reference":
        return
    capability = get_style_reference_capability()
    if capability["available"] is not True:
        raise HTTPException(400, f"IPAdapter style reference is not ready. {capability['detail']}")


def _require_controlnet_ready(*, generation_profile: str, control_image: str) -> None:
    normalized_profile = normalize_generation_profile_name(generation_profile)
    if normalized_profile != "sdxl_controlnet_depth":
        return
    capability = get_controlnet_depth_capability()
    if capability["available"] is not True:
        raise HTTPException(400, f"ControlNet depth is not ready. {capability['detail']}")


def _score_value(value: object, default: float = 0.0) -> float:
    return clamp_float(value, default)


def _spaced_seed(seed_base: int, offset: int, variant_index: int) -> int:
    return (seed_base + (offset * 1009) + (variant_index * 9176)) % 2147483647


def _randomized_seed(seed_base: int, offset: int, variant_index: int) -> int:
    mixed = (seed_base * 1103515245) + (offset * 12345) + (variant_index * 2654435761)
    return abs(mixed) % 2147483647


def _seed_for_variant(seed_base: int, offset: int, variant_index: int, seed_policy: str) -> int:
    policy = normalize_seed_policy(seed_policy)
    if policy == "fixed":
        return (seed_base + (offset * 1009)) % 2147483647
    if policy == "random":
        return _randomized_seed(seed_base, offset, variant_index)
    if policy == "variant_random":
        scene_seed = (seed_base + (offset * 1009)) % 2147483647
        return _randomized_seed(scene_seed, offset + 17, variant_index + 31)
    return _spaced_seed(seed_base, offset, variant_index)


_HIGH_RISK_COMPOSITION_TEMPLATES = {
    "growthcomparison",
    "labextraction",
    "pollutionfragment",
    "soildecomposition",
    "wastetomaterial",
}

_HIGH_RISK_DOMAIN_TERMS = {
    "agriculture_environment": {
        "decomposition",
        "film",
        "leaf",
        "microplastic",
        "mulch",
        "plastic",
        "pollution",
        "soil",
        "sprout",
    },
    "science_materials": {
        "biodegradable",
        "decomposition",
        "extraction",
        "film",
        "lab",
        "material",
        "sample",
        "soil",
    },
}


def _mapping_value(mapping: Mapping[str, object], key: str) -> object:
    return mapping.get(key)


def _item_visual_brief(item: Mapping[str, object]) -> Mapping[str, object]:
    raw = _mapping_value(item, "visual_brief")
    if isinstance(raw, Mapping):
        return raw
    return {}


def _text_tokens(value: object) -> set[str]:
    if isinstance(value, str):
        return {value.strip().lower()} if value.strip() else set()
    if isinstance(value, list):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    return set()


def _is_high_risk_prompt_item(item: Mapping[str, object]) -> bool:
    visual_brief = _item_visual_brief(item)
    template = str(visual_brief.get("composition_template") or item.get("composition_template") or "").replace("_", "").lower()
    if template in _HIGH_RISK_COMPOSITION_TEMPLATES:
        return True
    domain = str(visual_brief.get("domain") or item.get("domain") or "").strip()
    domain_terms = _HIGH_RISK_DOMAIN_TERMS.get(domain, set())
    if not domain_terms:
        return False
    tokens = set()
    for key in ("must_show", "primary_keywords", "secondary_keywords", "props"):
        tokens.update(_text_tokens(visual_brief.get(key)))
    tokens.update(_text_tokens(item.get("positive_prompt")))
    tokens.update(_text_tokens(item.get("prompt_g")))
    tokens.update(_text_tokens(item.get("prompt_l")))
    joined_tokens = " ".join(sorted(tokens))
    return any(term in joined_tokens for term in domain_terms)


def _variant_count_for_prompt_item(item: Mapping[str, object], payload: ComfyBatchJobPayload) -> int:
    if not payload.selective_high_risk_variants:
        return payload.variants_per_scene
    if _is_high_risk_prompt_item(item):
        return max(payload.variants_per_scene, payload.high_risk_variants)
    return payload.variants_per_scene


def _prompt_manifest_items(project: ProjectRecord) -> list[dict[str, object]]:
    raw_path = project["body_image_options"].get("image_prompts_manifest_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise HTTPException(400, "Generate image prompts before starting ComfyUI image generation.")
    path = Path(raw_path)
    if not path.is_file():
        raise HTTPException(400, f"Image prompt manifest not found: {raw_path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(400, f"Image prompt manifest could not be read: {exc}") from exc
    items = None
    if isinstance(payload, dict):
        items = payload.get("prompts") or payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "Image prompt manifest has no prompt items.")
    return [item for item in items if isinstance(item, dict)]


def _fallback_ratio_block_threshold(project: ProjectRecord) -> float:
    raw = project["body_image_options"].get("fallback_ratio_block_threshold", 0.3)
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return 0.3


def _has_strict_prompt_quality_domain(suggestions: list[dict[str, object]]) -> bool:
    strict_domains = {"ev_battery", "food_trend", "news_explainer", "ai_policy_conflict"}
    for item in suggestions:
        visual_brief = item.get("visual_brief")
        visual_plan = item.get("visual_plan")
        domains: list[str] = []
        if isinstance(visual_brief, dict):
            domains.append(str(visual_brief.get("domain") or "").strip().lower())
        if isinstance(visual_plan, dict):
            domains.append(str(visual_plan.get("domain") or "").strip().lower())
        if any(domain in strict_domains for domain in domains):
            return True
    return False


def _strict_prompt_coverage_failures(suggestions: list[dict[str, object]]) -> list[int]:
    failures: list[int] = []
    for offset, item in enumerate(suggestions):
        if not _has_strict_prompt_quality_domain([item]):
            continue
        keyword_coverage = item.get("keyword_coverage")
        if not isinstance(keyword_coverage, dict):
            continue
        if keyword_coverage.get("passed") is False:
            raw_idx = item.get("sentence_idx", offset)
            try:
                failures.append(int(raw_idx))
            except (TypeError, ValueError):
                failures.append(offset)
    return failures


def _validate_prompt_quality_before_generation(
    project: ProjectRecord,
    suggestions: list[dict[str, object]],
    *,
    source: str,
) -> dict[str, object]:
    if project["body_image_options"].get("force_prompt_quality_override") is True:
        return {"blocked": False, "override": True}
    report = build_prompt_quality_report(suggestions)
    project_issue_codes = [
        str(item)
        for item in report.get("project_issue_codes", [])
        if isinstance(item, str)
    ]
    fallback_rate = float(report.get("fallback_rate") or 0.0)
    fallback_threshold = _fallback_ratio_block_threshold(project)
    blocking_codes = [
        code
        for code in project_issue_codes
        if code in _BLOCKING_PROMPT_QUALITY_CODES
    ]
    if _has_strict_prompt_quality_domain(suggestions) and fallback_rate > fallback_threshold:
        blocking_codes.append("FALLBACK_RATE_BLOCKED")
    coverage_failures = _strict_prompt_coverage_failures(suggestions)
    if coverage_failures:
        blocking_codes.append("STRICT_PROMPT_COVERAGE_FAILED")
    if not blocking_codes:
        return report
    message = (
        "Prompt quality gate blocked ComfyUI generation "
        f"({source}): {', '.join(dict.fromkeys(blocking_codes))}."
    )
    options = dict(project["body_image_options"])
    options["prompt_quality_report"] = report
    options["prompt_quality_blocking_codes"] = list(dict.fromkeys(blocking_codes))
    db.update_project(
        project["id"],
        body_image_state="blocked",
        body_image_phase="prompt_quality_gate",
        body_image_error=message,
        body_image_last_log=message,
        body_image_options=options,
    )
    raise HTTPException(409, message)


def _reset_generated_candidate_state(
    project: ProjectRecord,
    options: dict[str, object],
    sentence_indices: set[int],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    reset_keys = {str(idx) for idx in sentence_indices}
    for option_key in ("candidate_groups", "candidate_reviews"):
        raw = options.get(option_key)
        if isinstance(raw, dict):
            options[option_key] = {
                key: value
                for key, value in raw.items()
                if str(key) not in reset_keys
            }
    mappings = [
        dict(item)
        for item in project["body_image_mappings"]
        if isinstance(item, dict) and to_int(item.get("sentence_idx"), -1) not in sentence_indices
    ]
    return options, mappings


def _batch_items_from_suggestions(
    project: ProjectRecord,
    payload: ComfyBatchJobPayload,
    suggestions: list[dict[str, object]],
) -> list[dict[str, object]]:
    normalized_profile = normalize_generation_profile_name(payload.generation_profile)
    resolved_style_reference_image = (
        _resolve_style_reference_path(project, payload.style_reference_image)
        if normalized_profile == "sdxl_style_reference"
        else ""
    )
    resolved_control_image = (
        _resolve_control_image_path(project, payload.control_image)
        if normalized_profile == "sdxl_controlnet_depth"
        else ""
    )
    if normalized_profile == "sdxl_style_reference" and not resolved_style_reference_image:
        raise HTTPException(400, "Style reference profile could not find a default reference image in thumbnail or project media.")
    if normalized_profile == "sdxl_controlnet_depth" and not resolved_control_image:
        raise HTTPException(400, "ControlNet depth profile could not find a default control image in thumbnail or project media.")

    batch_items: list[dict[str, object]] = []
    for offset, item in enumerate(suggestions):
        raw_sentence_idx = item.get("sentence_idx", 0)
        if isinstance(raw_sentence_idx, bool):
            sentence_idx = 0
        elif isinstance(raw_sentence_idx, int):
            sentence_idx = raw_sentence_idx
        elif isinstance(raw_sentence_idx, str):
            try:
                sentence_idx = int(raw_sentence_idx)
            except ValueError:
                sentence_idx = 0
        else:
            sentence_idx = 0
        positive_prompt = str(item.get("positive_prompt", ""))
        positive_prompt_g = str(item.get("prompt_g", ""))
        positive_prompt_l = str(item.get("prompt_l", ""))
        negative_prompt = str(item.get("negative_prompt", ""))
        explicit_profile_requested = bool(payload.generation_profile.strip())
        profile = profile_for_request(
            quality_mode=item.get("quality_mode", payload.quality_mode),
            generation_profile=payload.generation_profile or item.get("generation_profile", ""),
        )
        resolved_seed_policy = normalize_seed_policy(payload.seed_policy, profile["seed_policy"])
        scene_variant_count = _variant_count_for_prompt_item(item, payload)
        for variant_index in range(scene_variant_count):
            batch_items.append(
                {
                    "template_id": _resolve_template_for_profile(profile["workflow_template"], payload.lora_name, str(payload.generation_profile or item.get("generation_profile") or profile["profile_name"])),
                    "checkpoint": payload.checkpoint,
                    "positive_prompt": positive_prompt,
                    "prompt_g": positive_prompt_g,
                    "prompt_l": positive_prompt_l,
                    "negative_prompt": negative_prompt,
                    "width": payload.width,
                    "height": payload.height,
                    "seed": _seed_for_variant(payload.seed_base, offset, variant_index, resolved_seed_policy),
                    "steps": profile["steps"] if explicit_profile_requested else to_int(item.get("steps"), profile["steps"]),
                    "cfg": profile["cfg"] if explicit_profile_requested else to_float(item.get("cfg"), profile["cfg"]),
                    "sampler_name": profile["sampler_name"] if explicit_profile_requested else str(item.get("sampler_name") or profile["sampler_name"]),
                    "scheduler": profile["scheduler"] if explicit_profile_requested else str(item.get("scheduler") or profile["scheduler"]),
                    "denoise": profile["denoise"] if explicit_profile_requested else to_float(item.get("denoise"), profile["denoise"]),
                    "generation_profile": str(payload.generation_profile or item.get("generation_profile") or profile["profile_name"]),
                    "score_version": str(item.get("score_version") or profile["score_version"]),
                    "quality_mode": str(item.get("quality_mode") or payload.quality_mode),
                    "request_timeout_sec": to_int(item.get("request_timeout_sec"), profile["request_timeout_sec"]),
                    "seed_policy": resolved_seed_policy,
                    "requires_lightning_checkpoint": profile["requires_lightning_checkpoint"],
                    "requires_ipadapter": profile["requires_ipadapter"],
                    "requires_controlnet": profile["requires_controlnet"],
                    "style_reference_image": resolved_style_reference_image,
                    "style_reference_strength": payload.style_reference_strength,
                    "control_image": resolved_control_image,
                    "control_strength": payload.control_strength,
                    **micro_conditioning_values(
                        profile=profile,
                        width=payload.width,
                        height=payload.height,
                        original_width=to_int(item.get("original_width"), payload.width),
                        original_height=to_int(item.get("original_height"), payload.height),
                        target_width=to_int(item.get("target_width"), payload.width),
                        target_height=to_int(item.get("target_height"), payload.height),
                        crop_w=to_int(item.get("crop_w"), 0),
                        crop_h=to_int(item.get("crop_h"), 0),
                    ),
                    "filename_prefix": f"{payload.filename_prefix}_scene_{sentence_idx:03d}_v{variant_index + 1}",
                    "client_id": payload.client_id,
                    "sentence_idx": sentence_idx,
                    "prompt": positive_prompt,
                    "visual_brief": item.get("visual_brief"),
                    "visual_plan": item.get("visual_plan"),
                    "keyword_coverage": item.get("keyword_coverage"),
                    "sentence_hash": str(item.get("sentence_hash", "")),
                    "lora_name": payload.lora_name,
                    "lora_strength": payload.lora_strength,
                    "candidate_index": variant_index + 1,
                    "candidate_total": scene_variant_count,
                }
            )
    return batch_items


@router.get("/{pid}/comfyui/prompt-suggestion")
def get_comfyui_prompt_suggestion(pid: str, sentence_idx: int = 0) -> dict[str, object]:
    project = _require_project(pid)
    try:
        suggestion = suggest_image_prompt(project, sentence_idx)
        if suggestion.get("template_id") == "txt2img_sdxl_stickman_lora":
            positive_prompt = str(suggestion.get("positive_prompt") or "")
            if "Stick figure" not in positive_prompt:
                suggestion = dict(suggestion)
                suggestion["positive_prompt"] = f"Stick figure, {positive_prompt}"
        return suggestion
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{pid}/comfyui/prompt-suggestions")
def get_comfyui_prompt_suggestions(pid: str, start_idx: int = 0, count: int = 3) -> dict[str, object]:
    project = _require_project(pid)
    suggestions = suggest_image_prompt_batch(project, start_idx=start_idx, count=count)
    return {
        "items": suggestions,
        "start_idx": start_idx,
        "count": count,
    }


@router.post("/{pid}/media-simple/prompt-manifest")
def create_simple_media_prompt_manifest(pid: str, payload: PromptManifestPayload) -> dict[str, object]:
    project = _require_project(pid)
    sentence_count = len(project["sentences"])
    if sentence_count <= 0:
        raise HTTPException(400, "No script sentences are available for image prompt generation.")
    count = payload.count or max(1, min(48, sentence_count - payload.start_idx))
    suggestions = suggest_image_prompt_batch(project, start_idx=payload.start_idx, count=count)
    if not suggestions:
        raise HTTPException(400, "No image prompts were generated.")
    manifest_path = save_image_prompt_manifest(
        db.project_dir(pid) / "image_prompts_manifest.json",
        project=project,
        source="simple_media_prompt_manifest",
        prompts=suggestions,
    )
    loaded_models_before = loaded_lmstudio_models()
    unload_result = unload_lmstudio_model() if payload.unload_lmstudio_after else {"ok": False, "skipped": True}
    loaded_models_after = loaded_lmstudio_models()
    body_image_options = dict(project["body_image_options"])
    body_image_options.update(
        {
            "image_prompts_manifest_path": str(manifest_path),
            "simple_media_prompt_state": "done",
            "simple_media_prompt_count": len(suggestions),
            "simple_media_lmstudio_unload": unload_result,
            "simple_media_lmstudio_models_before": loaded_models_before,
            "simple_media_lmstudio_models_after": loaded_models_after,
        }
    )
    updated = db.update_project(
        pid,
        body_image_state="idle",
        body_image_progress=0,
        body_image_error="",
        body_image_phase="prompt_manifest_done",
        body_image_last_log=f"Generated {len(suggestions)} image prompts and checked LM Studio unload.",
        body_image_options=body_image_options,
    )
    return {
        "ok": True,
        "count": len(suggestions),
        "items": suggestions,
        "manifest_path": str(manifest_path),
        "lmstudio_unload": unload_result,
        "lmstudio_models_before": loaded_models_before,
        "lmstudio_models_after": loaded_models_after,
        "project": updated or db.get_project(pid),
    }


@router.post("/{pid}/media-simple/lmstudio-unload")
def unload_simple_media_lmstudio(pid: str) -> dict[str, object]:
    project = _require_project(pid)
    loaded_models_before = loaded_lmstudio_models()
    unload_result = unload_lmstudio_model()
    loaded_models_after = loaded_lmstudio_models()
    body_image_options = dict(project["body_image_options"])
    body_image_options.update(
        {
            "simple_media_lmstudio_unload": unload_result,
            "simple_media_lmstudio_models_before": loaded_models_before,
            "simple_media_lmstudio_models_after": loaded_models_after,
        }
    )
    updated = db.update_project(
        pid,
        body_image_last_log="LM Studio unload checked for ComfyUI image generation.",
        body_image_options=body_image_options,
    )
    return {
        "ok": bool(unload_result.get("ok")),
        "lmstudio_unload": unload_result,
        "lmstudio_models_before": loaded_models_before,
        "lmstudio_models_after": loaded_models_after,
        "project": updated or db.get_project(pid),
    }


@router.post("/{pid}/comfyui/workflow/render")
def render_comfyui_workflow(pid: str, payload: ComfyWorkflowPayload) -> dict[str, object]:
    project = _require_project(pid)
    _require_style_reference_ready(
        generation_profile=payload.generation_profile,
        style_reference_image=payload.style_reference_image,
        lora_name=payload.lora_name,
    )
    _require_controlnet_ready(
        generation_profile=payload.generation_profile,
        control_image=payload.control_image,
    )
    payload.style_reference_image = _resolve_style_reference_path(project, payload.style_reference_image)
    payload.control_image = _resolve_control_image_path(project, payload.control_image)
    if normalize_generation_profile_name(payload.generation_profile) == "sdxl_style_reference" and not payload.style_reference_image:
        raise HTTPException(400, "Style reference profile could not find a default reference image in thumbnail or project media.")
    if normalize_generation_profile_name(payload.generation_profile) == "sdxl_controlnet_depth" and not payload.control_image:
        raise HTTPException(400, "ControlNet depth profile could not find a default control image in thumbnail or project media.")
    workflow = render_workflow_template(
        _resolve_template_for_profile(payload.template_id, payload.lora_name, payload.generation_profile),
        payload.placeholders(),
    )
    return {"workflow": workflow}


@router.post("/{pid}/comfyui/workflow/submit")
def submit_comfyui_workflow(pid: str, payload: ComfyWorkflowPayload) -> dict[str, object]:
    project = _require_project(pid)
    _require_style_reference_ready(
        generation_profile=payload.generation_profile,
        style_reference_image=payload.style_reference_image,
        lora_name=payload.lora_name,
    )
    _require_controlnet_ready(
        generation_profile=payload.generation_profile,
        control_image=payload.control_image,
    )
    payload.style_reference_image = _resolve_style_reference_path(project, payload.style_reference_image)
    payload.control_image = _resolve_control_image_path(project, payload.control_image)
    if normalize_generation_profile_name(payload.generation_profile) == "sdxl_style_reference" and not payload.style_reference_image:
        raise HTTPException(400, "Style reference profile could not find a default reference image in thumbnail or project media.")
    if normalize_generation_profile_name(payload.generation_profile) == "sdxl_controlnet_depth" and not payload.control_image:
        raise HTTPException(400, "ControlNet depth profile could not find a default control image in thumbnail or project media.")
    workflow = render_workflow_template(
        _resolve_template_for_profile(payload.template_id, payload.lora_name, payload.generation_profile),
        payload.placeholders(),
    )
    submission = ComfyUIClient(timeout_sec=payload.request_timeout_sec).submit_workflow(workflow, client_id=payload.client_id)
    db.update_project(
        pid,
        body_image_state="running",
        body_image_progress=10,
        body_image_error="",
    )
    return {
        "prompt_id": submission.prompt_id,
        "number": submission.number,
        "node_errors": submission.node_errors,
    }


@router.post("/{pid}/comfyui/job")
def enqueue_comfyui_job(pid: str, payload: ComfyJobPayload) -> dict[str, bool]:
    project = _require_project(pid)
    _require_style_reference_ready(
        generation_profile=payload.generation_profile,
        style_reference_image=payload.style_reference_image,
        lora_name=payload.lora_name,
    )
    _require_controlnet_ready(
        generation_profile=payload.generation_profile,
        control_image=payload.control_image,
    )
    payload.style_reference_image = _resolve_style_reference_path(project, payload.style_reference_image)
    payload.control_image = _resolve_control_image_path(project, payload.control_image)
    if normalize_generation_profile_name(payload.generation_profile) == "sdxl_style_reference" and not payload.style_reference_image:
        raise HTTPException(400, "Style reference profile could not find a default reference image in thumbnail or project media.")
    if normalize_generation_profile_name(payload.generation_profile) == "sdxl_controlnet_depth" and not payload.control_image:
        raise HTTPException(400, "ControlNet depth profile could not find a default control image in thumbnail or project media.")
    existing_options = (
        dict(project["body_image_options"])
        if isinstance(project.get("body_image_options"), Mapping)
        else {}
    )
    existing_options.update(payload.model_dump())
    db.update_project(
        pid,
        body_image_state="queued",
        body_image_progress=0,
        body_image_error="",
        body_image_phase="queued",
        body_image_last_log="Queued ComfyUI image generation.",
        body_image_job_id="",
        body_image_started_at="",
        body_image_heartbeat_at="",
        body_image_options=existing_options,
    )
    return {"ok": True}


@router.post("/{pid}/comfyui/job/batch-auto")
def enqueue_comfyui_batch_job(pid: str, payload: ComfyBatchJobPayload) -> dict[str, object]:
    project = _require_project(pid)
    _require_style_reference_ready(
        generation_profile=payload.generation_profile,
        style_reference_image=payload.style_reference_image,
        lora_name=payload.lora_name,
    )
    _require_controlnet_ready(
        generation_profile=payload.generation_profile,
        control_image=payload.control_image,
    )
    normalized_profile = normalize_generation_profile_name(payload.generation_profile)
    resolved_style_reference_image = (
        _resolve_style_reference_path(project, payload.style_reference_image)
        if normalized_profile == "sdxl_style_reference"
        else ""
    )
    resolved_control_image = (
        _resolve_control_image_path(project, payload.control_image)
        if normalized_profile == "sdxl_controlnet_depth"
        else ""
    )
    if normalized_profile == "sdxl_style_reference" and not resolved_style_reference_image:
        raise HTTPException(400, "Style reference profile could not find a default reference image in thumbnail or project media.")
    if normalized_profile == "sdxl_controlnet_depth" and not resolved_control_image:
        raise HTTPException(400, "ControlNet depth profile could not find a default control image in thumbnail or project media.")
    suggestions = suggest_image_prompt_batch(project, start_idx=payload.start_idx, count=payload.count)
    if not suggestions:
        raise HTTPException(400, "No sentences are available for batch image generation.")
    prompt_quality_report = _validate_prompt_quality_before_generation(
        project,
        suggestions,
        source="batch_auto",
    )
    batch_items = []
    for offset, item in enumerate(suggestions):
        raw_sentence_idx = item.get("sentence_idx", 0)
        if isinstance(raw_sentence_idx, bool):
            sentence_idx = int(raw_sentence_idx)
        elif isinstance(raw_sentence_idx, int):
            sentence_idx = raw_sentence_idx
        elif isinstance(raw_sentence_idx, float):
            sentence_idx = int(raw_sentence_idx)
        elif isinstance(raw_sentence_idx, str):
            try:
                sentence_idx = int(raw_sentence_idx)
            except ValueError:
                sentence_idx = 0
        else:
            sentence_idx = 0
        positive_prompt = str(item.get("positive_prompt", ""))
        positive_prompt_g = str(item.get("prompt_g", ""))
        positive_prompt_l = str(item.get("prompt_l", ""))
        negative_prompt = str(item.get("negative_prompt", ""))
        explicit_profile_requested = bool(payload.generation_profile.strip())
        profile = profile_for_request(
            quality_mode=item.get("quality_mode", payload.quality_mode),
            generation_profile=payload.generation_profile or item.get("generation_profile", ""),
        )
        resolved_seed_policy = normalize_seed_policy(payload.seed_policy, profile["seed_policy"])
        scene_variant_count = _variant_count_for_prompt_item(item, payload)
        for variant_index in range(scene_variant_count):
            batch_items.append(
                {
                    "template_id": _resolve_template_for_profile(profile["workflow_template"], payload.lora_name, str(payload.generation_profile or item.get("generation_profile") or profile["profile_name"])),
                    "checkpoint": payload.checkpoint,
                    "positive_prompt": positive_prompt,
                    "prompt_g": positive_prompt_g,
                    "prompt_l": positive_prompt_l,
                    "negative_prompt": negative_prompt,
                    "width": payload.width,
                    "height": payload.height,
                    "seed": _seed_for_variant(payload.seed_base, offset, variant_index, resolved_seed_policy),
                    "steps": profile["steps"] if explicit_profile_requested else to_int(item.get("steps"), profile["steps"]),
                    "cfg": profile["cfg"] if explicit_profile_requested else to_float(item.get("cfg"), profile["cfg"]),
                    "sampler_name": profile["sampler_name"] if explicit_profile_requested else str(item.get("sampler_name") or profile["sampler_name"]),
                    "scheduler": profile["scheduler"] if explicit_profile_requested else str(item.get("scheduler") or profile["scheduler"]),
                    "denoise": profile["denoise"] if explicit_profile_requested else to_float(item.get("denoise"), profile["denoise"]),
                    "generation_profile": str(payload.generation_profile or item.get("generation_profile") or profile["profile_name"]),
                    "score_version": str(item.get("score_version") or profile["score_version"]),
                    "quality_mode": str(item.get("quality_mode") or payload.quality_mode),
                    "request_timeout_sec": to_int(item.get("request_timeout_sec"), profile["request_timeout_sec"]),
                    "seed_policy": resolved_seed_policy,
                    "requires_lightning_checkpoint": profile["requires_lightning_checkpoint"],
                    "requires_ipadapter": profile["requires_ipadapter"],
                    "requires_controlnet": profile["requires_controlnet"],
                    "style_reference_image": resolved_style_reference_image,
                    "style_reference_strength": payload.style_reference_strength,
                    "control_image": resolved_control_image,
                    "control_strength": payload.control_strength,
                    **micro_conditioning_values(
                        profile=profile,
                        width=payload.width,
                        height=payload.height,
                        original_width=to_int(item.get("original_width"), payload.width),
                        original_height=to_int(item.get("original_height"), payload.height),
                        target_width=to_int(item.get("target_width"), payload.width),
                        target_height=to_int(item.get("target_height"), payload.height),
                        crop_w=to_int(item.get("crop_w"), 0),
                        crop_h=to_int(item.get("crop_h"), 0),
                    ),
                    "filename_prefix": f"{payload.filename_prefix}_scene_{sentence_idx:03d}_v{variant_index + 1}",
                    "client_id": payload.client_id,
                    "sentence_idx": sentence_idx,
                    "prompt": positive_prompt,
                    "visual_brief": item.get("visual_brief"),
                    "visual_plan": item.get("visual_plan"),
                    "keyword_coverage": item.get("keyword_coverage"),
                    "sentence_hash": str(item.get("sentence_hash", "")),
                    "lora_name": payload.lora_name,
                    "lora_strength": payload.lora_strength,
                    "candidate_index": variant_index + 1,
                    "candidate_total": scene_variant_count,
                }
            )
    manifest_path = save_image_prompt_manifest(
        db.project_dir(pid) / "image_prompts_manifest.json",
        project=project,
        source="manual_batch_auto",
        prompts=suggestions,
    )
    body_image_options = dict(project["body_image_options"])
    reset_sentence_indices = {
        to_int(item.get("sentence_idx"), -1)
        for item in batch_items
        if isinstance(item, dict) and to_int(item.get("sentence_idx"), -1) >= 0
    }
    body_image_options, reset_mappings = _reset_generated_candidate_state(
        project,
        body_image_options,
        reset_sentence_indices,
    )
    body_image_options.update(
        {
            "batch_items": batch_items,
            "auto_build_plans_after_image": payload.auto_build_plans_after_image,
            "image_prompts_manifest_path": str(manifest_path),
            "quality_mode": payload.quality_mode,
            "prompt_quality_report": prompt_quality_report,
        }
    )
    db.update_project(
        pid,
        body_image_state="queued",
        body_image_progress=0,
        body_image_error="",
        body_image_mappings=reset_mappings,
        body_image_phase="queued",
        body_image_last_log=f"Queued {len(batch_items)} ComfyUI image jobs.",
        body_image_job_id="",
        body_image_started_at="",
        body_image_heartbeat_at="",
        body_image_options=body_image_options,
    )
    return {
        "ok": True,
        "count": len(batch_items),
        "variants_per_scene": payload.variants_per_scene,
        "selective_high_risk_variants": payload.selective_high_risk_variants,
        "high_risk_variants": payload.high_risk_variants,
    }


@router.post("/{pid}/media-simple/comfyui/job")
def enqueue_simple_media_comfyui_job(pid: str, payload: ComfyBatchJobPayload) -> dict[str, object]:
    project = _require_project(pid)
    _require_style_reference_ready(
        generation_profile=payload.generation_profile,
        style_reference_image=payload.style_reference_image,
        lora_name=payload.lora_name,
    )
    _require_controlnet_ready(
        generation_profile=payload.generation_profile,
        control_image=payload.control_image,
    )
    suggestions = _prompt_manifest_items(project)
    start = max(0, payload.start_idx)
    end = start + max(1, payload.count)
    selected = suggestions[start:end]
    if not selected:
        raise HTTPException(400, "No prompt manifest items are available for the selected range.")
    loaded_models = loaded_lmstudio_models()
    if loaded_models:
        raise HTTPException(409, "LM Studio still has a model loaded. Use the LM Studio unload button before image generation.")
    prompt_quality_report = _validate_prompt_quality_before_generation(
        project,
        selected,
        source="simple_media",
    )
    batch_items = _batch_items_from_suggestions(project, payload, selected)
    body_image_options = dict(project["body_image_options"])
    reset_sentence_indices = {
        to_int(item.get("sentence_idx"), -1)
        for item in batch_items
        if isinstance(item, dict) and to_int(item.get("sentence_idx"), -1) >= 0
    }
    body_image_options, reset_mappings = _reset_generated_candidate_state(
        project,
        body_image_options,
        reset_sentence_indices,
    )
    body_image_options.update(
        {
            "batch_items": batch_items,
            "auto_build_plans_after_image": payload.auto_build_plans_after_image,
            "quality_mode": payload.quality_mode,
            "simple_media_image_state": "queued",
            "prompt_quality_report": prompt_quality_report,
        }
    )
    db.update_project(
        pid,
        visual_source_mode="comfyui_auto",
        body_image_state="queued",
        body_image_progress=0,
        body_image_error="",
        body_image_mappings=reset_mappings,
        body_image_phase="queued",
        body_image_last_log=f"Queued {len(batch_items)} simple Media ComfyUI image jobs.",
        body_image_job_id="",
        body_image_started_at="",
        body_image_heartbeat_at="",
        body_image_options=body_image_options,
    )
    return {
        "ok": True,
        "count": len(batch_items),
        "variants_per_scene": payload.variants_per_scene,
        "prompt_count": len(selected),
    }


@router.post("/{pid}/visual-diagnostics/regenerate")
def regenerate_visual_diagnostics(pid: str) -> dict[str, object]:
    project = _require_project(pid)
    report_json_path, report_md_path = write_visual_mismatch_report(project)
    contact_sheet_path = write_visual_contact_sheet(project)
    return {
        "ok": True,
        "visual_mismatch_report_json_path": str(report_json_path),
        "visual_mismatch_report_md_path": str(report_md_path),
        "diagnostic_contact_sheet_path": str(contact_sheet_path),
    }


@router.get("/{pid}/comfyui/history/{prompt_id}")
def get_comfyui_history(pid: str, prompt_id: str) -> dict[str, object]:
    _require(pid)
    history = ComfyUIClient().get_history(prompt_id)
    images = ComfyUIClient().extract_image_results(history, prompt_id)
    return {
        "history": history,
        "images": [
            {
                "filename": item.filename,
                "subfolder": item.subfolder,
                "type": item.type,
            }
            for item in images
        ],
    }


@router.post("/{pid}/comfyui/history/import")
def import_comfyui_history_image(pid: str, payload: ComfyImportPayload) -> dict[str, object]:
    project = _require_project(pid)
    updated_project, imported_file, source_file = import_history_image(
        project,
        prompt_id=payload.prompt_id,
        sentence_idx=payload.sentence_idx,
        prompt=payload.prompt,
        manifest_sentence_hash=payload.manifest_sentence_hash,
    )
    return {
        "project": updated_project,
        "imported_file": imported_file,
        "source_file": source_file,
    }


@router.post("/{pid}/comfyui/candidates/select")
def select_comfyui_candidate(pid: str, payload: ComfyCandidateSelectPayload) -> dict[str, object]:
    project = _require_project(pid)
    options = dict(project["body_image_options"])
    candidate_groups = options.get("candidate_groups", {})
    if not isinstance(candidate_groups, dict):
        raise HTTPException(404, "No candidate groups are available for this project.")
    group_items = candidate_groups.get(str(payload.sentence_idx))
    if not isinstance(group_items, list) or not group_items:
        raise HTTPException(404, "No candidates are available for that sentence.")
    selected_candidate: dict[str, object] | None = None
    updated_group_items: list[dict[str, object]] = []
    for item in group_items:
        if not isinstance(item, dict):
            continue
        updated_item = dict(item)
        is_selected = str(updated_item.get("path", "")) == payload.path
        updated_item["selected"] = is_selected
        if is_selected:
            selected_candidate = updated_item
        updated_group_items.append(updated_item)
    if selected_candidate is None:
        raise HTTPException(404, "Selected candidate path was not found.")
    candidate_groups[str(payload.sentence_idx)] = updated_group_items
    options["candidate_groups"] = candidate_groups
    sentence_text = project["sentences"][payload.sentence_idx] if payload.sentence_idx < len(project["sentences"]) else ""
    mappings = [item for item in project["body_image_mappings"] if item["sentence_idx"] != payload.sentence_idx]
    mappings.append(
        {
            "sentence_idx": payload.sentence_idx,
            "path": str(selected_candidate.get("path", payload.path)),
            "prompt": str(selected_candidate.get("prompt", "")),
            "sentence_text": sentence_text,
            "sentence_hash": str(sentence_hash(sentence_text)),
            "project_id": project["id"],
            "prompt_id": str(selected_candidate.get("prompt_id", "")),
            "manifest_sentence_hash": str(selected_candidate.get("sentence_hash", "")),
            "selected_reason": "manual_pick",
            "candidate_index": to_int(selected_candidate.get("candidate_index", 1), 1),
            "candidate_total": to_int(selected_candidate.get("candidate_total", 1), 1),
            "candidate_score": _score_value(selected_candidate.get("candidate_score", 0.0), 0.0),
            "candidate_score_version": str(selected_candidate.get("candidate_score_version", "candidate_score_v2")),
        }
    )
    updated = db.update_project(
        pid,
        body_image_mappings=mappings,
        body_image_options=options,
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    return {"project": updated}
