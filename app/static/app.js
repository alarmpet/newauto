// @ts-check

/**
 * @typedef {"idle" | "queued" | "running" | "done" | "error"} TaskState
 * @typedef {"idle" | "queued" | "running" | "paused" | "done" | "error" | "canceled"} AutopilotState
 * @typedef {"image" | "video"} MediaKind
 * @typedef {"idle" | "uploading" | "processing" | "done" | "error"} MediaClientPhase
 * @typedef {"top" | "upper" | "middle" | "lower" | "bottom"} SubtitlePosition
 * @typedef {"none" | "fade" | "pop" | "karaoke"} SubtitleEffect
 * @typedef {"auto" | "design" | "clone"} TtsMode
 * @typedef {"landscape" | "shorts"} RenderFormat
 * @typedef {"standard" | "bible_longform"} ContentMode
 * @typedef {"upload_only" | "hybrid" | "comfyui_auto" | "flow_assisted" | "flow_auto" | "flow_then_comfyui_fallback"} VisualSourceMode
 * @typedef {"intro" | "body" | "bible"} Region
 * @typedef {"" | "url" | "keyword"} SourceDraftInputMode
 * @typedef {"" | "hook" | "point" | "story" | "lesson"} SourceRegenerateMode
 * @typedef {"script" | "url" | "keyword"} AutopilotInputMode
 * @typedef {"pass" | "stale" | "missing"} VisualRelevanceState
 */

/**
 * @typedef {{
 *   sentence_idx: number,
 *   sentence_hash: string,
 *   section: string,
 *   narration: string,
 *   core_keyword: string,
 *   visual_keyword: string,
 *   emotion: string,
 *   aspect_ratio: string,
 *   prompt: string,
 *   negative_prompt: string,
 *   asset_path: string,
 *   status: string,
 *   updated_at: string,
 *   source: string,
 * }} FlowPromptEntry
 */

/**
 * @typedef {{
 *   version: number,
 *   project_id: string,
 *   generated_at: string,
 *   aspect_ratio: string,
 *   mode: string,
 *   entries: FlowPromptEntry[],
 *   flow_project_url?: string,
 * }} FlowPromptManifest
 */

/**
 * @typedef {{
 *   font_family: string,
 *   font_size: number,
 *   primary_color: string,
 *   outline_color: string,
 *   background_color: string,
 *   background_opacity: number,
 *   outline_width: number,
 *   shadow: number,
 *   position: SubtitlePosition,
 *   margin_h: number,
 *   margin_v: number,
 *   max_line_chars: number,
 *   min_display_sec: number,
 *   effect: SubtitleEffect,
 * }} SubtitleStyle
 */

/**
 * @typedef {{
 *   mode: TtsMode,
 *   seed_mode: "fixed" | "per_sentence",
 *   language: string,
 *   instruct: string,
 *   speed: number,
 *   duration: number | null,
 *   num_step: number,
 *   guidance_scale: number,
 *   denoise: boolean,
 *   postprocess_output: boolean,
 *   seed: number | null,
 * }} TtsProfile
 */

/**
 * @typedef {{
 *   idx: number,
 *   text: string,
 *   region: Region,
 * }} RegionalSentence
 */

/**
 * @typedef {{
 *   id: string,
 *   url: string,
 *   final_url: string,
 *   title: string,
 *   domain: string,
 *   author: string,
 *   published_at: string,
 *   language: string,
 *   excerpt: string,
 *   fetched_at: string,
 *   word_count: number,
 * }} SourceDraftSource
 */

/**
 * @typedef {{
 *   source_id: string,
 *   note: string,
 * }} SourceDraftFactNote
 */

/**
 * @typedef {{
 *   input_mode: AutopilotInputMode,
 *   script: string,
 *   url: string,
 *   keyword: string,
 *   tone: string,
 *   target_minutes: string,
 *   regenerate_mode: SourceRegenerateMode,
 *   visual_source_mode: VisualSourceMode,
 *   image_count: number | "auto",
 *   render_after_preflight: boolean,
 *   debug_verbose: boolean,
 * }} AutopilotOptions
 */

/**
 * @typedef {{
 *   ts: string,
 *   job_id: string,
 *   phase: string,
 *   level: string,
 *   event: string,
 *   message: string,
 *   progress: number,
 *   worker_state: string,
 *   related_state: Record<string, string>,
 *   debug: Record<string, unknown>,
 * }} AutopilotEvent
 */

/**
 * @typedef {{
 *   ts: string,
 *   job_id: string,
 *   phase: string,
 *   error_code: string,
 *   message: string,
 *   action_hint: string,
 *   recoverable: boolean,
 *   project_state: Record<string, string>,
 * }} AutopilotFailureSnapshot
 */

/**
 * @typedef {{
 *   project_id: string,
 *   state: AutopilotState,
 *   phase: string,
 *   progress: number,
 *   last_log: string,
 *   error: string,
 *   error_code: string,
 *   debug_summary: string,
 *   job_id: string,
 *   started_at: string,
 *   heartbeat_at: string,
 *   wait_started_at: string,
 *   retry_count: number,
 *   options: AutopilotOptions | Object,
 *   current_owner: string,
 *   last_failure: AutopilotFailureSnapshot | null,
 *   recent_events: AutopilotEvent[],
 * }} AutopilotDebugSnapshot
 */

/**
 * @typedef {{
 *   sentence_idx: number,
 *   sentence_text: string,
 *   status: VisualRelevanceState,
 *   path: string,
 *   reason: string,
 *   issue_codes: string[],
 * }} VisualRelevanceRow
 */

/**
 * @typedef {{
 *   total: number,
 *   pass_count: number,
 *   stale_count: number,
 *   missing_count: number,
 * }} VisualRelevanceSummary
 */

/**
 * @typedef {{
 *   idx: number,
 *   sentence_idx: number,
 *   text: string,
 *   region: Region,
 *   duration_sec: number,
 *   visual_intent: string,
 *   prompt: string,
 *   style: string,
 *   media_path: string,
 * }} ScenePlanScene
 */

/**
 * @typedef {{
 *   version: number,
 *   format: RenderFormat,
 *   total_duration: number,
 *   scenes: ScenePlanScene[],
 * }} ScenePlan
 */

/**
 * @typedef {{
 *   region: Region,
 *   start: number,
 *   end: number,
  *   media: { path: string, kind: MediaKind }[],
 *   motion: string,
 *   effect: string,
 *   caption_style: string,
 * }} RenderPlanSegment
 */

/**
 * @typedef {{
 *   version: number,
 *   total_duration: number,
 *   segments: RenderPlanSegment[],
 * }} RenderPlan
 */

/**
 * @typedef {{
 *   idx: number,
 *   scene_id: string,
 *   sentence_idx: number,
 *   text: string,
 *   region: Region,
 *   duration_sec: number,
 *   voice_asset_path: string,
 *   visual_asset_path: string,
 *   prompt: string,
 *   subtitle_override: SubtitleStyle | null,
 *   motion: string,
 *   flow_status: string,
 *   locked: boolean,
 *   warnings: string[],
 * }} SceneCard
 */

/**
 * @typedef {{
 *   reference: string,
 *   text: string,
 * }} SelectedVerse
 */

/**
 * @typedef {{
 *   id: string,
 *   title: string,
 *   script: string,
 *   content_mode: ContentMode,
 *   visual_source_mode: VisualSourceMode,
 *   user_script: string,
 *   compiled_script: string,
 *   regional_sentences: RegionalSentence[],
 *   bible_query: string,
 *   selected_verses: SelectedVerse[],
 *   bible_background_file: string,
 *   body_image_state: TaskState,
 *   body_image_progress: number,
 *   body_image_error: string,
 *   body_image_phase: string,
 *   body_image_last_log: string,
 *   body_image_started_at: string,
 *   body_image_heartbeat_at: string,
 *   body_image_options: Object,
 *   body_image_mappings: {sentence_idx: number, path: string, prompt: string, selected_reason?: string, candidate_index?: number, candidate_total?: number, candidate_score?: number}[],
 *   visual_relevance_rows?: VisualRelevanceRow[],
 *   visual_relevance_summary?: VisualRelevanceSummary,
 *   source_draft_state: TaskState,
 *   source_draft_progress: number,
 *   source_draft_error: string,
 *   source_draft_input_mode: SourceDraftInputMode,
 *   source_draft_query: string,
 *   source_draft_sources: SourceDraftSource[],
 *   source_draft_fact_notes: SourceDraftFactNote[],
 *   source_draft_script: string,
 *   source_draft_previous_script: string,
 *   source_draft_warnings: string[],
 *   source_draft_model: string,
 *   source_draft_risk_score: number,
 *   source_draft_regenerate_mode: SourceRegenerateMode,
 *   source_draft_regenerate_note: string,
 *   source_draft_job_id: string,
 *   source_draft_started_at: string,
 *   source_draft_heartbeat_at: string,
 *   source_draft_phase: string,
 *   source_draft_last_log: string,
 *   source_draft_options: Object,
 *   autopilot_state: AutopilotState,
 *   autopilot_progress: number,
 *   autopilot_phase: string,
 *   autopilot_last_log: string,
 *   autopilot_error: string,
 *   autopilot_job_id: string,
 *   autopilot_started_at: string,
 *   autopilot_heartbeat_at: string,
 *   autopilot_options: AutopilotOptions | Object,
 *   autopilot_last_error_code: string,
 *   autopilot_debug_summary: string,
 *   autopilot_wait_started_at: string,
 *   autopilot_retry_count: number,
 *   scene_plan: ScenePlan | null,
 *   render_plan: RenderPlan | null,
 *   sentences: string[],
 *   media_order: string[],
 *   thumbnail_file: string,
 *   subtitle_style: SubtitleStyle,
 *   voice_preset: string,
 *   tts_profile: TtsProfile,
 *   kenburns_enabled: boolean,
 *   bgm_file: string,
 *   bgm_volume_db: number,
 *   bgm_ducking_enabled: boolean,
 *   render_formats: RenderFormat[],
 *   youtube_schedule_at: string,
 *   tts_state: TaskState,
 *   tts_progress: number,
 *   render_state: TaskState,
 *   render_progress: number,
 *   render_phase: string,
 *   render_phase_pct: number,
 *   render_progress_detail: string,
 *   render_speed_x: number,
 *   render_eta_sec: number,
 *   render_job_id: string,
 *   render_started_at: string,
 *   render_heartbeat_at: string,
 *   render_last_log: string,
 *   upload_state: TaskState,
 *   upload_progress: number,
 *   media_upload_state: TaskState,
 *   media_upload_progress: number,
 *   media_upload_completed: number,
 *   media_upload_total: number,
 *   media_upload_error: string,
 *   youtube_id: string | null,
 *   created_at: string,
 *   updated_at: string,
 * }} Project
 */

/**
 * @typedef {{
 *   id: string,
 *   title: string,
 *   updated_at: string,
 *   tts_state: TaskState,
 *   render_state: TaskState,
 *   upload_state: TaskState,
 *   youtube_id: string | null,
 * }} ProjectCard
 */

/**
 * @typedef {{
 *   original_name: string,
 *   saved_name: string,
 *   kind: MediaKind,
 * }} AcceptedUploadFile
 */

/**
 * @typedef {{
 *   name: string,
 *   reason: string,
 * }} SkippedUploadFile
 */

/**
 * @typedef {{
 *   project: Project,
 *   accepted_files: AcceptedUploadFile[],
 *   skipped_files: SkippedUploadFile[],
 * }} MediaUploadResponse
 */

/**
 * @typedef {{
 *   id: string,
 *   tts_state: TaskState,
 *   tts_progress: number,
 *   body_image_state: TaskState,
 *   body_image_progress: number,
 *   body_image_phase: string,
 *   body_image_last_log: string,
 *   body_image_started_at: string,
 *   body_image_heartbeat_at: string,
 *   body_image_error: string,
 *   source_draft_state: TaskState,
 *   source_draft_progress: number,
 *   source_draft_phase: string,
 *   source_draft_last_log: string,
 *   source_draft_started_at: string,
 *   source_draft_heartbeat_at: string,
 *   source_draft_error: string,
 *   autopilot_state: AutopilotState,
 *   autopilot_progress: number,
 *   autopilot_phase: string,
 *   autopilot_last_log: string,
 *   autopilot_error: string,
 *   autopilot_job_id: string,
 *   autopilot_started_at: string,
 *   autopilot_heartbeat_at: string,
 *   autopilot_last_error_code: string,
 *   autopilot_debug_summary: string,
 *   autopilot_wait_started_at: string,
 *   autopilot_retry_count: number,
 *   render_state: TaskState,
 *   render_progress: number,
 *   render_phase: string,
 *   render_phase_pct: number,
 *   render_progress_detail: string,
 *   render_speed_x: number,
 *   render_eta_sec: number,
 *   render_job_id: string,
 *   render_started_at: string,
 *   render_heartbeat_at: string,
 *   render_last_log: string,
 *   upload_state: TaskState,
 *   upload_progress: number,
 *   media_upload_state: TaskState,
 *   media_upload_progress: number,
 *   media_upload_completed: number,
 *   media_upload_total: number,
 *   media_upload_error: string,
 *   thumbnail_file: string,
 *   visual_relevance_rows?: VisualRelevanceRow[],
 *   visual_relevance_summary?: VisualRelevanceSummary,
 *   subtitle_style: SubtitleStyle,
 *   kenburns_enabled: boolean,
 *   bgm_file: string,
 *   bgm_volume_db: number,
 *   bgm_ducking_enabled: boolean,
 *   render_formats: RenderFormat[],
 *   youtube_schedule_at: string,
 *   youtube_id: string | null,
 * }} ProjectStatus
 */

/**
 * @typedef {{
 *   client_secret_present: boolean,
 *   authorized: boolean,
 * }} OAuthStatus
 */

/**
 * @typedef {{
 *   phase: MediaClientPhase,
 *   transferProgress: number,
 *   message: string,
 *   lastAccepted: AcceptedUploadFile[],
 *   lastSkipped: SkippedUploadFile[],
 * }} MediaClientState
 */

/**
 * @typedef {{
 *   project: Project,
 *   thumbnail_url: string,
 * }} ThumbnailUploadResponse
 */

/**
 * @typedef {{
 *   project: Project,
 *   effective_style: SubtitleStyle,
 * }} SubtitleStyleResponse
 */

/**
 * @typedef {{
 *   voice_preset: string,
 *   tts_profile: TtsProfile,
 *   signature: string,
 * }} TtsPreviewLock
 */

/**
 * @typedef {{
 *   preview_url: string,
 *   sample_text: string,
 *   voice_preset: string,
 *   tts_profile: TtsProfile,
 *   preview_lock: TtsPreviewLock,
 * }} TtsPreviewResponse
 */

/**
 * @typedef {{
 *   order: string[],
 *   labels: Record<string, string>,
 *   aliases: Record<string, string>,
 *   presets: Record<string, TtsProfile>,
 *   sample_text: string,
 * }} TtsPresetCatalogResponse
 */

class HttpError extends Error {
  /**
   * @param {string} message
   * @param {number} status
   */
  constructor(message, status) {
    super(message);
    this.name = "HttpError";
    this.status = status;
  }
}

/**
 * @template {Element} T
 * @param {string} selector
 * @param {ParentNode} [root]
 * @returns {T}
 */
function query(selector, root = document) {
  const element = root.querySelector(selector);
  if (!element) {
    throw new Error(`Missing element: ${selector}`);
  }
  return /** @type {T} */ (element);
}

/**
 * @template {Element} T
 * @param {string} selector
 * @param {ParentNode} [root]
 * @returns {T[]}
 */
function queryAll(selector, root = document) {
  return /** @type {T[]} */ (Array.from(root.querySelectorAll(selector)));
}

/**
 * @template T
 * @param {string} url
 * @param {RequestInit} [init]
 * @returns {Promise<T>}
 */
async function requestJson(url, init) {
  const response = await fetch(url, init);
  if (response.ok) {
    return /** @type {Promise<T>} */ (response.json());
  }

  let message = response.statusText || "Request failed";
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await response.json();
    if (payload && typeof payload.detail === "string") {
      message = payload.detail;
    }
  } else {
    const text = await response.text();
    if (text) {
      message = text;
    }
  }

  throw new HttpError(message, response.status);
}

/**
 * @param {Record<string, string>} values
 * @returns {FormData}
 */
function formDataFromObject(values) {
  const formData = new FormData();
  for (const [key, value] of Object.entries(values)) {
    formData.append(key, value);
  }
  return formData;
}

/**
 * @param {string} value
 * @returns {string}
 */
function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => (
    {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char] || char
  ));
}

/**
 * @param {string} label
 * @param {TaskState} state
 * @returns {string}
 */
function chip(label, state) {
  if (state === "idle") {
    return "";
  }
  const extraClass = state === "error" ? " error" : state === "running" ? " running" : "";
  return `<span class="chip${extraClass}">${label} ${state}</span>`;
}

/**
 * @param {string} url
 * @returns {string}
 */
function buildMediaUrl(url) {
  return `${url}?t=${Date.now()}`;
}

/**
 * @param {string} script
 * @returns {number}
 */
function estimateSentenceCount(script) {
  return script
    .split(/(?<=[.!?])\s+|\n+/)
    .map((item) => item.trim())
    .filter(Boolean).length;
}

/**
 * @param {string} region
 * @returns {Region}
 */
function normalizeRegion(region) {
  if (region === "intro" || region === "bible") {
    return region;
  }
  return "body";
}

/**
 * @param {Project} project
 * @returns {RegionalSentence[]}
 */
function effectiveRegionalSentences(project) {
  if (project.regional_sentences.length > 0) {
    return project.regional_sentences;
  }
  return project.sentences.map((text, index) => ({
    idx: index,
    text,
    region: "body",
  }));
}

/**
 * @param {string} name
 * @returns {MediaKind}
 */
function mediaKindFromName(name) {
  return /\.(mp4|mov|webm)$/i.test(name) ? "video" : "image";
}

/**
 * @param {string} value
 * @returns {SubtitlePosition}
 */
function subtitlePositionFromValue(value) {
  if (value === "top" || value === "upper" || value === "middle" || value === "lower" || value === "bottom") {
    return value;
  }
  return "bottom";
}

/**
 * @param {string} value
 * @returns {SubtitleEffect}
 */
function subtitleEffectFromValue(value) {
  if (value === "fade" || value === "pop" || value === "none" || value === "karaoke") {
    return value;
  }
  return "none";
}

/**
 * @param {string} value
 * @param {number} fallback
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
function numberInRange(value, fallback, min, max) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, numericValue));
}

/**
 * @param {Project} project
 * @returns {SubtitleStyle}
 */
function effectiveSubtitleStyle(project) {
  return {
    ...DEFAULT_SUBTITLE_STYLE,
    ...project.subtitle_style,
  };
}

/**
 * @param {Project} project
 * @returns {TtsProfile}
 */
function effectiveTtsProfile(project) {
  return {
    ...DEFAULT_TTS_PROFILE,
    ...project.tts_profile,
  };
}

/**
 * @param {TaskState} state
 * @returns {string}
 */
function readableTaskState(state) {
  switch (state) {
    case "queued":
      return "대기 중";
    case "running":
      return "진행 중";
    case "done":
      return "완료";
    case "error":
      return "오류";
    default:
      return "대기";
  }
}

/**
 * @param {AutopilotState} state
 * @returns {string}
 */
function readableAutopilotState(state) {
  switch (state) {
    case "queued":
      return "대기 중";
    case "running":
      return "진행 중";
    case "paused":
      return "일시정지";
    case "done":
      return "완료";
    case "error":
      return "오류";
    case "canceled":
      return "중단됨";
    default:
      return "대기";
  }
}

/**
 * @param {string} phase
 * @returns {string}
 */
function readableRenderPhase(phase) {
  /** @type {Record<string, string>} */
  const labels = {
    "": "",
    queued: "대기 중",
    validate_media: "미디어 사전 검사",
    prepare_media: "미디어 준비",
    concat_audio: "오디오 합치는 중",
    concat_audio_done: "오디오 결합 완료",
    build_word_timings: "단어 타이밍 생성",
    normalize_audio: "오디오 정규화",
    normalize_audio_done: "오디오 정규화 완료",
    mix_bgm: "BGM 믹싱",
    audio_ready: "오디오 준비 완료",
    write_subtitles: "자막 ASS 생성",
    subtitles_ready: "자막 생성 완료",
    build_visual_landscape: "가로형 영상 구성",
    mux_landscape: "가로형 영상 합성",
    done_landscape: "가로형 출력 완료",
    build_visual_shorts: "쇼츠 영상 구성",
    mux_shorts: "쇼츠 영상 합성",
    done_shorts: "쇼츠 출력 완료",
    done: "렌더 완료",
  };
  return labels[phase] || phase;
}

/**
 * @param {string} phase
 * @returns {string}
 */
function readableImagePhase(phase) {
  /** @type {Record<string, string>} */
  const labels = {
    "": "",
    queued: "대기 중",
    wait_gpu: "GPU 대기",
    submit: "ComfyUI 제출",
    poll_history: "결과 대기",
    import_media: "미디어 가져오기",
    refresh_plans: "플랜 재구성",
    done: "완료",
    done_with_plan_warning: "완료(플랜 경고)",
    done_with_operator_warning: "완료(운영자 확인 필요)",
  };
  return labels[phase] || phase;
}

/**
 * @param {VisualRelevanceState} state
 * @returns {string}
 */
function readableVisualRelevanceState(state) {
  switch (state) {
    case "pass":
      return "PASS";
    case "stale":
      return "STALE";
    case "missing":
      return "MISSING";
    default:
      return state;
  }
}

/**
 * @param {string} renderLog
 * @returns {string}
 */
function readableRenderIssue(renderLog) {
  if (renderLog.includes("Failed to configure output pad on Parsed_concat") || renderLog.includes("Input link in0:v0 parameters")) {
    return "입력 이미지와 영상의 최종 해상도가 서로 달라 하나의 영상으로 합쳐지지 않았습니다.";
  }
  if (renderLog.includes("Invalid data found when processing input")) {
    return "손상되었거나 지원되지 않는 미디어 파일이 포함되어 있습니다.";
  }
  if (renderLog.includes("video stream metadata unavailable")) {
    return "미디어 파일 중 일부에서 영상 크기를 읽지 못했습니다.";
  }
  if (renderLog.includes("No such file or directory")) {
    return "렌더에 필요한 파일을 찾지 못했습니다.";
  }
  return "";
}

/**
 * @param {TaskState} state
 * @param {string} phase
 * @param {string} detail
 * @param {string} renderLog
 * @param {string} heartbeatAt
 * @returns {string}
 */
function formatRenderLog(state, phase, detail, renderLog, heartbeatAt) {
  if (!phase && !detail && !renderLog) {
    return "렌더를 시작하면 현재 단계와 마지막 로그를 여기에서 확인할 수 있습니다.";
  }
  const summary = readableRenderIssue(renderLog);
  const lines = [`Current phase: ${readableRenderPhase(phase)}`];
  if (state === "queued") {
    lines.push("", "세부 진행: 렌더 워커 대기열에 등록되었습니다.");
  } else if (detail) {
    lines.push("", `세부 진행: ${detail}`);
  } else if (phase) {
    lines.push("", "세부 진행 정보를 수집하는 중입니다.");
  }
  if (heartbeatAt) {
    lines.push("", `최근 heartbeat: ${heartbeatAt}`);
  }
  if (summary) {
    lines.push("", `문제 요약: ${summary}`);
  }
  if (renderLog) {
    lines.push("", renderLog);
  }
  return lines.join("\n");
}

