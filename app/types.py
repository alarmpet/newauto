from typing import Literal

from typing_extensions import NotRequired, TypedDict

TaskState = Literal["idle", "queued", "running", "done", "error"]
AutopilotState = Literal["idle", "queued", "running", "paused", "done", "error", "canceled"]
MediaKind = Literal["image", "video"]
PrivacyValue = Literal["private", "unlisted", "public"]
RenderFormat = Literal["landscape", "shorts"]
ContentMode = Literal["standard", "bible_longform"]
VisualSourceMode = Literal["upload_only", "hybrid", "comfyui_auto", "flow_assisted", "flow_auto", "flow_then_comfyui_fallback"]
VisualBriefMode = Literal["literal_scene", "keyword_image", "symbolic_metaphor"]
Region = Literal["intro", "body", "bible"]
SourceDraftInputMode = Literal["", "url", "keyword"]
SourceRegenerateMode = Literal["", "hook", "point", "story", "lesson"]
AutopilotInputMode = Literal["script", "url", "keyword"]
AutopilotImageCount = int | Literal["auto"]
QualityMode = Literal["fast", "balanced", "exhaustive"]
SubtitlePosition = Literal["top", "upper", "middle", "lower", "bottom"]
SubtitleEffect = Literal["none", "fade", "pop", "karaoke"]
SubtitleCueSplitMode = Literal["off", "sentence", "readable"]
TtsMode = Literal["auto", "design", "clone"]
TtsSeedMode = Literal["fixed", "per_sentence"]
TtsSynthesisMode = Literal["sentence", "full_passage"]
VoicePresetArg = str | float | int | bool
VoiceRuntimeDType = Literal["float16", "float32"]
ToolAvailability = Literal["available", "unavailable"]
VisualRelevanceState = Literal["pass", "stale", "missing"]
VisualPlanSubjectMode = Literal["person", "environment", "object_metaphor", "symbolic"]
VisualPriority = Literal["literal_simile", "core_metaphor", "concrete_action", "object_symbol"]
VisualIntent = Literal["literal", "metaphor", "diagram", "character_scene"]
VisualSceneMode = Literal["editorial_scene", "symbolic_concept", "simple_explainer", "data_diagram"]
SemanticAnchorType = Literal[
    "institutional_decision",
    "technical_barrier",
    "investment_signal",
    "market_structure",
    "comparison_frame",
    "future_outlook",
    "generic",
]


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
    cue_split_mode: NotRequired[SubtitleCueSplitMode]
    max_cue_sec: NotRequired[float]
    max_lines: NotRequired[int]
    effect: SubtitleEffect


class TtsProfile(TypedDict):
    mode: TtsMode
    synthesis_mode: NotRequired[TtsSynthesisMode]
    seed_mode: TtsSeedMode
    language: str
    instruct: str
    speed: float
    duration: float | None
    num_step: int
    guidance_scale: float
    denoise: bool
    postprocess_output: bool
    seed: int | None


class RegionalSentence(TypedDict):
    idx: int
    text: str
    region: Region


class SelectedVerse(TypedDict):
    reference: str
    text: str


class BodyImageMapping(TypedDict):
    sentence_idx: int
    path: str
    prompt: str
    sentence_text: NotRequired[str]
    sentence_hash: NotRequired[str]
    project_id: NotRequired[str]
    prompt_id: NotRequired[str]
    manifest_sentence_hash: NotRequired[str]
    selected_reason: NotRequired[str]
    candidate_index: NotRequired[int]
    candidate_total: NotRequired[int]
    candidate_score: NotRequired[float]
    candidate_score_version: NotRequired[str]
    vision_qa_issue_codes: NotRequired[list[str]]


class SdxlDualPrompt(TypedDict):
    prompt_g: str
    prompt_l: str
    combined: str


class ControlNetDecision(TypedDict):
    enabled: bool
    type: str
    strength: float
    start_percent: float
    end_percent: float


class LoraDecision(TypedDict):
    enabled: bool
    name: str
    strength: float


class PromptRepairDecision(TypedDict):
    should_retry: bool
    attempt: int
    issue_codes: list[str]
    repaired_positive_prompt: str
    repaired_prompt_g: str
    repaired_prompt_l: str
    repaired_negative_prompt: str
    repair_reason: str


