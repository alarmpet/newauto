import re
from typing import cast

from .types import TtsMode, TtsPresetCatalogResponse, TtsProfile, VoicePresetArg

VOICE_SAMPLE_TEXT = (
    "안녕하세요. 지금 들으시는 음성은 OmniVoice 보이스 비교 샘플입니다. "
    "목소리 톤과 속도, 전달감의 차이를 확인해 주세요."
)

DEFAULT_TTS_PROFILE: TtsProfile = {
    "mode": "auto",
    "language": "ko",
    "instruct": "",
    "speed": 1.0,
    "duration": None,
    "num_step": 32,
    "guidance_scale": 2.6,
    "denoise": True,
    "postprocess_output": True,
}

_PRESET_DEFINITIONS: dict[str, TtsProfile] = {
    "auto": cast(TtsProfile, dict(DEFAULT_TTS_PROFILE)),
    "male-deep-calm": {
        "mode": "design",
        "language": "ko",
        "instruct": "male, low pitch",
        "speed": 0.96,
        "duration": None,
        "num_step": 36,
        "guidance_scale": 2.9,
        "denoise": True,
        "postprocess_output": True,
    },
    "male-mid-clear": {
        "mode": "design",
        "language": "ko",
        "instruct": "male, moderate pitch",
        "speed": 1.0,
        "duration": None,
        "num_step": 34,
        "guidance_scale": 2.7,
        "denoise": True,
        "postprocess_output": True,
    },
    "male-40s-50s-lowmid": {
        "mode": "design",
        "language": "ko",
        "instruct": "male, middle-aged, low pitch",
        "speed": 0.94,
        "duration": None,
        "num_step": 38,
        "guidance_scale": 3.0,
        "denoise": True,
        "postprocess_output": True,
    },
    "male-announcer-40s-50s": {
        "mode": "design",
        "language": "ko",
        "instruct": "male, middle-aged, moderate pitch",
        "speed": 1.0,
        "duration": None,
        "num_step": 36,
        "guidance_scale": 2.9,
        "denoise": True,
        "postprocess_output": True,
    },
    "male-pastor-40s-50s": {
        "mode": "design",
        "language": "ko",
        "instruct": "male, middle-aged, low pitch",
        "speed": 0.9,
        "duration": None,
        "num_step": 40,
        "guidance_scale": 3.1,
        "denoise": True,
        "postprocess_output": True,
    },
    "female-bright-clear": {
        "mode": "design",
        "language": "ko",
        "instruct": "female, high pitch",
        "speed": 1.03,
        "duration": None,
        "num_step": 35,
        "guidance_scale": 3.0,
        "denoise": True,
        "postprocess_output": True,
    },
    "female-low-calm": {
        "mode": "design",
        "language": "ko",
        "instruct": "female, low pitch",
        "speed": 0.97,
        "duration": None,
        "num_step": 36,
        "guidance_scale": 2.8,
        "denoise": True,
        "postprocess_output": True,
    },
    "elder-narration": {
        "mode": "design",
        "language": "ko",
        "instruct": "elderly, moderate pitch",
        "speed": 0.94,
        "duration": None,
        "num_step": 38,
        "guidance_scale": 3.1,
        "denoise": True,
        "postprocess_output": True,
    },
    "whisper-story": {
        "mode": "design",
        "language": "ko",
        "instruct": "whisper, young adult",
        "speed": 0.92,
        "duration": None,
        "num_step": 40,
        "guidance_scale": 3.2,
        "denoise": True,
        "postprocess_output": True,
    },
    "english-bright": {
        "mode": "design",
        "language": "en",
        "instruct": "female, high pitch",
        "speed": 1.0,
        "duration": None,
        "num_step": 34,
        "guidance_scale": 2.8,
        "denoise": True,
        "postprocess_output": True,
    },
}

LEGACY_VOICE_PRESET_ALIASES: dict[str, str] = {
    "male-calm": "male-deep-calm",
    "female-bright": "female-bright-clear",
    "narrator": "male-mid-clear",
    "male-30s-40s-lowmid": "male-deep-calm",
    "male-40s-50s-lowmid": "male-40s-50s-lowmid",
    "male-announcer-30s-40s": "male-mid-clear",
    "male-low-30s-40s": "male-deep-calm",
    "male-pastor-30s-40s": "male-pastor-40s-50s",
}

VOICE_PRESET_ORDER = [
    "auto",
    "male-deep-calm",
    "male-mid-clear",
    "male-40s-50s-lowmid",
    "male-announcer-40s-50s",
    "male-pastor-40s-50s",
    "female-bright-clear",
    "female-low-calm",
    "elder-narration",
    "whisper-story",
    "english-bright",
]