/**
 * @returns {Promise<TtsPresetCatalogResponse>}
 */
async function ensureTtsPresetCatalog() {
  if (ttsPresetCatalog) {
    return ttsPresetCatalog;
  }
  ttsPresetCatalog = /** @type {TtsPresetCatalogResponse} */ (await requestJson("/api/tts/presets"));
  return ttsPresetCatalog;
}

/**
 * @param {string} presetId
 * @returns {string}
 */
function canonicalVoicePresetId(presetId) {
  const catalog = ttsPresetCatalog;
  if (!catalog) {
    return presetId;
  }
  return catalog.aliases[presetId] || presetId;
}

/**
 * @param {string} presetId
 * @returns {TtsProfile}
 */
function presetProfile(presetId) {
  const catalog = ttsPresetCatalog;
  const canonicalId = canonicalVoicePresetId(presetId);
  const preset = catalog ? catalog.presets[canonicalId] : null;
  return {
    ...DEFAULT_TTS_PROFILE,
    ...(preset || {}),
  };
}

/**
 * @returns {void}
 */
function populateVoiceSelect() {
  const catalog = ttsPresetCatalog;
  if (!catalog) {
    return;
  }
  const currentValue = voiceSelect.value;
  voiceSelect.innerHTML = "";
  for (const presetId of catalog.order) {
    const option = document.createElement("option");
    option.value = presetId;
    option.textContent = catalog.labels[presetId] || presetId;
    voiceSelect.appendChild(option);
  }
  voiceSelect.value = canonicalVoicePresetId(currentValue) || catalog.order[0] || "auto";
}

/** @type {Project | null} */
let current = null;
/** @type {AutopilotDebugSnapshot | null} */
let autopilotDebugSnapshot = null;
/** @type {number | null} */
let pollTimer = null;
/** @type {number | null} */
let operatorPollTimer = null;
/** @type {string | null} */
let selectedMediaName = null;
/** @type {string | null} */
let draggingMediaName = null;
/** @type {FlowPromptManifest | null} */
let flowPromptManifest = null;
/** @type {SceneCard[]} */
let sceneCards = [];
/** @type {number | null} */
let pendingFlowAssetSentenceIdx = null;
/** @type {Array<Record<string, unknown>>} */
let simplePromptItems = [];
/** @type {MediaClientState} */
let mediaClientState = {
  phase: "idle",
  transferProgress: 0,
  message: "업로드를 시작하면 파일별 진행 상황을 여기에서 확인할 수 있습니다.",
  lastAccepted: [],
  lastSkipped: [],
};

/** @type {SubtitleStyle} */
const DEFAULT_SUBTITLE_STYLE = {
  font_family: "Malgun Gothic",
  font_size: 48,
  primary_color: "#FFFFFF",
  outline_color: "#000000",
  background_color: "#000000",
  background_opacity: 0,
  outline_width: 2,
  shadow: 1,
  position: "bottom",
  margin_h: 120,
  margin_v: 80,
  max_line_chars: 26,
  min_display_sec: 1,
  effect: "none",
};

/** @type {TtsProfile} */
const DEFAULT_TTS_PROFILE = {
  mode: "auto",
  seed_mode: "per_sentence",
  language: "ko",
  instruct: "",
  speed: 1,
  duration: null,
  num_step: 32,
  guidance_scale: 2.6,
  denoise: true,
  postprocess_output: true,
  seed: null,
};

const DEFAULT_TTS_SAMPLE_TEXT = "안녕하세요. 지금 들으시는 음성은 현재 보이스 설정으로 만든 짧은 샘플입니다.";
/** @type {TtsPresetCatalogResponse | null} */
let ttsPresetCatalog = null;
let ttsFormDirtyAfterPreset = false;
/** @type {TtsPreviewLock | null} */
let lastTtsPreviewLock = null;
/** @type {{ promptG: string, promptL: string }} */
let manualPromptOverrides = { promptG: "", promptL: "" };
const PLAY_RES_Y = 1080;
const SUBTITLE_POSITION_CENTER_RATIO = {
  top: 0.12,
  upper: 0.30,
  middle: 0.50,
  lower: 0.78,
  bottom: 0.88,
};

/** @type {Record<string, Partial<SubtitleStyle>>} */
const SUBTITLE_PRESETS = {
  default: { ...DEFAULT_SUBTITLE_STYLE },
  bold: {
    font_size: 64,
    outline_width: 3,
    shadow: 2,
  },
  minimal: {
    primary_color: "#DDDDDD",
    outline_width: 1,
    shadow: 0,
    effect: "none",
  },
  highlight: {
    primary_color: "#FFE066",
    outline_width: 4,
    effect: "pop",
  },
};

const navProjects = /** @type {HTMLButtonElement} */ (query("#nav-projects"));
const workflowNav = /** @type {HTMLElement} */ (query("#workflow-nav"));
const viewProjects = /** @type {HTMLElement} */ (query("#view-projects"));
const viewWorkflow = /** @type {HTMLElement} */ (query("#view-workflow"));
const projectsList = /** @type {HTMLElement} */ (query("#projects-list"));
const projectsEmpty = /** @type {HTMLElement} */ (query("#projects-empty"));
const newTitleInput = /** @type {HTMLInputElement} */ (query("#new-title"));
const workflowTitle = /** @type {HTMLElement} */ (query("#wf-title"));
const workflowId = /** @type {HTMLElement} */ (query("#wf-id"));
const progressBar = /** @type {HTMLElement} */ (query("#progress-bar"));
const progressLabel = /** @type {HTMLElement} */ (query("#progress-label"));
const s1TabScript = /** @type {HTMLButtonElement} */ (query("#s1-tab-script"));
const s1TabSource = /** @type {HTMLButtonElement} */ (query("#s1-tab-source"));
const s1ScriptView = /** @type {HTMLElement} */ (query("#s1-script-view"));
const s1SourceView = /** @type {HTMLElement} */ (query("#s1-source-view"));
const scriptTitleInput = /** @type {HTMLInputElement} */ (query("#s1-title"));
const contentModeSelect = /** @type {HTMLSelectElement} */ (query("#s1-content-mode"));
const scriptModeHint = /** @type {HTMLElement} */ (query("#s1-mode-hint"));
const scriptInput = /** @type {HTMLTextAreaElement} */ (query("#s1-script"));
const scriptCount = /** @type {HTMLElement} */ (query("#s1-count"));
const compiledPreview = /** @type {HTMLElement} */ (query("#s1-compiled-preview"));
const regionList = /** @type {HTMLElement} */ (query("#s1-region-list"));
const sourceUrlInput = /** @type {HTMLInputElement} */ (query("#s1-source-url"));
const sourceKeywordInput = /** @type {HTMLInputElement} */ (query("#s1-source-keyword"));
const sourceKeywordRunButton = /** @type {HTMLButtonElement} */ (query("#s1-source-keyword-run"));
const sourceBraveStatus = /** @type {HTMLElement} */ (query("#s1-source-brave-status"));
const sourceToneSelect = /** @type {HTMLSelectElement} */ (query("#s1-source-tone"));
const sourceMinutesSelect = /** @type {HTMLSelectElement} */ (query("#s1-source-minutes"));
sourceMinutesSelect.value = "auto";
const sourceStructureSelect = /** @type {HTMLSelectElement} */ (query("#s1-source-structure"));
const sourceNoteInput = /** @type {HTMLInputElement} */ (query("#s1-source-note"));
const sourceAnalyzeButton = /** @type {HTMLButtonElement} */ (query("#s1-source-analyze"));
const sourceClearButton = /** @type {HTMLButtonElement} */ (query("#s1-source-clear"));
const sourceGenerateButton = /** @type {HTMLButtonElement} */ (query("#s1-source-generate"));
const sourceRegenerateButton = /** @type {HTMLButtonElement} */ (query("#s1-source-regenerate"));
const sourceRestoreButton = /** @type {HTMLButtonElement} */ (query("#s1-source-restore"));
const sourceApplyButton = /** @type {HTMLButtonElement} */ (query("#s1-source-apply"));
const sourceState = /** @type {HTMLElement} */ (query("#s1-source-state"));
const sourceSummary = /** @type {HTMLElement} */ (query("#s1-source-summary"));
const sourceFacts = /** @type {HTMLElement} */ (query("#s1-source-facts"));
const sourceWarnings = /** @type {HTMLElement} */ (query("#s1-source-warnings"));
const sourceModeBadge = /** @type {HTMLElement} */ (query("#s1-source-mode-badge"));
const sourceRisk = /** @type {HTMLElement} */ (query("#s1-source-risk"));
const sourceDraftPreview = /** @type {HTMLElement} */ (query("#s1-source-draft"));
const sourceModeButtons = /** @type {HTMLButtonElement[]} */ (queryAll(".source-mode-btn"));
const autopilotInputModeSelect = /** @type {HTMLSelectElement} */ (query("#autopilot-input-mode"));
const autopilotImageCountInput = /** @type {HTMLInputElement} */ (query("#autopilot-image-count"));
const autopilotRenderAfterPreflightSelect = /** @type {HTMLSelectElement} */ (query("#autopilot-render-after-preflight"));
const autopilotDebugVerboseSelect = /** @type {HTMLSelectElement} */ (query("#autopilot-debug-verbose"));
const autopilotStartButton = /** @type {HTMLButtonElement} */ (query("#autopilot-start"));
const autopilotPauseButton = /** @type {HTMLButtonElement} */ (query("#autopilot-pause"));
const autopilotResumeButton = /** @type {HTMLButtonElement} */ (query("#autopilot-resume"));
const autopilotCancelButton = /** @type {HTMLButtonElement} */ (query("#autopilot-cancel"));
const autopilotDebugRefreshButton = /** @type {HTMLButtonElement} */ (query("#autopilot-debug-refresh"));
const autopilotStatePanel = /** @type {HTMLElement} */ (query("#autopilot-state"));
const autopilotEventsPanel = /** @type {HTMLElement} */ (query("#autopilot-events"));
const autopilotDebugPanel = /** @type {HTMLElement} */ (query("#autopilot-debug"));
const dropzone = /** @type {HTMLElement} */ (query("#dropzone"));
const fileInput = /** @type {HTMLInputElement} */ (query("#file-input"));
const thumbnailUploadButton = /** @type {HTMLButtonElement} */ (query("#thumbnail-upload"));
const thumbnailDeleteButton = /** @type {HTMLButtonElement} */ (query("#thumbnail-delete"));
const thumbnailInput = /** @type {HTMLInputElement} */ (query("#thumbnail-input"));
const thumbnailPreview = /** @type {HTMLElement} */ (query("#thumbnail-preview"));
const thumbnailMeta = /** @type {HTMLElement} */ (query("#thumbnail-meta"));
const bgmUploadButton = /** @type {HTMLButtonElement} */ (query("#bgm-upload"));
const bgmDeleteButton = /** @type {HTMLButtonElement} */ (query("#bgm-delete"));
const bgmInput = /** @type {HTMLInputElement} */ (query("#bgm-input"));
const bgmMeta = /** @type {HTMLElement} */ (query("#bgm-meta"));
const mediaWorkflowHint = /** @type {HTMLElement} */ (query("#media-workflow-hint"));
const mediaUploadPanel = /** @type {HTMLElement} */ (query("#media-upload-panel"));
const mediaUploadStatus = /** @type {HTMLElement} */ (query("#media-upload-status"));
const mediaTransferBar = /** @type {HTMLElement} */ (query("#media-transfer-bar"));
const mediaTransferLabel = /** @type {HTMLElement} */ (query("#media-transfer-label"));
const mediaServerBar = /** @type {HTMLElement} */ (query("#media-server-bar"));
const mediaServerLabel = /** @type {HTMLElement} */ (query("#media-server-label"));
const mediaUploadSummary = /** @type {HTMLElement} */ (query("#media-upload-summary"));
const mediaGrid = /** @type {HTMLElement} */ (query("#media-grid"));
const mediaCount = /** @type {HTMLElement} */ (query("#media-count"));
const mediaPreviewStage = /** @type {HTMLElement} */ (query("#media-preview-stage"));
const mediaPreviewMeta = /** @type {HTMLElement} */ (query("#media-preview-meta"));
const imageVisualModeSelect = /** @type {HTMLSelectElement} */ (query("#image-visual-mode"));
const imageCheckpointInput = /** @type {HTMLInputElement} */ (query("#image-checkpoint"));
const imageWidthInput = /** @type {HTMLInputElement} */ (query("#image-width"));
const imageHeightInput = /** @type {HTMLInputElement} */ (query("#image-height"));
const imageSeedInput = /** @type {HTMLInputElement} */ (query("#image-seed"));
const imageLoraNameInput = /** @type {HTMLInputElement} */ (query("#image-lora-name"));
const imageLoraStrengthInput = /** @type {HTMLInputElement} */ (query("#image-lora-strength"));
const imageGenerationProfileSelect = /** @type {HTMLSelectElement} */ (query("#image-generation-profile"));
const imageStylePresetSelect = /** @type {HTMLSelectElement} */ (query("#image-style-preset"));
const imageSeedPolicySelect = /** @type {HTMLSelectElement} */ (query("#image-seed-policy"));
const imageStyleReferenceInput = /** @type {HTMLInputElement} */ (query("#image-style-reference"));
const imageStyleStrengthInput = /** @type {HTMLInputElement} */ (query("#image-style-strength"));
const imageControlReferenceInput = /** @type {HTMLInputElement} */ (query("#image-control-reference"));
const imageControlStrengthInput = /** @type {HTMLInputElement} */ (query("#image-control-strength"));
const imageReferenceOptions = /** @type {HTMLDataListElement} */ (query("#image-reference-options"));
const imageStyleReferenceHint = /** @type {HTMLElement} */ (query("#image-style-reference-hint"));
const simplePromptAllButton = /** @type {HTMLButtonElement} */ (query("#simple-prompt-all"));
const simpleLmstudioUnloadButton = /** @type {HTMLButtonElement} */ (query("#simple-lmstudio-unload"));
const simpleCopyPromptsButton = /** @type {HTMLButtonElement} */ (query("#simple-copy-prompts"));
const simpleImageGenerateButton = /** @type {HTMLButtonElement} */ (query("#simple-image-generate"));
const simpleMediaState = /** @type {HTMLElement} */ (query("#simple-media-state"));
const simplePromptList = /** @type {HTMLElement} */ (query("#simple-prompt-list"));
const flowAspectRatioSelect = /** @type {HTMLSelectElement} */ (query("#flow-aspect-ratio"));
const flowPromptsGenerateButton = /** @type {HTMLButtonElement} */ (query("#flow-prompts-generate"));
const flowOpenButton = /** @type {HTMLButtonElement} */ (query("#flow-open"));
const flowAssetInput = /** @type {HTMLInputElement} */ (query("#flow-asset-input"));
const flowPromptList = /** @type {HTMLElement} */ (query("#flow-prompt-list"));
const imageSentenceIdxInput = /** @type {HTMLInputElement} */ (query("#image-sentence-idx"));
const imageBatchStartIdxInput = /** @type {HTMLInputElement} */ (query("#image-batch-start-idx"));
const imageBatchCountInput = /** @type {HTMLInputElement} */ (query("#image-batch-count"));
const imageVariantsPerSceneInput = /** @type {HTMLInputElement} */ (query("#image-variants-per-scene"));
const imagePositivePromptInput = /** @type {HTMLTextAreaElement} */ (query("#image-positive-prompt"));
const imageNegativePromptInput = /** @type {HTMLTextAreaElement} */ (query("#image-negative-prompt"));
const imageGenSuggestButton = /** @type {HTMLButtonElement} */ (query("#image-gen-suggest"));
const imageGenRunButton = /** @type {HTMLButtonElement} */ (query("#image-gen-run"));
const imageGenBatchRunButton = /** @type {HTMLButtonElement} */ (query("#image-gen-batch-run"));
const imageScenePlanRunButton = /** @type {HTMLButtonElement} */ (query("#image-scene-plan-run"));
const imageRenderPlanRunButton = /** @type {HTMLButtonElement} */ (query("#image-render-plan-run"));
const imageGenState = /** @type {HTMLElement} */ (query("#image-gen-state"));
const sceneCardsRefreshButton = /** @type {HTMLButtonElement} */ (query("#scene-cards-refresh"));
const sceneCardList = /** @type {HTMLElement} */ (query("#scene-card-list"));
const imageRelevanceList = /** @type {HTMLElement} */ (query("#image-relevance-list"));
const imageGenMappings = /** @type {HTMLElement} */ (query("#image-gen-mappings"));
const imageScenePlanList = /** @type {HTMLElement} */ (query("#image-scene-plan-list"));
const imageRenderPlanList = /** @type {HTMLElement} */ (query("#image-render-plan-list"));
const voiceSelect = /** @type {HTMLSelectElement} */ (query("#s3-voice"));
const ttsModeSelect = /** @type {HTMLSelectElement} */ (query("#s3-mode"));
const ttsLanguageSelect = /** @type {HTMLSelectElement} */ (query("#s3-language"));
const ttsSpeedInput = /** @type {HTMLInputElement} */ (query("#s3-speed"));
const ttsDurationInput = /** @type {HTMLInputElement} */ (query("#s3-duration"));
const ttsNumStepInput = /** @type {HTMLInputElement} */ (query("#s3-num-step"));
const ttsGuidanceInput = /** @type {HTMLInputElement} */ (query("#s3-guidance"));
const ttsDenoiseSelect = /** @type {HTMLSelectElement} */ (query("#s3-denoise"));
const ttsPostprocessSelect = /** @type {HTMLSelectElement} */ (query("#s3-postprocess"));
const ttsInstructInput = /** @type {HTMLTextAreaElement} */ (query("#s3-instruct"));
const ttsState = /** @type {HTMLElement} */ (query("#s3-state"));
const ttsPreviewRunButton = /** @type {HTMLButtonElement} */ (query("#s3-preview-run"));
const ttsPreviewTextInput = /** @type {HTMLTextAreaElement} */ (query("#s3-preview-text"));
const ttsPreviewState = /** @type {HTMLElement} */ (query("#s3-preview-state"));
const ttsPreviewAudio = /** @type {HTMLAudioElement} */ (query("#s3-preview-audio"));
const ttsEffectiveProfile = /** @type {HTMLElement} */ (query("#s3-effective-profile"));
const ttsDirtyBadge = /** @type {HTMLElement} */ (query("#s3-dirty-badge"));
const ttsList = /** @type {HTMLElement} */ (query("#s3-list"));
const renderState = /** @type {HTMLElement} */ (query("#s4-state"));
const renderLogPanel = /** @type {HTMLElement} */ (query("#s4-log"));
const renderVideo = /** @type {HTMLVideoElement} */ (query("#s4-video"));
const preflightRunButton = /** @type {HTMLButtonElement} */ (query("#preflight-run"));
const systemHealthRunButton = /** @type {HTMLButtonElement} */ (query("#system-health-run"));
const renderReportRunButton = /** @type {HTMLButtonElement} */ (query("#render-report-run"));
const operatorStatusRunButton = /** @type {HTMLButtonElement} */ (query("#operator-status-run"));
const preflightResults = /** @type {HTMLElement} */ (query("#preflight-results"));
const systemHealthResults = /** @type {HTMLElement} */ (query("#system-health-results"));
const renderReportResults = /** @type {HTMLElement} */ (query("#render-report-results"));
const operatorStatusResults = /** @type {HTMLElement} */ (query("#operator-status-results"));
const featureKenburnsSelect = /** @type {HTMLSelectElement} */ (query("#feature-kenburns"));
const featureBgmVolumeInput = /** @type {HTMLInputElement} */ (query("#feature-bgm-volume"));
const featureBgmDuckingSelect = /** @type {HTMLSelectElement} */ (query("#feature-bgm-ducking"));
const featureRenderLandscapeInput = /** @type {HTMLInputElement} */ (query("#feature-render-landscape"));
const featureRenderShortsInput = /** @type {HTMLInputElement} */ (query("#feature-render-shorts"));
const featureHyperframesOverlayInput = /** @type {HTMLInputElement} */ (query("#feature-hyperframes-overlay"));
const featureHyperframesRequiredInput = /** @type {HTMLInputElement} */ (query("#feature-hyperframes-required"));
const featureSaveButton = /** @type {HTMLButtonElement} */ (query("#feature-save"));
const subtitleSaveButton = /** @type {HTMLButtonElement} */ (query("#subtitle-save"));
const subtitleFontInput = /** @type {HTMLInputElement} */ (query("#subtitle-font"));
const subtitleSizeInput = /** @type {HTMLInputElement} */ (query("#subtitle-size"));
const subtitlePrimaryColorInput = /** @type {HTMLInputElement} */ (query("#subtitle-primary-color"));
const subtitleOutlineColorInput = /** @type {HTMLInputElement} */ (query("#subtitle-outline-color"));
const subtitleOutlineWidthInput = /** @type {HTMLInputElement} */ (query("#subtitle-outline-width"));
const subtitleShadowInput = /** @type {HTMLInputElement} */ (query("#subtitle-shadow"));
const subtitlePositionSelect = /** @type {HTMLSelectElement} */ (query("#subtitle-position"));
const subtitleMarginHInput = /** @type {HTMLInputElement} */ (query("#subtitle-margin-h"));
const subtitleMarginVInput = /** @type {HTMLInputElement} */ (query("#subtitle-margin-v"));
const subtitleBackgroundColorInput = /** @type {HTMLInputElement} */ (query("#subtitle-background-color"));
const subtitleBackgroundOpacityInput = /** @type {HTMLInputElement} */ (query("#subtitle-background-opacity"));
const subtitleMaxLineCharsInput = /** @type {HTMLInputElement} */ (query("#subtitle-max-line-chars"));
const subtitleMinDisplaySecInput = /** @type {HTMLInputElement} */ (query("#subtitle-min-display-sec"));
const subtitleEffectSelect = /** @type {HTMLSelectElement} */ (query("#subtitle-effect"));
const subtitlePositionHint = /** @type {HTMLElement} */ (query("#subtitle-position-hint"));
const subtitlePreviewCaption = /** @type {HTMLElement} */ (query("#subtitle-preview-caption"));
const subtitlePresetButtons = /** @type {HTMLButtonElement[]} */ (queryAll(".subtitle-preset"));
const oauthPanel = /** @type {HTMLElement} */ (query("#oauth-panel"));
const uploadTitleInput = /** @type {HTMLInputElement} */ (query("#s5-title"));
const uploadDescInput = /** @type {HTMLTextAreaElement} */ (query("#s5-desc"));
const uploadTagsInput = /** @type {HTMLInputElement} */ (query("#s5-tags"));
const uploadPrivacySelect = /** @type {HTMLSelectElement} */ (query("#s5-privacy"));
const uploadScheduleInput = /** @type {HTMLInputElement} */ (query("#s5-schedule"));
const uploadState = /** @type {HTMLElement} */ (query("#s5-state"));
const uploadLink = /** @type {HTMLElement} */ (query("#s5-link"));
const uploadStatsPanel = /** @type {HTMLElement} */ (query("#s5-stats-panel"));
const backButton = /** @type {HTMLButtonElement} */ (query("#back"));
const cloneProjectButton = /** @type {HTMLButtonElement} */ (query("#clone-project"));

