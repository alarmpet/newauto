// @ts-check

/**
 * @typedef {"idle" | "running" | "done" | "error"} TaskState
 * @typedef {"image" | "video"} MediaKind
 * @typedef {"idle" | "uploading" | "processing" | "done" | "error"} MediaClientPhase
 * @typedef {"top" | "upper" | "middle" | "lower" | "bottom"} SubtitlePosition
 * @typedef {"none" | "fade" | "pop" | "karaoke"} SubtitleEffect
 * @typedef {"auto" | "design" | "clone"} TtsMode
 * @typedef {"landscape" | "shorts"} RenderFormat
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
 *   language: string,
 *   instruct: string,
 *   speed: number,
 *   duration: number | null,
 *   num_step: number,
 *   guidance_scale: number,
 *   denoise: boolean,
 *   postprocess_output: boolean,
 * }} TtsProfile
 */

/**
 * @typedef {{
 *   id: string,
 *   title: string,
 *   script: string,
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
 *   render_state: TaskState,
 *   render_progress: number,
 *   render_phase: string,
 *   render_last_log: string,
 *   upload_state: TaskState,
 *   upload_progress: number,
 *   media_upload_state: TaskState,
 *   media_upload_progress: number,
 *   media_upload_completed: number,
 *   media_upload_total: number,
 *   media_upload_error: string,
 *   thumbnail_file: string,
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
 *   preview_url: string,
  *   sample_text: string,
  *   voice_preset: string,
  *   tts_profile: TtsProfile,
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
 * @param {string} phase
 * @param {string} renderLog
 * @returns {string}
 */
function formatRenderLog(phase, renderLog) {
  if (!renderLog) {
    return "렌더를 시작하면 현재 단계와 마지막 로그를 여기에서 확인할 수 있습니다.";
  }
  const summary = readableRenderIssue(renderLog);
  const lines = [`Current phase: ${readableRenderPhase(phase)}`];
  if (summary) {
    lines.push("", `문제 요약: ${summary}`);
  }
  lines.push("", renderLog);
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
/** @type {number | null} */
let pollTimer = null;
/** @type {string | null} */
let selectedMediaName = null;
/** @type {string | null} */
let draggingMediaName = null;
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
  language: "ko",
  instruct: "",
  speed: 1,
  duration: null,
  num_step: 32,
  guidance_scale: 2.6,
  denoise: true,
  postprocess_output: true,
};

const DEFAULT_TTS_SAMPLE_TEXT = "안녕하세요. 지금 들으시는 음성은 현재 보이스 설정으로 만든 짧은 샘플입니다.";
/** @type {TtsPresetCatalogResponse | null} */
let ttsPresetCatalog = null;
let ttsFormDirtyAfterPreset = false;

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
const scriptTitleInput = /** @type {HTMLInputElement} */ (query("#s1-title"));
const scriptInput = /** @type {HTMLTextAreaElement} */ (query("#s1-script"));
const scriptCount = /** @type {HTMLElement} */ (query("#s1-count"));
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
const preflightResults = /** @type {HTMLElement} */ (query("#preflight-results"));
const systemHealthResults = /** @type {HTMLElement} */ (query("#system-health-results"));
const featureKenburnsSelect = /** @type {HTMLSelectElement} */ (query("#feature-kenburns"));
const featureBgmVolumeInput = /** @type {HTMLInputElement} */ (query("#feature-bgm-volume"));
const featureBgmDuckingSelect = /** @type {HTMLSelectElement} */ (query("#feature-bgm-ducking"));
const featureRenderLandscapeInput = /** @type {HTMLInputElement} */ (query("#feature-render-landscape"));
const featureRenderShortsInput = /** @type {HTMLInputElement} */ (query("#feature-render-shorts"));
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
 * @param {"projects" | "workflow"} view
 * @returns {void}
 */
function show(view) {
  viewProjects.hidden = view !== "projects";
  viewWorkflow.hidden = view !== "workflow";
  workflowNav.hidden = view !== "workflow";
  navProjects.classList.toggle("active", view === "projects");
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
}

/**
 * @returns {Promise<void>}
 */
async function loadProjects() {
  const projects = await requestJson("/api/projects");
  const projectCards = /** @type {ProjectCard[]} */ (projects);
  projectsList.innerHTML = "";
  projectsEmpty.hidden = projectCards.length > 0;

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
  scriptInput.value = current.script;
  uploadTitleInput.value = current.title || "";
  uploadDescInput.value = "";
  uploadTagsInput.value = "";
  uploadPrivacySelect.value = "private";

  renderScriptStats();
  renderMedia();
  renderThumbnail();
  renderBgmMeta();
  renderTtsProfileControls();
  renderFeatureControls();
  renderLogPanel.textContent = formatRenderLog(current.render_phase, current.render_last_log);
  renderMediaUploadStatus();
  renderSubtitleStyleControls();
  renderTtsList();
  renderStep5();
  updateOutputVideo();
  updateProgressBar();
  updateStepMarks();
  showStep(1);
  startPoll();
}

/**
 * @returns {void}
 */
