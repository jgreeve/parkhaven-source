"""Live isolated imported-model acceptance with preparation timings and source hashes."""

import argparse
import ctypes
from ctypes import wintypes
import json
import math
from pathlib import Path
import sys
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.projects import _sha256, create_project, update_placement
from app.workflow import _processes, launch_run, load_run, prepare_run


def window_snapshot(pid):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    windows = []

    @callback
    def visit(window, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
        if owner.value == pid:
            title = ctypes.create_unicode_buffer(1024)
            user32.GetWindowTextW(window, title, len(title))
            if title.value:
                windows.append(title.value)
        return True

    user32.EnumWindows(visit, 0)
    return windows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--model-units", choices=["file", "meters", "millimeters", "centimeters"], default="file")
    parser.add_argument("--expected-bvo", type=float)
    parser.add_argument("--expected-sight", type=float)
    parser.add_argument("--x", type=float, default=0)
    parser.add_argument("--y", type=float, default=0)
    parser.add_argument("--z", type=float, default=0)
    parser.add_argument("--rotation", type=float, default=0)
    parser.add_argument("--stack-tool", type=Path, help="Optional dotnet-stack executable for failed-run diagnostics")
    args = parser.parse_args()
    analyzer = ROOT.parent / "ParkHaven_Analyzer_App_v0.2"
    protected = [args.source.resolve()] + [analyzer / name for name in (
        "ParkHaven_MVP.3dm", "ParkHaven_MVP.ghx", "data/latest.json", "data/scene.json")]
    hashes = {str(path): _sha256(path) for path in protected}
    workspace = Path(tempfile.mkdtemp(prefix="parkhaven-import-", dir=Path(tempfile.gettempdir()) / "opencode"))
    project = create_project(workspace, args.source, "Imported-model acceptance")
    project_id = project["project_id"]
    update_placement(workspace, project_id, x=args.x, y=args.y, z=args.z, rotation_z_degrees=args.rotation,
                     approved=True, model_units=args.model_units)
    job = prepare_run(workspace, project_id, analyzer, ROOT / "app/rhino/run_analysis.py")
    report = {"workspace": str(workspace), "passed": False, "observed_progress": []}
    process = None
    started = time.monotonic()
    try:
        job = launch_run(workspace, project_id, job["run_id"], Path(r"C:\Program Files\Rhino 8\System\Rhino.exe"))
        process = _processes[job["run_id"]]
        previous = None
        while time.monotonic() - started < args.timeout:
            job = load_run(workspace, project_id, job["run_id"])
            progress = (job["status"], job.get("progress_step"), job.get("progress_detail"))
            if progress != previous:
                print(progress, flush=True)
                report["observed_progress"].append({"elapsed_seconds": round(time.monotonic() - started, 2),
                                                    "status": progress[0], "step": progress[1], "detail": progress[2]})
                previous = progress
            if job["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.5)
        assert job["status"] == "completed", job.get("error") or f"Timed out at {job.get('progress_detail')}"
        assert job.get("results") and job["scene_available"], "Missing calculation evidence"
        report["metric_checks"] = {}
        for key, expected in (("bvo_m2", args.expected_bvo), ("sight_pct", args.expected_sight)):
            if expected is not None:
                assert math.isclose(job["results"][key], expected, rel_tol=1e-6, abs_tol=1e-4), (key, job["results"][key], expected)
                report["metric_checks"][key] = True
        results = job["results"]
        assert math.isclose(results["indicative_cost_eur"], results["bvo_m2"] * results["cost_per_m2"] * results["complexity_factor"], rel_tol=1e-9)
        report["metric_checks"]["cost_follows_bvo"] = True
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        if process is not None:
            report["rhino_windows"] = window_snapshot(process.pid)
            if args.stack_tool and process.poll() is None:
                try:
                    stack = subprocess.run([str(args.stack_tool), "report", "--process-id", str(process.pid)],
                                           capture_output=True, text=True, timeout=20)
                    report["managed_stack"] = stack.stdout.splitlines()
                    report["stack_error"] = stack.stderr
                except subprocess.TimeoutExpired:
                    report["stack_error"] = "Stack capture timed out"
        raise
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        report["job"] = load_run(workspace, project_id, job["run_id"])
        error_log = Path(job["data_dir"]).parent / "runner-error.log"
        if error_log.is_file():
            report["runner_errors"] = error_log.read_text(encoding="utf-8").splitlines()
        preserved = all(_sha256(Path(path)) == digest for path, digest in hashes.items())
        preserved = preserved and all(_sha256(path) == project["source"]["sha256"] for path in (
            workspace / project_id / "source/original-design.3dm",
            workspace / project_id / "working/parkhaven-design.3dm", Path(job["working_model"])))
        report["source_working_run_and_analyzer_preserved"] = preserved
        report["protected_sha256"] = hashes
        report["passed"] = report["passed"] and preserved
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Evidence: {args.output}", flush=True)
        assert preserved, "Protected input changed"


if __name__ == "__main__":
    main()