/**
 * @param {"projects" | "workflow"} view
 * @returns {void}
 */
function show(view) {
  viewProjects.hidden = view !== "projects";
  viewWorkflow.hidden = view !== "workflow";
  if (view === "workflow") {
    showStep(1);
  }
  workflowNav.hidden = view !== "workflow";
  navProjects.classList.toggle("active", view === "projects");
}

/**
 * @param {"script" | "source"} mode
 */
function setS1Mode(mode) {
  s1TabScript.classList.toggle("active", mode === "script");
  s1TabSource.classList.toggle("active", mode === "source");
  s1ScriptView.hidden = mode !== "script";
  s1SourceView.hidden = mode !== "source";
}

const createButton = /** @type {HTMLButtonElement} */ (query("#btn-new"));
const saveScriptButton = /** @type {HTMLButtonElement} */ (query("#s1-save"));
const ttsRunButton = /** @type {HTMLButtonElement} */ (query("#s3-run"));
const renderRunButton = /** @type {HTMLButtonElement} */ (query("#s4-run"));
const youtubeRunButton = /** @type {HTMLButtonElement} */ (query("#s5-run"));
const stepButtons = /** @type {HTMLButtonElement[]} */ (queryAll(".nav.step"));
const stepViews = /** @type {HTMLElement[]} */ (queryAll(".step-view"));

/**
 * @returns {Project}
 */
function requireCurrent() {
  if (!current) {
    throw new Error("No active project");
  }
  return current;
}

/**
 * @returns {string}
 */
function requestedProjectId() {
  return new URL(window.location.href).searchParams.get("project") || "";
}

/**
 * @returns {number}
 */
function requestedStep() {
  const rawValue = new URL(window.location.href).searchParams.get("step") || "1";
  const parsed = Number(rawValue);
  if (!Number.isFinite(parsed)) {
    return 1;
  }
  return Math.max(1, Math.min(5, Math.trunc(parsed)));
}

/**
 * @returns {void}
 */
function syncUrlState() {
  const url = new URL(window.location.href);
  if (!current) {
    url.searchParams.delete("project");
    url.searchParams.delete("step");
  } else {
    url.searchParams.set("project", current.id);
    const activeButton = stepButtons.find((button) => button.classList.contains("active"));
    const activeStep = Number(activeButton?.dataset.step || "1");
    url.searchParams.set("step", String(activeStep));
  }
  window.history.replaceState({}, "", url.toString());
}

/**
 * @param {number} step
 * @returns {void}
 */
function showStep(step) {
  stepViews.forEach((view, index) => {
    view.hidden = index + 1 !== step;
  });
  stepButtons.forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.step) === step);
  });
  if (current) {
    syncUrlState();
  }
}

/**
 * @returns {Promise<void>}
 */
async function loadProjects() {
  const projects = await requestJson("/api/projects");
  const projectCards = /** @type {ProjectCard[]} */ (projects);
  projectsList.innerHTML = "";
  projectsEmpty.hidden = projectCards.length > 0;
  const requestedId = requestedProjectId();

  for (const project of projectCards) {
    const card = document.createElement("article");
    card.className = "project-card";
    card.innerHTML = `
      <div class="title">${escapeHtml(project.title || "Untitled Project")}</div>
      <div class="muted">${escapeHtml(project.updated_at)}</div>
      <div class="chips">
        ${chip("TTS", project.tts_state)}
        ${chip("Render", project.render_state)}
        ${chip("Upload", project.upload_state)}
        ${project.youtube_id ? '<span class="chip">YouTube linked</span>' : ""}
      </div>
      <div class="row between">
        <span class="muted">Click to open</span>
        <button class="btn danger" type="button" data-delete="${project.id}">Delete</button>
      </div>
    `;
    card.addEventListener("click", (event) => {
      const target = /** @type {HTMLElement} */ (event.target);
      if (target.dataset.delete) {
        return;
      }
      void openProject(project.id);
    });
    projectsList.appendChild(card);
  }
  if (requestedId) {
    const requested = projectCards.find((project) => project.id === requestedId);
    if (requested) {
      await openProject(requested.id);
    }
  }
}

/**
 * @param {string} pid
 * @returns {Promise<void>}
 */
async function openProject(pid) {
  await ensureTtsPresetCatalog();
  populateVoiceSelect();
  current = /** @type {Project} */ (await requestJson(`/api/projects/${pid}`));
  selectedMediaName = current.media_order[0] || null;
  mediaClientState = {
    phase: current.media_upload_state === "running" ? "processing" : "idle",
    transferProgress: current.media_upload_state === "done" ? 100 : 0,
    message: current.media_upload_error || "업로드를 시작하면 파일별 진행 상황을 여기에서 확인할 수 있습니다.",
    lastAccepted: [],
    lastSkipped: [],
  };

  show("workflow");
  workflowTitle.textContent = current.title || "Untitled Project";
  workflowId.textContent = current.id;
  scriptTitleInput.value = current.title;
  contentModeSelect.value = current.content_mode || "standard";
  scriptInput.value = current.user_script || current.script;
  uploadTitleInput.value = current.title || "";
  uploadDescInput.value = "";
  uploadTagsInput.value = "";
  uploadPrivacySelect.value = "private";

  renderScriptStats();
  renderSourceDraft(current);
  const initialMode = current.source_draft_query ? "source" : "script";
  setS1Mode(initialMode);
  renderAutopilot(current);
  void renderBraveUsageStatus();
  renderMedia();
  renderThumbnail();
  renderBgmMeta();
  renderTtsProfileControls();
  renderFeatureControls();
  renderImageGenPanel();
  void loadSceneCards();
  void loadFlowPrompts();
  renderLogPanel.textContent = formatRenderLog(
    current.render_state,
    current.render_phase,
    current.render_progress_detail,
    current.render_last_log,
    current.render_heartbeat_at,
  );
  renderMediaUploadStatus();
  renderSubtitleStyleControls();
  renderTtsList();
  renderStep5();
  updateOutputVideo();
  updateProgressBar();
  updateStepMarks();
  showStep(pid === requestedProjectId() ? requestedStep() : 1);
  syncUrlState();
  startPoll();
  void refreshAutopilotDebug().catch(() => {
    autopilotDebugSnapshot = null;
    renderAutopilot(requireCurrent());
  });
  void runOperatorStatus().catch(() => {
    // Ignore initial operator status failures.
  });
}

/**
 * @returns {void}
 */
function renderScriptStats() {
  const project = current;
  if (!project) return;
  const regionalSentences = project ? effectiveRegionalSentences(project) : [];
  const sentenceCount = regionalSentences.length || estimateSentenceCount(scriptInput.value);
  const bibleCount = regionalSentences.filter((sentence) => sentence.region === "bible").length;
  scriptCount.textContent = bibleCount > 0
    ? `문장 ${sentenceCount}개 | bible ${bibleCount}개`
    : `문장 ${sentenceCount}개`;
  scriptModeHint.textContent = contentModeSelect.value === "bible_longform"
    ? "Bible Longform mode keeps the user script separate from the compiled script. Use region markers before saving."
    : "Standard mode preserves the existing script-to-TTS flow.";
  const isUnsavedScript = project
    ? scriptInput.value !== (project.user_script || project.script || "")
      || contentModeSelect.value !== (project.content_mode || "standard")
    : true;
  compiledPreview.textContent = isUnsavedScript
    ? "Save the script to refresh compiled preview."
    : (project?.compiled_script || project?.script || "");
  regionList.innerHTML = "";
  if (isUnsavedScript || !project || regionalSentences.length === 0) {
    regionList.innerHTML = '<div class="muted">Save the script to see compiled regions.</div>';
    return;
  }
  for (const sentence of regionalSentences) {
    const region = normalizeRegion(sentence.region);
    const row = document.createElement("div");
    row.className = `region-row ${region}`;
    row.innerHTML = `
      <div class="region-badge">${escapeHtml(region)}</div>
      <div class="region-text">${escapeHtml(sentence.text)}</div>
    `;
    regionList.appendChild(row);
  }
}

/**
 * @param {Project} project
 * @returns {void}
 */
function renderSourceDraft(project) {
  if (!project) return;
  if (document.activeElement !== sourceUrlInput) {
    sourceUrlInput.value = project.source_draft_input_mode === "url" ? project.source_draft_query || "" : "";
  }
  if (document.activeElement !== sourceKeywordInput) {
    sourceKeywordInput.value = project.source_draft_input_mode === "keyword" ? project.source_draft_query || "" : "";
  }
  if (document.activeElement !== sourceNoteInput) {
    sourceNoteInput.value = project.source_draft_regenerate_note || "";
  }
  sourceModeButtons.forEach((button) => {
    button.classList.toggle("active", (button.dataset.mode || "") === (project.source_draft_regenerate_mode || ""));
  });

  if (project.source_draft_state === "queued") {
    sourceState.textContent = "대본 초안 생성이 대기열에 등록되었습니다...";
  } else if (project.source_draft_state === "running") {
    const phase = project.source_draft_phase || "generate";
    const phaseLabel = phase === "generate" ? "초안 생성 중" : phase;
    sourceState.textContent = `${phaseLabel} ${project.source_draft_progress}%`;
  } else if (project.source_draft_state === "error") {
    sourceState.textContent = project.source_draft_error || "분석 중 오류가 발생했습니다.";
  } else if (project.source_draft_state === "done") {
    sourceState.textContent = `분석 완료 ${project.source_draft_progress}%`;
  } else {
    sourceState.textContent = "기사 URL을 넣고 분석하면 여기에서 source draft를 확인할 수 있습니다.";
  }

  const source = project.source_draft_sources[0];
  if (!source) {
    sourceSummary.innerHTML = '<div class="muted">아직 분석된 URL이 없습니다. 기사 URL을 입력해 주세요.</div>';
    sourceFacts.innerHTML = '<div class="muted">fact note가 아직 없습니다.</div>';
    sourceWarnings.innerHTML = '<div class="muted">안전 경고가 아직 없습니다.</div>';
    sourceDraftPreview.textContent = "대본 초안을 생성하면 여기에서 검토할 수 있습니다.";
    sourceModeBadge.textContent = "";
    sourceRisk.textContent = "";
    sourceGenerateButton.disabled = true;
    sourceRegenerateButton.disabled = true;
    sourceRestoreButton.disabled = true;
    sourceApplyButton.disabled = true;
    return;
  }

  const factItems = project.source_draft_fact_notes
    .map((item) => `<li>${escapeHtml(item.note)}</li>`)
    .join("");
  const warningItems = project.source_draft_warnings
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  sourceSummary.innerHTML = `
    <div class="source-summary-list">
      ${project.source_draft_sources.map((item) => `
        <div class="source-summary-item">
          <div class="source-summary-top">
            <strong>${escapeHtml(item.title || item.domain)}</strong>
            <a href="${escapeHtml(item.final_url || item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.domain)}</a>
          </div>
          <div class="muted">단어 ${item.word_count}개 | ${escapeHtml(item.fetched_at || "")}</div>
          <p>${escapeHtml(item.excerpt || "")}</p>
        </div>
      `).join("")}
    </div>
  `;
  sourceFacts.innerHTML = factItems ? `<ol>${factItems}</ol>` : '<div class="muted">fact note가 아직 없습니다.</div>';
  sourceWarnings.innerHTML = warningItems ? `<ul>${warningItems}</ul>` : '<div class="muted">안전 경고가 없습니다.</div>';
  sourceDraftPreview.textContent = project.source_draft_script || "대본 초안을 생성하면 여기에서 검토할 수 있습니다.";
  sourceModeBadge.textContent = project.source_draft_regenerate_mode
    ? `Mode: ${project.source_draft_regenerate_mode}`
    : "Mode: default";
  sourceRisk.textContent = project.source_draft_script
    ? `유사도 ${Math.round((project.source_draft_risk_score || 0) * 100)}% | ${project.source_draft_model || "-"}`
    : "";
  sourceGenerateButton.disabled = project.source_draft_sources.length === 0 || ["queued", "running"].includes(project.source_draft_state);
  sourceRegenerateButton.disabled = project.source_draft_sources.length === 0 || ["queued", "running"].includes(project.source_draft_state);
  sourceRestoreButton.disabled = !project.source_draft_previous_script;
  sourceApplyButton.disabled = !project.source_draft_script;
  sourceKeywordRunButton.disabled = ["queued", "running"].includes(project.source_draft_state);
}

/**
 * @returns {Promise<void>}
 */
async function renderBraveUsageStatus() {
  try {
    const status = /** @type {{month: string, used: number, remaining: number, limit: number}} */ (
      await requestJson("/api/projects/_/source/brave/status")
    );
    sourceBraveStatus.textContent = `Brave 무료 검색 ${status.used}/${status.limit} | 이번 달 남은 ${status.remaining}건`;
  } catch {
    sourceBraveStatus.textContent = "Brave 사용량 정보를 불러오지 못했습니다.";
  }
}

/**
 * @returns {number | "auto"}
 */
function autopilotImageCountValue() {
  const rawValue = autopilotImageCountInput.value.trim().toLowerCase();
  if (!rawValue || rawValue === "auto") {
    return "auto";
  }
  const parsed = Number(rawValue);
  if (!Number.isFinite(parsed)) {
    return "auto";
  }
  return Math.max(1, Math.min(48, Math.trunc(parsed)));
}

/**
 * @returns {AutopilotOptions}
 */
function buildAutopilotPayload() {
  return {
    input_mode: /** @type {AutopilotInputMode} */ (autopilotInputModeSelect.value),
    script: scriptInput.value,
    url: sourceUrlInput.value.trim(),
    keyword: sourceKeywordInput.value.trim(),
    tone: sourceToneSelect.value || "documentary",
    target_minutes: sourceMinutesSelect.value || "auto",
    regenerate_mode: /** @type {SourceRegenerateMode} */ (sourceModeButtons.find((button) => button.classList.contains("active"))?.dataset.mode || ""),
    visual_source_mode: /** @type {VisualSourceMode} */ (imageVisualModeSelect.value || "comfyui_auto"),
    image_count: autopilotImageCountValue(),
    render_after_preflight: autopilotRenderAfterPreflightSelect.value === "on",
    debug_verbose: autopilotDebugVerboseSelect.value === "on",
  };
}

/**
 * @param {Project} project
 * @returns {void}
 */
function renderAutopilot(project) {
  if (!project) return;
  const autopilotOptions = /** @type {Partial<AutopilotOptions>} */ (project.autopilot_options || {});
  if (document.activeElement !== autopilotInputModeSelect) {
    autopilotInputModeSelect.value = autopilotOptions.input_mode || autopilotInputModeSelect.value || "script";
  }
  if ("image_count" in autopilotOptions) {
    const value = autopilotOptions.image_count;
    autopilotImageCountInput.value = value === "auto" ? "auto" : String(value || "auto");
  }
  autopilotRenderAfterPreflightSelect.value = autopilotOptions.render_after_preflight === false ? "off" : "on";
  autopilotDebugVerboseSelect.value = autopilotOptions.debug_verbose ? "on" : "off";

  const summaryBits = [
    `상태: ${readableAutopilotState(project.autopilot_state)}`,
    `진행률: ${project.autopilot_progress}%`,
    `단계: ${project.autopilot_phase || "-"}`,
  ];
  if (project.autopilot_last_error_code) {
    summaryBits.push(`오류 코드: ${project.autopilot_last_error_code}`);
  }
  if (project.autopilot_debug_summary) {
    summaryBits.push(`요약: ${project.autopilot_debug_summary}`);
  }
  const lastLine = project.autopilot_error || project.autopilot_last_log || "아직 오토파일럿 실행 기록이 없습니다.";
  autopilotStatePanel.textContent = `${summaryBits.join(" | ")}\n${lastLine}`;

  const isActive = project.autopilot_state === "queued" || project.autopilot_state === "running";
  autopilotStartButton.disabled = isActive || project.autopilot_state === "paused";
  autopilotPauseButton.disabled = !isActive;
  autopilotResumeButton.disabled = project.autopilot_state !== "paused";
  autopilotCancelButton.disabled = ["idle", "done", "error", "canceled"].includes(project.autopilot_state);

  const events = autopilotDebugSnapshot?.recent_events || [];
  if (events.length === 0) {
    autopilotEventsPanel.innerHTML = "이벤트 로그가 아직 없습니다.";
  } else {
    autopilotEventsPanel.innerHTML = events.slice(-10).reverse().map((eventItem) => `
      <div class="autopilot-event">
        <div><strong>${escapeHtml(eventItem.phase || "-")}</strong> | ${escapeHtml(eventItem.level)} | ${escapeHtml(eventItem.ts)}</div>
        <div>${escapeHtml(eventItem.message || "")}</div>
      </div>
    `).join("");
  }

  const debugSnapshot = autopilotDebugSnapshot;
  autopilotDebugPanel.textContent = debugSnapshot
    ? JSON.stringify(debugSnapshot, null, 2)
    : "디버그 스냅샷이 아직 없습니다.";
}

/**
 * @returns {Promise<void>}
 */
async function refreshAutopilotDebug() {
  const project = requireCurrent();
  autopilotDebugSnapshot = /** @type {AutopilotDebugSnapshot} */ (await requestJson(`/api/projects/${project.id}/autopilot/debug`));
  renderAutopilot(project);
}

/**
 * @returns {Promise<void>}
 */
