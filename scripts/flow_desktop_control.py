from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Protocol, cast

import pyautogui
import pygetwindow as gw


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"
DEFAULT_API_BASE = "http://127.0.0.1:9001"
SCREENSHOT_DIR = ROOT / "storage" / "flow_desktop_screenshots"
ALLOWED_SUFFIXES = {".jpeg", ".jpg", ".png", ".webp", ".mp4", ".mov", ".webm"}


class WindowLike(Protocol):
    title: str
    width: int
    height: int
    left: int
    top: int

    def activate(self) -> None:
        ...

    def restore(self) -> None:
        ...

    def maximize(self) -> None:
        ...


def _desktop_state_payload() -> dict[str, object]:
    try:
        user32 = ctypes.windll.user32
        hwnd = int(user32.GetForegroundWindow())
    except (AttributeError, OSError, ValueError) as exc:
        return {
            "desktop_locked": "undetermined",
            "foreground_hwnd": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "desktop_locked": hwnd == 0,
        "foreground_hwnd": hwnd,
    }


def _ensure_desktop_unlocked() -> None:
    state = _desktop_state_payload()
    if state.get("desktop_locked") is True:
        raise RuntimeError(
            "desktop_locked=true. 화면 잠금이 감지되어 GUI 클릭이 불가능합니다. "
            "화면 잠금을 해제하고 Flow 창을 전면에 둔 뒤 진행이라고 말해주세요."
        )


def _activate_flow_window() -> WindowLike:
    _ensure_desktop_unlocked()
    candidates: list[WindowLike] = []
    for window in gw.getAllWindows():
        candidate = cast(WindowLike, window)
        title = str(candidate.title)
        if "Flow" in title and ("Chrome" in title or "Edge" in title or "Chromium" in title):
            if candidate.width <= 0 or candidate.height <= 0:
                continue
            candidates.append(candidate)
    if not candidates:
        raise RuntimeError("Flow browser window was not found. Open/authenticate Flow first.")
    candidates.sort(
        key=lambda item: (
            item.width * item.height,
            -abs(item.left),
            -abs(item.top),
        ),
        reverse=True,
    )
    selected = candidates[0]
    try:
        selected.restore()
    except Exception:
        pass
    try:
        selected.maximize()
    except Exception:
        pass
    try:
        selected.activate()
    except Exception:
        pass
    time.sleep(0.3)
    _dismiss_browser_overlays(selected)
    return selected


def _flow_window_title() -> str:
    return str(_activate_flow_window().title)


def _dismiss_browser_overlays(window: WindowLike) -> None:
    pyautogui.press("esc")
    time.sleep(0.15)
    # Chrome's "restore pages" bubble can sit over Flow controls after a
    # browser crash/restart. This click lands on its close button when present,
    # and on empty page chrome when absent.
    pyautogui.click(window.left + window.width - 40, window.top + 112)
    time.sleep(0.15)
    pyautogui.press("esc")
    time.sleep(0.15)


def _screenshot(project_id: str, sentence_number: int, label: str) -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    path = SCREENSHOT_DIR / f"{project_id}_s{sentence_number:03d}_{label}_{stamp}.png"
    image = pyautogui.screenshot()
    image.save(path)
    return path


def _copy_to_clipboard(text: str) -> None:
    try:
        import pyperclip

        pyperclip.copy(text)
    except Exception:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            input=text,
            text=True,
            check=True,
        )


def _read_clipboard() -> str:
    try:
        import pyperclip

        return str(pyperclip.paste())
    except Exception:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip()


def _current_browser_url() -> str:
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.1)
    url = _read_clipboard()
    pyautogui.press("esc")
    time.sleep(0.1)
    return url


def _ensure_project_prompt_view() -> None:
    url = _current_browser_url()
    if "/edit/" in url or "/scene/" in url:
        pyautogui.hotkey("alt", "left")
        time.sleep(1.8)


