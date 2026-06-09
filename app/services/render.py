import json
import os
import shutil
import subprocess
import threading
import traceback
import wave
from collections import deque
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from time import monotonic

from .. import db
from ..config import ALLOWED_IMAGE_EXT, FPS, SHORTS_H, SHORTS_W, VIDEO_H, VIDEO_W
from ..types import ProjectRecord, RenderFormat, TimingEntry, WordTimingEntry
from .hyperframes_overlay import OVERLAY_DIR_NAME, write_overlay_project
from .render_plan import build_render_plan
from .render_report import build_render_report, save_render_report
from .subtitle import count_display_cues, write_ass
from .transcribe import save_word_timings
from .visual_relevance import (
    format_visual_relevance_issues,
    validate_generated_image_mappings,
    write_final_scene_review,
    write_visual_mismatch_report,
)
from scripts.render_hyperframes_overlay import render_hyperframes_overlay

PROGRESS_EMIT_INTERVAL_SEC = 0.5
SENTENCE_GAP_SEC = 0.3
AUDIO_DURATION_DRIFT_TOLERANCE_SEC = 1.0
AUDIO_SAMPLE_RATE = 24000
AUDIO_CHANNELS = 1
AUDIO_SAMPLE_WIDTH_BYTES = 2
FINAL_AUDIO_SAMPLE_RATE = 48000
FINAL_AUDIO_CHANNELS = 2


@dataclass
class ProgressEvent:
    phase_pct: int
    speed_x: float
    frame: int
    fps: float
    elapsed_sec: float
    eta_sec: int
    output_size_bytes: int


@dataclass(frozen=True)
class HyperFramesOverlayResult:
    overlay_path: Path | None
    status: str
    report_path: Path | None
    log: str


@dataclass(frozen=True)
class VisualSegment:
    path: Path
    duration_sec: float
    motion: str
    effect: str


@dataclass(frozen=True)
class VisualSegmentFramePlan:
    path: Path
    duration_sec: float
    motion: str
    effect: str
    frame_count: int
    target_frame_count: int
    frame_duration_sec: float
    drift_frames: int


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
    runaway_error = ""

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
                if expected_duration_sec > 1.0 and elapsed_sec > expected_duration_sec * 1.5:
                    runaway_error = (
                        "Render stopped because the generated video duration exceeded the expected "
                        f"timeline by too much ({elapsed_sec:.1f}s vs {expected_duration_sec:.1f}s)."
                    )
                    process.terminate()
                    break
            while True:
                try:
                    stderr_queue.get_nowait()
                    drained = True
                except Empty:
                    break
            if runaway_error:
                break
            if process.poll() is not None and progress_ended:
                break
            if process.poll() is not None and not drained:
                break
            emit_progress()
            threading.Event().wait(0.1)
    finally:
        try:
            process.wait(timeout=5.0)
        except TypeError:
            process.wait()
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=5.0)
            except TypeError:
                process.wait()
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)

    emit_progress(force=True)
    stderr_text = "\n".join(stderr_buffer)
    if runaway_error:
        detail = _tail_lines(stderr_text, limit=20)
        if detail:
            raise RuntimeError(f"{runaway_error}\n\n{detail}")
        raise RuntimeError(runaway_error)
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


def _write_silence_wav(target: Path, duration_sec: float) -> None:
    frame_count = max(1, int(round(duration_sec * AUDIO_SAMPLE_RATE)))
    silence_chunk = b"\x00" * (frame_count * AUDIO_CHANNELS * AUDIO_SAMPLE_WIDTH_BYTES)
    with wave.open(str(target), "wb") as handle:
        handle.setnchannels(AUDIO_CHANNELS)
        handle.setsampwidth(AUDIO_SAMPLE_WIDTH_BYTES)
        handle.setframerate(AUDIO_SAMPLE_RATE)
        handle.writeframes(silence_chunk)


