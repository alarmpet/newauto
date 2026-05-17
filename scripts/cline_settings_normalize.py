from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "read_file": ("read_file", "read_text_file"),
    "read_text_file": ("read_text_file", "read_file"),
    "read_multiple_files": ("read_multiple_files", "read_text_file"),
    "write_file": ("write_file", "write_text_file"),
    "write_text_file": ("write_text_file", "write_file"),
}

DEFAULT_SETTINGS = (
    Path.home()
    / "AppData"
    / "Roaming"
    / "Code"
    / "User"
    / "globalStorage"
    / "saoudrizwan.claude-dev"
    / "settings"
    / "cline_mcp_settings.json"
)


def _load(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("settings root must be a JSON object")
    return payload


def normalize(payload: dict[str, object], *, dual_key: bool = False) -> dict[str, object]:
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict):
        raise ValueError("mcpServers must be a JSON object")
    for config in servers.values():
        if not isinstance(config, dict):
            continue
        auto = config.get("autoApprove")
        always = config.get("alwaysAllow")
        selected = auto if isinstance(auto, list) else always if isinstance(always, list) else None
        if selected is None:
            continue
        expanded: list[object] = []
        seen: set[str] = set()
        for item in selected:
            if not isinstance(item, str):
                expanded.append(item)
                continue
            for candidate in TOOL_ALIASES.get(item, (item,)):
                if candidate in seen:
                    continue
                seen.add(candidate)
                expanded.append(candidate)
        config["autoApprove"] = expanded
        if dual_key:
            config["alwaysAllow"] = expanded
        elif "alwaysAllow" in config:
            del config["alwaysAllow"]
        config.setdefault("disabled", False)
        config.setdefault("transportType", "stdio")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Cline MCP settings format.")
    parser.add_argument("--path", default=str(DEFAULT_SETTINGS))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dual-key", action="store_true", help="Write both autoApprove and alwaysAllow.")
    args = parser.parse_args()

    path = Path(args.path)
    payload = _load(path)
    normalized = normalize(payload, dual_key=args.dual_key)
    text = json.dumps(normalized, ensure_ascii=False, indent=2)
    if args.apply:
        backup = path.with_name(f"{path.stem}.backup-{time.strftime('%Y%m%d-%H%M%S')}{path.suffix}")
        shutil.copy2(path, backup)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"updated: {path}")
        print(f"backup: {backup}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
