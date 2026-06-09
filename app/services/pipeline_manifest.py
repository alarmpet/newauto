from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone

from ..types import PipelineManifest, PipelineSegmentArtifact, Region


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def _copy_manifest(manifest: PipelineManifest) -> PipelineManifest:
    copied = copy.deepcopy(manifest)
    copied["updated_at"] = _now_iso()
    return copied


def _segment_for_update(manifest: PipelineManifest, sentence_idx: int) -> PipelineSegmentArtifact:
    for segment in manifest["segments"]:
        if segment["sentence_idx"] == sentence_idx:
            return segment
    raise ValueError(f"pipeline segment not found: {sentence_idx}")


def build_initial_pipeline_manifest(
    project_id: str,
    title: str,
    sentences: list[str],
    region: Region = "body",
) -> PipelineManifest:
    now = _now_iso()
    segments: list[PipelineSegmentArtifact] = [
        {
            "sentence_idx": idx,
            "script_text": sentence,
            "script_hash": text_hash(sentence),
            "region": region,
            "visual": None,
            "image": None,
            "tts": None,
        }
        for idx, sentence in enumerate(sentences)
    ]
    return {
        "version": 1,
        "project_id": project_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "segments": segments,
        "stage_status": {
            "script": {
                "state": "ready" if segments else "empty",
                "error_code": "",
                "recovery_hint": "",
                "input_hash": "",
                "output_hash": text_hash("\n".join(sentences)),
            },
            "visual": {"state": "idle", "error_code": "", "recovery_hint": "", "input_hash": "", "output_hash": ""},
            "image": {"state": "idle", "error_code": "", "recovery_hint": "", "input_hash": "", "output_hash": ""},
            "tts": {"state": "idle", "error_code": "", "recovery_hint": "", "input_hash": "", "output_hash": ""},
            "render": {"state": "idle", "error_code": "", "recovery_hint": "", "input_hash": "", "output_hash": ""},
        },
    }


def validate_pipeline_manifest(manifest: PipelineManifest) -> None:
    seen: set[int] = set()
    for segment in manifest["segments"]:
        idx = segment["sentence_idx"]
        if idx in seen:
            raise ValueError(f"duplicate pipeline segment index: {idx}")
        seen.add(idx)
        if not segment["script_text"].strip():
            raise ValueError(f"blank script text at segment {idx}")
        if segment["script_hash"] != text_hash(segment["script_text"]):
            raise ValueError(f"script hash mismatch at segment {idx}")


def update_stage_status(
    manifest: PipelineManifest,
    stage: str,
    *,
    state: str,
    error_code: str = "",
    recovery_hint: str = "",
    input_hash: str = "",
    output_hash: str = "",
) -> PipelineManifest:
    updated = _copy_manifest(manifest)
    updated["stage_status"][stage] = {
        "state": state,
        "error_code": error_code,
        "recovery_hint": recovery_hint,
        "input_hash": input_hash,
        "output_hash": output_hash,
    }
    return updated


def record_visual_artifact(
    manifest: PipelineManifest,
    *,
    sentence_idx: int,
    positive_prompt: str,
    negative_prompt: str,
    preset_id: str,
    domain: str,
    required_props: list[str],
    visual_intent: str,
    prompt_hash: str,
) -> PipelineManifest:
    updated = _copy_manifest(manifest)
    segment = _segment_for_update(updated, sentence_idx)
    segment["visual"] = {
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "preset_id": preset_id,
        "domain": domain,
        "required_props": required_props,
        "visual_intent": visual_intent,
        "prompt_hash": prompt_hash,
    }
    return updated


def record_image_attempt(
    manifest: PipelineManifest,
    *,
    sentence_idx: int,
    path: str,
    prompt_id: str,
    attempt: int,
    seed: int,
    prompt_hash: str,
    candidate_score: float,
    issue_codes: list[str],
    selected: bool,
) -> PipelineManifest:
    updated = _copy_manifest(manifest)
    segment = _segment_for_update(updated, sentence_idx)
    image = segment["image"] or {"path": path, "prompt_id": prompt_id, "attempts": []}
    image["path"] = path
    image["prompt_id"] = prompt_id
    image["attempts"].append(
        {
            "attempt": attempt,
            "seed": seed,
            "prompt_hash": prompt_hash,
            "candidate_score": candidate_score,
            "issue_codes": issue_codes,
            "selected": selected,
        }
    )
    segment["image"] = image
    return updated


def record_tts_artifact(
    manifest: PipelineManifest,
    *,
    sentence_idx: int,
    wav_path: str,
    start: float,
    end: float,
    duration_sec: float,
    seed: int,
    issue_codes: list[str],
) -> PipelineManifest:
    updated = _copy_manifest(manifest)
    segment = _segment_for_update(updated, sentence_idx)
    segment["tts"] = {
        "wav_path": wav_path,
        "start": start,
        "end": end,
        "duration_sec": duration_sec,
        "seed": seed,
        "issue_codes": issue_codes,
    }
    return updated
