"""Live known-size metre/mm/mislabeled-mm comparison; optional rhino3dm dependency."""

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

import rhino3dm

ROOT = Path(__file__).resolve().parents[1]


def scene_bounds(path):
    scene = json.loads(path.read_text(encoding="utf-8-sig"))
    assert scene["units"] == "meters"
    return {layer["name"]: [min(layer["vertices"][axis::3]) for axis in range(3)] +
                          [max(layer["vertices"][axis::3]) for axis in range(3)]
            for layer in scene["layers"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/rhino_unit_equivalence.json")
    args = parser.parse_args()
    workspace = Path(tempfile.mkdtemp(prefix="parkhaven-units-", dir=Path(tempfile.gettempdir()) / "opencode"))
    evidence = {"workspace": str(workspace), "passed": False, "cases": {}}
    try:
        # All three express the same 10 x 20 x 9 metre mass, with the same
        # physical tolerance. At a 3 m floor height its BVO is exactly 600 m2.
        for name, declared, coordinate_factor, interpretation in (
            ("meters", rhino3dm.UnitSystem.Meters, 1, "file"),
            ("millimeters", rhino3dm.UnitSystem.Millimeters, 1000, "file"),
            ("mislabeled_mm", rhino3dm.UnitSystem.Millimeters, 1, "meters"),
        ):
            source = workspace / (name + ".3dm")
            model = rhino3dm.File3dm()
            model.Settings.ModelUnitSystem = declared
            model.Settings.ModelAbsoluteTolerance = 0.001 * coordinate_factor
            layer = rhino3dm.Layer()
            layer.Name = "Design"
            attributes = rhino3dm.ObjectAttributes()
            attributes.LayerIndex = model.Layers.Add(layer)
            box = rhino3dm.BoundingBox(0, 0, 0, 10 * coordinate_factor, 20 * coordinate_factor, 9 * coordinate_factor)
            model.Objects.AddBrep(rhino3dm.Brep.CreateFromBox(rhino3dm.Box(box)), attributes)
            assert model.Write(str(source), 8)
            report = workspace / (name + ".json")
            subprocess.run([sys.executable, str(ROOT / "scripts/verify_rhino_import.py"), str(source),
                            "--model-units", interpretation, "--expected-bvo", "600", "--x", "12.5",
                            "--y", "-3", "--z", "2", "--rotation", "30", "--output", str(report)], check=True)
            result = json.loads(report.read_text(encoding="utf-8"))
            job = result["job"]
            assert result["passed"] and result["source_working_run_and_analyzer_preserved"]
            evidence["cases"][name] = {"report": str(report), "results": job["results"],
                                        "model_units": job["model_units"],
                                        "scene_bounds_m": scene_bounds(Path(job["data_dir"]) / "scene.json")}
        reference = evidence["cases"]["meters"]
        for name, case in evidence["cases"].items():
            for key in ("bvo_m2", "sight_pct", "indicative_cost_eur"):
                assert math.isclose(case["results"][key], reference["results"][key], rel_tol=1e-6, abs_tol=1e-4), (name, key)
            for layer, bounds in reference["scene_bounds_m"].items():
                assert all(math.isclose(a, b, abs_tol=1e-4) for a, b in zip(bounds, case["scene_bounds_m"][layer])), (name, layer)
        assert evidence["cases"]["millimeters"]["model_units"]["coordinate_scale"] == 1
        assert evidence["cases"]["mislabeled_mm"]["model_units"]["coordinate_scale"] == 1000
        evidence["passed"] = True
    finally:
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("PASS: metre, true-mm and corrected-mm models agree on BVO, sight, cost and placed scene bounds.")


if __name__ == "__main__":
    main()
