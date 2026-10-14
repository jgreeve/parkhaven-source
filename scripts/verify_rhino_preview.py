"""Live placement-preview acceptance; launches and terminates only its own Rhino."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.projects import _sha256, create_project, update_placement
from app.workflow import _processes, launch_run, load_run, prepare_preview


def complete_preview(workspace, project_id, job, timeout):
    job = launch_run(workspace, project_id, job["run_id"], Path(r"C:\Program Files\Rhino 8\System\Rhino.exe"))
    process = _processes[job["run_id"]]
    try:
        started = time.monotonic()
        previous = None
        while time.monotonic() - started < timeout:
            job = load_run(workspace, project_id, job["run_id"])
            if job["status"] != previous:
                print(job["status"], flush=True)
                previous = job["status"]
            if job["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(1)
        return job
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT.parent / "test-ui-dora.3dm")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/rhino_preview_verification.json")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--analyzer-root", type=Path, default=ROOT.parent / "ParkHaven_Analyzer_App_v0.2")
    parser.add_argument("--expected-plugin", type=Path)
    args = parser.parse_args()
    analyzer = args.analyzer_root.resolve()
    protected = [args.source, analyzer / "ParkHaven_MVP.3dm", analyzer / "ParkHaven_MVP.ghx"]
    hashes = {str(path): _sha256(path) for path in protected}
    temp_root = Path(tempfile.gettempdir()) / "opencode"
    temp_root.mkdir(exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="parkhaven-preview-", dir=temp_root))
    project = create_project(workspace, args.source, "Rhino placement-preview acceptance")
    project_id = project["project_id"]
    update_placement(workspace, project_id, x=12.5, y=-3, z=2, rotation_z_degrees=30,
                     approved=False, model_units="meters")
    job = prepare_preview(workspace, project_id, analyzer)
    report = {"workspace": str(workspace), "job_file": str(Path(job["data_dir"]).parent / "job.json"),
              "checks": {}, "passed": False}
    completed_jobs = []
    try:
        job = complete_preview(workspace, project_id, job, args.timeout)
        completed_jobs.append(job)
        report["job"] = job
        assert job["status"] == "completed", job.get("error") or "Rhino preview timed out"
        if args.expected_plugin:
            assert Path(job["plugin_path"]).resolve() == args.expected_plugin.resolve()
            report["checks"]["expected_registered_plugin_used"] = True
        assert job["job_type"] == "placement_preview" and job["placement"]["approved"] is False
        assert "definition" not in job and "results" not in job
        assert "load_grasshopper" not in job.get("step_seconds", {})
        assert not (Path(job["data_dir"]) / "latest.json").exists()
        report["checks"]["completed_without_approval_or_grasshopper"] = True

        scene = json.loads((Path(job["data_dir"]) / "scene.json").read_text(encoding="utf-8"))
        assert scene["kind"] == "placement_preview" and scene["units"] == "meters" and scene["up_axis"] == "Z"
        layers = {layer["name"]: layer for layer in scene["layers"]}
        assert set(layers) == {"PH_DESIGN", "PH_VISUAL_ONLY", "PH_FACADES", "PH_TARGET", "REFERENCE_CONTEXT"}
        assert len(layers["PH_DESIGN"]["triangles"]) > 0
        assert len(layers["PH_VISUAL_ONLY"]["triangles"]) > 0
        assert job["model_summary"]["visual_only_objects"] == 2
        report["checks"]["design_visual_and_reference_layers_exported"] = True

        summary_path = Path(job["data_dir"]) / "geometry-summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        objects = summary["objects"]
        ids = [item["id"] for item in objects]
        assert summary["id_strategy"] == "source-rhino-object-uuid-v1"
        assert summary["project_id"] == project_id and summary["run_id"] == job["run_id"]
        assert summary["total_objects"] == summary["included_objects"] == 233 and summary["omitted_objects"] == 0
        assert len(ids) == len(set(ids)) and all(item.startswith("source:") for item in ids)
        assert sum(item["classification"] == "analysis_volume" for item in objects) == 231
        assert sum(item["classification"] == "visual_only" for item in objects) == 2
        assert all(len(item["bounds_m"]["min"]) == 3 and len(item["dimensions_m"]) == 3 for item in objects)
        assert _sha256(summary_path) == job["geometry_summary"]["sha256"]
        assert len(layers["PH_DESIGN"]["objects"]) == 231 and len(layers["PH_VISUAL_ONLY"]["objects"]) == 2
        report["checks"]["stable_ids_bounds_and_mesh_ranges_exported"] = True

        repeat = complete_preview(workspace, project_id, prepare_preview(workspace, project_id, analyzer), args.timeout)
        completed_jobs.append(repeat)
        repeat_summary_path = Path(repeat["data_dir"]) / "geometry-summary.json"
        repeat_summary = json.loads(repeat_summary_path.read_text(encoding="utf-8"))
        assert repeat_summary["objects"] == objects
        assert repeat_summary["objects_sha256"] == summary["objects_sha256"]
        assert repeat["geometry_summary"]["objects_sha256"] == job["geometry_summary"]["objects_sha256"]
        assert repeat["geometry_summary"]["sha256"] != job["geometry_summary"]["sha256"]
        report["checks"]["object_ids_and_summary_stable_across_repeated_preview"] = True
        report["stable_objects_sha256"] = repeat["geometry_summary"]["objects_sha256"]

        report["scene"] = {name: {"vertices": len(layer["vertices"]) // 3,
                                   "triangles": len(layer["triangles"]) // 3}
                           for name, layer in layers.items()}
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        project_dir = workspace / project_id
        preserved = all(_sha256(Path(path)) == digest for path, digest in hashes.items())
        preserved = preserved and all(_sha256(path) == project["source"]["sha256"] for path in (
            project_dir / "source/original-design.3dm",
            project_dir / "working/parkhaven-design.3dm",
            *(Path(item["working_model"]) for item in completed_jobs),
        ))
        report["checks"]["source_working_preview_and_analyzer_preserved"] = preserved
        report["passed"] = report["passed"] and preserved
        report["protected_sha256"] = hashes
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Evidence: {args.output}", flush=True)
        assert preserved, "Protected input or reference data changed"


if __name__ == "__main__":
    main()
