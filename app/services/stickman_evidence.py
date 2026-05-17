from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from .. import db
from ..types import ProjectRecord
from .image_prompting import save_image_prompt_manifest, suggest_image_prompt_batch


DEFAULT_STICKMAN_BUSINESS_SENTENCES: list[str] = [
    "Nvidia strategy turns GPU sales into a developer ecosystem engine.",
    "Power grid infrastructure becomes a bottleneck for AI data center growth.",
    "Copilot is compared with competing models on a business value scale.",
    "Cloud revenue turns into capital expenditure through a spotlighted cost arrow.",
]


class StickmanEvidencePaths(TypedDict):
    evidence_dir: Path
    prompts_on: Path
    prompts_off: Path
    review: Path


def create_stickman_business_project(
    *,
    title: str = "Stickman Business Evidence",
    sentences: list[str] | None = None,
) -> ProjectRecord:
    db.init_db()
    selected_sentences = [item.strip() for item in (sentences or DEFAULT_STICKMAN_BUSINESS_SENTENCES) if item.strip()]
    if not selected_sentences:
        raise ValueError("at least one sentence is required")
    project = db.create_project(title=title)
    script = "\n".join(selected_sentences)
    updated = db.update_project(
        project["id"],
        script=script,
        user_script=script,
        compiled_script=script,
        sentences=selected_sentences,
        content_mode="standard",
        visual_source_mode="comfyui_auto",
        body_image_options={
            "style_preset": "stickman_business",
            "disable_llm_visual_planner": True,
        },
    )
    if updated is None:
        raise RuntimeError("project update failed")
    return updated


def _without_lora(prompt: dict[str, object]) -> dict[str, object]:
    updated = dict(prompt)
    positive_prompt = str(updated.get("positive_prompt") or "")
    prompt_g = str(updated.get("prompt_g") or "")
    prompt_l = str(updated.get("prompt_l") or "")
    for token in ("Stick figure, Flipchartvisu", "Flipchartvisu, Stick figure", "Stick figure", "Flipchartvisu"):
        positive_prompt = positive_prompt.replace(token, "")
        prompt_g = prompt_g.replace(token, "")
        prompt_l = prompt_l.replace(token, "")
    updated["positive_prompt"] = " ".join(positive_prompt.replace(",,", ",").split()).strip(" ,")
    updated["prompt_g"] = " ".join(prompt_g.replace(",,", ",").split()).strip(" ,")
    updated["prompt_l"] = " ".join(prompt_l.replace(",,", ",").split()).strip(" ,")
    updated["template_id"] = "txt2img_sdxl_basic"
    updated["lora_name"] = ""
    updated["lora_strength"] = 0.0
    updated["evidence_variant"] = "lora_off"
    return updated


def _with_lora(prompt: dict[str, object]) -> dict[str, object]:
    updated = dict(prompt)
    updated["evidence_variant"] = "lora_on"
    return updated


def _empty_review(prompts_on: list[dict[str, object]], prompts_off: list[dict[str, object]]) -> dict[str, object]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "pending_generation",
        "failure_categories": [
            "wrong_visual_style",
            "missing_round_head_business_character",
            "weak_metaphor_object",
            "fake_or_gibberish_text",
            "cluttered_layout",
            "blank_or_generic_card",
            "subtitle_or_label_collision_risk",
        ],
        "decision_gate": {
            "existing_lora_accept_threshold": 0.6,
            "rule": "Defer custom LoRA training if existing Stickfigures LoRA reaches acceptable style in at least 60% of prompts.",
        },
        "items": [
            {
                "sentence_idx": prompt.get("sentence_idx"),
                "sentence": prompt.get("sentence"),
                "template_key": prompt.get("template_key"),
                "lora_on_template_id": prompt.get("template_id"),
                "lora_on_strength": prompt.get("lora_strength"),
                "lora_off_template_id": prompts_off[index].get("template_id") if index < len(prompts_off) else "",
                "review_status": "not_generated",
                "failure_categories": [],
                "notes": "",
            }
            for index, prompt in enumerate(prompts_on)
        ],
    }


def build_stickman_evidence_bundle(project: ProjectRecord, *, count: int | None = None) -> StickmanEvidencePaths:
    prompt_count = count or len(project["sentences"])
    prompts = suggest_image_prompt_batch(project, start_idx=0, count=prompt_count)
    prompts_on = [_with_lora(prompt) for prompt in prompts]
    prompts_off = [_without_lora(prompt) for prompt in prompts]
    evidence_dir = db.project_dir(project["id"]) / "diagnostics_bundle" / "stickman_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    prompts_on_path = save_image_prompt_manifest(
        evidence_dir / "prompts_lora_on.json",
        project=project,
        source="stickman_business_evidence_lora_on",
        prompts=prompts_on,
    )
    prompts_off_path = save_image_prompt_manifest(
        evidence_dir / "prompts_lora_off.json",
        project=project,
        source="stickman_business_evidence_lora_off",
        prompts=prompts_off,
    )
    review_path = evidence_dir / "frame_reviews.json"
    review_path.write_text(json.dumps(_empty_review(prompts_on, prompts_off), ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "evidence_dir": evidence_dir,
        "prompts_on": prompts_on_path,
        "prompts_off": prompts_off_path,
        "review": review_path,
    }
