from fastapi import APIRouter, BackgroundTasks, Form, HTTPException

from .. import db
from ..services import yt_upload
from ..types import OAuthStatus, PrivacyValue, ProjectRecord, YouTubeStats

router = APIRouter(prefix="/api/projects", tags=["youtube"])


def _require(pid: str) -> ProjectRecord:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


@router.get("/_/oauth/status")
def oauth_status() -> OAuthStatus:
    return yt_upload.oauth_status()


@router.post("/_/oauth/authorize")
def oauth_authorize() -> dict[str, bool]:
    try:
        yt_upload.run_oauth_flow()
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"OAuth failed: {exc}") from exc
    return {"ok": True}


@router.post("/{pid}/upload")
def start_upload(
    pid: str,
    bg: BackgroundTasks,
    title: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    privacy: PrivacyValue = Form("private"),
    schedule_at: str = Form(""),
) -> dict[str, bool]:
    project = _require(pid)
    if project["render_state"] != "done":
        raise HTTPException(400, "render the video first")
    if project["upload_state"] == "running":
        raise HTTPException(409, "upload already running")
    if not yt_upload.has_credentials():
        raise HTTPException(400, "YouTube OAuth not completed - click Authorize first")

    db.update_project(
        pid,
        upload_state="running",
        upload_progress=0,
        youtube_id=None,
        youtube_schedule_at=schedule_at,
    )
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    bg.add_task(yt_upload.run_upload_job, pid, title, description, tag_list, privacy, schedule_at)
    return {"ok": True}


@router.get("/{pid}/stats")
def youtube_stats(pid: str) -> YouTubeStats:
    project = _require(pid)
    if not project["youtube_id"]:
        raise HTTPException(400, "project has not been uploaded to YouTube yet")
    try:
        return yt_upload.fetch_video_stats(project["youtube_id"])
    except Exception as exc:
        raise HTTPException(500, f"failed to fetch YouTube stats: {exc}") from exc
