from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app.services.stickman_layout_sketch import build_stickman_layout_sketches  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic stickman business layout sketches.")
    parser.add_argument("project_id", help="Project id to write sketches into.")
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=432)
    parser.add_argument("--templates", nargs="*", default=None)
    args = parser.parse_args()

    db.init_db()
    project = db.get_project(args.project_id)
    if project is None:
        print(json.dumps({"error": "project_not_found", "project_id": args.project_id}, indent=2))
        return 2

    sketches = build_stickman_layout_sketches(
        project,
        template_keys=args.templates,
        width=args.width,
        height=args.height,
    )
    print(
        json.dumps(
            {
                "project_id": args.project_id,
                "generated_count": len(sketches),
                "paths": [item["path"] for item in sketches],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
