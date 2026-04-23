from typing import Literal

from typing_extensions import TypedDict

TaskState = Literal["idle", "running", "done", "error"]
MediaKind = Literal["image", "video"]
PrivacyValue = Literal["private", "unlisted", "public"]
SubtitlePosition = Literal["top", "upper", "middle", "lower", "bottom"]
SubtitleEffect = Literal["none", "fade", "pop"]
VoicePresetArg = str | float
VoiceRuntimeDType = Literal["float16", "float32"]


class SubtitleStyle(TypedDict):
    font_family: str
    font_size: int
    primary_color: str
    outline_color: str
    background_color: str
    background_opacity: float
    outline_width: int
    shadow: int
    position: SubtitlePosition
    margin_h: int
    margin_v: int
    max_line_chars: int
    min_display_sec: float
    effect: SubtitleEffect


class ProjectRecord(TypedDict):
    id: str
    title: str
    script: str
    sentences: list[str]
    media_order: list[str]
    thumbnail_file: str
    subtitle_style: SubtitleStyle
    voice_preset: str
    tts_state: TaskState
    tts_progress: int
    render_state: TaskState
    render_progress: int
    upload_state: TaskState
    upload_progress: int
    media_upload_state: TaskState
    media_upload_progress: int
    media_upload_completed: int
    media_upload_total: int
    media_upload_error: str
    youtube_id: str | None
    created_at: str
    updated_at: str


class ProjectCard(TypedDict):
    id: str
    title: str
    updated_at: str
    tts_state: TaskState
    render_state: TaskState
    upload_state: TaskState
    youtube_id: str | None


class ProjectStatus(TypedDict):
    id: str
    tts_state: TaskState
    tts_progress: int
    render_state: TaskState
    render_progress: int
    upload_state: TaskState
    upload_progress: int
    media_upload_state: TaskState
    media_upload_progress: int
    media_upload_completed: int
    media_upload_total: int
    media_upload_error: str
    thumbnail_file: str
    subtitle_style: SubtitleStyle
    youtube_id: str | None


class OAuthStatus(TypedDict):
    client_secret_present: bool
    authorized: bool


class TimingEntry(TypedDict):
    idx: int
    text: str
    start: float
    end: float
    dur: float


class AcceptedUploadFile(TypedDict):
    original_name: str
    saved_name: str
    kind: MediaKind


class SkippedUploadFile(TypedDict):
    name: str
    reason: str


class MediaUploadResponse(TypedDict):
    project: ProjectRecord
    accepted_files: list[AcceptedUploadFile]
    skipped_files: list[SkippedUploadFile]


class ThumbnailUploadResponse(TypedDict):
    project: ProjectRecord
    thumbnail_url: str


class SubtitleStyleResponse(TypedDict):
    project: ProjectRecord
    effective_style: SubtitleStyle


class TtsRuntimeInfo(TypedDict):
    device: str
    dtype: VoiceRuntimeDType


class VoiceSampleEntry(TypedDict):
    preset_id: str
    label: str
    output_file: str
    kwargs: dict[str, VoicePresetArg]


class VoiceSampleManifest(TypedDict):
    generated_at: str
    sample_text: str
    samples: list[VoiceSampleEntry]
