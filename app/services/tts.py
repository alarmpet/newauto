import hashlib
import json
import random
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, cast

from .. import db
from ..config import SAMPLE_RATE
from ..text import filter_tts_segments
from ..tts_profiles import normalize_tts_profile, tts_profile_to_manifest_kwargs
from ..types import (
    ProjectRecord,
    TimingEntry,
    TtsPreviewLock,
    TtsProfile,
    TtsSentenceManifestEntry,
    TtsRunManifest,
    TtsRuntimeInfo,
    VoicePresetArg,
    VoiceRuntimeDType,
)
from .transcribe import save_word_timings


class AudioBufferLike(Protocol):
    def __len__(self) -> int:
        ...


class OmniVoiceModel(Protocol):
    def generate(
        self,
        text: str,
        **kwargs: object,
    ) -> AudioBufferLike | list[AudioBufferLike] | tuple[AudioBufferLike, ...]:
        ...


_model: OmniVoiceModel | None = None
_runtime_info: TtsRuntimeInfo | None = None


def _get_model() -> OmniVoiceModel:
    """Lazy-load OmniVoice so UI development works without ML dependencies."""
    global _model
    if _model is not None:
        return _model
    import torch  # noqa: WPS433
    from omnivoice import OmniVoice  # noqa: WPS433

    runtime = get_runtime_info()
    device = runtime["device"]
    dtype = torch.float16 if runtime["dtype"] == "float16" else torch.float32
    _model = OmniVoice.from_pretrained(
        "k2-fsa/OmniVoice",
        device_map=device,
        dtype=dtype,
    )
    return _model


def get_runtime_info() -> TtsRuntimeInfo:
    global _runtime_info
    if _runtime_info is not None:
        return _runtime_info
    import torch  # noqa: WPS433

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype: VoiceRuntimeDType = "float16" if device.startswith("cuda") else "float32"
    _runtime_info = {
        "device": device,
        "dtype": dtype,
    }
    return _runtime_info


def get_preset_kwargs(preset: str) -> dict[str, VoicePresetArg]:
    _, profile = normalize_tts_profile({}, preset)
    return tts_profile_to_manifest_kwargs(profile)


def _project_tts_profile(project: ProjectRecord) -> tuple[str, TtsProfile]:
    return normalize_tts_profile(
        project["tts_profile"],
        project["voice_preset"],
        project["script"],
    )


def _build_generation_config(profile: TtsProfile) -> object:
    from omnivoice import OmniVoiceGenerationConfig  # noqa: WPS433

    return OmniVoiceGenerationConfig(
        num_step=profile["num_step"],
        guidance_scale=profile["guidance_scale"],
        denoise=profile["denoise"],
        postprocess_output=profile["postprocess_output"],
    )


def _build_generate_kwargs(profile: TtsProfile) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "generation_config": _build_generation_config(profile),
    }
    if profile["language"]:
        kwargs["language"] = profile["language"]
    if profile["mode"] == "design" and profile["instruct"]:
        kwargs["instruct"] = profile["instruct"]
    if profile["speed"] != 1.0:
        kwargs["speed"] = profile["speed"]
    if profile["duration"] is not None:
        kwargs["duration"] = profile["duration"]
    return kwargs


def _new_seed() -> int:
    return random.SystemRandom().randint(1, 2_147_483_647)


def ensure_seed(profile: TtsProfile, forced_seed: int | None = None) -> TtsProfile:
    updated = cast(TtsProfile, dict(profile))
    if forced_seed is not None:
        updated["seed"] = forced_seed
    elif updated["seed"] is None:
        updated["seed"] = _new_seed()
    return updated


def _apply_seed(seed: int) -> None:
    from omnivoice.utils.common import fix_random_seed  # noqa: WPS433

    fix_random_seed(seed)


