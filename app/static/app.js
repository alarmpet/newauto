// @ts-check

/**
 * @typedef {"idle" | "running" | "done" | "error"} TaskState
 * @typedef {"image" | "video"} MediaKind
 * @typedef {"idle" | "uploading" | "processing" | "done" | "error"} MediaClientPhase
 */

/**
 * @typedef {{
 *   id: string,
 *   title: string,
 *   script: string,
 *   sentences: string[],
 *   media_order: string[],
 *   voice_preset: string,
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
  message: "업로드를 시작하면 파일별 진행 상황이 여기에 표시됩니다.",
  lastAccepted: [],
  lastSkipped: [],
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
const ttsState = /** @type {HTMLElement} */ (query("#s3-state"));
const ttsList = /** @type {HTMLElement} */ (query("#s3-list"));
const renderState = /** @type {HTMLElement} */ (query("#s4-state"));
const renderVideo = /** @type {HTMLVideoElement} */ (query("#s4-video"));
const oauthPanel = /** @type {HTMLElement} */ (query("#oauth-panel"));
const uploadTitleInput = /** @type {HTMLInputElement} */ (query("#s5-title"));
const uploadDescInput = /** @type {HTMLTextAreaElement} */ (query("#s5-desc"));
const uploadTagsInput = /** @type {HTMLInputElement} */ (query("#s5-tags"));
const uploadPrivacySelect = /** @type {HTMLSelectElement} */ (query("#s5-privacy"));
const uploadState = /** @type {HTMLElement} */ (query("#s5-state"));
const uploadLink = /** @type {HTMLElement} */ (query("#s5-link"));
const backButton = /** @type {HTMLButtonElement} */ (query("#back"));
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
    message: current.media_upload_error || "업로드를 시작하면 파일별 진행 상황이 여기에 표시됩니다.",
    lastAccepted: [],
    lastSkipped: [],
  };

  show("workflow");
  workflowTitle.textContent = current.title || "Untitled Project";
  workflowId.textContent = current.id;
  scriptTitleInput.value = current.title;
  scriptInput.value = current.script;
  voiceSelect.value = current.voice_preset;
  uploadTitleInput.value = current.title || "";
  uploadDescInput.value = "";
  uploadTagsInput.value = "";
  uploadPrivacySelect.value = "private";

  renderScriptStats();
  renderMedia();
  renderMediaUploadStatus();
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

  mediaWorkflowHint.textContent = `전체 제작 단계 진행률은 ${workflowPercent}%이며, 아래 막대는 실제 미디어 업로드 상태만 보여줍니다.`;

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
      ? `서버 저장 중 ${project.media_upload_progress}%`
      : "전송 완료, 서버 응답 대기 중";
  } else if (mediaClientState.phase === "done") {
    statusText = "업로드 완료";
  } else if (mediaClientState.phase === "error") {
    statusText = "업로드 오류";
  } else if (project && project.media_upload_state === "running") {
    statusText = `서버 저장 중 ${project.media_upload_progress}%`;
  } else if (project && project.media_upload_state === "done" && project.media_upload_total > 0) {
    statusText = "최근 업로드 완료";
  }
  mediaUploadStatus.textContent = statusText;

  const summaryParts = [mediaClientState.message].filter(Boolean);
  if (mediaClientState.lastAccepted.length > 0) {
    summaryParts.push(`저장된 파일: ${mediaClientState.lastAccepted.map((item) => item.saved_name).join(", ")}`);
  }
  if (mediaClientState.lastSkipped.length > 0) {
    summaryParts.push(`건너뛴 파일: ${mediaClientState.lastSkipped.map((item) => `${item.name} (${item.reason})`).join(", ")}`);
  }
  if (project && project.media_upload_error) {
    summaryParts.push(`최근 오류: ${project.media_upload_error}`);
  }
  mediaUploadSummary.textContent = summaryParts.join(" · ") || "업로드를 시작하면 파일별 진행 상황이 여기에 표시됩니다.";

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
    mediaPreviewStage.innerHTML = '<div class="media-empty">아직 업로드된 미디어가 없습니다.</div>';
    mediaPreviewMeta.textContent = "이미지와 영상을 업로드하면 이곳에서 확인하고 순서를 조정할 수 있습니다.";
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
      mediaClientState.message = "전송이 끝났습니다. 서버가 파일을 저장하는 중입니다.";
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
        message: `업로드 완료: ${response.accepted_files.length}개 저장, ${response.skipped_files.length}개 건너뜀`,
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
 * @returns {void}
 */
function updateOutputVideo() {
  const project = requireCurrent();
  if (project.render_state === "done") {
    renderVideo.src = `/api/projects/${project.id}/output?t=${Date.now()}`;
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
  const oauthStatus = /** @type {OAuthStatus} */ (await requestJson("/api/projects/_/oauth/status"));

  if (oauthStatus.authorized) {
    oauthPanel.className = "card ok";
    oauthPanel.innerHTML = "YouTube OAuth가 연결되어 있습니다.";
  } else if (!oauthStatus.client_secret_present) {
    oauthPanel.className = "card warn";
    oauthPanel.innerHTML = "storage/oauth/client_secret.json 파일을 배치한 뒤 다시 시도하세요.";
  } else {
    oauthPanel.className = "card warn";
    oauthPanel.innerHTML = 'YouTube 업로드 전 최초 1회 인증이 필요합니다. <button id="btn-auth" class="btn" type="button">Authorize</button>';
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

  ttsState.textContent = `${readableTaskState(status.tts_state)} · ${status.tts_progress}%`;
  renderState.textContent = `${readableTaskState(status.render_state)} · ${status.render_progress}%`;
  uploadState.textContent = `${readableTaskState(status.upload_state)} · ${status.upload_progress}%`;
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

ttsRunButton.addEventListener("click", async () => {
  const project = requireCurrent();
  try {
    await requestJson(`/api/projects/${project.id}/tts`, {
      method: "POST",
      body: formDataFromObject({ voice_preset: voiceSelect.value }),
    });
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
    toast("렌더링을 시작했습니다.");
  } catch (error) {
    handleError(error, "렌더링을 시작하지 못했습니다.");
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
      }),
    });
    toast("YouTube 업로드를 시작했습니다.");
  } catch (error) {
    handleError(error, "YouTube 업로드를 시작하지 못했습니다.");
  }
});

void loadProjects().catch((error) => handleError(error, "프로젝트 목록을 불러오지 못했습니다."));
