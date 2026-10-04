"use strict";

const form = document.getElementById("project-form");
const formStatus = document.getElementById("form-status");
const projectList = document.getElementById("project-list");
const refreshButton = document.getElementById("refresh");
const workflow = document.getElementById("workflow");
let activeProjectId = null;
let activeRunId = null;
let activeRun = null;
let activePreviewId = null;
let activePreview = null;
let viewerMode = "preview";
let pollTimer = null;
let previewPollTimer = null;
let placementDirty = false;
let placementRevision = 0;
let savedPlacement = null;
let runActive = false;
let captureRequestId = null;
let capturePending = false;
const browseDesign = document.getElementById("browse-design");
const createProjectButton = form.querySelector('button[type="submit"]');
const desktop = window.chrome?.webview;
let pickerRequestId = null;

if (desktop && typeof desktop.postMessage === "function" && typeof desktop.addEventListener === "function") {
  browseDesign.hidden = false;
  document.getElementById("import-help").textContent = "Kies uw Rhino-bestand met Bladeren. Controleer het gekozen pad en maak daarna het project aan.";
  desktop.addEventListener("message", event => {
    const result = event.data;
    if (!pickerRequestId || result?.type !== "parkhaven.pickDesignResult" || result.requestId !== pickerRequestId) return;
    pickerRequestId = null;
    browseDesign.disabled = false;
    createProjectButton.disabled = false;
    if (result.status === "selected" && typeof result.path === "string" && result.path) {
      document.getElementById("design-path").value = result.path;
      formStatus.textContent = "Bestand gekozen. Selecteer Project aanmaken om te importeren.";
    } else if (result.status === "cancelled") {
      formStatus.textContent = "Bestandskeuze geannuleerd. Het huidige pad is behouden.";
    } else {
      formStatus.textContent = result.error || "Het bestand kon niet worden gekozen. Probeer opnieuw.";
    }
  });
  browseDesign.addEventListener("click", () => {
    if (pickerRequestId) return;
    pickerRequestId = crypto.randomUUID();
    browseDesign.disabled = true;
    createProjectButton.disabled = true;
    formStatus.textContent = "Kies een Rhino-bestand in het Windows-venster...";
    try {
      desktop.postMessage({type: "parkhaven.pickDesign", requestId: pickerRequestId});
    } catch (error) {
      pickerRequestId = null;
      browseDesign.disabled = false;
      createProjectButton.disabled = false;
      formStatus.textContent = "De bestandskiezer is niet beschikbaar. U kunt het pad handmatig invullen.";
    }
  });
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toLocaleString("nl-NL") : "Onbekend";
}

function renderProjects(projects) {
  projectList.replaceChildren();
  if (!projects.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Nog geen projecten. Importeer hierboven uw eerste Rhino-ontwerp.";
    projectList.append(empty);
    return;
  }
  for (const project of projects) {
    const article = document.createElement("article");
    const heading = document.createElement("h3");
    const metadata = document.createElement("p");
    const state = document.createElement("span");
    heading.textContent = project.name;
    metadata.textContent = `${project.source.original_filename} · ${formatDate(project.updated_at)}`;
    state.textContent = "GEIMPORTEERD";
    const open = document.createElement("button");
    open.className = "open-project";
    open.textContent = "Verdergaan";
    open.addEventListener("click", () => openProject(project.project_id));
    article.append(heading, metadata, state, open);
    projectList.append(article);
  }
}

function number(value, digits = 1) {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("nl-NL", {maximumFractionDigits: digits}).format(value) : "-";
}

function formPlacement() {
  const numeric = id => document.getElementById(id).valueAsNumber;
  return {
    translation_m: {
      x: numeric("place-x"),
      y: numeric("place-y"),
      z: numeric("place-z"),
    },
    rotation_z_degrees: numeric("place-rotation"),
    approved: document.getElementById("place-approved").checked,
    model_units: document.getElementById("place-model-units").value,
  };
}

