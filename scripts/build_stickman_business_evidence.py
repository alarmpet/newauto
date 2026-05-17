from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import db
from app.services.stickman_evidence import build_stickman_evidence_bundle, create_stickman_business_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Stickman business LoRA on/off evidence bundle.")
    parser.add_argument("--title", default="Stickman Business Evidence")
    parser.add_argument("--sentences-file", default="")
    parser.add_argument("--count", type=int, default=0)
    args = parser.parse_args()

    db.init_db()
    sentences: list[str] | None = None
    if args.sentences_file:
        sentences = [
            line.strip()
            for line in Path(args.sentences_file).read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    project = create_stickman_business_project(title=args.title, sentences=sentences)
    paths = build_stickman_evidence_bundle(project, count=args.count or None)
    print(
        json.dumps(
            {
                "project_id": project["id"],
                "project_dir": str(db.project_dir(project["id"])),
                "evidence_dir": str(paths["evidence_dir"]),
                "prompts_lora_on": str(paths["prompts_on"]),
                "prompts_lora_off": str(paths["prompts_off"]),
                "review": str(paths["review"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