def _concat_audio(tts_dir: Path, timings: list[TimingEntry], out_wav: Path) -> str:
    concat_list = tts_dir / "_concat.txt"
    gap_dir = tts_dir / "_gaps"
    gap_dir.mkdir(parents=True, exist_ok=True)
    try:
        with concat_list.open("w", encoding="utf-8") as handle:
            for index, timing in enumerate(timings):
                wav_path = tts_dir / f"{timing['idx']:04d}.wav"
                handle.write(f"file '{wav_path.as_posix()}'\n")
                if index >= len(timings) - 1:
                    continue
                next_timing = timings[index + 1]
                gap_sec = max(0.0, float(next_timing["start"] - timing["end"]))
                if gap_sec <= 0.005:
                    continue
                gap_path = gap_dir / f"gap_{index:04d}.wav"
                _write_silence_wav(gap_path, gap_sec)
                handle.write(f"file '{gap_path.as_posix()}'\n")
        return _run(
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
    finally:
        concat_list.unlink(missing_ok=True)
        shutil.rmtree(gap_dir, ignore_errors=True)


def _normalize_audio(
    in_wav: Path,
    out_wav: Path,
    *,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> str:
    command = [
        _ffmpeg(),
        "-y",
        "-i",
        str(in_wav),
        "-af",
        "highpass=f=80,loudnorm=I=-14:TP=-1.5:LRA=11",
        "-ar",
        str(AUDIO_SAMPLE_RATE),
        "-ac",
        str(AUDIO_CHANNELS),
        "-c:a",
        "pcm_s16le",
        str(out_wav),
    ]
    if on_progress is None:
        return _run(command)
    return _run_with_progress(
        command,
        expected_duration_sec=max(_probe_duration(in_wav), 0.1),
        on_progress=on_progress,
        output_path=out_wav,
        show_eta=False,
    )


def _validate_audio_duration_alignment(raw_audio_path: Path, normalized_audio_path: Path) -> tuple[float, float]:
    raw_duration_sec = _probe_duration(raw_audio_path)
    normalized_duration_sec = _probe_duration(normalized_audio_path)
    drift_sec = abs(raw_duration_sec - normalized_duration_sec)
    if drift_sec > AUDIO_DURATION_DRIFT_TOLERANCE_SEC:
        raise RuntimeError(
            "Normalized audio drift is too large "
            f"({raw_duration_sec:.2f}s vs {normalized_duration_sec:.2f}s)."
        )
    return raw_duration_sec, normalized_duration_sec


def _mix_background_audio(voice_wav: Path, bgm_path: Path, out_wav: Path, volume_db: int, ducking_enabled: bool) -> str:
    bgm_duration = _probe_duration(voice_wav)
    filter_graph = (
        f"[1:a]volume={volume_db}dB[bgm];"
        "[bgm][0:a]sidechaincompress=threshold=0.03:ratio=8[bgmduck];"
        "[0:a][bgmduck]amix=inputs=2:duration=first:dropout_transition=0[mix]"
        if ducking_enabled
        else f"[1:a]volume={volume_db}dB[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[mix]"
    )
    return _run(
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


def _zoompan_filter(index: int, per_item_duration: float, width: int, height: int, motion: str = "slow_zoom_in") -> str:
    frame_count = max(1, round(per_item_duration * FPS))
    overscan_width = max(width, int(width * 1.2))
    overscan_height = max(height, int(height * 1.2))
    if motion == "slow_zoom_out":
        zoom_expr = "max(1.0,1.10-on/1200)"
    else:
        zoom_expr = "min(zoom+0.0012,1.10)"
    return (
        f"[{index}:v]scale={overscan_width}:{overscan_height}:force_original_aspect_ratio=increase,"
        f"crop={overscan_width}:{overscan_height},zoompan=z='{zoom_expr}':d={frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height},"
        f"fps={FPS},trim=end_frame={frame_count},setpts=N/({FPS}*TB),"
        f"setsar=1,format=yuv420p[v{index}]"
    )


def _micro_motion_locked_filter(index: int, frame_count: int, width: int, height: int, motion: str = "micro_motion_locked") -> str:
    locked_frame_count = max(1, frame_count)
    overscan_width = max(width, int(width * 1.03))
    overscan_height = max(height, int(height * 1.03))
    if motion == "micro_motion_locked_out":
        zoom_expr = f"max(1.0,1.018-(on*0.018/max(1,{locked_frame_count - 1})))"
    else:
        zoom_expr = f"min(1.018,1.0+(on*0.018/max(1,{locked_frame_count - 1})))"
    return (
        f"[{index}:v]scale={overscan_width}:{overscan_height}:force_original_aspect_ratio=increase,"
        f"crop={overscan_width}:{overscan_height},zoompan=z='{zoom_expr}':d={locked_frame_count}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:"
        f"fps={FPS},trim=end_frame={locked_frame_count},setpts=N/({FPS}*TB),"
        f"setsar=1,format=yuv420p[v{index}]"
    )


def _stable_still_filter(index: int, frame_count: int, width: int, height: int) -> str:
    return (
        f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fps={FPS},trim=end_frame={frame_count},setpts=N/({FPS}*TB),"
        f"setsar=1,format=yuv420p[v{index}]"
    )


def _segment_effect_filter(duration_sec: float, effect: str) -> str:
    if effect != "fade" or duration_sec <= 0.25:
        return ""
    fade_duration = min(0.3, max(0.12, duration_sec * 0.18))
    fade_out_start = max(0.0, duration_sec - fade_duration)
    return (
        f",fade=t=in:st=0:d={fade_duration:.3f}"
        f",fade=t=out:st={fade_out_start:.3f}:d={fade_duration:.3f}"
    )


def _effective_segment_motion(segment: VisualSegment, kenburns_enabled: bool) -> str:
    if segment.motion == "still_locked":
        return "still_locked"
    if segment.motion in {
        "slow_zoom_in",
        "slow_zoom_out",
        "stable_zoom_in",
        "stable_zoom_out",
        "micro_motion_locked",
        "micro_motion_locked_out",
    }:
        return segment.motion
    if segment.motion == "none":
        return "slow_zoom_in" if kenburns_enabled else "none"
    return segment.motion


def _plan_visual_segment_frames(
    visual_segments: list[VisualSegment],
    total_duration: float,
) -> list[VisualSegmentFramePlan]:
    if not visual_segments:
        return []
    total_target_frames = max(1, round(max(total_duration, 0.1) * FPS))
    planned: list[VisualSegmentFramePlan] = []
    assigned_frames = 0
    for index, segment in enumerate(visual_segments):
        target_frame_count = max(1, round(max(segment.duration_sec, 0.2) * FPS))
        remaining_segments = len(visual_segments) - index - 1
        if index == len(visual_segments) - 1:
            frame_count = max(1, total_target_frames - assigned_frames)
        else:
            max_for_current = max(1, total_target_frames - assigned_frames - remaining_segments)
            frame_count = min(target_frame_count, max_for_current)
        assigned_frames += frame_count
        planned.append(
            VisualSegmentFramePlan(
                path=segment.path,
                duration_sec=max(segment.duration_sec, 0.2),
                motion=segment.motion,
                effect=segment.effect,
                frame_count=frame_count,
                target_frame_count=target_frame_count,
                frame_duration_sec=frame_count / FPS,
                drift_frames=frame_count - target_frame_count,
            )
        )
    return planned


def _validate_planned_frame_count(frame_plan: list[VisualSegmentFramePlan], total_duration: float) -> None:
    expected_total_frames = max(1, round(max(total_duration, 0.1) * FPS))
    actual_total_frames = sum(item.frame_count for item in frame_plan)
    if actual_total_frames != expected_total_frames:
        raise RuntimeError(
            "Visual frame allocation drifted away from the target timeline "
            f"({actual_total_frames} frames vs {expected_total_frames} frames)."
        )


def _resolve_visual_segments(project: ProjectRecord, media_dir: Path, total_duration: float) -> list[VisualSegment]:
    render_plan = project["render_plan"]
    if render_plan:
        resolved: list[VisualSegment] = []
        for segment in render_plan["segments"]:
            duration_sec = max(0.2, float(segment["end"] - segment["start"]))
            media_path = next(
                (
                    media_dir / media["path"]
                    for media in segment["media"]
                    if (media_dir / media["path"]).exists()
                ),
                None,
            )
            if media_path is None:
                continue
            resolved.append(
                VisualSegment(
                    path=media_path,
                    duration_sec=duration_sec,
                    motion=segment["motion"],
                    effect=segment["effect"],
                )
            )
        if resolved:
            return resolved

    media_files = [
        media_dir / name
        for name in project["media_order"]
        if (media_dir / name).exists()
    ]
    if not media_files:
        return []
    per_item_duration = max(total_duration / len(media_files), 0.5)
    fallback_motion = "still_locked" if len(media_files) == 1 else ("slow_zoom_in" if project["kenburns_enabled"] else "none")
    return [
        VisualSegment(
            path=media_path,
            duration_sec=per_item_duration,
            motion=fallback_motion,
            effect="none",
        )
        for media_path in media_files
    ]


def _build_visual_track(
    media_files: list[Path],
    total_duration: float,
    out_mp4: Path,
    render_format: RenderFormat,
    kenburns_enabled: bool,
    *,
    segments: list[VisualSegment] | None = None,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> str:
    visual_segments = segments or [
        VisualSegment(
            path=media_path,
            duration_sec=max(total_duration / max(1, len(media_files)), 0.5),
            motion="still_locked" if len(media_files) == 1 else ("slow_zoom_in" if kenburns_enabled else "none"),
            effect="none",
        )
        for media_path in media_files
    ]
    item_count = len(visual_segments)
    if item_count == 0:
        raise RuntimeError("no visual segments")
    width, height = (VIDEO_W, VIDEO_H) if render_format == "landscape" else (SHORTS_W, SHORTS_H)
    frame_plan = _plan_visual_segment_frames(visual_segments, total_duration)
    _validate_planned_frame_count(frame_plan, total_duration)

    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    for index, segment in enumerate(frame_plan):
        media_path = segment.path
        segment_duration = segment.frame_duration_sec
        is_image = media_path.suffix.lower() in ALLOWED_IMAGE_EXT
        effective_motion = _effective_segment_motion(
            VisualSegment(
                path=segment.path,
                duration_sec=segment.duration_sec,
                motion=segment.motion,
                effect=segment.effect,
            ),
            kenburns_enabled,
        )
        use_motion = is_image and effective_motion not in {"none", "still_locked"}
        if is_image and use_motion:
            inputs += ["-loop", "1", "-framerate", "1", "-i", str(media_path)]
        elif is_image:
            inputs += ["-loop", "1", "-framerate", str(FPS), "-i", str(media_path)]
        else:
            inputs += ["-t", f"{segment_duration:.3f}", "-i", str(media_path)]
        if is_image and effective_motion in {"micro_motion_locked", "micro_motion_locked_out"}:
            filters.append(
                _micro_motion_locked_filter(index, segment.frame_count, width, height, effective_motion)
                .replace(f"[v{index}]", f"[basev{index}]")
            )
        elif is_image and use_motion:
            filters.append(
                _zoompan_filter(index, segment_duration, width, height, effective_motion)
                .replace(f"[v{index}]", f"[basev{index}]")
            )
        else:
            filters.append(_stable_still_filter(index, segment.frame_count, width, height).replace(f"[v{index}]", f"[basev{index}]"))
        effect_filter = _segment_effect_filter(segment_duration, segment.effect)
        if effect_filter:
            filters.append(
                f"[basev{index}]{effect_filter.lstrip(',')}[v{index}]"
            )
        else:
            filters.append(f"[basev{index}]null[v{index}]")
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
        return _run(command)
    return _run_with_progress(
        command,
        expected_duration_sec=max(sum(segment.frame_duration_sec for segment in frame_plan), 0.1),
        on_progress=on_progress,
        output_path=out_mp4,
    )


def _escape_filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace(":", "\\:").replace("'", r"\'")


def _hyperframes_required(options: dict[str, object], *, env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return bool(options.get("hyperframes_overlay_required")) or source.get("NEWAUTO_HYPERFRAMES_STRICT") == "1"


def _hyperframes_overlay_path(project_dir: Path) -> Path | None:
    overlay_dir = project_dir / "hyperframes_overlay"
    report_path = overlay_dir / "overlay_report.json"
    if report_path.exists():
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("ok") is True:
            raw_path = payload.get("overlay_path")
            if isinstance(raw_path, str) and raw_path.strip():
                candidate = Path(raw_path)
                if not candidate.is_absolute():
                    if not candidate.exists():
                        candidate = project_dir / candidate
                if candidate.exists():
                    return candidate
    for name in ("overlay.webm", "overlay.mov"):
        candidate = overlay_dir / name
        if candidate.exists():
            return candidate
    return None


def _render_dimensions(render_format: RenderFormat) -> tuple[int, int]:
    if render_format == "shorts":
        return SHORTS_W, SHORTS_H
    return VIDEO_W, VIDEO_H


def _prepare_hyperframes_overlay(
    project_dir: Path,
    timings: list[dict[str, object]],
    options: dict[str, object],
    *,
    render_format: RenderFormat,
) -> HyperFramesOverlayResult:
    if options.get("hyperframes_overlay_enabled") is not True:
        return HyperFramesOverlayResult(None, "skipped", None, "HyperFrames overlay disabled.")
    overlay_dir = project_dir / OVERLAY_DIR_NAME
    width, height = _render_dimensions(render_format)
    normalized_timings: list[dict[str, object]] = []
    for index, item in enumerate(timings):
        normalized_timings.append(
            {
                "sentence_idx": int(item.get("idx", item.get("sentence_idx", index)) or index),
                "start": float(item.get("start", 0.0) or 0.0),
                "end": float(item.get("end", item.get("start", 0.0)) or 0.0),
                "text": str(item.get("text", "")),
            }
        )
    write_overlay_project(overlay_dir, normalized_timings, width=width, height=height)
    expected_duration = max((float(item.get("end", 0.0) or 0.0) for item in normalized_timings), default=0.0)
    report = render_hyperframes_overlay(overlay_dir, expected_duration_sec=expected_duration)
    report_path = overlay_dir / "overlay_report.json"
    if report.get("ok") is True:
        overlay_path = _hyperframes_overlay_path(project_dir)
        if overlay_path is not None:
            return HyperFramesOverlayResult(overlay_path, "done", report_path, f"HyperFrames overlay ready: {overlay_path}")
    detail = str(report.get("validation", {}).get("error") if isinstance(report.get("validation"), dict) else "")
    return HyperFramesOverlayResult(None, "failed", report_path, detail or "HyperFrames overlay generation failed.")


def _mux(
    silent_video: Path,
    audio: Path,
    subtitle_path: Path,
    out_mp4: Path,
    *,
    overlay_path: Path | None = None,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> str:
    subtitle_filter = f"ass='{_escape_filter_path(subtitle_path)}'"
    if overlay_path is None:
        command = [
            _ffmpeg(),
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(audio),
            "-vf",
            subtitle_filter,
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
            "-ar",
            str(FINAL_AUDIO_SAMPLE_RATE),
            "-ac",
            str(FINAL_AUDIO_CHANNELS),
            "-b:a",
            "192k",
            "-shortest",
            str(out_mp4),
        ]
    else:
        filter_graph = f"[0:v][1:v]overlay=0:0:format=auto:shortest=1[base];[base]{subtitle_filter}[v]"
        command = [
            _ffmpeg(),
            "-y",
            "-i",
            str(silent_video),
            "-i",
            str(overlay_path),
            "-i",
            str(audio),
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-map",
            "2:a:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            "-c:a",
            "aac",
            "-ar",
            str(FINAL_AUDIO_SAMPLE_RATE),
            "-ac",
            str(FINAL_AUDIO_CHANNELS),
            "-b:a",
            "192k",
            "-shortest",
            str(out_mp4),
        ]
    if on_progress is None:
        return _run(command)
    return _run_with_progress(
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


def _media_files_from_render_plan(project: ProjectRecord, media_dir: Path) -> list[Path]:
    render_plan = project["render_plan"]
    if not render_plan:
        return []
    media_files: list[Path] = []
    for segment in render_plan["segments"]:
        for media in segment["media"]:
            candidate = media_dir / media["path"]
            if candidate.exists():
                media_files.append(candidate)
                break
    return media_files


def _caption_style_map_from_render_plan(project: ProjectRecord) -> dict[int, str]:
    render_plan = project["render_plan"]
    if not render_plan:
        return {}
    cue_style_map: dict[int, str] = {}
    for segment in render_plan["segments"]:
        sentence_idx = segment.get("sentence_idx")
        if isinstance(sentence_idx, int):
            cue_style_map[sentence_idx] = segment["caption_style"]
    return cue_style_map


def _duration_guard_tolerance(expected_duration_sec: float) -> float:
    if expected_duration_sec < 60.0:
        return 0.5
    return min(1.0, expected_duration_sec * 0.01)


def _validate_output_duration(
    output_path: Path,
    *,
    expected_audio_duration_sec: float,
    expected_timeline_duration_sec: float,
) -> tuple[float, float]:
    output_duration_sec = _probe_duration(output_path)
    target_duration_sec = max(expected_audio_duration_sec, expected_timeline_duration_sec)
    drift_sec = abs(output_duration_sec - target_duration_sec)
    tolerance_sec = _duration_guard_tolerance(target_duration_sec)
    if drift_sec > tolerance_sec:
        output_path.unlink(missing_ok=True)
        raise RuntimeError(
            "Final output duration drift is too large "
            f"({output_duration_sec:.2f}s vs target {target_duration_sec:.2f}s)."
        )
    return output_duration_sec, drift_sec


def _operator_intervention_messages(project: ProjectRecord) -> list[str]:
    review_path = write_final_scene_review(project)
    try:
        payload = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    messages: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("operator_intervention_required") is not True:
            continue
        sentence_idx = entry.get("sentence_idx")
        reason = str(entry.get("operator_intervention_reason") or entry.get("retry_reason") or "visual review required")
        messages.append(f"sentence {sentence_idx}: {reason}")
    return messages


def _visual_plan_report(project: ProjectRecord, media_dir: Path, total_duration: float) -> tuple[list[VisualSegment], bool]:
    render_plan = project["render_plan"]
    if render_plan:
        resolved = _resolve_visual_segments(project, media_dir, total_duration)
        if resolved:
            return resolved, False
    media_files = [
        media_dir / name
        for name in project["media_order"]
        if (media_dir / name).exists()
    ]
    if not media_files:
        return [], bool(render_plan)
    per_item_duration = max(total_duration / len(media_files), 0.5)
    fallback_motion = "still_locked" if len(media_files) == 1 else ("slow_zoom_in" if project["kenburns_enabled"] else "none")
    return (
        [
            VisualSegment(
                path=media_path,
                duration_sec=per_item_duration,
                motion=fallback_motion,
                effect="none",
            )
            for media_path in media_files
        ],
        bool(render_plan),
    )


def run_render_job(pid: str) -> None:
    project = db.get_project(pid)
    if project is None:
        return
    ffmpeg_logs: list[str] = []
    fallback_used = False
    total_duration = 0.0
    raw_audio_duration_sec = 0.0
    normalized_audio_duration_sec = 0.0
    output_duration_sec = 0.0
    duration_drift_sec = 0.0
    duration_guard_passed = False
    timings: list[TimingEntry] = []
    word_timings: list[WordTimingEntry] = []
    visual_frame_plan: list[VisualSegmentFramePlan] = []
    try:
        project_dir = db.project_dir(pid)
        tts_dir = project_dir / "tts"
        media_dir = project_dir / "media"

        visual_relevance_issues = validate_generated_image_mappings(project)
        write_visual_mismatch_report(project)
        allow_visual_relevance_warnings = bool(
            project["body_image_options"].get("allow_visual_relevance_warnings_for_render")
        )
        if visual_relevance_issues and not allow_visual_relevance_warnings:
            raise RuntimeError(format_visual_relevance_issues(visual_relevance_issues))
        if visual_relevance_issues:
            ffmpeg_logs.append(format_visual_relevance_issues(visual_relevance_issues))
        intervention_messages = _operator_intervention_messages(project)
        if intervention_messages and not allow_visual_relevance_warnings:
            detail = "\n".join(f"- {message}" for message in intervention_messages[:8])
            raise RuntimeError("Operator visual review is required before render:\n" + detail)
        if intervention_messages:
            ffmpeg_logs.append(
                "Operator visual review override used:\n"
                + "\n".join(f"- {message}" for message in intervention_messages[:8])
            )

        timings_path = tts_dir / "timings.json"
        if not timings_path.exists():
            raise RuntimeError("timings.json missing - re-run TTS")
        timings = json.loads(timings_path.read_text(encoding="utf-8-sig"))
        total_duration = timings[-1]["end"] if timings else 0.0
        if total_duration <= 0:
            raise RuntimeError("audio duration is zero")

        if project["scene_plan"]:
            render_plan = build_render_plan(project)
            project = db.update_project(pid, render_plan=render_plan) or project
        media_files = _media_files_from_render_plan(project, media_dir)
        visual_segments, fallback_used = _visual_plan_report(project, media_dir, total_duration)
        visual_frame_plan = _plan_visual_segment_frames(visual_segments, total_duration)
        _validate_planned_frame_count(visual_frame_plan, total_duration)
        if not media_files:
            media_files = [segment.path for segment in visual_segments]
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
        concat_log = _concat_audio(tts_dir, timings, raw_audio_wav)
        if concat_log:
            ffmpeg_logs.append(concat_log)
        _set_render_stage(pid, 30, "concat_audio_done")

        word_timings = save_word_timings(tts_dir / "timings_words.json", timings)
        _set_render_stage(pid, 36, "build_word_timings")

        normalized_audio_wav = project_dir / "audio.wav"
        _set_render_stage(pid, 40, "normalize_audio")
        normalize_log = ""
        try:
            normalize_log = _normalize_audio(
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
            if normalize_log:
                ffmpeg_logs.append(normalize_log)
            raw_audio_duration_sec, normalized_audio_duration_sec = _validate_audio_duration_alignment(
                raw_audio_wav,
                normalized_audio_wav,
            )
        except Exception as exc:
            _set_render_stage(pid, 40, "normalize_audio", str(exc))
            raise
        _set_render_stage(pid, 48, "normalize_audio_done", normalize_log)

        final_audio_wav = normalized_audio_wav
        if project["bgm_file"]:
            bgm_path = project_dir / "bgm" / project["bgm_file"]
            if bgm_path.exists():
                mixed_audio_wav = project_dir / "audio_bgm.wav"
                _set_render_stage(pid, 52, "mix_bgm")
                mix_log = _mix_background_audio(
                    normalized_audio_wav,
                    bgm_path,
                    mixed_audio_wav,
                    project["bgm_volume_db"],
                    project["bgm_ducking_enabled"],
                )
                if mix_log:
                    ffmpeg_logs.append(mix_log)
                final_audio_wav = mixed_audio_wav
        _set_render_stage(pid, 58, "audio_ready")

        subtitle_path = project_dir / "subtitles.ass"
        _set_render_stage(pid, 62, "write_subtitles")
        write_ass(
            timings,
            subtitle_path,
            project["subtitle_style"],
            word_timings,
            _caption_style_map_from_render_plan(project),
        )
        _set_render_stage(pid, 68, "subtitles_ready")

        render_formats = project["render_formats"] or ["landscape"]
        progress_step = max(1, int(24 / max(1, len(render_formats))))
        current_progress = 68
        for render_format in render_formats:
            silent_video = project_dir / f"_visual_{render_format}.mp4"
            visual_phase = f"build_visual_{render_format}"
            mux_phase = f"mux_{render_format}"
            _set_render_stage(pid, current_progress + 2, visual_phase)
            visual_log = _build_visual_track(
                media_files,
                total_duration,
                silent_video,
                render_format,
                project["kenburns_enabled"],
                segments=visual_segments,
                on_progress=_phase_progress_callback(
                    pid,
                    visual_phase,
                    current_progress + 2,
                    12,
                ),
            )
            if visual_log:
                ffmpeg_logs.append(visual_log)
            output_path = _render_output_path(project_dir, render_format)
            overlay_path: Path | None = None
            body_image_options = dict(project["body_image_options"])
            if body_image_options.get("hyperframes_overlay_enabled") is True:
                overlay_result = _prepare_hyperframes_overlay(
                    project_dir,
                    timings,
                    body_image_options,
                    render_format=render_format,
                )
                overlay_path = overlay_result.overlay_path
                body_image_options["hyperframes_overlay_status"] = overlay_result.status
                body_image_options["hyperframes_overlay_report_path"] = (
                    str(overlay_result.report_path) if overlay_result.report_path is not None else ""
                )
                project = db.update_project(pid, body_image_options=body_image_options) or project
                if overlay_result.log:
                    ffmpeg_logs.append(overlay_result.log)
                if overlay_path is None and _hyperframes_required(body_image_options):
                    raise RuntimeError("HyperFrames overlay is required but generation failed: " + overlay_result.log)
            _set_render_stage(pid, current_progress + 14, mux_phase)
            mux_log = _mux(
                silent_video,
                final_audio_wav,
                subtitle_path,
                output_path,
                overlay_path=overlay_path,
                on_progress=_phase_progress_callback(
                    pid,
                    mux_phase,
                    current_progress + 14,
                    8,
                ),
            )
            if mux_log:
                ffmpeg_logs.append(mux_log)
            output_duration_sec, duration_drift_sec = _validate_output_duration(
                output_path,
                expected_audio_duration_sec=max(normalized_audio_duration_sec, raw_audio_duration_sec, total_duration),
                expected_timeline_duration_sec=total_duration,
            )
            duration_guard_passed = True
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
        latest_project = db.get_project(pid)
        if latest_project is not None:
            write_final_scene_review(latest_project)
            save_render_report(
                build_render_report(
                    latest_project,
                    status="done",
                    audio_duration_sec=total_duration,
                    audio_raw_duration_sec=raw_audio_duration_sec,
                    audio_normalized_duration_sec=normalized_audio_duration_sec,
                    output_duration_sec=output_duration_sec,
                    duration_drift_sec=duration_drift_sec,
                    duration_guard_passed=duration_guard_passed,
                    subtitle_cue_count=count_display_cues(timings, project["subtitle_style"], word_timings),
                    fallback_used=fallback_used,
                    ffmpeg_log_tail=_tail_lines("\n".join(ffmpeg_logs), limit=20),
                    segment_frame_data=visual_frame_plan,
                )
            )
    except Exception as exc:
        traceback.print_exc()
        if "project_dir" in locals():
            for partial_path in (
                project_dir / "_visual_landscape.mp4",
                project_dir / "_visual_shorts.mp4",
                project_dir / "audio_raw.wav",
            ):
                with suppress(OSError, PermissionError):
                    partial_path.unlink(missing_ok=True)
        db.update_project(
            pid,
            render_state="error",
            render_progress=0,
            render_phase="",
            render_phase_pct=0,
            render_progress_detail="",
            render_speed_x=0.0,
            render_eta_sec=0,
            render_last_log=_format_render_error(exc),
        )
        latest_project = db.get_project(pid)
        if latest_project is not None:
            save_render_report(
                build_render_report(
                    latest_project,
                    status="error",
                    audio_duration_sec=total_duration,
                    audio_raw_duration_sec=raw_audio_duration_sec,
                    audio_normalized_duration_sec=normalized_audio_duration_sec,
                    output_duration_sec=output_duration_sec,
                    duration_drift_sec=duration_drift_sec,
                    duration_guard_passed=duration_guard_passed,
                    subtitle_cue_count=count_display_cues(timings, project["subtitle_style"], word_timings),
                    fallback_used=fallback_used,
                    ffmpeg_log_tail=_tail_lines("\n".join(ffmpeg_logs), limit=20),
                    error=_format_render_error(exc),
                    segment_frame_data=visual_frame_plan,
                )
            )
