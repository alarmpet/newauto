import json
import shutil
import subprocess
import traceback
from pathlib import Path

from .. import db
from ..config import ALLOWED_IMAGE_EXT, FPS, SHORTS_H, SHORTS_W, VIDEO_H, VIDEO_W
from ..types import RenderFormat, TimingEntry
from .subtitle import write_ass
from .transcribe import save_word_timings


def _ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg not found on PATH - install FFmpeg first")
    return executable


def _run(command: list[str]) -> None:
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        stderr_tail = process.stderr.strip().splitlines()[-20:]
        raise RuntimeError("ffmpeg failed:\n" + "\n".join(stderr_tail))


def _probe_duration(media_path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    process = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        return 0.0
    try:
        return float(process.stdout.strip())
    except ValueError:
        return 0.0


def _concat_audio(tts_dir: Path, timings: list[TimingEntry], out_wav: Path) -> None:
    concat_list = tts_dir / "_concat.txt"
    with concat_list.open("w", encoding="utf-8") as handle:
        for timing in timings:
            wav_path = tts_dir / f"{timing['idx']:04d}.wav"
            handle.write(f"file '{wav_path.as_posix()}'\n")
    _run(
        [
            _ffmpeg(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ]
    )


def _normalize_audio(in_wav: Path, out_wav: Path) -> None:
    _run(
        [
            _ffmpeg(),
            "-y",
            "-i",
            str(in_wav),
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=11",
            str(out_wav),
        ]
    )


def _mix_background_audio(voice_wav: Path, bgm_path: Path, out_wav: Path, volume_db: int, ducking_enabled: bool) -> None:
    bgm_duration = _probe_duration(voice_wav)
    filter_graph = (
        f"[1:a]volume={volume_db}dB[bgm];"
        "[bgm][0:a]sidechaincompress=threshold=0.03:ratio=8[bgmduck];"
        "[0:a][bgmduck]amix=inputs=2:duration=first:dropout_transition=0[mix]"
        if ducking_enabled
        else f"[1:a]volume={volume_db}dB[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[mix]"
    )
    _run(
        [
            _ffmpeg(),
            "-y",
            "-i",
            str(voice_wav),
            "-stream_loop",
            "-1",
            "-t",
            f"{bgm_duration:.3f}",
            "-i",
            str(bgm_path),
            "-filter_complex",
            filter_graph,
            "-map",
            "[mix]",
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ]
    )


def _zoompan_filter(index: int, per_item_duration: float, width: int, height: int) -> str:
    frame_count = max(1, int(per_item_duration * FPS))
    return (
        f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},zoompan=z='min(zoom+0.0012,1.10)':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',fps={FPS},setsar=1,format=yuv420p[v{index}]"
    )


def _build_visual_track(
    media_files: list[Path],
    total_duration: float,
    out_mp4: Path,
    render_format: RenderFormat,
    kenburns_enabled: bool,
) -> None:
    item_count = len(media_files)
    per_item_duration = max(total_duration / item_count, 0.5)
    width, height = (VIDEO_W, VIDEO_H) if render_format == "landscape" else (SHORTS_W, SHORTS_H)

    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    for index, media_path in enumerate(media_files):
        is_image = media_path.suffix.lower() in ALLOWED_IMAGE_EXT
        if is_image:
            inputs += ["-loop", "1", "-t", f"{per_item_duration:.3f}", "-i", str(media_path)]
        else:
            inputs += ["-t", f"{per_item_duration:.3f}", "-i", str(media_path)]
        if is_image and kenburns_enabled:
            filters.append(_zoompan_filter(index, per_item_duration, width, height))
        else:
            filters.append(
                f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"setsar=1,fps={FPS},format=yuv420p[v{index}]"
            )
        labels.append(f"[v{index}]")

    concat_filter = "".join(labels) + f"concat=n={item_count}:v=1:a=0[vout]"
    filter_graph = ";".join(filters + [concat_filter])
    _run(
        [
            _ffmpeg(),
            "-y",
            *inputs,
            "-filter_complex",
            filter_graph,
            "-map",
            "[vout]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            "-preset",
            "veryfast",
            "-crf",
            "20",
            str(out_mp4),
        ]
    )


def _escape_filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace(":", "\\:").replace("'", r"\'")


def _mux(silent_video: Path, audio: Path, subtitle_path: Path, out_mp4: Path) -> None:
    video_filter = f"ass='{_escape_filter_path(subtitle_path)}'"
    _run(
        [
            _ffmpeg(),
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(audio),
            "-vf",
            video_filter,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(out_mp4),
        ]
    )


def _render_output_path(project_dir: Path, render_format: RenderFormat) -> Path:
    if render_format == "shorts":
        return project_dir / "output_shorts.mp4"
    return project_dir / "output.mp4"


def run_render_job(pid: str) -> None:
    project = db.get_project(pid)
    if project is None:
        return
    try:
        project_dir = db.project_dir(pid)
        tts_dir = project_dir / "tts"
        media_dir = project_dir / "media"

        timings_path = tts_dir / "timings.json"
        if not timings_path.exists():
            raise RuntimeError("timings.json missing - re-run TTS")
        timings = json.loads(timings_path.read_text(encoding="utf-8"))
        total_duration = timings[-1]["end"] if timings else 0.0
        if total_duration <= 0:
            raise RuntimeError("audio duration is zero")

        media_files = [
            media_dir / name
            for name in project["media_order"]
            if (media_dir / name).exists()
        ]
        if not media_files:
            raise RuntimeError("no valid media files")

        db.update_project(pid, render_progress=10)

        raw_audio_wav = project_dir / "audio_raw.wav"
        _concat_audio(tts_dir, timings, raw_audio_wav)
        db.update_project(pid, render_progress=30)

        word_timings = save_word_timings(tts_dir / "timings_words.json", timings)
        db.update_project(pid, render_progress=35)

        normalized_audio_wav = project_dir / "audio.wav"
        _normalize_audio(raw_audio_wav, normalized_audio_wav)
        db.update_project(pid, render_progress=45)

        final_audio_wav = normalized_audio_wav
        if project["bgm_file"]:
            bgm_path = project_dir / "bgm" / project["bgm_file"]
            if bgm_path.exists():
                mixed_audio_wav = project_dir / "audio_bgm.wav"
                _mix_background_audio(
                    normalized_audio_wav,
                    bgm_path,
                    mixed_audio_wav,
                    project["bgm_volume_db"],
                    project["bgm_ducking_enabled"],
                )
                final_audio_wav = mixed_audio_wav
        db.update_project(pid, render_progress=55)

        subtitle_path = project_dir / "subtitles.ass"
        write_ass(timings, subtitle_path, project["subtitle_style"], word_timings)
        db.update_project(pid, render_progress=65)

        render_formats = project["render_formats"] or ["landscape"]
        progress_step = max(1, int(30 / max(1, len(render_formats))))
        current_progress = 65
        for render_format in render_formats:
            silent_video = project_dir / f"_visual_{render_format}.mp4"
            _build_visual_track(
                media_files,
                total_duration,
                silent_video,
                render_format,
                project["kenburns_enabled"],
            )
            output_path = _render_output_path(project_dir, render_format)
            _mux(silent_video, final_audio_wav, subtitle_path, output_path)
            silent_video.unlink(missing_ok=True)
            current_progress = min(95, current_progress + progress_step)
            db.update_project(pid, render_progress=current_progress)

        db.update_project(pid, render_state="done", render_progress=100)
    except Exception:
        traceback.print_exc()
        db.update_project(pid, render_state="error")