function renderScriptStats() {
  scriptCount.textContent = `문장 ${estimateSentenceCount(scriptInput.value)}개`;
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
    `Effective: ${canonicalId} | mode=${profile.mode} | language=${profile.language} | ` +
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
function renderMedia() {
  const project = requireCurrent();
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
  featureKenburnsSelect.value = project.kenburns_enabled ? "on" : "off";
  featureBgmVolumeInput.value = String(project.bgm_volume_db);
  featureBgmDuckingSelect.value = project.bgm_ducking_enabled ? "on" : "off";
  featureRenderLandscapeInput.checked = project.render_formats.includes("landscape");
  featureRenderShortsInput.checked = project.render_formats.includes("shorts");
}

/**
 * @returns {{kenburns_enabled: boolean, bgm_volume_db: number, bgm_ducking_enabled: boolean, render_formats: RenderFormat[]}}
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
  toast("Render settings saved.");
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
  const payload = /** @type {{ ffmpeg_available: boolean, oauth_ready: boolean, omnivoice_python_found: boolean, disk_free_gb: number, storage_path: string }} */ (
    await requestJson("/api/system/health")
  );
  systemHealthResults.innerHTML = `
    <div><strong>FFmpeg</strong>: ${payload.ffmpeg_available ? "ok" : "missing"}</div>
    <div><strong>OAuth</strong>: ${payload.oauth_ready ? "ready" : "missing client_secret.json"}</div>
    <div><strong>OmniVoice Python</strong>: ${payload.omnivoice_python_found ? "found" : "missing"}</div>
    <div><strong>Disk Free</strong>: ${payload.disk_free_gb} GB</div>
    <div><strong>Storage</strong>: ${escapeHtml(payload.storage_path)}</div>
  `;
  systemHealthResults.className = "card";
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
 * @returns {Promise<void>}
 */
async function fetchYoutubeStats() {
  const project = requireCurrent();
  if (!project.youtube_id) {
    toast("Upload to YouTube first.");
    return;
  }
  const stats = /** @type {{ view_count: number, like_count: number, comment_count: number, video_id: string }} */ (
    await requestJson(`/api/projects/${project.id}/stats`)
  );
  uploadStatsPanel.innerHTML = `
    <div><strong>Video</strong>: ${escapeHtml(stats.video_id)}</div>
    <div><strong>Views</strong>: ${stats.view_count}</div>
    <div><strong>Likes</strong>: ${stats.like_count}</div>
    <div><strong>Comments</strong>: ${stats.comment_count}</div>
  `;
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
  subtitlePositionHint.textContent = usesFixedVerticalAnchor(style.position)
    ? "Upper, middle, lower positions use fixed anchors. Lower is tuned closer to the lower-third area."
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
  subtitlePreviewCaption.style.transform = style.effect === "pop"
    ? "translateX(-50%) scale(1.05)"
    : "translateX(-50%)";
  subtitlePreviewCaption.style.top = "";
  subtitlePreviewCaption.style.bottom = "";
  if (style.position === "top") {
    subtitlePreviewCaption.style.top = `${Math.max(8, Math.round(style.margin_v * 0.25))}px`;
    return;
  }
  if (style.position === "upper") {
    subtitlePreviewCaption.style.top = "28%";
    subtitlePreviewCaption.style.transform = style.effect === "pop"
      ? "translate(-50%, -50%) scale(1.05)"
      : "translate(-50%, -50%)";
    return;
  }
  if (style.position === "middle") {
    subtitlePreviewCaption.style.top = "50%";
    subtitlePreviewCaption.style.transform = style.effect === "pop"
      ? "translate(-50%, -50%) scale(1.05)"
      : "translate(-50%, -50%)";
    return;
  }
  if (style.position === "lower") {
    subtitlePreviewCaption.style.bottom = "14%";
    subtitlePreviewCaption.style.transform = style.effect === "pop"
      ? "translateX(-50%) scale(1.05)"
      : "translateX(-50%)";
    return;
  }
  subtitlePreviewCaption.style.bottom = `${Math.max(8, Math.round(style.margin_v * 0.25))}px`;
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

  project.sentences.forEach((sentence, index) => {
    const row = document.createElement("div");
    row.className = "tts-row";
    const pad = String(index).padStart(4, "0");
    row.innerHTML = `
      <div class="idx">${index + 1}</div>
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
    ttsPreviewAudio.src = `${response.preview_url}?t=${Date.now()}`;
    ttsPreviewAudio.load();
    void ttsPreviewAudio.play().catch(() => {
      // Some browsers block autoplay after async work.
    });
    ttsPreviewState.textContent = `샘플 준비 완료: ${response.sample_text}`;
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
  const renderPhaseText = status.render_state === "running" && status.render_phase
    ? ` | ${readableRenderPhase(status.render_phase)}`
    : "";
  renderState.textContent = `${readableTaskState(status.render_state)} ${status.render_progress}%${renderPhaseText}`;
  renderLogPanel.textContent = formatRenderLog(status.render_phase, status.render_last_log);
  uploadState.textContent = `${readableTaskState(status.upload_state)} ${status.upload_progress}%`;
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
}

/**
 * @returns {void}
 */
function stopPoll() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
  }
  pollTimer = null;
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
        }),
      })
    );
    workflowTitle.textContent = current.title || "Untitled Project";
    renderScriptStats();
    updateProgressBar();
    updateStepMarks();
    toast("스크립트를 저장했습니다.");
  } catch (error) {
    handleError(error, "스크립트를 저장하지 못했습니다.");
  }
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

preflightRunButton.addEventListener("click", () => {
  void runPreflight().catch((error) => handleError(error, "Pre-flight failed."));
});

systemHealthRunButton.addEventListener("click", () => {
  void runSystemHealth().catch((error) => handleError(error, "System health check failed."));
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
      }),
    });
    current = {
      ...project,
      voice_preset: canonicalId,
      tts_profile: ttsProfile || presetProfile(canonicalId),
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