async function startAutopilot() {
  const project = requireCurrent();
  const response = /** @type {{project: Project}} */ (
    await requestJson(`/api/projects/${project.id}/autopilot/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildAutopilotPayload()),
    })
  );
  current = response.project;
  renderAutopilot(current);
  await refreshAutopilotDebug();
}

/**
 * @param {"pause" | "resume" | "cancel"} action
 * @returns {Promise<void>}
 */
async function updateAutopilotState(action) {
  const project = requireCurrent();
  const response = /** @type {{project: Project}} */ (
    await requestJson(`/api/projects/${project.id}/autopilot/${action}`, {
      method: "POST",
      body: new FormData(),
    })
  );
  current = response.project;
  renderAutopilot(current);
  await refreshAutopilotDebug();
}

/**
 * @returns {Promise<void>}
 */
async function analyzeSourceUrl() {
  const project = requireCurrent();
  const url = sourceUrlInput.value.trim();
  if (!url) {
    toast("기사 URL을 먼저 입력해 주세요.");
    return;
  }
  sourceAnalyzeButton.disabled = true;
  sourceState.textContent = "URL 본문을 분석하는 중입니다...";
  try {
    current = /** @type {Project} */ (
      await requestJson(`/api/projects/${project.id}/source/url/analyze`, {
        method: "POST",
        body: formDataFromObject({ url }),
      })
    );
    renderSourceDraft(current);
    toast("URL 분석이 완료되었습니다.");
  } finally {
    sourceAnalyzeButton.disabled = false;
  }
}

/**
 * @returns {Promise<void>}
 */
async function collectSourceKeyword() {
  const project = requireCurrent();
  const keyword = sourceKeywordInput.value.trim();
  if (!keyword) {
    toast("키워드를 먼저 입력해 주세요.");
    return;
  }
  sourceKeywordRunButton.disabled = true;
  sourceState.textContent = "키워드 검색 결과를 수집하는 중입니다...";
  try {
    current = /** @type {Project} */ (
      await requestJson(`/api/projects/${project.id}/source/keyword/collect`, {
        method: "POST",
        body: formDataFromObject({ keyword }),
      })
    );
    renderSourceDraft(current);
    await renderBraveUsageStatus();
    toast("키워드 리서치 수집이 완료되었습니다.");
  } finally {
    sourceKeywordRunButton.disabled = false;
  }
}

/**
 * @returns {Promise<void>}
 */
async function clearSourceDraft() {
  const project = requireCurrent();
  current = /** @type {Project} */ (await requestJson(`/api/projects/${project.id}/source/draft`, { method: "DELETE" }));
  renderSourceDraft(current);
  toast("Source draft를 비웠습니다.");
}

/**
 * @returns {Promise<void>}
 */
async function generateSourceScript() {
  const project = requireCurrent();
  if (project.source_draft_sources.length === 0) {
    toast("먼저 기사 URL을 분석해 주세요.");
    return;
  }
  const selectedModeButton = sourceModeButtons.find((button) => button.classList.contains("active"));
  const selectedMode = selectedModeButton ? (selectedModeButton.dataset.mode || "") : "";
  sourceGenerateButton.disabled = true;
  sourceRegenerateButton.disabled = true;
  sourceState.textContent = "대본 초안을 생성하는 중입니다...";
  try {
    current = /** @type {Project} */ (
      await requestJson(`/api/projects/${project.id}/source/script/generate`, {
        method: "POST",
        body: formDataFromObject({
          tone: sourceToneSelect.value,
          target_minutes: sourceMinutesSelect.value,
          language: "ko",
          mode: selectedMode,
          note: sourceNoteInput.value.trim(),
          script_structure: sourceStructureSelect.value || "hpsl",
        }),
      })
    );
    renderSourceDraft(current);
    toast("대본 초안 생성을 대기열에 등록했습니다.");
  } finally {
    sourceGenerateButton.disabled = false;
    sourceRegenerateButton.disabled = false;
  }
}

/**
 * @returns {Promise<void>}
 */
async function applySourceScript() {
  const project = requireCurrent();
  if (!project.source_draft_script) {
    toast("적용할 대본 초안이 없습니다.");
    return;
  }
  current = /** @type {Project} */ (
    await requestJson(`/api/projects/${project.id}/source/script/apply`, {
      method: "POST",
      body: new FormData(),
    })
  );
  scriptInput.value = current.user_script || current.script || "";
  contentModeSelect.value = current.content_mode || "standard";
  renderScriptStats();
  renderSourceDraft(current);
  updateProgressBar();
  updateStepMarks();
  setS1Mode("script");
  toast("대본 초안을 Step 1 스크립트에 적용했습니다.");
}

/**
 * @returns {Promise<void>}
 */
async function restorePreviousSourceScript() {
  const project = requireCurrent();
  if (!project.source_draft_previous_script) {
    toast("복원할 이전 초안이 없습니다.");
    return;
  }
  current = /** @type {Project} */ (
    await requestJson(`/api/projects/${project.id}/source/script/restore-previous`, {
      method: "POST",
      body: new FormData(),
    })
  );
  renderSourceDraft(current);
  toast("이전 초안으로 복원했습니다.");
}

/**
 * @returns {void}
 */
function renderTtsProfileControls() {
  const project = requireCurrent();
  const resolvedPreset = canonicalVoicePresetId(project.voice_preset);
  const profile = project.voice_preset === resolvedPreset
    ? effectiveTtsProfile(project)
    : presetProfile(resolvedPreset);
  voiceSelect.value = resolvedPreset;
  ttsModeSelect.value = profile.mode === "design" ? "design" : "auto";
  ttsLanguageSelect.value = profile.language || "ko";
  ttsSpeedInput.value = String(profile.speed);
  ttsDurationInput.value = profile.duration === null ? "" : String(profile.duration);
  ttsNumStepInput.value = String(profile.num_step);
  ttsGuidanceInput.value = String(profile.guidance_scale);
  ttsDenoiseSelect.value = profile.denoise ? "on" : "off";
  ttsPostprocessSelect.value = profile.postprocess_output ? "on" : "off";
  ttsInstructInput.value = profile.instruct;
  if (!ttsPreviewTextInput.value.trim()) {
    ttsPreviewTextInput.value = ttsPresetCatalog ? ttsPresetCatalog.sample_text : DEFAULT_TTS_SAMPLE_TEXT;
  }
  lastTtsPreviewLock = null;
  ttsPreviewState.textContent = "샘플을 생성하면 여기에서 바로 재생할 수 있습니다.";
  ttsPreviewAudio.src = "";
  ttsPreviewAudio.load();
  ttsFormDirtyAfterPreset = false;
  updateTtsEffectiveProfile();
}

/**
 * @returns {void}
 */
function updateTtsEffectiveProfile() {
  const canonicalId = canonicalVoicePresetId(voiceSelect.value);
  const profile = readTtsProfileInputs();
  ttsEffectiveProfile.textContent =
    `Effective: ${canonicalId} | mode=${profile.mode} | seed_mode=${profile.seed_mode} | language=${profile.language} | ` +
    `instruct="${profile.instruct || "(none)"}" | speed=${profile.speed} | ` +
    `num_step=${profile.num_step} | guidance=${profile.guidance_scale}`;
  ttsDirtyBadge.hidden = !ttsFormDirtyAfterPreset;
}

/**
 * @returns {TtsProfile}
 */
function readTtsProfileInputs() {
  const durationValue = ttsDurationInput.value.trim();
  return {
    mode: /** @type {TtsMode} */ (ttsModeSelect.value === "design" ? "design" : "auto"),
    seed_mode: "per_sentence",
    language: ttsLanguageSelect.value,
    instruct: ttsInstructInput.value.trim(),
    speed: numberInRange(ttsSpeedInput.value, DEFAULT_TTS_PROFILE.speed, 0.75, 1.25),
    duration: durationValue ? numberInRange(durationValue, 0, 0, 30) : null,
    num_step: Math.round(numberInRange(ttsNumStepInput.value, DEFAULT_TTS_PROFILE.num_step, 16, 64)),
    guidance_scale: numberInRange(
      ttsGuidanceInput.value,
      DEFAULT_TTS_PROFILE.guidance_scale,
      1,
      5,
    ),
    denoise: ttsDenoiseSelect.value === "on",
    postprocess_output: ttsPostprocessSelect.value === "on",
    seed: null,
  };
}

/**
 * @param {string} presetId
 * @returns {void}
 */
function applyTtsPreset(presetId) {
  const canonicalId = canonicalVoicePresetId(presetId);
  const merged = presetProfile(canonicalId);
  voiceSelect.value = canonicalId;
  ttsModeSelect.value = merged.mode === "design" ? "design" : "auto";
  ttsLanguageSelect.value = merged.language;
  ttsSpeedInput.value = String(merged.speed);
  ttsDurationInput.value = merged.duration === null ? "" : String(merged.duration);
  ttsNumStepInput.value = String(merged.num_step);
  ttsGuidanceInput.value = String(merged.guidance_scale);
  ttsDenoiseSelect.value = merged.denoise ? "on" : "off";
  ttsPostprocessSelect.value = merged.postprocess_output ? "on" : "off";
  ttsInstructInput.value = merged.instruct;
  ttsFormDirtyAfterPreset = false;
  lastTtsPreviewLock = null;
  updateTtsEffectiveProfile();
}

/**
 * @returns {TtsProfile | null}
 */
function buildTtsProfilePayload() {
  const canonicalId = canonicalVoicePresetId(voiceSelect.value);
  if (!ttsFormDirtyAfterPreset && canonicalId !== "auto") {
    return null;
  }
  return readTtsProfileInputs();
}

/**
 * @returns {void}
 */
function clearTtsPreviewLock() {
  lastTtsPreviewLock = null;
}

/**
 * @param {boolean} disabled
 * @returns {void}
 */
function setUploadControlsDisabled(disabled) {
  fileInput.disabled = disabled;
  dropzone.classList.toggle("is-disabled", disabled);
  dropzone.setAttribute("aria-disabled", disabled ? "true" : "false");
}

/**
 * @returns {void}
 */
function renderMediaUploadStatus() {
  const project = current;
  if (!project) return;
  const workflowPercent = project
    ? [
        project.sentences.length > 0,
        project.media_order.length > 0,
        project.tts_state === "done",
        project.render_state === "done",
        project.upload_state === "done",
      ].filter(Boolean).length * 20
    : 0;

  mediaWorkflowHint.textContent = `Workflow progress is ${workflowPercent}%, and the panel below shows only media upload status.`;

  mediaTransferBar.style.width = `${mediaClientState.transferProgress}%`;
  mediaTransferLabel.textContent = `${mediaClientState.transferProgress}%`;

  const serverProgress = project ? project.media_upload_progress : 0;
  mediaServerBar.style.width = `${serverProgress}%`;
  if (project && project.media_upload_total > 0) {
    mediaServerLabel.textContent = `${project.media_upload_completed}/${project.media_upload_total} files`;
  } else {
    mediaServerLabel.textContent = `${serverProgress}%`;
  }

  let statusText = "대기 중";
  if (mediaClientState.phase === "uploading") {
    statusText = `브라우저 전송 중 ${mediaClientState.transferProgress}%`;
  } else if (mediaClientState.phase === "processing") {
      statusText = project && project.media_upload_state === "running"
        ? `서버 처리 중 ${project.media_upload_progress}%`
        : "전송 완료, 서버 응답 대기 중";
  } else if (mediaClientState.phase === "done") {
    statusText = "업로드 완료";
  } else if (mediaClientState.phase === "error") {
    statusText = "업로드 오류";
  } else if (project && project.media_upload_state === "running") {
    statusText = `서버 처리 중 ${project.media_upload_progress}%`;
  } else if (project && project.media_upload_state === "done" && project.media_upload_total > 0) {
    statusText = "최근 업로드 완료";
  }
  mediaUploadStatus.textContent = statusText;

  const summaryParts = [mediaClientState.message].filter(Boolean);
  if (mediaClientState.lastAccepted.length > 0) {
    summaryParts.push(`저장한 파일: ${mediaClientState.lastAccepted.map((item) => item.saved_name).join(", ")}`);
  }
  if (mediaClientState.lastSkipped.length > 0) {
    summaryParts.push(`건너뛴 파일: ${mediaClientState.lastSkipped.map((item) => `${item.name} (${item.reason})`).join(", ")}`);
  }
  if (project && project.media_upload_error) {
    summaryParts.push(`최근 오류: ${project.media_upload_error}`);
  }
  mediaUploadSummary.textContent = summaryParts.join(" | ") || "업로드를 시작하면 파일별 진행 상황을 여기에서 확인할 수 있습니다.";

  mediaUploadPanel.classList.toggle("ok", mediaClientState.phase === "done");
  mediaUploadPanel.classList.toggle("warn", mediaClientState.phase === "uploading" || mediaClientState.phase === "processing");
  mediaUploadPanel.classList.toggle("error", mediaClientState.phase === "error");
}

/**
 * @returns {void}
 */
function renderSimpleMediaPanel() {
  const project = requireCurrent();
  if (!project) return;
  const options = /** @type {Record<string, unknown>} */ (project.body_image_options || {});
  const promptCount = Number(options.simple_media_prompt_count || 0);
  const unload = /** @type {Record<string, unknown>} */ (options.simple_media_lmstudio_unload || {});
  const unloadOk = unload.ok === true;
  const isBusy = project.body_image_state === "queued" || project.body_image_state === "running";
  simplePromptAllButton.disabled = isBusy || project.sentences.length === 0;
  simpleLmstudioUnloadButton.disabled = isBusy || promptCount <= 0;
  simpleCopyPromptsButton.disabled = simplePromptItems.length === 0;
  simpleImageGenerateButton.disabled = isBusy || promptCount <= 0 || !unloadOk;

  const statusParts = [];
  statusParts.push(promptCount > 0 ? `프롬프트 ${promptCount}개 생성됨` : "프롬프트 미생성");
  if (promptCount > 0) {
    statusParts.push(unloadOk ? "LM Studio 종료/언로드 확인됨" : "LM Studio 종료 필요");
  }
  if (project.body_image_last_log) {
    statusParts.push(project.body_image_last_log);
  }
  simpleMediaState.textContent = statusParts.join(" | ");
  simpleMediaState.className = unloadOk ? "card ok" : promptCount > 0 ? "card warn" : "muted";

  if (simplePromptItems.length === 0) {
    simplePromptList.innerHTML = '<div class="muted">전체 이미지 프롬프트 생성 후 문장별 프롬프트가 여기에 표시됩니다.</div>';
    return;
  }
  simplePromptList.innerHTML = simplePromptItems.map((item) => {
    const idx = Number(item.sentence_idx || 0);
    const sentence = String(item.sentence || "");
    const prompt = String(item.positive_prompt || "");
    const negative = String(item.negative_prompt || "");
    return `
      <article class="image-gen-mapping-item">
        <div class="image-gen-mapping-body">
          <div><strong>문장 ${idx + 1}</strong>: ${escapeHtml(sentence)}</div>
          <div><strong>프롬프트</strong>: ${escapeHtml(prompt)}</div>
          <div class="muted"><strong>Negative</strong>: ${escapeHtml(negative)}</div>
          <div class="row"><button class="btn" type="button" data-simple-copy-prompt="${idx}">복사</button></div>
        </div>
      </article>
    `;
  }).join("");
}

/**
 * @returns {void}
 */
function renderImageGenPanel() {
  const project = requireCurrent();
  if (!project) return;
  imageVisualModeSelect.value = project.visual_source_mode || "upload_only";
  imageGenRunButton.disabled = project.body_image_state === "queued" || project.body_image_state === "running";
  imageGenBatchRunButton.disabled = imageGenRunButton.disabled;
  syncImageReferenceOptions();
  syncImageProfileUi();
  renderSimpleMediaPanel();

  let statusText = `상태: ${readableTaskState(project.body_image_state)} ${project.body_image_progress}%`;
  if (project.body_image_phase) {
    statusText += ` | 단계: ${readableImagePhase(project.body_image_phase)}`;
  }
  if (project.body_image_error) {
    statusText += ` | 오류: ${project.body_image_error}`;
  } else if (project.body_image_last_log) {
    statusText += ` | 로그: ${project.body_image_last_log}`;
  }
  imageGenState.textContent = statusText;
  imageGenState.className = project.body_image_state === "error"
    ? "card error"
    : project.body_image_state === "done"
      ? "card ok"
      : project.body_image_state === "queued" || project.body_image_state === "running"
        ? "card warn"
        : "card muted";

  if (!imagePositivePromptInput.value.trim()) {
    const sentence = project.sentences[Number(imageSentenceIdxInput.value) || 0] || project.sentences[0] || "";
    imagePositivePromptInput.value = sentence;
  }
  imageBatchStartIdxInput.value = imageBatchStartIdxInput.value || imageSentenceIdxInput.value || "0";
  if (imageGenerationProfileSelect.value === "sdxl_style_reference" && !imageStyleReferenceInput.value.trim()) {
    imageStyleReferenceInput.value = preferredStyleReferenceValue();
  }
  if (imageGenerationProfileSelect.value === "sdxl_controlnet_depth" && !imageControlReferenceInput.value.trim()) {
    imageControlReferenceInput.value = preferredControlImageValue();
  }

  const relevanceRows = project.visual_relevance_rows || [];
  const relevanceSummary = project.visual_relevance_summary || {
    total: relevanceRows.length,
    pass_count: relevanceRows.filter((item) => item.status === "pass").length,
    stale_count: relevanceRows.filter((item) => item.status === "stale").length,
    missing_count: relevanceRows.filter((item) => item.status === "missing").length,
  };
  if (project.visual_source_mode !== "comfyui_auto") {
    imageRelevanceList.innerHTML = '<div class="muted">현재 visual mode에서는 generated-image relevance 상태를 표시하지 않습니다.</div>';
  } else if (relevanceRows.length === 0) {
    imageRelevanceList.innerHTML = '<div class="muted">아직 relevance 상태를 계산할 생성 이미지가 없습니다.</div>';
  } else {
    const summaryChips = `
      <div class="image-relevance-summary">
        <span class="chip">총 ${relevanceSummary.total}</span>
        <span class="chip image-relevance-chip pass">PASS ${relevanceSummary.pass_count}</span>
        <span class="chip image-relevance-chip stale">STALE ${relevanceSummary.stale_count}</span>
        <span class="chip image-relevance-chip missing">MISSING ${relevanceSummary.missing_count}</span>
      </div>
    `;
    imageRelevanceList.innerHTML = summaryChips + relevanceRows.map((item) => `
      <article class="image-relevance-item ${escapeHtml(item.status)}">
        <div class="image-relevance-top">
          <strong>문장 ${item.sentence_idx}</strong>
          <span class="chip image-relevance-chip ${escapeHtml(item.status)}">${readableVisualRelevanceState(item.status)}</span>
        </div>
        <div class="image-relevance-text">${escapeHtml(item.sentence_text)}</div>
        <div class="muted">${escapeHtml(item.reason)}</div>
        <div class="image-relevance-meta">
          <span><strong>파일</strong>: ${escapeHtml(item.path || "(미연결)")}</span>
          <span><strong>코드</strong>: ${item.issue_codes.length > 0 ? escapeHtml(item.issue_codes.join(", ")) : "정상"}</span>
        </div>
      </article>
    `).join("");
  }

  if (project.body_image_mappings.length === 0) {
    imageGenMappings.innerHTML = '<div class="muted">아직 생성된 장면 매핑이 없습니다.</div>';
  } else {
    imageGenMappings.innerHTML = project.body_image_mappings.map((item) => {
      const mediaUrl = `/api/projects/${project.id}/media/${encodeURIComponent(item.path)}`;
      const review = candidateReviewForSentence(item.sentence_idx);
      const visionIssueCodes = Array.isArray(review.vision_qa_issue_codes) ? review.vision_qa_issue_codes.join(", ") : "";
      const styleReason = typeof review.style_consistency_reason === "string" ? review.style_consistency_reason : "";
      const visionReason = typeof review.vision_qa_reason === "string" ? review.vision_qa_reason : "";
      const repairIssueCodeLabels = Array.isArray(review.repair_issue_codes)
        ? review.repair_issue_codes.map((code) => readableIssueCode(String(code))).join(" | ")
        : "";
      const repairReason = typeof review.repair_reason === "string" ? review.repair_reason : "";
      const suggestedRepairReason = typeof review.suggested_repair_reason === "string" ? review.suggested_repair_reason : "";
      const suggestedPromptG = previewText(review.suggested_prompt_g, 120);
      const suggestedPromptL = previewText(review.suggested_prompt_l, 120);
      const currentNegativePrompt = previewText(review.current_negative_prompt, 100);
      const suggestedNegativePrompt = previewText(review.suggested_negative_prompt, 100);
      const fallbackDowngradeApplied = review.fallback_downgrade_applied === true;
      const fallbackDowngradeReason = typeof review.fallback_downgrade_reason === "string" ? review.fallback_downgrade_reason : "";
      const operatorInterventionRequired = review.operator_intervention_required === true;
      const operatorInterventionReason = typeof review.operator_intervention_reason === "string" ? review.operator_intervention_reason : "";
      const repairState = review.repair_attempted === true
        ? "retry executed"
        : (repairReason ? "retry skipped" : "none");
      const repairSummary = repairReason
        ? `${repairState} | ${readableRepairReason(repairReason)}${repairIssueCodeLabels ? ` | ${repairIssueCodeLabels}` : ""}`
        : "none";
      const operatorSummary = operatorInterventionRequired
        ? `<div><strong>Operator</strong>: ${escapeHtml(readableOperatorInterventionReason(operatorInterventionReason))}</div>`
        : "";
      const fallbackSummary = fallbackDowngradeApplied
        ? `<div><strong>Fallback 강등</strong>: ${escapeHtml(readableRepairReason("fallback_downgrade"))}${fallbackDowngradeReason ? ` | ${escapeHtml(fallbackDowngradeReason)}` : ""}</div>`
        : "";
      const suggestionSummary = suggestedRepairReason
        ? `
            <div><strong>Suggested Fix</strong>: ${escapeHtml(readableRepairReason(suggestedRepairReason))}</div>
            ${suggestedPromptG ? `<div class="muted"><strong>Prompt G</strong>: ${escapeHtml(suggestedPromptG)}</div>` : ""}
            ${suggestedPromptL && suggestedPromptL !== suggestedPromptG ? `<div class="muted"><strong>Prompt L</strong>: ${escapeHtml(suggestedPromptL)}</div>` : ""}
            ${(currentNegativePrompt || suggestedNegativePrompt) ? `<div class="muted"><strong>Negative</strong>: ${escapeHtml(currentNegativePrompt || "(empty)")}${suggestedNegativePrompt ? ` -> ${escapeHtml(suggestedNegativePrompt)}` : ""}</div>` : ""}
            <div class="row"><button class="btn" type="button" data-action="apply-repair-suggestion" data-sentence-idx="${item.sentence_idx}">Apply Suggestion</button></div>
          `
        : "";
      return `
        <article class="image-gen-mapping-item">
          <div class="image-gen-mapping-preview">
            <img src="${escapeHtml(buildMediaUrl(mediaUrl))}" alt="${escapeHtml(item.path)}">
          </div>
          <div class="image-gen-mapping-body">
            <div><strong>문장</strong>: ${item.sentence_idx}</div>
            <div><strong>파일</strong>: ${escapeHtml(item.path)}</div>
            <div><strong>선택</strong>: ${escapeHtml(String(item.selected_reason || "legacy"))}</div>
            <div><strong>후보</strong>: ${item.candidate_index ? `${item.candidate_index} / ${item.candidate_total || 1}` : "1 / 1"}</div>
            <div><strong>후보 점수</strong>: ${readableScore(item.candidate_score)}</div>
            <div><strong>Vision QA</strong>: ${readableScore(review.vision_qa_score)}${visionIssueCodes ? ` | ${escapeHtml(visionIssueCodes)}` : ""}</div>
            <div><strong>Style 일관성</strong>: ${readableScore(review.style_consistency_score)}</div>
            <div><strong>QA 메모</strong>: ${escapeHtml(visionReason || styleReason || "추가 이슈 없음")}</div>
            <div><strong>Repair</strong>: ${escapeHtml(repairSummary)}</div>
            ${fallbackSummary}
            ${operatorSummary}
            ${suggestionSummary}
            <div><strong>프롬프트</strong>: ${escapeHtml(item.prompt || "")}</div>
          </div>
        </article>
      `;
    }).join("");
  }

  if (!project.scene_plan || project.scene_plan.scenes.length === 0) {
    imageScenePlanList.innerHTML = '<div class="muted">아직 scene plan 이 없습니다.</div>';
    return;
  }
  imageScenePlanList.innerHTML = project.scene_plan.scenes.map((scene) => `
    <article class="image-scene-plan-item">
      <div><strong>Scene ${scene.idx}</strong> | 문장 ${scene.sentence_idx} | ${escapeHtml(scene.region)} | ${scene.duration_sec.toFixed(1)}s</div>
      <div><strong>의도</strong>: ${escapeHtml(scene.visual_intent)}</div>
      <div><strong>프롬프트</strong>: ${escapeHtml(scene.prompt)}</div>
      <div><strong>미디어</strong>: ${escapeHtml(scene.media_path || "(미연결)")}</div>
      <div><strong>스타일</strong>: ${escapeHtml(scene.style)}</div>
    </article>
  `).join("");

  if (!project.render_plan || !project.render_plan.segments || project.render_plan.segments.length === 0) {
    imageRenderPlanList.innerHTML = '<div class="muted">아직 render plan 이 없습니다.</div>';
    return;
  }
  const renderPlan = /** @type {RenderPlan} */ (project.render_plan);
  imageRenderPlanList.innerHTML = renderPlan.segments.map(
    /** @param {{ region: Region, start: number, end: number, media: { path: string, kind: MediaKind }[], motion: string, effect: string, caption_style: string }} segment
     *  @param {number} index
     */
    (segment, index) => `
    <article class="image-scene-plan-item">
      <div><strong>Segment ${index + 1}</strong> | ${escapeHtml(segment.region)} | ${segment.start.toFixed(1)}s - ${segment.end.toFixed(1)}s</div>
      <div><strong>미디어</strong>: ${segment.media.length > 0 ? segment.media.map(
        /** @param {{ path: string, kind: MediaKind }} item */
        (item) => escapeHtml(item.path),
      ).join(", ") : "(미연결)"}</div>
      <div><strong>모션</strong>: ${escapeHtml(segment.motion)} | <strong>효과</strong>: ${escapeHtml(segment.effect)} | <strong>자막</strong>: ${escapeHtml(segment.caption_style)}</div>
    </article>
  `).join("");
}

/**
 * @param {string} value
 * @returns {string}
 */
function sceneCardChip(value) {
  return value ? `<span class="chip">${escapeHtml(value)}</span>` : "";
}

/**
 * @returns {Promise<void>}
 */
async function loadSceneCards() {
  const project = requireCurrent();
  sceneCardsRefreshButton.disabled = true;
  try {
    sceneCards = /** @type {SceneCard[]} */ (await requestJson(`/api/projects/${project.id}/scene-cards`));
    renderSceneCards();
  } finally {
    sceneCardsRefreshButton.disabled = false;
  }
}

/**
 * @returns {void}
 */
function renderSceneCards() {
  const project = requireCurrent();
  if (sceneCards.length === 0) {
    sceneCardList.innerHTML = '<div class="muted">대본을 저장하면 문장별 장면 카드가 여기에 표시됩니다.</div>';
    return;
  }
  sceneCardList.innerHTML = sceneCards.map((card) => {
    const visualUrl = card.visual_asset_path
      ? `/api/projects/${project.id}/media/${encodeURIComponent(card.visual_asset_path)}`
      : "";
    const voiceUrl = card.voice_asset_path
      ? `/api/projects/${project.id}/tts/${encodeURIComponent(card.voice_asset_path)}`
      : "";
    const subtitleState = card.subtitle_override ? "자막 개별설정" : "전체 자막";
    return `
      <article class="scene-card ${card.locked ? "locked" : ""}" data-sentence-idx="${card.sentence_idx}">
        <div class="scene-card-preview">
          ${visualUrl ? `<img src="${escapeHtml(buildMediaUrl(visualUrl))}" alt="${escapeHtml(card.visual_asset_path)}">` : '<div class="scene-card-empty">No image</div>'}
        </div>
        <div class="scene-card-body">
          <div class="row between scene-card-title">
            <strong>${escapeHtml(card.scene_id)} · 문장 ${card.sentence_idx + 1}</strong>
            <label class="scene-lock-row"><input type="checkbox" data-scene-action="lock" ${card.locked ? "checked" : ""}> Lock</label>
          </div>
          <div class="scene-card-text">${escapeHtml(card.text)}</div>
          <div class="scene-card-meta">
            ${sceneCardChip(card.region)}
            ${sceneCardChip(`${card.duration_sec.toFixed(1)}s`)}
            ${sceneCardChip(card.flow_status || "flow 미생성")}
            ${sceneCardChip(subtitleState)}
          </div>
          <div class="scene-card-assets">
            <span><strong>음성</strong>: ${voiceUrl ? `<audio src="${escapeHtml(buildMediaUrl(voiceUrl))}" controls preload="none"></audio>` : "미생성"}</span>
            <span><strong>이미지</strong>: ${escapeHtml(card.visual_asset_path || "미연결")}</span>
          </div>
          <div class="scene-card-controls">
            <label>움직임
              <select data-scene-action="motion">
                ${sceneMotionOptions(card.motion)}
              </select>
            </label>
            <button class="btn" type="button" data-scene-action="subtitle-large">큰 자막</button>
            <button class="btn" type="button" data-scene-action="subtitle-clear" ${card.subtitle_override ? "" : "disabled"}>개별 자막 해제</button>
          </div>
          ${card.warnings.length ? `<div class="scene-card-warnings">${card.warnings.map((warning) => `<span>${escapeHtml(warning)}</span>`).join("")}</div>` : ""}
        </div>
      </article>
    `;
  }).join("");
}

/**
 * @param {string} selected
 * @returns {string}
 */
function sceneMotionOptions(selected) {
  const options = [
    ["none", "움직임 없음"],
    ["slow_zoom_in", "보통 움직임"],
    ["slow_zoom_out", "느린 축소"],
    ["pan_left", "좌측 이동"],
    ["pan_right", "우측 이동"],
    ["pan_up", "위로 이동"],
    ["pan_down", "아래로 이동"],
    ["parallax_light", "입체감"],
    ["push_in_fade", "확대+페이드"],
    ["documentary_hold", "다큐 고정"],
    ["beat_cut", "비트 컷"],
    ["still_locked", "완전 고정"],
  ];
  return options.map(([value, label]) => (
    `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`
  )).join("");
}

/**
 * @param {number} sentenceIdx
 * @param {Record<string, unknown>} patch
 * @returns {Promise<void>}
 */
async function patchSceneCard(sentenceIdx, patch) {
  const project = requireCurrent();
  const updatedCard = /** @type {SceneCard} */ (await requestJson(`/api/projects/${project.id}/scene-cards/${sentenceIdx}`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(patch),
  }));
  sceneCards = sceneCards.map((card) => (card.sentence_idx === sentenceIdx ? updatedCard : card));
  renderSceneCards();
}

/**
 * @param {FlowPromptManifest | null} manifest
 * @returns {void}
 */
function renderFlowPromptList(manifest) {
  if (!manifest || manifest.entries.length === 0) {
    flowPromptList.innerHTML = '<div class="muted">Flow 프롬프트를 생성하면 문장별 작업 큐가 여기에 표시됩니다.</div>';
    return;
  }
  flowAspectRatioSelect.value = manifest.aspect_ratio || "9:16";
  flowPromptList.innerHTML = manifest.entries.map((entry) => `
    <article class="image-gen-mapping-item">
      <div class="image-gen-mapping-body">
        <div class="row between">
          <strong>문장 ${entry.sentence_idx + 1} · ${escapeHtml(entry.section)}</strong>
          <span class="chip">${escapeHtml(entry.status || "prompt_ready")}</span>
        </div>
        <div><strong>대본</strong>: ${escapeHtml(entry.narration)}</div>
        <div><strong>핵심</strong>: ${escapeHtml(entry.core_keyword || "-")} | <strong>시각</strong>: ${escapeHtml(entry.visual_keyword || "-")}</div>
        <textarea class="flow-prompt-text" rows="7" readonly>${escapeHtml(entry.prompt)}</textarea>
        <div class="row">
          <button class="btn" type="button" data-flow-action="copy" data-sentence-idx="${entry.sentence_idx}">프롬프트 복사</button>
          <button class="btn" type="button" data-flow-action="attach" data-sentence-idx="${entry.sentence_idx}">Flow 결과 파일 첨부</button>
          ${entry.asset_path ? `<span class="muted">연결됨: ${escapeHtml(entry.asset_path)}</span>` : '<span class="muted">아직 asset 없음</span>'}
        </div>
      </div>
    </article>
  `).join("");
}

/**
 * @returns {Promise<void>}
 */
async function loadFlowPrompts() {
  const project = requireCurrent();
  try {
    flowPromptManifest = /** @type {FlowPromptManifest} */ (await requestJson(`/api/flow/manifest/${project.id}`));
  } catch {
    flowPromptManifest = null;
  }
  renderFlowPromptList(flowPromptManifest);
}

/**
 * @returns {Promise<void>}
 */
async function generateFlowPrompts() {
  const project = requireCurrent();
  flowPromptsGenerateButton.disabled = true;
  try {
    flowPromptManifest = /** @type {FlowPromptManifest} */ (
      await requestJson(`/api/flow/prompts/${project.id}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          aspect_ratio: flowAspectRatioSelect.value || "9:16",
          mode: "assisted",
        }),
      })
    );
    renderFlowPromptList(flowPromptManifest);
    imageVisualModeSelect.value = "flow_assisted";
    await saveFeatureSettings();
    toast("Flow 프롬프트를 생성했습니다.");
  } finally {
    flowPromptsGenerateButton.disabled = false;
  }
}

