from pathlib import Path
from typing import TypedDict

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat


VISION_QA_VERSION = "vision_qa_v1"


class VisionQaResult(TypedDict):
    score: float
    version: str
    issue_codes: list[str]
    components: dict[str, float]
    reason: str


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _average_hash(image: Image.Image, hash_size: int = 8) -> list[int]:
    reduced = ImageOps.grayscale(image).resize((hash_size, hash_size))
    pixels = list(reduced.getdata())
    mean_value = sum(pixels) / max(1, len(pixels))
    return [1 if pixel >= mean_value else 0 for pixel in pixels]


def _hash_distance(left: list[int], right: list[int]) -> int:
    return sum(1 for left_bit, right_bit in zip(left, right) if left_bit != right_bit)


def _component_count(mask: Image.Image, *, sample_size: int = 96) -> tuple[int, float]:
    small = mask.resize((sample_size, sample_size))
    pixels = [1 if value > 0 else 0 for value in list(small.getdata())]
    visited = [False] * len(pixels)
    components = 0
    largest = 0
    for index, value in enumerate(pixels):
        if not value or visited[index]:
            continue
        components += 1
        stack = [index]
        visited[index] = True
        size = 0
        while stack:
            current = stack.pop()
            size += 1
            x = current % sample_size
            y = current // sample_size
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if nx < 0 or ny < 0 or nx >= sample_size or ny >= sample_size:
                    continue
                neighbor = ny * sample_size + nx
                if pixels[neighbor] and not visited[neighbor]:
                    visited[neighbor] = True
                    stack.append(neighbor)
        largest = max(largest, size)
    return components, largest / float(sample_size * sample_size)


def _color_scene_ratios(image: Image.Image, *, sample_width: int = 160) -> tuple[float, float]:
    target_height = max(1, round(image.height * (sample_width / max(1, image.width))))
    small = image.resize((sample_width, target_height))
    purple_pixels = 0
    neutral_pixels = 0
    total_pixels = max(1, sample_width * target_height)
    for red, green, blue in list(small.getdata()):
        if blue > 90 and red > 70 and blue > green + 24 and red > green + 8:
            purple_pixels += 1
        if max(red, green, blue) - min(red, green, blue) < 18 and max(red, green, blue) > 150:
            neutral_pixels += 1
    return purple_pixels / float(total_pixels), neutral_pixels / float(total_pixels)


