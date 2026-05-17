from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import cast

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


BASE_URL = os.environ.get(
    "NEWAUTO_BASE_URL",
    f"http://127.0.0.1:{os.environ.get('NEWAUTO_API_PORT', '9002')}",
).rstrip("/")
FLOW_URL = os.environ.get("FLOW_URL", "https://labs.google/fx/tools/flow").strip() or "https://labs.google/fx/tools/flow"
ROOT_DIR = Path(__file__).resolve().parents[1]
MAKELENS_FLOW_PROFILE_DIR = Path.home() / "music-auto" / "browser_profiles" / "automation_notebooklm"
PROFILE_DIR = Path(
    os.environ.get(
        "FLOW_PROFILE_DIR",
        str(MAKELENS_FLOW_PROFILE_DIR if MAKELENS_FLOW_PROFILE_DIR.exists() else ROOT_DIR / "data" / "flow-browser-profile"),
    )
)
LOG_DIR = ROOT_DIR / "storage" / "logs"
DOWNLOADS_DIR = Path.home() / "Downloads"
FLOW_ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm"}
CDP_PORT = int(os.environ.get("FLOW_CDP_PORT", "9225"))
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
FLOW_PROMPT_SUBMIT_DELAY_MS = int(max(12.0, float(os.environ.get("FLOW_PROMPT_SUBMIT_DELAY_SECONDS", "15"))) * 1000)
FLOW_GENERATE_COOLDOWN_MS = int(max(75.0, float(os.environ.get("FLOW_GENERATE_COOLDOWN_SECONDS", "90"))) * 1000)
FLOW_DIRECT_TIMEOUT_SECONDS = int(max(30.0, float(os.environ.get("FLOW_DIRECT_TIMEOUT_SECONDS", "120"))))
FLOW_DIRECT_RETRIES = int(max(1.0, float(os.environ.get("FLOW_DIRECT_RETRIES", "3"))))
FLOW_DIRECT_FRESH_PROJECT_EACH_PROMPT = os.environ.get("FLOW_DIRECT_FRESH_PROJECT_EACH_PROMPT", "1").strip().lower() not in {"0", "false", "no"}
FLOW_DIRECT_ATTACH = os.environ.get("FLOW_DIRECT_ATTACH", "1").strip().lower() not in {"0", "false", "no"}

PROMPT_INPUT_SELECTORS = [
    "div[role='textbox']",
    "textarea:not([id*='recaptcha'])",
    ".prompt-input",
    "[contenteditable='true']",
    "textarea",
    "input[type='text']",
]
GENERATE_BUTTON_SELECTORS = [
    "button:has(.material-icons:has-text('arrow_forward'))",
    "button:has(i:has-text('arrow_forward'))",
    "button:has(span:has-text('arrow_forward'))",
    ".generate-button",
    "[aria-label*='Generate']",
    "[aria-label*='만들기']",
    "[aria-label*='생성']",
    "button:has-text('Generate')",
    "button:has-text('만들기')",
    "button:has-text('생성')",
    "button:has-text('Create shot')",
    "button:has-text('Generate shots')",
]
FLOW_IMAGE_MODE_SELECTORS = [
    "button:has-text('Image')",
    "button:has-text('이미지')",
    "button:has-text('Nano Banana')",
    "text=Image",
    "text=이미지",
]
FLOW_SCENE_BUILDER_SELECTORS = [
    "button:has-text('Scene builder')",
    "button:has-text('Scene Builder')",
    "button:has-text('장면 빌더')",
    "button:has(.material-icons:has-text('play_movies'))",
    "button:has(i:has-text('play_movies'))",
    "button:has(span:has-text('play_movies'))",
    "[aria-label*='Scene builder' i]",
    "[aria-label*='장면 빌더']",
]
FLOW_CREATE_ENTRY_SELECTORS = [
    "button:has(.material-icons:has-text('add_2'))",
    "button:has(i:has-text('add_2'))",
    "button:has(span:has-text('add_2'))",
    "button:has-text('Create')",
    "button:has-text('만들기')",
    "[aria-label*='Create' i]",
    "[aria-label*='만들기']",
]
NEW_PROJECT_LABELS = [
    "New project",
    "Create project",
    "Start new project",
    "New",
    "Create",
    "새 프로젝트",
    "새 프로젝트 만들기",
    "프로젝트 만들기",
    "만들기",
]
GENERATE_LABELS = [
    "Generate",
    "Create",
    "Submit",
    "Send",
    "Create shot",
    "Generate shot",
    "Generate shots",
    "만들기",
    "생성",
    "제출",
    "보내기",
]
FLOW_CARD_MENU_BUTTON_SELECTORS = [
    "button[aria-haspopup='menu'][aria-label*='more options' i]",
    "button[aria-haspopup='menu'][aria-label*='options' i]",
    "button[aria-haspopup='menu']:has(.google-symbols:has-text('more_vert'))",
    "button[aria-haspopup='menu']:has(i:has-text('more_vert'))",
    "button[aria-haspopup='menu']:has(span:has-text('more_vert'))",
]
FLOW_DOWNLOAD_ITEM_SELECTORS = [
    "[role='menuitem']:has-text('Download')",
    "[role='menuitem']:has-text('download')",
    "[role='menuitem']:has-text('다운로드')",
    "button:has-text('Download')",
    "button:has-text('download')",
    "button:has-text('다운로드')",
    "div[role='menuitem']:has-text('Download')",
    "div[role='menuitem']:has-text('download')",
    "div[role='menuitem']:has-text('다운로드')",
]
FLOW_DOWNLOAD_RESOLUTION_SELECTORS = [
    "button:has-text('1K')",
    "[role='menuitem']:has-text('1K')",
    "[role='option']:has-text('1K')",
    "text=1K",
]
FLOW_DETAIL_DOWNLOAD_BUTTON_SELECTORS = [
    "button[aria-label*='Download' i]",
    "button[title*='Download' i]",
    "button:has(.google-symbols:has-text('download'))",
    "button:has(i:has-text('download'))",
    "button:has(span:has-text('download'))",
    "button:has-text('Download')",
    "button:has-text('다운로드')",
]
RESULT_MIN_WIDTH = 160
RESULT_MIN_HEIGHT = 120


