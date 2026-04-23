import json
import traceback
from pathlib import Path
from typing import Protocol
from typing import cast

from .. import db
from ..config import SAMPLE_RATE, VOICE_PRESETS
from ..text import filter_tts_segments
from ..types import TimingEntry, TtsRuntimeInfo, VoicePresetArg, VoiceRuntimeDType
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
    if preset == "auto":
        return {}
    return dict(VOICE_PRESETS.get(preset, {}))


def _synthesize_one(model: OmniVoiceModel, text: str, preset: str) -> AudioBufferLike:
    kwargs = get_preset_kwargs(preset)
    generated = model.generate(text=text, **kwargs)
    if isinstance(generated, (list, tuple)):
        if not generated:
            raise ValueError("OmniVoice returned no audio buffers")
        return cast(AudioBufferLike, generated[0])
    return generated


def synthesize_preview(text: str, preset: str) -> AudioBufferLike:
    model = _get_model()
    return _synthesize_one(model, text, preset)


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
    preset: str = project["voice_preset"]
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
            audio = _synthesize_one(model, text, preset)
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
        db.update_project(pid, tts_state="done", tts_progress=100)
    except Exception:
        traceback.print_exc()
        _clear_tts_outputs(output_dir)
        db.update_project(pid, tts_state="error")