function setFormPlacement(placement) {
  document.getElementById("place-x").value = placement.translation_m.x;
  document.getElementById("place-y").value = placement.translation_m.y;
  document.getElementById("place-z").value = placement.translation_m.z;
  document.getElementById("place-rotation").value = placement.rotation_z_degrees;
  document.getElementById("place-approved").checked = placement.approved;
  document.getElementById("place-model-units").value = placement.model_units || "file";
}

function markPlacementDirty(message = "Wijzigingen nog niet opgeslagen. Sla plaatsing en modeleenheid op vóór een nieuwe analyse.") {
  placementDirty = true;
  placementRevision++;
  document.getElementById("placement-status").textContent = message;
  document.getElementById("metrics-provenance").textContent = activeRun?.results
    ? "Getoonde resultaten horen bij de onveranderde laatste analyse, niet bij dit concept." : "";
  updateActionState();
  if (viewerMode === "preview") showViewerMode("preview");
}

function updateActionState() {
  const previewRunning = ["launch_requested", "runner_started", "preparing_model"].includes(activePreview?.status);
  document.getElementById("start-preview").disabled = placementDirty || runActive || previewRunning;
  document.getElementById("cancel-preview").disabled = !previewRunning && activePreview?.status !== "prepared";
  document.getElementById("start-analysis").disabled = runActive || previewRunning || placementDirty;
  document.getElementById("capture-views").disabled = capturePending || viewerMode !== "analysis"
    || activeRun?.status !== "completed" || !activeRun.scene_sha256 || !activeRun.geometry_summary?.sha256;
}

function showViewerMode(mode) {
  viewerMode = mode;
  document.getElementById("show-preview").setAttribute("aria-pressed", String(mode === "preview"));
  document.getElementById("show-analysis").setAttribute("aria-pressed", String(mode === "analysis"));
  document.getElementById("viewer-kind").textContent = mode === "preview" ? "3D / PLAATSINGSPREVIEW" : "3D / LAATSTE ANALYSE";
  const item = mode === "preview" ? activePreview : activeRun;
  const evidenceId = item?.run_id || null;
  const endpoint = mode === "preview" && evidenceId
    ? `/api/projects/${encodeURIComponent(activeProjectId)}/placement-previews/${encodeURIComponent(evidenceId)}/scene.json`
    : evidenceId ? `/api/projects/${encodeURIComponent(activeProjectId)}/runs/${encodeURIComponent(evidenceId)}/scene.json` : null;
  window.dispatchEvent(new CustomEvent("parkhaven-viewer-run", {detail: activeProjectId ? {
    kind: mode, projectId: activeProjectId, evidenceId, endpoint, item,
    currentPlacement: mode === "preview" ? formPlacement() : null,
    placementState: placementDirty ? "draft" : (formPlacement().approved ? "approved" : "saved"),
  } : null}));
  updateActionState();
}

document.getElementById("show-preview").addEventListener("click", () => showViewerMode("preview"));
document.getElementById("show-analysis").addEventListener("click", () => showViewerMode("analysis"));

async function openProject(projectId) {
  window.dispatchEvent(new CustomEvent("parkhaven-viewer-run", {detail: null}));
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {cache: "no-store"});
  if (!response.ok) return;
  const project = await response.json();
  activeProjectId = projectId;
  activeRunId = null;
  activeRun = null;
  activePreviewId = project.placement_preview?.run_id || null;
  activePreview = project.placement_preview || null;
  captureRequestId = null;
  capturePending = false;
  document.getElementById("capture-status").textContent = "Selecteer Laatste analyse na een voltooide run.";
  placementDirty = false;
  placementRevision++;
  clearTimeout(pollTimer);
  clearTimeout(previewPollTimer);
  renderRun({status: "not_started"});
  document.getElementById("active-project-name").textContent = project.name;
  const placement = project.placement;
  savedPlacement = structuredClone(placement);
  setFormPlacement(placement);
  document.getElementById("placement-status").textContent = "";
  workflow.hidden = false;
  workflow.scrollIntoView({behavior: "smooth"});
  if (project.runs.length) {
    activeRunId = project.runs[0].run_id;
    activeRun = project.runs[0];
    renderRun(project.runs[0]);
    schedulePoll();
  }
  renderPreview(activePreview);
  showViewerMode(activePreview ? "preview" : "analysis");
  if (activePreview && !["completed", "failed", "cancelled"].includes(activePreview.status)) schedulePreviewPoll();
}

