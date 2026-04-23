import json
import shutil
import subprocess
import threading
import traceback
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from time import monotonic

from .. import db
from ..config import ALLOWED_IMAGE_EXT, FPS, SHORTS_H, SHORTS_W, VIDEO_H, VIDEO_W
from ..types import RenderFormat, TimingEntry
from .subtitle import write_ass
from .transcribe import save_word_timings

PROGRESS_EMIT_INTERVAL_SEC = 0.5


@dataclass
class ProgressEvent:
    phase_pct: int
    speed_x: float
    frame: int
    fps: float
    elapsed_sec: float
    eta_sec: int
    output_size_bytes: int


def _format_clock(total_seconds: float) -> str:
    clamped = max(0, int(total_seconds))
    hours = clamped // 3600
    minutes = (clamped % 3600) // 60
    seconds = clamped % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _decode_process_text(raw: bytes | str | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return raw


def _tail_lines(text: str | None, limit: int = 12) -> str:
    if not text:
        return ""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-limit:])


def _set_render_stage(pid: str, progress: int, phase: str, log: str = "") -> None:
    db.update_project(
        pid,
        render_progress=progress,
        render_phase=phase,
        render_phase_pct=0,
        render_progress_detail="",
        render_speed_x=0.0,
        render_eta_sec=0,
        render_last_log=log,
    )


def _ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg not found on PATH - install FFmpeg first")
    return executable


def _run(command: list[str]) -> str:
    process = subprocess.run(command, capture_output=True, text=False, check=False)
    stderr_text = _decode_process_text(process.stderr)
    stderr_tail = _tail_lines(stderr_text, limit=20)
    if process.returncode != 0:
        detail = stderr_tail or "ffmpeg failed with no stderr output"
        raise RuntimeError("ffmpeg failed:\n" + detail)
    return _tail_lines(stderr_text)


def _drain_stream(stream: object, queue: Queue[str], stderr_buffer: deque[str] | None = None) -> None:
    if not hasattr(stream, "readline"):
        return
    readline = getattr(stream, "readline")
    while True:
        raw = readline()
        if raw in (b"", ""):
            break
        text = _decode_process_text(raw).strip()
        if not text:
            continue
        queue.put(text)
        if stderr_buffer is not None:
            stderr_buffer.append(text)


def _parse_progress_time(line: str) -> float:
    if not line.startswith("out_time="):
        return 0.0
    value = line.split("=", maxsplit=1)[1]
    parts = value.split(":")
    if len(parts) != 3:
        return 0.0
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except ValueError:
        return 0.0
    return hours * 3600 + minutes * 60 + seconds


def _parse_progress_float(line: str, prefix: str, suffix: str = "") -> float:
    if not line.startswith(prefix):
        return 0.0
    raw_value = line.split("=", maxsplit=1)[1]
    if suffix and raw_value.endswith(suffix):
        raw_value = raw_value[: -len(suffix)]
    try:
        return float(raw_value)
    except ValueError:
        return 0.0


def _parse_progress_int(line: str, prefix: str) -> int:
    if not line.startswith(prefix):
        return 0
    try:
        return int(line.split("=", maxsplit=1)[1])
    except ValueError:
        return 0


def _format_progress_detail(event: ProgressEvent, *, show_eta: bool = True) -> str:
    detail = (
        f"{event.phase_pct}% | {event.speed_x:.2f}x | frame {event.frame} | "
        f"elapsed {_format_clock(event.elapsed_sec)}"
    )
    if show_eta and event.eta_sec > 0:
        return f"{detail} | ETA {_format_clock(event.eta_sec)}"
    if event.output_size_bytes > 0:
        size_mb = event.output_size_bytes / (1024 * 1024)
        return f"{detail} | output {size_mb:.1f} MB"
    return detail


