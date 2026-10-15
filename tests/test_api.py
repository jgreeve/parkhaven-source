import base64
import hashlib
import json
import struct
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.projects import ProjectError
from app.view_evidence import MAX_IMAGE_BYTES, _decode_png


def png_data_url(width=768, height=512):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + b"\x00\x00\x00" * width for _ in range(height))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def test_view_capture_rejects_oversized_image_before_png_processing():
    data_url = "data:image/png;base64," + base64.b64encode(b"x" * (MAX_IMAGE_BYTES + 1)).decode("ascii")
    with pytest.raises(ProjectError, match="groter dan 5 MB"):
        _decode_png(data_url)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "PROJECTS_ROOT", tmp_path / "projects")
    with TestClient(main.app) as test_client:
        yield test_client


def test_site_context_serves_pinned_aerial_and_provenance(client):
    manifest = client.get("/api/site-context")
    assert manifest.status_code == 200
    context = manifest.json()
    assert context["context_id"] == "parkhaven-pdok-aerial-2025-v1"
    assert context["alignment"]["status"] == "provisional"
    assert "PDOK" in context["source"]["attribution"]
    image = client.get(context["image_url"])
    assert image.status_code == 200 and image.headers["content-type"].startswith("image/jpeg")
    assert hashlib.sha256(image.content).hexdigest() == context["image_sha256"]
    assert image.headers["etag"] == f'"{context["image_sha256"]}"'


def test_health_and_ui(client):
    assert client.get("/api/health").json() == {"status": "ok", "version": "0.1.0"}
    assert "ParkHaven" in client.get("/").text
    assert client.get("/styles.css").status_code == 200
    page = client.get("/").text
    viewer = client.get("/viewer.js").text
    assert "Schaduwscreening" in page and "UTCI / hittestress (screening)" in page
    assert "Palenfundering (indicatief)" in page
    assert "[1, 2].includes(data.schema_version)" in viewer
    assert "Uint8BufferAttribute(vertexColors, 3, true)" in viewer


def test_create_list_and_open_project(client, tmp_path):
    source = tmp_path / "ontwerp.3dm"
    source.write_bytes(b"sample 3dm payload")
    response = client.post(
        "/api/projects",
        json={"design_path": str(source), "name": "Parkhaven alternatief"},
    )
    assert response.status_code == 201
    project = response.json()
    assert project["name"] == "Parkhaven alternatief"
    assert response.headers["cache-control"] == "no-store"

    listing = client.get("/api/projects")
    assert listing.headers["cache-control"] == "no-store"
    assert [item["project_id"] for item in listing.json()] == [project["project_id"]]
    detail = client.get(f"/api/projects/{project['project_id']}").json()
    assert detail["project_id"] == project["project_id"]
    assert detail["placement"]["approved"] is False
    assert detail["runs"] == []


def test_invalid_import_returns_readable_error(client, tmp_path):
    response = client.post("/api/projects", json={"design_path": str(tmp_path / "missing.3dm")})
    assert response.status_code == 400
    assert "bestaat niet" in response.json()["detail"]


def test_invalid_project_id_is_not_found(client):
    assert client.get("/api/projects/not-valid").status_code == 404


def test_placement_must_be_approved_before_analysis(client, tmp_path, monkeypatch):
    source = tmp_path / "ontwerp.3dm"
    source.write_bytes(b"sample 3dm payload")
    project = client.post("/api/projects", json={"design_path": str(source)}).json()
    project_id = project["project_id"]

    blocked = client.post(f"/api/projects/{project_id}/analysis", json={"launch_rhino": False})
    assert blocked.status_code == 400
    assert "plaatsing" in blocked.json()["detail"].lower()

    placement = client.put(
        f"/api/projects/{project_id}/placement",
        json={"x": 12.5, "y": -3, "z": 0, "rotation_z_degrees": 370, "approved": True},
    )
    assert placement.status_code == 200
    assert placement.json()["rotation_z_degrees"] == 10

    analyzer = tmp_path / "analyzer"
    analyzer.mkdir()
    (analyzer / "ParkHaven_MVP.3dm").write_bytes(b"context")
    (analyzer / "ParkHaven_MVP.ghx").write_bytes(b"definition")
    (analyzer / "weather").mkdir()
    (analyzer / "weather" / "NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw").write_text("weather")
    monkeypatch.setattr(main, "ANALYZER_ROOT", analyzer)

    started = client.post(f"/api/projects/{project_id}/analysis", json={"launch_rhino": False})
    assert started.status_code == 202
    job = started.json()
    assert job["status"] == "prepared"
    assert Path(job["definition"]).is_file()
    assert client.get(f"/api/projects/{project_id}/runs/{job['run_id']}").status_code == 200


