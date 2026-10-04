import hashlib
import json

from app.reports import build_report


def test_report_renders_only_current_evidence_grounded_advice(tmp_path):
    run_dir = tmp_path / "run"
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True)
    manifest = b'{"capture_id":"current"}\n'
    (data_dir / "view-evidence.json").write_bytes(manifest)
    advice = {
        "samenvatting": "Zicht & massa.", "model": "vision-model", "visual_evidence_used": True,
        "evidence_provenance": {"view_evidence_sha256": hashlib.sha256(manifest).hexdigest()},
        "berekeningsbewijs": [{"tekst": "BVO uit Grasshopper.", "metric_fields": ["bvo_m2"]}],
        "visuele_observaties": [{"tekst": "Massa zichtbaar.", "view_ids": ["overview"]}],
        "aanbevelingen": [{"tekst": "Onderzoek parkzijde.", "evidence_refs": ["view:park-side"]}],
        "beperkingen": ["Noord niet geverifieerd."],
    }
    (run_dir / "ai-advice.json").write_text(json.dumps(advice), encoding="utf-8")
    job = {"data_dir": str(data_dir), "results": {"bvo_m2": 1000}, "run_id": "run-1",
           "status": "completed", "created_at": "2026-10-02T00:00:00Z"}
    report = build_report({"name": "Test"}, job)
    assert "Model-grounded AI-advies" in report
    assert "Zicht &amp; massa." in report
    assert "view:park-side" in report and "Noord niet geverifieerd." in report

    (data_dir / "view-evidence.json").write_bytes(b'{"capture_id":"changed"}\n')
    stale_report = build_report({"name": "Test"}, job)
    assert "Onderzoek parkzijde." not in stale_report
    assert "niet gekoppeld aan het huidige modelbeeldbewijs" in stale_report