def _ensure_flow_url() -> str:
    url = _current_browser_url()
    lower_url = url.lower()
    if "labs.google" not in lower_url and "flow" not in lower_url:
        raise RuntimeError(
            "Flow browser window is active, but the current URL does not look like Google Flow. "
            f"current_url={url}"
        )
    return url


def _enter_prompt_text(text: str) -> None:
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")
    time.sleep(0.1)
    if text.isascii():
        pyautogui.write(text, interval=0.001)
        return
    _copy_to_clipboard(text)
    pyautogui.hotkey("ctrl", "v")


def _prompt_path(project_id: str, sentence_number: int) -> Path:
    return ROOT / "storage" / "projects" / project_id / "uivision" / f"prompt_{sentence_number:03d}.txt"


def _recent_download_names() -> set[str]:
    return {path.name for path in DOWNLOADS.glob("*") if path.is_file()}


def _is_complete_new_asset(path: Path, previous_names: set[str]) -> bool:
    return (
        path.name not in previous_names
        and path.is_file()
        and path.suffix.lower() in ALLOWED_SUFFIXES
        and not path.name.endswith(".crdownload")
        and not (path.parent / f"{path.name}.crdownload").exists()
    )


def _newest_generated_download(previous_names: set[str], timeout_seconds: int = 45) -> Path:
    deadline = time.time() + max(5, timeout_seconds)
    stable_sizes: dict[str, int] = {}
    while time.time() < deadline:
        recent = sorted(DOWNLOADS.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in recent:
            if not _is_complete_new_asset(path, previous_names):
                continue
            size = path.stat().st_size
            previous_size = stable_sizes.get(path.name)
            if previous_size == size and size > 0:
                return path
            stable_sizes[path.name] = size
        time.sleep(1.0)
    raise RuntimeError("No completed new Flow download was found before timeout.")


def _attach_asset(api_base: str, project_id: str, sentence_number: int, asset_path: Path) -> list[str]:
    payload = json.dumps({"paths": [str(asset_path)], "start_sentence_number": sentence_number}).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base}/api/flow/assets/{project_id}/attach-local",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    attached = body.get("attached", [])
    if not isinstance(attached, list):
        return []
    return [str(item) for item in attached]


def _pending_attach_path(project_id: str, sentence_number: int) -> Path:
    directory = ROOT / "storage" / "projects" / project_id / "uivision"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"pending_attach_{sentence_number:03d}.json"


