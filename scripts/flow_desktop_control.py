from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import pyautogui
import pygetwindow as gw


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"
DEFAULT_API_BASE = "http://127.0.0.1:9001"


def _flow_window_title() -> str:
    for window in gw.getAllWindows():
        title = str(window.title)
        if "Flow" in title and "Chrome" in title:
            try:
                window.activate()
            except Exception:
                pass
            return title
    raise RuntimeError("Flow Chrome window was not found. Open/authenticate Flow first.")


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


def _newest_generated_download(previous_names: set[str]) -> Path:
    allowed_suffixes = {".jpeg", ".jpg", ".png", ".webp", ".mp4"}
    recent = sorted(DOWNLOADS.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in recent:
        if path.name not in previous_names and path.is_file() and path.suffix.lower() in allowed_suffixes:
            return path
    for path in recent:
        if path.is_file() and path.suffix.lower() in allowed_suffixes:
            return path
    raise RuntimeError("No generated Flow download was found.")


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


def generate_one(project_id: str, sentence_number: int, wait_seconds: int, api_base: str) -> Path:
    prompt = _prompt_path(project_id, sentence_number).read_text(encoding="utf-8")
    previous_names = _recent_download_names()
    _flow_window_title()
    time.sleep(0.4)
    _copy_to_clipboard(prompt)
    pyautogui.click(360, 815)
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)
    pyautogui.click(790, 850)
    time.sleep(wait_seconds)
    pyautogui.click(987, 181)
    time.sleep(0.8)
    pyautogui.click(874, 223)
    time.sleep(8)
    asset_path = _newest_generated_download(previous_names)
    attached = _attach_asset(api_base, project_id, sentence_number, asset_path)
    print(f"sentence={sentence_number} downloaded={asset_path} attached={attached}")
    return asset_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Control authenticated Google Flow via desktop coordinates.")
    parser.add_argument("project_id")
    parser.add_argument("--sentence", type=int, required=True)
    parser.add_argument("--wait-seconds", type=int, default=60)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    args = parser.parse_args()
    generate_one(
        project_id=str(args.project_id),
        sentence_number=int(args.sentence),
        wait_seconds=int(args.wait_seconds),
        api_base=str(args.api_base),
    )


if __name__ == "__main__":
    main()
