from pathlib import Path

from app.services.text_health import looks_mojibake


PRODUCT_TEXT_FILES = [
    "app/static/app.js",
    "app/static/index.html",
    "app/tts_profiles.py",
    "app/presets/voice_catalog.json",
]


def test_product_text_files_do_not_contain_mojibake():
    suspicious: list[str] = []
    for relative_path in PRODUCT_TEXT_FILES:
        path = Path(relative_path)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if looks_mojibake(text):
            suspicious.append(relative_path)

    assert suspicious == []
