import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.diagnostics import MAX_RUNS, developer_status
from app.projects import _write_json, create_project, update_placement
from app.workflow import prepare_run, load_run


def make_run(tmp_path):
    root = tmp_path / "projects"
    source = tmp_path / "design.3dm"
    source.write_bytes(b"model fixture")
    project = create_project(root, source, "Diagnostische test")
    project_id = project["project_id"]
    update_placement(root, project_id, x=0, y=0, z=0, rotation_z_degrees=0, approved=True)
    analyzer = tmp_path / "analyzer"
    analyzer.mkdir()
    (analyzer / "ParkHaven_MVP.3dm").write_bytes(b"context fixture")
    (analyzer / "ParkHaven_MVP.ghx").write_bytes(b"definition fixture")
    (analyzer / "weather").mkdir()
    (analyzer / "weather" / "NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw").write_text("weather")
    job = prepare_run(root, project_id, analyzer, main.RHINO_RUNNER)
    return root, job, Path(job["data_dir"]).parent / "job.json"


def test_developer_status_shows_stage_pid_and_redacted_diagnostics(tmp_path, monkeypatch):
    root, job, path = make_run(tmp_path)
    token = "a" * 64
    job.update(status="failed", error="Mesh is open. Authorization: Bearer secret-value; api_key=other-secret",
               warnings=[f"Session {token}", "Gesloten volume ontbreekt."],
               progress_detail=f"Object 23: token={token}", progress_step="classify_design",
               phase_started_at=job["created_at"], step_seconds={"classify_design": 0.125, "invalid": "private"},
               api_key="must-never-appear", traceback="unfiltered-private-trace", results={"internal": "private"})
    _write_json(path, job)
    _write_json(path.parent / "launch.json", {"rhino_process_id": 1234})
    monkeypatch.setattr(main, "PROJECTS_ROOT", root)
    monkeypatch.setattr(main.app.state, "desktop_session", {"token": token, "authority": "testserver", "origin": "http://testserver"})
    with TestClient(main.app) as client:
        response = client.get("/api/developer/status", headers={"X-ParkHaven-Session": token})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["process_id"] > 0 and payload["uptime_seconds"] >= 0
    run = payload["runs"][0]
    assert run["status"] == "failed" and run["rhino_process_id"] == 1234
    assert "Mesh is open" in run["error"] and "[redacted]" in run["error"]
    assert run["warnings"][1] == "Gesloten volume ontbreekt."
    assert run["progress_detail"] == "Object 23: token=[redacted]"
    assert run["step_seconds"] == {"classify_design": 0.125}
    assert run["phase_started_at"] == job["created_at"]
    for secret in (token, "secret-value", "other-secret", "must-never-appear", "unfiltered-private-trace", "private"):
        assert secret not in response.text
    assert "definition" not in run and "working_model" not in run and "results" not in run


def test_developer_status_updates_from_run_files_without_touching_them(tmp_path):
    root, job, path = make_run(tmp_path)
    for status in ("launch_requested", "preparing_model", "solving", "completed"):
        job["status"] = status
        _write_json(path, job)
        before = path.read_bytes()
        assert developer_status(root)["runs"][0]["status"] == status
        assert path.read_bytes() == before


def test_developer_status_handles_missing_and_corrupt_workspaces(tmp_path):
    assert developer_status(tmp_path / "missing")["runs"] == []
    root, _, path = make_run(tmp_path)
    path.write_text("{broken", encoding="utf-8")
    result = developer_status(root)
    assert result["runs"] == [] and result["warnings"]


def test_diagnostics_are_bounded_and_skip_non_string_warnings(tmp_path):
    root, job, path = make_run(tmp_path)
    job.update(error="E" * 10000, warnings=["W" * 10000] * 30 + [{"api_key": "hidden"}])
    _write_json(path, job)
    result = developer_status(root)
    assert result["limit"] == MAX_RUNS
    assert len(result["runs"][0]["error"]) == 4000
    assert len(result["runs"][0]["warnings"]) == 10
    assert all(len(warning) == 4000 for warning in result["runs"][0]["warnings"])


def test_job_poll_retries_transient_windows_publication_lock(tmp_path, monkeypatch):
    root, job, path = make_run(tmp_path)
    read_text = Path.read_text
    denied = 0

    def locked_read(self, *args, **kwargs):
        nonlocal denied
        if self == path and denied < 2:
            denied += 1
            raise PermissionError("Windows sharing violation")
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", locked_read)
    assert load_run(root, job["project_id"], job["run_id"])["status"] == "prepared"
    assert denied == 2
