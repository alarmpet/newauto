from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise AssertionError(f"missing required smoke artifact: {path.name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"smoke artifact must be a JSON object: {path.name}")
    return payload


def _unique_ratio(values: list[str]) -> float:
    if not values:
        return 0.0
    return len(set(values)) / float(len(values))


def verify_prompt_manifest(project_dir: Path, min_unique_prompt_ratio: float) -> None:
    payload = _load_json(project_dir / "image_prompts_manifest.json")
    prompts = payload.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        raise AssertionError("prompt manifest has no prompts")
    hashes = [
        str(item.get("prompt_hash") or "")
        for item in prompts
        if isinstance(item, dict) and item.get("prompt_hash")
    ]
    if len(hashes) != len(prompts):
        raise AssertionError("prompt manifest rows must include prompt_hash")
    ratio = _unique_ratio(hashes)
    if ratio < min_unique_prompt_ratio:
        raise AssertionError(f"prompt diversity {ratio:.2f} is below {min_unique_prompt_ratio:.2f}")


def verify_image_manifest(project_dir: Path, min_unique_image_ratio: float) -> None:
    payload = _load_json(project_dir / "body_image_manifest.json")
    selected = payload.get("selected")
    if not isinstance(selected, list) or not selected:
        raise AssertionError("image manifest has no selected images")
    hashes: list[str] = []
    for item in selected:
        if not isinstance(item, dict):
            raise AssertionError("image manifest selected rows must be objects")
        if not isinstance(item.get("seed"), int):
            raise AssertionError("every selected image must include seed")
        if not item.get("prompt_hash"):
            raise AssertionError("every selected image must include prompt_hash")
        qa = item.get("qa")
        if not isinstance(qa, dict) or not isinstance(qa.get("score"), (int, float)):
            raise AssertionError("every selected image must include QA score")
        perceptual_hash = item.get("perceptual_hash")
        if not isinstance(perceptual_hash, str) or not perceptual_hash:
            raise AssertionError("every selected image must include perceptual_hash")
        hashes.append(perceptual_hash)
    ratio = _unique_ratio(hashes)
    if ratio < min_unique_image_ratio:
        raise AssertionError(f"image diversity {ratio:.2f} is below {min_unique_image_ratio:.2f}")


def verify_tts_consistency(project_dir: Path) -> None:
    payload = _load_json(project_dir / "tts" / "tts_consistency_report.json")
    if payload.get("metadata_consistent") is not True:
        raise AssertionError("TTS metadata consistency failed")
    if payload.get("audio_consistency_passed") is not True:
        raise AssertionError("TTS audio consistency failed")


def verify_render_report(project_dir: Path, min_duration_sec: float) -> None:
    payload = _load_json(project_dir / "render_report.json")
    if payload.get("duration_guard_passed") is not True:
        raise AssertionError("render duration guard failed")
    duration = payload.get("output_duration_sec")
    if not isinstance(duration, (int, float)) or float(duration) < min_duration_sec:
        raise AssertionError(f"render duration is below {min_duration_sec:.1f}s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--min-unique-prompt-ratio", type=float, default=0.85)
    parser.add_argument("--min-unique-image-ratio", type=float, default=0.85)
    parser.add_argument("--min-duration-sec", type=float, default=30.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    verify_prompt_manifest(args.project_dir, args.min_unique_prompt_ratio)
    verify_image_manifest(args.project_dir, args.min_unique_image_ratio)
    verify_tts_consistency(args.project_dir)
    verify_render_report(args.project_dir, args.min_duration_sec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