class VisualBrief(TypedDict):
    mode: VisualBriefMode
    main_subject: str
    action: str
    primary_prop: str
    secondary_prop: str
    scene: str
    emotion: str
    must_show: list[str]
    avoid: list[str]
    rationale: str
    domain: NotRequired[str]
    core_meaning: NotRequired[str]
    primary_keywords: NotRequired[list[str]]
    secondary_keywords: NotRequired[list[str]]
    subject_modes: NotRequired[list[VisualPlanSubjectMode]]
    prompt_hint: NotRequired[str]
    may_show: NotRequired[list[str]]
    vocab_refs: NotRequired[list[str]]
    visual_priority: NotRequired[VisualPriority]
    literal_simile: NotRequired[str]
    allow_objects: NotRequired[list[str]]
    visual_intent: NotRequired[VisualIntent]
    layout: NotRequired[str]
    scene_anchor: NotRequired[str]
    hero_subject: NotRequired[str]
    symbolic_marker: NotRequired[str]
    prompt_g: NotRequired[str]
    prompt_l: NotRequired[str]
    style_mode: NotRequired[str]
    qa_expectations: NotRequired[list[str]]
    controlnet: NotRequired[ControlNetDecision]
    lora: NotRequired[LoraDecision]
    composition_template: NotRequired[str]
    visual_mode: NotRequired[VisualSceneMode]
    semantic_anchor_type: NotRequired[SemanticAnchorType]
    semantic_anchor_tokens: NotRequired[list[str]]
    sub_strategy: NotRequired[str]
    template_hint: NotRequired[str]
    lora_policy: NotRequired[str]


class VisualPlanEntry(TypedDict):
    sentence_idx: int
    sentence: str
    core_meaning: str
    primary_keywords: list[str]
    secondary_keywords: list[str]
    visual_metaphor: str
    subject_modes: list[VisualPlanSubjectMode]
    must_show: list[str]
    may_show: list[str]
    avoid: list[str]
    prompt_hint: str
    vocab_refs: list[str]
    domain: str
    source: str
    visual_priority: NotRequired[VisualPriority]
    literal_simile: NotRequired[str]
    allow_objects: NotRequired[list[str]]
    composition_template: NotRequired[str]
    scene_anchor: NotRequired[str]
    hero_subject: NotRequired[str]
    symbolic_marker: NotRequired[str]
    visual_mode: NotRequired[VisualSceneMode]
    semantic_anchor_type: NotRequired[SemanticAnchorType]
    semantic_anchor_tokens: NotRequired[list[str]]


class VisualRelevanceRow(TypedDict):
    sentence_idx: int
    sentence_text: str
    status: VisualRelevanceState
    path: str
    reason: str
    issue_codes: list[str]


class VisualRelevanceSummary(TypedDict):
    total: int
    pass_count: int
    stale_count: int
    missing_count: int


class SourceDraftSource(TypedDict):
    id: str
    url: str
    final_url: str
    title: str
    domain: str
    author: str
    published_at: str
    language: str
    excerpt: str
    fetched_at: str
    word_count: int


class SourceDraftFactNote(TypedDict):
    source_id: str
    note: str


class AutopilotOptions(TypedDict):
    input_mode: AutopilotInputMode
    script: str
    url: str
    keyword: str
    tone: str
    target_minutes: str
    regenerate_mode: SourceRegenerateMode
    visual_source_mode: VisualSourceMode
    image_count: AutopilotImageCount
    quality_mode: NotRequired[QualityMode]
    render_after_preflight: bool
    debug_verbose: bool


class AutopilotEvent(TypedDict):
    ts: str
    job_id: str
    phase: str
    level: str
    event: str
    message: str
    progress: int
    worker_state: str
    related_state: dict[str, str]
    debug: dict[str, object]


class AutopilotFailureSnapshot(TypedDict):
    ts: str
    job_id: str
    phase: str
    error_code: str
    message: str
    action_hint: str
    recoverable: bool
    project_state: dict[str, str]


class AutopilotDebugSnapshot(TypedDict):
    project_id: str
    state: AutopilotState
    phase: str
    progress: int
    last_log: str
    error: str
    error_code: str
    debug_summary: str
    job_id: str
    started_at: str
    heartbeat_at: str
    wait_started_at: str
    retry_count: int
    options: AutopilotOptions | dict[str, object]
    current_owner: str
    last_failure: AutopilotFailureSnapshot | None
    recent_events: list[AutopilotEvent]


class RenderPlanSegmentMedia(TypedDict):
    path: str
    kind: MediaKind