document.getElementById("close-project").addEventListener("click", () => {
  window.dispatchEvent(new CustomEvent("parkhaven-viewer-run", {detail: null}));
  workflow.hidden = true;
  activeProjectId = null;
  activeRunId = null;
  activeRun = null;
  activePreviewId = null;
  activePreview = null;
  captureRequestId = null;
  capturePending = false;
  savedPlacement = null;
  clearTimeout(pollTimer);
  clearTimeout(previewPollTimer);
});

document.getElementById("placement-form").addEventListener("input", () => {
  markPlacementDirty();
});

window.addEventListener("parkhaven-gizmo-placement", event => {
  const placement = event.detail;
  if (!activeProjectId || viewerMode !== "preview" || !placement?.translation_m) return;
  setFormPlacement({...formPlacement(), ...placement, approved: false});
  markPlacementDirty("Plaatsing met het 3D-gereedschap gewijzigd. Sla het concept expliciet op.");
});

document.getElementById("gizmo-reset").addEventListener("click", () => {
  if (!savedPlacement) return;
  setFormPlacement(savedPlacement);
  placementDirty = false;
  placementRevision++;
  document.getElementById("placement-status").textContent = "Opgeslagen plaatsing hersteld; er is niets gewijzigd.";
  document.getElementById("metrics-provenance").textContent = activeRun?.results
    ? `Resultaten van run ${activeRun.run_id}. Plaatsingswijzigingen vereisen een nieuwe analyse.` : "";
  updateActionState();
  if (viewerMode === "preview") showViewerMode("preview");
});

document.getElementById("placement-form").addEventListener("submit", async event => {
  event.preventDefault();
  const projectId = activeProjectId, revision = placementRevision;
  const placement = formPlacement();
  const payload = {x: placement.translation_m.x, y: placement.translation_m.y, z: placement.translation_m.z,
    rotation_z_degrees: placement.rotation_z_degrees, approved: placement.approved, model_units: placement.model_units};
  const response = await fetch(`/api/projects/${projectId}/placement`, {
    method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (projectId !== activeProjectId || revision !== placementRevision) return;
  if (response.ok) {
    placementDirty = false;
    savedPlacement = structuredClone(result);
    updateActionState();
    if (viewerMode === "preview") showViewerMode("preview");
  }
  document.getElementById("placement-status").textContent = response.ok
    ? (result.approved ? "Plaatsing en modeleenheid opgeslagen. Start een nieuwe analyse om wijzigingen door te rekenen." : "Conceptplaatsing opgeslagen.")
    : result.detail;
});

document.getElementById("start-preview").addEventListener("click", async () => {
  const projectId = activeProjectId;
  document.getElementById("start-preview").disabled = true;
  document.getElementById("preview-status").textContent = "Preview voorbereiden en Rhino starten...";
  try {
    const response = await fetch(`/api/projects/${projectId}/placement-preview`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({launch_rhino: true}),
    });
    const result = await response.json();
    if (projectId !== activeProjectId) return;
    if (!response.ok) throw new Error(result.detail);
    activePreview = result;
    activePreviewId = result.run_id;
    renderPreview(result);
    showViewerMode("preview");
    schedulePreviewPoll();
  } catch (error) {
    if (projectId === activeProjectId) {
      document.getElementById("preview-status").textContent = error.message;
      updateActionState();
    }
  }
});

document.getElementById("cancel-preview").addEventListener("click", async () => {
  const projectId = activeProjectId, previewId = activePreviewId;
  document.getElementById("cancel-preview").disabled = true;
  try {
    const response = await fetch(`/api/projects/${projectId}/placement-previews/${previewId}/cancel`, {method: "POST"});
    const result = await response.json();
    if (projectId !== activeProjectId || previewId !== activePreviewId) return;
    if (!response.ok) throw new Error(result.detail);
    clearTimeout(previewPollTimer);
    activePreview = result;
    renderPreview(result);
    showViewerMode("preview");
  } catch (error) {
    if (projectId === activeProjectId && previewId === activePreviewId) {
      document.getElementById("preview-status").textContent = error.message;
      updateActionState();
    }
  }
});

document.getElementById("start-analysis").addEventListener("click", async () => {
  const projectId = activeProjectId;
  const status = document.getElementById("analysis-status");
  const button = document.getElementById("start-analysis");
  button.disabled = true;
  status.textContent = "Run voorbereiden en Rhino starten...";
  try {
    const response = await fetch(`/api/projects/${projectId}/analysis`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({launch_rhino: true}),
    });
    const result = await response.json();
    if (activeProjectId !== projectId) return;
    if (!response.ok) throw new Error(result.detail);
    activeRunId = result.run_id;
    renderRun(result);
    schedulePoll();
  } catch (error) {
    if (activeProjectId === projectId) { status.textContent = error.message; updateActionState(); }
  }
});