def test_completed_run_has_printable_report(client, tmp_path, monkeypatch):
    source = tmp_path / "ontwerp.3dm"
    source.write_bytes(b"sample")
    project_id = client.post("/api/projects", json={"design_path": str(source)}).json()["project_id"]
    client.put(
        f"/api/projects/{project_id}/placement",
        json={"x": 0, "y": 0, "z": 0, "rotation_z_degrees": 0, "approved": True},
    )
    analyzer = tmp_path / "analyzer"
    analyzer.mkdir()
    (analyzer / "ParkHaven_MVP.3dm").write_bytes(b"context")
    (analyzer / "ParkHaven_MVP.ghx").write_bytes(b"definition")
    (analyzer / "weather").mkdir()
    (analyzer / "weather" / "NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw").write_text("weather")
    monkeypatch.setattr(main, "ANALYZER_ROOT", analyzer)
    job = client.post(f"/api/projects/{project_id}/analysis", json={"launch_rhino": False}).json()
    run_dir = Path(job["data_dir"]).parent
    job_path = run_dir / "job.json"
    persisted = __import__("json").loads(job_path.read_text(encoding="utf-8"))
    persisted["status"] = "completed"
    job_path.write_text(__import__("json").dumps(persisted), encoding="utf-8")
    (run_dir / "data" / "latest.json").write_text(
        '{"bvo_m2":1000,"sight_pct":60,"indicative_cost_eur":1800000}', encoding="utf-8"
    )

    report = client.get(f"/projects/{project_id}/runs/{job['run_id']}/report")
    assert report.status_code == 200
    assert "1,000.0 m²" in report.text
    assert "Save as PDF" in report.text
    missing_evidence = client.post(f"/api/projects/{project_id}/runs/{job['run_id']}/ai-review", json={
        "endpoint": "https://ai.example.test/v1", "api_key": "temporary",
        "model": "vision-model", "design_goal": "Meer zicht",
    })
    assert missing_evidence.status_code == 400
    assert "Leg eerst vier geldige modelbeelden vast" in missing_evidence.json()["detail"]


def test_scene_is_only_served_as_no_store_completed_evidence(client, tmp_path, monkeypatch):
    source = tmp_path / "scene.3dm"
    source.write_bytes(b"sample")
    project_id = client.post("/api/projects", json={"design_path": str(source)}).json()["project_id"]
    client.put(f"/api/projects/{project_id}/placement",
               json={"x": 0, "y": 0, "z": 0, "rotation_z_degrees": 0, "approved": True})
    analyzer = tmp_path / "analyzer"
    analyzer.mkdir()
    (analyzer / "ParkHaven_MVP.3dm").write_bytes(b"context")
    (analyzer / "ParkHaven_MVP.ghx").write_bytes(b"definition")
    (analyzer / "weather").mkdir()
    (analyzer / "weather" / "NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw").write_text("weather")
    monkeypatch.setattr(main, "ANALYZER_ROOT", analyzer)
    job = client.post(f"/api/projects/{project_id}/analysis", json={"launch_rhino": False}).json()
    run_dir = Path(job["data_dir"]).parent
    scene = b'{"schema_version":1,"units":"meters","up_axis":"Z","layers":[]}'
    (run_dir / "data/scene.json").write_bytes(scene)
    url = f"/api/projects/{project_id}/runs/{job['run_id']}/scene.json"
    assert client.get(url).status_code == 409
    job_path = run_dir / "job.json"
    persisted = __import__("json").loads(job_path.read_text(encoding="utf-8"))
    persisted["status"] = "completed"
    job_path.write_text(__import__("json").dumps(persisted), encoding="utf-8")
    response = client.get(url)
    assert response.status_code == 200
    assert response.content == scene
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "no-store"
    (run_dir / "data/scene.json").unlink()
    assert client.get(url).status_code == 404


def test_unapproved_placement_preview_is_isolated_from_analysis_runs(client, tmp_path, monkeypatch):
    source = tmp_path / "preview.3dm"
    source.write_bytes(b"preview source remains unchanged")
    project_id = client.post("/api/projects", json={"design_path": str(source)}).json()["project_id"]
    analyzer = tmp_path / "analyzer"
    analyzer.mkdir()
    (analyzer / "ParkHaven_MVP.3dm").write_bytes(b"context")
    monkeypatch.setattr(main, "ANALYZER_ROOT", analyzer)

    response = client.post(f"/api/projects/{project_id}/placement-preview", json={"launch_rhino": False})
    assert response.status_code == 202
    preview = response.json()
    assert preview["job_type"] == "placement_preview"
    assert preview["placement"]["approved"] is False
    assert "definition" not in preview and "results" not in preview

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["runs"] == []
    assert detail["placement_preview"]["run_id"] == preview["run_id"]
    preview_url = f"/api/projects/{project_id}/placement-previews/{preview['run_id']}"
    assert client.get(preview_url).status_code == 200
    assert client.get(f"/api/projects/{project_id}/runs/{preview['run_id']}").status_code == 404

    run_dir = Path(preview["data_dir"]).parent
    scene = b'{"schema_version":1,"kind":"placement_preview","units":"meters","up_axis":"Z","layers":[]}'
    (run_dir / "data" / "scene.json").write_bytes(scene)
    scene_url = preview_url + "/scene.json"
    assert client.get(scene_url).status_code == 409
    job_path = run_dir / "job.json"
    persisted = __import__("json").loads(job_path.read_text(encoding="utf-8"))
    persisted["status"] = "completed"
    job_path.write_text(__import__("json").dumps(persisted), encoding="utf-8")
    served = client.get(scene_url)
    assert served.status_code == 200
    assert served.content == scene
    assert served.headers["cache-control"] == "no-store"
    assert client.get(f"/api/projects/{project_id}/runs/{preview['run_id']}/scene.json").status_code == 404
    assert source.read_bytes() == b"preview source remains unchanged"


