from __future__ import annotations

from collections.abc import Mapping
import json

from .. import db
from ..types import ProjectRecord
from .image_prompt import ImagePrompt, build_z_image_prompt
from .pipeline_manifest import build_initial_pipeline_manifest, record_visual_artifact, text_hash, update_stage_status


def _project_sentences(project: Mapping[str, object]) -> list[str]:
    sentences = project.get("sentences")
    if isinstance(sentences, list):
        return [item for item in sentences if isinstance(item, str)]
    script = project.get("script")
    if isinstance(script, str):
        return [line.strip() for line in script.splitlines() if line.strip()]
    return []


def _required_props(sentence: str) -> list[str]:
    if "빛" in sentence:
        return ["burst of light", "dark sky splitting open"]
    if "바다" in sentence or "새" in sentence:
        return ["wide sea", "birds in the sky"]
    if "땅" in sentence:
        return ["fresh ground", "green plants"]
    words = [word.strip(".,!?") for word in sentence.split() if word.strip(".,!?")]
    return words[:3] or ["central symbolic subject"]


def _visual_intent(sentence: str) -> str:
    props = _required_props(sentence)
    return f"Show {', '.join(props)} as the concrete focus of this sentence."


def _visual_brief(sentence: str, domain: str) -> dict[str, object]:
    props = _required_props(sentence)
    return {
        "main_subject": props[0],
        "action": "appears in a clear story moment",
        "primary_prop": props[0],
        "secondary_prop": props[1] if len(props) > 1 else "",
        "scene": "cinematic bible story illustration" if domain == "bible" else "editorial explainer scene",
        "emotion": "wonder",
        "must_show": props,
        "avoid": ["written labels", "duplicate main scene"],
        "rationale": "sentence-specific visual contract",
        "domain": domain,
        "visual_intent": "literal",
        "qa_expectations": props,
    }


def build_directed_prompt_for_sentence(
    project: Mapping[str, object],
    sentence_idx: int,
) -> tuple[ImagePrompt, dict[str, object]]:
    sentences = _project_sentences(project)
    sentence = sentences[sentence_idx]
    title = str(project.get("title") or "")
    domain = "bible" if "창세기" in title or "Genesis" in title else "general"
    visual_brief = _visual_brief(sentence, domain)
    prompt = build_z_image_prompt(sentence, visual_brief=visual_brief)
    prompt_hash = text_hash(f"{prompt.positive}\n{prompt.negative}")
    item: dict[str, object] = {
        "sentence_idx": sentence_idx,
        "sentence": sentence,
        "sentence_hash": text_hash(sentence),
        "domain": domain,
        "visual_intent": _visual_intent(sentence),
        "required_props": list(visual_brief["must_show"]),
        "positive_prompt": prompt.positive,
        "negative_prompt": prompt.negative,
        "prompt_hash": prompt_hash,
        "qa_expectations": list(visual_brief["must_show"]),
        "visual_brief": visual_brief,
        "visual_plan": {
            "sentence_idx": sentence_idx,
            "sentence": sentence,
            "domain": domain,
            "must_show": list(visual_brief["must_show"]),
            "visual_intent": _visual_intent(sentence),
        },
    }
    issues = validate_directed_prompt_item(item)
    if issues:
        item["validation_issues"] = issues
    return prompt, item


def build_prompt_director_manifest(project: Mapping[str, object]) -> dict[str, object]:
    prompts: list[dict[str, object]] = []
    for sentence_idx, _sentence in enumerate(_project_sentences(project)):
        _prompt, item = build_directed_prompt_for_sentence(project, sentence_idx)
        prompts.append(item)
    return {
        "version": 1,
        "project_id": str(project.get("id") or ""),
        "title": str(project.get("title") or ""),
        "prompts": prompts,
    }


def write_prompt_director_manifest(project: ProjectRecord) -> dict[str, object]:
    payload = build_prompt_director_manifest(project)
    project_dir = db.project_dir(project["id"])
    project_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = project_dir / "image_prompts_manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    pipeline_manifest = project["pipeline_manifest"]
    if len(pipeline_manifest.get("segments", [])) != len(project["sentences"]):
        pipeline_manifest = build_initial_pipeline_manifest(project["id"], project["title"], project["sentences"])
    for item in payload["prompts"]:
        if not isinstance(item, dict):
            continue
        sentence_idx = item.get("sentence_idx")
        if not isinstance(sentence_idx, int):
            continue
        pipeline_manifest = record_visual_artifact(
            pipeline_manifest,
            sentence_idx=sentence_idx,
            positive_prompt=str(item.get("positive_prompt") or ""),
            negative_prompt=str(item.get("negative_prompt") or ""),
            preset_id=str(item.get("preset_id") or "directed"),
            domain=str(item.get("domain") or ""),
            required_props=[prop for prop in item.get("required_props", []) if isinstance(prop, str)]
            if isinstance(item.get("required_props"), list)
            else [],
            visual_intent=str(item.get("visual_intent") or ""),
            prompt_hash=str(item.get("prompt_hash") or ""),
        )
    pipeline_manifest = update_stage_status(
        pipeline_manifest,
        "visual",
        state="done",
        input_hash=text_hash("\n".join(project["sentences"])),
        output_hash=text_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True)),
    )
    options = dict(project["body_image_options"])
    options["image_prompts_manifest_path"] = str(manifest_path)
    db.update_project(
        project["id"],
        body_image_options=options,
        pipeline_manifest=pipeline_manifest,
    )
    return payload


def validate_directed_prompt_item(item: dict[str, object]) -> list[str]:
    issues: list[str] = []
    if not str(item.get("positive_prompt") or "").strip():
        issues.append("PROMPT_POSITIVE_EMPTY")
    if not item.get("required_props"):
        issues.append("PROMPT_REQUIRED_PROPS_EMPTY")
    if str(item.get("positive_prompt") or "").count("Main scene:") > 1:
        issues.append("PROMPT_DUPLICATE_MAIN_SCENE")
    return issues
