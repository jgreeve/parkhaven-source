"""Explicit live acceptance test; launches and terminates only its own Rhino."""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.projects import _sha256, create_project, update_placement
from app.workflow import _processes, launch_run, load_run, prepare_run


def scene_summary(scene):
    result = {}
    for layer in scene["layers"]:
        vertices = layer["vertices"]
        result[layer["name"]] = {
            "vertices": len(vertices) // 3,
            "triangles": len(layer["triangles"]) // 3,
            "bounds": [min(vertices[i::3]) for i in range(3)] + [max(vertices[i::3]) for i in range(3)],
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/rhino_plugin_verification.json")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    analyzer = ROOT.parent / "ParkHaven_Analyzer_App_v0.2"
    protected = [analyzer / name for name in ("ParkHaven_MVP.3dm", "ParkHaven_MVP.ghx", "ParkHaven_MVP.gh", "data/latest.json", "data/scene.json")]
    hashes = {str(path): _sha256(path) for path in protected}
    workspace = Path(tempfile.mkdtemp(prefix="parkhaven-plugin-", dir=Path(tempfile.gettempdir()) / "opencode"))
    project = create_project(workspace, analyzer / "ParkHaven_MVP.3dm", "Rhino plug-in baseline acceptance")
    project_id = project["project_id"]
    update_placement(workspace, project_id, x=0, y=0, z=0, rotation_z_degrees=0, approved=True)
    job = prepare_run(workspace, project_id, analyzer, ROOT / "app/rhino/run_analysis.py")
    report = {"workspace": str(workspace), "job_file": str(Path(job["data_dir"]).parent / "job.json"), "checks": {}, "passed": False}
    process = None
    try:
        job = launch_run(workspace, project_id, job["run_id"], Path(r"C:\Program Files\Rhino 8\System\Rhino.exe"))
        process = _processes[job["run_id"]]
        started = time.monotonic()
        previous = None
        while time.monotonic() - started < args.timeout:
            job = load_run(workspace, project_id, job["run_id"])
            if job["status"] != previous:
                print(job["status"], flush=True)
                previous = job["status"]
            if job["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(1)
        report["job"] = job
        assert job["status"] == "completed", job.get("error") or "Rhino startup/solve timed out"
        report["checks"]["automatic_startup_and_solve"] = True
        assert job["model_summary"]["design_objects"] == 4, job["model_summary"]
        report["checks"]["four_design_masses"] = True
        geometry_summary_path = Path(job["data_dir"]) / "geometry-summary.json"
        geometry_summary = json.loads(geometry_summary_path.read_text(encoding="utf-8"))
        object_ids = [item["id"] for item in geometry_summary["objects"]]
        assert geometry_summary["job_type"] == "analysis"
        assert geometry_summary["project_id"] == project_id and geometry_summary["run_id"] == job["run_id"]
        assert geometry_summary["total_objects"] == geometry_summary["included_objects"] == 4
        assert geometry_summary["omitted_objects"] == 0 and len(object_ids) == len(set(object_ids))
        assert all(item["classification"] == "analysis_volume" for item in geometry_summary["objects"])
        assert _sha256(geometry_summary_path) == job["geometry_summary"]["sha256"]
        assert geometry_summary["objects_sha256"] == job["geometry_summary"]["objects_sha256"]
        report["checks"]["stable_geometry_summary"] = True
        expected = {"bvo_m2": 17024.070833234422, "sight_pct": 65.12, "indicative_cost_eur": 30643327.49982196}
        for key, value in expected.items():
            assert math.isclose(job["results"][key], value, rel_tol=1e-9, abs_tol=1e-6), (key, job["results"][key], value)
            report["checks"][key] = True
        actual_scene = json.loads((Path(job["data_dir"]) / "scene.json").read_text(encoding="utf-8-sig"))
        baseline_scene = json.loads((analyzer / "data/scene.json").read_text(encoding="utf-8-sig"))
        design_layer = next(layer for layer in actual_scene["layers"] if layer["name"] == "PH_DESIGN")
        color_values = design_layer.get("vertex_colors", [])
        assert actual_scene.get("design_render_style") == "volume-colors-v1"
        assert len(color_values) == len(design_layer["vertices"])
        assert len({tuple(color_values[index:index + 3]) for index in range(0, len(color_values), 3)}) >= 3
        report["checks"]["stable_volume_colors"] = True
        actual, baseline = scene_summary(actual_scene), scene_summary(baseline_scene)
        report["scene"] = actual
        assert actual.keys() == baseline.keys()
        for name, expected_layer in baseline.items():
            assert actual[name]["vertices"] == expected_layer["vertices"], name
            assert actual[name]["triangles"] == expected_layer["triangles"], name
            assert all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(actual[name]["bounds"], expected_layer["bounds"])), name
        report["checks"]["scene_layer_mesh_counts_and_bounds"] = True
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        preserved = all(_sha256(Path(path)) == digest for path, digest in hashes.items())
        project_dir = workspace / project_id
        preserved = preserved and all(_sha256(path) == project["source"]["sha256"] for path in [
            project_dir / "source/original-design.3dm", project_dir / "working/parkhaven-design.3dm", Path(job["working_model"]),
        ])
        report["checks"]["source_working_run_and_analyzer_preserved"] = preserved
        report["passed"] = report["passed"] and preserved
        report["protected_sha256"] = hashes
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Evidence: {args.output}", flush=True)
        assert preserved, "Protected input or baseline data changed"


if __name__ == "__main__":
    main()