/**
 * @param {number} sentenceIdx
 * @returns {FlowPromptEntry | null}
 */
function flowEntryBySentence(sentenceIdx) {
  if (!flowPromptManifest) return null;
  return flowPromptManifest.entries.find((entry) => entry.sentence_idx === sentenceIdx) || null;
}

/**
 * @param {number} sentenceIdx
 * @returns {Promise<void>}
 */
async function copyFlowPrompt(sentenceIdx) {
  const entry = flowEntryBySentence(sentenceIdx);
  if (!entry) {
    toast("복사할 Flow 프롬프트가 없습니다.");
    return;
  }
  await navigator.clipboard.writeText(entry.prompt);
  toast(`문장 ${sentenceIdx + 1} Flow 프롬프트를 복사했습니다.`);
}

/**
 * @param {File | null} file
 * @returns {Promise<void>}
 */
async function uploadFlowAsset(file) {
  const project = requireCurrent();
  if (!file || pendingFlowAssetSentenceIdx === null) {
    return;
  }
  const entry = flowEntryBySentence(pendingFlowAssetSentenceIdx);
  const form = new FormData();
  form.append("file", file);
  form.append("prompt", entry ? entry.prompt : "");
  const response = /** @type {{project: Project, manifest: FlowPromptManifest}} */ (
    await requestJson(`/api/flow/assets/${project.id}/${pendingFlowAssetSentenceIdx}`, {
      method: "POST",
      body: form,
    })
  );
  current = response.project;
  flowPromptManifest = response.manifest;
  pendingFlowAssetSentenceIdx = null;
  flowAssetInput.value = "";
  renderFlowPromptList(flowPromptManifest);
  renderMedia();
  renderImageGenPanel();
  toast("Flow 결과 파일을 문장 asset으로 연결했습니다.");
}

/**
 * @returns {void}
 */
function renderMedia() {
  const project = requireCurrent();
  if (!project) return;
  if (project.media_order.length === 0) {
    mediaGrid.innerHTML = "";
    mediaCount.textContent = "0 items";
    mediaPreviewStage.innerHTML = '<div class="media-empty">아직 업로드한 미디어가 없습니다.</div>';
    mediaPreviewMeta.textContent = "이미지나 영상을 업로드하면 여기에서 확인하고 순서를 조정할 수 있습니다.";
    return;
  }

  if (!selectedMediaName || !project.media_order.includes(selectedMediaName)) {
    selectedMediaName = project.media_order[0];
  }

  mediaGrid.innerHTML = "";
  mediaCount.textContent = `${project.media_order.length} items`;

  project.media_order.forEach((name, index) => {
    const kind = mediaKindFromName(name);
    const url = `/api/projects/${project.id}/media/${encodeURIComponent(name)}`;
    const card = document.createElement("article");
    card.className = "media-item";
    card.draggable = true;
    card.dataset.name = name;
    card.classList.toggle("active", name === selectedMediaName);
    card.innerHTML = `
      <div class="media-thumb">
        ${kind === "video" ? `<video src="${escapeHtml(buildMediaUrl(url))}" muted preload="metadata"></video>` : `<img src="${escapeHtml(buildMediaUrl(url))}" alt="${escapeHtml(name)}">`}
      </div>
      <div class="media-item-body">
        <div class="media-item-top">
          <div>
            <div class="media-kind">${kind}</div>
            <div class="media-filename">${escapeHtml(name)}</div>
          </div>
          <div class="media-order-badge">${index + 1}</div>
        </div>
        <div class="media-actions">
          <button class="btn" type="button" data-action="left" ${index === 0 ? "disabled" : ""}>Left</button>
          <button class="btn" type="button" data-action="right" ${index === project.media_order.length - 1 ? "disabled" : ""}>Right</button>
          <button class="btn danger" type="button" data-action="delete">Delete</button>
        </div>
      </div>
    `;

    card.addEventListener("click", (event) => {
      const target = /** @type {HTMLElement} */ (event.target);
      if (target.dataset.action) {
        return;
      }
      selectedMediaName = name;
      renderMedia();
    });

    card.addEventListener("dragstart", () => {
      draggingMediaName = name;
      card.classList.add("dragging");
    });

    card.addEventListener("dragend", () => {
      draggingMediaName = null;
      card.classList.remove("dragging");
      queryAll(".media-item", mediaGrid).forEach((item) => item.classList.remove("drop-target"));
    });

    card.addEventListener("dragover", (event) => {
      event.preventDefault();
      card.classList.add("drop-target");
    });

    card.addEventListener("dragleave", () => {
      card.classList.remove("drop-target");
    });

    card.addEventListener("drop", (event) => {
      event.preventDefault();
      card.classList.remove("drop-target");
      if (!draggingMediaName || draggingMediaName === name) {
        return;
      }
      void persistMediaOrder(moveMediaBefore(project.media_order, draggingMediaName, name));
    });

    mediaGrid.appendChild(card);
  });

  const selectedName = selectedMediaName || project.media_order[0];
  const selectedKind = mediaKindFromName(selectedName);
  const selectedUrl = `/api/projects/${project.id}/media/${encodeURIComponent(selectedName)}`;
  mediaPreviewStage.innerHTML = selectedKind === "video"
    ? `<video src="${escapeHtml(buildMediaUrl(selectedUrl))}" controls muted></video>`
    : `<img src="${escapeHtml(buildMediaUrl(selectedUrl))}" alt="${escapeHtml(selectedName)}">`;
  mediaPreviewMeta.innerHTML = `
    <div><strong>파일</strong>: ${escapeHtml(selectedName)}</div>
    <div><strong>형식</strong>: ${selectedKind}</div>
    <div><strong>순서</strong>: ${project.media_order.indexOf(selectedName) + 1} / ${project.media_order.length}</div>
  `;
}

/**
 * @returns {void}
 */
function renderThumbnail() {
  const project = requireCurrent();
  if (!project) return;
  thumbnailDeleteButton.disabled = !project.thumbnail_file;
  if (!project.thumbnail_file) {
    thumbnailPreview.innerHTML = '<div class="media-empty">아직 업로드한 썸네일이 없습니다.</div>';
    thumbnailMeta.textContent = "YouTube 업로드용 썸네일을 별도로 관리할 수 있습니다.";
    return;
  }

  const thumbnailUrl = `/api/projects/${project.id}/thumbnail`;
  thumbnailPreview.innerHTML = `<img src="${escapeHtml(buildMediaUrl(thumbnailUrl))}" alt="YouTube thumbnail">`;
  thumbnailMeta.innerHTML = `
    <div><strong>파일</strong>: ${escapeHtml(project.thumbnail_file)}</div>
    <div><strong>용도</strong>: YouTube 업로드 시 자동 썸네일 설정</div>
  `;
}

/**
 * @returns {void}
 */
function renderBgmMeta() {
  const project = requireCurrent();
  if (!project) return;
  bgmDeleteButton.disabled = !project.bgm_file;
  bgmMeta.textContent = project.bgm_file
    ? `BGM file: ${project.bgm_file}`
    : "No BGM uploaded.";
}

/**
 * @returns {void}
 */
function renderFeatureControls() {
  const project = requireCurrent();
  if (!project) return;
  featureKenburnsSelect.value = project.kenburns_enabled ? "on" : "off";
  featureBgmVolumeInput.value = String(project.bgm_volume_db);
  featureBgmDuckingSelect.value = project.bgm_ducking_enabled ? "on" : "off";
  featureRenderLandscapeInput.checked = project.render_formats.includes("landscape");
  featureRenderShortsInput.checked = project.render_formats.includes("shorts");
  imageVisualModeSelect.value = project.visual_source_mode || "upload_only";
  const rawOptions = /** @type {Record<string, unknown>} */ (project.body_image_options || {});
  imageStylePresetSelect.value = typeof rawOptions.style_preset === "string"
    ? rawOptions.style_preset
    : recommendedStylePresetForProject(project);
  featureHyperframesOverlayInput.checked = rawOptions.hyperframes_overlay_enabled === true;
  featureHyperframesRequiredInput.checked = rawOptions.hyperframes_overlay_required === true;
  featureHyperframesRequiredInput.disabled = !featureHyperframesOverlayInput.checked;
}

/**
 * @param {Project} project
 * @returns {string}
 */
function recommendedStylePresetForProject(project) {
  if (project.content_mode === "bible_longform") {
    return "";
  }
  const haystack = [
    project.title,
    project.compiled_script,
    project.script,
    ...project.sentences,
    ...(project.source_draft_fact_notes || []).map((item) => item.note || ""),
  ].join(" ").toLowerCase();
  const needles = [
    "ai",
    "agent",
    "agents",
    "gpu",
    "browser",
    "headless",
    "automation",
    "model",
    "models",
    "datacenter",
    "data center",
    "power",
    "electricity",
    "payment",
    "message",
    "messages",
    "schedule",
    "workflow",
    "compare",
    "comparison",
    "전력",
    "브라우저",
    "자동화",
    "에이전트",
    "데이터센터",
    "결제",
    "메시지",
    "일정",
  ];
  return needles.some((needle) => haystack.includes(needle)) ? "editorial_symbolic" : "";
}

/**
 * @returns {string}
 */
function preferredStyleReferenceValue() {
  const project = requireCurrent();
  const typedValue = imageStyleReferenceInput.value.trim();
  if (typedValue) {
    return typedValue;
  }
  if (project.thumbnail_file) {
    return "__auto__";
  }
  const selectedName = selectedMediaName || project.media_order[0] || "";
  if (selectedName && mediaKindFromName(selectedName) === "image") {
    return selectedName;
  }
  const firstImage = project.media_order.find((name) => mediaKindFromName(name) === "image");
  if (firstImage) {
    return firstImage;
  }
  return "__auto__";
}

/**
 * @returns {string[]}
 */
function collectImageReferenceOptions() {
  const project = requireCurrent();
  /** @type {string[]} */
  const options = [];
  if (project.thumbnail_file) {
    options.push("__auto__");
    options.push(project.thumbnail_file);
  }
  project.media_order.forEach((name) => {
    if (mediaKindFromName(name) === "image") {
      options.push(name);
    }
  });
  project.body_image_mappings.forEach((item) => {
    if (item.path) {
      options.push(item.path);
    }
  });
  return [...new Set(options.filter(Boolean))];
}

/**
 * @returns {void}
 */
function syncImageReferenceOptions() {
  imageReferenceOptions.innerHTML = collectImageReferenceOptions().map((value) => (
    `<option value="${escapeHtml(value)}"></option>`
  )).join("");
}

/**
 * @returns {string}
 */
function preferredControlImageValue() {
  const project = requireCurrent();
  const typedValue = imageControlReferenceInput.value.trim();
  if (typedValue) {
    return typedValue;
  }
  const selectedName = selectedMediaName || project.media_order[0] || "";
  if (selectedName && mediaKindFromName(selectedName) === "image") {
    return selectedName;
  }
  if (project.thumbnail_file) {
    return "__auto__";
  }
  const generatedImage = project.body_image_mappings.find((item) => item.path)?.path || "";
  if (generatedImage) {
    return generatedImage;
  }
  const firstImage = project.media_order.find((name) => mediaKindFromName(name) === "image");
  if (firstImage) {
    return firstImage;
  }
  return "__auto__";
}

/**
 * @param {number} sentenceIdx
 * @returns {Record<string, unknown>}
 */
function candidateReviewForSentence(sentenceIdx) {
  const project = requireCurrent();
  const rawOptions = /** @type {Record<string, unknown>} */ (project.body_image_options || {});
  if (!rawOptions || typeof rawOptions !== "object") {
    return {};
  }
  const candidateReviews = /** @type {Record<string, unknown>} */ (rawOptions.candidate_reviews || {});
  const review = candidateReviews[String(sentenceIdx)];
  return review && typeof review === "object" ? /** @type {Record<string, unknown>} */ (review) : {};
}

/**
 * @returns {void}
 */
function clearManualPromptOverrides() {
  manualPromptOverrides = { promptG: "", promptL: "" };
}

/**
 * @param {number} sentenceIdx
 * @returns {void}
 */
function applyRepairSuggestionForSentence(sentenceIdx) {
  const project = requireCurrent();
  const review = candidateReviewForSentence(sentenceIdx);
  const suggestedPositivePrompt = typeof review.suggested_positive_prompt === "string" ? review.suggested_positive_prompt.trim() : "";
  const suggestedNegativePrompt = typeof review.suggested_negative_prompt === "string" ? review.suggested_negative_prompt.trim() : "";
  const suggestedPromptG = typeof review.suggested_prompt_g === "string" ? review.suggested_prompt_g.trim() : "";
  const suggestedPromptL = typeof review.suggested_prompt_l === "string" ? review.suggested_prompt_l.trim() : "";
  const suggestedRepairReason = typeof review.suggested_repair_reason === "string" ? review.suggested_repair_reason.trim() : "";
  if (!suggestedPositivePrompt && !suggestedPromptG && !suggestedPromptL) {
    toast("적용할 repair suggestion이 없습니다.");
    return;
  }
  imageSentenceIdxInput.value = String(sentenceIdx);
  imagePositivePromptInput.value = suggestedPositivePrompt || suggestedPromptG || suggestedPromptL;
  if (suggestedNegativePrompt) {
    imageNegativePromptInput.value = suggestedNegativePrompt;
  }
  manualPromptOverrides = {
    promptG: suggestedPromptG,
    promptL: suggestedPromptL,
  };
  imageGenState.textContent =
    `Repair suggestion applied | 문장 ${sentenceIdx} | ${suggestedRepairReason || "manual fix ready"} | ${project.sentences[sentenceIdx] || ""}`;
  imageGenState.className = "card ok";
}

/**
 * @param {unknown} value
 * @param {number} maxLength
 * @returns {string}
 */
