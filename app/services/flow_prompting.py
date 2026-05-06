import json
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from fastapi import HTTPException
from typing_extensions import NotRequired, TypedDict

from .. import db
from ..types import ProjectRecord
from .hpsl_script import HpslPayload, load_hpsl_payload
from .visual_relevance import sentence_hash


class FlowPromptEntry(TypedDict):
    sentence_idx: int
    sentence_hash: str
    section: str
    narration: str
    core_keyword: str
    visual_keyword: str
    emotion: str
    aspect_ratio: str
    prompt: str
    negative_prompt: str
    asset_path: str
    status: str
    updated_at: str
    source: str


class FlowPromptManifest(TypedDict):
    version: int
    project_id: str
    generated_at: str
    aspect_ratio: str
    mode: str
    entries: list[FlowPromptEntry]
    flow_project_url: NotRequired[str]


def flow_prompt_manifest_path(pid: str) -> Path:
    return db.project_dir(pid) / "flow_prompts.json"


def flow_assets_dir(pid: str) -> Path:
    path = db.project_dir(pid) / "flow_assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: str, fallback: str) -> str:
    stripped = value.strip()
    return stripped if stripped else fallback


def _is_ascii_text(value: str) -> bool:
    return all(ord(char) < 128 for char in value)


def _keyword_scene(text: str) -> str:
    lowered = text.lower()
    if "gemini" in lowered and ("home" in lowered or "camera" in lowered or "smart" in lowered):
        return "Google Gemini smart home assistant controlling cameras and connected home devices"
    if "gemini" in lowered or "google" in lowered or "ai" in lowered:
        return "Google Gemini AI assistant shown as a practical everyday productivity companion"
    if "agent" in lowered or "nano banana" in lowered:
        return "AI agent workspace with clean visual layout panels and an image generation control surface"
    if "video" in lowered or "8" in lowered:
        return "short-form video generation workstation producing a polished vertical cinematic clip"
    if "music" in lowered or "melody" in lowered or "lo-fi" in lowered:
        return "AI music creation desk with waveform layers, melody blocks, and calm lo-fi production controls"
    korean_matches: tuple[tuple[str, str], ...] = (
        ("카메라", "smart camera feed review screen with clear AI event markers"),
        ("스마트", "connected smart home devices responding to an AI assistant"),
        ("동영상", "short-form video generation workstation producing a polished vertical cinematic clip"),
        ("영상", "short-form video generation workstation producing a polished vertical cinematic clip"),
        ("음악", "AI music creation desk with waveform layers and melody controls"),
        ("멜로디", "AI music creation desk with waveform layers and melody controls"),
        ("로파이", "calm lo-fi music production desk with soft studio lighting"),
        ("사진", "creative AI studio transforming a photo into a customized media scene"),
        ("감정", "creative AI interface translating emotions into visual mood boards"),
        ("농담", "creative AI assistant turning a short joke into a playful media concept"),
        ("아이디어", "rough idea sketch transforming into a finished vertical video scene"),
        ("생각", "rough idea sketch transforming into a finished vertical video scene"),
        ("기능", "clean product feature showcase with modular AI tool panels"),
        ("레이아웃", "clean visual layout editor with organized AI-generated panels"),
        ("일상", "everyday person using an AI assistant on a phone and laptop"),
    )
    for keyword, scene in korean_matches:
        if keyword in text:
            return scene
    return "clear editorial technology scene about a practical AI workflow"


def _english_visual_text(*, sentence: str, core_keyword: str, visual_keyword: str) -> str:
    candidates = [visual_keyword.strip(), core_keyword.strip(), sentence.strip()]
    for candidate in candidates:
        if candidate and _is_ascii_text(candidate):
            return candidate[:180]
    return _keyword_scene(" ".join(candidates))


