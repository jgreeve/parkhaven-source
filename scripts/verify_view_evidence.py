"""Render and persist controlled views from the latest live baseline run evidence."""

from __future__ import annotations

import json
import struct
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.projects import load_project, read_project_file
from app.site_context import public_site_context
from app.view_evidence import save_view_evidence
from app.workflow import load_run


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    plugin_evidence = json.loads((ROOT / "docs/rhino_plugin_verification.json").read_text(encoding="utf-8"))
    workspace = Path(plugin_evidence["workspace"])
    project_id = plugin_evidence["job"]["project_id"]
    run_id = plugin_evidence["job"]["run_id"]
    job = load_run(workspace, project_id, run_id)
    project = load_project(workspace, project_id)
    project["placement"] = read_project_file(workspace, project_id, "placement.json")
    project["runs"] = [job]
    project["placement_preview"] = None
    viewer_assets = ROOT.parent / "ParkHaven_Analyzer_App_v0.2/app/static/vendor/three"
    published = {}

    def asset(route):
        path = viewer_assets / route.request.url.split("/viewer-assets/")[1]
        route.fulfill(status=200, content_type="text/javascript", body=path.read_bytes())

    def api(route):
        path = route.request.url.split("/api/")[1]
        if path == "projects":
            payload = [project]
        elif path == "site-context":
            payload = public_site_context()
        elif path == "site-context/aerial.jpg":
            route.fulfill(status=200, content_type="image/jpeg",
                          body=(ROOT / "site-context/parkhaven-aerial-2025.jpg").read_bytes())
            return
        elif path == f"projects/{project_id}":
            payload = project
        elif path == f"projects/{project_id}/runs/{run_id}/scene.json":
            route.fulfill(status=200, content_type="application/json",
                          body=(Path(job["data_dir"]) / "scene.json").read_bytes())
            return
        elif path == f"projects/{project_id}/runs/{run_id}":
            payload = job
        elif path == f"projects/{project_id}/runs/{run_id}/view-evidence":
            manifest = save_view_evidence(job, route.request.post_data_json)
            published.update(manifest)
            route.fulfill(status=201, content_type="application/json", body=json.dumps(manifest))
            return
        else:
            route.fulfill(status=404, content_type="application/json", body='{"detail":"not found"}')
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "app/static")))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/viewer-assets/**", asset)
            page.route("**/api/**", api)
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.locator(".open-project").click()
            expect(page.locator("#model-viewer")).to_have_attribute("data-state", "ready")
            expect(page.locator("#capture-views")).to_be_enabled()
            page.locator("#capture-views").click()
            expect(page.locator("#capture-status")).to_contain_text("Vier modelbeelden opgeslagen", timeout=30_000)
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert published["run_id"] == run_id and len(published["views"]) == 4
    view_report = []
    for view in published["views"]:
        image = Path(job["data_dir"]) / view["path"]
        data = image.read_bytes()
        width, height = struct.unpack(">II", data[16:24])
        assert (width, height) == (1200, 800)
        view_report.append({key: view[key] for key in (
            "id", "image_sha256", "bytes", "width", "height", "camera_position",
            "camera_target", "camera_up", "visible_layers")})
    report = {
        "passed": True,
        "workspace": str(workspace),
        "project_id": project_id,
        "run_id": run_id,
        "capture_id": published["capture_id"],
        "scene_sha256": published["scene_sha256"],
        "geometry_summary_sha256": published["geometry_summary_sha256"],
        "results_sha256": published["results_sha256"],
        "definition_sha256": published["definition_sha256"],
        "site_context_id": published["site_context_id"],
        "site_context_sha256": published["site_context_sha256"],
        "site_context_image_sha256": published["site_context_image_sha256"],
        "site_context_alignment_status": published["site_context_alignment_status"],
        "site_context_attribution": published["site_context_attribution"],
        "north_status": published["north_status"],
        "plot_status": published["plot_status"],
        "ground_status": published["ground_status"],
        "views": view_report,
    }
    output = ROOT / "docs/view_evidence_verification.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: live baseline controlled view evidence. Evidence: {output}")


if __name__ == "__main__":
    main()
