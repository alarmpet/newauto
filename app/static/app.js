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
      return "?꾨즺";
    case "error":
      return "?ㅻ쪟";
    default:
      return "대기";
  }
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
  message: "?낅줈?쒕? ?쒖옉?섎㈃ ?뚯씪蹂?吏꾪뻾 ?곹솴???ш린???쒖떆?⑸땲??",
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
  max_line_chars: 40,
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

/** @type {Record<string, Partial<TtsProfile>>} */
const TTS_PROFILE_PRESETS = {
  auto: { ...DEFAULT_TTS_PROFILE },
  "male-deep-calm": {
    mode: "design",
    language: "ko",
    instruct: "adult male, deep calm studio narration voice",
    speed: 0.96,
    num_step: 36,
    guidance_scale: 2.9,
  },
  "male-mid-clear": {
    mode: "design",
    language: "ko",
    instruct: "adult male, clear neutral explainer voice",
    speed: 1,
    num_step: 34,
    guidance_scale: 2.7,
  },
  "female-bright-clear": {
    mode: "design",
    language: "ko",
    instruct: "adult female, bright clear presenter voice",
    speed: 1.03,
    num_step: 35,
    guidance_scale: 3,
  },
  "female-low-calm": {
    mode: "design",
    language: "ko",
    instruct: "adult female, low calm documentary voice",
    speed: 0.97,
    num_step: 36,
    guidance_scale: 2.8,
  },
  "elder-narration": {
    mode: "design",
    language: "ko",
    instruct: "older adult, warm authoritative narration voice",
    speed: 0.94,
    num_step: 38,
    guidance_scale: 3.1,
  },
  "whisper-story": {
    mode: "design",
    language: "ko",
    instruct: "soft intimate storytelling voice, close mic",
    speed: 0.92,
    num_step: 40,
    guidance_scale: 3.2,
  },
  "english-bright": {
    mode: "design",
    language: "en",
    instruct: "bright clear English presenter voice",
    speed: 1,
    num_step: 34,
    guidance_scale: 2.8,
  },
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
const ttsList = /** @type {HTMLElement} */ (query("#s3-list"));
const renderState = /** @type {HTMLElement} */ (query("#s4-state"));
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
  current = /** @type {Project} */ (await requestJson(`/api/projects/${pid}`));
  selectedMediaName = current.media_order[0] || null;
  mediaClientState = {
    phase: current.media_upload_state === "running" ? "processing" : "idle",
    transferProgress: current.media_upload_state === "done" ? 100 : 0,
    message: current.media_upload_error || "?낅줈?쒕? ?쒖옉?섎㈃ ?뚯씪蹂?吏꾪뻾 ?곹솴???ш린???쒖떆?⑸땲??",
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
  const profile = effectiveTtsProfile(project);
  voiceSelect.value = project.voice_preset;
  ttsModeSelect.value = profile.mode === "design" ? "design" : "auto";
  ttsLanguageSelect.value = profile.language || "ko";
  ttsSpeedInput.value = String(profile.speed);
  ttsDurationInput.value = profile.duration === null ? "" : String(profile.duration);
  ttsNumStepInput.value = String(profile.num_step);
  ttsGuidanceInput.value = String(profile.guidance_scale);
  ttsDenoiseSelect.value = profile.denoise ? "on" : "off";
  ttsPostprocessSelect.value = profile.postprocess_output ? "on" : "off";
  ttsInstructInput.value = profile.instruct;
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
  const preset = TTS_PROFILE_PRESETS[presetId];
  if (!preset) {
    return;
  }
  const merged = {
    ...DEFAULT_TTS_PROFILE,
    ...preset,
  };
  ttsModeSelect.value = merged.mode === "design" ? "design" : "auto";
  ttsLanguageSelect.value = merged.language;
  ttsSpeedInput.value = String(merged.speed);
  ttsDurationInput.value = merged.duration === null ? "" : String(merged.duration);
  ttsNumStepInput.value = String(merged.num_step);
  ttsGuidanceInput.value = String(merged.guidance_scale);
  ttsDenoiseSelect.value = merged.denoise ? "on" : "off";
  ttsPostprocessSelect.value = merged.postprocess_output ? "on" : "off";
  ttsInstructInput.value = merged.instruct;
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
    statusText = `釉뚮씪?곗? ?꾩넚 以?${mediaClientState.transferProgress}%`;
  } else if (mediaClientState.phase === "processing") {
      statusText = project && project.media_upload_state === "running"
        ? `?쒕쾭 ???以?${project.media_upload_progress}%`
        : "전송 완료, 서버 응답 대기 중";
  } else if (mediaClientState.phase === "done") {
    statusText = "?낅줈???꾨즺";
  } else if (mediaClientState.phase === "error") {
    statusText = "?낅줈???ㅻ쪟";
  } else if (project && project.media_upload_state === "running") {
    statusText = `?쒕쾭 ???以?${project.media_upload_progress}%`;
  } else if (project && project.media_upload_state === "done" && project.media_upload_total > 0) {
    statusText = "理쒓렐 ?낅줈???꾨즺";
  }
  mediaUploadStatus.textContent = statusText;

  const summaryParts = [mediaClientState.message].filter(Boolean);
  if (mediaClientState.lastAccepted.length > 0) {
    summaryParts.push(`??λ맂 ?뚯씪: ${mediaClientState.lastAccepted.map((item) => item.saved_name).join(", ")}`);
  }
  if (mediaClientState.lastSkipped.length > 0) {
    summaryParts.push(`嫄대꼫???뚯씪: ${mediaClientState.lastSkipped.map((item) => `${item.name} (${item.reason})`).join(", ")}`);
  }
  if (project && project.media_upload_error) {
    summaryParts.push(`理쒓렐 ?ㅻ쪟: ${project.media_upload_error}`);
  }
  mediaUploadSummary.textContent = summaryParts.join(" 쨌 ") || "?낅줈?쒕? ?쒖옉?섎㈃ ?뚯씪蹂?吏꾪뻾 ?곹솴???ш린???쒖떆?⑸땲??";

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
    mediaPreviewStage.innerHTML = '<div class="media-empty">?꾩쭅 ?낅줈?쒕맂 誘몃뵒?닿? ?놁뒿?덈떎.</div>';
    mediaPreviewMeta.textContent = "?대?吏? ?곸긽???낅줈?쒗븯硫??닿납?먯꽌 ?뺤씤?섍퀬 ?쒖꽌瑜?議곗젙?????덉뒿?덈떎.";
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
    <div><strong>?뚯씪</strong>: ${escapeHtml(selectedName)}</div>
    <div><strong>?뺤떇</strong>: ${selectedKind}</div>
    <div><strong>?쒖꽌</strong>: ${project.media_order.indexOf(selectedName) + 1} / ${project.media_order.length}</div>
  `;
}

/**
 * @returns {void}
 */
function renderThumbnail() {
  const project = requireCurrent();
  thumbnailDeleteButton.disabled = !project.thumbnail_file;
  if (!project.thumbnail_file) {
    thumbnailPreview.innerHTML = '<div class="media-empty">?꾩쭅 ?낅줈?쒕맂 ?몃꽕?쇱씠 ?놁뒿?덈떎.</div>';
    thumbnailMeta.textContent = "YouTube ?낅줈?쒖슜 ?몃꽕?쇱쓣 蹂꾨룄濡?愿由ы븷 ???덉뒿?덈떎.";
    return;
  }

  const thumbnailUrl = `/api/projects/${project.id}/thumbnail`;
  thumbnailPreview.innerHTML = `<img src="${escapeHtml(buildMediaUrl(thumbnailUrl))}" alt="YouTube thumbnail">`;
  thumbnailMeta.innerHTML = `
    <div><strong>?뚯씪</strong>: ${escapeHtml(project.thumbnail_file)}</div>
    <div><strong>?⑸룄</strong>: YouTube ?낅줈?????먮룞 ?몃꽕???ㅼ젙</div>
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
  toast("?몃꽕?쇱쓣 ?낅줈?쒗뻽?듬땲??");
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
  toast("?몃꽕?쇱쓣 ??젣?덉뒿?덈떎.");
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
      80,
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
    ? "Upper, middle, lower positions use fixed screen anchors. Vertical margin mainly affects top and bottom."
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
    subtitlePreviewCaption.style.top = "25%";
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
    subtitlePreviewCaption.style.top = "75%";
    subtitlePreviewCaption.style.transform = style.effect === "pop"
      ? "translate(-50%, -50%) scale(1.05)"
      : "translate(-50%, -50%)";
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
  toast("?먮쭑 ?ㅽ??쇱쓣 ??ν뻽?듬땲??");
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
  toast("誘몃뵒???쒖꽌瑜???ν뻽?듬땲??");
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
    message: "釉뚮씪?곗??먯꽌 ?쒕쾭濡??뚯씪???꾩넚?섍퀬 ?덉뒿?덈떎.",
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
      mediaClientState.message = "?꾩넚???앸궗?듬땲?? ?쒕쾭媛 ?뚯씪????ν븯??以묒엯?덈떎.";
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
        message: `?낅줈???꾨즺: ${response.accepted_files.length}媛???? ${response.skipped_files.length}媛?嫄대꼫?`,
        lastAccepted: response.accepted_files,
        lastSkipped: response.skipped_files,
      };
      renderMedia();
      renderMediaUploadStatus();
      updateProgressBar();
      updateStepMarks();
      toast("誘몃뵒???낅줈?쒓? ?꾨즺?섏뿀?듬땲??");
      return;
    }

    let message = "?낅줈?쒖뿉 ?ㅽ뙣?덉뒿?덈떎.";
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
      message: "?ㅽ듃?뚰겕 ?ㅻ쪟濡??낅줈?쒖뿉 ?ㅽ뙣?덉뒿?덈떎.",
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
    oauthPanel.innerHTML = "YouTube OAuth媛 ?곌껐?섏뼱 ?덉뒿?덈떎.";
  } else if (!oauthStatus.client_secret_present) {
    oauthPanel.className = "card warn";
    oauthPanel.innerHTML = "storage/oauth/client_secret.json ?뚯씪??諛곗튂?????ㅼ떆 ?쒕룄?섏꽭??";
  } else {
    oauthPanel.className = "card warn";
    oauthPanel.innerHTML = 'YouTube ?낅줈????理쒖큹 1???몄쬆???꾩슂?⑸땲?? <button id="btn-auth" class="btn" type="button">Authorize</button>';
    const authButton = /** @type {HTMLButtonElement} */ (query("#btn-auth", oauthPanel));
    authButton.addEventListener("click", async () => {
      oauthPanel.innerHTML = "釉뚮씪?곗? 李쎌뿉??Google 濡쒓렇?멸낵 沅뚰븳 ?덉슜???꾨즺?????뚯븘? 二쇱꽭??";
      try {
        await requestJson("/api/projects/_/oauth/authorize", { method: "POST", body: new FormData() });
        toast("OAuth ?몄쬆???꾨즺?섏뿀?듬땲??");
      } catch (error) {
        handleError(error, "OAuth ?몄쬆???ㅽ뙣?덉뒿?덈떎.");
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

  ttsState.textContent = `${readableTaskState(status.tts_state)} 쨌 ${status.tts_progress}%`;
  renderState.textContent = `${readableTaskState(status.render_state)} 쨌 ${status.render_progress}%`;
  uploadState.textContent = `${readableTaskState(status.upload_state)} 쨌 ${status.upload_progress}%`;
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

navProjects.addEventListener("click", () => {
  stopPoll();
  show("projects");
  void loadProjects().catch((error) => handleError(error, "?꾨줈?앺듃 紐⑸줉??遺덈윭?ㅼ? 紐삵뻽?듬땲??"));
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
    handleError(error, "?꾨줈?앺듃瑜?留뚮뱾吏 紐삵뻽?듬땲??");
  }
});

projectsList.addEventListener("click", async (event) => {
  const target = /** @type {HTMLElement} */ (event.target);
  const projectId = target.dataset.delete;
  if (!projectId) {
    return;
  }
  event.stopPropagation();
  if (!window.confirm("???꾨줈?앺듃瑜???젣?좉퉴??")) {
    return;
  }
  try {
    await requestJson(`/api/projects/${projectId}`, { method: "DELETE" });
    await loadProjects();
  } catch (error) {
    handleError(error, "?꾨줈?앺듃瑜???젣?섏? 紐삵뻽?듬땲??");
  }
});

backButton.addEventListener("click", () => {
  stopPoll();
  show("projects");
  void loadProjects().catch((error) => handleError(error, "?꾨줈?앺듃 紐⑸줉??遺덈윭?ㅼ? 紐삵뻽?듬땲??"));
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
    toast("?ㅽ겕由쏀듃瑜???ν뻽?듬땲??");
  } catch (error) {
    handleError(error, "?ㅽ겕由쏀듃瑜???ν븯吏 紐삵뻽?듬땲??");
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
  void uploadThumbnail(file).catch((error) => handleError(error, "?몃꽕?쇱쓣 ?낅줈?쒗븯吏 紐삵뻽?듬땲??"));
});

thumbnailDeleteButton.addEventListener("click", () => {
  void deleteThumbnail().catch((error) => handleError(error, "?몃꽕?쇱쓣 ??젣?섏? 紐삵뻽?듬땲??"));
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
    void deleteMedia(name).catch((error) => handleError(error, "誘몃뵒?대? ??젣?섏? 紐삵뻽?듬땲??"));
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
  void saveSubtitleStyle().catch((error) => handleError(error, "?먮쭑 ?ㅽ??쇱쓣 ??ν븯吏 紐삵뻽?듬땲??"));
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

ttsRunButton.addEventListener("click", async () => {
  const project = requireCurrent();
  try {
    const ttsProfile = readTtsProfileInputs();
    await requestJson(`/api/projects/${project.id}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        voice_preset: voiceSelect.value,
        tts_profile: ttsProfile,
      }),
    });
    current = {
      ...project,
      voice_preset: voiceSelect.value,
      tts_profile: ttsProfile,
      tts_state: "running",
      tts_progress: 0,
    };
    renderTtsProfileControls();
    toast("TTS ?앹꽦???쒖옉?덉뒿?덈떎.");
  } catch (error) {
    handleError(error, "TTS ?앹꽦???쒖옉?섏? 紐삵뻽?듬땲??");
  }
});

renderRunButton.addEventListener("click", async () => {
  const project = requireCurrent();
  try {
    await requestJson(`/api/projects/${project.id}/render`, {
      method: "POST",
      body: new FormData(),
    });
    toast("?뚮뜑留곸쓣 ?쒖옉?덉뒿?덈떎.");
  } catch (error) {
    handleError(error, "?뚮뜑留곸쓣 ?쒖옉?섏? 紐삵뻽?듬땲??");
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
    toast("YouTube ?낅줈?쒕? ?쒖옉?덉뒿?덈떎.");
  } catch (error) {
    handleError(error, "YouTube ?낅줈?쒕? ?쒖옉?섏? 紐삵뻽?듬땲??");
  }
});


void loadProjects().catch((error) => handleError(error, "?꾨줈?앺듃 紐⑸줉??遺덈윭?ㅼ? 紐삵뻽?듬땲??"));