def preview_lock_signature(voice_preset: str, profile: TtsProfile) -> str:
    payload = {
        "voice_preset": voice_preset,
        "tts_profile": tts_profile_to_manifest_kwargs(profile),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_preview_lock(voice_preset: str, profile: TtsProfile) -> TtsPreviewLock:
    return {
        "voice_preset": voice_preset,
        "tts_profile": cast(TtsProfile, dict(profile)),
        "signature": preview_lock_signature(voice_preset, profile),
    }


def validate_preview_lock(
    preview_lock: object,
    voice_preset: str,
    profile: TtsProfile,
) -> TtsPreviewLock:
    if not isinstance(preview_lock, dict):
        raise ValueError("preview lock payload is invalid")
    signature = preview_lock.get("signature")
    locked_preset = preview_lock.get("voice_preset")
    locked_profile = preview_lock.get("tts_profile")
    if not isinstance(signature, str) or not isinstance(locked_preset, str):
        raise ValueError("preview lock payload is invalid")
    if not isinstance(locked_profile, dict):
        raise ValueError("preview lock payload is invalid")
    normalized_preset, normalized_profile = normalize_tts_profile(
        locked_profile,
        locked_preset,
    )
    normalized_profile = ensure_seed(normalized_profile)
    expected_signature = preview_lock_signature(normalized_preset, normalized_profile)
    if signature != expected_signature:
        raise ValueError("preview lock signature is invalid")
    if normalized_preset != voice_preset:
        raise ValueError("voice preset changed after preview; generate a new sample first")
    if normalized_profile != profile:
        raise ValueError("TTS tuning changed after preview; generate a new sample first")
    return {
        "voice_preset": normalized_preset,
        "tts_profile": normalized_profile,
        "signature": signature,
    }


def _synthesize_one(model: OmniVoiceModel, text: str, profile: TtsProfile) -> AudioBufferLike:
    if profile["seed"] is None:
        raise ValueError("TTS seed must be resolved before synthesis")
    _apply_seed(profile["seed"])
    kwargs = _build_generate_kwargs(profile)
    generated = model.generate(text=text, **kwargs)
    if isinstance(generated, (list, tuple)):
        if not generated:
            raise ValueError("OmniVoice returned no audio buffers")
        return cast(AudioBufferLike, generated[0])
    return generated


def synthesize_preview(text: str, preset: str) -> AudioBufferLike:
    model = _get_model()
    _, profile = normalize_tts_profile({}, preset, text)
    profile = ensure_seed(profile)
    return _synthesize_one(model, text, profile)


def synthesize_preview_with_profile(
    text: str,
    preset: str,
    payload: object,
) -> tuple[str, TtsProfile, TtsPreviewLock, AudioBufferLike]:
    model = _get_model()
    normalized_preset, profile = normalize_tts_profile(payload, preset, text)
    profile = ensure_seed(profile)
    preview_lock = build_preview_lock(normalized_preset, profile)
    return normalized_preset, profile, preview_lock, _synthesize_one(model, text, profile)


def save_audio_file(audio: AudioBufferLike, out_path: Path) -> None:
    import soundfile as sf  # noqa: WPS433

    sf.write(out_path, cast(object, audio), SAMPLE_RATE)


def _clear_tts_outputs(output_dir: Path) -> None:
    for audio_path in output_dir.glob("*.wav"):
        audio_path.unlink(missing_ok=True)
    for json_name in ("timings.json", "timings_words.json", "tts_run_manifest.json"):
        timings_path = output_dir / json_name
        if timings_path.exists():
            timings_path.unlink()


def _effective_sentence_profile(profile: TtsProfile, index: int, _text: str) -> TtsProfile:
    sentence_profile = cast(TtsProfile, dict(profile))
    seed = sentence_profile["seed"]
    if seed is None:
        raise ValueError("TTS seed must be resolved before sentence profile creation")
    sentence_profile["seed"] = seed + index
    return sentence_profile


def run_tts_job(pid: str) -> None:
    project = db.get_project(pid)
    if project is None:
        return
    sentences: list[str] = filter_tts_segments(project["sentences"])
    preset, profile = _project_tts_profile(project)
    profile = ensure_seed(profile)
    output_dir: Path = db.project_dir(pid) / "tts"
    output_dir.mkdir(parents=True, exist_ok=True)
    _clear_tts_outputs(output_dir)

    try:
        import soundfile as sf  # noqa: WPS433

        if sentences != project["sentences"]:
            db.update_project(pid, sentences=sentences)
        if not sentences:
            raise ValueError("script has no TTS-readable sentences")

        model = _get_model()
        total = max(len(sentences), 1)
        timings: list[TimingEntry] = []
        manifest_sentences: list[TtsSentenceManifestEntry] = []
        cursor = 0.0
        for index, text in enumerate(sentences):
            sentence_profile = _effective_sentence_profile(profile, index, text)
            sentence_seed = sentence_profile["seed"]
            if sentence_seed is None:
                raise ValueError("TTS sentence seed must be resolved before synthesis")
            audio = _synthesize_one(model, text, sentence_profile)
            if len(audio) == 0:
                raise ValueError(
                    f"OmniVoice returned empty audio for sentence {index}: {text[:80]}"
                )
            duration = float(len(audio)) / SAMPLE_RATE
            sf.write(output_dir / f"{index:04d}.wav", audio, SAMPLE_RATE)
            timings.append(
                {
                    "idx": index,
                    "text": text,
                    "start": round(cursor, 3),
                    "end": round(cursor + duration, 3),
                    "dur": round(duration, 3),
                }
            )
            manifest_sentences.append(
                {
                    "idx": index,
                    "text": text,
                    "voice_preset": preset,
                    "effective_profile": sentence_profile,
                    "kwargs": tts_profile_to_manifest_kwargs(sentence_profile),
                    "seed": sentence_seed,
                }
            )
            cursor += duration
            db.update_project(pid, tts_progress=int((index + 1) / total * 100))

        (output_dir / "timings.json").write_text(
            json.dumps(timings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest: TtsRunManifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "voice_preset": preset,
            "tts_profile": profile,
            "sentences": manifest_sentences,
        }
        (output_dir / "tts_run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        save_word_timings(output_dir / "timings_words.json", timings)
        db.update_project(
            pid,
            voice_preset=preset,
            tts_profile=profile,
            tts_state="done",
            tts_progress=100,
        )
    except Exception:
        traceback.print_exc()
        _clear_tts_outputs(output_dir)
        db.update_project(pid, tts_state="error")
