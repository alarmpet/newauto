from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import cast

import pyautogui
import pygetwindow as gw


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"
DEFAULT_API_BASE = "http://127.0.0.1:9001"
SCREENSHOT_DIR = ROOT / "storage" / "flow_desktop_screenshots"
ALLOWED_SUFFIXES = {".jpeg", ".jpg", ".png", ".webp", ".mp4", ".mov", ".webm"}


def _flow_window_title() -> str:
    for window in gw.getAllWindows():
        title = str(window.title)
        if "Flow" in title and ("Chrome" in title or "Edge" in title or "Chromium" in title):
            try:
                window.activate()
            except Exception:
                pass
            return title
    raise RuntimeError("Flow browser window was not found. Open/authenticate Flow first.")


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


def click_generate(project_id: str, sentence_number: int) -> dict[str, object]:
    prompt = _prompt_path(project_id, sentence_number).read_text(encoding="utf-8")
    previous_names = _recent_download_names()
    title = _flow_window_title()
    time.sleep(0.4)
    pyautogui.press("esc")
    time.sleep(0.2)
    before = _screenshot(project_id, sentence_number, "before_generate")
    _copy_to_clipboard(prompt)
    pyautogui.click(360, 815)
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)
    pyautogui.click(895, 854)
    time.sleep(0.8)
    after = _screenshot(project_id, sentence_number, "after_generate")
    return {
        "ok": True,
        "mode": "click-generate",
        "project_id": project_id,
        "sentence_number": sentence_number,
        "window_title": title,
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
    title = _flow_window_title()
    time.sleep(0.4)
    pyautogui.press("esc")
    time.sleep(0.3)
    before = _screenshot(project_id, sentence_number, "before_download")
    pyautogui.click(225, 420)
    time.sleep(1.5)
    pyautogui.click(987, 181)
    time.sleep(0.8)
    pyautogui.click(874, 223)
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