def _build_flow_prompt(
    *,
    sentence: str,
    core_keyword: str,
    visual_keyword: str,
    emotion: str,
    aspect_ratio: str,
    section: str,
) -> str:
    subject = _safe_text(
        _english_visual_text(sentence=sentence, core_keyword=core_keyword, visual_keyword=visual_keyword),
        "a concrete visual metaphor matching the narration",
    )
    action = _safe_text(
        _english_visual_text(sentence=sentence, core_keyword=core_keyword, visual_keyword=core_keyword),
        "showing the key idea clearly",
    )
    mood = _safe_text(emotion, "focused curiosity")
    return "\n".join(
        [
            f"Create a cinematic {aspect_ratio} image for a Korean YouTube {section} narration.",
            f"Subject: {subject}.",
            f"Action/meaning: {action}.",
            "Setting: realistic editorial documentary scene with a clear foreground subject and uncluttered background.",
            f"Mood: {mood}.",
            "Camera: medium-wide shot, strong composition, natural perspective.",
            "Lighting: clean cinematic lighting, high clarity, realistic details.",
            "Style: realistic editorial documentary, polished but not glossy, suitable for YouTube storytelling.",
            "Avoid: text overlays, subtitles, readable words, logos, watermarks, UI screenshots, distorted hands, clutter.",
            "Narration language: Korean. Do not render Korean text in the image.",
        ]
    )


def _entry_from_hpsl_sentence(
    *,
    sentence_idx: int,
    section: str,
    narration: str,
    core_keyword: str,
    visual_keyword: str,
    emotion: str,
    aspect_ratio: str,
    source: str,
    existing_asset_path: str = "",
) -> FlowPromptEntry:
    prompt = _build_flow_prompt(
        sentence=narration,
        core_keyword=core_keyword,
        visual_keyword=visual_keyword,
        emotion=emotion,
        aspect_ratio=aspect_ratio,
        section=section,
    )
    return {
        "sentence_idx": sentence_idx,
        "sentence_hash": sentence_hash(narration),
        "section": section,
        "narration": narration,
        "core_keyword": core_keyword,
        "visual_keyword": visual_keyword,
        "emotion": emotion,
        "aspect_ratio": aspect_ratio,
        "prompt": prompt,
        "negative_prompt": "text, subtitles, readable words, logo, watermark, UI, clutter, low quality",
        "asset_path": existing_asset_path,
        "status": "asset_attached" if existing_asset_path else "prompt_ready",
        "updated_at": _now(),
        "source": source,
    }


def _entries_from_hpsl(payload: HpslPayload, *, aspect_ratio: str) -> list[FlowPromptEntry]:
    entries: list[FlowPromptEntry] = []
    for sentence_idx, sentence in enumerate(payload["sentences"]):
        entries.append(
            _entry_from_hpsl_sentence(
                sentence_idx=sentence_idx,
                section=sentence["section"],
                narration=sentence["narration"],
                core_keyword=sentence["core_keyword"],
                visual_keyword=sentence["visual_keyword"],
                emotion=sentence["emotion"],
                aspect_ratio=aspect_ratio,
                source="hpsl",
            )
        )
    return entries


def _entries_from_project(project: ProjectRecord, *, aspect_ratio: str) -> list[FlowPromptEntry]:
    entries: list[FlowPromptEntry] = []
    for sentence_idx, sentence in enumerate(project["sentences"]):
        entries.append(
            _entry_from_hpsl_sentence(
                sentence_idx=sentence_idx,
                section="body",
                narration=sentence,
                core_keyword=sentence[:80],
                visual_keyword=sentence[:80],
                emotion="focused curiosity",
                aspect_ratio=aspect_ratio,
                source="compiled_script",
            )
        )
    return entries


