import json
import traceback
from pathlib import Path
from typing import Protocol
from typing import cast

from .. import db
from ..config import SAMPLE_RATE
from ..text import filter_tts_segments
from ..tts_profiles import normalize_tts_profile, tts_profile_to_manifest_kwargs
from ..types import ProjectRecord, TimingEntry, TtsProfile, TtsRuntimeInfo, VoicePresetArg, VoiceRuntimeDType
from .transcribe import save_word_timings


class AudioBufferLike(Protocol):
    def __len__(self) -> int:
        ...


class OmniVoiceModel(Protocol):
    def generate(self, text: str, **kwargs: object) -> AudioBufferLike | list[AudioBufferLike] | tuple[AudioBufferLike, ...]:
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
    _model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device, dtype=dtype)
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
    return normalize_tts_profile(project["tts_profile"], project["voice_preset"], project["script"])


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


def _synthesize_one(model: OmniVoiceModel, text: str, profile: TtsProfile) -> AudioBufferLike:
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
    return _synthesize_one(model, text, profile)


def synthesize_preview_with_profile(
    text: str,
    preset: str,
    payload: object,
) -> tuple[str, TtsProfile, AudioBufferLike]:
    model = _get_model()
    normalized_preset, profile = normalize_tts_profile(payload, preset, text)
    return normalized_preset, profile, _synthesize_one(model, text, profile)


def save_audio_file(audio: AudioBufferLike, out_path: Path) -> None:
    import soundfile as sf  # noqa: WPS433

    sf.write(out_path, cast(object, audio), SAMPLE_RATE)


def _clear_tts_outputs(output_dir: Path) -> None:
    for audio_path in output_dir.glob("*.wav"):
        audio_path.unlink(missing_ok=True)
    for json_name in ("timings.json", "timings_words.json"):
        timings_path = output_dir / json_name
        if timings_path.exists():
            timings_path.unlink()


def run_tts_job(pid: str) -> None:
    project = db.get_project(pid)
    if project is None:
        return
    sentences: list[str] = filter_tts_segments(project["sentences"])
    preset, profile = _project_tts_profile(project)
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
        cursor = 0.0
        for index, text in enumerate(sentences):
            audio = _synthesize_one(model, text, profile)
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
            cursor += duration
            db.update_project(pid, tts_progress=int((index + 1) / total * 100))

        (output_dir / "timings.json").write_text(
            json.dumps(timings, ensure_ascii=False, indent=2),
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
