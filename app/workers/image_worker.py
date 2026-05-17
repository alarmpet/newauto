from __future__ import annotations

import time

from .. import db
from ..config import STORAGE_DIR
from ..services.comfyui_client import ComfyUIClient
from ..services.comfyui_pipeline import import_history_image, submit_z_image_workflow
from ..services.image_prompt import build_z_image_prompt
from ..types import ProjectRecord
from .worker_lock import single_instance_lock

POLL_INTERVAL_SEC = 3.0
WORKER_LOCK_PATH = STORAGE_DIR / "locks" / "image_worker.lock"


def _mark_error(pid: str, message: str) -> None:
    db.update_project(
        pid,
        body_image_state="error",
        body_image_progress=0,
        body_image_error=message,
        body_image_phase="error",
        body_image_last_log=message,
        body_image_job_id="",
        body_image_started_at="",
        body_image_heartbeat_at="",
    )


def _mark_stale_jobs_disabled() -> None:
    for project in db.list_projects():
        if project["body_image_state"] in {"queued", "running"}:
            db.update_project(
                project["id"],
                body_image_state="queued",
                body_image_progress=0,
                body_image_phase="queued",
                body_image_last_log="Z-Image Turbo image job queued.",
            )


def _sentence_indices(project: ProjectRecord) -> list[int]:
    options = project["body_image_options"]
    queued = options.get("queued_sentence_idx")
    if isinstance(queued, int):
        return [queued]
    return list(range(len(project["sentences"])))


def _process_project(pid: str) -> None:
    project = db.get_project(pid)
    if project is None:
        return
    options = project["body_image_options"]
    aspect_ratio = str(options.get("aspect_ratio") or "16:9")
    negative_override = str(options.get("negative_prompt_override") or "")
    indices = _sentence_indices(project)
    if not indices:
        _mark_error(pid, "No sentences are available for Z-Image generation.")
        return

    db.update_project(
        pid,
        body_image_phase="z_image_generating",
        body_image_last_log="Starting Z-Image Turbo generation.",
        body_image_progress=1,
    )
    client = ComfyUIClient(timeout_sec=30)
    for completed, sentence_idx in enumerate(indices):
        project = db.get_project(pid)
        if project is None:
            return
        if sentence_idx < 0 or sentence_idx >= len(project["sentences"]):
            _mark_error(pid, f"sentence_idx out of range: {sentence_idx}")
            return
        sentence = project["sentences"][sentence_idx]
        prompt = build_z_image_prompt(sentence, negative_prompt_override=negative_override)
        db.update_project(
            pid,
            body_image_phase="z_image_generating",
            body_image_last_log=f"Generating Z-Image for sentence {sentence_idx + 1}/{len(project['sentences'])}.",
            body_image_progress=max(1, int(completed / len(indices) * 95)),
        )
        db.touch_body_image_heartbeat(pid)
        try:
            prompt_id, results = submit_z_image_workflow(
                client,
                positive_prompt=prompt.positive,
                negative_prompt=prompt.negative,
                aspect_ratio=aspect_ratio,
                filename_prefix=f"newauto_{pid}_{sentence_idx}",
                timeout_sec=600,
            )
            import_history_image(
                project,
                result=results[0],
                prompt=prompt.positive,
                prompt_id=prompt_id,
                sentence_idx=sentence_idx,
                selected_reason="z_image_turbo_korean",
            )
        except Exception as exc:
            _mark_error(pid, str(exc))
            return

    db.update_project(
        pid,
        body_image_state="done",
        body_image_progress=100,
        body_image_error="",
        body_image_phase="done",
        body_image_last_log="Z-Image Turbo generation complete.",
        body_image_job_id="",
        body_image_started_at="",
        body_image_heartbeat_at="",
    )


def main() -> int:
    db.init_db()
    with single_instance_lock(WORKER_LOCK_PATH) as acquired:
        if not acquired:
            return 0
        _mark_stale_jobs_disabled()
        while True:
            pid = db.claim_next_queued_body_image()
            if pid is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            _process_project(pid)
