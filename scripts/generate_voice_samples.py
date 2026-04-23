from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import VOICE_PRESETS, VOICE_PRESET_LABELS, VOICE_SAMPLE_TEXT, VOICE_SAMPLES_DIR
from app.services import tts
from app.types import VoiceSampleEntry, VoiceSampleManifest

DEFAULT_OUTPUT_DIR = VOICE_SAMPLES_DIR / "2026-04-male-presets"
DEFAULT_PRESETS = [
    "male-deep-calm",
    "male-mid-clear",
    "female-bright-clear",
    "elder-narration",
    "whisper-story",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate OmniVoice comparison samples.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where generated sample wav files and manifest.json will be stored.",
    )
    parser.add_argument(
        "--text",
        default=VOICE_SAMPLE_TEXT,
        help="Sample text used for all generated voice samples.",
    )
    parser.add_argument(
        "--preset",
        action="append",
        dest="presets",
        help="Preset id to generate. Repeat this flag to generate multiple presets.",
    )
    return parser


def validate_presets(preset_ids: list[str]) -> list[str]:
    invalid = [preset_id for preset_id in preset_ids if preset_id not in VOICE_PRESETS]
    if invalid:
        invalid_text = ", ".join(invalid)
        raise ValueError(f"Unsupported preset id(s): {invalid_text}")
    return preset_ids


def output_filename_for_preset(preset_id: str) -> str:
    return f"{preset_id}.wav"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    preset_ids = validate_presets(args.presets or DEFAULT_PRESETS)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    samples: list[VoiceSampleEntry] = []
    for preset_id in preset_ids:
        out_name = output_filename_for_preset(preset_id)
        out_path = output_dir / out_name
        audio = tts.synthesize_preview(args.text, preset_id)
        tts.save_audio_file(audio, out_path)
        samples.append(
            {
                "preset_id": preset_id,
                "label": VOICE_PRESET_LABELS[preset_id],
                "output_file": out_name,
                "kwargs": tts.get_preset_kwargs(preset_id),
            }
        )

    manifest: VoiceSampleManifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample_text": args.text,
        "samples": samples,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