class ScenePlanScene(TypedDict):
    idx: int
    sentence_idx: int
    text: str
    region: Region
    duration_sec: float
    visual_intent: str
    prompt: str
    style: str
    media_path: str
    key_concept: NotRequired[str]
    visual_metaphor: NotRequired[str]
    subject: NotRequired[str]
    props: NotRequired[list[str]]
    background: NotRequired[str]
    avoid: NotRequired[list[str]]
    core_meaning: NotRequired[str]
    primary_keywords: NotRequired[list[str]]
    secondary_keywords: NotRequired[list[str]]
    subject_modes: NotRequired[list[VisualPlanSubjectMode]]
    must_show: NotRequired[list[str]]
    may_show: NotRequired[list[str]]
    prompt_hint: NotRequired[str]
    vocab_refs: NotRequired[list[str]]
    domain: NotRequired[str]
    locked: NotRequired[bool]
    subtitle_override: NotRequired[SubtitleStyle | None]


class ScenePlan(TypedDict):
    version: int
    format: RenderFormat
    total_duration: float
    scenes: list[ScenePlanScene]


class RenderPlanSegment(TypedDict):
    region: Region
    start: float
    end: float
    media: list[RenderPlanSegmentMedia]
    sentence_idx: NotRequired[int]
    motion: str
    effect: str
    caption_style: str


class RenderPlan(TypedDict):
    version: int
    total_duration: float
    segments: list[RenderPlanSegment]


class ProjectRecord(TypedDict):
    id: str
    title: str
    script: str
    content_mode: ContentMode
    visual_source_mode: VisualSourceMode
    user_script: str
    compiled_script: str
    regional_sentences: list[RegionalSentence]
    bible_query: str
    selected_verses: list[SelectedVerse]
    bible_background_file: str
    body_image_state: TaskState
    body_image_progress: int
    body_image_error: str
    body_image_mappings: list[BodyImageMapping]
    body_image_job_id: str
    body_image_started_at: str
    body_image_heartbeat_at: str
    body_image_phase: str
    body_image_last_log: str
    body_image_options: dict[str, object]
    source_draft_state: TaskState
    source_draft_progress: int
    source_draft_error: str
    source_draft_input_mode: SourceDraftInputMode
    source_draft_query: str
    source_draft_sources: list[SourceDraftSource]
    source_draft_fact_notes: list[SourceDraftFactNote]
    source_draft_script: str
    source_draft_previous_script: str
    source_draft_warnings: list[str]
    source_draft_model: str
    source_draft_risk_score: float
    source_draft_regenerate_mode: SourceRegenerateMode
    source_draft_regenerate_note: str
    source_draft_job_id: str
    source_draft_started_at: str
    source_draft_heartbeat_at: str
    source_draft_phase: str
    source_draft_last_log: str
    source_draft_options: dict[str, object]
    autopilot_state: AutopilotState
    autopilot_progress: int
    autopilot_phase: str
    autopilot_last_log: str
    autopilot_error: str
    autopilot_job_id: str
    autopilot_started_at: str
    autopilot_heartbeat_at: str
    autopilot_options: AutopilotOptions | dict[str, object]
    autopilot_last_error_code: str
    autopilot_debug_summary: str
    autopilot_wait_started_at: str
    autopilot_retry_count: int
    scene_plan: ScenePlan | None
    render_plan: RenderPlan | None
    sentences: list[str]
    media_order: list[str]
    thumbnail_file: str
    subtitle_style: SubtitleStyle
    voice_preset: str
    tts_profile: TtsProfile
    kenburns_enabled: bool
    bgm_file: str
    bgm_volume_db: int
    bgm_ducking_enabled: bool
    render_formats: list[RenderFormat]
    youtube_schedule_at: str
    tts_state: TaskState
    tts_progress: int
    tts_error: str
    tts_job_id: str
    tts_started_at: str
    tts_heartbeat_at: str
    render_state: TaskState
    render_progress: int
    render_phase: str
    render_phase_pct: int
    render_progress_detail: str
    render_speed_x: float
    render_eta_sec: int
    render_job_id: str
    render_started_at: str
    render_heartbeat_at: str
    render_last_log: str
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
    visual_relevance_rows: NotRequired[list[VisualRelevanceRow]]
    visual_relevance_summary: NotRequired[VisualRelevanceSummary]


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
    tts_error: str
    tts_job_id: str
    tts_started_at: str
    tts_heartbeat_at: str
    body_image_state: TaskState
    body_image_progress: int
    body_image_phase: str
    body_image_last_log: str
    body_image_started_at: str
    body_image_heartbeat_at: str
    body_image_error: str
    source_draft_state: TaskState
    source_draft_progress: int
    source_draft_phase: str
    source_draft_last_log: str
    source_draft_started_at: str
    source_draft_heartbeat_at: str
    source_draft_error: str
    autopilot_state: AutopilotState
    autopilot_progress: int
    autopilot_phase: str
    autopilot_last_log: str
    autopilot_error: str
    autopilot_job_id: str
    autopilot_started_at: str
    autopilot_heartbeat_at: str
    autopilot_last_error_code: str
    autopilot_debug_summary: str
    autopilot_wait_started_at: str
    autopilot_retry_count: int
    scene_plan: ScenePlan | None
    render_state: TaskState
    render_progress: int
    render_phase: str
    render_phase_pct: int
    render_progress_detail: str
    render_speed_x: float
    render_eta_sec: int
    render_job_id: str
    render_started_at: str
    render_heartbeat_at: str
    render_last_log: str
    upload_state: TaskState
    upload_progress: int
    media_upload_state: TaskState
    media_upload_progress: int
    media_upload_completed: int
    media_upload_total: int
    media_upload_error: str
    thumbnail_file: str
    subtitle_style: SubtitleStyle
    kenburns_enabled: bool
    bgm_file: str
    bgm_volume_db: int
    bgm_ducking_enabled: bool
    render_formats: list[RenderFormat]
    youtube_schedule_at: str
    youtube_id: str | None
    visual_relevance_rows: NotRequired[list[VisualRelevanceRow]]
    visual_relevance_summary: NotRequired[VisualRelevanceSummary]