def _save_pending_attach(project_id: str, sentence_number: int, asset_path: Path, error: str) -> Path:
    path = _pending_attach_path(project_id, sentence_number)
    payload: dict[str, object] = {
        "sentence_number": sentence_number,
        "asset_path": str(asset_path),
        "error": error,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _click_flow_download_1k(window: WindowLike) -> None:
    download_x = window.left + int(window.width * 0.84)
    download_y = window.top + int(window.height * 0.24)
    pyautogui.click(download_x, download_y)
    time.sleep(0.5)
    pyautogui.click(download_x - 116, download_y + 43)
    time.sleep(0.5)


def _open_first_flow_card(window: WindowLike) -> None:
    pyautogui.click(window.left + int(window.width * 0.12), window.top + int(window.height * 0.43))
    time.sleep(1.5)


def _download_from_current_flow_view(window: WindowLike, previous_names: set[str]) -> Path:
    _click_flow_download_1k(window)
    try:
        return _newest_generated_download(previous_names, timeout_seconds=6)
    except RuntimeError:
        _open_first_flow_card(window)
        _click_flow_download_1k(window)
        return _newest_generated_download(previous_names, timeout_seconds=45)


def click_generate(project_id: str, sentence_number: int) -> dict[str, object]:
    prompt = _prompt_path(project_id, sentence_number).read_text(encoding="utf-8")
    previous_names = _recent_download_names()
    window = _activate_flow_window()
    title = str(window.title)
    time.sleep(0.4)
    pyautogui.press("esc")
    time.sleep(0.2)
    _ensure_project_prompt_view()
    url = _ensure_flow_url()
    before = _screenshot(project_id, sentence_number, "before_generate")
    pyautogui.click(window.left + int(window.width * 0.44), window.top + window.height - 90)
    time.sleep(0.2)
    _enter_prompt_text(prompt)
    time.sleep(0.5)
    pyautogui.click(window.left + int(window.width * 0.69), window.top + window.height - 66)
    time.sleep(0.8)
    after = _screenshot(project_id, sentence_number, "after_generate")
    return {
        "ok": True,
        "mode": "click-generate",
        "project_id": project_id,
        "sentence_number": sentence_number,
        "window_title": title,
        "current_url": url,
        "downloads_before": sorted(previous_names),
        "screenshots": [str(before), str(after)],
    }


def download_and_attach(
    project_id: str,
    sentence_number: int,
    api_base: str,
    previous_names: set[str],
    download_timeout_seconds: int,
) -> dict[str, object]:
    window = _activate_flow_window()
    title = str(window.title)
    time.sleep(0.4)
    previous_names = set(previous_names)
    previous_names.update(_recent_download_names())
    pyautogui.press("esc")
    time.sleep(0.3)
    url = _ensure_flow_url()
    before = _screenshot(project_id, sentence_number, "before_download")
    try:
        asset_path = _download_from_current_flow_view(window, previous_names)
    except RuntimeError:
        _open_first_flow_card(window)
        _click_flow_download_1k(window)
        asset_path = _newest_generated_download(previous_names, timeout_seconds=download_timeout_seconds)
    after = _screenshot(project_id, sentence_number, "after_download")
    try:
        attached = _attach_asset(api_base, project_id, sentence_number, asset_path)
    except Exception as exc:
        pending_path = _save_pending_attach(project_id, sentence_number, asset_path, str(exc))
        return {
            "ok": False,
            "mode": "download-attach",
            "project_id": project_id,
            "sentence_number": sentence_number,
            "window_title": title,
            "current_url": url,
            "downloaded": str(asset_path),
            "pending_attach": str(pending_path),
            "error": f"attach failed: {exc}",
            "screenshots": [str(before), str(after)],
        }
    return {
        "ok": True,
        "mode": "download-attach",
        "project_id": project_id,
        "sentence_number": sentence_number,
        "window_title": title,
        "current_url": url,
        "downloaded": str(asset_path),
        "attached": attached,
        "screenshots": [str(before), str(after)],
    }


def _json_list_arg(raw_value: str) -> set[str]:
    if not raw_value.strip():
        return set()
    payload = json.loads(raw_value)
    if not isinstance(payload, list):
        raise RuntimeError("--downloads-before-json must be a JSON list.")
    return {str(item) for item in payload}


def main() -> None:
    parser = argparse.ArgumentParser(description="Control authenticated Google Flow via desktop coordinates.")
    parser.add_argument("project_id")
    parser.add_argument("--sentence", type=int, required=True)
    parser.add_argument("--mode", choices=["generate-one", "click-generate", "download-attach"], default="generate-one")
    parser.add_argument("--downloads-before-json", default="")
    parser.add_argument("--download-timeout-seconds", type=int, default=45)
    parser.add_argument("--wait-seconds", type=int, default=60)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    args = parser.parse_args()
    project_id = str(args.project_id)
    sentence_number = int(args.sentence)
    mode = cast(str, args.mode)
    if mode == "click-generate":
        result = click_generate(project_id, sentence_number)
    elif mode == "download-attach":
        result = download_and_attach(
            project_id,
            sentence_number,
            str(args.api_base),
            _json_list_arg(str(args.downloads_before_json)),
            int(args.download_timeout_seconds),
        )
    else:
        click_result = click_generate(project_id, sentence_number)
        time.sleep(int(args.wait_seconds))
        result = download_and_attach(
            project_id,
            sentence_number,
            str(args.api_base),
            {str(item) for item in cast(list[object], click_result.get("downloads_before", []))},
            int(args.download_timeout_seconds),
        )
    print(json.dumps(result, ensure_ascii=False))
    if result.get("ok") is not True:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