def _phase_progress_callback(
    pid: str,
    phase: str,
    base_progress: int,
    span_progress: int,
    *,
    show_eta: bool = True,
) -> Callable[[ProgressEvent], None]:
    def on_progress(event: ProgressEvent) -> None:
        global_progress = min(99, base_progress + int(span_progress * event.phase_pct / 100))
        db.update_project(
            pid,
            render_progress=global_progress,
            render_phase=phase,
            render_phase_pct=event.phase_pct,
            render_progress_detail=_format_progress_detail(event, show_eta=show_eta),
            render_speed_x=event.speed_x,
            render_eta_sec=event.eta_sec,
        )

    return on_progress


def _run_with_progress(
    command: list[str],
    *,
    expected_duration_sec: float,
    on_progress: Callable[[ProgressEvent], None],
    output_path: Path | None = None,
    show_eta: bool = True,
) -> str:
    progress_command = [
        *command[:-1],
        "-progress",
        "pipe:1",
        "-nostats",
        "-stats_period",
        "0.5",
        command[-1],
    ]
    process = subprocess.Popen(
        progress_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        bufsize=0,
    )
    stdout_queue: Queue[str] = Queue()
    stderr_queue: Queue[str] = Queue()
    stderr_buffer: deque[str] = deque(maxlen=200)

    assert process.stdout is not None
    assert process.stderr is not None
    stdout_thread = threading.Thread(
        target=_drain_stream,
        args=(process.stdout, stdout_queue),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_drain_stream,
        args=(process.stderr, stderr_queue, stderr_buffer),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    frame = 0
    fps = 0.0
    speed_x = 0.0
    elapsed_sec = 0.0
    last_emit = 0.0
    start_time = monotonic()
    progress_ended = False

    def emit_progress(force: bool = False) -> None:
        nonlocal last_emit
        now = monotonic()
        if not force and now - last_emit < PROGRESS_EMIT_INTERVAL_SEC:
            return
        last_emit = now
        safe_expected = max(expected_duration_sec, 0.1)
        phase_pct = min(100, max(0, int((elapsed_sec / safe_expected) * 100)))
        eta_sec = 0
        if show_eta and speed_x > 0.05 and elapsed_sec < safe_expected:
            eta_sec = max(0, int((safe_expected - elapsed_sec) / speed_x))
        output_size_bytes = 0
        if output_path is not None and output_path.exists():
            output_size_bytes = output_path.stat().st_size
        on_progress(
            ProgressEvent(
                phase_pct=phase_pct,
                speed_x=speed_x,
                frame=frame,
                fps=fps,
                elapsed_sec=elapsed_sec if elapsed_sec > 0 else now - start_time,
                eta_sec=eta_sec,
                output_size_bytes=output_size_bytes,
            )
        )

    try:
        while True:
            drained = False
            while True:
                try:
                    line = stdout_queue.get_nowait()
                except Empty:
                    break
                drained = True
                if line.startswith("out_time="):
                    elapsed_sec = _parse_progress_time(line)
                elif line.startswith("frame="):
                    frame = _parse_progress_int(line, "frame=")
                elif line.startswith("fps="):
                    fps = _parse_progress_float(line, "fps=")
                elif line.startswith("speed="):
                    speed_x = _parse_progress_float(line, "speed=", suffix="x")
                elif line == "progress=end":
                    progress_ended = True
                emit_progress()
            while True:
                try:
                    stderr_queue.get_nowait()
                    drained = True
                except Empty:
                    break
            if process.poll() is not None and progress_ended:
                break
            if process.poll() is not None and not drained:
                break
            emit_progress()
            threading.Event().wait(0.1)
    finally:
        process.wait()
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)

    emit_progress(force=True)
    stderr_text = "\n".join(stderr_buffer)
    if process.returncode != 0:
        detail = _tail_lines(stderr_text, limit=20) or "ffmpeg failed with no stderr output"
        raise RuntimeError("ffmpeg failed:\n" + detail)
    return _tail_lines(stderr_text)


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
        text=False,
        check=False,
    )
    if process.returncode != 0:
        return 0.0
    try:
        return float(_decode_process_text(process.stdout).strip())
    except ValueError:
        return 0.0


