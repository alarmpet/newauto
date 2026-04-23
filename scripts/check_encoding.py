from __future__ import annotations

import sys
from pathlib import Path

SUSPECT_SNIPPETS = (
    "\ufffd",
    "?낅",
    "?뚯",
    "釉뚮",
    "媛",
    "몃꽕",
)
TARGET_SUFFIXES = {".py", ".js", ".html", ".css", ".md"}
TARGET_DIRS = ("app", "scripts", "tests")


def _safe_output(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")


def _contains_suspect(line: str) -> bool:
    for snippet in SUSPECT_SNIPPETS:
        if snippet in line:
            return True
    return False


def main() -> int:
    bad_lines: list[tuple[Path, int, str]] = []
    for root_name in TARGET_DIRS:
        root = Path(root_name)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TARGET_SUFFIXES:
                continue
            if path.name == "check_encoding.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if _contains_suspect(line):
                    bad_lines.append((path, line_no, line.strip()))

    for path, line_no, line in bad_lines:
        print(_safe_output(f"{path}:{line_no}: {line[:120]}"))
    return 1 if bad_lines else 0


if __name__ == "__main__":
    sys.exit(main())
