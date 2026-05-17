// @ts-check

/** @typedef {{id: string, title: string, updated_at?: string, body_image_state?: string}} ProjectCard */
/** @typedef {{id: string, title: string, script: string}} ProjectRecord */

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
  const project = /** @type {ProjectRecord} */ (await api("/api/projects", {
    method: "POST",
    body: JSON.stringify({title}),
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
  const updated = /** @type {ProjectRecord} */ (await api(`/api/projects/${currentProject.id}`, {
    method: "PATCH",
    body: JSON.stringify({
      title: scriptTitle?.value || currentProject.title,
      script: scriptText?.value || "",
    }),
  }));
  showWorkflow(updated);
});

void loadProjects();
