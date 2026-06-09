from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..config import COMFYUI_WORKFLOW_DIR
from .comfyui_workflows import load_workflow_template

Z_IMAGE_TEMPLATE_ID = "community/deno2026/z_image_turbo_korean"
POSITIVE_NODE_ID = 67
NEGATIVE_NODE_ID = 191
LATENT_NODE_ID = 68
SAVE_NODE_ID = 228
UNET_NODE_IDS = (109, 130)
CLIP_NODE_ID = 62
VAE_NODE_ID = 63
DEFAULT_UNET_NAME = "z_image_turbo_nvfp4.safetensors"
DEFAULT_CLIP_NAME = "qwen_3_4b_fp8_mixed.safetensors"
DEFAULT_VAE_NAME = "ae.safetensors"

_WIDGET_INPUTS: dict[str, list[str]] = {
    "UNETLoader": ["unet_name", "weight_dtype"],
    "UnetLoaderGGUF": ["unet_name"],
    "CLIPLoader": ["clip_name", "type", "device"],
    "VAELoader": ["vae_name"],
    "CLIPTextEncode": ["text"],
    "EmptySD3LatentImage": ["width", "height", "batch_size"],
    "KSampler": ["seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "BasicScheduler": ["scheduler", "steps", "denoise"],
    "ImageScaleToTotalPixels": ["upscale_method", "megapixels", "resolution_steps"],
    "ImageScaleBy": ["upscale_method", "scale_by"],
    "SaveImage": ["filename_prefix"],
    "LoadImage": ["image", "upload"],
    "DenoResolutionSetup": ["mode", "aspect_ratio", "batch_size", "base_size"],
    "ModelSamplingAuraFlow": ["shift"],
    "Power Lora Loader (rgthree)": ["lora_stack"],
    "SimplePromptBatcher": ["prompt", "prefix", "suffix"],
}


def _find_node(workflow: dict[str, Any], node_id: int) -> dict[str, Any]:
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        raise HTTPException(500, "Z-Image workflow is not a ComfyUI graph export.")
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == node_id:
            return node
    raise HTTPException(500, f"Z-Image workflow node not found: {node_id}")


def _set_first_widget(node: dict[str, Any], value: object) -> None:
    widgets = node.get("widgets_values")
    if not isinstance(widgets, list):
        widgets = []
    if widgets:
        widgets[0] = value
    else:
        widgets.append(value)
    node["widgets_values"] = widgets


def _dimensions_for_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    ratio = aspect_ratio.strip().lower()
    if ratio in {"9:16", "shorts", "portrait"}:
        return 768, 1344
    if ratio in {"1:1", "square"}:
        return 1024, 1024
    return 1344, 768


def load_z_image_workflow(
    *,
    positive_prompt: str,
    negative_prompt: str,
    aspect_ratio: str = "16:9",
    filename_prefix: str = "newauto_z_image",
    seed: int = 8,
    unet_name: str = DEFAULT_UNET_NAME,
    clip_name: str = DEFAULT_CLIP_NAME,
    vae_name: str = DEFAULT_VAE_NAME,
    character_descriptor: dict[str, object] | None = None,
    base_dir: Path = COMFYUI_WORKFLOW_DIR,
) -> dict[str, object]:
    workflow = copy.deepcopy(load_workflow_template(Z_IMAGE_TEMPLATE_ID, base_dir=base_dir))
    # Validate the vendored workflow still contains the node classes D2 depends on.
    for node_id in (CLIP_NODE_ID, VAE_NODE_ID, POSITIVE_NODE_ID, NEGATIVE_NODE_ID, LATENT_NODE_ID, UNET_NODE_IDS[0], 107, 106, 111):
        _find_node(workflow, node_id)
    _set_first_widget(_find_node(workflow, CLIP_NODE_ID), clip_name)
    _set_first_widget(_find_node(workflow, VAE_NODE_ID), vae_name)
    width, height = _dimensions_for_aspect_ratio(aspect_ratio)
    sampler_model_input: list[object] = ["107", 0]
    api_workflow: dict[str, object] = {
        str(CLIP_NODE_ID): {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": clip_name, "type": "lumina2", "device": "default"},
        },
        str(VAE_NODE_ID): {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        str(POSITIVE_NODE_ID): {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": [str(CLIP_NODE_ID), 0], "text": positive_prompt},
        },
        str(NEGATIVE_NODE_ID): {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": [str(CLIP_NODE_ID), 0], "text": negative_prompt},
        },
        str(LATENT_NODE_ID): {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        str(UNET_NODE_IDS[0]): {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet_name, "weight_dtype": "default"},
        },
        "107": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": [str(UNET_NODE_IDS[0]), 0], "shift": 5},
        },
        "106": {
            "class_type": "KSampler",
            "inputs": {
                "model": sampler_model_input,
                "positive": [str(POSITIVE_NODE_ID), 0],
                "negative": [str(NEGATIVE_NODE_ID), 0],
                "latent_image": [str(LATENT_NODE_ID), 0],
                "seed": seed,
                "control_after_generate": "fixed",
                "steps": 9,
                "cfg": 1,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 0.6,
            },
        },
        "111": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["106", 0], "vae": [str(VAE_NODE_ID), 0]},
        },
        str(SAVE_NODE_ID): {
            "class_type": "SaveImage",
            "inputs": {"images": ["111", 0], "filename_prefix": filename_prefix},
        },
    }
    if character_descriptor:
        reference_image = str(
            character_descriptor.get("reference_image")
            or character_descriptor.get("image")
            or character_descriptor.get("image_path")
            or ""
        )
        weight = character_descriptor.get("weight", 0.75)
        api_workflow["300"] = {
            "class_type": "LoadImage",
            "inputs": {"image": reference_image, "upload": "image"},
        }
        api_workflow["301"] = {
            "class_type": "IPAdapterApply",
            "inputs": {"image": ["300", 0], "weight": weight, "model": ["107", 0]},
        }
        sampler = api_workflow["106"]
        if isinstance(sampler, dict):
            inputs = sampler.get("inputs")
            if isinstance(inputs, dict):
                inputs["model"] = ["301", 0]
    return api_workflow


