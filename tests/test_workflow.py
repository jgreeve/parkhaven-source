import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from app import workflow
from app.projects import ProjectError, _sha256, create_project, update_placement


@pytest.fixture
def run_setup(tmp_path, monkeypatch):
    source = tmp_path / "ontwerp met spaties.3dm"
    source.write_bytes(b"test model")
    root = tmp_path / "projects"
    project = create_project(root, source)
    project_id = project["project_id"]
    update_placement(root, project_id, x=12, y=-3, z=0, rotation_z_degrees=90, approved=True)
    analyzer = tmp_path / "analyzer"
    analyzer.mkdir()
    (analyzer / "ParkHaven_MVP.3dm").write_bytes(b"context")
    (analyzer / "ParkHaven_MVP.ghx").write_bytes(b"GHX")
    runner = Path(workflow.__file__).parent / "rhino/run_analysis.py"
    executable = tmp_path / "Rhino.exe"
    executable.touch()
    monkeypatch.setattr(workflow, "_registered_plugin", lambda: tmp_path / "test.rhp")
    monkeypatch.setattr(workflow.threading, "Thread", Mock())
    monkeypatch.setattr(workflow, "_processes", {})
    monkeypatch.setattr(workflow, "_run_locations", {})
    monkeypatch.setattr(workflow, "_shutting_down", False)

    def prepare():
        return workflow.prepare_run(root, project_id, analyzer, runner)

    return root, project_id, executable, prepare, source


def test_run_snapshots_and_provenance(run_setup):
    root, project_id, _, prepare, source = run_setup
    first, second = prepare(), prepare()
    first_model = Path(first["working_model"])
    assert first_model.parent.name == first["run_id"]
    assert first_model != Path(second["working_model"])
    assert first["input_sha256"] == first["source_sha256"] == _sha256(source)
    assert first["definition_sha256"] == _sha256(Path(first["definition"]))
    assert first["placement"]["rotation_z_degrees"] == 90
    first_model.write_bytes(b"run-local edit")
    assert Path(second["working_model"]).read_bytes() == source.read_bytes()
    assert (root / project_id / "working/parkhaven-design.3dm").read_bytes() == source.read_bytes()


def test_unit_correction_is_snapshotted_per_run_without_scaling_source(run_setup):
    root, project_id, _, prepare, source = run_setup
    original = source.read_bytes()
    old = prepare()
    update_placement(root, project_id, x=12, y=-3, z=0, rotation_z_degrees=90,
                     approved=True, model_units="meters")
    corrected = prepare()
    assert old["placement"]["model_units"] == "file"
    assert corrected["placement"]["model_units"] == "meters"
    assert corrected["placement"]["translation_m"] == {"x": 12, "y": -3, "z": 0}
    assert workflow.load_run(root, project_id, old["run_id"])["placement"]["model_units"] == "file"
    for path in (source, Path(corrected["working_model"]), root / project_id / "working/parkhaven-design.3dm"):
        assert path.read_bytes() == original


def test_preview_snapshots_unapproved_placement_without_analysis_assets(run_setup):
    root, project_id, _, _, source = run_setup
    update_placement(root, project_id, x=4, y=5, z=6, rotation_z_degrees=30,
                     approved=False, model_units="meters")
    analyzer = source.parent / "analyzer"
    (analyzer / "ParkHaven_MVP.ghx").unlink()
    original = source.read_bytes()

    preview = workflow.prepare_preview(root, project_id, analyzer)

    assert preview["job_type"] == "placement_preview"
    assert preview["placement"]["approved"] is False
    assert preview["placement"]["translation_m"] == {"x": 4, "y": 5, "z": 6}
    assert "definition" not in preview and "definition_sha256" not in preview
    assert Path(preview["working_model"]).read_bytes() == original
    assert (root / project_id / "working/parkhaven-design.3dm").read_bytes() == original
    assert workflow.list_runs(root, project_id) == []
    assert [item["run_id"] for item in workflow.list_previews(root, project_id)] == [preview["run_id"]]


def test_launch_does_not_overwrite_fast_plugin_and_uses_direct_process(run_setup, monkeypatch):
    root, project_id, exe, prepare, _ = run_setup
    job = prepare()
    process = Mock(pid=1234)

    def start(command, env):
        assert command == [str(exe), "/netcore", "/newinstance", "/nosplash", job["working_model"]]
        path = Path(env["PARKHAVEN_JOB_FILE"])
        persisted = json.loads(path.read_text(encoding="utf-8"))
        assert persisted["status"] == "launch_requested"
        persisted["status"] = "completed"
        path.write_text(json.dumps(persisted), encoding="utf-8")
        return process

    monkeypatch.setattr(workflow.subprocess, "Popen", start)
    launched = workflow.launch_run(root, project_id, job["run_id"], exe)
    assert launched["status"] == "completed"
    assert launched["rhino_process_id"] == 1234


def test_relaunch_and_concurrent_project_launch_are_rejected(run_setup, monkeypatch):
    root, project_id, exe, prepare, _ = run_setup
    job, other = prepare(), prepare()
    start = Mock(return_value=Mock(pid=1234))
    monkeypatch.setattr(workflow.subprocess, "Popen", start)
    workflow.launch_run(root, project_id, job["run_id"], exe)
    with pytest.raises(ProjectError, match="al gestart"):
        workflow.launch_run(root, project_id, job["run_id"], exe)
    with pytest.raises(ProjectError, match="al een analyse"):
        workflow.launch_run(root, project_id, other["run_id"], exe)
    assert start.call_count == 1


