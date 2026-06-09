from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.services.diagnostics import collect_project_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a newautostudio project diagnostics bundle.")
    parser.add_argument("project_id", help="Project id under storage/projects")
    args = parser.parse_args()

    db.init_db()
    try:
        manifest = collect_project_diagnostics(args.project_id)
    except Exception as exc:
        print(f"diagnostics failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