class OAuthStatus(TypedDict):
    client_secret_present: bool
    authorized: bool


class TimingEntry(TypedDict):
    idx: int
    text: str
    start: float
    end: float
    dur: float
    region: NotRequired[Region]
    source_idx: NotRequired[int]


class WordTimingEntry(TypedDict):
    cue_idx: int
    word: str
    start: float
    end: float


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


class ProjectFeatureSettingsResponse(TypedDict):
    project: ProjectRecord


class ProjectCloneResponse(TypedDict):
    project: ProjectRecord
    source_project_id: str


class BgmUploadResponse(TypedDict):
    project: ProjectRecord
    bgm_url: str


class TtsRuntimeInfo(TypedDict):
    device: str
    dtype: VoiceRuntimeDType


class TtsPreviewResponse(TypedDict):
    preview_url: str
    sample_text: str
    voice_preset: str
    tts_profile: TtsProfile
    preview_lock: "TtsPreviewLock"


class TtsPreviewLock(TypedDict):
    voice_preset: str
    tts_profile: TtsProfile
    signature: str


class TtsSentenceManifestEntry(TypedDict):
    idx: int
    text: str
    region: NotRequired[Region]
    voice_preset: str
    effective_profile: TtsProfile
    kwargs: dict[str, VoicePresetArg]
    seed: int


class TtsRunManifest(TypedDict):
    generated_at: str
    voice_preset: str
    tts_profile: TtsProfile
    sentences: list[TtsSentenceManifestEntry]


class TtsPresetCatalogResponse(TypedDict):
    order: list[str]
    labels: dict[str, str]
    aliases: dict[str, str]
    presets: dict[str, TtsProfile]
    sample_text: str


class PreflightCheck(TypedDict):
    key: str
    ok: bool
    message: str


class PreflightReport(TypedDict):
    ok: bool
    checks: list[PreflightCheck]


class RenderReportOutput(TypedDict):
    format: RenderFormat
    path: str
    exists: bool
    size_bytes: int
    duration_sec: float
    audio_codec: NotRequired[str]
    audio_sample_rate: NotRequired[int]
    audio_channels: NotRequired[int]
    audio_bitrate: NotRequired[int]
    audio_profile_ok: NotRequired[bool]
    audio_mean_volume_db: NotRequired[float]
    audio_max_volume_db: NotRequired[float]
    audio_audibility_ok: NotRequired[bool]
    hyperframes_overlay_status: NotRequired[str]
    hyperframes_overlay_path: NotRequired[str]
    hyperframes_overlay_report_path: NotRequired[str]
    hyperframes_overlay_pix_fmt: NotRequired[str]


class RenderReportSegment(TypedDict):
    region: Region
    start: float
    end: float
    sentence_idx: NotRequired[int]
    media_path: str
    media_missing: bool
    motion: str
    effect: str
    caption_style: str
    frame_count: NotRequired[int]
    target_frame_count: NotRequired[int]
    frame_duration_sec: NotRequired[float]
    drift_frames: NotRequired[int]