class FlowAutomationError(RuntimeError):
    pass


def _request_json(path: str) -> dict[str, object]:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=30) as response:
        raw = response.read().decode("utf-8", errors="replace")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise FlowAutomationError(f"Unexpected JSON payload from {path}")
    return cast(dict[str, object], payload)


def _post_json(path: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise FlowAutomationError(f"Unexpected JSON payload from {path}")
    return cast(dict[str, object], parsed)


def _log(project_id: str, message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"flow_browser_{project_id}.log"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def _manifest_entries(project_id: str) -> list[dict[str, object]]:
    manifest = _request_json(f"/api/flow/prompts/{project_id}")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _visible_first(locator: Locator) -> Locator | None:
    try:
        count = locator.count()
    except Exception:
        return None
    for index in range(count):
        item = locator.nth(index)
        try:
            if item.is_visible(timeout=500) and item.is_enabled(timeout=500):
                return item
        except Exception:
            continue
    return None


def _viewport_size(locator: Locator) -> tuple[int, int]:
    try:
        viewport = locator.page.viewport_size or {}
    except Exception:
        viewport = {}
    width = int(viewport.get("width") or 1280)
    height = int(viewport.get("height") or 720)
    return width, height


def _is_in_viewport(locator: Locator) -> bool:
    try:
        box = locator.bounding_box(timeout=500)
    except Exception:
        return False
    if not box:
        return False
    width, height = _viewport_size(locator)
    center_x = float(box.get("x") or 0) + (float(box.get("width") or 0) / 2)
    center_y = float(box.get("y") or 0) + (float(box.get("height") or 0) / 2)
    return 0 <= center_x <= width and 0 <= center_y <= height


def _first_actionable(locator: Locator) -> Locator | None:
    visible: list[Locator] = []
    try:
        count = locator.count()
    except Exception:
        return None
    for index in range(count):
        item = locator.nth(index)
        try:
            if not item.is_visible(timeout=500) or not item.is_enabled(timeout=500):
                continue
            visible.append(item)
            if _is_in_viewport(item):
                return item
        except Exception:
            continue
    for item in visible:
        try:
            item.scroll_into_view_if_needed(timeout=1000)
            if _is_in_viewport(item):
                return item
        except Exception:
            continue
    return visible[0] if visible else None


def _safe_click(locator: Locator, *, timeout: int = 3000) -> None:
    try:
        locator.scroll_into_view_if_needed(timeout=1000)
    except Exception:
        pass
    try:
        locator.click(timeout=timeout, force=True)
        return
    except Exception:
        pass
    locator.evaluate("(el) => el.click()")


def _is_prompt_input_meta(meta: dict[str, object]) -> bool:
    if not isinstance(meta, dict):
        return False
    label = " ".join(
        str(meta.get(key) or "").lower()
        for key in ("placeholder", "aria", "title", "role", "type")
    )
    if any(token in label for token in ("search", "검색", "asset", "애셋", "filter", "필터", "sort", "정렬")):
        return False
    width = int(meta.get("width") or 0)
    height = int(meta.get("height") or 0)
    if width < 120 or height < 18:
        return False
    tag = str(meta.get("tag") or "")
    if tag == "textarea":
        return True
    if str(meta.get("contenteditable") or "").lower() == "true":
        return True
    if tag == "input" and str(meta.get("type") or "") in {"", "text"}:
        return True
    return str(meta.get("role") or "") == "textbox"


def _is_prompt_input_candidate(locator: Locator) -> bool:
    try:
        meta = locator.evaluate(
            """(el) => {
                const rect = el.getBoundingClientRect();
                return {
                    tag: String(el.tagName || '').toLowerCase(),
                    type: String(el.getAttribute('type') || '').toLowerCase(),
                    role: String(el.getAttribute('role') || '').toLowerCase(),
                    placeholder: String(el.getAttribute('placeholder') || ''),
                    aria: String(el.getAttribute('aria-label') || ''),
                    title: String(el.getAttribute('title') || ''),
                    contenteditable: String(el.getAttribute('contenteditable') || ''),
                    width: Math.round(rect.width || 0),
                    height: Math.round(rect.height || 0)
                };
            }"""
        )
    except Exception:
        return False
    return _is_prompt_input_meta(cast(dict[str, object], meta))


def _find_prompt_input(page: Page) -> Locator | None:
    candidates = [
        page.locator("textarea"),
        page.locator("[contenteditable='true']"),
        page.get_by_role("textbox"),
        page.locator("input[type='text']"),
    ]
    for candidate in candidates:
        try:
            count = candidate.count()
        except Exception:
            continue
        for index in range(count):
            item = candidate.nth(index)
            try:
                if item.is_visible(timeout=500) and item.is_enabled(timeout=500) and _is_prompt_input_candidate(item):
                    return item
            except Exception:
                continue
    return None


def _find_button_by_labels(page: Page, labels: list[str]) -> Locator | None:
    for label in labels:
        item = _visible_first(page.get_by_role("button", name=label))
        if item is not None:
            return item
        item = _visible_first(page.get_by_role("link", name=label))
        if item is not None:
            return item
        escaped = re.escape(label)
        pattern = re.compile(escaped, re.IGNORECASE)
        for locator in (
            page.get_by_role("button", name=pattern),
            page.get_by_role("link", name=pattern),
            page.locator("button").filter(has_text=pattern),
            page.locator("a").filter(has_text=pattern),
            page.locator("[role='button']").filter(has_text=pattern),
        ):
            item = _visible_first(locator)
            if item is not None:
                return item
    return None


def _click_first_visible(locator: Locator, *, timeout: int = 3000) -> bool:
    item = _first_actionable(locator)
    if item is None:
        return False
    _safe_click(item, timeout=timeout)
    return True


def _find_visible(page: Page, selectors: list[str], *, timeout_ms: int = 3000) -> Locator | None:
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        for selector in selectors:
            try:
                locator = page.locator(selector)
                item = _first_actionable(locator)
                if item is not None:
                    return item
            except Exception:
                continue
        time.sleep(0.15)
    return None


def _click_visible(page: Page, selectors: list[str], *, timeout_ms: int = 3000) -> bool:
    target = _find_visible(page, selectors, timeout_ms=timeout_ms)
    if target is None:
        return False
    try:
        _safe_click(target, timeout=min(timeout_ms, 3000))
        return True
    except Exception:
        return False


def _read_body_excerpt(page: Page, limit: int = 500) -> str:
    try:
        text = str(page.locator("body").inner_text(timeout=1000) or "")
    except Exception:
        return ""
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 3].rstrip() + "..."


def _flow_page_markers(page: Page) -> dict[str, bool]:
    body = _read_body_excerpt(page, limit=3000).lower()
    return {
        "has_scene_builder": "장면 빌더" in body or "scene builder" in body,
        "has_asset_search": "애셋 검색" in body or "asset search" in body,
        "has_create": "만들기" in body or "create" in body,
        "has_prompt_input": _find_prompt_input(page) is not None,
    }


def _enter_scene_builder_if_present(page: Page, project_id: str) -> bool:
    if _find_prompt_input(page) is not None:
        return False
    markers = _flow_page_markers(page)
    clicked = False
    if markers["has_scene_builder"]:
        if _click_visible(page, FLOW_SCENE_BUILDER_SELECTORS, timeout_ms=2500):
            clicked = True
            _log(project_id, "Clicked Flow Scene Builder entry point.")
            page.wait_for_timeout(1500)
            _dismiss_overlays(page)
    if _find_prompt_input(page) is not None:
        return clicked
    if markers["has_create"] or clicked:
        if _click_visible(page, FLOW_CREATE_ENTRY_SELECTORS, timeout_ms=2500):
            clicked = True
            _log(project_id, "Clicked Flow Create entry point.")
            page.wait_for_timeout(1500)
            _dismiss_overlays(page)
    return clicked


def _open_new_project_if_present(page: Page, project_id: str) -> bool:
    try:
        clicked = page.evaluate(
            """() => {
                const labels = [
                    'new project',
                    'create project',
                    'start new project',
                    '새 프로젝트',
                    '새 프로젝트 만들기',
                    '프로젝트 만들기'
                ];
                const isTarget = (el) => {
                    const text = [
                        el.innerText || '',
                        el.textContent || '',
                        el.getAttribute('aria-label') || '',
                        el.getAttribute('title') || ''
                    ].join(' ').trim();
                    const normalized = text.toLowerCase().replace(/\\s+/g, ' ');
                    const rect = el.getBoundingClientRect();
                    if (rect.width <= 20 || rect.height <= 20) return false;
                    if (labels.some((label) => normalized.includes(label))) return true;
                    return normalized === '+' || normalized.startsWith('+ ');
                };
                const controls = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                const target = controls.find(isTarget) ||
                    Array.from(document.querySelectorAll('div, span')).find(isTarget);
                if (!target) return false;
                target.click();
                return true;
            }"""
        )
        if clicked is True:
            _log(project_id, "Clicked Flow new project button via DOM text.")
            page.wait_for_timeout(2000)
            return True
    except Exception:
        pass
    label_item = _find_button_by_labels(page, NEW_PROJECT_LABELS)
    if label_item is not None:
        try:
            label_item.click(timeout=3000, force=True)
            _log(project_id, "Clicked Flow new project button via role/text label.")
            page.wait_for_timeout(1500)
            return True
        except Exception:
            pass
    candidates = [
        page.get_by_role("button", name=re.compile(r"새\s*프로젝트|new\s*project", re.IGNORECASE)),
        page.get_by_role("link", name=re.compile(r"새\s*프로젝트|new\s*project", re.IGNORECASE)),
        page.locator("[aria-label*='New project' i]"),
        page.locator("[aria-label*='Create project' i]"),
        page.locator("[aria-label*='새 프로젝트']"),
        page.locator("[title*='New project' i]"),
        page.locator("[title*='새 프로젝트']"),
        page.locator("button").filter(has_text=re.compile(r"새\s*프로젝트|\+", re.IGNORECASE)),
    ]
    for candidate in candidates:
        try:
            if _click_first_visible(candidate):
                _log(project_id, "Clicked Flow new project button.")
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


def _dismiss_overlays(page: Page) -> None:
    for _ in range(2):
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(200)
    _click_visible(
        page,
        [
            "button[aria-label*='close' i]",
            "button[aria-label*='Close']",
            ".close-button",
            ".dismiss-button",
            "button:has(i:has-text('close'))",
            "button:has(span:has-text('close'))",
            "button:has-text('Got it')",
            "button:has-text('Done')",
        ],
        timeout_ms=1000,
    )
    try:
        page.evaluate(
            """() => {
                for (const wrapper of Array.from(document.querySelectorAll("[data-radix-popper-content-wrapper]"))) {
                    const rect = wrapper.getBoundingClientRect();
                    if (rect.width > 20 && rect.height > 20) {
                        document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
                    }
                }
            }"""
        )
    except Exception:
        pass


def _prepare_flow_workspace(page: Page, project_id: str) -> None:
    page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        pass
    _dismiss_overlays(page)
    _enter_scene_builder_if_present(page, project_id)
    _open_new_project_if_present(page, project_id)
    page.wait_for_timeout(2000)
    _dismiss_overlays(page)
    _click_visible(page, FLOW_IMAGE_MODE_SELECTORS, timeout_ms=1500)
    _enter_scene_builder_if_present(page, project_id)
    _dismiss_overlays(page)


def _media_candidates(page: Page) -> list[dict[str, object]]:
    try:
        payload = page.evaluate(
            """() => Array.from(document.querySelectorAll("img, canvas, video"))
                .map((el, index) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    const src = "currentSrc" in el
                        ? String(el.currentSrc || el.src || "")
                        : String(el.getAttribute("src") || "");
                    const tile = el.closest("[data-tile-id]");
                    return {
                        index,
                        tag: String(el.tagName || "").toLowerCase(),
                        src,
                        width: Math.round(rect.width || 0),
                        height: Math.round(rect.height || 0),
                        top: Math.round(rect.top || 0),
                        left: Math.round(rect.left || 0),
                        tile_id: tile ? String(tile.getAttribute("data-tile-id") || "") : "",
                        visible: style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0"
                    };
                })
                .filter((item) => item.visible && item.width >= 160 && item.height >= 120 && item.top > -40)"""
        )
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    candidates: list[dict[str, object]] = []
    for item in payload:
        if isinstance(item, dict):
            key = f"{item.get('tag')}:{item.get('tile_id')}:{item.get('src')}:{item.get('width')}x{item.get('height')}:{item.get('left')}:{item.get('top')}"
            normalized = dict(item)
            normalized["key"] = key
            candidates.append(normalized)
    candidates.sort(key=lambda item: (int(item.get("top") or 0), int(item.get("left") or 0), int(item.get("index") or 0)))
    return candidates


def _media_keys(page: Page) -> set[str]:
    return {str(item.get("key") or "") for item in _media_candidates(page) if str(item.get("key") or "")}


def _wait_for_new_result(page: Page, previous_keys: set[str]) -> tuple[bool, str]:
    deadline = time.time() + FLOW_DIRECT_TIMEOUT_SECONDS
    while time.time() < deadline:
        current = _media_candidates(page)
        current_keys = {str(item.get("key") or "") for item in current if str(item.get("key") or "")}
        if current_keys - previous_keys:
            return True, ""
        body = _read_body_excerpt(page).lower()
        for marker in ("something went wrong", "please try again", "temporarily unavailable"):
            if marker in body:
                return False, marker
        time.sleep(0.75)
    return False, "timeout waiting for a new Flow result"


def _set_prompt_input(input_box: Locator, prompt: str) -> None:
    page = input_box.page
    _dismiss_overlays(page)
    try:
        input_box.evaluate(
            """(el) => {
                el.scrollIntoView({block: "center", inline: "nearest"});
                el.focus();
                const selection = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(el);
                selection.removeAllRanges();
                selection.addRange(range);
            }"""
        )
        page.keyboard.press("Backspace")
        page.keyboard.insert_text(prompt)
        return
    except Exception:
        pass
    input_box.click(timeout=5000, force=True)
    try:
        input_box.fill(prompt, timeout=5000)
        return
    except Exception:
        pass
    input_box.press("Control+A")
    input_box.press("Backspace")
    input_box.page.keyboard.insert_text(prompt)


def _bytes_from_media_candidate(page: Page, candidate: dict[str, object]) -> bytes:
    tag = str(candidate.get("tag") or "").lower()
    index = int(candidate.get("index") or 0)
    src = str(candidate.get("src") or "")
    if tag == "canvas":
        data_url = page.evaluate(
            """(index) => {
                const canvas = Array.from(document.querySelectorAll("canvas"))[index];
                return canvas ? canvas.toDataURL("image/png") : "";
            }""",
            index,
        )
        raw = str(data_url or "")
        if "," not in raw:
            raise FlowAutomationError("Canvas result did not expose an image data URL.")
        return base64.b64decode(raw.split(",", 1)[1])
    if src.startswith("blob:") or src.startswith("data:") or src.startswith("http://") or src.startswith("https://"):
        data_url = page.evaluate(
            """async (src) => {
                const response = await fetch(src, {credentials: "include"});
                if (!response.ok) {
                    throw new Error(`fetch failed ${response.status}`);
                }
                const blob = await response.blob();
                return await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(String(reader.result || ""));
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }""",
            src,
        )
        raw = str(data_url or "")
        if "," not in raw:
            raise FlowAutomationError("Flow result blob did not expose image bytes.")
        return base64.b64decode(raw.split(",", 1)[1])
    raise FlowAutomationError("No downloadable Flow result source was found.")


def _download_save_path(output_path: Path, suggested_filename: str | None) -> Path:
    suffix = Path(str(suggested_filename or "")).suffix.lower()
    if suffix in FLOW_ASSET_EXTENSIONS and suffix != output_path.suffix.lower():
        return output_path.with_suffix(suffix)
    return output_path


def _save_playwright_download(download: object, output_path: Path) -> Path:
    suggested = getattr(download, "suggested_filename", None)
    save_path = _download_save_path(output_path, str(suggested or ""))
    save_path.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(str(save_path))  # type: ignore[attr-defined]
    if save_path.stat().st_size <= 0:
        raise FlowAutomationError("Downloaded Flow image was empty.")
    return save_path


def _media_locator_for_candidate(page: Page, candidate: dict[str, object]) -> Locator:
    index = int(candidate.get("index") or 0)
    tile_id = str(candidate.get("tile_id") or "").strip()
    if tile_id:
        try:
            scoped = page.locator(
                f"[data-tile-id='{tile_id}'] img, "
                f"[data-tile-id='{tile_id}'] canvas, "
                f"[data-tile-id='{tile_id}'] video"
            ).first
            if scoped.count():
                return scoped
        except Exception:
            pass
    return page.locator("img, canvas, video").nth(index)


def _candidate_menu_scopes(page: Page, candidate: dict[str, object]) -> list[Locator | Page]:
    scopes: list[Locator | Page] = []
    tile_id = str(candidate.get("tile_id") or "").strip()
    if tile_id:
        try:
            tile = page.locator(f"[data-tile-id='{tile_id}']").first
            if tile.count():
                scopes.append(tile)
        except Exception:
            pass
    scopes.append(page)
    return scopes


def _try_download_from_open_menu(page: Page, click_target: Locator, output_path: Path) -> Path | None:
    try:
        with page.expect_download(timeout=12_000) as download_info:
            click_target.click(timeout=2_500, force=True)
            page.wait_for_timeout(250)
            resolution_item = _find_visible(page, FLOW_DOWNLOAD_RESOLUTION_SELECTORS, timeout_ms=3_000)
            if resolution_item is not None:
                resolution_item.click(timeout=2_500, force=True)
        return _save_playwright_download(download_info.value, output_path)
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return None


def _try_download_via_flow_card_menu(page: Page, candidate: dict[str, object], output_path: Path) -> Path | None:
    result_locator = _media_locator_for_candidate(page, candidate)
    try:
        result_locator.scroll_into_view_if_needed(timeout=2_000)
        result_locator.hover(timeout=2_000)
        page.wait_for_timeout(250)
    except Exception:
        pass

    for scope in _candidate_menu_scopes(page, candidate):
        for selector in FLOW_CARD_MENU_BUTTON_SELECTORS:
            try:
                locator = scope.locator(selector)  # type: ignore[union-attr]
                count = min(locator.count(), 4)
            except Exception:
                continue
            for index in range(count):
                menu_button = locator.nth(index)
                try:
                    if not menu_button.is_visible(timeout=500):
                        continue
                    if scope is page:
                        box = menu_button.bounding_box()
                        if box and float(box.get("y") or 0.0) < 80:
                            continue
                    menu_button.click(timeout=2_500, force=True)
                    page.wait_for_timeout(250)
                    download_item = _find_visible(page, FLOW_DOWNLOAD_ITEM_SELECTORS, timeout_ms=3_000)
                    if download_item is None:
                        page.keyboard.press("Escape")
                        continue
                    saved = _try_download_from_open_menu(page, download_item, output_path)
                    if saved is not None:
                        return saved
                except Exception:
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass
                    continue
    return None


def _try_download_via_flow_detail(page: Page, candidate: dict[str, object], output_path: Path) -> Path | None:
    result_locator = _media_locator_for_candidate(page, candidate)
    try:
        result_locator.scroll_into_view_if_needed(timeout=2_000)
        result_locator.click(timeout=3_000, force=True)
        page.wait_for_timeout(1_000)
    except Exception:
        return None

    for selector in FLOW_DETAIL_DOWNLOAD_BUTTON_SELECTORS:
        try:
            locator = page.locator(selector)
            count = min(locator.count(), 4)
        except Exception:
            continue
        for index in range(count):
            button = locator.nth(index)
            try:
                if not button.is_visible(timeout=500):
                    continue
                saved = _try_download_from_open_menu(page, button, output_path)
                if saved is not None:
                    return saved
            except Exception:
                continue
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    return None


def _try_download_latest_result(page: Page, candidate: dict[str, object], output_path: Path) -> Path | None:
    _dismiss_overlays(page)
    saved = _try_download_via_flow_card_menu(page, candidate, output_path)
    if saved is not None:
        return saved
    _dismiss_overlays(page)
    return _try_download_via_flow_detail(page, candidate, output_path)


def _save_latest_result_image(page: Page, output_path: Path) -> Path:
    candidates = [
        item
        for item in _media_candidates(page)
        if str(item.get("tag") or "").lower() in {"img", "canvas"}
        and int(item.get("width") or 0) >= RESULT_MIN_WIDTH
        and int(item.get("height") or 0) >= RESULT_MIN_HEIGHT
    ]
    if not candidates:
        raise FlowAutomationError("No visible Flow image result was found.")
    selected = sorted(
        candidates,
        key=lambda item: (int(item.get("top") or 0), int(item.get("left") or 0), int(item.get("index") or 0)),
    )[-1]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    downloaded_path = _try_download_latest_result(page, selected, output_path)
    if downloaded_path is not None:
        return downloaded_path
    try:
        output_path.write_bytes(_bytes_from_media_candidate(page, selected))
    except Exception:
        handles = page.query_selector_all("img, canvas, video")
        selected_index = int(selected.get("index") or -1)
        if selected_index < 0 or selected_index >= len(handles):
            raise
        handles[selected_index].screenshot(path=str(output_path))
    if output_path.stat().st_size <= 0:
        raise FlowAutomationError("Saved Flow image was empty.")
    return output_path


def _attach_generated_asset(project_id: str, sentence_number: int, output_path: Path) -> dict[str, object]:
    if not FLOW_DIRECT_ATTACH:
        return {"attached": [], "skipped": [], "path": str(output_path)}
    return _post_json(
        f"/api/flow/assets/{project_id}/attach-local",
        {"paths": [str(output_path)], "start_sentence_number": sentence_number},
    )


def _ensure_prompt_surface(page: Page, project_id: str) -> Locator | None:
    input_box = _find_prompt_input(page)
    if input_box is not None:
        return input_box
    _enter_scene_builder_if_present(page, project_id)
    input_box = _find_prompt_input(page)
    if input_box is not None:
        return input_box
    _open_new_project_if_present(page, project_id)
    _enter_scene_builder_if_present(page, project_id)
    return _find_prompt_input(page)


def _find_generate_button(page: Page) -> Locator | None:
    item = _find_button_by_labels(page, GENERATE_LABELS)
    if item is not None:
        return item
    text_candidates = page.locator("button").filter(has_text="Generate")
    item = _visible_first(text_candidates)
    if item is not None:
        return item
    aria_candidates = [
        page.locator("[aria-label*='Send' i]"),
        page.locator("[aria-label*='Submit' i]"),
        page.locator("[aria-label*='Generate' i]"),
        page.locator("[aria-label*='Create' i]"),
        page.locator("[aria-label*='보내']"),
        page.locator("[aria-label*='생성']"),
        page.locator("[aria-label*='만들기']"),
        page.locator("[title*='Generate' i]"),
        page.locator("[title*='Create' i]"),
        page.locator("[title*='보내']"),
        page.locator("[title*='생성']"),
        page.locator("[title*='만들기']"),
    ]
    for candidate in aria_candidates:
        item = _visible_first(candidate)
        if item is not None:
            return item
    visible_buttons: list[Locator] = []
    try:
        buttons = page.locator("button")
        for index in range(buttons.count()):
            button = buttons.nth(index)
            if button.is_visible(timeout=300) and button.is_enabled(timeout=300):
                visible_buttons.append(button)
    except Exception:
        visible_buttons = []
    return visible_buttons[-1] if visible_buttons else None


def _download_buttons(page: Page) -> list[Locator]:
    locators = [
        page.get_by_role("button", name=re.compile("download|다운로드", re.IGNORECASE)),
        page.get_by_role("link", name=re.compile("download|다운로드", re.IGNORECASE)),
        page.locator("[aria-label*='Download' i]"),
        page.locator("[aria-label*='다운로드' i]"),
        page.locator("[title*='Download' i]"),
        page.locator("[title*='다운로드' i]"),
        page.locator("text=/다운로드|Download/i"),
        page.locator("a[download]"),
    ]
    buttons: list[Locator] = []
    for locator in locators:
        try:
            count = locator.count()
        except Exception:
            continue
        for index in range(count):
            item = locator.nth(index)
            try:
                if item.is_visible(timeout=300) and item.is_enabled(timeout=300):
                    buttons.append(item)
            except Exception:
                continue
    return buttons


def _fill_prompt(input_box: Locator, prompt: str) -> None:
    input_box.click(timeout=5000)
    try:
        input_box.fill(prompt, timeout=5000)
    except Exception:
        input_box.press("Control+A")
        input_box.press("Backspace")
        input_box.page.keyboard.insert_text(prompt)


def _wait_for_new_downloads(started_at: float, *, expected: int, timeout_sec: int) -> list[Path]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        candidates = [
            path
            for path in DOWNLOADS_DIR.iterdir()
            if path.is_file()
            and path.suffix.lower() in FLOW_ASSET_EXTENSIONS
            and path.stat().st_mtime >= started_at
            and not path.name.endswith(".crdownload")
        ]
        if len(candidates) >= expected:
            candidates.sort(key=lambda item: item.stat().st_mtime)
            return candidates[:expected]
        time.sleep(2.0)
    candidates = [
        path
        for path in DOWNLOADS_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() in FLOW_ASSET_EXTENSIONS
        and path.stat().st_mtime >= started_at
        and not path.name.endswith(".crdownload")
    ]
    candidates.sort(key=lambda item: item.stat().st_mtime)
    return candidates


def _chrome_executable() -> Path:
    browser = os.environ.get("FLOW_BROWSER", "").strip().lower()
    chrome_candidates = [
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    ]
    edge_candidates = [
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    ]
    if browser in {"edge", "msedge", "microsoft-edge"}:
        candidates = edge_candidates + chrome_candidates
    elif browser in {"chrome", "google-chrome"}:
        candidates = chrome_candidates + edge_candidates
    else:
        candidates = chrome_candidates + edge_candidates
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FlowAutomationError("Chrome or Edge executable was not found.")


def _cdp_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def _ensure_cdp_browser() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    if _cdp_ready():
        return
    executable = _chrome_executable()
    subprocess.Popen(
        [
            str(executable),
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={PROFILE_DIR}",
            "--new-window",
            FLOW_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        if _cdp_ready():
            return
        time.sleep(0.5)
    raise FlowAutomationError("Flow CDP browser did not become ready.")


def _connect_context() -> tuple[Playwright, Browser, BrowserContext]:
    _ensure_cdp_browser()
    playwright = sync_playwright().start()
    browser = playwright.chromium.connect_over_cdp(CDP_URL)
    if not browser.contexts:
        raise FlowAutomationError("No browser context is available over CDP.")
    return playwright, browser, browser.contexts[0]


def open_flow(project_id: str) -> dict[str, object]:
    playwright, browser, context = _connect_context()
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeoutError:
        pass
    clicked = _open_new_project_if_present(page, project_id)
    _log(project_id, "Opened Flow browser for user authentication.")
    playwright.stop()
    return {
        "ok": True,
        "clicked_new_project": clicked,
        "message": "Flow opened. Authenticate in the visible browser if needed.",
    }


def fill_or_generate(
    project_id: str,
    *,
    start_sentence_number: int,
    limit: int,
    click_generate: bool,
) -> dict[str, object]:
    entries = _manifest_entries(project_id)
    start_idx = max(0, start_sentence_number - 1)
    selected = [
        entry
        for entry in entries
        if isinstance(entry.get("sentence_idx"), int)
        and cast(int, entry["sentence_idx"]) >= start_idx
        and not str(entry.get("asset_path") or "").strip()
    ]
    if limit > 0:
        selected = selected[:limit]
    if not selected:
        return {"ok": True, "message": "No prompt entries need Flow generation.", "count": 0}

    if click_generate and os.environ.get("FLOW_DIRECT_GENERATE", "1").strip().lower() not in {"0", "false", "no"}:
        return generate_direct_and_attach(project_id, selected)

    playwright, browser, context = _connect_context()
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=30000)
    input_box = _ensure_prompt_surface(page, project_id)
    if input_box is None:
        _log(project_id, "Prompt input not found. User probably needs to authenticate or Flow UI changed.")
        playwright.stop()
        return {
            "ok": False,
            "needs_user": True,
            "message": "Prompt input was not found. Authenticate in Flow, close popups, then run the automation again.",
        }

    started_at = time.time()
    processed = 0
    for entry in selected:
        sentence_idx = cast(int, entry["sentence_idx"])
        prompt = str(entry.get("prompt") or "").strip()
        if not prompt:
            continue
        _fill_prompt(input_box, prompt)
        _log(project_id, f"Filled Flow prompt for sentence {sentence_idx + 1}.")
        if click_generate:
            page.wait_for_timeout(FLOW_PROMPT_SUBMIT_DELAY_MS)
            button = _find_generate_button(page)
            if button is None:
                return {
                    "ok": False,
                    "needs_user": True,
                    "message": f"Filled sentence {sentence_idx + 1}, but could not find a Generate button.",
                    "processed": processed,
                }
            button.click(timeout=10000)
            _log(project_id, f"Clicked Generate for sentence {sentence_idx + 1}.")
            if processed + 1 < len(selected):
                page.wait_for_timeout(FLOW_GENERATE_COOLDOWN_MS)
            else:
                page.wait_for_timeout(2500)
        processed += 1

    result = {
        "ok": True,
        "processed": processed,
        "download_wait_hint": "Download the generated Flow assets, then run attach_latest_flow_downloads.",
        "downloads_seen": [str(path) for path in _wait_for_new_downloads(started_at, expected=processed, timeout_sec=3)],
    }
    playwright.stop()
    return result


def _generate_direct_records(
    project_id: str,
    selected: list[dict[str, object]],
    generated_dir: Path,
    *,
    attach_to_project: bool,
) -> dict[str, object]:
    playwright, browser, context = _connect_context()
    page = context.pages[0] if context.pages else context.new_page()
    generated_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    attached: list[str] = []
    try:
        _prepare_flow_workspace(page, project_id)
        for offset, entry in enumerate(selected):
            sentence_idx = cast(int, entry["sentence_idx"])
            sentence_number = sentence_idx + 1
            prompt = str(entry.get("prompt") or "").strip()
            if not prompt:
                continue
            if offset > 0 and FLOW_DIRECT_FRESH_PROJECT_EACH_PROMPT:
                _prepare_flow_workspace(page, project_id)
            output_name = str(entry.get("output_name") or "").strip()
            output_path = generated_dir / (
                output_name if output_name else f"flow_s{sentence_number:03d}_{time.strftime('%Y%m%dT%H%M%S')}.png"
            )
            if output_path.suffix.lower() not in FLOW_ASSET_EXTENSIONS:
                output_path = output_path.with_suffix(".png")
            last_error = ""
            for attempt in range(1, FLOW_DIRECT_RETRIES + 1):
                try:
                    input_box = _ensure_prompt_surface(page, project_id)
                    if input_box is None:
                        raise FlowAutomationError("Flow prompt input was not found.")
                    previous_keys = _media_keys(page)
                    _set_prompt_input(input_box, prompt)
                    page.wait_for_timeout(500)
                    button = _find_visible(page, GENERATE_BUTTON_SELECTORS, timeout_ms=4000)
                    if button is not None:
                        _safe_click(button, timeout=5000)
                    else:
                        input_box.press("Enter")
                    _log(project_id, f"Clicked Flow Generate for sentence {sentence_number}, attempt {attempt}.")
                    ok, reason = _wait_for_new_result(page, previous_keys)
                    if not ok:
                        raise FlowAutomationError(reason)
                    saved_path = _save_latest_result_image(page, output_path)
                    attach_payload = (
                        _attach_generated_asset(project_id, sentence_number, saved_path)
                        if attach_to_project
                        else {"attached": [], "skipped": [], "path": str(saved_path)}
                    )
                    attached.extend(str(item) for item in attach_payload.get("attached", []) if str(item))
                    records.append(
                        {
                            "sentence_number": sentence_number,
                            "status": "ok",
                            "attempt": attempt,
                            "source": str(entry.get("source") or ""),
                            "path": str(saved_path),
                            "attached": attach_payload.get("attached", []),
                        }
                    )
                    break
                except Exception as exc:
                    last_error = str(exc)
                    _log(project_id, f"Flow direct generation failed for sentence {sentence_number}, attempt {attempt}: {last_error}")
                    if attempt < FLOW_DIRECT_RETRIES:
                        _prepare_flow_workspace(page, project_id)
                        page.wait_for_timeout(min(5000 * attempt, 15000))
                        continue
                    records.append(
                        {
                            "sentence_number": sentence_number,
                            "status": "failed",
                            "attempt": attempt,
                            "error": last_error,
                            "body_excerpt": _read_body_excerpt(page),
                        }
                    )
    finally:
        playwright.stop()

    failed = [record for record in records if record.get("status") != "ok"]
    result = {
        "ok": not failed,
        "mode": "flow_direct_generate_attach",
        "project_id": project_id,
        "processed": len([record for record in records if record.get("status") == "ok"]),
        "requested": len(selected),
        "attached": attached,
        "records": records,
        "profile_dir": str(PROFILE_DIR),
        "cdp_url": CDP_URL,
    }
    if failed:
        result["message"] = f"Flow direct generation failed for {len(failed)} sentence(s)."
    return result


def generate_direct_and_attach(project_id: str, selected: list[dict[str, object]]) -> dict[str, object]:
    generated_dir = ROOT_DIR / "storage" / "projects" / project_id / "flow_generated"
    return _generate_direct_records(project_id, selected, generated_dir, attach_to_project=True)


def _prompt_file_entries(prompt_dir: Path, pattern: str, limit: int) -> list[dict[str, object]]:
    files = sorted(path for path in prompt_dir.glob(pattern) if path.is_file())
    if limit > 0:
        files = files[:limit]
    entries: list[dict[str, object]] = []
    for index, path in enumerate(files):
        prompt = path.read_text(encoding="utf-8").strip()
        if not prompt:
            continue
        entries.append(
            {
                "sentence_idx": index,
                "prompt": prompt,
                "source": str(path),
                "output_name": f"{path.stem}_{time.strftime('%Y%m%dT%H%M%S')}.png",
            }
        )
    return entries


def generate_prompt_file_images(
    *,
    prompt_dir: Path,
    pattern: str,
    output_dir: Path,
    limit: int,
) -> dict[str, object]:
    prompt_dir = prompt_dir.expanduser()
    output_dir = output_dir.expanduser()
    if not prompt_dir.is_absolute():
        prompt_dir = (ROOT_DIR / prompt_dir).resolve()
    if not output_dir.is_absolute():
        output_dir = (ROOT_DIR / output_dir).resolve()
    entries = _prompt_file_entries(prompt_dir, pattern, limit)
    if not entries:
        return {
            "ok": False,
            "message": f"No non-empty prompt files matched {prompt_dir / pattern}.",
            "prompt_dir": str(prompt_dir),
            "pattern": pattern,
        }
    run_id = f"prompt_files_{time.strftime('%Y%m%dT%H%M%S')}"
    result = _generate_direct_records(run_id, entries, output_dir, attach_to_project=False)
    result.update(
        {
            "mode": "prompt_file_image_batch",
            "prompt_dir": str(prompt_dir),
            "pattern": pattern,
            "output_dir": str(output_dir),
            "sources": [str(entry.get("source") or "") for entry in entries],
        }
    )
    return result


def download_visible_results(project_id: str, *, expected_count: int, timeout_sec: int) -> dict[str, object]:
    playwright, browser, context = _connect_context()
    page = context.pages[0] if context.pages else context.new_page()
    started_at = time.time()
    buttons = _download_buttons(page)
    if not buttons:
        playwright.stop()
        return {
            "ok": False,
            "needs_user": True,
            "message": "No visible Flow download buttons were found.",
        }
    clicked = 0
    for button in buttons[: max(1, expected_count)]:
        try:
            with page.expect_download(timeout=10000) as download_info:
                button.click(timeout=5000)
            download = download_info.value
            target = DOWNLOADS_DIR / download.suggested_filename
            download.save_as(target)
            clicked += 1
        except Exception:
            try:
                button.click(timeout=5000)
                clicked += 1
            except Exception:
                continue
    downloads = _wait_for_new_downloads(started_at, expected=max(1, clicked), timeout_sec=timeout_sec)
    playwright.stop()
    return {
        "ok": bool(downloads),
        "clicked": clicked,
        "downloads": [str(path) for path in downloads],
        "message": "Downloaded visible Flow results." if downloads else "Clicked download buttons but no files were detected.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["open", "fill", "generate", "download", "prompt-files"])
    parser.add_argument("--project-id", default="")
    parser.add_argument("--start-sentence-number", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--prompt-dir", default="temp_prompts")
    parser.add_argument("--pattern", default="prompt_*.txt")
    parser.add_argument("--output-dir", default="storage/prompt_file_images")
    args = parser.parse_args()
    try:
        if args.command != "prompt-files" and not args.project_id:
            raise FlowAutomationError("--project-id is required for this command.")
        if args.command == "open":
            result = open_flow(args.project_id)
        elif args.command == "prompt-files":
            result = generate_prompt_file_images(
                prompt_dir=Path(str(args.prompt_dir)),
                pattern=str(args.pattern),
                output_dir=Path(str(args.output_dir)),
                limit=max(0, int(args.limit)),
            )
        elif args.command == "download":
            result = download_visible_results(
                args.project_id,
                expected_count=max(1, args.limit),
                timeout_sec=120,
            )
        else:
            result = fill_or_generate(
                args.project_id,
                start_sentence_number=args.start_sentence_number,
                limit=args.limit,
                click_generate=args.command == "generate",
            )
    except PlaywrightTimeoutError as exc:
        result = {"ok": False, "needs_user": True, "message": f"Flow browser timed out: {exc}"}
    except Exception as exc:
        result = {"ok": False, "message": str(exc)}
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