document.getElementById("cancel-analysis").addEventListener("click", async () => {
  const projectId = activeProjectId, runId = activeRunId;
  const button = document.getElementById("cancel-analysis");
  button.disabled = true;
  try {
    const response = await fetch(`/api/projects/${projectId}/runs/${runId}/cancel`, {method: "POST"});
    const result = await response.json();
    if (projectId !== activeProjectId || runId !== activeRunId) return;
    if (!response.ok) throw new Error(result.detail);
    clearTimeout(pollTimer);
    renderRun(result);
  } catch (error) {
    if (projectId === activeProjectId && runId === activeRunId) {
      document.getElementById("analysis-status").textContent = error.message;
      button.disabled = false;
    }
  }
});

function renderRun(run) {
  const labels = {not_started: "Nog geen analyse gestart.", prepared: "Voorbereid", launch_requested: "Rhino wordt gestart", runner_started: "Rhino-plug-in gestart", preparing_model: "Model voorbereiden", solving: "Grasshopper rekent", completed: "Analyse voltooid", failed: "Analyse mislukt", cancelled: "Analyse geannuleerd"};
  const running = ["launch_requested", "runner_started", "preparing_model", "solving"].includes(run.status);
  runActive = running;
  activeRun = run.status === "not_started" ? null : run;
  document.getElementById("cancel-analysis").disabled = !running && run.status !== "prepared";
  const launchHelp = run.status === "launch_requested"
    ? "Rhino wordt gestart. Loopt de status niet door? Voer ParkHavenAnalyze uit in de Rhino-sessie die de app heeft geopend." : null;
  const progress = running && run.progress_detail ? `${labels[run.status]} · ${run.progress_detail}` : null;
  document.getElementById("analysis-status").textContent = run.error || launchHelp || progress || labels[run.status] || run.status;
  const units = run.model_units;
  document.getElementById("analysis-units").textContent = units
    ? `Deze run: bestand ${units.declared} → coördinaten geïnterpreteerd als ${units.interpreted}; schaalfactor ${number(units.coordinate_scale, 6)}.`
      + (Array.isArray(units.physical_size_m) ? ` Ontwerpomvang: ${units.physical_size_m.map(value => number(value, 3)).join(" × ")} m.` : "")
    : "";
  document.getElementById("analysis-warnings").textContent = Array.isArray(run.warnings) ? run.warnings.join(" ") : "";
  updateActionState();
  if (viewerMode === "analysis") showViewerMode("analysis");
  document.getElementById("metrics").hidden = true;
  if (run.status === "completed" && run.results) {
    document.getElementById("metrics").hidden = false;
    document.getElementById("metric-bvo").textContent = `${number(run.results.bvo_m2)} m2`;
    document.getElementById("metric-sight").textContent = `${number(run.results.sight_pct)}%`;
    document.getElementById("metric-cost").textContent = `EUR ${number(run.results.indicative_cost_eur, 0)}`;
  }
  document.getElementById("metrics-provenance").textContent = run.status === "completed" && run.results
    ? (placementDirty ? "Getoonde resultaten horen bij de onveranderde laatste analyse, niet bij dit concept."
      : `Resultaten van run ${run.run_id}. Plaatsingswijzigingen vereisen een nieuwe analyse.`) : "";
  const complete = run.status === "completed";
  const aiReady = complete && run.view_evidence_available === true;
  document.querySelector("#ai-form button").disabled = !aiReady;
  document.getElementById("ai-status").textContent = complete && !aiReady
    ? "Leg eerst vier modelbeelden vast voor model-grounded AI-advies."
    : (aiReady ? "Modelbeelden en rekenresultaten zijn gereed voor AI-advies." : "Beschikbaar na een voltooide analyse.");
  const report = document.getElementById("report-link");
  report.classList.toggle("disabled", !complete);
  report.setAttribute("aria-disabled", String(!complete));
  report.href = complete ? `/projects/${activeProjectId}/runs/${activeRunId}/report` : "#";
}

