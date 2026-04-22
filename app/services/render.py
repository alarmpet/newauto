import json
import shutil
import subprocess
import traceback
from pathlib import Path

from .. import db
from ..config import ALLOWED_IMAGE_EXT, FPS, VIDEO_H, VIDEO_W
from ..types import TimingEntry
from .subtitle import write_srt


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


def _build_visual_track(media_files: list[Path], total_duration: float, out_mp4: Path) -> None:
    item_count = len(media_files)
    per_item_duration = max(total_duration / item_count, 0.5)

    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    for index, media_path in enumerate(media_files):
        is_image = media_path.suffix.lower() in ALLOWED_IMAGE_EXT
        if is_image:
            inputs += ["-loop", "1", "-t", f"{per_item_duration:.3f}", "-i", str(media_path)]
        else:
            inputs += ["-t", f"{per_item_duration:.3f}", "-i", str(media_path)]
        filters.append(
            f"[{index}:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:black,"
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


def _mux(silent_video: Path, audio: Path, srt: Path, out_mp4: Path) -> None:
    escaped_srt = srt.as_posix().replace(":", "\\:")
    video_filter = f"subtitles='{escaped_srt}':charenc=UTF-8"
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

        audio_wav = project_dir / "audio.wav"
        _concat_audio(tts_dir, timings, audio_wav)
        db.update_project(pid, render_progress=30)

        subtitle_path = project_dir / "subtitles.srt"
        write_srt(timings, subtitle_path)
        db.update_project(pid, render_progress=40)

        silent_video = project_dir / "_visual.mp4"
        _build_visual_track(media_files, total_duration, silent_video)
        db.update_project(pid, render_progress=80)

        output_path = project_dir / "output.mp4"
        _mux(silent_video, audio_wav, subtitle_path, output_path)
        silent_video.unlink(missing_ok=True)

        db.update_project(pid, render_state="done", render_progress=100)
    except Exception:
        traceback.print_exc()
        db.update_project(pid, render_state="error")
