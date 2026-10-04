"""Validation and atomic publication of deterministic model-view captures."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import shutil
import struct
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .projects import ProjectError, _sha256, _write_json
from .site_context import DEFAULT_SITE_CONTEXT_ROOT, SiteContextError, load_site_context


VIEW_IDS = ("top", "overview", "facade-side", "park-side")
WIDTH = 1200
HEIGHT = 800
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _vector(value: Any, field: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3 or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in value
    ):
        raise ProjectError(f"Ongeldige camerawaarde: {field}.")
    return [float(item) for item in value]


def _decode_png(data_url: Any) -> bytes:
    prefix = "data:image/png;base64,"
    if not isinstance(data_url, str) or not data_url.startswith(prefix):
        raise ProjectError("Modelbeeld is geen PNG-data-URL.")
    try:
        data = base64.b64decode(data_url[len(prefix):], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ProjectError("Modelbeeld bevat ongeldige base64-data.") from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise ProjectError("Een modelbeeld is groter dan 5 MB.")
    if len(data) < 45 or not data.startswith(PNG_SIGNATURE):
        raise ProjectError("Modelbeeld heeft geen geldige PNG-header.")
    offset = len(PNG_SIGNATURE)
    chunks = []
    width = height = None
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        end = offset + 12 + length
        if end > len(data):
            raise ProjectError("Modelbeeld bevat een afgebroken PNG-chunk.")
        chunk_type = data[offset + 4:offset + 8]
        chunk_data = data[offset + 8:offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length:end])[0]
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
            raise ProjectError("Modelbeeld bevat een ongeldige PNG-controlesom.")
        chunks.append(chunk_type)
        if chunk_type == b"IHDR":
            if len(chunks) != 1 or length != 13:
                raise ProjectError("Modelbeeld heeft een ongeldige PNG-header.")
            width, height = struct.unpack(">II", chunk_data[:8])
        offset = end
        if chunk_type == b"IEND":
            break
    if offset != len(data) or not chunks or chunks[-1] != b"IEND" or b"IDAT" not in chunks or width is None:
        raise ProjectError("Modelbeeld is geen compleet PNG-bestand.")
    if (width, height) != (WIDTH, HEIGHT):
        raise ProjectError(f"Modelbeeld moet exact {WIDTH} × {HEIGHT} pixels zijn.")
    return data


def save_view_evidence(job: dict[str, Any], payload: dict[str, Any],
                       site_context_root: Path = DEFAULT_SITE_CONTEXT_ROOT) -> dict[str, Any]:
    data_dir = Path(job["data_dir"])
    scene_path = data_dir / "scene.json"
    summary_path = data_dir / "geometry-summary.json"
    results_path = data_dir / "latest.json"
    if job.get("job_type", "analysis") != "analysis" or job.get("status") != "completed":
        raise ProjectError("Modelbeelden zijn alleen beschikbaar voor een voltooide analyse.")
    if not scene_path.is_file() or not summary_path.is_file() or not results_path.is_file():
        raise ProjectError("Scene, geometriesamenvatting en metrics moeten uit dezelfde voltooide run beschikbaar zijn.")
    scene_sha256 = _sha256(scene_path)
    summary_sha256 = _sha256(summary_path)
    results_sha256 = _sha256(results_path)
    if payload.get("scene_sha256") != scene_sha256 or payload.get("geometry_summary_sha256") != summary_sha256:
        raise ProjectError("De geladen scene of geometriesamenvatting is verouderd; laad de run opnieuw.")
    try:
        site_context = load_site_context(site_context_root)
    except SiteContextError as exc:
        raise ProjectError(str(exc)) from exc
    if payload.get("site_context_sha256") != site_context["manifest_sha256"]:
        raise ProjectError("De geladen luchtfotocontext is verouderd; laad de viewer opnieuw.")

    try:
        scene = json.loads(scene_path.read_text(encoding="utf-8-sig"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError("De runscene of geometriesamenvatting kan niet worden gevalideerd.") from exc
    expected_summary = {
        "project_id": job["project_id"], "run_id": job["run_id"],
        "source_sha256": job["source_sha256"], "input_sha256": job["input_sha256"],
        "context_sha256": job["context_sha256"], "placement": job["placement"],
    }
    if not isinstance(summary, dict) or any(summary.get(key) != value for key, value in expected_summary.items()):
        raise ProjectError("De geometriesamenvatting hoort niet aantoonbaar bij deze run en plaatsing.")
    expected_layers = sorted(
        layer["name"] for layer in scene.get("layers", [])
        if isinstance(layer, dict) and isinstance(layer.get("vertices"), list) and layer["vertices"]
        and isinstance(layer.get("triangles"), list) and layer["triangles"]
    )
    expected_layers.append("PDOK_AERIAL")
    expected_layers.sort()
    raw_views = payload.get("views")
    if not isinstance(raw_views, list) or len(raw_views) != len(VIEW_IDS):
        raise ProjectError("Exact vier gecontroleerde modelbeelden zijn vereist.")

    decoded: dict[str, tuple[bytes, dict[str, Any]]] = {}
    total_bytes = 0
    for raw in raw_views:
        if not isinstance(raw, dict) or raw.get("id") not in VIEW_IDS or raw["id"] in decoded:
            raise ProjectError("Modelbeeld-ID ontbreekt, is dubbel of is onbekend.")
        if raw.get("projection") != "perspective" or raw.get("width") != WIDTH or raw.get("height") != HEIGHT:
            raise ProjectError("Modelbeeld heeft ongeldige projectie of afmetingen.")
        fov = raw.get("fov_degrees")
        if isinstance(fov, bool) or not isinstance(fov, (int, float)) or not math.isclose(float(fov), 40, abs_tol=1e-9):
            raise ProjectError("Modelbeeld heeft een onverwacht camerabeeldveld.")
        layers = raw.get("visible_layers")
        if not isinstance(layers, list) or sorted(layers) != expected_layers or len(layers) != len(set(layers)):
            raise ProjectError("Modelbeeld gebruikt niet exact de geladen runlagen.")
        camera = {
            "camera_position": _vector(raw.get("camera_position"), "positie"),
            "camera_target": _vector(raw.get("camera_target"), "doel"),
            "camera_up": _vector(raw.get("camera_up"), "omhoog"),
        }
        image = _decode_png(raw.get("image_data_url"))
        total_bytes += len(image)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ProjectError("De vier modelbeelden zijn samen groter dan 16 MB.")
        decoded[raw["id"]] = (image, {**camera, "visible_layers": layers})
    if set(decoded) != set(VIEW_IDS):
        raise ProjectError("De vereiste modelbeeldset is niet compleet.")

    capture_id = str(uuid.uuid4())
    capture_root = data_dir / "view-evidence"
    capture_dir = capture_root / capture_id
    capture_dir.mkdir(parents=True)
    views = []
    try:
        for view_id in VIEW_IDS:
            image, camera = decoded[view_id]
            image_path = capture_dir / f"{view_id}.png"
            image_path.write_bytes(image)
            views.append({
                "id": view_id,
                "path": f"view-evidence/{capture_id}/{view_id}.png",
                "image_sha256": hashlib.sha256(image).hexdigest(),
                "bytes": len(image),
                "width": WIDTH,
                "height": HEIGHT,
                "projection": "perspective",
                "fov_degrees": 40,
                **camera,
            })
        manifest = {
            "schema_version": 1,
            "capture_id": capture_id,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "project_id": job["project_id"],
            "run_id": job["run_id"],
            "units": "meters",
            "up_axis": "Z",
            "source_sha256": job["source_sha256"],
            "input_sha256": job["input_sha256"],
            "context_sha256": job["context_sha256"],
            "scene_sha256": scene_sha256,
            "geometry_summary_sha256": summary_sha256,
            "results_sha256": results_sha256,
            "definition_sha256": job.get("definition_sha256"),
            "site_context_id": site_context["context_id"],
            "site_context_sha256": site_context["manifest_sha256"],
            "site_context_image_sha256": site_context["image_sha256"],
            "site_context_alignment_status": site_context["alignment"]["status"],
            "site_context_attribution": site_context["source"]["attribution"],
            "placement": job["placement"],
            "north_status": "unverified",
            "plot_status": "unavailable",
            "ground_status": "unavailable",
            "views": views,
        }
        _write_json(data_dir / "view-evidence.json", manifest)
    except Exception:
        shutil.rmtree(capture_dir, ignore_errors=True)
        raise
    for old_dir in capture_root.iterdir():
        if old_dir.is_dir() and old_dir != capture_dir:
            shutil.rmtree(old_dir, ignore_errors=True)
    return manifest