class FinalSceneReviewEntry(TypedDict):
    sentence_idx: int
    sentence: str
    selected_image: str
    selected_reason: str
    candidate_score: float
    candidate_score_version: str
    selection_reason: str
    repair_attempted: bool
    repair_reason: str
    retry_recommended: bool
    retry_reason: str
    fallback_downgrade_applied: bool
    fallback_downgrade_reason: str
    operator_intervention_required: bool
    operator_intervention_reason: str
    visual_plan_source: str
    visual_mode: str
    scene_anchor: str
    semantic_anchor_type: str
    semantic_anchor_tokens: list[str]
    composition_template: str
    hero_subject: str
    vision_qa_issue_codes: list[str]


class FinalSceneReview(TypedDict):
    project_id: str
    title: str
    created_at: str
    total_sentences: int
    fallback_scene_plan_count: int
    retry_recommended_count: int
    entries: list[FinalSceneReviewEntry]


class RenderReport(TypedDict):
    project_id: str
    title: str
    status: str
    created_at: str
    autopilot_job_id: str
    autopilot_input_mode: str
    autopilot_state: AutopilotState
    autopilot_phase: str
    render_started_at: str
    render_finished_at: str
    audio_duration_sec: float
    audio_raw_duration_sec: float
    audio_normalized_duration_sec: float
    output_duration_sec: float
    duration_drift_sec: float
    duration_guard_passed: bool
    subtitle_cue_count: int
    render_plan_segment_count: int
    missing_render_plan_media_count: int
    fallback_used: bool
    outputs: list[RenderReportOutput]
    segments: list[RenderReportSegment]
    final_scene_review_path: str
    final_scene_review_exists: bool
    ffmpeg_log_tail: str
    error: str


class SystemHealth(TypedDict):
    ffmpeg_available: bool
    oauth_ready: bool
    llm_provider: str
    llm_model: str
    llm_base_url: str
    llm_ready: bool
    lmstudio_loaded_models: list[str]
    omnivoice_python_found: bool
    omnivoice_python_path: str
    omnivoice_import_ok: bool
    omnivoice_torch_ok: bool
    omnivoice_cuda_available: bool
    hyperframes_node_available: bool
    hyperframes_node_version: str
    hyperframes_npx_available: bool
    hyperframes_npx_version: str
    hyperframes_doctor_ok: bool
    hyperframes_doctor_detail: str
    hyperframes_ffmpeg_alpha_ok: bool
    disk_free_gb: float
    storage_path: str


class ToolStatus(TypedDict):
    key: str
    label: str
    availability: ToolAvailability
    configured: bool
    version: str
    detail: str
    install_path: str


class ModelStatus(TypedDict):
    key: str
    label: str
    available: bool
    source: str
    path: str
    detail: str


class UsageRecord(TypedDict):
    provider: str
    day_count: int
    month_count: int
    day_limit: int | None
    month_limit: int | None
    last_day_reset: str
    last_month_reset: str


class GpuStatus(TypedDict):
    locked: bool
    owner: str
    resource: str
    expires_at: str
    owner_pid: int
    owner_project_id: str
    owner_job_type: str
    stale: bool


class OperatorQueueStatus(TypedDict):
    source_draft_queued: int
    source_draft_running: int
    autopilot_queued: int
    autopilot_running: int
    autopilot_paused: int
    render_queued: int
    render_running: int
    tts_queued: int
    tts_running: int


class OperatorAutopilotMetrics(TypedDict):
    total: int
    done: int
    paused: int
    error: int
    running: int
    queued: int


class AutopilotRunSummary(TypedDict):
    project_id: str
    title: str
    state: AutopilotState
    phase: str
    progress: int
    updated_at: str
    started_at: str
    job_id: str
    last_error_code: str


class OperatorStatus(TypedDict):
    health: SystemHealth
    tools: list[ToolStatus]
    models: list[ModelStatus]
    usage: list[UsageRecord]
    gpu: GpuStatus
    queue: OperatorQueueStatus
    render_metrics: dict[str, int]
    autopilot_metrics: OperatorAutopilotMetrics
    recent_autopilot_runs: list[AutopilotRunSummary]


class YouTubeStats(TypedDict):
    view_count: int
    like_count: int
    comment_count: int
    video_id: str


class StockSearchItem(TypedDict):
    provider: str
    title: str
    media_url: str
    thumbnail_url: str
    attribution_url: str


class StockSearchResponse(TypedDict):
    query: str
    results: list[StockSearchItem]


class VoiceSampleEntry(TypedDict):
    preset_id: str
    label: str
    output_file: str
    kwargs: dict[str, VoicePresetArg]


class VoiceSampleManifest(TypedDict):
    generated_at: str
    sample_text: str
    samples: list[VoiceSampleEntry]