function previewText(value, maxLength = 140) {
  if (typeof value !== "string") {
    return "";
  }
  const text = value.trim();
  if (!text) {
    return "";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}

/**
 * @param {string} code
 * @returns {string}
 */
function readableIssueCode(code) {
  const labels = /** @type {Record<string, string>} */ ({
    RAW_TEXT_VISUAL_TARGET: "원문 문장이 그대로 시각 목표에 섞임",
    GENERIC_SYMBOL_WITHOUT_ALLOW: "자동차/체크리스트 같은 generic 상징으로 새는 중",
    DIAGRAM_STYLE_COLLISION: "다이어그램 장면에 실사/시네마틱 표현이 섞임",
    DIAGRAM_COMPLEXITY_RISK: "다이어그램이 너무 복잡하거나 배경이 과함",
    DIAGRAM_TEXT_CONTROL_MISSING: "텍스트 억제 네거티브가 부족함",
    BOOK_TEXT_RISK: "책/문서/화면에 읽을 수 있는 글자가 생길 위험",
    CLOSEUP_RISK: "손/화면 클로즈업으로 잘릴 위험",
    MISSING_FRAMING_SLOT: "구도 앵커가 부족함",
    MISSING_CAMERA_TECHNICAL_SLOT: "카메라/기술 앵커가 부족함",
    LITERAL_SIMILE_IGNORED: "직유/비유 핵심이 프롬프트에 반영되지 않음",
    FORBIDDEN_OBJECT_IN_NEGATIVE_MISSING: "금지 오브젝트 네거티브가 비어 있음",
    ESSAY_ROAD_WITHOUT_VEHICLE_BAN: "길 장면인데 차량 차단 네거티브가 부족함",
  });
  return labels[code] || code;
}

/**
 * @param {string} reason
 * @returns {string}
 */
function readableRepairReason(reason) {
  const labels = /** @type {Record<string, string>} */ ({
    must_show_reinforced: "핵심 시각 요소를 더 강하게 고정",
    generic_drift_blocked: "generic 상징으로 새는 경로 차단",
    diagram_style_reinforced: "다이어그램 스타일을 다시 고정",
    diagram_simplified: "장면 복잡도를 낮춤",
    text_risk_blocked: "읽히는 텍스트 위험 차단",
    framing_repaired: "구도/프레이밍 앵커 보강",
    camera_anchor_added: "카메라/기술 앵커 보강",
    generic_retry_reinforcement: "기본 repair 강화",
    preserve_control_layout: "ControlNet 구도 유지 힌트 추가",
    preserve_style_reference: "Style reference 톤 유지 힌트 추가",
    preserve_lora_style: "LoRA 스타일/캐릭터 일관성 유지 힌트 추가",
    repair_retry_skipped_heavy_path: "heavy path라 자동 재시도는 건너뜀",
    repair_retry_skipped_gpu_busy: "GPU 사용 중이라 자동 재시도는 건너뜀",
    fallback_downgrade: "안전 fallback 장면으로 강등",
  });
  if (reason.startsWith("retry_limit_reached:")) {
    return `재시도 한도 도달 (${reason.slice("retry_limit_reached:".length) || "score gate"})`;
  }
  return reason.split(",").map((part) => labels[part.trim()] || part.trim()).join(" + ");
}

/**
 * @param {string} reason
 * @returns {string}
 */
function readableOperatorInterventionReason(reason) {
  if (reason.startsWith("operator_review_required:")) {
    return `자동 복구 후에도 ${reason.slice("operator_review_required:".length) || "score gate"} 문제가 남아 운영자 확인이 필요합니다.`;
  }
  return reason || "운영자 확인 필요";
}

/**
 * @param {unknown} value
 * @returns {string}
 */
function readableScore(value) {
  return typeof value === "number" ? value.toFixed(2) : "-";
}

/**
 * @returns {void}
 */
function syncImageProfileUi() {
  const styleMode = imageGenerationProfileSelect.value === "sdxl_style_reference";
  const controlMode = imageGenerationProfileSelect.value === "sdxl_controlnet_depth";
  imageStyleReferenceInput.disabled = !styleMode;
  imageStyleStrengthInput.disabled = !styleMode;
  imageControlReferenceInput.disabled = !controlMode;
  imageControlStrengthInput.disabled = !controlMode;
  let hint = "Style reference profile uses a project thumbnail, uploaded image, or explicit file path to keep tone more consistent across scenes.";
  if (styleMode) {
    hint = "Style reference is active. Leave the field blank to use the project thumbnail or the first uploaded image automatically.";
    if (imageLoraNameInput.value.trim()) {
      hint += " LoRA and style reference will use the mixed workflow.";
    }
  } else if (controlMode) {
    hint = "ControlNet Depth is active. Pick an image with clear structure, or leave it blank to fall back to the thumbnail / first image automatically.";
  }
  imageStyleReferenceHint.textContent = hint;
}

/**
 * @returns {{kenburns_enabled: boolean, bgm_volume_db: number, bgm_ducking_enabled: boolean, render_formats: RenderFormat[], visual_source_mode: VisualSourceMode, style_preset: string, hyperframes_overlay_enabled: boolean, hyperframes_overlay_required: boolean}}
 */
function readFeatureInputs() {
  /** @type {RenderFormat[]} */
  const renderFormats = [];
  if (featureRenderLandscapeInput.checked) {
    renderFormats.push("landscape");
  }
  if (featureRenderShortsInput.checked) {
    renderFormats.push("shorts");
  }
  if (renderFormats.length === 0) {
    renderFormats.push("landscape");
  }
  return {
    kenburns_enabled: featureKenburnsSelect.value === "on",
    bgm_volume_db: numberInRange(featureBgmVolumeInput.value, -20, -40, 6),
    bgm_ducking_enabled: featureBgmDuckingSelect.value === "on",
    render_formats: renderFormats,
    visual_source_mode: /** @type {VisualSourceMode} */ (imageVisualModeSelect.value || "upload_only"),
    style_preset: imageStylePresetSelect.value || "",
    hyperframes_overlay_enabled: featureHyperframesOverlayInput.checked,
    hyperframes_overlay_required: featureHyperframesOverlayInput.checked && featureHyperframesRequiredInput.checked,
  };
}

/**
 * @param {File | null} file
 * @returns {Promise<void>}
 */
async function uploadThumbnail(file) {
  if (!file) {
    return;
  }
  const project = requireCurrent();
  const formData = new FormData();
  formData.append("file", file);
  const response = /** @type {ThumbnailUploadResponse} */ (
    await requestJson(`/api/projects/${project.id}/thumbnail`, {
      method: "POST",
      body: formData,
    })
  );
  current = response.project;
  thumbnailInput.value = "";
  renderThumbnail();
  toast("썸네일을 업로드했습니다.");
}

/**
 * @returns {Promise<void>}
 */
async function deleteThumbnail() {
  const project = requireCurrent();
  current = /** @type {Project} */ (
    await requestJson(`/api/projects/${project.id}/thumbnail`, {
      method: "DELETE",
    })
  );
  renderThumbnail();
  toast("썸네일을 삭제했습니다.");
}

/**
 * @param {File | null} file
 * @returns {Promise<void>}
 */
async function uploadBgm(file) {
  if (!file) {
    return;
  }
  const project = requireCurrent();
  const formData = new FormData();
  formData.append("file", file);
  const response = await requestJson(`/api/projects/${project.id}/bgm`, {
    method: "POST",
    body: formData,
  });
  current = /** @type {Project} */ (response.project);
  bgmInput.value = "";
  renderBgmMeta();
  renderFeatureControls();
  toast("BGM uploaded.");
}

/**
 * @returns {Promise<void>}
 */
async function deleteBgm() {
  const project = requireCurrent();
  current = /** @type {Project} */ (await requestJson(`/api/projects/${project.id}/bgm`, {
    method: "DELETE",
  }));
  renderBgmMeta();
  renderFeatureControls();
  toast("BGM deleted.");
}

/**
 * @returns {Promise<void>}
 */
async function saveFeatureSettings() {
  const project = requireCurrent();
  const payload = readFeatureInputs();
  const response = await requestJson(`/api/projects/${project.id}/features`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  current = /** @type {Project} */ (response.project);
  renderFeatureControls();
  renderBgmMeta();
  renderImageGenPanel();
  toast("Render settings saved.");
}

/**
 * @returns {Promise<void>}
 */
async function enqueueImageGen() {
  const project = requireCurrent();
  const sentenceIdx = numberInRange(imageSentenceIdxInput.value, 0, 0, 99999);
  const loraName = imageLoraNameInput.value.trim();
  const generationProfile = imageGenerationProfileSelect.value || "";
  const styleReferenceImage = generationProfile === "sdxl_style_reference" ? preferredStyleReferenceValue() : "";
  const controlImage = generationProfile === "sdxl_controlnet_depth" ? preferredControlImageValue() : "";
  const positivePrompt = imagePositivePromptInput.value.trim()
    || project.sentences[sentenceIdx]
    || project.sentences[0]
    || "";
  if (!positivePrompt) {
    throw new Error("이미지 생성 프롬프트가 비어 있습니다.");
  }

  const featurePayload = readFeatureInputs();
  current = /** @type {Project} */ ((await requestJson(`/api/projects/${project.id}/features`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(featurePayload),
  })).project);

  await requestJson(`/api/projects/${project.id}/comfyui/job`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      template_id: "txt2img_sdxl_basic",
      checkpoint: imageCheckpointInput.value.trim() || "sd_xl_base_1.0.safetensors",
      positive_prompt: positivePrompt,
      positive_prompt_g: manualPromptOverrides.promptG,
      positive_prompt_l: manualPromptOverrides.promptL,
      negative_prompt: imageNegativePromptInput.value.trim(),
      width: numberInRange(imageWidthInput.value, 1024, 256, 2048),
      height: numberInRange(imageHeightInput.value, 576, 256, 2048),
      seed: numberInRange(imageSeedInput.value, 1, 0, 2147483647),
      generation_profile: generationProfile,
      lora_name: loraName,
      lora_strength: numberInRange(imageLoraStrengthInput.value, 0.8, 0, 2),
      style_reference_image: styleReferenceImage,
      style_reference_strength: numberInRange(imageStyleStrengthInput.value, 0.65, 0, 2),
      control_image: controlImage,
      control_strength: numberInRange(imageControlStrengthInput.value, 0.75, 0, 2),
      filename_prefix: `project_${project.id}`,
      client_id: `newauto-${project.id}`,
      sentence_idx: sentenceIdx,
      prompt: positivePrompt,
    }),
  });

  current = {
    ...requireCurrent(),
    body_image_state: "queued",
    body_image_progress: 0,
    body_image_phase: "queued",
    body_image_last_log: "Queued ComfyUI image generation.",
    body_image_error: "",
    visual_source_mode: featurePayload.visual_source_mode,
  };
  renderFeatureControls();
  renderImageGenPanel();
  toast("이미지 생성 작업을 큐에 등록했습니다.");
}

/**
 * @returns {Promise<void>}
 */
async function suggestImagePrompt() {
  const project = requireCurrent();
  const sentenceIdx = numberInRange(imageSentenceIdxInput.value, 0, 0, 99999);
  const featurePayload = readFeatureInputs();
  current = /** @type {Project} */ ((await requestJson(`/api/projects/${project.id}/features`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(featurePayload),
  })).project);
  const payload = /** @type {{
   *   sentence_idx: number,
   *   sentence: string,
   *   positive_prompt: string,
   *   negative_prompt: string,
   *   style_hint: string,
   *   template_key: string,
   *   reference_names: string[],
   *   visual_source_mode: VisualSourceMode,
   *   requested_style_preset: string,
   *   recommended_style_preset: string,
   * }} */ (
    await requestJson(`/api/projects/${project.id}/comfyui/prompt-suggestion?sentence_idx=${sentenceIdx}`)
  );
  clearManualPromptOverrides();
  imagePositivePromptInput.value = payload.positive_prompt;
  if (!imageNegativePromptInput.value.trim()) {
    imageNegativePromptInput.value = payload.negative_prompt;
  }
  if (!imageStylePresetSelect.value && payload.recommended_style_preset) {
    imageStylePresetSelect.value = payload.recommended_style_preset;
  }
  imageGenState.textContent =
    `추천 완료 | 문장 ${payload.sentence_idx} | 템플릿 ${payload.template_key} | 스타일 ${payload.requested_style_preset || payload.recommended_style_preset || "default"} | ${payload.sentence}`;
  imageGenState.className = "card ok";
}

/**
 * @returns {Promise<void>}
 */
async function enqueueBatchImageGen() {
  const project = requireCurrent();
  const startIdx = numberInRange(imageBatchStartIdxInput.value, 0, 0, 99999);
  const count = numberInRange(imageBatchCountInput.value, 3, 1, 12);
  const loraName = imageLoraNameInput.value.trim();
  const generationProfile = imageGenerationProfileSelect.value || "";
  const styleReferenceImage = generationProfile === "sdxl_style_reference" ? preferredStyleReferenceValue() : "";
  const controlImage = generationProfile === "sdxl_controlnet_depth" ? preferredControlImageValue() : "";
  const featurePayload = readFeatureInputs();
  current = /** @type {Project} */ ((await requestJson(`/api/projects/${project.id}/features`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(featurePayload),
  })).project);

  const variantsPerScene = numberInRange(imageVariantsPerSceneInput.value, 1, 1, 5);
  const payload = /** @type {{ ok: boolean, count: number, variants_per_scene: number }} */ (await requestJson(`/api/projects/${project.id}/comfyui/job/batch-auto`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      checkpoint: imageCheckpointInput.value.trim() || "sd_xl_base_1.0.safetensors",
      start_idx: startIdx,
      count,
      width: numberInRange(imageWidthInput.value, 1024, 256, 2048),
      height: numberInRange(imageHeightInput.value, 576, 256, 2048),
      seed_base: numberInRange(imageSeedInput.value, 1, 0, 2147483647),
      generation_profile: generationProfile,
      seed_policy: imageSeedPolicySelect.value || "spaced",
      lora_name: loraName,
      lora_strength: numberInRange(imageLoraStrengthInput.value, 0.8, 0, 2),
      style_reference_image: styleReferenceImage,
      style_reference_strength: numberInRange(imageStyleStrengthInput.value, 0.65, 0, 2),
      control_image: controlImage,
      control_strength: numberInRange(imageControlStrengthInput.value, 0.75, 0, 2),
      filename_prefix: `project_${project.id}`,
      client_id: `newauto-${project.id}`,
      variants_per_scene: variantsPerScene,
    }),
  }));

  current = {
    ...requireCurrent(),
    body_image_state: "queued",
    body_image_progress: 0,
    body_image_phase: "queued",
    body_image_last_log: `Queued ${payload.count} ComfyUI image jobs (${payload.variants_per_scene} variant(s) per scene).`,
    body_image_error: "",
    visual_source_mode: featurePayload.visual_source_mode,
  };
  renderFeatureControls();
  renderImageGenPanel();
  toast(`이미지 ${payload.count}건 일괄 생성을 큐에 등록했습니다.`);
}

/**
 * @returns {Promise<void>}
 */