def load_flow_prompt_manifest(project: ProjectRecord) -> FlowPromptManifest:
    path = flow_prompt_manifest_path(project["id"])
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict):
            entries_raw = raw.get("entries")
            entries: list[FlowPromptEntry] = []
            if isinstance(entries_raw, list):
                for item in entries_raw:
                    if not isinstance(item, dict):
                        continue
                    sentence_idx = item.get("sentence_idx")
                    narration = item.get("narration")
                    prompt = item.get("prompt")
                    if not isinstance(sentence_idx, int) or not isinstance(narration, str) or not isinstance(prompt, str):
                        continue
                    entries.append(
                        {
                            "sentence_idx": sentence_idx,
                            "sentence_hash": str(item.get("sentence_hash") or sentence_hash(narration)),
                            "section": str(item.get("section") or "body"),
                            "narration": narration,
                            "core_keyword": str(item.get("core_keyword") or ""),
                            "visual_keyword": str(item.get("visual_keyword") or ""),
                            "emotion": str(item.get("emotion") or ""),
                            "aspect_ratio": str(item.get("aspect_ratio") or "9:16"),
                            "prompt": prompt,
                            "negative_prompt": str(item.get("negative_prompt") or ""),
                            "asset_path": str(item.get("asset_path") or ""),
                            "status": str(item.get("status") or "prompt_ready"),
                            "updated_at": str(item.get("updated_at") or ""),
                            "source": str(item.get("source") or "manifest"),
                        }
                    )
            return {
                "version": 1,
                "project_id": project["id"],
                "generated_at": str(raw.get("generated_at") or ""),
                "aspect_ratio": str(raw.get("aspect_ratio") or "9:16"),
                "mode": str(raw.get("mode") or "assisted"),
                "entries": entries,
                "flow_project_url": str(raw.get("flow_project_url") or ""),
            }
    return {
        "version": 1,
        "project_id": project["id"],
        "generated_at": "",
        "aspect_ratio": "9:16",
        "mode": "assisted",
        "entries": [],
        "flow_project_url": "",
    }


def save_flow_prompt_manifest(pid: str, manifest: FlowPromptManifest) -> None:
    path = flow_prompt_manifest_path(pid)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_flow_prompt_manifest(
    project: ProjectRecord,
    *,
    aspect_ratio: str = "9:16",
    mode: str = "assisted",
) -> FlowPromptManifest:
    normalized_aspect_ratio = aspect_ratio.strip() if aspect_ratio.strip() in {"9:16", "16:9", "1:1"} else "9:16"
    hpsl_payload = load_hpsl_payload(project)
    entries = (
        _entries_from_hpsl(hpsl_payload, aspect_ratio=normalized_aspect_ratio)
        if hpsl_payload is not None
        else _entries_from_project(project, aspect_ratio=normalized_aspect_ratio)
    )
    if not entries:
        raise HTTPException(400, "Save or generate a script before creating Flow prompts.")
    existing = load_flow_prompt_manifest(project)
    existing_assets = {entry["sentence_idx"]: entry["asset_path"] for entry in existing["entries"] if entry["asset_path"]}
    merged_entries: list[FlowPromptEntry] = []
    for entry in entries:
        asset_path = existing_assets.get(entry["sentence_idx"], "")
        if asset_path:
            updated = dict(entry)
            updated["asset_path"] = asset_path
            updated["status"] = "asset_attached"
            merged_entries.append(cast(FlowPromptEntry, updated))
        else:
            merged_entries.append(entry)
    manifest: FlowPromptManifest = {
        "version": 1,
        "project_id": project["id"],
        "generated_at": _now(),
        "aspect_ratio": normalized_aspect_ratio,
        "mode": mode,
        "entries": merged_entries,
        "flow_project_url": existing.get("flow_project_url", ""),
    }
    save_flow_prompt_manifest(project["id"], manifest)
    return manifest


def attach_flow_asset_to_manifest(project: ProjectRecord, *, sentence_idx: int, asset_path: str) -> FlowPromptManifest:
    manifest = load_flow_prompt_manifest(project)
    if not manifest["entries"]:
        manifest = generate_flow_prompt_manifest(project)
    updated_entries: list[FlowPromptEntry] = []
    found = False
    for entry in manifest["entries"]:
        if entry["sentence_idx"] == sentence_idx:
            updated = dict(entry)
            updated["asset_path"] = asset_path
            updated["status"] = "asset_attached"
            updated["updated_at"] = _now()
            updated_entries.append(cast(FlowPromptEntry, updated))
            found = True
        else:
            updated_entries.append(entry)
    if not found:
        raise HTTPException(404, f"sentence index {sentence_idx} has no Flow prompt.")
    manifest["entries"] = updated_entries
    save_flow_prompt_manifest(project["id"], manifest)
    return manifest