def analyze_image_quality(
    image_path: Path,
    *,
    previous_image_path: Path | None = None,
    style_mode: str = "",
) -> VisionQaResult:
    with Image.open(image_path) as opened:
        image = opened.convert("RGB")
        grayscale = ImageOps.grayscale(image)
        width, height = image.size
        stat = ImageStat.Stat(grayscale)
        brightness = float(stat.mean[0]) if stat.mean else 0.0
        contrast = float(stat.stddev[0]) if stat.stddev else 0.0
        entropy = float(grayscale.entropy())
        edges = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
        edge_mask = edges.point(lambda value: 255 if value > 24 else 0)
        edge_bbox = edge_mask.getbbox()
        edge_density = 0.0
        if edge_bbox is not None:
            edge_pixels = len([value for value in list(edge_mask.getdata()) if value > 0])
            edge_density = edge_pixels / float(width * height)
        background = Image.new("RGB", image.size, image.resize((1, 1)).getpixel((0, 0)))
        foreground = ImageChops.difference(image, background).convert("L").point(lambda value: 255 if value > 28 else 0)
        component_count, dominant_area = _component_count(foreground)
        current_hash = _average_hash(grayscale)
        purple_ratio, neutral_ratio = _color_scene_ratios(image)

    issue_codes: list[str] = []
    components: dict[str, float] = {
        "resolution": 0.0,
        "entropy": 0.0,
        "contrast": 0.0,
        "edge_detail": 0.0,
        "exposure": 0.0,
        "duplicate_penalty": 0.0,
        "diagram_simplicity": 0.0,
        "diagram_subject_area": 0.0,
        "food_purple_accent": 0.0,
        "food_subject_area": 0.0,
        "food_scene_clarity": 0.0,
        "editorial_subject_area": 0.0,
        "editorial_scene_detail": 0.0,
        "editorial_clutter_control": 0.0,
        "editorial_flat_shape_penalty": 0.0,
    }

    min_edge = min(width, height)
    components["resolution"] = 0.15 if min_edge >= 512 else 0.05
    if min_edge < 512:
        issue_codes.append("LOW_RESOLUTION")

    entropy_score = _clamp((entropy - 3.5) / 3.5)
    components["entropy"] = entropy_score * 0.25
    if entropy_score < 0.35:
        issue_codes.append("LOW_ENTROPY")

    contrast_score = _clamp((contrast - 18.0) / 42.0)
    components["contrast"] = contrast_score * 0.2
    if contrast_score < 0.3:
        issue_codes.append("LOW_CONTRAST")

    edge_score = _clamp((edge_mean - 8.0) / 28.0)
    components["edge_detail"] = edge_score * 0.2
    if edge_score < 0.28:
        issue_codes.append("LOW_EDGE_DETAIL")

    exposure_score = 1.0 - _clamp(abs(brightness - 128.0) / 96.0)
    components["exposure"] = exposure_score * 0.1
    if brightness < 45.0 or brightness > 210.0:
        issue_codes.append("EXTREME_EXPOSURE")

    if previous_image_path is not None and previous_image_path.exists():
        with Image.open(previous_image_path) as previous_opened:
            previous_hash = _average_hash(previous_opened.convert("RGB"))
        distance = _hash_distance(current_hash, previous_hash)
        if distance <= 4:
            issue_codes.append("NEAR_DUPLICATE_PREVIOUS")
            components["duplicate_penalty"] = -0.1

    if style_mode == "simple_diagram":
        edge_density_score = 1.0 - _clamp((edge_density - 0.08) / 0.18)
        components["diagram_simplicity"] = edge_density_score * 0.18
        if edge_density > 0.20:
            issue_codes.append("DENSE_DIAGRAM_CLUTTER")
        if component_count > 42:
            issue_codes.append("TINY_ICON_GRID")
            components["diagram_simplicity"] -= 0.08
        subject_score = _clamp((dominant_area - 0.035) / 0.13)
        components["diagram_subject_area"] = subject_score * 0.17
        if dominant_area < 0.045:
            issue_codes.append("DOMINANT_SUBJECT_TOO_SMALL")
        if edge_density > 0.16 and dominant_area < 0.07:
            issue_codes.append("ABSTRACT_UI_NO_CLEAR_SUBJECT")
        if component_count > 28 and dominant_area < 0.08:
            issue_codes.append("GENERIC_DASHBOARD_LAYOUT")
    elif style_mode == "editorial_science":
        material_detail_score = _clamp((edge_mean - 10.0) / 24.0)
        subject_area_score = _clamp((dominant_area - 0.025) / 0.12)
        components["editorial_material_detail"] = material_detail_score * 0.08
        components["editorial_subject_area"] = subject_area_score * 0.08
        if dominant_area < 0.03:
            issue_codes.append("EDITORIAL_SUBJECT_TOO_SMALL")
        if entropy_score < 0.32 and edge_score < 0.30:
            issue_codes.append("LOW_MATERIAL_DETAIL")
    elif style_mode == "food_trend_editorial":
        purple_score = _clamp((purple_ratio - 0.015) / 0.12)
        subject_area_score = _clamp((dominant_area - 0.03) / 0.13)
        scene_clarity_score = 1.0 - _clamp((neutral_ratio - 0.70) / 0.22)
        components["food_purple_accent"] = purple_score * 0.09
        components["food_subject_area"] = subject_area_score * 0.08
        components["food_scene_clarity"] = scene_clarity_score * 0.07
        if purple_ratio < 0.01:
            issue_codes.append("FOOD_TREND_PURPLE_ACCENT_WEAK")
        if dominant_area < 0.04:
            issue_codes.append("FOOD_TREND_SUBJECT_TOO_SMALL")
        if neutral_ratio > 0.78 and dominant_area < 0.07:
            issue_codes.append("FOOD_TREND_EMPTY_INTERIOR")
        if entropy_score < 0.34 and purple_ratio < 0.012 and dominant_area < 0.06:
            issue_codes.append("FOOD_TREND_GENERIC_INTERIOR")
    elif style_mode == "editorial_symbolic":
        subject_area_score = _clamp((dominant_area - 0.035) / 0.14)
        scene_detail_score = _clamp(((entropy_score + contrast_score + edge_score) / 3.0) / 0.55)
        clutter_score = 1.0 - _clamp((component_count - 24) / 28.0)
        flat_shape_penalty = 0.0
        if edge_density < 0.025 and entropy_score < 0.35:
            flat_shape_penalty = -0.10
            issue_codes.append("EDITORIAL_FLAT_SHAPE_ONLY")
        components["editorial_subject_area"] = subject_area_score * 0.09
        components["editorial_scene_detail"] = scene_detail_score * 0.08
        components["editorial_clutter_control"] = clutter_score * 0.07
        components["editorial_flat_shape_penalty"] = flat_shape_penalty
        if dominant_area < 0.035:
            issue_codes.append("EDITORIAL_SUBJECT_TOO_SMALL")
        if entropy_score < 0.30 and contrast_score < 0.30:
            issue_codes.append("EDITORIAL_SCENE_TOO_FLAT")
        if component_count > 36 and dominant_area < 0.09:
            issue_codes.append("EDITORIAL_CLUTTERED_SYMBOLS")

    score = _clamp(sum(components.values()))
    if score >= 0.78:
        reason = "strong_image_sanity"
    elif score >= 0.55:
        reason = "acceptable_image_sanity"
    else:
        reason = "weak_image_sanity"

    return {
        "score": score,
        "version": VISION_QA_VERSION,
        "issue_codes": issue_codes,
        "components": components,
        "reason": reason,
    }
