"""Local API and initial UI for the ParkHaven desktop application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai import AiError, load_model_evidence, request_review
from .diagnostics import developer_status
from .projects import (
    ProjectError,
    create_project,
    list_projects,
    load_project,
    read_project_file,
    update_placement,
)
from .reports import build_report
from .session import DesktopSessionMiddleware
from .site_context import DEFAULT_SITE_CONTEXT_ROOT, SiteContextError, load_site_context, public_site_context
from .view_evidence import save_view_evidence
from .workflow import (
    cancel_run,
    launch_run,
    list_previews,
    list_runs,
    load_run,
    prepare_preview,
    prepare_run,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROJECTS_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ParkHaven" / "projects"
PROJECTS_ROOT = Path(os.environ.get("PARKHAVEN_PROJECTS_DIR", DEFAULT_PROJECTS_ROOT))
PACKAGED_ANALYZER_ROOT = ROOT / "analyzer"
DEVELOPMENT_ANALYZER_ROOT = ROOT.parent / "ParkHaven_Analyzer_App_v0.2"
ANALYZER_ROOT = Path(os.environ.get(
    "PARKHAVEN_ANALYZER_ROOT",
    PACKAGED_ANALYZER_ROOT if PACKAGED_ANALYZER_ROOT.is_dir() else DEVELOPMENT_ANALYZER_ROOT,
))
RHINO_EXE = Path(os.environ.get("PARKHAVEN_RHINO_EXE", r"C:\Program Files\Rhino 8\System\Rhino.exe"))
RHINO_RUNNER = ROOT / "app" / "rhino" / "run_analysis.py"
VIEWER_ASSETS = ANALYZER_ROOT / "app" / "static" / "vendor" / "three"
SITE_CONTEXT_ROOT = DEFAULT_SITE_CONTEXT_ROOT

app = FastAPI(title="ParkHaven App", version="0.1.0", docs_url=None, redoc_url=None)
app.state.desktop_session = None
app.add_middleware(DesktopSessionMiddleware, session=lambda: app.state.desktop_session)


class ProjectCreate(BaseModel):
    design_path: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)


class PlacementUpdate(BaseModel):
    x: float
    y: float
    z: float = 0
    rotation_z_degrees: float
    approved: bool = False
    model_units: Literal["file", "meters", "millimeters", "centimeters"] | None = None


class AnalysisStart(BaseModel):
    launch_rhino: bool = True


class AiReviewRequest(BaseModel):
    endpoint: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    design_goal: str = Field(default="", max_length=4000)


class ViewCapture(BaseModel):
    id: Literal["top", "overview", "facade-side", "park-side"]
    image_data_url: str = Field(min_length=32, max_length=7_000_000)
    width: int
    height: int
    projection: str
    fov_degrees: float
    camera_position: list[float] = Field(min_length=3, max_length=3)
    camera_target: list[float] = Field(min_length=3, max_length=3)
    camera_up: list[float] = Field(min_length=3, max_length=3)
    visible_layers: list[str] = Field(max_length=8)


class ViewEvidenceRequest(BaseModel):
    scene_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    geometry_summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    site_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    render_style: Literal["volume-colors-v1"]
    views: list[ViewCapture] = Field(min_length=4, max_length=4)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/site-context")
def site_context_manifest():
    try:
        return JSONResponse(public_site_context(SITE_CONTEXT_ROOT), headers={"Cache-Control": "no-store"})
    except SiteContextError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/site-context/aerial.jpg")
def site_context_aerial():
    try:
        context = load_site_context(SITE_CONTEXT_ROOT)
    except SiteContextError as exc:
        raise HTTPException(503, str(exc)) from exc
    return FileResponse(context["image_path"], media_type="image/jpeg", headers={
        "Cache-Control": "no-store", "ETag": f'"{context["image_sha256"]}"',
    })


@app.get("/api/developer/status")
def developer_status_show():
    session = app.state.desktop_session
    return JSONResponse(developer_status(PROJECTS_ROOT, session["token"] if session else ""),
                        headers={"Cache-Control": "no-store"})


@app.get("/api/projects")
def projects_index():
    return JSONResponse(list_projects(PROJECTS_ROOT), headers={"Cache-Control": "no-store"})


@app.post("/api/projects", status_code=201)
def projects_create(request: ProjectCreate):
    try:
        project = create_project(PROJECTS_ROOT, Path(request.design_path), request.name)
    except ProjectError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, "Projectmap kon niet worden aangemaakt.") from exc
    return JSONResponse(project, status_code=201, headers={"Cache-Control": "no-store"})


@app.get("/api/projects/{project_id}")
def projects_show(project_id: str):
    try:
        project = load_project(PROJECTS_ROOT, project_id)
        project["placement"] = read_project_file(PROJECTS_ROOT, project_id, "placement.json")
        project["runs"] = list_runs(PROJECTS_ROOT, project_id)
        previews = list_previews(PROJECTS_ROOT, project_id)
        project["placement_preview"] = previews[0] if previews else None
    except ProjectError as exc:
        raise HTTPException(404, str(exc)) from exc
    return JSONResponse(project, headers={"Cache-Control": "no-store"})


@app.put("/api/projects/{project_id}/placement")
def placement_update(project_id: str, request: PlacementUpdate):
    try:
        placement = update_placement(
            PROJECTS_ROOT,
            project_id,
            x=request.x,
            y=request.y,
            z=request.z,
            rotation_z_degrees=request.rotation_z_degrees,
            approved=request.approved,
            model_units=request.model_units,
        )
    except ProjectError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(placement, headers={"Cache-Control": "no-store"})


@app.post("/api/projects/{project_id}/analysis", status_code=202)
def analysis_start(project_id: str, request: AnalysisStart):
    try:
        job = prepare_run(PROJECTS_ROOT, project_id, ANALYZER_ROOT, RHINO_RUNNER)
        if request.launch_rhino:
            job = launch_run(PROJECTS_ROOT, project_id, job["run_id"], RHINO_EXE)
    except ProjectError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(job, status_code=202, headers={"Cache-Control": "no-store"})


@app.post("/api/projects/{project_id}/placement-preview", status_code=202)
def placement_preview_start(project_id: str, request: AnalysisStart):
    try:
        job = prepare_preview(PROJECTS_ROOT, project_id, ANALYZER_ROOT)
        if request.launch_rhino:
            job = launch_run(PROJECTS_ROOT, project_id, job["run_id"], RHINO_EXE)
    except ProjectError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(job, status_code=202, headers={"Cache-Control": "no-store"})


@app.get("/api/projects/{project_id}/placement-previews/{preview_id}")
def placement_preview_show(project_id: str, preview_id: str):
    try:
        job = load_run(PROJECTS_ROOT, project_id, preview_id)
        if job.get("job_type") != "placement_preview":
            raise ProjectError("Plaatsingspreview niet gevonden.")
    except ProjectError as exc:
        raise HTTPException(404, str(exc)) from exc
    return JSONResponse(job, headers={"Cache-Control": "no-store"})


@app.post("/api/projects/{project_id}/placement-previews/{preview_id}/cancel")
def placement_preview_cancel(project_id: str, preview_id: str):
    try:
        job = load_run(PROJECTS_ROOT, project_id, preview_id)
        if job.get("job_type") != "placement_preview":
            raise ProjectError("Plaatsingspreview niet gevonden.")
        job = cancel_run(PROJECTS_ROOT, project_id, preview_id)
    except ProjectError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(job, headers={"Cache-Control": "no-store"})


@app.get("/api/projects/{project_id}/placement-previews/{preview_id}/scene.json")
def placement_preview_scene(project_id: str, preview_id: str):
    try:
        job = load_run(PROJECTS_ROOT, project_id, preview_id)
    except ProjectError as exc:
        raise HTTPException(404, str(exc)) from exc
    if job.get("job_type") != "placement_preview":
        raise HTTPException(404, "Plaatsingspreview niet gevonden.")
    if job.get("status") != "completed":
        raise HTTPException(409, "3D-preview is pas beschikbaar na voltooide voorbereiding.")
    path = Path(job["data_dir"]) / "scene.json"
    if not path.is_file():
        raise HTTPException(404, "3D-preview is niet beschikbaar.")
    return FileResponse(path, media_type="application/json", headers={"Cache-Control": "no-store"})


@app.get("/api/projects/{project_id}/runs/{run_id}")
def analysis_show(project_id: str, run_id: str):
    try:
        job = load_run(PROJECTS_ROOT, project_id, run_id)
        if job.get("job_type") != "analysis":
            raise ProjectError("Analyse niet gevonden.")
    except ProjectError as exc:
        raise HTTPException(404, str(exc)) from exc
    return JSONResponse(job, headers={"Cache-Control": "no-store"})


@app.post("/api/projects/{project_id}/runs/{run_id}/cancel")
def analysis_cancel(project_id: str, run_id: str):
    try:
        job = load_run(PROJECTS_ROOT, project_id, run_id)
        if job.get("job_type") != "analysis":
            raise ProjectError("Analyse niet gevonden.")
        job = cancel_run(PROJECTS_ROOT, project_id, run_id)
    except ProjectError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(job, headers={"Cache-Control": "no-store"})


@app.get("/api/projects/{project_id}/runs/{run_id}/scene.json")
def analysis_scene(project_id: str, run_id: str):
    try:
        job = load_run(PROJECTS_ROOT, project_id, run_id)
    except ProjectError as exc:
        raise HTTPException(404, str(exc)) from exc
    if job.get("job_type") != "analysis":
        raise HTTPException(404, "Analyse niet gevonden.")
    if job.get("status") != "completed":
        raise HTTPException(409, "3D-resultaat is pas beschikbaar na een voltooide analyse.")
    path = Path(job["data_dir"]) / "scene.json"
    if not path.is_file():
        raise HTTPException(404, "3D-resultaat is nog niet beschikbaar.")
    return FileResponse(path, media_type="application/json", headers={"Cache-Control": "no-store"})


@app.post("/api/projects/{project_id}/runs/{run_id}/view-evidence", status_code=201)
def view_evidence_create(project_id: str, run_id: str, request: ViewEvidenceRequest):
    try:
        job = load_run(PROJECTS_ROOT, project_id, run_id)
        manifest = save_view_evidence(job, request.model_dump(), SITE_CONTEXT_ROOT)
    except ProjectError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(manifest, status_code=201, headers={"Cache-Control": "no-store"})


@app.post("/api/projects/{project_id}/runs/{run_id}/ai-review")
def ai_review(project_id: str, run_id: str, request: AiReviewRequest):
    try:
        job = load_run(PROJECTS_ROOT, project_id, run_id)
        if job.get("job_type") != "analysis" or job.get("status") != "completed" or not isinstance(job.get("results"), dict):
            raise ProjectError("AI-advies is pas beschikbaar na een geldige analyse.")
        evidence = load_model_evidence(job)
        review = request_review(
            endpoint=request.endpoint,
            api_key=request.api_key,
            model=request.model,
            evidence=evidence,
            design_goal=request.design_goal,
        )
        review_path = Path(job["data_dir"]).parent / "ai-advice.json"
        review_path.write_text(__import__("json").dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ProjectError, AiError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(review, headers={"Cache-Control": "no-store"})


@app.get("/projects/{project_id}/runs/{run_id}/report", response_class=HTMLResponse)
def report(project_id: str, run_id: str):
    try:
        project = load_project(PROJECTS_ROOT, project_id)
        job = load_run(PROJECTS_ROOT, project_id, run_id)
        if job.get("job_type") != "analysis":
            raise ProjectError("Analyse niet gevonden.")
        html = build_report(project, job)
    except ProjectError as exc:
        raise HTTPException(404, str(exc)) from exc
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


app.mount("/viewer-assets", StaticFiles(directory=VIEWER_ASSETS, check_dir=False), name="viewer-assets")
app.mount("/", StaticFiles(directory=ROOT / "app" / "static", html=True), name="desktop-ui")
