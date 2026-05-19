// @ts-check

/** @typedef {{id: string, title: string, updated_at?: string, body_image_state?: string}} ProjectCard */
/** @typedef {{sentence_idx: number, positive_prompt: string, negative_prompt: string}} PromptSuggestion */
/** @typedef {{id: string, title: string, script: string, sentences?: string[], body_image_state?: string, body_image_progress?: number, body_image_phase?: string, body_image_last_log?: string}} ProjectRecord */
/** @typedef {{stage: string, state: string, issues?: string[], primary_action?: string}} StageCard */

const projectsView = document.querySelector("#view-projects");
const workflowView = document.querySelector("#view-workflow");
const projectsList = document.querySelector("#projects-list");
const projectsEmpty = /** @type {HTMLElement | null} */ (document.querySelector("#projects-empty"));
const newTitle = /** @type {HTMLInputElement | null} */ (document.querySelector("#new-title"));
const createButton = document.querySelector("#btn-new");
const backButton = document.querySelector("#back");
const workflowTitle = document.querySelector("#wf-title");
const workflowId = document.querySelector("#wf-id");
const scriptTitle = /** @type {HTMLInputElement | null} */ (document.querySelector("#s1-title"));
const scriptText = /** @type {HTMLTextAreaElement | null} */ (document.querySelector("#s1-script"));
const saveScriptButton = document.querySelector("#s1-save");
const sentenceSelect = /** @type {HTMLSelectElement | null} */ (document.querySelector("#s2-sentence"));
const aspectSelect = /** @type {HTMLSelectElement | null} */ (document.querySelector("#s2-aspect"));
const negativeInput = /** @type {HTMLInputElement | null} */ (document.querySelector("#s2-negative"));
const previewButton = document.querySelector("#s2-preview");
const generateOneButton = document.querySelector("#s2-generate-one");
const generateAllButton = document.querySelector("#s2-generate-all");
const promptPreview = /** @type {HTMLTextAreaElement | null} */ (document.querySelector("#s2-prompt-preview"));
const imageStatus = /** @type {HTMLElement | null} */ (document.querySelector("#s2-status"));
const workflowStageCards = /** @type {HTMLElement | null} */ (document.querySelector("#workflow-stage-cards"));

/** @type {ProjectRecord | null} */
let currentProject = null;

/**
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<any>}
 */
async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

function showProjects() {
  projectsView?.removeAttribute("hidden");
  workflowView?.setAttribute("hidden", "");
  currentProject = null;
}

/**
 * @param {ProjectRecord} project
 */
function showWorkflow(project) {
  currentProject = project;
  projectsView?.setAttribute("hidden", "");
  workflowView?.removeAttribute("hidden");
  if (workflowTitle) workflowTitle.textContent = project.title || "Untitled";
  if (workflowId) workflowId.textContent = project.id;
  if (scriptTitle) scriptTitle.value = project.title || "";
  if (scriptText) scriptText.value = project.script || "";
  renderImageControls(project);
  void refreshWorkflowStatus();
}

/**
 * @param {ProjectRecord} project
 */
function renderImageControls(project) {
  if (sentenceSelect) {
    sentenceSelect.textContent = "";
    const sentences = project.sentences || splitSentences(project.script || "");
    sentences.forEach((sentence, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = `${index + 1}. ${sentence.slice(0, 54)}`;
      sentenceSelect.appendChild(option);
    });
  }
  updateImageStatus(project);
}

/**
 * @param {string} script
 * @returns {string[]}
 */
function splitSentences(script) {
  return script.split(/\n+/).map((line) => line.trim()).filter(Boolean);
}

/**
 * @param {ProjectRecord} project
 */
function updateImageStatus(project) {
  if (!imageStatus) return;
  const state = project.body_image_state || "idle";
  const progress = Number(project.body_image_progress || 0);
  const phase = project.body_image_phase || "";
  const log = project.body_image_last_log || "";
  imageStatus.textContent = `State: ${state} ${progress}% ${phase}${log ? ` - ${log}` : ""}`;
}