def test_model_units_persist_and_legacy_updates_preserve_selection(client, tmp_path):
    source = tmp_path / "units.3dm"
    source.write_bytes(b"source stays unchanged")
    project = client.post("/api/projects", json={"design_path": str(source)}).json()
    url = f"/api/projects/{project['project_id']}"
    assert client.get(url).json()["placement"]["model_units"] == "file"
    placement = {"x": 12, "y": -3, "z": 0, "rotation_z_degrees": 90, "approved": True}
    response = client.put(url + "/placement", json={**placement, "model_units": "meters"})
    assert response.status_code == 200 and response.json()["model_units"] == "meters"
    assert client.get(url).json()["placement"]["model_units"] == "meters"
    # An older API client omitting the new field must retain the correction.
    assert client.put(url + "/placement", json=placement).json()["model_units"] == "meters"
    assert client.put(url + "/placement", json={**placement, "model_units": "file"}).json()["model_units"] == "file"
    assert source.read_bytes() == b"source stays unchanged"


def test_completed_run_publishes_bounded_same_run_view_evidence(client, tmp_path, monkeypatch):
    source = tmp_path / "views.3dm"
    source.write_bytes(b"sample")
    project_id = client.post("/api/projects", json={"design_path": str(source)}).json()["project_id"]
    client.put(f"/api/projects/{project_id}/placement",
               json={"x": 0, "y": 0, "z": 0, "rotation_z_degrees": 0, "approved": True})
    analyzer = tmp_path / "analyzer"
    analyzer.mkdir()
    (analyzer / "ParkHaven_MVP.3dm").write_bytes(b"context")
    (analyzer / "ParkHaven_MVP.ghx").write_bytes(b"definition")
    (analyzer / "weather").mkdir()
    (analyzer / "weather" / "NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw").write_text("weather")
    monkeypatch.setattr(main, "ANALYZER_ROOT", analyzer)
    job = client.post(f"/api/projects/{project_id}/analysis", json={"launch_rhino": False}).json()
    data_dir = Path(job["data_dir"])
    scene = {"schema_version": 2, "units": "meters", "up_axis": "Z",
             "design_render_style": "volume-colors-v1", "layers": [
        {"name": "PH_DESIGN", "vertices": [0, 0, 0], "triangles": [0, 0, 0],
         "vertex_colors": [47, 128, 237]},
        {"name": "REFERENCE_CONTEXT", "vertices": [1, 1, 0], "triangles": [0, 0, 0]},
        {"name": "ANALYSIS_SHADOW", "vertices": [0, 0, 0], "triangles": [0, 0, 0],
         "vertex_colors": [20, 80, 180]},
        {"name": "ANALYSIS_UTCI", "vertices": [0, 0, 0], "triangles": [0, 0, 0],
         "vertex_colors": [220, 80, 40]},
        {"name": "ANALYSIS_PILES", "vertices": [0, 0, 0], "triangles": [0, 0, 0]},
    ]}
    scene_bytes = json.dumps(scene).encode()
    summary_bytes = json.dumps({
        "schema_version": 1, "project_id": project_id, "run_id": job["run_id"],
        "source_sha256": job["source_sha256"], "input_sha256": job["input_sha256"],
        "context_sha256": job["context_sha256"], "placement": job["placement"], "objects": [{
            "id": "source:12345678-1234-1234-1234-123456789abc",
            "classification": "analysis_volume",
            "bounds_m": {"min": [-10, -10, 0], "max": [10, 10, 20]},
        }],
    }).encode()
    results_bytes = b'{"bvo_m2":1000,"sight_pct":60,"indicative_cost_eur":1800000,"shadow_mean_hours":4.5,"utci_mean_c":27.4,"pile_count_load":42}'
    (data_dir / "scene.json").write_bytes(scene_bytes)
    (data_dir / "geometry-summary.json").write_bytes(summary_bytes)
    (data_dir / "latest.json").write_bytes(results_bytes)
    job_path = data_dir.parent / "job.json"
    persisted = json.loads(job_path.read_text(encoding="utf-8"))
    persisted["status"] = "completed"
    job_path.write_text(json.dumps(persisted), encoding="utf-8")
    image = png_data_url()
    payload = {
        "scene_sha256": hashlib.sha256(scene_bytes).hexdigest(),
        "geometry_summary_sha256": hashlib.sha256(summary_bytes).hexdigest(),
        "site_context_sha256": client.get("/api/site-context").json()["manifest_sha256"],
        "render_style": "volume-colors-v1",
        "views": [{
            "id": view_id, "image_data_url": image, "width": 768, "height": 512,
            "projection": "perspective", "fov_degrees": 40,
            "camera_position": [10, -10, 10], "camera_target": [0, 0, 0], "camera_up": [0, 0, 1],
            "visible_layers": ["PH_DESIGN", "REFERENCE_CONTEXT", "PDOK_AERIAL"],
        } for view_id in ("top", "overview", "facade-side", "park-side")],
    }
    url = f"/api/projects/{project_id}/runs/{job['run_id']}/view-evidence"
    response = client.post(url, json=payload)
    assert response.status_code == 201
    manifest = response.json()
    assert manifest["run_id"] == job["run_id"] and len(manifest["views"]) == 4
    assert manifest["scene_sha256"] == payload["scene_sha256"]
    assert manifest["results_sha256"] == hashlib.sha256(results_bytes).hexdigest()
    assert manifest["weather_sha256"] == job["weather_sha256"]
    assert manifest["render_style"] == "volume-colors-v1"
    assert {view["id"] for view in manifest["views"]} == {"top", "overview", "facade-side", "park-side"}
    assert all((data_dir / view["path"]).read_bytes().startswith(b"\x89PNG") for view in manifest["views"])
    assert json.loads((data_dir / "view-evidence.json").read_text(encoding="utf-8"))["capture_id"] == manifest["capture_id"]

    assert client.post(url, json={**payload, "scene_sha256": "0" * 64}).status_code == 400
    bad_view = {**payload["views"][0], "image_data_url": "data:image/png;base64," + base64.b64encode(b"not png").decode()}
    assert client.post(url, json={**payload, "views": [bad_view, *payload["views"][1:]]}).status_code == 400
    duplicate = {**payload["views"][1], "id": "top"}
    assert client.post(url, json={**payload, "views": [payload["views"][0], duplicate, *payload["views"][2:]]}).status_code == 400
    assert json.loads((data_dir / "view-evidence.json").read_text(encoding="utf-8"))["capture_id"] == manifest["capture_id"]

    captured = {}
    def fake_review(**kwargs):
        captured.update(kwargs)
        return {"samenvatting": "Evidence ontvangen.", "visual_evidence_used": True}
    monkeypatch.setattr(main, "request_review", fake_review)
    ai_url = f"/api/projects/{project_id}/runs/{job['run_id']}/ai-review"
    ai_payload = {"endpoint": "https://ai.example.test/v1", "api_key": "temporary",
                  "model": "vision-model", "design_goal": "Meer parkzicht"}
    advice = client.post(ai_url, json=ai_payload)
    assert advice.status_code == 200 and advice.json()["visual_evidence_used"] is True
    assert captured["evidence"]["images"] == []
    assert captured["evidence"]["view_ids"] == {"top", "overview", "facade-side", "park-side"}
    assert captured["evidence"]["metric_fields"] == {
        "bvo_m2", "sight_pct", "indicative_cost_eur", "shadow_mean_hours", "utci_mean_c", "pile_count_load"}
    assert "geometry" not in captured["evidence"]["structured"]
    assert set(captured["evidence"]["structured"]) == {
        "calculated_results", "design_elements", "views", "evidence_status", "site_constraints"}
    assert captured["evidence"]["horizontal_moves_allowed"] is True
    assert captured["evidence"]["structured"]["site_constraints"]["status"] == "unavailable"
    assert client.get(f"/api/projects/{project_id}/runs/{job['run_id']}").json()["view_evidence_available"] is True

    first_image = data_dir / manifest["views"][0]["path"]
    first_image.write_bytes(first_image.read_bytes() + b"changed")
    rejected = client.post(ai_url, json=ai_payload)
    assert rejected.status_code == 400 and "gewijzigd" in rejected.json()["detail"]


@pytest.mark.parametrize("units", ["automatic-guess", 1000, "", "inches"])
def test_model_units_reject_unknown_interpretations(client, units):
    response = client.put("/api/projects/unused/placement", json={
        "x": 0, "y": 0, "rotation_z_degrees": 0, "model_units": units})
    assert response.status_code == 422
