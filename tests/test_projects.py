import hashlib
import json
from pathlib import Path

import pytest

from app.projects import ProjectError, create_project, list_projects, load_project


def make_design(path: Path, contents: bytes = b"Rhino test model") -> Path:
    path.write_bytes(contents)
    return path


def test_create_project_preserves_source_and_creates_verified_working_copy(tmp_path):
    source = make_design(tmp_path / "variant A.3dm")
    original = source.read_bytes()
    projects_root = tmp_path / "projects"

    manifest = create_project(projects_root, source, "Variant A")
    project_dir = projects_root / manifest["project_id"]

    assert source.read_bytes() == original
    assert (project_dir / "source" / "original-design.3dm").read_bytes() == original
    assert (project_dir / "working" / "parkhaven-design.3dm").read_bytes() == original
    assert manifest["source"]["sha256"] == hashlib.sha256(original).hexdigest()
    assert manifest["status"] == "imported"
    assert json.loads((project_dir / "placement.json").read_text(encoding="utf-8"))["approved"] is False
    assert json.loads((project_dir / "repairs.json").read_text(encoding="utf-8"))["status"] == "not_inspected"


@pytest.mark.parametrize("filename", ["model.obj", "model.3dm.txt", "model"])
def test_rejects_non_rhino_files_without_creating_workspace(tmp_path, filename):
    source = make_design(tmp_path / filename)
    projects_root = tmp_path / "projects"
    with pytest.raises(ProjectError, match="3dm"):
        create_project(projects_root, source)
    assert not projects_root.exists()


def test_rejects_missing_and_empty_sources(tmp_path):
    with pytest.raises(ProjectError, match="bestaat niet"):
        create_project(tmp_path / "projects", tmp_path / "missing.3dm")
    empty = make_design(tmp_path / "empty.3dm", b"")
    with pytest.raises(ProjectError, match="leeg"):
        create_project(tmp_path / "projects", empty)


def test_list_and_load_projects(tmp_path):
    root = tmp_path / "projects"
    first = create_project(root, make_design(tmp_path / "first.3dm"), "Eerste")
    second = create_project(root, make_design(tmp_path / "second.3dm"), "Tweede")
    assert {project["project_id"] for project in list_projects(root)} == {
        first["project_id"], second["project_id"]
    }
    assert load_project(root, first["project_id"])["name"] == "Eerste"


def test_project_id_cannot_escape_workspace(tmp_path):
    with pytest.raises(ProjectError, match="Ongeldig project-ID"):
        load_project(tmp_path, "../outside")


def test_corrupt_manifest_is_not_listed(tmp_path):
    root = tmp_path / "projects"
    bad = root / "not-a-project"
    bad.mkdir(parents=True)
    (bad / "project.json").write_text("{", encoding="utf-8")
    assert list_projects(root) == []
