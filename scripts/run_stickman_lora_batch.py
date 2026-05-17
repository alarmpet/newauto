from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import cast

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import HTTPException

from app import db
from app.services.comfyui_client import ComfyUIClient
from app.services.comfyui_pipeline import import_history_image
from app.services.comfyui_prompt_adapter import build_prompt_placeholders
from app.services.comfyui_workflows import render_workflow_template
from app.services.image_generation_profiles import micro_conditioning_values, profile_for_request, profile_placeholders
from app.services.image_prompting import save_image_prompt_manifest, suggest_image_prompt_batch
from app.types import ProjectRecord


DEFAULT_SENTENCES: list[str] = [
    "소년은 돌을 쥐고 거인을 향해 달려갑니다.",
    "그는 무릎을 꿇고 간절히 기도합니다.",
    "시간이 없어 시계 앞으로 달려갑니다.",
    "돈을 쥔 채 갈림길 앞에서 선택을 망설입니다.",
    "유혹 앞에서 금지된 물건에 손을 뻗습니다.",
    "넘어졌지만 다시 일어나 앞으로 걸어갑니다.",
    "거센 비바람과 파도 앞에서 두려움을 마주합니다.",
    "책상 앞에서 책을 펴고 집중해 공부합니다.",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a stickman LoRA sample batch and import it into a project.")
    parser.add_argument("--title", default="Stickman LoRA Batch")
    parser.add_argument("--checkpoint", default="sd_xl_base_1.0.safetensors")
    parser.add_argument("--lora-name", default="Stickfigures-000005.safetensors")
    parser.add_argument("--lora-strength", type=float, default=0.8)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=432)
    parser.add_argument("--seed-base", type=int, default=5000)
    parser.add_argument("--variants-per-scene", type=int, default=1)
    parser.add_argument("--sentence-indices", default="")
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--poll-sec", type=float, default=2.0)
    parser.add_argument("--client-id", default="newauto-stickman-batch")
    return parser.parse_args()


def _selected_indices(raw_value: str) -> list[int]:
    cleaned = raw_value.strip()
    if not cleaned:
        return list(range(len(DEFAULT_SENTENCES)))
    values: list[int] = []
    for chunk in cleaned.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.append(max(0, int(chunk)))
    return values


def _create_project(title: str) -> ProjectRecord:
    project = db.create_project(title=title)
    script = "\n".join(DEFAULT_SENTENCES)
    updated = db.update_project(
        project["id"],
        script=script,
        user_script=script,
        compiled_script=script,
        sentences=DEFAULT_SENTENCES,
        content_mode="standard",
        visual_source_mode="comfyui_auto",
    )
    if updated is None:
        raise RuntimeError("Project update failed after creation.")
    return updated


def _submit_and_wait(
    client: ComfyUIClient,
    *,
    checkpoint: str,
    positive_prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    seed: int,
    filename_prefix: str,
    client_id: str,
    lora_name: str,
    lora_strength: float,
    timeout_sec: int,
    poll_sec: float,
) -> tuple[str, dict[str, object]]:
    profile = profile_for_request(quality_mode="balanced")
    workflow = render_workflow_template(
        "txt2img_sdxl_stickman_lora",
        {
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
            "__LORA_NAME__": lora_name,
            "__LORA_STRENGTH__": lora_strength,
        },
    )
    submission = client.submit_workflow(workflow, client_id=client_id)
    deadline = time.monotonic() + max(timeout_sec, 1)
    while time.monotonic() < deadline:
        history = client.get_history(submission.prompt_id)
        images = client.extract_image_results(history, submission.prompt_id)
        if images:
            return submission.prompt_id, {
                "filename": images[0].filename,
                "subfolder": images[0].subfolder,
                "type": images[0].type,
            }
        execution_error = client.extract_execution_error(history, submission.prompt_id)
        if execution_error:
            raise RuntimeError(execution_error)
        time.sleep(max(poll_sec, 0.2))
    raise TimeoutError(f"No image produced within {timeout_sec} seconds.")


def main() -> int:
    args = _parse_args()
    db.init_db()
    project = _create_project(args.title)
    selected_indices = _selected_indices(args.sentence_indices)
    suggestions = [
        item
        for item in suggest_image_prompt_batch(project, start_idx=0, count=len(DEFAULT_SENTENCES))
        if cast(int, item["sentence_idx"]) in selected_indices
    ]
    manifest_path = save_image_prompt_manifest(
        db.project_dir(project["id"]) / "image_prompts_manifest.json",
        project=project,
        source="stickman_lora_batch",
        prompts=suggestions,
    )
    client = ComfyUIClient()
    imported_items: list[dict[str, object]] = []
    variant_count = max(1, args.variants_per_scene)

    for index, item in enumerate(suggestions):
        sentence_idx = cast(int, item["sentence_idx"])
        positive_prompt = str(item["positive_prompt"])
        negative_prompt = str(item["negative_prompt"])
        for variant_index in range(variant_count):
            seed = args.seed_base + (index * variant_count) + variant_index
            prompt_id, output_info = _submit_and_wait(
                client,
                checkpoint=args.checkpoint,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                width=args.width,
                height=args.height,
                seed=seed,
                filename_prefix=f"{project['id']}_stickman_{sentence_idx:03d}_v{variant_index + 1}",
                client_id=args.client_id,
                lora_name=args.lora_name,
                lora_strength=args.lora_strength,
                timeout_sec=args.timeout_sec,
                poll_sec=args.poll_sec,
            )
            latest = db.get_project(project["id"])
            if latest is None:
                raise RuntimeError("Project disappeared during batch generation.")
            updated_project, imported_file, source_file = import_history_image(
                latest,
                prompt_id=prompt_id,
                sentence_idx=sentence_idx,
                prompt=positive_prompt,
            )
            project = updated_project
            imported_items.append(
                {
                    "sentence_idx": sentence_idx,
                    "template_key": item.get("template_key", ""),
                    "variant_index": variant_index + 1,
                    "seed": seed,
                    "prompt_id": prompt_id,
                    "sentence_hash": item.get("sentence_hash", ""),
                    "positive_prompt": positive_prompt,
                    "negative_prompt": negative_prompt,
                    "source_file": source_file,
                    "output_info": output_info,
                    "imported_file": imported_file,
                }
            )

    summary_path = db.project_dir(project["id"]) / "stickman_lora_batch_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "project_id": project["id"],
                "title": project["title"],
                "checkpoint": args.checkpoint,
                "lora_name": args.lora_name,
                "lora_strength": args.lora_strength,
                "sentence_indices": selected_indices,
                "variants_per_scene": variant_count,
                "manifest_path": str(manifest_path),
                "items": imported_items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "project_id": project["id"],
                "project_dir": str(db.project_dir(project["id"])),
                "manifest_path": str(manifest_path),
                "summary_path": str(summary_path),
                "media_count": len(project["media_order"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HTTPException as exc:
        print(json.dumps({"http_error": {"status_code": exc.status_code, "detail": exc.detail}}, ensure_ascii=False))
        raise SystemExit(1)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
