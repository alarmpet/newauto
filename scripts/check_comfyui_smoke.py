from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import HTTPException

from app.config import COMFYUI_BASE_URL
from app.services.comfyui_client import ComfyUIClient
from app.services.comfyui_prompt_adapter import build_prompt_placeholders
from app.services.image_generation_profiles import (
    micro_conditioning_values,
    profile_for_request,
    profile_placeholders,
)
from app.services.comfyui_workflows import render_workflow_template


def _request_json(base_url: str, path: str) -> dict[str, Any]:
    request = Request(urljoin(base_url.rstrip("/") + "/", path), method="GET")
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}".strip()) from exc
    except URLError as exc:
        raise RuntimeError(f"ComfyUI connection failed: {exc.reason}") from exc
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ComfyUI system_stats returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("ComfyUI system_stats returned a non-object payload.")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a lightweight ComfyUI smoke check.")
    parser.add_argument("--base-url", default=COMFYUI_BASE_URL)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--template-id", default="txt2img_sdxl_basic")
    parser.add_argument("--positive-prompt", default="cinematic documentary still, quiet korean room, morning light, realistic, 16:9")
    parser.add_argument("--negative-prompt", default="text, watermark, logo, blurry, low quality, distorted hands")
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=432)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--filename-prefix", default="newauto_smoke")
    parser.add_argument("--lora-name", default="")
    parser.add_argument("--lora-strength", type=float, default=0.8)
    parser.add_argument("--style-reference-image", default="")
    parser.add_argument("--style-reference-strength", type=float, default=0.65)
    parser.add_argument("--control-image", default="")
    parser.add_argument("--control-strength", type=float, default=0.75)
    parser.add_argument("--generation-profile", default="")
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--poll-sec", type=float, default=2.0)
    args = parser.parse_args()

    payload: dict[str, Any] = {
        "base_url": args.base_url,
        "checkpoint": args.checkpoint,
        "template_id": args.template_id,
        "lora_name": args.lora_name,
        "lora_strength": args.lora_strength,
        "style_reference_image": args.style_reference_image,
    }
    try:
        profile = profile_for_request(quality_mode="balanced", generation_profile=args.generation_profile or "")
        payload["system_stats"] = _request_json(args.base_url, "system_stats")
        workflow = render_workflow_template(
            args.template_id,
            {
                "__CHECKPOINT__": args.checkpoint,
                **build_prompt_placeholders(
                    positive_prompt=args.positive_prompt,
                    negative_prompt=args.negative_prompt,
                ),
                "__WIDTH__": args.width,
                "__HEIGHT__": args.height,
                "__SEED__": args.seed,
                **profile_placeholders(profile),
                "__FILENAME_PREFIX__": args.filename_prefix,
                "__LORA_NAME__": args.lora_name,
                "__LORA_STRENGTH__": args.lora_strength,
                "__STYLE_REFERENCE_IMAGE__": args.style_reference_image,
                "__STYLE_REFERENCE_STRENGTH__": args.style_reference_strength,
                "__CONTROL_IMAGE__": args.control_image,
                "__CONTROL_STRENGTH__": args.control_strength,
                **micro_conditioning_values(
                    profile=profile,
                    width=args.width,
                    height=args.height,
                    original_width=args.width,
                    original_height=args.height,
                    target_width=args.width,
                    target_height=args.height,
                    crop_w=0,
                    crop_h=0,
                ),
            },
        )
        client = ComfyUIClient(base_url=args.base_url)
        submission = client.submit_workflow(workflow, client_id="newauto-smoke")
        payload["submission"] = asdict(submission)

        deadline = time.monotonic() + max(args.timeout_sec, 1)
        while time.monotonic() < deadline:
            history = client.get_history(submission.prompt_id)
            images = client.extract_image_results(history, submission.prompt_id)
            if images:
                payload["result"] = {
                    "prompt_id": submission.prompt_id,
                    "images": [asdict(image) for image in images],
                }
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 0
            execution_error = client.extract_execution_error(history, submission.prompt_id)
            if execution_error:
                payload["execution_error"] = execution_error
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                return 2
            time.sleep(max(args.poll_sec, 0.2))
        payload["timeout"] = f"No image was produced within {args.timeout_sec} seconds."
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 3
    except HTTPException as exc:
        payload["http_error"] = {
            "status_code": exc.status_code,
            "detail": exc.detail,
        }
    except Exception as exc:  # noqa: BLE001
        payload["error"] = str(exc)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
