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
    base_dir: Path = COMFYUI_WORKFLOW_DIR,
) -> dict[str, object]:
    workflow = copy.deepcopy(load_workflow_template(Z_IMAGE_TEMPLATE_ID, base_dir=base_dir))
    _set_first_widget(_find_node(workflow, POSITIVE_NODE_ID), positive_prompt)
    _set_first_widget(_find_node(workflow, NEGATIVE_NODE_ID), negative_prompt)
    width, height = _dimensions_for_aspect_ratio(aspect_ratio)
    latent = _find_node(workflow, LATENT_NODE_ID)
    latent["widgets_values"] = [width, height, 1]
    _set_first_widget(_find_node(workflow, SAVE_NODE_ID), filename_prefix)
    return convert_comfyui_graph_to_api(workflow)


def convert_comfyui_graph_to_api(workflow: dict[str, Any]) -> dict[str, object]:
    nodes = workflow.get("nodes")
    links = workflow.get("links", [])
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise HTTPException(500, "ComfyUI workflow graph export is invalid.")

    link_sources: dict[int, list[object]] = {}
    for link in links:
        if isinstance(link, list) and len(link) >= 6:
            link_id, origin_id, origin_slot = link[0], link[1], link[2]
            if isinstance(link_id, int):
                link_sources[link_id] = [str(origin_id), origin_slot]

    api: dict[str, object] = {}
    for node in nodes:
        if not isinstance(node, dict) or node.get("mode") == 2:
            continue
        node_id = node.get("id")
        class_type = node.get("type")
        if not isinstance(node_id, int) or not isinstance(class_type, str):
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