def test_process_creation_failure_is_persisted(run_setup, monkeypatch):
    root, project_id, exe, prepare, _ = run_setup
    job = prepare()
    monkeypatch.setattr(workflow.subprocess, "Popen", Mock(side_effect=OSError("launch denied")))
    with pytest.raises(ProjectError, match="launch denied"):
        workflow.launch_run(root, project_id, job["run_id"], exe)
    assert workflow.load_run(root, project_id, job["run_id"])["status"] == "failed"


@pytest.mark.parametrize("mode", ["crash", "startup_timeout", "solve_timeout"])
def test_monitor_reports_crashes_and_timeouts(run_setup, monkeypatch, mode):
    root, project_id, exe, prepare, _ = run_setup
    job = prepare()
    process = Mock(pid=1234)
    process.poll.return_value = 1 if mode == "crash" else None
    monkeypatch.setattr(workflow.subprocess, "Popen", Mock(return_value=process))
    workflow.launch_run(root, project_id, job["run_id"], exe)
    if mode == "solve_timeout":
        job["status"] = "solving"
        workflow._finish_run(root, project_id, job, "solving", None)
    monkeypatch.setattr(workflow.time, "sleep", lambda _: None)
    monkeypatch.setattr(workflow.time, "monotonic", lambda: 1)
    monkeypatch.setattr(workflow, "STARTUP_TIMEOUT_SECONDS", -1)
    monkeypatch.setattr(workflow, "SOLVE_TIMEOUT_SECONDS", -1)
    workflow._monitor_run(root, project_id, job["run_id"], process)
    result = workflow.load_run(root, project_id, job["run_id"])
    assert result["status"] == "failed"
    expected = {"crash": "afgesloten", "startup_timeout": "120 seconden", "solve_timeout": "10 minuten"}
    assert expected[mode] in result["error"]
    assert process.terminate.call_count == (0 if mode == "crash" else 1)


def test_cancel_stops_only_owned_run_and_preserves_source(run_setup, monkeypatch):
    root, project_id, exe, prepare, source = run_setup
    job = prepare()
    digest = _sha256(source)
    process = Mock(pid=1234)
    process.poll.return_value = None
    monkeypatch.setattr(workflow.subprocess, "Popen", Mock(return_value=process))
    workflow.launch_run(root, project_id, job["run_id"], exe)
    cancelled = workflow.cancel_run(root, project_id, job["run_id"])
    assert cancelled["status"] == "cancelled"
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=10)
    assert _sha256(source) == digest
    with pytest.raises(ProjectError, match="afgerond"):
        workflow.cancel_run(root, project_id, job["run_id"])


def test_cancel_refuses_process_not_owned_after_restart(run_setup):
    root, project_id, _, prepare, _ = run_setup
    job = prepare()
    workflow._finish_run(root, project_id, job, "solving", None)
    with pytest.raises(ProjectError, match="niet van dit app-proces"):
        workflow.cancel_run(root, project_id, job["run_id"])


def test_completed_job_is_not_rewritten_when_rhino_exits(run_setup, monkeypatch):
    root, project_id, _, prepare, _ = run_setup
    job = prepare()
    workflow._finish_run(root, project_id, job, "completed", None)
    monkeypatch.setattr(workflow.time, "sleep", lambda _: None)
    process = Mock()
    workflow._monitor_run(root, project_id, job["run_id"], process)
    assert workflow.load_run(root, project_id, job["run_id"])["status"] == "completed"
    process.terminate.assert_not_called()


def test_cancel_does_not_erase_completion_published_during_shutdown(run_setup, monkeypatch):
    root, project_id, exe, prepare, _ = run_setup
    job = prepare()
    process = Mock(pid=1234)
    process.poll.return_value = None
    process.terminate.side_effect = lambda: workflow._finish_run(root, project_id, job, "completed", None)
    monkeypatch.setattr(workflow.subprocess, "Popen", Mock(return_value=process))
    workflow.launch_run(root, project_id, job["run_id"], exe)
    assert workflow.cancel_run(root, project_id, job["run_id"])["status"] == "completed"


@pytest.mark.parametrize("status,expected", [("solving", "cancelled"), ("completed", "completed")])
def test_desktop_shutdown_stops_owned_rhino_and_preserves_finished_evidence(run_setup, monkeypatch, status, expected):
    root, project_id, exe, prepare, source = run_setup
    job = prepare()
    digest = _sha256(source)
    process = Mock(pid=1234)
    process.poll.return_value = None
    monkeypatch.setattr(workflow.subprocess, "Popen", Mock(return_value=process))
    workflow.launch_run(root, project_id, job["run_id"], exe)
    workflow._finish_run(root, project_id, job, status, None)
    workflow.shutdown_owned_runs()
    process.terminate.assert_called_once()
    assert workflow.load_run(root, project_id, job["run_id"])["status"] == expected
    assert not workflow._processes and not workflow._run_locations
    assert _sha256(source) == digest
    with pytest.raises(ProjectError, match="afgesloten"):
        workflow.launch_run(root, project_id, prepare()["run_id"], exe)
