import hashlib
import gc
import json
import random
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, cast

from .. import db
from ..config import SAMPLE_RATE, SCRIPT_LLM_MODEL
from ..text import filter_tts_segments
from ..text import is_tts_readable_text
from ..text import normalize_tts_reading_text
from ..tts_profiles import normalize_tts_profile, tts_profile_to_manifest_kwargs
from ..types import (
    ProjectRecord,
    Region,
    RegionalSentence,
    TimingEntry,
    TtsPreviewLock,
    TtsProfile,
    TtsSentenceManifestEntry,
    TtsRunManifest,
    TtsRuntimeInfo,
    VoicePresetArg,
    VoiceRuntimeDType,
)
from . import gpu_guard
from .pipeline_manifest import build_initial_pipeline_manifest, record_tts_artifact, text_hash, update_stage_status
from .text_health import looks_mojibake
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
GPU_WAIT_TIMEOUT_SEC = 30.0
GPU_WAIT_POLL_SEC = 1.0
GENERATION_MEMORY_CLEANUP_INTERVAL = 5
SENTENCE_GAP_SEC = 0.3
TAIL_SILENCE_THRESHOLD = 0.003
TAIL_SILENCE_MIN_SEC = 0.12
TAIL_SILENCE_KEEP_SEC = 0.03
TTS_AUDIO_DRIFT_WARN_RATIO = 0.65
TTS_PITCH_DRIFT_WARN_RATIO = 0.22
TTS_FULL_PASSAGE_PITCH_DRIFT_WARN_RATIO = 0.35
TTS_DC_OFFSET_WARN_RATIO = 0.08


class _FallbackGenerationConfig:
    def __init__(
        self,
        *,
        num_step: int,
        guidance_scale: float,
        denoise: bool,
        postprocess_output: bool,
    ) -> None:
        self.num_step = num_step
        self.guidance_scale = guidance_scale
        self.denoise = denoise
        self.postprocess_output = postprocess_output


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
        project["compiled_script"] or project["script"],
    )


def _acquire_tts_gpu(owner: str, *, timeout_sec: float = GPU_WAIT_TIMEOUT_SEC) -> None:
    deadline = time.monotonic() + max(timeout_sec, 1.0)
    while time.monotonic() < deadline:
        if gpu_guard.acquire("tts", owner, timeout_sec=max(int(timeout_sec), 1)):
            return
        if gpu_guard.current_owner().startswith("source-draft:"):
            try:
                from .llm_ollama import OllamaClient  # noqa: WPS433

                OllamaClient(model=SCRIPT_LLM_MODEL).unload()
            except Exception:
                pass
        time.sleep(GPU_WAIT_POLL_SEC)
    owner_name = gpu_guard.current_owner() or "unknown owner"
    raise RuntimeError(f"GPU is busy with {owner_name}; try again in a moment.")


def unload_model() -> None:
    global _model
    if _model is not None:
        del _model
        _model = None
    gc.collect()
    try:
        import torch  # noqa: WPS433
    except Exception:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _cleanup_generation_memory() -> None:
    gc.collect()
    try:
        import torch  # noqa: WPS433
    except Exception:
        return
    if not torch.cuda.is_available():
        return
    torch.cuda.empty_cache()
    try:
        torch.cuda.synchronize()
    except Exception:
        pass


def _trim_trailing_silence(audio: AudioBufferLike) -> AudioBufferLike:
    import numpy as np  # noqa: WPS433

    array = np.asarray(audio)
    if array.size == 0:
        return cast(AudioBufferLike, array)
    if array.ndim == 1:
        amplitude = np.abs(array)
    else:
        amplitude = np.max(np.abs(array), axis=tuple(range(1, array.ndim)))
    non_silent = np.flatnonzero(amplitude > TAIL_SILENCE_THRESHOLD)
    if non_silent.size == 0:
        return array
    trim_start = int(non_silent[-1]) + 1
    trailing_samples = max(0, int(array.shape[0]) - trim_start)
    trailing_sec = trailing_samples / SAMPLE_RATE
    if trailing_sec < TAIL_SILENCE_MIN_SEC:
        return cast(AudioBufferLike, array)
    keep_samples = int(TAIL_SILENCE_KEEP_SEC * SAMPLE_RATE)
    end_index = min(int(array.shape[0]), trim_start + keep_samples)
    return cast(AudioBufferLike, array[:end_index])


