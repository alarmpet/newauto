from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import db
from app.services.comfyui_client import ComfyUIClient
from app.services.comfyui_pipeline import import_history_image
from app.services.comfyui_prompt_adapter import build_prompt_placeholders
from app.services.comfyui_workflows import render_workflow_template
from app.services.image_generation_profiles import micro_conditioning_values, profile_for_request, profile_placeholders


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest root must be an object: {path}")
    return payload


def _submit_and_wait(
    client: ComfyUIClient,
    *,
    item: dict[str, Any],
    checkpoint: str,
    lora_name: str,
    width: int,
    height: int,
    seed: int,
    filename_prefix: str,
    client_id: str,
    timeout_sec: int,
    poll_sec: float,
) -> str:
    template_id = str(item.get("template_id") or "txt2img_sdxl_basic")
    positive_prompt = str(item.get("positive_prompt") or "")
    negative_prompt = str(item.get("negative_prompt") or "")
    profile = profile_for_request(quality_mode=str(item.get("quality_mode") or "fast"))
    placeholders: dict[str, object] = {
        "__CHECKPOINT__": checkpoint,
        **build_prompt_placeholders(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
        ),
        "__WIDTH__": width,
        "__HEIGHT__": height,
        "__SEED__": seed,
        **profile_placeholders(profile),
        **micro_conditioning_values(
            profile=profile,
            width=width,
            height=height,
            original_width=width,
            original_height=height,
            target_width=width,
            target_height=height,
            crop_w=0,
            crop_h=0,
        ),
        "__FILENAME_PREFIX__": filename_prefix,
    }
    if template_id == "txt2img_sdxl_stickman_lora":
        placeholders["__LORA_NAME__"] = str(item.get("lora_name") or lora_name)
        placeholders["__LORA_STRENGTH__"] = float(item.get("lora_strength") or 0.8)
    workflow = render_workflow_template(template_id, placeholders)
    submission = client.submit_workflow(workflow, client_id=client_id)
    deadline = time.monotonic() + max(timeout_sec, 1)
    while time.monotonic() < deadline:
        history = client.get_history(submission.prompt_id)
        images = client.extract_image_results(history, submission.prompt_id)
        if images:
            return submission.prompt_id
        execution_error = client.extract_execution_error(history, submission.prompt_id)
        if execution_error:
            raise RuntimeError(execution_error)
        time.sleep(max(poll_sec, 0.2))
    raise TimeoutError(f"No image produced within {timeout_sec} seconds.")


def _selected_items(manifest: dict[str, Any], *, count: int) -> list[dict[str, Any]]:
    prompts = manifest.get("prompts")
    if not isinstance(prompts, list):
        raise ValueError("Manifest has no prompts list.")
    items = [dict(item) for item in prompts if isinstance(item, dict)]
    return items[:count] if count > 0 else items


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate LoRA on/off images for a Stickman evidence bundle.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--checkpoint", default="sd_xl_base_1.0.safetensors")
    parser.add_argument("--lora-name", default="Stickfigures-000005.safetensors")
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=432)
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--seed-base", type=int, default=9000)
    parser.add_argument("--timeout-sec", type=int, default=240)
    parser.add_argument("--poll-sec", type=float, default=2.0)
    parser.add_argument("--client-id", default="newauto-stickman-evidence")
    args = parser.parse_args()

    db.init_db()
    project = db.get_project(args.project_id)
    if project is None:
        raise ValueError(f"Project not found: {args.project_id}")
    evidence_dir = db.project_dir(args.project_id) / "diagnostics_bundle" / "stickman_evidence"
    on_manifest = _load_manifest(evidence_dir / "prompts_lora_on.json")
    off_manifest = _load_manifest(evidence_dir / "prompts_lora_off.json")
    variants = [
        ("lora_on", _selected_items(on_manifest, count=args.count)),
        ("lora_off", _selected_items(off_manifest, count=args.count)),
    ]
    client = ComfyUIClient(timeout_sec=30)
    generated: list[dict[str, Any]] = []
    item_number = 0
    for variant_name, items in variants:
        for item in items:
            sentence_idx = int(item.get("sentence_idx") or 0)
            seed = args.seed_base + item_number
            item_number += 1
            prompt_id = _submit_and_wait(
                client,
                item=item,
                checkpoint=args.checkpoint,
                lora_name=args.lora_name,
                width=args.width,
                height=args.height,
                seed=seed,
                filename_prefix=f"{args.project_id}_{variant_name}_{sentence_idx:03d}",
                client_id=args.client_id,
                timeout_sec=args.timeout_sec,
                poll_sec=args.poll_sec,
            )
            latest = db.get_project(args.project_id)
            if latest is None:
                raise RuntimeError("Project disappeared during evidence generation.")
            project, imported_file, source_file = import_history_image(
                latest,
                prompt_id=prompt_id,
                sentence_idx=sentence_idx,
                prompt=str(item.get("positive_prompt") or ""),
                manifest_sentence_hash=str(item.get("sentence_hash") or ""),
                candidate_index=1 if variant_name == "lora_on" else 2,
                candidate_total=2,
                selected_reason="stickman_evidence",
                template_id=str(item.get("template_id") or ""),
                generation_profile=str(item.get("generation_profile") or ""),
                lora_name=str(item.get("lora_name") or args.lora_name) if variant_name == "lora_on" else "",
                width=args.width,
                height=args.height,
                prompt_item_override=item,
            )
            generated.append(
                {
                    "variant": variant_name,
                    "sentence_idx": sentence_idx,
                    "template_key": item.get("template_key", ""),
                    "template_id": item.get("template_id", ""),
                    "seed": seed,
                    "prompt_id": prompt_id,
                    "imported_file": imported_file,
                    "source_file": source_file,
                }
            )
    summary_path = evidence_dir / "generated_images.json"
    summary_path.write_text(
        json.dumps(
            {
                "project_id": args.project_id,
                "checkpoint": args.checkpoint,
                "lora_name": args.lora_name,
                "width": args.width,
                "height": args.height,
                "generated": generated,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"project_id": args.project_id, "summary_path": str(summary_path), "generated_count": len(generated)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