async function generateAllSimpleImagePrompts() {
  const project = requireCurrent();
  simplePromptAllButton.disabled = true;
  simpleMediaState.textContent = "전체 문장 이미지 프롬프트를 생성하는 중입니다...";
  try {
    const response = /** @type {{ ok: boolean, count: number, items: Array<Record<string, unknown>>, lmstudio_unload: Record<string, unknown>, project: Project }} */ (
      await requestJson(`/api/projects/${project.id}/media-simple/prompt-manifest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start_idx: 0,
          count: Math.max(1, Math.min(48, project.sentences.length || 1)),
          unload_lmstudio_after: true,
        }),
      })
    );
    simplePromptItems = response.items || [];
    current = response.project;
    renderImageGenPanel();
    const unloadOk = response.lmstudio_unload && response.lmstudio_unload.ok === true;
    toast(unloadOk ? "전체 이미지 프롬프트 생성 후 LM Studio를 종료했습니다." : "프롬프트 생성 완료. LM Studio 종료 확인이 필요합니다.");
  } finally {
    simplePromptAllButton.disabled = false;
  }
}

async function unloadLmStudioForSimpleMedia() {
  const project = requireCurrent();
  simpleLmstudioUnloadButton.disabled = true;
  try {
    const response = /** @type {{ ok: boolean, project: Project }} */ (
      await requestJson(`/api/projects/${project.id}/media-simple/lmstudio-unload`, {
        method: "POST",
      })
    );
    current = response.project;
    renderImageGenPanel();
    toast(response.ok ? "LM Studio를 종료/언로드했습니다." : "LM Studio 종료를 확인하지 못했습니다. LM Studio에서 모델을 직접 언로드해 주세요.");
  } finally {
    simpleLmstudioUnloadButton.disabled = false;
  }
}

async function copyAllSimplePrompts() {
  if (simplePromptItems.length === 0) {
    toast("복사할 이미지 프롬프트가 없습니다.");
    return;
  }
  const text = simplePromptItems.map((item) => {
    const idx = Number(item.sentence_idx || 0) + 1;
    return `[${idx}] ${String(item.positive_prompt || "")}`;
  }).join("\n\n");
  await navigator.clipboard.writeText(text);
  toast("전체 이미지 프롬프트를 복사했습니다.");
}

async function enqueueSimpleMediaImageGen() {
  const project = requireCurrent();
  const options = /** @type {Record<string, unknown>} */ (project.body_image_options || {});
  const promptCount = Number(options.simple_media_prompt_count || simplePromptItems.length || project.sentences.length || 1);
  const unload = /** @type {Record<string, unknown>} */ (options.simple_media_lmstudio_unload || {});
  if (unload.ok !== true) {
    throw new Error("이미지 생성 전에 LM Studio를 종료/언로드해 주세요.");
  }
  const generationProfile = imageGenerationProfileSelect.value || "";
  const styleReferenceImage = generationProfile === "sdxl_style_reference" ? preferredStyleReferenceValue() : "";
  const controlImage = generationProfile === "sdxl_controlnet_depth" ? preferredControlImageValue() : "";
  const featurePayload = {
    ...readFeatureInputs(),
    visual_source_mode: "comfyui_auto",
  };
  current = /** @type {Project} */ ((await requestJson(`/api/projects/${project.id}/features`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(featurePayload),
  })).project);
  const variantsPerScene = numberInRange(imageVariantsPerSceneInput.value, 1, 1, 5);
  const payload = /** @type {{ ok: boolean, count: number, variants_per_scene: number }} */ (await requestJson(`/api/projects/${project.id}/media-simple/comfyui/job`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      checkpoint: imageCheckpointInput.value.trim() || "sd_xl_base_1.0.safetensors",
      start_idx: 0,
      count: Math.max(1, Math.min(48, promptCount)),
      width: numberInRange(imageWidthInput.value, 1024, 256, 2048),
      height: numberInRange(imageHeightInput.value, 576, 256, 2048),
      seed_base: numberInRange(imageSeedInput.value, 1, 0, 2147483647),
      generation_profile: generationProfile,
      seed_policy: imageSeedPolicySelect.value || "spaced",
      lora_name: imageLoraNameInput.value.trim(),
      lora_strength: numberInRange(imageLoraStrengthInput.value, 0.8, 0, 2),
      style_reference_image: styleReferenceImage,
      style_reference_strength: numberInRange(imageStyleStrengthInput.value, 0.65, 0, 2),
      control_image: controlImage,
      control_strength: numberInRange(imageControlStrengthInput.value, 0.75, 0, 2),
      filename_prefix: `project_${project.id}`,
      client_id: `newauto-${project.id}`,
      variants_per_scene: variantsPerScene,
    }),
  }));
  current = {
    ...requireCurrent(),
    body_image_state: "queued",
    body_image_progress: 0,
    body_image_phase: "queued",
    body_image_last_log: `Queued ${payload.count} ComfyUI image jobs.`,
    body_image_error: "",
    visual_source_mode: "comfyui_auto",
  };
  renderFeatureControls();
  renderImageGenPanel();
  toast(`이미지 ${payload.count}건 생성을 큐에 등록했습니다.`);
}

async function buildScenePlan() {
  const project = requireCurrent();
  const renderFormat = featureRenderShortsInput.checked && !featureRenderLandscapeInput.checked ? "shorts" : "landscape";
  const scenePlan = /** @type {ScenePlan} */ (await requestJson(`/api/projects/${project.id}/scene-plan/build?render_format=${renderFormat}`, {
    method: "POST",
  }));
  current = {
    ...requireCurrent(),
    scene_plan: scenePlan,
  };
  renderImageGenPanel();
  toast(`Scene plan ${scenePlan.scenes.length}개를 생성했습니다.`);
}

/**
 * @returns {Promise<void>}
 */
async function buildRenderPlan() {
  const project = requireCurrent();
  const renderPlan = /** @type {RenderPlan} */ (
    await requestJson(`/api/projects/${project.id}/render-plan/build`, {
      method: "POST",
    })
  );
  current = {
    ...requireCurrent(),
    render_plan: renderPlan,
  };
  renderImageGenPanel();
  toast(`Render plan ${renderPlan.segments.length}개를 생성했습니다.`);
}

/**
 * @returns {Promise<void>}
 */
async function runPreflight() {
  const project = requireCurrent();
  const report = await requestJson(`/api/projects/${project.id}/preflight`);
  const payload = /** @type {{ ok: boolean, checks: { key: string, ok: boolean, message: string }[] }} */ (report);
  preflightResults.innerHTML = payload.checks.map((check) => (
    `<div><strong>${escapeHtml(check.key)}</strong>: ${escapeHtml(check.ok ? "ok" : "needs attention")} - ${escapeHtml(check.message)}</div>`
  )).join("");
  preflightResults.className = payload.ok ? "card ok" : "card warn";
}

/**
 * @returns {Promise<void>}
 */
async function runSystemHealth() {
  const payload = /** @type {{ ffmpeg_available: boolean, oauth_ready: boolean, omnivoice_python_found: boolean, omnivoice_python_path: string, omnivoice_import_ok: boolean, omnivoice_torch_ok: boolean, omnivoice_cuda_available: boolean, disk_free_gb: number, storage_path: string }} */ (
    await requestJson("/api/system/health")
  );
  systemHealthResults.innerHTML = `
    <div><strong>FFmpeg</strong>: ${payload.ffmpeg_available ? "ok" : "missing"}</div>
    <div><strong>OAuth</strong>: ${payload.oauth_ready ? "ready" : "missing client_secret.json"}</div>
    <div><strong>OmniVoice Python</strong>: ${payload.omnivoice_python_found ? "found" : "missing"}</div>
    <div><strong>OmniVoice Path</strong>: ${escapeHtml(payload.omnivoice_python_path || "-")}</div>
    <div><strong>OmniVoice Import</strong>: ${payload.omnivoice_import_ok ? "ok" : "failed"}</div>
    <div><strong>Torch / CUDA</strong>: ${payload.omnivoice_torch_ok ? "ok" : "failed"} / ${payload.omnivoice_cuda_available ? "cuda" : "cpu-or-missing"}</div>
    <div><strong>Disk Free</strong>: ${payload.disk_free_gb} GB</div>
    <div><strong>Storage</strong>: ${escapeHtml(payload.storage_path)}</div>
  `;
  systemHealthResults.className = "card";
}

/**
 * @returns {Promise<void>}
 */
async function runRenderReport() {
  const project = requireCurrent();
  const payload = /** @type {{
   *   status: string,
   *   autopilot_job_id: string,
   *   autopilot_input_mode: string,
   *   autopilot_state: AutopilotState,
   *   autopilot_phase: string,
   *   audio_duration_sec: number,
   *   subtitle_cue_count: number,
   *   render_plan_segment_count: number,
   *   missing_render_plan_media_count: number,
   *   fallback_used: boolean,
   *   outputs: { format: string, path: string, exists: boolean, size_bytes: number, duration_sec: number, hyperframes_overlay_status?: string, hyperframes_overlay_path?: string, hyperframes_overlay_pix_fmt?: string }[],
   *   segments: { region: string, media_path: string, motion: string, effect: string, caption_style: string, media_missing: boolean }[],
   *   final_scene_review_exists: boolean,
   *   final_scene_review_path: string,
   *   ffmpeg_log_tail: string,
   *   error: string
   * }} */ (
    await requestJson(`/api/projects/${project.id}/render-report`)
  );
  let finalSceneReview = null;
  if (payload.final_scene_review_exists) {
    try {
      finalSceneReview = await requestJson(`/api/projects/${project.id}/final-scene-review`);
    } catch (_error) {
      finalSceneReview = null;
    }
  }
  const outputs = payload.outputs.map(
    /** @param {{ format: string, exists: boolean, size_bytes: number, duration_sec: number, hyperframes_overlay_status?: string, hyperframes_overlay_path?: string, hyperframes_overlay_pix_fmt?: string }} item */
    (item) => {
      const overlay = item.hyperframes_overlay_status
        ? ` | overlay ${escapeHtml(item.hyperframes_overlay_status)}${item.hyperframes_overlay_pix_fmt ? ` (${escapeHtml(item.hyperframes_overlay_pix_fmt)})` : ""}${item.hyperframes_overlay_path ? ` | ${escapeHtml(item.hyperframes_overlay_path)}` : ""}`
        : "";
      return `<div><strong>${escapeHtml(item.format)}</strong>: ${item.exists ? `${(item.size_bytes / (1024 * 1024)).toFixed(1)} MB | ${item.duration_sec.toFixed(1)}s${overlay}` : `missing output file${overlay}`}</div>`;
    },
  ).join("");
  const segments = payload.segments.slice(0, 4).map(
    /** @param {{ region: string, motion: string, effect: string, caption_style: string, media_missing: boolean }} item */
    (item) => (
    `<div><strong>${escapeHtml(item.region)}</strong>: ${escapeHtml(item.motion)} / ${escapeHtml(item.effect)} / ${escapeHtml(item.caption_style)}${item.media_missing ? " | missing media" : ""}</div>`
  )).join("");
  const finalEntries = finalSceneReview && Array.isArray(finalSceneReview.entries)
    ? finalSceneReview.entries
    : [];
  const operatorEntries = finalEntries.filter(
    /** @param {{ operator_intervention_required?: boolean } | null} item */
    (item) => item && item.operator_intervention_required === true,
  );
  const fallbackEntries = finalEntries.filter(
    /** @param {{ fallback_downgrade_applied?: boolean } | null} item */
    (item) => item && item.fallback_downgrade_applied === true,
  );
  const reviewPreview = finalEntries.slice(0, 4).map(
    /** @param {{ sentence_idx: number, visual_mode?: string, selection_reason?: string, selected_reason?: string, operator_intervention_required?: boolean }} item */
    (item) => (
    `<div><strong>문장 ${item.sentence_idx}</strong>: ${escapeHtml(item.visual_mode || "-")} | ${escapeHtml(item.selection_reason || item.selected_reason || "-")}${item.operator_intervention_required ? " | operator review" : ""}</div>`
  )).join("");
  renderReportResults.innerHTML = `
    <div><strong>Status</strong>: ${escapeHtml(payload.status)}</div>
    <div><strong>Autopilot</strong>: ${payload.autopilot_job_id ? `${escapeHtml(payload.autopilot_input_mode || "manual")} | ${escapeHtml(readableAutopilotState(payload.autopilot_state))} | ${escapeHtml(payload.autopilot_phase || "-")} | ${escapeHtml(payload.autopilot_job_id)}` : "manual render or no autopilot metadata"}</div>
    <div><strong>Audio</strong>: ${payload.audio_duration_sec.toFixed(1)}s | <strong>Subtitle cues</strong>: ${payload.subtitle_cue_count}</div>
    <div><strong>Plan</strong>: segments ${payload.render_plan_segment_count} | missing media ${payload.missing_render_plan_media_count} | fallback ${payload.fallback_used ? "yes" : "no"}</div>
    <div><strong>Final Scene Review</strong>: ${payload.final_scene_review_exists ? `${escapeHtml(payload.final_scene_review_path)} | fallback ${fallbackEntries.length} | operator warning ${operatorEntries.length}` : "missing"}</div>
    ${reviewPreview ? `<div><strong>Review Preview</strong></div>${reviewPreview}` : ""}
    <div><strong>Outputs</strong></div>
    ${outputs || "<div>표시할 출력 정보가 없습니다.</div>"}
    <div><strong>Segments</strong></div>
    ${segments || "<div>표시할 세그먼트 정보가 없습니다.</div>"}
    ${payload.error ? `<div><strong>Error</strong>: ${escapeHtml(payload.error)}</div>` : ""}
    ${payload.ffmpeg_log_tail ? `<div><strong>FFmpeg tail</strong><pre>${escapeHtml(payload.ffmpeg_log_tail)}</pre></div>` : ""}
  `;
  renderReportResults.className = payload.status === "done" && operatorEntries.length === 0 ? "card ok" : "card warn";
}

/**
 * @returns {Promise<void>}
 */
async function runOperatorStatus() {
  const payload = /** @type {{
   *   health: { ffmpeg_available: boolean, oauth_ready: boolean, omnivoice_python_found: boolean, disk_free_gb: number, storage_path: string },
   *   tools: { key: string, label: string, availability: "available" | "unavailable", configured: boolean, version: string, detail: string, install_path: string }[],
   *   models: { key: string, label: string, available: boolean, source: string, path: string, detail: string }[],
   *   usage: { provider: string, day_count: number, month_count: number, day_limit: number | null, month_limit: number | null }[],
   *   gpu: { locked: boolean, owner: string, resource: string, expires_at: string },
   *   queue: { source_draft_queued: number, source_draft_running: number, autopilot_queued: number, autopilot_running: number, autopilot_paused: number, render_queued: number, render_running: number, tts_queued: number, tts_running: number },
   *   render_metrics: { total: number, success: number, error: number, fallback: number, missing_media: number },
   *   autopilot_metrics: { total: number, done: number, paused: number, error: number, running: number, queued: number },
   *   recent_autopilot_runs: { project_id: string, title: string, state: AutopilotState, phase: string, progress: number, updated_at: string, started_at: string, job_id: string, last_error_code: string }[]
   * }} */ (
    await requestJson("/api/system/operator")
  );
  const queue = payload.queue;
  const queueSummary = [
    `Autopilot ${queue.autopilot_queued}/${queue.autopilot_running}/${queue.autopilot_paused}`,
    `Source Draft ${queue.source_draft_queued}/${queue.source_draft_running}`,
    `TTS ${queue.tts_queued}/${queue.tts_running}`,
    `Render ${queue.render_queued}/${queue.render_running}`,
  ].join(" | ");
  const usageItems = payload.usage.map((item) => (
    `<div><strong>${escapeHtml(item.provider)}</strong>: day ${item.day_count}${item.day_limit === null ? "" : `/${item.day_limit}`} | month ${item.month_count}${item.month_limit === null ? "" : `/${item.month_limit}`}</div>`
  )).join("");
  const toolItems = payload.tools.map((item) => (
    `<div><strong>${escapeHtml(item.label)}</strong>: ${item.availability === "available" ? "ready" : "missing"} | ${item.configured ? "configured" : "not configured"}${item.version ? ` | ${escapeHtml(item.version)}` : ""}</div>`
  )).join("");
  const modelItems = payload.models.map((item) => (
    `<div><strong>${escapeHtml(item.label)}</strong>: ${item.available ? "ready" : "missing"} | ${escapeHtml(item.detail)}</div>`
  )).join("");
  const recentAutopilotItems = payload.recent_autopilot_runs.map((item) => (
    `<div><strong>${escapeHtml(item.title || item.project_id)}</strong>: ${escapeHtml(readableAutopilotState(item.state))} ${item.progress}%${item.phase ? ` | ${escapeHtml(item.phase)}` : ""}${item.last_error_code ? ` | ${escapeHtml(item.last_error_code)}` : ""}</div>`
  )).join("");
  operatorStatusResults.innerHTML = `
    <div class="operator-grid">
      <div class="operator-section">
        <strong>Queue</strong>
        <div>${escapeHtml(queueSummary)}</div>
        <div>Autopilot queue/running/paused</div>
      </div>
      <div class="operator-section">
        <strong>GPU</strong>
        <div>${payload.gpu.locked ? `사용 중: ${escapeHtml(payload.gpu.owner || payload.gpu.resource)}` : "대기 중"}</div>
      </div>
      <div class="operator-section">
        <strong>System</strong>
        <div>FFmpeg ${payload.health.ffmpeg_available ? "ok" : "missing"} | Disk ${payload.health.disk_free_gb} GB</div>
      </div>
      <div class="operator-section">
        <strong>Usage</strong>
        ${usageItems || "<div>표시할 사용량이 없습니다.</div>"}
      </div>
      <div class="operator-section">
        <strong>Tools</strong>
        ${toolItems || "<div>표시할 도구 상태가 없습니다.</div>"}
      </div>
      <div class="operator-section">
        <strong>Models</strong>
        ${modelItems || "<div>표시할 모델 상태가 없습니다.</div>"}
      </div>
      <div class="operator-section">
        <strong>Recent Render</strong>
        <div>Total ${payload.render_metrics.total} | Success ${payload.render_metrics.success} | Error ${payload.render_metrics.error}</div>
        <div>Fallback ${payload.render_metrics.fallback} | Missing media ${payload.render_metrics.missing_media}</div>
      </div>
      <div class="operator-section">
        <strong>Autopilot</strong>
        <div>Total ${payload.autopilot_metrics.total} | Done ${payload.autopilot_metrics.done} | Paused ${payload.autopilot_metrics.paused}</div>
        <div>Running ${payload.autopilot_metrics.running} | Queued ${payload.autopilot_metrics.queued} | Error ${payload.autopilot_metrics.error}</div>
      </div>
      <div class="operator-section">
        <strong>Recent Autopilot Runs</strong>
        ${recentAutopilotItems || "<div>표시할 오토파일럿 실행 기록이 없습니다.</div>"}
      </div>
    </div>
  `;
  operatorStatusResults.className = "card";
}

/**
 * @returns {Promise<void>}
 */
async function cloneProject() {
  const project = requireCurrent();
  const response = /** @type {{ project: Project }} */ (await requestJson(`/api/projects/${project.id}/clone?include_script=true`, {
    method: "POST",
  }));
  await openProject(response.project.id);
  toast("Project cloned.");
}

/**
 * @returns {SubtitleStyle}
 */
function readSubtitleStyleInputs() {
  return {
    font_family: subtitleFontInput.value.trim() || DEFAULT_SUBTITLE_STYLE.font_family,
    font_size: numberInRange(subtitleSizeInput.value, DEFAULT_SUBTITLE_STYLE.font_size, 24, 96),
    primary_color: subtitlePrimaryColorInput.value || DEFAULT_SUBTITLE_STYLE.primary_color,
    outline_color: subtitleOutlineColorInput.value || DEFAULT_SUBTITLE_STYLE.outline_color,
    background_color: subtitleBackgroundColorInput.value || DEFAULT_SUBTITLE_STYLE.background_color,
    background_opacity: numberInRange(
      subtitleBackgroundOpacityInput.value,
      DEFAULT_SUBTITLE_STYLE.background_opacity,
      0,
      1,
    ),
    outline_width: numberInRange(
      subtitleOutlineWidthInput.value,
      DEFAULT_SUBTITLE_STYLE.outline_width,
      0,
      8,
    ),
    shadow: numberInRange(subtitleShadowInput.value, DEFAULT_SUBTITLE_STYLE.shadow, 0, 8),
    position: subtitlePositionFromValue(subtitlePositionSelect.value),
    margin_h: numberInRange(subtitleMarginHInput.value, DEFAULT_SUBTITLE_STYLE.margin_h, 0, 400),
    margin_v: numberInRange(subtitleMarginVInput.value, DEFAULT_SUBTITLE_STYLE.margin_v, 0, 240),
    max_line_chars: numberInRange(
      subtitleMaxLineCharsInput.value,
      DEFAULT_SUBTITLE_STYLE.max_line_chars,
      16,
      40,
    ),
    min_display_sec: numberInRange(
      subtitleMinDisplaySecInput.value,
      DEFAULT_SUBTITLE_STYLE.min_display_sec,
      0.5,
      3,
    ),
    effect: subtitleEffectFromValue(subtitleEffectSelect.value),
  };
}

/**
 * @param {SubtitlePosition} position
 * @returns {boolean}
 */
function usesFixedVerticalAnchor(position) {
  return position === "upper" || position === "middle" || position === "lower";
}

/**
 * @param {SubtitleStyle} style
 * @returns {number}
 */
function subtitlePreviewCenterPercent(style) {
  let centerPercent = SUBTITLE_POSITION_CENTER_RATIO[style.position] * 100;
  if (style.position === "top") {
    centerPercent -= (style.margin_v / PLAY_RES_Y) * 100;
  }
  if (style.position === "bottom") {
    centerPercent += (style.margin_v / PLAY_RES_Y) * 100;
  }
  return centerPercent;
}

/**
 * @param {SubtitleStyle} style
 * @returns {void}
 */
function writeSubtitleStyleInputs(style) {
  subtitleFontInput.value = style.font_family;
  subtitleSizeInput.value = String(style.font_size);
  subtitlePrimaryColorInput.value = style.primary_color;
  subtitleOutlineColorInput.value = style.outline_color;
  subtitleBackgroundColorInput.value = style.background_color;
  subtitleBackgroundOpacityInput.value = String(style.background_opacity);
  subtitleOutlineWidthInput.value = String(style.outline_width);
  subtitleShadowInput.value = String(style.shadow);
  subtitlePositionSelect.value = style.position;
  subtitleMarginHInput.value = String(style.margin_h);
  subtitleMarginVInput.value = String(style.margin_v);
  subtitleMaxLineCharsInput.value = String(style.max_line_chars);
  subtitleMinDisplaySecInput.value = String(style.min_display_sec);
  subtitleEffectSelect.value = style.effect;
}

/**
 * @returns {void}
 */
function renderSubtitleStyleControls() {
  const style = effectiveSubtitleStyle(requireCurrent());
  writeSubtitleStyleInputs(style);
  renderSubtitlePreview();
}

/**
 * @returns {void}
 */
function renderSubtitlePreview() {
  const style = readSubtitleStyleInputs();
  const previewWidth = Math.max(42, 100 - Math.round((style.margin_h / 400) * 36));
  const centerPercent = subtitlePreviewCenterPercent(style);
  subtitlePositionHint.textContent = usesFixedVerticalAnchor(style.position)
    ? "Upper, middle, lower positions use fixed center anchors. Lower targets the lower-third area."
    : "Top and bottom use the vertical margin value directly, so you can fine-tune the edge spacing.";
  subtitlePreviewCaption.textContent = style.effect === "pop"
    ? "자막 스타일 미리보기!"
    : "자막 스타일 미리보기";
  subtitlePreviewCaption.style.fontFamily = style.font_family;
  subtitlePreviewCaption.style.fontSize = `${Math.max(18, Math.round(style.font_size * 0.62))}px`;
  subtitlePreviewCaption.style.color = style.primary_color;
  subtitlePreviewCaption.style.textShadow = `0 0 ${style.outline_width + 1}px ${style.outline_color}, ${style.shadow}px ${style.shadow}px ${style.shadow + 2}px rgba(0,0,0,.72)`;
  subtitlePreviewCaption.style.backgroundColor = `rgba(0, 0, 0, ${style.background_opacity})`;
  subtitlePreviewCaption.style.fontWeight = style.effect === "pop" ? "800" : "700";
  subtitlePreviewCaption.style.width = `${previewWidth}%`;
  subtitlePreviewCaption.style.top = `${centerPercent}%`;
  subtitlePreviewCaption.style.bottom = "";
  subtitlePreviewCaption.style.transform = style.effect === "pop"
    ? "translate(-50%, -50%) scale(1.05)"
    : "translate(-50%, -50%)";
}

/**
 * @param {string} presetName
 * @returns {void}
 */
function applySubtitlePreset(presetName) {
  const preset = SUBTITLE_PRESETS[presetName];
  if (!preset) {
    return;
  }
  const style = {
    ...readSubtitleStyleInputs(),
    ...preset,
  };
  writeSubtitleStyleInputs(style);
  renderSubtitlePreview();
}

/**
 * @returns {Promise<void>}
 */
async function saveSubtitleStyle() {
  const project = requireCurrent();
  const style = readSubtitleStyleInputs();
  const response = /** @type {SubtitleStyleResponse} */ (
    await requestJson(`/api/projects/${project.id}/subtitle-style`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(style),
    })
  );
  current = response.project;
  renderSubtitleStyleControls();
  toast("자막 스타일을 저장했습니다.");
}

/**
 * @param {string[]} order
 * @param {string} moveName
 * @param {string} targetName
 * @returns {string[]}
 */
function moveMediaBefore(order, moveName, targetName) {
  const next = order.filter((name) => name !== moveName);
  const targetIndex = next.indexOf(targetName);
  if (targetIndex < 0) {
    return order;
  }
  next.splice(targetIndex, 0, moveName);
  return next;
}

/**
 * @param {string} name
 * @param {number} offset
 * @returns {string[]}
 */
function moveMediaByOffset(name, offset) {
  const project = requireCurrent();
  const order = [...project.media_order];
  const currentIndex = order.indexOf(name);
  if (currentIndex < 0) {
    return order;
  }
  const nextIndex = Math.max(0, Math.min(order.length - 1, currentIndex + offset));
  order.splice(currentIndex, 1);
  order.splice(nextIndex, 0, name);
  return order;
}

/**
 * @param {string[]} order
 * @returns {Promise<void>}
 */
async function persistMediaOrder(order) {
  const project = requireCurrent();
  current = /** @type {Project} */ (
    await requestJson(`/api/projects/${project.id}/media/order`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(order),
    })
  );
  renderMedia();
  updateProgressBar();
  updateStepMarks();
  toast("미디어 순서를 저장했습니다.");
}

/**
 * @param {string} name
 * @returns {Promise<void>}
 */
async function deleteMedia(name) {
  const project = requireCurrent();
  current = /** @type {Project} */ (
    await requestJson(`/api/projects/${project.id}/media/${encodeURIComponent(name)}`, {
      method: "DELETE",
    })
  );
  if (selectedMediaName === name) {
    selectedMediaName = current.media_order[0] || null;
  }
  renderMedia();
  updateProgressBar();
  updateStepMarks();
}

/**
 * @param {FileList | null} files
 * @returns {void}
 */
function uploadFiles(files) {
  if (!files || files.length === 0) {
    return;
  }

  const project = requireCurrent();
  const xhr = new XMLHttpRequest();
  const formData = new FormData();
  for (const file of Array.from(files)) {
    formData.append("files", file);
  }

  setUploadControlsDisabled(true);
  mediaClientState = {
    phase: "uploading",
    transferProgress: 0,
    message: "브라우저에서 서버로 파일을 전송하고 있습니다.",
    lastAccepted: [],
    lastSkipped: [],
  };
  renderMediaUploadStatus();

  xhr.open("POST", `/api/projects/${project.id}/media`);
  xhr.responseType = "json";

  xhr.upload.addEventListener("progress", (event) => {
    if (!event.lengthComputable) {
      return;
    }
    mediaClientState.transferProgress = Math.min(100, Math.round((event.loaded / event.total) * 100));
    if (mediaClientState.transferProgress >= 100) {
      mediaClientState.phase = "processing";
      mediaClientState.message = "전송이 끝났습니다. 서버가 파일을 처리하고 있습니다.";
    }
    renderMediaUploadStatus();
  });

  xhr.addEventListener("load", () => {
    setUploadControlsDisabled(false);
    fileInput.value = "";

    if (xhr.status >= 200 && xhr.status < 300) {
      const response = /** @type {MediaUploadResponse} */ (xhr.response);
      current = response.project;
      selectedMediaName = response.accepted_files[0]?.saved_name || current.media_order[0] || null;
      mediaClientState = {
        phase: "done",
        transferProgress: 100,
        message: `업로드 완료: ${response.accepted_files.length}개 수락, ${response.skipped_files.length}개 건너뜀`,
        lastAccepted: response.accepted_files,
        lastSkipped: response.skipped_files,
      };
      renderMedia();
      renderMediaUploadStatus();
      updateProgressBar();
      updateStepMarks();
      toast("미디어 업로드가 완료되었습니다.");
      return;
    }

    let message = "업로드에 실패했습니다.";
    const response = xhr.response;
    if (response && typeof response.detail === "string") {
      message = response.detail;
    }
    mediaClientState = {
      phase: "error",
      transferProgress: mediaClientState.transferProgress,
      message,
      lastAccepted: [],
      lastSkipped: [],
    };
    renderMediaUploadStatus();
    toast(message);
  });

  xhr.addEventListener("error", () => {
    setUploadControlsDisabled(false);
    mediaClientState = {
      phase: "error",
      transferProgress: mediaClientState.transferProgress,
      message: "네트워크 오류로 업로드에 실패했습니다.",
      lastAccepted: [],
      lastSkipped: [],
    };
    renderMediaUploadStatus();
    toast(mediaClientState.message);
  });

  xhr.send(formData);
}

/**
 * @returns {void}
 */
function renderTtsList() {
  const project = requireCurrent();
  ttsList.innerHTML = "";
  if (project.tts_state !== "done") {
    return;
  }

  const regionalSentences = effectiveRegionalSentences(project);
  project.sentences.forEach((sentence, index) => {
    const region = normalizeRegion(regionalSentences[index]?.region || "body");
    const row = document.createElement("div");
    row.className = `tts-row ${region}`;
    const pad = String(index).padStart(4, "0");
    row.innerHTML = `
      <div class="idx">${index + 1}</div>
      <div class="region-badge">${escapeHtml(region)}</div>
      <div class="text">${escapeHtml(sentence)}</div>
      <audio controls src="/api/projects/${project.id}/tts/${pad}.wav"></audio>
    `;
    ttsList.appendChild(row);
  });
}

/**
 * @returns {Promise<void>}
 */
async function generateTtsPreview() {
  const project = requireCurrent();
  ttsPreviewRunButton.disabled = true;
  ttsPreviewState.textContent = "샘플 음성을 생성하고 있습니다...";
  try {
    const canonicalId = canonicalVoicePresetId(voiceSelect.value);
    const response = /** @type {TtsPreviewResponse} */ (
      await requestJson(`/api/projects/${project.id}/tts/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          voice_preset: canonicalId,
          sample_text: ttsPreviewTextInput.value.trim(),
          tts_profile: buildTtsProfilePayload(),
        }),
      })
    );
    lastTtsPreviewLock = response.preview_lock;
    ttsPreviewAudio.src = `${response.preview_url}?t=${Date.now()}`;
    ttsPreviewAudio.load();
    void ttsPreviewAudio.play().catch(() => {
      // Some browsers block autoplay after async work.
    });
    ttsPreviewState.textContent =
      `샘플 준비 완료: ${response.sample_text} | seed ${response.preview_lock.tts_profile.seed}`;
  } finally {
    ttsPreviewRunButton.disabled = false;
  }
}

/**
 * @returns {void}
 */
function updateOutputVideo() {
  const project = requireCurrent();
  if (project.render_state === "done") {
    const format = project.render_formats.includes("landscape") ? "landscape" : "shorts";
    renderVideo.src = `/api/projects/${project.id}/output?format=${format}&t=${Date.now()}`;
    renderVideo.hidden = false;
  } else {
    renderVideo.hidden = true;
    renderVideo.src = "";
  }
}

/**
 * @returns {Promise<void>}
 */
async function renderStep5() {
  const project = requireCurrent();
  uploadTitleInput.value = project.title || "";
  uploadScheduleInput.value = project.youtube_schedule_at || "";
  uploadStatsPanel.innerHTML = project.youtube_id ? uploadStatsPanel.innerHTML : "";
  const oauthStatus = /** @type {OAuthStatus} */ (await requestJson("/api/projects/_/oauth/status"));

  if (oauthStatus.authorized) {
    oauthPanel.className = "card ok";
    oauthPanel.innerHTML = "YouTube OAuth가 연결되어 있습니다.";
  } else if (!oauthStatus.client_secret_present) {
    oauthPanel.className = "card warn";
    oauthPanel.innerHTML = "storage/oauth/client_secret.json 파일을 배치한 뒤 다시 시도해 주세요.";
  } else {
    oauthPanel.className = "card warn";
    oauthPanel.innerHTML = 'YouTube 업로드 전에 최초 1회 인증이 필요합니다. <button id="btn-auth" class="btn" type="button">Authorize</button>';
    const authButton = /** @type {HTMLButtonElement} */ (query("#btn-auth", oauthPanel));
    authButton.addEventListener("click", async () => {
      oauthPanel.innerHTML = "브라우저 창에서 Google 로그인과 권한 허용을 완료한 뒤 돌아와 주세요.";
      try {
        await requestJson("/api/projects/_/oauth/authorize", { method: "POST", body: new FormData() });
        toast("OAuth 인증이 완료되었습니다.");
      } catch (error) {
        handleError(error, "OAuth 인증에 실패했습니다.");
      }
      await renderStep5();
    });
  }

  if (project.youtube_id) {
    uploadLink.innerHTML = `<a href="https://youtu.be/${project.youtube_id}" target="_blank" rel="noreferrer">https://youtu.be/${project.youtube_id}</a>`;
  } else {
    uploadLink.innerHTML = "";
  }
}

/**
 * @returns {void}
 */
function updateProgressBar() {
  const project = requireCurrent();
  const values = [
    project.sentences.length > 0 ? 20 : 0,
    project.media_order.length > 0 ? 20 : 0,
    project.tts_state === "done" ? 20 : 0,
    project.render_state === "done" ? 20 : 0,
    project.upload_state === "done" ? 20 : 0,
  ];
  const percent = values.reduce((sum, value) => sum + value, 0);
  progressBar.style.width = `${percent}%`;
  progressLabel.textContent = `${percent}%`;
}

/**
 * @returns {void}
 */
function updateStepMarks() {
  const project = requireCurrent();
  const done = [
    project.sentences.length > 0,
    project.media_order.length > 0,
    project.tts_state === "done",
    project.render_state === "done",
    project.upload_state === "done",
  ];
  stepButtons.forEach((button, index) => {
    button.classList.toggle("done", done[index]);
  });
}

/**
 * @returns {Promise<void>}
 */
async function pollProjectStatus() {
  const project = requireCurrent();
  const previous = {
    tts: project.tts_state,
    bodyImage: project.body_image_state,
    sourceDraft: project.source_draft_state,
    autopilot: project.autopilot_state,
    render: project.render_state,
    upload: project.upload_state,
    mediaUpload: project.media_upload_state,
  };

  const status = /** @type {ProjectStatus} */ (await requestJson(`/api/projects/${project.id}/status`));
  current = {
    ...project,
    ...status,
  };

  ttsState.textContent = `${readableTaskState(status.tts_state)} ${status.tts_progress}%`;
  const renderPhaseText = (status.render_state === "running" || status.render_state === "queued") && status.render_phase
    ? ` | ${readableRenderPhase(status.render_phase)}`
    : "";
  renderState.textContent = `${readableTaskState(status.render_state)} ${status.render_progress}%${renderPhaseText}`;
  renderLogPanel.textContent = formatRenderLog(
    status.render_state,
    status.render_phase,
    status.render_progress_detail,
    status.render_last_log,
    status.render_heartbeat_at,
  );
  uploadState.textContent = `${readableTaskState(status.upload_state)} ${status.upload_progress}%`;
  renderSourceDraft(current);
  renderAutopilot(current);
  renderImageGenPanel();
  renderMediaUploadStatus();
  updateProgressBar();
  updateStepMarks();

  if (previous.tts !== "done" && status.tts_state === "done") {
    current = /** @type {Project} */ (await requestJson(`/api/projects/${project.id}`));
    renderTtsList();
  }
  if (previous.render !== "done" && status.render_state === "done") {
    updateOutputVideo();
  }
  if (previous.upload !== "done" && status.upload_state === "done") {
    await renderStep5();
  }
  if (previous.mediaUpload !== "done" && status.media_upload_state === "done") {
    current = /** @type {Project} */ (await requestJson(`/api/projects/${project.id}`));
    renderMedia();
    renderMediaUploadStatus();
  }
  if (previous.sourceDraft !== "done" && status.source_draft_state === "done") {
    current = /** @type {Project} */ (await requestJson(`/api/projects/${project.id}`));
    renderSourceDraft(current);
  }
  if (
    previous.autopilot !== status.autopilot_state
    || ["queued", "running", "paused"].includes(status.autopilot_state)
  ) {
    await refreshAutopilotDebug().catch(() => {
      autopilotDebugSnapshot = null;
      renderAutopilot(requireCurrent());
    });
  }
  if (previous.bodyImage !== "done" && status.body_image_state === "done") {
    current = /** @type {Project} */ (await requestJson(`/api/projects/${project.id}`));
    renderMedia();
    renderImageGenPanel();
  }
}