def convert_comfyui_graph_to_api(workflow: dict[str, Any]) -> dict[str, object]:
    nodes = workflow.get("nodes")
    links = workflow.get("links", [])
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise HTTPException(500, "ComfyUI workflow graph export is invalid.")

    link_sources: dict[int, list[object]] = {}
    required_node_ids: set[int] = {SAVE_NODE_ID}
    incoming_by_node: dict[int, list[int]] = {}
    for link in links:
        if isinstance(link, list) and len(link) >= 6:
            link_id, origin_id, origin_slot, target_id = link[0], link[1], link[2], link[3]
            if isinstance(link_id, int):
                link_sources[link_id] = [str(origin_id), origin_slot]
            if isinstance(origin_id, int) and isinstance(target_id, int):
                incoming_by_node.setdefault(target_id, []).append(origin_id)

    queue = [SAVE_NODE_ID]
    while queue:
        node_id = queue.pop()
        for upstream_id in incoming_by_node.get(node_id, []):
            if upstream_id in required_node_ids:
                continue
            required_node_ids.add(upstream_id)
            queue.append(upstream_id)

    api: dict[str, object] = {}
    for node in nodes:
        if not isinstance(node, dict) or node.get("mode") == 2:
            continue
        node_id = node.get("id")
        class_type = node.get("type")
        if not isinstance(node_id, int) or not isinstance(class_type, str):
            continue
        if node_id not in required_node_ids:
            continue

        inputs: dict[str, object] = {}
        for item in node.get("inputs", []):
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            link = item.get("link")
            if isinstance(name, str) and isinstance(link, int) and link in link_sources:
                inputs[name] = link_sources[link]

        widget_names = _WIDGET_INPUTS.get(class_type, [])
        widgets = node.get("widgets_values")
        if isinstance(widgets, list):
            for index, value in enumerate(widgets):
                if index >= len(widget_names):
                    break
                inputs[widget_names[index]] = value

        api[str(node_id)] = {"class_type": class_type, "inputs": inputs}
    if not api:
        raise HTTPException(500, "ComfyUI workflow converted to an empty API prompt.")
    return api