def _build_generation_config(profile: TtsProfile) -> object:
    try:
        from omnivoice import OmniVoiceGenerationConfig  # noqa: WPS433
    except ModuleNotFoundError:
        return _FallbackGenerationConfig(
            num_step=profile["num_step"],
            guidance_scale=profile["guidance_scale"],
            denoise=profile["denoise"],
            postprocess_output=profile["postprocess_output"],
        )

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


def synthesize_preview(text: str, preset: str, *, owner: str | None = None) -> AudioBufferLike:
    gpu_owner = owner or f"tts-preview:{preset}"
    _acquire_tts_gpu(gpu_owner)
    try:
        model = _get_model()
        _, profile = normalize_tts_profile({}, preset, text)
        profile = ensure_seed(profile)
        return _synthesize_one(model, text, profile)
    finally:
        unload_model()
        gpu_guard.release(gpu_owner)


def synthesize_preview_with_profile(
    text: str,
    preset: str,
    payload: object,
    *,
    owner: str | None = None,
) -> tuple[str, TtsProfile, TtsPreviewLock, AudioBufferLike]:
    gpu_owner = owner or f"tts-preview:{preset}"
    _acquire_tts_gpu(gpu_owner)
    try:
        model = _get_model()
        normalized_preset, profile = normalize_tts_profile(payload, preset, text)
        profile = ensure_seed(profile)
        preview_lock = build_preview_lock(normalized_preset, profile)
        return normalized_preset, profile, preview_lock, _synthesize_one(model, text, profile)
    finally:
        unload_model()
        gpu_guard.release(gpu_owner)


def _sanitize_audio_for_write(audio: AudioBufferLike) -> object:
    import numpy as np  # noqa: WPS433

    array = np.asarray(audio, dtype=np.float32)
    if array.size == 0:
        return array
    array = np.squeeze(array)
    if array.ndim == 0:
        array = array.reshape(1)
    if array.ndim > 2:
        array = array.reshape(array.shape[0], -1)
    array = np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0)
    if array.ndim == 1:
        array = array - float(np.mean(array))
    else:
        array = array - np.mean(array, axis=0, keepdims=True)
    peak = float(np.max(np.abs(array))) if array.size else 0.0
    if peak > 0.98:
        array = array * (0.98 / peak)
    return array


def save_audio_file(audio: AudioBufferLike, out_path: Path) -> None:
    import soundfile as sf  # noqa: WPS433

    sf.write(out_path, _sanitize_audio_for_write(audio), SAMPLE_RATE)