document.getElementById("capture-views").addEventListener("click", () => {
  if (!activeRunId || viewerMode !== "analysis" || capturePending) return;
  captureRequestId = crypto.randomUUID();
  capturePending = true;
  document.getElementById("capture-status").textContent = "Vier gecontroleerde modelbeelden renderen...";
  updateActionState();
  window.dispatchEvent(new CustomEvent("parkhaven-viewer-capture-request", {detail: {
    requestId: captureRequestId, projectId: activeProjectId, runId: activeRunId,
  }}));
});

window.addEventListener("parkhaven-viewer-capture-result", async event => {
  const result = event.detail;
  if (!captureRequestId || result?.requestId !== captureRequestId) return;
  const requestId = captureRequestId, projectId = activeProjectId, runId = activeRunId;
  if (result.error) {
    captureRequestId = null;
    capturePending = false;
    document.getElementById("capture-status").textContent = result.error;
    updateActionState();
    return;
  }
  document.getElementById("capture-status").textContent = "Modelbeelden valideren en aan de run koppelen...";
  try {
    const response = await fetch(`/api/projects/${projectId}/runs/${runId}/view-evidence`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({
        scene_sha256: activeRun.scene_sha256,
        geometry_summary_sha256: activeRun.geometry_summary.sha256,
        site_context_sha256: result.siteContextSha256,
        views: result.views,
      }),
    });
    const manifest = await response.json();
    if (requestId !== captureRequestId || projectId !== activeProjectId || runId !== activeRunId) return;
    if (!response.ok) throw new Error(manifest.detail || "Modelbeelden konden niet worden opgeslagen.");
    document.getElementById("capture-status").textContent = `Vier modelbeelden opgeslagen voor run ${manifest.run_id}.`;
    activeRun.view_evidence_available = true;
    document.querySelector("#ai-form button").disabled = false;
    document.getElementById("ai-status").textContent = "Modelbeelden en rekenresultaten zijn gereed voor AI-advies.";
  } catch (error) {
    if (requestId === captureRequestId) document.getElementById("capture-status").textContent = error.message;
  } finally {
    if (requestId === captureRequestId) {
      captureRequestId = null;
      capturePending = false;
      updateActionState();
    }
  }
});

function renderPreview(preview) {
  const labels = {prepared: "Preview voorbereid", launch_requested: "Rhino wordt gestart voor preview",
    runner_started: "Rhino-plug-in gestart", preparing_model: "Previewgeometrie voorbereiden",
    completed: "Plaatsingspreview gereed", failed: "Plaatsingspreview mislukt", cancelled: "Plaatsingspreview geannuleerd"};
  activePreview = preview;
  activePreviewId = preview?.run_id || null;
  document.getElementById("preview-status").textContent = preview
    ? (preview.error || (preview.progress_detail ? `${labels[preview.status]} · ${preview.progress_detail}` : labels[preview.status] || preview.status))
    : "Maak na het opslaan een preview zonder Grasshopper-berekening.";
  updateActionState();
  if (viewerMode === "preview") showViewerMode("preview");
}