/**
 * @returns {void}
 */
function startPoll() {
  stopPoll();
  pollTimer = window.setInterval(() => {
    void pollProjectStatus().catch(() => {
      // Ignore transient polling failures and keep the UI responsive.
    });
  }, 1500);
  operatorPollTimer = window.setInterval(() => {
    void runOperatorStatus().catch(() => {
      // Ignore static operator polling failures.
    });
  }, 30000);
}

/**
 * @returns {void}
 */
function stopPoll() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
  }
  pollTimer = null;
  if (operatorPollTimer !== null) {
    window.clearInterval(operatorPollTimer);
  }
  operatorPollTimer = null;
}

/**
 * @param {object | null | undefined} error
 * @param {string} fallback
 * @returns {void}
 */
function handleError(error, fallback) {
  if (error instanceof HttpError) {
    toast(error.message);
    return;
  }
  if (error instanceof Error) {
    toast(error.message || fallback);
    return;
  }
  toast(fallback);
}

/**
 * @param {string} message
 * @returns {void}
 */
function toast(message) {
  const popup = document.createElement("div");
  popup.textContent = message;
  Object.assign(popup.style, {
    position: "fixed",
    bottom: "20px",
    left: "50%",
    transform: "translateX(-50%)",
    background: "#22e397",
    color: "#05130d",
    padding: "10px 16px",
    borderRadius: "10px",
    fontWeight: "600",
    zIndex: "9999",
    boxShadow: "0 10px 30px rgba(0,0,0,.3)",
  });
  document.body.appendChild(popup);
  window.setTimeout(() => popup.remove(), 2400);
}

[
  ttsModeSelect,
  ttsLanguageSelect,
  ttsSpeedInput,
  ttsDurationInput,
  ttsNumStepInput,
  ttsGuidanceInput,
  ttsDenoiseSelect,
  ttsPostprocessSelect,
  ttsInstructInput,
].forEach((control) => {
  control.addEventListener("input", () => {
    ttsFormDirtyAfterPreset = true;
    updateTtsEffectiveProfile();
  });
  control.addEventListener("change", () => {
    ttsFormDirtyAfterPreset = true;
    updateTtsEffectiveProfile();
  });
});

navProjects.addEventListener("click", () => {
  stopPoll();
  show("projects");
  void loadProjects().catch((error) => handleError(error, "프로젝트 목록을 불러오지 못했습니다."));
});

createButton.addEventListener("click", async () => {
  const title = newTitleInput.value.trim();
  try {
    const project = /** @type {Project} */ (
      await requestJson("/api/projects", { method: "POST", body: formDataFromObject({ title }) })
    );
    newTitleInput.value = "";
    await openProject(project.id);
  } catch (error) {
    handleError(error, "프로젝트를 만들지 못했습니다.");
  }
});

projectsList.addEventListener("click", async (event) => {
  const target = /** @type {HTMLElement} */ (event.target);
  const projectId = target.dataset.delete;
  if (!projectId) {
    return;
  }
  event.stopPropagation();
  if (!window.confirm("이 프로젝트를 삭제할까요?")) {
    return;
  }
  try {
    await requestJson(`/api/projects/${projectId}`, { method: "DELETE" });
    await loadProjects();
  } catch (error) {
    handleError(error, "프로젝트를 삭제하지 못했습니다.");
  }
});

backButton.addEventListener("click", () => {
  stopPoll();
  show("projects");
  void loadProjects().catch((error) => handleError(error, "프로젝트 목록을 불러오지 못했습니다."));
});

stepButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const step = Number(button.dataset.step || "1");
    showStep(step);
  });
});

contentModeSelect.addEventListener("change", renderScriptStats);
scriptInput.addEventListener("input", renderScriptStats);

saveScriptButton.addEventListener("click", async () => {
  const project = requireCurrent();
  try {
    current = /** @type {Project} */ (
      await requestJson(`/api/projects/${project.id}/script`, {
        method: "PUT",
        body: formDataFromObject({
          title: scriptTitleInput.value,
          script: scriptInput.value,
          content_mode: contentModeSelect.value,
        }),
      })
    );
    workflowTitle.textContent = current.title || "Untitled Project";
    contentModeSelect.value = current.content_mode || "standard";
    renderScriptStats();
    renderSourceDraft(current);
    updateProgressBar();
    updateStepMarks();
    toast("스크립트를 저장했습니다.");
  } catch (error) {
    handleError(error, "스크립트를 저장하지 못했습니다.");
  }
});

sourceAnalyzeButton.addEventListener("click", () => {
  void analyzeSourceUrl().catch((error) => handleError(error, "URL 분석을 완료하지 못했습니다."));
});

sourceKeywordRunButton.addEventListener("click", () => {
  void collectSourceKeyword().catch((error) => handleError(error, "키워드 리서치를 완료하지 못했습니다."));
});

sourceClearButton.addEventListener("click", () => {
  void clearSourceDraft().catch((error) => handleError(error, "Source draft를 비우지 못했습니다."));
});

autopilotStartButton.addEventListener("click", () => {
  void startAutopilot()
    .then(() => {
      toast("오토파일럿을 시작했습니다.");
    })
    .catch((error) => handleError(error, "오토파일럿을 시작하지 못했습니다."));
});

autopilotPauseButton.addEventListener("click", () => {
  void updateAutopilotState("pause")
    .then(() => {
      toast("오토파일럿을 일시정지했습니다.");
    })
    .catch((error) => handleError(error, "오토파일럿을 일시정지하지 못했습니다."));
});

autopilotResumeButton.addEventListener("click", () => {
  void updateAutopilotState("resume")
    .then(() => {
      toast("오토파일럿을 재개했습니다.");
    })
    .catch((error) => handleError(error, "오토파일럿을 재개하지 못했습니다."));
});

autopilotCancelButton.addEventListener("click", () => {
  void updateAutopilotState("cancel")
    .then(() => {
      toast("오토파일럿을 중단했습니다.");
    })
    .catch((error) => handleError(error, "오토파일럿을 중단하지 못했습니다."));
});

autopilotDebugRefreshButton.addEventListener("click", () => {
  void refreshAutopilotDebug().catch((error) => handleError(error, "디버그 스냅샷을 불러오지 못했습니다."));
});

sourceGenerateButton.addEventListener("click", () => {
  void generateSourceScript().catch((error) => handleError(error, "대본 초안을 생성하지 못했습니다."));
});

sourceRegenerateButton.addEventListener("click", () => {
  void generateSourceScript().catch((error) => handleError(error, "대본 초안을 다시 생성하지 못했습니다."));
});

sourceRestoreButton.addEventListener("click", () => {
  void restorePreviousSourceScript().catch((error) => handleError(error, "이전 초안을 복원하지 못했습니다."));
});

sourceApplyButton.addEventListener("click", () => {
  void applySourceScript().catch((error) => handleError(error, "대본 초안을 적용하지 못했습니다."));
});

flowPromptsGenerateButton.addEventListener("click", () => {
  void generateFlowPrompts().catch((error) => handleError(error, "Flow 프롬프트를 생성하지 못했습니다."));
});

simplePromptAllButton.addEventListener("click", () => {
  void generateAllSimpleImagePrompts().catch((error) => handleError(error, "전체 이미지 프롬프트를 생성하지 못했습니다."));
});

simpleLmstudioUnloadButton.addEventListener("click", () => {
  void unloadLmStudioForSimpleMedia().catch((error) => handleError(error, "LM Studio를 종료하지 못했습니다."));
});

simpleCopyPromptsButton.addEventListener("click", () => {
  void copyAllSimplePrompts().catch((error) => handleError(error, "이미지 프롬프트를 복사하지 못했습니다."));
});

simpleImageGenerateButton.addEventListener("click", () => {
  void enqueueSimpleMediaImageGen().catch((error) => handleError(error, "이미지 생성을 시작하지 못했습니다."));
});

simplePromptList.addEventListener("click", (event) => {
  const target = /** @type {HTMLElement} */ (event.target);
  const rawIdx = target.dataset.simpleCopyPrompt;
  if (rawIdx === undefined) {
    return;
  }
  const item = simplePromptItems.find((candidate) => Number(candidate.sentence_idx || 0) === Number(rawIdx));
  if (!item) {
    toast("복사할 프롬프트를 찾지 못했습니다.");
    return;
  }
  void navigator.clipboard.writeText(String(item.positive_prompt || ""))
    .then(() => toast(`문장 ${Number(rawIdx) + 1} 이미지 프롬프트를 복사했습니다.`))
    .catch((error) => handleError(error, "이미지 프롬프트를 복사하지 못했습니다."));
});

flowOpenButton.addEventListener("click", () => {
  window.open("https://labs.google/fx/tools/flow", "_blank", "noopener,noreferrer");
});

flowPromptList.addEventListener("click", (event) => {
  const target = /** @type {HTMLElement} */ (event.target);
  const action = target.dataset.flowAction || "";
  if (!action) return;
  const sentenceIdx = Number(target.dataset.sentenceIdx || "0");
  if (!Number.isFinite(sentenceIdx)) return;
  if (action === "copy") {
    void copyFlowPrompt(sentenceIdx).catch((error) => handleError(error, "Flow 프롬프트를 복사하지 못했습니다."));
  } else if (action === "attach") {
    pendingFlowAssetSentenceIdx = sentenceIdx;
    flowAssetInput.click();
  }
});

flowAssetInput.addEventListener("change", () => {
  const file = flowAssetInput.files ? flowAssetInput.files[0] || null : null;
  void uploadFlowAsset(file).catch((error) => handleError(error, "Flow 결과 파일을 연결하지 못했습니다."));
});

sceneCardsRefreshButton.addEventListener("click", () => {
  void loadSceneCards().catch((error) => handleError(error, "장면 카드를 불러오지 못했습니다."));
});

sceneCardList.addEventListener("change", (event) => {
  const target = /** @type {HTMLElement} */ (event.target);
  const card = target.closest(".scene-card");
  if (!(card instanceof HTMLElement)) {
    return;
  }
  const sentenceIdx = Number(card.dataset.sentenceIdx || "-1");
  if (!Number.isFinite(sentenceIdx) || sentenceIdx < 0) {
    return;
  }
  const action = target.dataset.sceneAction || "";
  if (action === "lock" && target instanceof HTMLInputElement) {
    void patchSceneCard(sentenceIdx, {locked: target.checked}).catch((error) => handleError(error, "장면 잠금을 저장하지 못했습니다."));
  }
  if (action === "motion" && target instanceof HTMLSelectElement) {
    void patchSceneCard(sentenceIdx, {motion: target.value}).catch((error) => handleError(error, "움직임 설정을 저장하지 못했습니다."));
  }
});

sceneCardList.addEventListener("click", (event) => {
  const target = /** @type {HTMLElement} */ (event.target);
  const action = target.dataset.sceneAction || "";
  if (!action) {
    return;
  }
  const card = target.closest(".scene-card");
  if (!(card instanceof HTMLElement)) {
    return;
  }
  const sentenceIdx = Number(card.dataset.sentenceIdx || "-1");
  if (!Number.isFinite(sentenceIdx) || sentenceIdx < 0) {
    return;
  }
  if (action === "subtitle-large") {
    void patchSceneCard(sentenceIdx, {
      subtitle_override: {
        font_size: Math.min(96, Math.max(60, DEFAULT_SUBTITLE_STYLE.font_size + 16)),
        primary_color: "#FFFFFF",
        outline_color: "#000000",
        outline_width: 4,
        shadow: 2,
      },
    }).catch((error) => handleError(error, "개별 자막 설정을 저장하지 못했습니다."));
  }
  if (action === "subtitle-clear") {
    void patchSceneCard(sentenceIdx, {clear_subtitle_override: true}).catch((error) => handleError(error, "개별 자막 설정을 해제하지 못했습니다."));
  }
});

sourceModeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    sourceModeButtons.forEach((item) => item.classList.toggle("active", item === button));
  });
});

dropzone.addEventListener("click", () => {
  if (!fileInput.disabled) {
    fileInput.click();
  }
});

dropzone.addEventListener("keydown", (event) => {
  if ((event.key === "Enter" || event.key === " ") && !fileInput.disabled) {
    event.preventDefault();
    fileInput.click();
  }
});

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  if (!fileInput.disabled) {
    dropzone.classList.add("drag");
  }
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("drag");
});

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("drag");
  if (fileInput.disabled) {
    return;
  }
  uploadFiles(event.dataTransfer ? event.dataTransfer.files : null);
});

fileInput.addEventListener("change", () => {
  uploadFiles(fileInput.files);
});

thumbnailUploadButton.addEventListener("click", () => {
  thumbnailInput.click();
});

thumbnailInput.addEventListener("change", () => {
  const file = thumbnailInput.files ? thumbnailInput.files[0] || null : null;
  void uploadThumbnail(file).catch((error) => handleError(error, "썸네일을 업로드하지 못했습니다."));
});

thumbnailDeleteButton.addEventListener("click", () => {
  void deleteThumbnail().catch((error) => handleError(error, "썸네일을 삭제하지 못했습니다."));
});

bgmUploadButton.addEventListener("click", () => {
  bgmInput.click();
});

bgmInput.addEventListener("change", () => {
  const file = bgmInput.files ? bgmInput.files[0] || null : null;
  void uploadBgm(file).catch((error) => handleError(error, "BGM upload failed."));
});

bgmDeleteButton.addEventListener("click", () => {
  void deleteBgm().catch((error) => handleError(error, "BGM delete failed."));
});

mediaGrid.addEventListener("click", (event) => {
  const target = /** @type {HTMLElement} */ (event.target);
  const action = target.dataset.action;
  if (!action) {
    return;
  }
  const card = target.closest(".media-item");
  if (!(card instanceof HTMLElement)) {
    return;
  }
  const name = card.dataset.name;
  if (!name) {
    return;
  }

  if (action === "left") {
    void persistMediaOrder(moveMediaByOffset(name, -1));
    return;
  }
  if (action === "right") {
    void persistMediaOrder(moveMediaByOffset(name, 1));
    return;
  }
  if (action === "delete") {
    void deleteMedia(name).catch((error) => handleError(error, "미디어를 삭제하지 못했습니다."));
  }
});

imageGenMappings.addEventListener("click", (event) => {
  const target = /** @type {HTMLElement} */ (event.target);
  const actionTarget = target.closest("[data-action]");
  if (!(actionTarget instanceof HTMLElement)) {
    return;
  }
  const action = actionTarget.dataset.action || "";
  if (action !== "apply-repair-suggestion") {
    return;
  }
  const sentenceIdx = Number(actionTarget.dataset.sentenceIdx || "0");
  applyRepairSuggestionForSentence(sentenceIdx);
});

[
  subtitleFontInput,
  subtitleSizeInput,
  subtitlePrimaryColorInput,
  subtitleOutlineColorInput,
  subtitleOutlineWidthInput,
  subtitleShadowInput,
  subtitlePositionSelect,
  subtitleMarginHInput,
  subtitleMarginVInput,
  subtitleBackgroundColorInput,
  subtitleBackgroundOpacityInput,
  subtitleMaxLineCharsInput,
  subtitleMinDisplaySecInput,
  subtitleEffectSelect,
].forEach((control) => {
  control.addEventListener("input", renderSubtitlePreview);
  control.addEventListener("change", renderSubtitlePreview);
});

subtitlePresetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    applySubtitlePreset(button.dataset.preset || "");
  });
});

subtitleSaveButton.addEventListener("click", () => {
  void saveSubtitleStyle().catch((error) => handleError(error, "자막 스타일을 저장하지 못했습니다."));
});

featureSaveButton.addEventListener("click", () => {
  void saveFeatureSettings().catch((error) => handleError(error, "Saving render settings failed."));
});

featureHyperframesOverlayInput.addEventListener("change", () => {
  if (!featureHyperframesOverlayInput.checked) {
    featureHyperframesRequiredInput.checked = false;
  }
  featureHyperframesRequiredInput.disabled = !featureHyperframesOverlayInput.checked;
});

youtubeRunButton.addEventListener("click", async () => {
  const project = requireCurrent();
  try {
    await requestJson(`/api/projects/${project.id}/upload`, {
      method: "POST",
      body: formDataFromObject({
        title: uploadTitleInput.value,
        description: uploadDescInput.value,
        tags: uploadTagsInput.value,
        privacy: uploadPrivacySelect.value,
        schedule_at: uploadScheduleInput.value,
      }),
    });
    toast("YouTube 업로드를 시작했습니다.");
  } catch (error) {
    handleError(error, "YouTube 업로드를 시작하지 못했습니다.");
  }
});

s1TabScript.addEventListener("click", () => setS1Mode("script"));
s1TabSource.addEventListener("click", () => setS1Mode("source"));

imageGenRunButton.addEventListener("click", () => {
  void enqueueImageGen().catch((error) => handleError(error, "이미지 생성 작업을 등록하지 못했습니다."));
});
imageGenBatchRunButton.addEventListener("click", () => {
  void enqueueBatchImageGen().catch((error) => handleError(error, "일괄 이미지 생성을 등록하지 못했습니다."));
});
imageGenSuggestButton.addEventListener("click", () => {
  void suggestImagePrompt().catch((error) => handleError(error, "프롬프트 추천을 불러오지 못했습니다."));
});
imageGenerationProfileSelect.addEventListener("change", () => {
  if (imageGenerationProfileSelect.value === "sdxl_style_reference" && !imageStyleReferenceInput.value.trim()) {
    imageStyleReferenceInput.value = preferredStyleReferenceValue();
  }
  if (imageGenerationProfileSelect.value === "sdxl_controlnet_depth" && !imageControlReferenceInput.value.trim()) {
    imageControlReferenceInput.value = preferredControlImageValue();
  }
  syncImageProfileUi();
});
imagePositivePromptInput.addEventListener("input", () => {
  clearManualPromptOverrides();
});
imageNegativePromptInput.addEventListener("input", () => {
  clearManualPromptOverrides();
});
imageLoraNameInput.addEventListener("input", () => {
  syncImageProfileUi();
});
imageScenePlanRunButton.addEventListener("click", () => {
  void buildScenePlan().catch((error) => handleError(error, "scene plan을 생성하지 못했습니다."));
});
imageRenderPlanRunButton.addEventListener("click", () => {
  void buildRenderPlan().catch((error) => handleError(error, "render plan을 생성하지 못했습니다."));
});

preflightRunButton.addEventListener("click", () => {
  void runPreflight().catch((error) => handleError(error, "Pre-flight failed."));
});

systemHealthRunButton.addEventListener("click", () => {
  void runSystemHealth().catch((error) => handleError(error, "System health check failed."));
});
renderReportRunButton.addEventListener("click", () => {
  void runRenderReport().catch((error) => handleError(error, "Render report check failed."));
});
operatorStatusRunButton.addEventListener("click", () => {
  void runOperatorStatus().catch((error) => handleError(error, "Operator status check failed."));
});

cloneProjectButton.addEventListener("click", () => {
  void cloneProject().catch((error) => handleError(error, "Project clone failed."));
});

voiceSelect.addEventListener("change", () => {
  applyTtsPreset(voiceSelect.value);
});

ttsPreviewRunButton.addEventListener("click", () => {
  void generateTtsPreview().catch((error) => handleError(error, "샘플 음성을 생성하지 못했습니다."));
});

for (const element of [
  ttsModeSelect,
  ttsLanguageSelect,
  ttsSpeedInput,
  ttsDurationInput,
  ttsNumStepInput,
  ttsGuidanceInput,
  ttsDenoiseSelect,
  ttsPostprocessSelect,
  ttsInstructInput,
  ttsPreviewTextInput,
]) {
  element.addEventListener("input", () => {
    clearTtsPreviewLock();
  });
  element.addEventListener("change", () => {
    clearTtsPreviewLock();
  });
}

ttsRunButton.addEventListener("click", async () => {
  const project = requireCurrent();
  try {
    const canonicalId = canonicalVoicePresetId(voiceSelect.value);
    const ttsProfile = buildTtsProfilePayload();
    await requestJson(`/api/projects/${project.id}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        voice_preset: canonicalId,
        tts_profile: ttsProfile,
        preview_lock: lastTtsPreviewLock,
      }),
    });
    current = {
      ...project,
      voice_preset: canonicalId,
      tts_profile: (lastTtsPreviewLock && lastTtsPreviewLock.voice_preset === canonicalId)
        ? lastTtsPreviewLock.tts_profile
        : (ttsProfile || presetProfile(canonicalId)),
      tts_state: "running",
      tts_progress: 0,
    };
    renderTtsProfileControls();
    toast("TTS 생성을 시작했습니다.");
  } catch (error) {
    handleError(error, "TTS 생성을 시작하지 못했습니다.");
  }
});

renderRunButton.addEventListener("click", async () => {
  const project = requireCurrent();
  try {
    await requestJson(`/api/projects/${project.id}/render`, {
      method: "POST",
      body: new FormData(),
    });
    current = {
      ...project,
      render_state: "queued",
      render_progress: 0,
      render_phase: "queued",
      render_phase_pct: 0,
      render_progress_detail: "",
      render_speed_x: 0,
      render_eta_sec: 0,
      render_job_id: "",
      render_started_at: "",
      render_heartbeat_at: "",
      render_last_log: "",
    };
    renderState.textContent = "대기 중 0% | 대기 중";
    renderLogPanel.textContent = formatRenderLog("queued", "queued", "", "", "");
    toast("렌더를 시작했습니다.");
  } catch (error) {
    handleError(error, "렌더를 시작하지 못했습니다.");
  }
});

youtubeRunButton.addEventListener("click", async () => {
  const project = requireCurrent();
  try {
    await requestJson(`/api/projects/${project.id}/upload`, {
      method: "POST",
      body: formDataFromObject({
        title: uploadTitleInput.value,
        description: uploadDescInput.value,
        tags: uploadTagsInput.value,
        privacy: uploadPrivacySelect.value,
        schedule_at: uploadScheduleInput.value,
      }),
    });
    toast("YouTube 업로드를 시작했습니다.");
  } catch (error) {
    handleError(error, "YouTube 업로드를 시작하지 못했습니다.");
  }
});


void ensureTtsPresetCatalog()
  .then(() => {
    populateVoiceSelect();
    return loadProjects();
  })
  .catch((error) => handleError(error, "프로젝트 목록을 불러오지 못했습니다."));
