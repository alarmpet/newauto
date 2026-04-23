import traceback
from typing import cast

from .. import db
from ..config import CLIENT_SECRET_PATH, TOKEN_PATH
from ..types import OAuthStatus, PrivacyValue, YouTubeStats

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _load_creds() -> object | None:
    from google.auth.transport.requests import Request  # noqa: WPS433
    from google.oauth2.credentials import Credentials  # noqa: WPS433

    if not TOKEN_PATH.exists():
        return None
    credentials = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")
    return cast(object, credentials)


def has_credentials() -> bool:
    try:
        credentials = _load_creds()
        return bool(credentials and cast(bool, getattr(credentials, "valid", False)))
    except Exception:
        return False


def oauth_status() -> OAuthStatus:
    return {
        "client_secret_present": CLIENT_SECRET_PATH.exists(),
        "authorized": has_credentials(),
    }


def run_oauth_flow() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: WPS433

    if not CLIENT_SECRET_PATH.exists():
        raise FileNotFoundError(
            f"Place your OAuth client_secret.json at {CLIENT_SECRET_PATH}"
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
    credentials = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")


def run_upload_job(
    pid: str,
    title: str,
    description: str,
    tags: list[str],
    privacy: PrivacyValue,
    schedule_at: str = "",
) -> None:
    try:
        from googleapiclient.discovery import build  # noqa: WPS433
        from googleapiclient.http import MediaFileUpload  # noqa: WPS433

        credentials = _load_creds()
        if not credentials or not cast(bool, getattr(credentials, "valid", False)):
            raise RuntimeError("YouTube credentials invalid - re-authorize")

        video_path = db.project_dir(pid) / "output.mp4"
        if not video_path.exists():
            raise RuntimeError("output.mp4 not found - render first")

        youtube = build("youtube", "v3", credentials=credentials)
        status_payload: dict[str, object] = {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        }
        body: dict[str, object] = {
            "snippet": {"title": title, "description": description, "tags": tags},
            "status": status_payload,
        }
        if schedule_at:
            status_payload["publishAt"] = schedule_at
        media = MediaFileUpload(str(video_path), chunksize=1024 * 1024, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                db.update_project(pid, upload_progress=int(status.progress() * 100))

        video_id = str(response.get("id") or "")
        if not video_id:
            raise RuntimeError("YouTube upload response did not include a video id")

        project = db.get_project(pid)
        if project is not None and project["thumbnail_file"]:
            thumbnail_path = db.project_dir(pid) / "thumbnail" / project["thumbnail_file"]
            if thumbnail_path.exists():
                try:
                    thumbnail_media = MediaFileUpload(str(thumbnail_path))
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=thumbnail_media,
                    ).execute()
                except Exception:
                    traceback.print_exc()

        db.update_project(pid, upload_state="done", upload_progress=100, youtube_id=video_id)
    except Exception:
        traceback.print_exc()
        db.update_project(pid, upload_state="error")


def fetch_video_stats(video_id: str) -> YouTubeStats:
    from googleapiclient.discovery import build  # noqa: WPS433

    credentials = _load_creds()
    if not credentials or not cast(bool, getattr(credentials, "valid", False)):
        raise RuntimeError("YouTube credentials invalid - re-authorize")
    youtube = build("youtube", "v3", credentials=credentials)
    response = youtube.videos().list(part="statistics", id=video_id).execute()
    items = response.get("items") or []
    if not items:
        raise RuntimeError("video statistics not found")
    statistics = items[0].get("statistics") or {}
    return {
        "video_id": video_id,
        "view_count": int(statistics.get("viewCount", 0)),
        "like_count": int(statistics.get("likeCount", 0)),
        "comment_count": int(statistics.get("commentCount", 0)),
    }