async function pollPreview() {
  if (!activeProjectId || !activePreviewId) return;
  const projectId = activeProjectId, previewId = activePreviewId;
  try {
    const response = await fetch(`/api/projects/${projectId}/placement-previews/${previewId}`, {cache: "no-store"});
    if (!response.ok) throw new Error("Previewstatus tijdelijk niet beschikbaar.");
    const preview = await response.json();
    if (projectId !== activeProjectId || previewId !== activePreviewId) return;
    renderPreview(preview);
    if (!["completed", "failed", "cancelled"].includes(preview.status)) schedulePreviewPoll();
  } catch (error) {
    if (projectId === activeProjectId && previewId === activePreviewId) {
      document.getElementById("preview-status").textContent = error.message;
      schedulePreviewPoll();
    }
  }
}

function schedulePreviewPoll() {
  clearTimeout(previewPollTimer);
  previewPollTimer = setTimeout(pollPreview, 1500);
}

async function pollRun() {
  if (!activeProjectId || !activeRunId) return;
  const projectId = activeProjectId, runId = activeRunId;
  try {
    const response = await fetch(`/api/projects/${projectId}/runs/${runId}`, {cache: "no-store"});
    if (!response.ok) throw new Error("Analysestatus tijdelijk niet beschikbaar.");
    const run = await response.json();
    if (projectId !== activeProjectId || runId !== activeRunId) return;
    renderRun(run);
    if (!["completed", "failed", "cancelled"].includes(run.status)) schedulePoll();
  } catch (error) {
    if (projectId === activeProjectId && runId === activeRunId) {
      document.getElementById("analysis-status").textContent = error.message;
      schedulePoll();
    }
  }
}

function schedulePoll() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(pollRun, 1500);
}

document.getElementById("ai-form").addEventListener("submit", async event => {
  event.preventDefault();
  const status = document.getElementById("ai-status");
  status.textContent = "AI-advies aanvragen...";
  const response = await fetch(`/api/projects/${activeProjectId}/runs/${activeRunId}/ai-review`, {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({
      endpoint: document.getElementById("ai-endpoint").value,
      api_key: document.getElementById("ai-key").value,
      model: document.getElementById("ai-model").value,
      design_goal: document.getElementById("design-goal").value,
    }),
  });
  const result = await response.json();
  status.textContent = response.ok ? result.samenvatting : result.detail;
  document.getElementById("ai-key").value = "";
});

async function loadProjects() {
  refreshButton.disabled = true;
  try {
    const response = await fetch("/api/projects", {cache: "no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderProjects(await response.json());
    document.getElementById("connection").textContent = "LOKAAL VERBONDEN";
  } catch (error) {
    projectList.textContent = "Projecten konden niet worden geladen.";
    document.getElementById("connection").textContent = "APP OFFLINE";
  } finally {
    refreshButton.disabled = false;
  }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (pickerRequestId || createProjectButton.disabled) return;
  const data = new FormData(form);
  formStatus.textContent = "Bronbestand controleren en veilige werkkopie maken...";
  createProjectButton.disabled = true;
  browseDesign.disabled = true;
  try {
    const response = await fetch("/api/projects", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        name: data.get("name") || null,
        design_path: data.get("design_path"),
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Importeren mislukt.");
    formStatus.textContent = `Project '${result.name}' is veilig aangemaakt.`;
    form.reset();
    await loadProjects();
  } catch (error) {
    formStatus.textContent = error.message;
  } finally {
    createProjectButton.disabled = false;
    browseDesign.disabled = false;
  }
});

refreshButton.addEventListener("click", loadProjects);
loadProjects();
