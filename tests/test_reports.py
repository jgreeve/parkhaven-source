import hashlib
import json

from app.reports import build_report


def test_report_renders_only_current_evidence_grounded_advice(tmp_path):
    run_dir = tmp_path / "run"
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True)
    artifacts = {
        "scene_sha256": (data_dir / "scene.json", b'{"scene":true}'),
        "geometry_summary_sha256": (data_dir / "geometry-summary.json", b'{"objects":[]}'),
        "results_sha256": (data_dir / "latest.json", b'{"bvo_m2":1000}'),
        "weather_sha256": (run_dir / "weather" / "NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw", b"weather"),
    }
    for path, content in artifacts.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    views = []
    for view_id in ("top", "overview", "facade-side", "park-side"):
        image = (view_id + "-png").encode()
        (data_dir / f"{view_id}.png").write_bytes(image)
        views.append({"id": view_id, "path": f"{view_id}.png", "bytes": len(image),
                      "image_sha256": hashlib.sha256(image).hexdigest()})
    manifest_value = {"capture_id": "current", "render_style": "volume-colors-v1", "views": views}
    for field, (_, content) in artifacts.items():
        manifest_value[field] = hashlib.sha256(content).hexdigest()
    manifest = (json.dumps(manifest_value) + "\n").encode()
    (data_dir / "view-evidence.json").write_bytes(manifest)
    provenance = {"view_evidence_sha256": hashlib.sha256(manifest).hexdigest()}
    provenance.update({field: digest for field, digest in manifest_value.items() if field.endswith("_sha256")})
    advice = {
        "samenvatting": "The sight_pct result defines the main visibility constraint.", "model": "vision-model",
        "visual_evidence_used": False, "model_view_evidence_used": True, "output_language": "en",
        "advice_policy_version": "site-constraints-v2",
        "evidence_provenance": provenance,
        "design_elements": [
            {"element_id": "volume-a", "label": "Volume A", "object_id": "source:one"},
            {"element_id": "volume-b", "label": "Volume B", "object_id": "source:two"},
            {"element_id": "volume-c", "label": "Volume C", "object_id": "source:three"},
        ],
        "berekeningsbewijs": [{"tekst": "Grasshopper reports the gross floor area.", "metric_fields": ["bvo_m2"]}],
        "visuele_observaties": [{"tekst": "The mass is visible.", "view_ids": ["overview"],
                                    "onzekerheid": "Visual evidence only."}],
        "ontwerpacties": [{"prioriteit": 1, "instructie": "Widen Volume A to the right.",
                             "testomvang": "Test 5-10% additional width.", "ontwerpdoel": "Improve cohesion.",
                             "verwacht_effect": "This may strengthen the cluster.", "afweging": "Less space between volumes.",
                             "controle_metric_fields": ["bvo_m2"],
                             "evidence_refs": ["view:park-side", "object:source:one"]}],
        "beperkingen": ["Orientation is not verified."],
    }
    (run_dir / "ai-advice.json").write_text(json.dumps(advice), encoding="utf-8")
    job = {"data_dir": str(data_dir), "results": {
        "bvo_m2": 1000, "shadow_mean_hours": 4.5, "shadow_min_hours": 1.2,
        "shadow_max_hours": 7.8, "shadow_sunlit_pct": 62, "utci_mean_c": 27.4,
        "utci_max_c": 35.1, "heat_stress_area_pct": 18, "weather_air_temp_c": 25,
        "weather_rh_pct": 55, "weather_wind_mps": 2.5, "pile_count_load": 42,
        "pile_count_grid": 48, "pile_max_storeys": 8, "pile_safe_spacing_m": 3.2,
        "pile_max_utilization_pct": 86, "pile_load_kn_m2": 12, "pile_capacity_kn": 900,
        "pile_spacing_m": 3.5,
    }, "run_id": "run-1",
           "status": "completed", "created_at": "2026-10-02T00:00:00Z"}
    report = build_report({"name": "Test"}, job)
    assert "Model-grounded design review" in report
    assert "The visibility result defines the main visibility constraint." in report
    assert "Widen Volume A to the right." in report
    assert "Park-side view · Volume A" in report and "Orientation is not verified." in report
    assert "view:park-side" not in report and "source:one" not in report
    assert "1,000.0 m²" in report
    assert "Climate screening" in report and "4.5 h mean sun" in report and "27.4 °C" in report
    assert "one weather condition" in report and "not a year-round solar-access or thermal-comfort study" in report
    assert "Foundation screening" in report and "42" in report and "86.0%" in report
    assert "Not a ground investigation, foundation design, structural verification, or construction design" in report
    assert "No verified plot, access, tunnel, or other infrastructure envelope is available" in report
    assert "exploratory test and requires site verification" in report
    assert "Analysis from 2 October 2026, 00:00 · Completed" in report
    assert "Images are shown for human review but were not sent to AI" in report
    assert "run-1" not in report and "sight_pct" not in report
    assert "Volume colour legend" in report
    assert "background:#2f80ed" in report and "background:#f2994a" in report and "background:#9b51e0" in report
    assert "volume-marker" not in report and "volume-label" not in report
    assert "@page{size:A4;margin:11mm}" in report
    assert "@media print" in report and "grid-template-columns:repeat(3,1fr)" in report
    assert "parkhaven.savePdf" in report and "window.print()" in report
    assert ".gallery-section,.limits{break-inside:avoid}" not in report

    overview_path = data_dir / "overview.png"
    overview_image = overview_path.read_bytes()
    overview_path.write_bytes(overview_image + b"changed")
    stale_report = build_report({"name": "Test"}, job)
    assert "Widen Volume A to the right." not in stale_report
    overview_path.write_bytes(overview_image)

    results_path = data_dir / "latest.json"
    results_image = results_path.read_bytes()
    results_path.write_bytes(results_image + b"changed")
    stale_report = build_report({"name": "Test"}, job)
    assert "Widen Volume A to the right." not in stale_report
    assert "not linked to the current model-view evidence" in stale_report
    results_path.write_bytes(results_image)

    advice.pop("advice_policy_version")
    (run_dir / "ai-advice.json").write_text(json.dumps(advice), encoding="utf-8")
    old_policy_report = build_report({"name": "Test"}, job)
    assert "Widen Volume A to the right." not in old_policy_report
    assert "not linked to the current model-view evidence" in old_policy_report


def test_report_keeps_legacy_results_compact(tmp_path):
    data_dir = tmp_path / "run" / "data"
    data_dir.mkdir(parents=True)
    report = build_report({"name": "Oude run"}, {
        "data_dir": str(data_dir), "results": {"bvo_m2": 500, "sight_pct": 40},
        "status": "completed", "created_at": "2026-01-01T00:00:00Z",
    })
    assert "500.0 m²" in report
    assert "Climate screening" not in report and "Foundation screening" not in report
