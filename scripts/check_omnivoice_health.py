from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import VOICE_SAMPLES_DIR
from app.services import tts

HEALTHCHECK_PRESET = "male-low-30s-40s"
HEALTHCHECK_TEXT = "안녕하세요. OmniVoice 연결 상태를 확인하는 헬스체크 음성입니다."


def main() -> int:
    output_dir = VOICE_SAMPLES_DIR / "_healthcheck"
    output_dir.mkdir(parents=True, exist_ok=True)
    wav_path = output_dir / "healthcheck_male_low.wav"
    log_path = output_dir / "healthcheck_log.json"

    payload: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "preset_id": HEALTHCHECK_PRESET,
        "text": HEALTHCHECK_TEXT,
    }

    try:
        runtime = tts.get_runtime_info()
        payload["runtime"] = runtime
    except Exception as exc:
        payload["status"] = "import_failed"
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    try:
        audio = tts.synthesize_preview(HEALTHCHECK_TEXT, HEALTHCHECK_PRESET)
        payload["audio_length"] = len(audio)
    except Exception as exc:
        payload["status"] = "inference_failed"
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    try:
        tts.save_audio_file(audio, wav_path)
        payload["output_file"] = wav_path.name
    except Exception as exc:
        payload["status"] = "wav_write_failed"
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    payload["status"] = "ok"
    log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
