"""Printable Dutch run report."""

from __future__ import annotations

import html
import hashlib
import json
from pathlib import Path
from typing import Any


def _number(value: Any, digits: int = 1) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "Niet beschikbaar"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _items(values: Any, *, references: str | None = None) -> str:
    rendered = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict) or not isinstance(value.get("tekst"), str):
            continue
        suffix = ""
        refs = value.get(references) if references else None
        if isinstance(refs, list) and all(isinstance(item, str) for item in refs):
            suffix = f" <small>[{html.escape(', '.join(refs))}]</small>"
        rendered.append(f"<li>{html.escape(value['tekst'])}{suffix}</li>")
    return "".join(rendered)


def build_report(project: dict[str, Any], job: dict[str, Any]) -> str:
    metrics = job.get("results") if isinstance(job.get("results"), dict) else {}
    advice_path = Path(job["data_dir"]).parent / "ai-advice.json"
    advice = None
    try:
        advice = json.loads(advice_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    recommendations = ""
    if advice:
        manifest_path = Path(job["data_dir"]) / "view-evidence.json"
        provenance = advice.get("evidence_provenance") if isinstance(advice.get("evidence_provenance"), dict) else {}
        current_hash = _sha256(manifest_path) if manifest_path.is_file() else None
        grounded = advice.get("visual_evidence_used") is True and provenance.get("view_evidence_sha256") == current_hash
        if grounded:
            calculations = _items(advice.get("berekeningsbewijs"), references="metric_fields")
            observations = _items(advice.get("visuele_observaties"), references="view_ids")
            proposals = _items(advice.get("aanbevelingen"), references="evidence_refs")
            limits = "".join(f"<li>{html.escape(item)}</li>" for item in advice.get("beperkingen", []) if isinstance(item, str))
            recommendations = f"""<section><h2>Model-grounded AI-advies</h2><p>{html.escape(advice.get('samenvatting', ''))}</p>
<h3>Berekeningsbewijs</h3><ul>{calculations}</ul><h3>Visuele observaties</h3><ul>{observations}</ul>
<h3>Aanbevelingen</h3><ul>{proposals}</ul><h3>Beperkingen</h3><ul>{limits}</ul>
<p class='note'>Model: {html.escape(advice.get('model', 'onbekend'))}. Gebaseerd op dezelfde runmetrics en vier gecontroleerde modelbeelden; AI-inferentie, geen berekeningsresultaat.</p></section>"""
        else:
            recommendations = "<section><h2>AI-advies</h2><p class='note'>Opgeslagen AI-advies is niet gekoppeld aan het huidige modelbeeldbewijs en wordt daarom niet getoond.</p></section>"
    return f"""<!doctype html><html lang='nl'><head><meta charset='utf-8'><title>ParkHaven rapport</title>
<style>body{{font:15px Segoe UI,Arial;color:#193a32;max-width:900px;margin:45px auto;padding:0 30px}}h1{{font-size:44px}}h2{{margin-top:38px}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.metric{{border:1px solid #ccd8d1;padding:20px}}.metric strong{{display:block;font-size:25px;margin-top:8px}}.note{{color:#687b74;font-size:12px}}button{{padding:10px 15px}}@media print{{button{{display:none}}body{{margin:0}}}}</style></head><body>
<button onclick='window.print()'>Opslaan als PDF</button><p>ParkHaven ontwerpbeoordeling</p><h1>{html.escape(project['name'])}</h1>
<p>Analyse: {html.escape(job['run_id'])}<br>Status: {html.escape(job['status'])}<br>Datum: {html.escape(job['created_at'])}</p>
<section><h2>Grasshopper-resultaten</h2><div class='metrics'><div class='metric'>BVO<strong>{_number(metrics.get('bvo_m2'))} m2</strong></div><div class='metric'>Zicht<strong>{_number(metrics.get('sight_pct'))}%</strong></div><div class='metric'>Indicatieve kosten<strong>EUR {_number(metrics.get('indicative_cost_eur'), 0)}</strong></div></div><p class='note'>Deze waarden zijn rechtstreeks uit de run-lokale Grasshopper-export gelezen. Kosten zijn indicatief.</p></section>
{recommendations}<section><h2>Grenzen</h2><p>Groenvoorstel, hittebestendigheidsproxy en conceptuele AI-render zijn nog niet in deze run aanwezig en worden daarom niet als resultaat getoond.</p></section>
</body></html>"""
