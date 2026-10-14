"""Explicit Edge UI smoke with mocked analysis APIs; requires optional playwright."""

import json
import hashlib
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    placement = {"translation_m": {"x": 0, "y": 0, "z": 0}, "rotation_z_degrees": 0,
                 "model_units": "file", "approved": True}
    projects = [
        {"project_id": name, "name": name, "updated_at": "2026-09-29T12:00:00Z",
         "source": {"original_filename": name + ".3dm"}, "placement": dict(placement), "runs": []}
        for name in ("Baseline", "Nieuw")
    ]
    projects[0]["runs"] = [{"run_id": "baseline", "status": "completed", "scene_available": True,
                            "scene_sha256": "a" * 64, "geometry_summary": {"sha256": "b" * 64},
                            "placement": placement, "model_units": {"physical_size_m": [10, 20, 9]},
                            "results": {"bvo_m2": 1000, "sight_pct": 65.12, "indicative_cost_eur": 1800000,
                                        "shadow_mean_hours": 5.1, "shadow_min_hours": 0, "shadow_max_hours": 11,
                                        "shadow_sunlit_pct": 93.9, "utci_mean_c": 12.6, "utci_max_c": 18.5,
                                        "heat_stress_area_pct": 0, "pile_count_load": 82, "pile_count_grid": 127,
                                        "pile_max_storeys": 21, "pile_max_utilization_pct": 100}}]
    projects[0]["placement_preview"] = {"run_id": "preview", "job_type": "placement_preview",
        "status": "completed", "scene_available": True, "placement": placement,
        "context_sha256": "e85306b01ca9bc2a0f12f80e37fc5da4a685aaf30e5e9ba8ff2c2148226f39d1",
        "model_units": {"declared": "Meters", "coordinate_scale": 1, "meters_per_coordinate": 1,
                        "physical_size_m": [10, 20, 9]}}
    projects[1]["placement_preview"] = None
    current = {"run_id": "active", "status": "launch_requested"}
    preview_current = {"run_id": "new-preview", "job_type": "placement_preview", "status": "launch_requested",
                       "scene_available": False, "placement": placement}
    cancellations = []
    preview_cancellations = []
    saved_units = []
    saved_gizmo = []
    captured_views = []
    context_raw = (ROOT / "site-context/manifest.json").read_bytes()
    context = json.loads(context_raw)
    context_public = {key: value for key, value in context.items() if key != "image_filename"}
    context_public.update(manifest_sha256=hashlib.sha256(context_raw).hexdigest(), image_url="/api/site-context/aerial.jpg")
    viewer_assets = ROOT.parent / "ParkHaven_Analyzer_App_v0.2/app/static/vendor/three"
    scene = {"schema_version": 2, "units": "meters", "up_axis": "Z", "design_render_style": "volume-colors-v1",
              "timestamp": "2026-09-30T12:00:00Z",
              "layers": [{"name": "PH_DESIGN", "vertices": [0, 0, 0, 10, 0, 0, 0, 10, 9], "triangles": [0, 1, 2],
                          "vertex_colors": [47, 128, 237, 47, 128, 237, 47, 128, 237]},
                         {"name": "PH_FACADES", "vertices": [-10, -20, 0, 10, -20, 0, 0, -20, 10], "triangles": [0, 1, 2]},
                         {"name": "PH_TARGET", "vertices": [-10, 20, 0, 10, 20, 0, 0, 20, 10], "triangles": [0, 1, 2]},
                         {"name": "REFERENCE_CONTEXT", "vertices": [-20, -20, 0, 20, -20, 0, 0, 20, 0], "triangles": [0, 1, 2]},
                         {"name": "ANALYSIS_SHADOW", "vertices": [0, 0, 9, 10, 0, 9, 0, 10, 9],
                          "triangles": [0, 1, 2], "vertex_colors": [30, 70, 130, 255, 220, 70, 30, 70, 130]},
                         {"name": "ANALYSIS_UTCI", "vertices": [0, 0, 9.1, 10, 0, 9.1, 0, 10, 9.1],
                          "triangles": [0, 1, 2], "vertex_colors": [45, 125, 210, 230, 55, 40, 45, 125, 210]},
                         {"name": "ANALYSIS_PILES", "vertices": [4, 4, 0, 5, 4, 0, 4, 5, 1], "triangles": [0, 1, 2]}]}
    preview_scene = {"schema_version": 1, "kind": "placement_preview", "units": "meters", "up_axis": "Z",
                      "design_render_style": "volume-colors-v1",
                      "layers": [*scene["layers"][:4],
                                {"name": "PH_VISUAL_ONLY", "vertices": [1, 1, 0, 2, 1, 0, 1, 2, 0],
                                 "triangles": [0, 1, 2]}]}

    def asset(route):
        path = viewer_assets / route.request.url.split("/viewer-assets/")[1]
        route.fulfill(status=200, content_type="text/javascript", body=path.read_bytes())

    def api(route):
        path = route.request.url.split("/api/")[1]
        method = route.request.method
        if path == "site-context":
            payload = context_public
        elif path == "site-context/aerial.jpg":
            route.fulfill(status=200, content_type="image/jpeg", body=(ROOT / "site-context" / context["image_filename"]).read_bytes())
            return
        elif path == "projects":
            payload = projects
        elif path == "projects/Baseline/placement":
            assert method == "PUT"
            values = route.request.post_data_json
            saved_gizmo.append(values)
            projects[0]["placement"] = {"translation_m": {"x": values["x"], "y": values["y"], "z": values["z"]},
                                         "rotation_z_degrees": values["rotation_z_degrees"],
                                         "model_units": values["model_units"], "approved": values["approved"]}
            payload = projects[0]["placement"]
        elif path == "projects/Nieuw/placement":
            assert method == "PUT"
            values = route.request.post_data_json
            saved_units.append(values["model_units"])
            projects[1]["placement"] = {**placement, "model_units": values["model_units"], "approved": values["approved"]}
            payload = projects[1]["placement"]
        elif path == "projects/Nieuw/analysis":
            assert method == "POST"
            payload = current
        elif path == "projects/Nieuw/placement-preview":
            assert method == "POST"
            payload = preview_current
        elif path == "projects/Nieuw/placement-previews/new-preview/cancel":
            assert method == "POST"
            preview_cancellations.append(path)
            preview_current["status"] = "cancelled"
            payload = preview_current
        elif path.endswith("/cancel"):
            assert method == "POST"
            cancellations.append(path)
            current["status"] = "cancelled"
            payload = current
        elif path == "projects/Baseline/runs/baseline/scene.json":
            payload = scene
        elif path == "projects/Baseline/runs/baseline":
            payload = projects[0]["runs"][0]
        elif path == "projects/Baseline/runs/baseline/view-evidence":
            assert method == "POST"
            values = route.request.post_data_json
            assert values["scene_sha256"] == "a" * 64 and values["geometry_summary_sha256"] == "b" * 64
            assert values["site_context_sha256"] == context_public["manifest_sha256"]
            assert values["render_style"] == "volume-colors-v1"
            assert [view["id"] for view in values["views"]] == ["top", "overview", "facade-side", "park-side"]
            assert all(view["width"] == 768 and view["height"] == 512 for view in values["views"])
            assert all(view["image_data_url"].startswith("data:image/png;base64,iVBOR") for view in values["views"])
            assert all(set(view["visible_layers"]) == {"PH_DESIGN", "PH_FACADES", "PH_TARGET", "REFERENCE_CONTEXT", "PDOK_AERIAL"}
                       for view in values["views"])
            assert values["views"][2]["camera_position"] != values["views"][3]["camera_position"]
            captured_views.extend(values["views"])
            projects[0]["runs"][0]["view_evidence_available"] = True
            payload = {"run_id": "baseline", "capture_id": "capture", "views": [{"id": view["id"]} for view in values["views"]]}
        elif path == "projects/Baseline/placement-previews/preview/scene.json":
            payload = preview_scene
        elif "/runs/" in path:
            payload = current
        else:
            payload = next(project for project in projects if path == "projects/" + project["project_id"])
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "app/static")))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/viewer-assets/**", asset)
            page.route("**/api/**", api)
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.locator(".open-project").nth(0).click()
            expect(page.locator("#metrics")).to_be_visible()
            expect(page.locator("#report-link")).to_have_attribute("aria-disabled", "false")
            expect(page.locator("#model-viewer")).to_have_attribute("data-state", "ready")
            expect(page.locator("#model-viewer")).to_have_attribute("data-site-context", "parkhaven-pdok-aerial-2025-v1")
            expect(page.locator("#aerial-visible")).to_be_enabled()
            expect(page.locator("#aerial-status")).to_contain_text("PDOK")
            expect(page.locator("#model-viewer")).to_have_attribute("data-triangles", "7")
            expect(page.locator("#analysis-legends")).to_be_visible()
            expect(page.locator("#metric-shadow")).to_contain_text("5,1 uur")
            expect(page.locator("#metric-utci")).to_contain_text("12,6 °C")
            expect(page.locator("#metric-piles")).to_contain_text("82 palen")
            expect(page.locator("#model-viewer")).to_have_attribute("data-placement-state", "calculated")
            expect(page.locator("#capture-views")).to_be_enabled()
            expect(page.locator("#capture-status")).to_contain_text("Laatste analyse geladen")
            page.locator("#show-preview").click()
            expect(page.locator("#model-viewer")).to_have_attribute("data-triangles", "5")
            expect(page.locator("#model-viewer")).to_have_attribute("data-placement-state", "approved")
            expect(page.locator("#model-viewer")).to_have_attribute("data-reference-matrix", "identity")
            expect(page.locator("#spatial-checks")).to_have_attribute("data-scale-status", "ok")
            expect(page.locator("#spatial-checks")).to_have_attribute("data-z-status", "touching")
            expect(page.locator("#spatial-checks")).to_have_attribute("data-reference-distance", "0")
            expect(page.locator("#check-provenance")).to_contain_text("e85306b01ca9")
            expect(page.locator("#viewer-canvas canvas")).to_have_count(1)
            expect(page.locator("#viewer-meta")).to_contain_text("10 × 20 × 9 m")
            expect(page.locator('#model-viewer input[data-viewer-layer="PH_VISUAL_ONLY"]')).to_be_visible()
            expect(page.locator("#gizmo-move")).to_be_enabled()
            page.locator("#viewer-canvas canvas").scroll_into_view_if_needed()
            origin = [float(value) for value in page.locator("#model-viewer").get_attribute("data-gizmo-origin").split(",")]
            x_handle = [float(value) for value in page.locator("#model-viewer").get_attribute("data-gizmo-x").split(",")]
            canvas_box = page.locator("#viewer-canvas canvas").bounding_box()
            origin = [origin[0] + canvas_box["x"], origin[1] + canvas_box["y"]]
            x_handle = [x_handle[0] + canvas_box["x"], x_handle[1] + canvas_box["y"]]
            page.mouse.move(*x_handle)
            page.mouse.down()
            page.mouse.move(x_handle[0] + (x_handle[0] - origin[0]) * 0.5,
                            x_handle[1] + (x_handle[1] - origin[1]) * 0.5)
            page.mouse.up()
            assert float(page.locator("#place-x").input_value()) > 0, (
                origin, x_handle, page.locator("#model-viewer").get_attribute("data-gizmo-hit"))
            assert float(page.locator("#place-y").input_value()) == 0
            expect(page.locator("#placement-status")).to_contain_text("3D-gereedschap")
            moved_x = float(page.locator("#place-x").input_value())
            page.locator('#placement-form button[type="submit"]').click()
            expect(page.locator("#placement-status")).to_contain_text("Conceptplaatsing opgeslagen")
            assert saved_gizmo[-1]["x"] == moved_x and saved_gizmo[-1]["approved"] is False
            page.locator("#gizmo-reset").click()
            assert float(page.locator("#place-x").input_value()) == moved_x
            page.locator("#place-x").fill("0")
            page.locator("#place-approved").check()
            page.locator('#placement-form button[type="submit"]').click()
            expect(page.locator("#model-viewer")).to_have_attribute("data-placement-state", "approved")
            page.locator("#gizmo-reference").select_option("center")
            page.locator("#gizmo-snap-origin").click()
            assert float(page.locator("#place-x").input_value()) == -5
            assert float(page.locator("#place-y").input_value()) == -5
            page.locator("#gizmo-reset").click()
            page.locator("#gizmo-rotate").click()
            ring_start = [float(value) for value in page.locator("#model-viewer").get_attribute("data-gizmo-ring").split(",")]
            ring_end = [float(value) for value in page.locator("#model-viewer").get_attribute("data-gizmo-ring-quarter").split(",")]
            page.locator("#viewer-canvas canvas").scroll_into_view_if_needed()
            canvas_box = page.locator("#viewer-canvas canvas").bounding_box()
            ring_start = [ring_start[0] + canvas_box["x"], ring_start[1] + canvas_box["y"]]
            ring_end = [ring_end[0] + canvas_box["x"], ring_end[1] + canvas_box["y"]]
            page.mouse.move(*ring_start)
            page.mouse.down()
            page.mouse.move(*ring_end)
            page.mouse.up()
            rotation = float(page.locator("#place-rotation").input_value())
            assert 20 < rotation < 340, (rotation, ring_start, ring_end,
                page.locator("#model-viewer").get_attribute("data-gizmo-hit"))
            page.locator("#gizmo-reset").click()
            page.locator("#place-z").fill("-2")
            expect(page.locator("#spatial-checks")).to_have_attribute("data-z-status", "below")
            expect(page.locator("#check-world-z")).to_contain_text("geen maaiveldtoets")
            page.locator("#place-z").fill("2")
            expect(page.locator("#spatial-checks")).to_have_attribute("data-z-status", "above")
            page.locator("#place-z").fill("0")
            page.locator("#place-x").fill("1000")
            expect(page.locator("#spatial-checks")).to_have_attribute("data-state", "warning")
            assert float(page.locator("#spatial-checks").get_attribute("data-reference-distance")) > 900
            expect(page.locator("#check-reference")).to_contain_text("geen plottoets")
            page.locator("#place-x").fill("12")
            expect(page.locator("#model-viewer")).to_have_attribute("data-placement-state", "draft")
            matrix = [float(value) for value in page.locator("#model-viewer").get_attribute("data-design-matrix").split(",")]
            assert matrix[12] == 12 and matrix[13] == 0 and matrix[14] == 0
            page.locator("#place-rotation").fill("90")
            page.locator("#place-model-units").select_option("millimeters")
            matrix = [float(value) for value in page.locator("#model-viewer").get_attribute("data-design-matrix").split(",")]
            assert matrix[0] == 0 and matrix[1] == 0.001 and matrix[4] == -0.001 and matrix[12] == 12
            expect(page.locator("#spatial-checks")).to_have_attribute("data-scale-status", "too-small")
            expect(page.locator("#check-scale")).to_contain_text("Controleer Modeleenheid")
            expect(page.locator("#metrics-provenance")).to_contain_text("laatste analyse")
            page.locator("#show-analysis").click()
            expect(page.locator("#model-viewer")).to_have_attribute("data-triangles", "7")
            expect(page.locator("#model-viewer")).to_have_attribute("data-placement-state", "calculated")
            expect(page.locator("#capture-views")).to_be_enabled()
            expect(page.locator("#ai-form button")).to_be_disabled()
            expect(page.locator("#ai-status")).to_contain_text("Leg eerst vier modelbeelden vast")
            page.locator("#capture-views").click()
            expect(page.locator("#capture-status")).to_contain_text("Vier modelbeelden opgeslagen")
            expect(page.locator("#ai-form button")).to_be_enabled()
            expect(page.locator("#ai-status")).to_contain_text("gereed voor AI-advies")
            assert len(captured_views) == 4
            assert all(not any(layer.startswith("ANALYSIS_") for layer in view["visible_layers"])
                       for view in captured_views)
            page.locator("#show-preview").click()
            expect(page.locator("#model-viewer")).to_have_attribute("data-triangles", "5")
            page.locator("#view-top").click()
            page.locator('input[data-viewer-layer="REFERENCE_CONTEXT"]').uncheck()
            page.locator(".open-project").nth(1).click()
            expect(page.locator("#metrics")).to_be_hidden()
            expect(page.locator("#report-link")).to_have_attribute("aria-disabled", "true")
            expect(page.locator("#ai-form button")).to_be_disabled()
            expect(page.locator("#model-viewer")).to_have_attribute("data-state", "empty")
            expect(page.locator("#viewer-status")).to_have_text("Er is nog geen berekende analyse om te tonen.")
            expect(page.locator("#place-model-units")).to_have_value("file")
            page.locator("#place-model-units").select_option("meters")
            expect(page.locator("#start-analysis")).to_be_disabled()
            page.locator('#placement-form button[type="submit"]').click()
            expect(page.locator("#placement-status")).to_contain_text("modeleenheid opgeslagen")
            expect(page.locator("#start-analysis")).to_be_enabled()
            page.locator("#start-preview").click()
            expect(page.locator("#cancel-preview")).to_be_enabled()
            page.locator("#cancel-preview").click()
            expect(page.locator("#preview-status")).to_contain_text("geannuleerd")
            expect(page.locator("#start-analysis")).to_be_enabled()
            page.locator(".open-project").nth(0).click()
            expect(page.locator("#place-model-units")).to_have_value("file")
            page.locator(".open-project").nth(1).click()
            expect(page.locator("#place-model-units")).to_have_value("meters")
            page.locator("#start-analysis").click()
            expect(page.locator("#start-analysis")).to_be_disabled()
            expect(page.locator("#cancel-analysis")).to_be_enabled()
            expect(page.locator("#analysis-status")).to_contain_text("ParkHavenAnalyze")
            page.locator("#cancel-analysis").click()
            expect(page.locator("#analysis-status")).to_have_text("Analyse geannuleerd")
            expect(page.locator("#start-analysis")).to_be_enabled()
            expect(page.locator("#cancel-analysis")).to_be_disabled()
            expect(page.locator("#metrics")).to_be_hidden()
            assert cancellations == ["projects/Nieuw/runs/active/cancel"]
            assert preview_cancellations == ["projects/Nieuw/placement-previews/new-preview/cancel"]
            assert saved_units == ["meters"]
            assert not errors, errors
            browser.close()
        print("PASS: Edge preview/gizmo/spatial checks plus four controlled 768x512 run-view captures with reference-derived cameras and evidence upload; no JS exceptions.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