VOICE_PRESET_LABELS: dict[str, str] = {
    "auto": "Auto Detect",
    "male-deep-calm": "Male Deep Calm",
    "male-mid-clear": "Male Mid Clear",
    "male-40s-50s-lowmid": "40~50대 남성 중저음",
    "male-announcer-40s-50s": "40~50대 남성 아나운서",
    "male-pastor-40s-50s": "40~50대 남성 목사",
    "female-bright-clear": "Female Bright Clear",
    "female-low-calm": "Female Low Calm",
    "elder-narration": "Elder Narration",
    "whisper-story": "Whisper Story",
    "english-bright": "English Bright",
    "male-calm": "Male Deep Calm",
    "female-bright": "Female Bright Clear",
    "narrator": "Male Mid Clear",
    "male-30s-40s-lowmid": "Male Deep Calm",
    "male-40s-50s-lowmid": "40~50대 남성 중저음",
    "male-announcer-30s-40s": "Male Mid Clear",
    "male-low-30s-40s": "Male Deep Calm",
    "male-pastor-30s-40s": "40~50대 남성 목사",
}

VOICE_PRESETS: dict[str, TtsProfile] = {
    preset_id: cast(TtsProfile, dict(profile))
    for preset_id, profile in _PRESET_DEFINITIONS.items()
}
for legacy_id, canonical_id in LEGACY_VOICE_PRESET_ALIASES.items():
    VOICE_PRESETS[legacy_id] = cast(TtsProfile, dict(_PRESET_DEFINITIONS[canonical_id]))


def canonical_voice_preset(preset: str) -> str:
    if preset in _PRESET_DEFINITIONS:
        return preset
    return LEGACY_VOICE_PRESET_ALIASES.get(preset, "auto")


def detect_tts_language(text: str) -> str:
    if re.search(r"[가-힣]", text):
        return "ko"
    if re.search(r"[A-Za-z]", text):
        return "en"
    return "ko"


def _clamp_float(value: object, fallback: float, minimum: float, maximum: float) -> float:
    if isinstance(value, (int, float)):
        return max(minimum, min(float(value), maximum))
    return fallback


def _clamp_int(value: object, fallback: int, minimum: int, maximum: int) -> int:
    if isinstance(value, int):
        return max(minimum, min(value, maximum))
    return fallback


def _coerce_bool(value: object, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def normalize_tts_profile(
    payload: object,
    voice_preset: str,
    script: str = "",
) -> tuple[str, TtsProfile]:
    canonical_preset = canonical_voice_preset(voice_preset)
    base_profile = cast(TtsProfile, dict(_PRESET_DEFINITIONS[canonical_preset]))
    overrides = payload if isinstance(payload, dict) else {}

    mode_value = overrides.get("mode")
    if mode_value in {"auto", "design", "clone"}:
        base_profile["mode"] = cast(TtsMode, mode_value)

    language_value = overrides.get("language")
    if isinstance(language_value, str) and language_value in {"auto", "ko", "en"}:
        base_profile["language"] = language_value

    if base_profile["language"] == "auto":
        base_profile["language"] = detect_tts_language(script)

    instruct_value = overrides.get("instruct")
    if isinstance(instruct_value, str):
        base_profile["instruct"] = instruct_value.strip()[:200]

    duration_value = overrides.get("duration")
    if duration_value is None or duration_value == "":
        base_profile["duration"] = None
    else:
        base_profile["duration"] = _clamp_float(duration_value, 0.0, 0.0, 30.0) or None

    base_profile["speed"] = _clamp_float(overrides.get("speed"), float(base_profile["speed"]), 0.75, 1.25)
    base_profile["num_step"] = _clamp_int(overrides.get("num_step"), int(base_profile["num_step"]), 16, 64)
    base_profile["guidance_scale"] = _clamp_float(
        overrides.get("guidance_scale"),
        float(base_profile["guidance_scale"]),
        1.0,
        5.0,
    )
    base_profile["denoise"] = _coerce_bool(overrides.get("denoise"), bool(base_profile["denoise"]))
    base_profile["postprocess_output"] = _coerce_bool(
        overrides.get("postprocess_output"),
        bool(base_profile["postprocess_output"]),
    )

    if base_profile["mode"] == "auto":
        base_profile["instruct"] = ""

    return canonical_preset, cast(TtsProfile, base_profile)


def tts_profile_to_manifest_kwargs(profile: TtsProfile) -> dict[str, VoicePresetArg]:
    payload: dict[str, VoicePresetArg] = {
        "mode": profile["mode"],
        "language": profile["language"],
        "speed": profile["speed"],
        "num_step": profile["num_step"],
        "guidance_scale": profile["guidance_scale"],
        "denoise": profile["denoise"],
        "postprocess_output": profile["postprocess_output"],
    }
    if profile["instruct"]:
        payload["instruct"] = profile["instruct"]
    if profile["duration"] is not None:
        payload["duration"] = profile["duration"]
    return payload


def build_tts_preset_catalog() -> TtsPresetCatalogResponse:
    presets: dict[str, TtsProfile] = {}
    for preset_id in VOICE_PRESET_ORDER:
        presets[preset_id] = cast(TtsProfile, dict(_PRESET_DEFINITIONS[preset_id]))
    return {
        "order": list(VOICE_PRESET_ORDER),
        "labels": dict(VOICE_PRESET_LABELS),
        "aliases": dict(LEGACY_VOICE_PRESET_ALIASES),
        "presets": presets,
        "sample_text": VOICE_SAMPLE_TEXT,
    }
