"""Versioned, isolated project workspaces for imported Rhino designs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_SCHEMA_VERSION = 1
PLACEMENT_SCHEMA_VERSION = 1
REPAIRS_SCHEMA_VERSION = 1
TARGETS_SCHEMA_VERSION = 1
SITE_ID = "parkhaven"


class ProjectError(ValueError):
    """A project request is invalid or its persisted data cannot be trusted."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def project_directory(projects_root: Path, project_id: str) -> Path:
    """Return a project directory only after validating its UUID boundary."""
    return projects_root.expanduser().resolve() / _validated_project_id(project_id)


def read_project_file(projects_root: Path, project_id: str, filename: str) -> dict[str, Any]:
    if filename not in {"placement.json", "repairs.json", "targets.json"}:
        raise ProjectError("Onbekend projectbestand.")
    path = project_directory(projects_root, project_id) / filename
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProjectError("Projectbestand niet gevonden.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError("Projectbestand kan niet worden gelezen.") from exc
    if not isinstance(payload, dict):
        raise ProjectError("Projectbestand is ongeldig.")
    return payload


def _validated_name(name: str | None, fallback: str) -> str:
    value = (name or fallback).strip()
    if not value or len(value) > 120 or any(ord(character) < 32 for character in value):
        raise ProjectError("Projectnaam moet 1 tot 120 geldige tekens bevatten.")
    return value


def _validated_project_id(project_id: str) -> str:
    try:
        parsed = uuid.UUID(project_id)
    except (ValueError, AttributeError) as exc:
        raise ProjectError("Ongeldig project-ID.") from exc
    if str(parsed) != project_id.lower():
        raise ProjectError("Ongeldig project-ID.")
    return str(parsed)


def create_project(projects_root: Path, design_path: Path, name: str | None = None) -> dict[str, Any]:
    """Create an isolated project while leaving the selected source untouched."""

    source = design_path.expanduser().resolve()
    if not source.is_file():
        raise ProjectError("Het gekozen Rhino-bestand bestaat niet.")
    if source.suffix.lower() != ".3dm":
        raise ProjectError("Kies een Rhino .3dm-bestand.")

    source_size = source.stat().st_size
    if source_size == 0:
        raise ProjectError("Het gekozen Rhino-bestand is leeg.")

    project_name = _validated_name(name, source.stem)
    project_id = str(uuid.uuid4())
    root = projects_root.expanduser().resolve()
    project_dir = root / project_id
    source_dir = project_dir / "source"
    working_dir = project_dir / "working"

    original_hash = _sha256(source)
    try:
        source_dir.mkdir(parents=True, exist_ok=False)
        working_dir.mkdir()
        (project_dir / "runs").mkdir()
        (project_dir / "reports").mkdir()
        (project_dir / "logs").mkdir()

        preserved = source_dir / "original-design.3dm"
        working = working_dir / "parkhaven-design.3dm"
        shutil.copy2(source, preserved)
        shutil.copy2(source, working)

        if _sha256(source) != original_hash:
            raise ProjectError("Het bronbestand veranderde tijdens het importeren; probeer opnieuw.")
        if _sha256(preserved) != original_hash or _sha256(working) != original_hash:
            raise ProjectError("De geimporteerde kopie kon niet worden geverifieerd.")

        created_at = _timestamp()
        placement = {
            "schema_version": PLACEMENT_SCHEMA_VERSION,
            "translation_m": {"x": 0.0, "y": 0.0, "z": 0.0},
            "rotation_z_degrees": 0.0,
            "unit_scale": 1.0,
            "model_units": "file",
            "approved": False,
        }
        repairs = {
            "schema_version": REPAIRS_SCHEMA_VERSION,
            "status": "not_inspected",
            "approved": False,
            "operations": [],
        }
        targets = {
            "schema_version": TARGETS_SCHEMA_VERSION,
            "profile": "parkhaven-draft",
            "approved": False,
            "overrides": {},
        }
        manifest = {
            "schema_version": PROJECT_SCHEMA_VERSION,
            "project_id": project_id,
            "name": project_name,
            "created_at": created_at,
            "updated_at": created_at,
            "status": "imported",
            "site": {"id": SITE_ID, "package_version": None},
            "source": {
                "original_filename": source.name,
                "stored_path": "source/original-design.3dm",
                "sha256": original_hash,
                "size_bytes": source_size,
            },
            "working": {
                "path": "working/parkhaven-design.3dm",
                "derived_from_sha256": original_hash,
            },
            "placement_path": "placement.json",
            "repairs_path": "repairs.json",
            "targets_path": "targets.json",
        }
        _write_json(project_dir / "placement.json", placement)
        _write_json(project_dir / "repairs.json", repairs)
        _write_json(project_dir / "targets.json", targets)
        _write_json(project_dir / "project.json", manifest)
        return manifest
    except Exception:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise


def load_project(projects_root: Path, project_id: str) -> dict[str, Any]:
    validated_id = _validated_project_id(project_id)
    manifest_path = project_directory(projects_root, validated_id) / "project.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProjectError("Project niet gevonden.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError("Projectmanifest kan niet worden gelezen.") from exc
    if not isinstance(manifest, dict) or manifest.get("project_id") != validated_id:
        raise ProjectError("Projectmanifest is ongeldig.")
    if manifest.get("schema_version") != PROJECT_SCHEMA_VERSION:
        raise ProjectError("Projectversie wordt niet ondersteund.")
    return manifest


def update_placement(
    projects_root: Path,
    project_id: str,
    *,
    x: float,
    y: float,
    z: float,
    rotation_z_degrees: float,
    approved: bool,
    model_units: str | None = None,
) -> dict[str, Any]:
    import math

    values = (x, y, z, rotation_z_degrees)
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
        raise ProjectError("Plaatsingswaarden moeten eindige getallen zijn.")
    if any(abs(value) > 5000 for value in (x, y, z)):
        raise ProjectError("Plaatsing valt buiten het toegestane bereik van 5 km.")
    if abs(rotation_z_degrees) > 36000:
        raise ProjectError("Rotatie valt buiten het toegestane bereik.")

    project = load_project(projects_root, project_id)
    directory = project_directory(projects_root, project_id)
    if model_units is None:
        # Older clients changing placement must not discard an existing correction.
        model_units = read_project_file(projects_root, project_id, "placement.json").get("model_units", "file")
    if model_units not in ("file", "meters", "millimeters", "centimeters"):
        raise ProjectError("Kies bestandseenheid, meters, millimeters of centimeters.")
    placement = {
        "schema_version": PLACEMENT_SCHEMA_VERSION,
        "translation_m": {"x": float(x), "y": float(y), "z": float(z)},
        "rotation_z_degrees": float(rotation_z_degrees) % 360.0,
        "unit_scale": 1.0,
        "model_units": model_units,
        "approved": bool(approved),
        "updated_at": _timestamp(),
    }
    _write_json(directory / "placement.json", placement)
    project["status"] = "placement_approved" if approved else "placement_draft"
    project["updated_at"] = placement["updated_at"]
    _write_json(directory / "project.json", project)
    return placement


def list_projects(projects_root: Path) -> list[dict[str, Any]]:
    root = projects_root.expanduser().resolve()
    if not root.exists():
        return []
    projects: list[dict[str, Any]] = []
    for manifest_path in root.glob("*/project.json"):
        try:
            manifest = load_project(root, manifest_path.parent.name)
        except ProjectError:
            continue
        projects.append(manifest)
    return sorted(projects, key=lambda project: project["updated_at"], reverse=True)
