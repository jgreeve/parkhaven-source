"""Analysis and placement-preview preparation with Rhino process integration."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .projects import ProjectError, _sha256, _write_json, load_project, project_directory, read_project_file
from .site_context import DEFAULT_SITE_CONTEXT_ROOT


RUN_SCHEMA_VERSION = 1
PLUGIN_ID = "7ff947f5-d80c-4be6-bc9b-88f77bdfe605"
ACTIVE_STATES = {"launch_requested", "runner_started", "preparing_model", "solving"}
TERMINAL_STATES = {"completed", "failed", "cancelled"}
STARTUP_TIMEOUT_SECONDS = 120
SOLVE_TIMEOUT_SECONDS = 600
_launch_lock = threading.RLock()
_processes: dict[str, subprocess.Popen] = {}
_run_locations: dict[str, tuple[Path, str]] = {}
_shutting_down = False


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _analyzer_assets(analyzer_root: Path) -> tuple[Path, Path]:
    root = analyzer_root.expanduser().resolve()
    model = root / "ParkHaven_MVP.3dm"
    definition = root / "ParkHaven_MVP.ghx"
    if not model.is_file() or not definition.is_file():
        raise ProjectError("De geverifieerde ParkHaven-analysebestanden ontbreken.")
    return model, definition


def _context_asset(analyzer_root: Path) -> Path:
    model = analyzer_root.expanduser().resolve() / "ParkHaven_MVP.3dm"
    if not model.is_file():
        raise ProjectError("Het geverifieerde ParkHaven-referentiemodel ontbreekt.")
    return model


def prepare_run(projects_root: Path, project_id: str, analyzer_root: Path, runner_path: Path) -> dict[str, Any]:
    project = load_project(projects_root, project_id)
    placement = read_project_file(projects_root, project_id, "placement.json")
    if placement.get("approved") is not True:
        raise ProjectError("Keur eerst de plaatsing goed voordat u analyseert.")

    context_model, definition = _analyzer_assets(analyzer_root)
    directory = project_directory(projects_root, project_id)
    run_id = str(uuid.uuid4())
    run_dir = directory / "runs" / run_id
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True)
    run_definition = run_dir / "ParkHaven_Analysis.ghx"
    shutil.copy2(definition, run_definition)
    # Rhino only ever opens this immutable-input snapshot, not the project copy.
    run_model = run_dir / "design.3dm"
    shutil.copy2(directory / project["working"]["path"], run_model)

    job = {
        "schema_version": RUN_SCHEMA_VERSION,
        "job_type": "analysis",
        "run_id": run_id,
        "project_id": project_id,
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
        "status": "prepared",
        "working_model": str(run_model.resolve()),
        "input_sha256": _sha256(run_model),
        "source_sha256": project["source"]["sha256"],
        "definition_sha256": _sha256(run_definition),
        "context_sha256": _sha256(context_model),
        "application_version": "0.1.0",
        "integration": "rhino-plugin-v1",
        "manual_command": "ParkHavenAnalyze",
        "context_model": str(context_model),
        "definition": str(run_definition),
        "definition_runtime_path": str(run_dir / "ParkHaven_Analysis.gh"),
        "runner_script": str(run_dir / "run_analysis.py"),
        "data_dir": str(data_dir),
        "placement": placement,
        "warnings": [],
        "error": None,
    }
    shutil.copy2(runner_path, run_dir / "run_analysis.py")
    job["targets"] = read_project_file(projects_root, project_id, "targets.json")
    job["repairs"] = read_project_file(projects_root, project_id, "repairs.json")
    _write_json(run_dir / "job.json", job)
    return job


def prepare_preview(projects_root: Path, project_id: str, analyzer_root: Path) -> dict[str, Any]:
    """Snapshot a saved placement for Rhino preparation without running Grasshopper."""
    project = load_project(projects_root, project_id)
    placement = read_project_file(projects_root, project_id, "placement.json")
    context_model = _context_asset(analyzer_root)
    directory = project_directory(projects_root, project_id)
    run_id = str(uuid.uuid4())
    run_dir = directory / "runs" / run_id
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True)
    preview_model = run_dir / "design.3dm"
    shutil.copy2(directory / project["working"]["path"], preview_model)
    job = {
        "schema_version": RUN_SCHEMA_VERSION,
        "job_type": "placement_preview",
        "run_id": run_id,
        "project_id": project_id,
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
        "status": "prepared",
        "working_model": str(preview_model.resolve()),
        "input_sha256": _sha256(preview_model),
        "source_sha256": project["source"]["sha256"],
        "context_sha256": _sha256(context_model),
        "application_version": "0.1.0",
        "integration": "rhino-plugin-v1",
        "manual_command": "ParkHavenAnalyze",
        "context_model": str(context_model),
        "data_dir": str(data_dir),
        "placement": placement,
        "warnings": [],
        "error": None,
    }
    _write_json(run_dir / "job.json", job)
    return job


def _registered_plugin() -> Path:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            rf"Software\McNeel\Rhinoceros\8.0\Plug-ins\{PLUGIN_ID}\PlugIn") as key:
            path = Path(winreg.QueryValueEx(key, "FileName")[0])
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            rf"Software\McNeel\Rhinoceros\8.0\Plug-ins\{PLUGIN_ID}") as key:
            if winreg.QueryValueEx(key, "LoadMode")[0] != 1:
                raise OSError("Plug-in laadt niet bij opstarten.")
        if path.is_file():
            return path
    except (ImportError, OSError):
        pass
    raise ProjectError("Bouw en registreer eerst de ParkHaven Rhino-plug-in; zie docs/RHINO_PLUGIN.md.")


def launch_run(
    projects_root: Path,
    project_id: str,
    run_id: str,
    rhino_executable: Path,
) -> dict[str, Any]:
    with _launch_lock:
        return _launch_run(projects_root, project_id, run_id, rhino_executable)


def _launch_run(projects_root: Path, project_id: str, run_id: str, rhino_executable: Path) -> dict[str, Any]:
    if _shutting_down:
        raise ProjectError("De toepassing wordt afgesloten.")
    job = load_run(projects_root, project_id, run_id)
    if job["status"] != "prepared":
        raise ProjectError("Deze analyse is al gestart. Maak een nieuwe run aan.")
    if any(run["status"] in ACTIVE_STATES for run in _list_jobs(projects_root, project_id)):
        raise ProjectError("Er loopt al een analyse of preview voor dit project.")
    executable = rhino_executable.expanduser().resolve()
    if not executable.is_file():
        raise ProjectError("Rhino 8 is niet gevonden.")
    plugin = _registered_plugin()
    run_dir = project_directory(projects_root, project_id) / "runs" / run_id
    command = [str(executable), "/netcore", "/newinstance", "/nosplash", job["working_model"]]
    environment = {**os.environ, "PARKHAVEN_JOB_FILE": str(run_dir / "job.json")}
    # Publish before CreateProcess: never overwrite an early plug-in status update.
    job.pop("scene_available", None)
    job["status"] = "launch_requested"
    job["updated_at"] = _timestamp()
    job["launch_command"] = command
    job["plugin_path"] = str(plugin)
    _write_json(run_dir / "job.json", job)
    try:
        process = subprocess.Popen(command, env=environment)
    except OSError as exc:
        job["status"] = "failed"
        job["error"] = "Rhino kon niet worden gestart: " + str(exc)
        _write_json(run_dir / "job.json", job)
        raise ProjectError("Rhino kon niet worden gestart: " + str(exc)) from exc
    _processes[run_id] = process
    _run_locations[run_id] = (projects_root, project_id)
    _write_json(run_dir / "launch.json", {"rhino_process_id": process.pid, "started_at": _timestamp()})
    threading.Thread(target=_monitor_run, args=(projects_root, project_id, run_id, process), daemon=True).start()
    return load_run(projects_root, project_id, run_id)


def _monitor_run(projects_root: Path, project_id: str, run_id: str, process: subprocess.Popen) -> None:
    started = time.monotonic()
    while True:
        time.sleep(0.5)
        with _launch_lock:
            try:
                job = load_run(projects_root, project_id, run_id)
            except ProjectError:
                return
            if job["status"] in TERMINAL_STATES:
                return
            error = None
            if process.poll() is not None:
                error = "Rhino is afgesloten voordat de analyse was voltooid. Start een nieuwe run."
            elif job["status"] == "launch_requested" and time.monotonic() - started > STARTUP_TIMEOUT_SECONDS:
                error = "De Rhino-plug-in reageerde niet binnen 120 seconden. Controleer installatie en licentie."
            elif time.monotonic() - started > SOLVE_TIMEOUT_SECONDS:
                error = "De analyse overschreed de maximale rekentijd van 10 minuten."
            if error:
                _stop_process(process)
                # Reload after stopping to retain any last plug-in diagnostics.
                job = load_run(projects_root, project_id, run_id)
                if job["status"] not in TERMINAL_STATES:
                    _finish_run(projects_root, project_id, job, "failed", error)
                return


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=10)


def shutdown_owned_runs() -> None:
    """Called only by the owned desktop backend, never by a browser/test client."""
    global _shutting_down
    with _launch_lock:
        _shutting_down = True
        for run_id, process in list(_processes.items()):
            try:
                _stop_process(process)
                root, project_id = _run_locations[run_id]
                job = load_run(root, project_id, run_id)
                if job["status"] not in TERMINAL_STATES:
                    _finish_run(root, project_id, job, "cancelled", "De desktoptoepassing is afgesloten.")
            except (OSError, subprocess.TimeoutExpired, ProjectError, KeyError):
                __import__("logging").getLogger(__name__).exception("Afsluiten van een eigen Rhino-run is mislukt.")
        _processes.clear()
        _run_locations.clear()


def _finish_run(projects_root: Path, project_id: str, job: dict, status: str, error: str | None) -> None:
    for field in ("results", "scene_available", "rhino_process_id"):
        job.pop(field, None)
    job.update(status=status, error=error, updated_at=_timestamp())
    _write_json(project_directory(projects_root, project_id) / "runs" / job["run_id"] / "job.json", job)


def cancel_run(projects_root: Path, project_id: str, run_id: str) -> dict[str, Any]:
    with _launch_lock:
        job = load_run(projects_root, project_id, run_id)
        if job["status"] in TERMINAL_STATES:
            raise ProjectError("Deze run is al afgerond.")
        process = _processes.get(run_id)
        if job["status"] in ACTIVE_STATES and process is None:
            raise ProjectError("Deze Rhino-sessie is niet van dit app-proces; sluit Rhino handmatig.")
        if process is not None:
            _stop_process(process)
        job = load_run(projects_root, project_id, run_id)
        # A solve may complete between the request and process termination.
        if job["status"] in TERMINAL_STATES:
            return job
        _finish_run(projects_root, project_id, job, "cancelled", None)
        return load_run(projects_root, project_id, run_id)


def _validated_run_id(run_id: str) -> str:
    try:
        parsed = uuid.UUID(run_id)
    except (ValueError, AttributeError) as exc:
        raise ProjectError("Ongeldig analyse-ID.") from exc
    if str(parsed) != run_id.lower():
        raise ProjectError("Ongeldig analyse-ID.")
    return str(parsed)


def load_run(projects_root: Path, project_id: str, run_id: str) -> dict[str, Any]:
    path = project_directory(projects_root, project_id) / "runs" / _validated_run_id(run_id) / "job.json"
    try:
        # Atomic plug-in publication can briefly deny an open on Windows.
        for attempt in range(5):
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
    except FileNotFoundError as exc:
        raise ProjectError("Analyse niet gevonden.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError("Analysestatus kan niet worden gelezen.") from exc
    if not isinstance(job, dict) or job.get("project_id") != project_id or job.get("run_id") != run_id:
        raise ProjectError("Analysestatus is ongeldig.")
    job.setdefault("job_type", "analysis")
    result_path = path.parent / "data" / "latest.json"
    scene_path = path.parent / "data" / "scene.json"
    view_evidence_path = path.parent / "data" / "view-evidence.json"
    if job["job_type"] == "analysis" and result_path.is_file():
        try:
            job["results"] = json.loads(result_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            job["results"] = None
    job["scene_available"] = scene_path.is_file()
    job["view_evidence_available"] = False
    if view_evidence_path.is_file():
        try:
            view_manifest = json.loads(view_evidence_path.read_text(encoding="utf-8"))
            job["view_evidence_available"] = (
                view_manifest.get("site_context_sha256") == _sha256(DEFAULT_SITE_CONTEXT_ROOT / "manifest.json"))
        except (OSError, json.JSONDecodeError):
            pass
    if scene_path.is_file():
        job["scene_sha256"] = _sha256(scene_path)
    launch_path = path.parent / "launch.json"
    if launch_path.is_file():
        try:
            job["rhino_process_id"] = json.loads(launch_path.read_text(encoding="utf-8"))["rhino_process_id"]
        except (OSError, ValueError, KeyError):
            pass
    return job


def list_runs(projects_root: Path, project_id: str) -> list[dict[str, Any]]:
    return [job for job in _list_jobs(projects_root, project_id) if job["job_type"] == "analysis"]


def list_previews(projects_root: Path, project_id: str) -> list[dict[str, Any]]:
    return [job for job in _list_jobs(projects_root, project_id) if job["job_type"] == "placement_preview"]


def _list_jobs(projects_root: Path, project_id: str) -> list[dict[str, Any]]:
    runs_dir = project_directory(projects_root, project_id) / "runs"
    if not runs_dir.exists():
        return []
    runs = []
    for job_path in runs_dir.glob("*/job.json"):
        try:
            runs.append(load_run(projects_root, project_id, job_path.parent.name))
        except ProjectError:
            continue
    return sorted(runs, key=lambda run: run["created_at"], reverse=True)