def probe_media_dimensions(media_path: Path) -> tuple[int, int]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return (0, 0)
    process = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(media_path),
        ],
        capture_output=True,
        text=False,
        check=False,
    )
    if process.returncode != 0:
        return (0, 0)
    output = _decode_process_text(process.stdout).strip()
    try:
        width_text, height_text = output.split("x", maxsplit=1)
        return (int(width_text), int(height_text))
    except ValueError:
        return (0, 0)


def find_invalid_media_files(media_files: list[Path]) -> list[str]:
    invalid: list[str] = []
    for media_path in media_files:
        width, height = probe_media_dimensions(media_path)
        if width <= 0 or height <= 0:
            invalid.append(f"{media_path.name} (video stream metadata unavailable)")
    return invalid


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


def _normalize_audio(
    in_wav: Path,
    out_wav: Path,
    *,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> None:
    command = [
        _ffmpeg(),
        "-y",
        "-i",
        str(in_wav),
        "-af",
        "loudnorm=I=-14:TP=-1.5:LRA=11",
        str(out_wav),
    ]
    if on_progress is None:
        _run(command)
        return
    _run_with_progress(
        command,
        expected_duration_sec=max(_probe_duration(in_wav), 0.1),
        on_progress=on_progress,
        output_path=out_wav,
        show_eta=False,
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
        f"[{index}:v]scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2},zoompan=z='min(zoom+0.0012,1.10)':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height},"
        f"fps={FPS},setsar=1,format=yuv420p[v{index}]"
    )


def _build_visual_track(
    media_files: list[Path],
    total_duration: float,
    out_mp4: Path,
    render_format: RenderFormat,
    kenburns_enabled: bool,
    *,
    on_progress: Callable[[ProgressEvent], None] | None = None,
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
    command = [
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
    if on_progress is None:
        _run(command)
        return
    _run_with_progress(
        command,
        expected_duration_sec=max(total_duration, 0.1),
        on_progress=on_progress,
        output_path=out_mp4,
    )


def _escape_filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace(":", "\\:").replace("'", r"\'")


def _mux(
    silent_video: Path,
    audio: Path,
    subtitle_path: Path,
    out_mp4: Path,
    *,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> None:
    video_filter = f"ass='{_escape_filter_path(subtitle_path)}'"
    command = [
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
    if on_progress is None:
        _run(command)
        return
    _run_with_progress(
        command,
        expected_duration_sec=max(_probe_duration(audio), 0.1),
        on_progress=on_progress,
        output_path=out_mp4,
    )


def _render_output_path(project_dir: Path, render_format: RenderFormat) -> Path:
    if render_format == "shorts":
        return project_dir / "output_shorts.mp4"
    return project_dir / "output.mp4"


def _friendly_render_error(detail: str) -> str:
    if "Failed to configure output pad on Parsed_concat" in detail or "Input link in0:v0 parameters" in detail:
        return "입력 이미지와 영상의 최종 해상도가 서로 달라 하나의 영상으로 합치지 못했습니다."
    if "Invalid data found when processing input" in detail:
        return "손상되었거나 지원되지 않는 미디어 파일이 포함되어 있습니다."
    if "No such file or directory" in detail:
        return "필요한 미디어 파일 또는 자막 파일을 찾지 못했습니다."
    if "video stream metadata unavailable" in detail:
        return "미디어 파일 중 일부에서 영상 크기를 읽지 못했습니다."
    return ""


def _format_render_error(exc: Exception) -> str:
    detail = str(exc).strip() or exc.__class__.__name__
    ffmpeg_prefix = "ffmpeg failed:\n"
    if detail.startswith(ffmpeg_prefix):
        detail = detail[len(ffmpeg_prefix):].strip()
    friendly = _friendly_render_error(detail)
    if friendly:
        return f"{friendly}\n\n{detail}"
    return detail


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
        _set_render_stage(pid, 14, "validate_media")
        invalid_media = find_invalid_media_files(media_files)
        if invalid_media:
            detail = "\n".join(f"- {name}" for name in invalid_media)
            raise RuntimeError(f"Invalid media metadata:\n{detail}")

        _set_render_stage(pid, 18, "prepare_media")

        raw_audio_wav = project_dir / "audio_raw.wav"
        _set_render_stage(pid, 22, "concat_audio")
        _concat_audio(tts_dir, timings, raw_audio_wav)
        _set_render_stage(pid, 30, "concat_audio_done")

        word_timings = save_word_timings(tts_dir / "timings_words.json", timings)
        _set_render_stage(pid, 36, "build_word_timings")

        normalized_audio_wav = project_dir / "audio.wav"
        _set_render_stage(pid, 40, "normalize_audio")
        normalize_log = ""
        try:
            _normalize_audio(
                raw_audio_wav,
                normalized_audio_wav,
                on_progress=_phase_progress_callback(
                    pid,
                    "normalize_audio",
                    40,
                    8,
                    show_eta=False,
                ),
            )
        except Exception as exc:
            _set_render_stage(pid, 40, "normalize_audio", str(exc))
            raise
        else:
            _set_render_stage(pid, 48, "normalize_audio_done", normalize_log)

        final_audio_wav = normalized_audio_wav
        if project["bgm_file"]:
            bgm_path = project_dir / "bgm" / project["bgm_file"]
            if bgm_path.exists():
                mixed_audio_wav = project_dir / "audio_bgm.wav"
                _set_render_stage(pid, 52, "mix_bgm")
                _mix_background_audio(
                    normalized_audio_wav,
                    bgm_path,
                    mixed_audio_wav,
                    project["bgm_volume_db"],
                    project["bgm_ducking_enabled"],
                )
                final_audio_wav = mixed_audio_wav
        _set_render_stage(pid, 58, "audio_ready")

        subtitle_path = project_dir / "subtitles.ass"
        _set_render_stage(pid, 62, "write_subtitles")
        write_ass(timings, subtitle_path, project["subtitle_style"], word_timings)
        _set_render_stage(pid, 68, "subtitles_ready")

        render_formats = project["render_formats"] or ["landscape"]
        progress_step = max(1, int(24 / max(1, len(render_formats))))
        current_progress = 68
        for render_format in render_formats:
            silent_video = project_dir / f"_visual_{render_format}.mp4"
            visual_phase = f"build_visual_{render_format}"
            mux_phase = f"mux_{render_format}"
            _set_render_stage(pid, current_progress + 2, visual_phase)
            _build_visual_track(
                media_files,
                total_duration,
                silent_video,
                render_format,
                project["kenburns_enabled"],
                on_progress=_phase_progress_callback(
                    pid,
                    visual_phase,
                    current_progress + 2,
                    12,
                ),
            )
            output_path = _render_output_path(project_dir, render_format)
            _set_render_stage(pid, current_progress + 14, mux_phase)
            _mux(
                silent_video,
                final_audio_wav,
                subtitle_path,
                output_path,
                on_progress=_phase_progress_callback(
                    pid,
                    mux_phase,
                    current_progress + 14,
                    8,
                ),
            )
            silent_video.unlink(missing_ok=True)
            current_progress = min(95, current_progress + progress_step)
            _set_render_stage(pid, current_progress, f"done_{render_format}")

        db.update_project(
            pid,
            render_state="done",
            render_progress=100,
            render_phase="done",
            render_phase_pct=100,
            render_progress_detail="완료",
            render_speed_x=0.0,
            render_eta_sec=0,
            render_last_log="",
        )
    except Exception as exc:
        traceback.print_exc()
        db.update_project(
            pid,
            render_state="error",
            render_progress_detail="",
            render_speed_x=0.0,
            render_eta_sec=0,
            render_last_log=_format_render_error(exc),
        )