def write_tts_error(pid: str, message: str, traceback_text: str = "") -> Path:
    output_dir = db.project_dir(pid) / "tts"
    output_dir.mkdir(parents=True, exist_ok=True)
    error_path = output_dir / "tts_error.json"
    payload = {
        "project_id": pid,
        "message": message,
        "traceback": traceback_text,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    error_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return error_path


def _clear_tts_outputs(output_dir: Path) -> None:
    for audio_path in output_dir.glob("*.wav"):
        audio_path.unlink(missing_ok=True)
    for json_name in ("timings.json", "timings_words.json", "tts_run_manifest.json", "tts_consistency_report.json"):
        timings_path = output_dir / json_name
        if timings_path.exists():
            timings_path.unlink()


def _estimate_pitch_hz(array: object, sample_rate: int) -> float | None:
    import numpy as np  # noqa: WPS433

    audio = np.asarray(array, dtype=np.float64)
    if audio.size < int(sample_rate * 0.08):
        return None
    audio = audio - np.mean(audio)
    frame_size = max(1, int(sample_rate * 0.04))
    hop_size = max(1, int(sample_rate * 0.02))
    min_lag = max(1, int(sample_rate / 420))
    max_lag = max(min_lag + 1, int(sample_rate / 60))
    estimates: list[float] = []
    for start in range(0, max(1, audio.size - frame_size), hop_size):
        frame = audio[start : start + frame_size]
        if frame.size < frame_size:
            break
        energy = float(np.sqrt(np.mean(np.square(frame))))
        if energy < 0.005:
            continue
        frame = frame * np.hanning(frame.size)
        corr = np.correlate(frame, frame, mode="full")[frame.size - 1 :]
        if corr.size <= max_lag:
            continue
        search = corr[min_lag:max_lag]
        if search.size == 0:
            continue
        lag = int(np.argmax(search)) + min_lag
        if corr[0] <= 0 or corr[lag] / corr[0] < 0.25:
            continue
        estimates.append(float(sample_rate) / float(lag))
    if not estimates:
        return None
    return float(np.median(estimates))


def _audio_feature_summary(audio_path: Path) -> dict[str, object]:
    if not audio_path.exists():
        return {
            "path": str(audio_path),
            "available": False,
            "duration_sec": 0.0,
            "rms": 0.0,
            "spectral_centroid_hz": 0.0,
            "estimated_pitch_hz": None,
        }
    import numpy as np  # noqa: WPS433
    import soundfile as sf  # noqa: WPS433

    data, sample_rate = sf.read(audio_path)
    array = np.asarray(data, dtype=np.float64)
    if array.size == 0:
        return {
            "path": str(audio_path),
            "available": False,
            "duration_sec": 0.0,
            "rms": 0.0,
            "spectral_centroid_hz": 0.0,
            "estimated_pitch_hz": None,
        }
    if array.ndim > 1:
        array = np.mean(array, axis=1)
    duration_sec = float(array.shape[0]) / float(sample_rate)
    dc_offset_abs = float(abs(np.mean(array)))
    rms = float(np.sqrt(np.mean(np.square(array))))
    spectrum = np.abs(np.fft.rfft(array))
    frequencies = np.fft.rfftfreq(array.shape[0], d=1.0 / float(sample_rate))
    magnitude_sum = float(np.sum(spectrum))
    centroid = 0.0 if magnitude_sum <= 0 else float(np.sum(frequencies * spectrum) / magnitude_sum)
    pitch_hz = _estimate_pitch_hz(array, int(sample_rate))
    return {
        "path": str(audio_path),
        "available": True,
        "duration_sec": round(duration_sec, 3),
        "dc_offset_abs": round(dc_offset_abs, 6),
        "rms": round(rms, 6),
        "spectral_centroid_hz": round(centroid, 2),
        "estimated_pitch_hz": round(pitch_hz, 2) if pitch_hz is not None else None,
    }


def _relative_drift(value: float, anchor: float) -> float:
    if anchor <= 0:
        return 0.0
    return abs(value - anchor) / anchor


def _float_feature(features: dict[str, object], key: str) -> float:
    value = features.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _metadata_consistent(manifest: TtsRunManifest) -> bool:
    sentences = manifest["sentences"]
    if not sentences:
        return True
    first = sentences[0]
    first_profile = first["effective_profile"]
    keys = ("mode", "synthesis_mode", "language", "instruct", "num_step", "guidance_scale", "seed_mode", "seed")
    for sentence in sentences[1:]:
        profile = sentence["effective_profile"]
        if sentence["voice_preset"] != first["voice_preset"]:
            return False
        for key in keys:
            if profile.get(key) != first_profile.get(key):
                return False
    return True


def save_tts_consistency_report(output_dir: Path, manifest: TtsRunManifest) -> Path:
    sentence_reports: list[dict[str, object]] = []
    anchor_centroid = 0.0
    anchor_rms = 0.0
    max_centroid_drift = 0.0
    max_rms_drift = 0.0
    max_pitch_drift = 0.0
    max_dc_offset = 0.0
    anchor_pitch: float | None = None
    for sentence in manifest["sentences"]:
        idx = int(sentence["idx"])
        features = _audio_feature_summary(output_dir / f"{idx:04d}.wav")
        centroid = _float_feature(features, "spectral_centroid_hz")
        rms = _float_feature(features, "rms")
        dc_offset = _float_feature(features, "dc_offset_abs")
        raw_pitch = features.get("estimated_pitch_hz")
        pitch = float(raw_pitch) if isinstance(raw_pitch, (int, float)) else None
        if not sentence_reports:
            anchor_centroid = centroid
            anchor_rms = rms
            anchor_pitch = pitch
        centroid_drift = _relative_drift(centroid, anchor_centroid)
        rms_drift = _relative_drift(rms, anchor_rms)
        pitch_drift = _relative_drift(pitch or 0.0, anchor_pitch or 0.0) if pitch is not None and anchor_pitch is not None else 0.0
        max_centroid_drift = max(max_centroid_drift, centroid_drift)
        max_rms_drift = max(max_rms_drift, rms_drift)
        max_pitch_drift = max(max_pitch_drift, pitch_drift)
        max_dc_offset = max(max_dc_offset, dc_offset)
        sentence_reports.append(
            {
                "idx": idx,
                "text": sentence["text"],
                "voice_preset": sentence["voice_preset"],
                "seed": sentence["seed"],
                "features": features,
                "spectral_centroid_relative_drift": round(centroid_drift, 4),
                "rms_relative_drift": round(rms_drift, 4),
                "estimated_pitch_relative_drift": round(pitch_drift, 4),
            }
        )
    metadata_consistent = _metadata_consistent(manifest)
    synthesis_mode = manifest["tts_profile"].get("synthesis_mode", "sentence")
    pitch_warn_ratio = (
        TTS_FULL_PASSAGE_PITCH_DRIFT_WARN_RATIO
        if synthesis_mode == "full_passage"
        else TTS_PITCH_DRIFT_WARN_RATIO
    )
    audio_checked = any(
        bool(features.get("available"))
        for item in sentence_reports
        for features in [item.get("features")]
        if isinstance(features, dict)
    )
    audio_passed = (not audio_checked) or (
        max_centroid_drift <= TTS_AUDIO_DRIFT_WARN_RATIO
        and max_pitch_drift <= pitch_warn_ratio
        and max_dc_offset <= TTS_DC_OFFSET_WARN_RATIO
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metadata_consistent": metadata_consistent,
        "audio_consistency_checked": audio_checked,
        "audio_consistency_passed": audio_passed,
        "max_spectral_centroid_relative_drift": round(max_centroid_drift, 4),
        "max_rms_relative_drift": round(max_rms_drift, 4),
        "max_estimated_pitch_relative_drift": round(max_pitch_drift, 4),
        "max_dc_offset_abs": round(max_dc_offset, 6),
        "dc_offset_warn_ratio": TTS_DC_OFFSET_WARN_RATIO,
        "pitch_drift_warn_ratio": pitch_warn_ratio,
        "recommended_tts_mode": synthesis_mode if metadata_consistent and audio_passed else "full_passage_or_reference_voice",
        "sentences": sentence_reports,
    }
    target = output_dir / "tts_consistency_report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def sync_tts_artifacts_to_pipeline_manifest(pid: str) -> None:
    project = db.get_project(pid)
    if project is None:
        return
    output_dir = db.project_dir(pid) / "tts"
    timings_path = output_dir / "timings.json"
    manifest_path = output_dir / "tts_run_manifest.json"
    if not timings_path.exists() or not manifest_path.exists():
        return
    try:
        timings_payload = json.loads(timings_path.read_text(encoding="utf-8"))
        run_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(timings_payload, list) or not isinstance(run_payload, dict):
        return
    raw_manifest_sentences = run_payload.get("sentences")
    manifest_sentences = raw_manifest_sentences if isinstance(raw_manifest_sentences, list) else []
    seed_by_idx: dict[int, int] = {}
    for item in manifest_sentences:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        seed = item.get("seed")
        if isinstance(idx, int) and isinstance(seed, int):
            seed_by_idx[idx] = seed
    pipeline_manifest = project["pipeline_manifest"]
    if len(pipeline_manifest.get("segments", [])) != len(project["sentences"]):
        pipeline_manifest = build_initial_pipeline_manifest(project["id"], project["title"], project["sentences"])
    for item in timings_payload:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        if not isinstance(idx, int):
            continue
        start = float(item.get("start") or 0.0)
        end = float(item.get("end") or start)
        duration = float(item.get("dur") or max(0.0, end - start))
        pipeline_manifest = record_tts_artifact(
            pipeline_manifest,
            sentence_idx=idx,
            wav_path=f"tts/{idx:04d}.wav",
            start=start,
            end=end,
            duration_sec=duration,
            seed=seed_by_idx.get(idx, 0),
            issue_codes=[],
        )
    pipeline_manifest = update_stage_status(
        pipeline_manifest,
        "tts",
        state="done",
        input_hash=text_hash(json.dumps(manifest_sentences, ensure_ascii=False, sort_keys=True)),
        output_hash=text_hash(json.dumps(timings_payload, ensure_ascii=False, sort_keys=True)),
    )
    db.update_project(pid, pipeline_manifest=pipeline_manifest)


def _effective_sentence_profile(
    profile: TtsProfile,
    index: int,
    _text: str,
    region: Region = "body",
) -> TtsProfile:
    sentence_profile = cast(TtsProfile, dict(profile))
    seed = sentence_profile["seed"]
    if seed is None:
        raise ValueError("TTS seed must be resolved before sentence profile creation")
    if sentence_profile["seed_mode"] == "per_sentence":
        sentence_profile["seed"] = seed + index
    else:
        sentence_profile["seed"] = seed
    if region == "bible":
        sentence_profile["speed"] = min(sentence_profile["speed"], 0.90)
    return sentence_profile


def _split_full_passage_audio(
    audio: AudioBufferLike,
    sentences: list[str],
) -> list[AudioBufferLike]:
    import numpy as np  # noqa: WPS433

    array = np.asarray(audio)
    if array.size == 0 or not sentences:
        return []
    total_samples = int(array.shape[0])
    weights = [max(1, len(sentence.strip())) for sentence in sentences]
    total_weight = max(1, sum(weights))
    chunks: list[AudioBufferLike] = []
    cursor = 0
    for index, weight in enumerate(weights):
        if index == len(weights) - 1:
            end = total_samples
        else:
            remaining_sentences = len(weights) - index - 1
            target = round(total_samples * weight / total_weight)
            end = min(total_samples - remaining_sentences, max(cursor + 1, cursor + target))
        chunks.append(cast(AudioBufferLike, array[cursor:end]))
        cursor = end
    return chunks


def _regional_sentences_for_project(project: ProjectRecord) -> list[RegionalSentence]:
    if project["regional_sentences"]:
        return [
            {
                "idx": index,
                "text": normalize_tts_reading_text(sentence["text"]),
                "region": sentence["region"],
            }
            for index, sentence in enumerate(project["regional_sentences"])
            if is_tts_readable_text(normalize_tts_reading_text(sentence["text"]))
        ]
    filtered = filter_tts_segments(project["sentences"])
    return [
        {
            "idx": index,
            "text": normalize_tts_reading_text(text),
            "region": "body",
        }
        for index, text in enumerate(filtered)
        if is_tts_readable_text(normalize_tts_reading_text(text))
    ]


def run_tts_job(pid: str) -> None:
    project = db.get_project(pid)
    if project is None:
        return
    gpu_owner = f"tts-job:{pid}"
    regional_sentences = _regional_sentences_for_project(project)
    sentences = [sentence["text"] for sentence in regional_sentences]
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
        mojibake_indexes = [
            index
            for index, text in enumerate(sentences)
            if looks_mojibake(text)
        ]
        if mojibake_indexes:
            raise ValueError(
                "TTS input contains mojibake text at sentence "
                + ", ".join(str(index) for index in mojibake_indexes)
                + ". Regenerate the script before running TTS."
            )

        _acquire_tts_gpu(gpu_owner)
        model = _get_model()
        total = max(len(sentences), 1)
        timings: list[TimingEntry] = []
        manifest_sentences: list[TtsSentenceManifestEntry] = []
        cursor = 0.0
        synthesized_chunks: list[AudioBufferLike] = []
        full_passage_mode = profile.get("synthesis_mode", "sentence") == "full_passage"
        if full_passage_mode:
            full_text = "\n".join(sentences)
            full_profile = cast(TtsProfile, dict(profile))
            full_profile["duration"] = None
            audio = _synthesize_one(model, full_text, full_profile)
            if len(audio) == 0:
                raise ValueError("OmniVoice returned empty audio for full passage synthesis")
            trimmed_audio = _trim_trailing_silence(audio)
            if len(trimmed_audio) == 0:
                raise ValueError("OmniVoice returned silence-only audio for full passage synthesis")
            synthesized_chunks = _split_full_passage_audio(trimmed_audio, sentences)
            if len(synthesized_chunks) != len(sentences):
                raise ValueError("Full passage synthesis did not produce sentence chunks")

        for index, text in enumerate(sentences):
            region = regional_sentences[index]["region"]
            if full_passage_mode:
                sentence_profile = cast(TtsProfile, dict(profile))
            else:
                sentence_profile = _effective_sentence_profile(profile, index, text, region)
            sentence_seed = sentence_profile["seed"]
            if sentence_seed is None:
                raise ValueError("TTS sentence seed must be resolved before synthesis")
            if full_passage_mode:
                trimmed_audio = synthesized_chunks[index]
            else:
                audio = _synthesize_one(model, text, sentence_profile)
                if len(audio) == 0:
                    raise ValueError(
                        f"OmniVoice returned empty audio for sentence {index}: {text[:80]}"
                    )
                trimmed_audio = _trim_trailing_silence(audio)
            if len(trimmed_audio) == 0:
                raise ValueError(
                    f"OmniVoice returned silence-only audio for sentence {index}: {text[:80]}"
                )
            duration = float(len(trimmed_audio)) / SAMPLE_RATE
            save_audio_file(trimmed_audio, output_dir / f"{index:04d}.wav")
            timings.append(
                {
                    "idx": index,
                    "text": text,
                    "start": round(cursor, 3),
                    "end": round(cursor + duration, 3),
                    "dur": round(duration, 3),
                    "region": region,
                }
            )
            manifest_sentences.append(
                {
                    "idx": index,
                    "text": text,
                    "region": region,
                    "voice_preset": preset,
                    "effective_profile": sentence_profile,
                    "kwargs": tts_profile_to_manifest_kwargs(sentence_profile),
                    "seed": sentence_seed,
                }
            )
            gap_after = 0.0 if full_passage_mode else SENTENCE_GAP_SEC if index < len(sentences) - 1 else 0.0
            cursor += duration + gap_after
            db.update_project(pid, tts_progress=int((index + 1) / total * 100))
            if (index + 1) % GENERATION_MEMORY_CLEANUP_INTERVAL == 0:
                _cleanup_generation_memory()

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
        save_tts_consistency_report(output_dir, manifest)
        sync_tts_artifacts_to_pipeline_manifest(pid)
        db.update_project(
            pid,
            voice_preset=preset,
            tts_profile=profile,
            tts_state="done",
            tts_progress=100,
            tts_error="",
        )
    except Exception as exc:
        traceback_text = traceback.format_exc()
        print(traceback_text)
        _clear_tts_outputs(output_dir)
        write_tts_error(pid, str(exc), traceback_text)
        db.update_project(
            pid,
            tts_state="error",
            tts_error=str(exc),
            render_last_log=str(exc),
        )
    finally:
        unload_model()
        gpu_guard.release(gpu_owner)