function imagePayload() {
  return {
    sentence_idx: Number(sentenceSelect?.value || 0),
    aspect_ratio: aspectSelect?.value || "16:9",
    negative_prompt_override: negativeInput?.value || "",
  };
}

async function refreshCurrentProject() {
  if (!currentProject) return;
  currentProject = /** @type {ProjectRecord} */ (await api(`/api/projects/${currentProject.id}`));
  renderImageControls(currentProject);
  await refreshWorkflowStatus();
}

/**
 * @param {StageCard[]} cards
 */
function renderStageCards(cards) {
  if (!workflowStageCards) return;
  workflowStageCards.textContent = "";
  for (const card of cards) {
    const item = document.createElement("div");
    item.className = "stage-card";
    const issues = (card.issues || []).join(", ");
    item.innerHTML = `
      <strong>${escapeHtml(card.stage)}</strong>
      <span>${escapeHtml(card.state)}</span>
      <small>${escapeHtml(card.primary_action || "review")}</small>
      ${issues ? `<em>${escapeHtml(issues)}</em>` : ""}
    `;
    workflowStageCards.appendChild(item);
  }
}

async function refreshWorkflowStatus() {
  if (!currentProject) return;
  const response = await fetch(`/api/projects/${currentProject.id}/workflow-status`);
  if (!response.ok) return;
  const payload = await response.json();
  renderStageCards(/** @type {StageCard[]} */ (payload.stage_cards || []));
}

async function loadProjects() {
  const projects = /** @type {ProjectCard[]} */ (await api("/api/projects"));
  if (!projectsList) return;
  projectsList.textContent = "";
  if (projectsEmpty) projectsEmpty.hidden = projects.length > 0;
  for (const project of projects) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "project-card";
    button.innerHTML = `<strong>${escapeHtml(project.title || "Untitled")}</strong><span>${escapeHtml(project.id)}</span>`;
    button.addEventListener("click", async () => {
      const fullProject = /** @type {ProjectRecord} */ (await api(`/api/projects/${project.id}`));
      showWorkflow(fullProject);
    });
    projectsList.appendChild(button);
  }
}

/**
 * @param {unknown} value
 * @returns {string}
 */
function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

createButton?.addEventListener("click", async () => {
  const title = newTitle?.value.trim() || "Untitled";
  const form = new FormData();
  form.set("title", title);
  const project = /** @type {ProjectRecord} */ (await api("/api/projects", {
    method: "POST",
    headers: {},
    body: form,
  }));
  await loadProjects();
  showWorkflow(project);
});

backButton?.addEventListener("click", () => {
  showProjects();
  void loadProjects();
});

saveScriptButton?.addEventListener("click", async () => {
  if (!currentProject) return;
  const form = new FormData();
  form.set("title", scriptTitle?.value || currentProject.title);
  form.set("script", scriptText?.value || "");
  const updated = /** @type {ProjectRecord} */ (await api(`/api/projects/${currentProject.id}/script`, {
    method: "PUT",
    headers: {},
    body: form,
  }));
  showWorkflow(updated);
});

previewButton?.addEventListener("click", async () => {
  if (!currentProject || !promptPreview) return;
  const payload = imagePayload();
  const suggestion = /** @type {PromptSuggestion} */ (await api(
    `/api/projects/${currentProject.id}/comfyui/prompt-suggestion?sentence_idx=${payload.sentence_idx}`,
  ));
  promptPreview.value = `${suggestion.positive_prompt}\n\nNegative:\n${suggestion.negative_prompt}`;
});

generateOneButton?.addEventListener("click", async () => {
  if (!currentProject) return;
  await api(`/api/projects/${currentProject.id}/comfyui/job`, {
    method: "POST",
    body: JSON.stringify(imagePayload()),
  });
  await refreshCurrentProject();
});

generateAllButton?.addEventListener("click", async () => {
  if (!currentProject) return;
  await api(`/api/projects/${currentProject.id}/comfyui/job/batch-auto`, {
    method: "POST",
    body: JSON.stringify(imagePayload()),
  });
  await refreshCurrentProject();
});

void loadProjects();
