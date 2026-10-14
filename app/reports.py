"""Printable English run report."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .ai import ADVICE_POLICY_VERSION, build_design_elements


METRIC_LABELS = {
    "bvo_m2": "Gross floor area", "sight_pct": "Visibility",
    "indicative_cost_eur": "Indicative cost", "cost_per_m2": "Cost per m²",
    "complexity_factor": "Complexity factor",
    "pile_count_load": "Load-based pile count", "pile_count_grid": "Grid-based pile count",
    "pile_max_storeys": "Maximum storeys", "pile_safe_spacing_m": "Safe pile spacing",
    "pile_max_utilization_pct": "Maximum pile utilisation", "pile_load_kn_m2": "Foundation load",
    "pile_capacity_kn": "Pile capacity", "pile_spacing_m": "Pile spacing",
    "shadow_mean_hours": "Mean sun hours", "shadow_min_hours": "Minimum sun hours",
    "shadow_max_hours": "Maximum sun hours", "shadow_sunlit_pct": "Sunlit area",
    "utci_mean_c": "Mean UTCI", "utci_max_c": "Maximum UTCI",
    "heat_stress_area_pct": "Heat-stress area", "weather_air_temp_c": "Air temperature",
    "weather_rh_pct": "Relative humidity", "weather_wind_mps": "Wind speed",
}
VIEW_LABELS = {"top": "Top view", "overview": "Overview",
               "facade-side": "Facade-side view", "park-side": "Park-side view"}
VOLUME_COLORS = ("#2f80ed", "#f2994a", "#9b51e0", "#27ae60",
                 "#eb5757", "#56ccf2", "#f2c94c", "#6fcf97")
MAX_REPORT_JSON_BYTES = 20 * 1024 * 1024
MAX_REPORT_SCENE_BYTES = 100 * 1024 * 1024
MAX_REPORT_IMAGE_BYTES = 5 * 1024 * 1024
TEXT_REPLACEMENTS = {
    **{field: label.lower() for field, label in METRIC_LABELS.items()},
    "bvo_m2": "gross floor area", "utci_mean_c": "mean UTCI", "utci_max_c": "maximum UTCI",
}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")


def _number(value: Any, digits: int = 1) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "Not available"
    return f"{value:,.{digits}f}"


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _text(value: Any) -> str:
    result = str(value)
    for source, target in TEXT_REPLACEMENTS.items():
        result = re.sub(rf"`?\b{re.escape(source)}\b`?", target, result, flags=re.IGNORECASE)
    result = re.sub(r"\b([A-Za-z][A-Za-z-]{2,})\s+\1\b", r"\1", result, flags=re.IGNORECASE)
    return result


def _analysis_date(value: Any) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return f"{parsed.day} {MONTHS[parsed.month - 1]} {parsed.year}, {parsed:%H:%M}"
    except (TypeError, ValueError):
        return "unknown date"


def _complete(metrics: dict[str, Any], *fields: str) -> bool:
    return all(isinstance(metrics.get(field), (int, float)) and not isinstance(metrics.get(field), bool)
               for field in fields)


def _screening_results(metrics: dict[str, Any]) -> str:
    rows = []
    if _complete(metrics, "shadow_mean_hours", "shadow_min_hours", "shadow_max_hours", "shadow_sunlit_pct",
                 "utci_mean_c", "utci_max_c", "heat_stress_area_pct", "weather_air_temp_c",
                 "weather_rh_pct", "weather_wind_mps"):
        rows.append(f"""<tr><th>Climate screening</th><td><strong>{_number(metrics.get('shadow_mean_hours'))} h mean sun</strong><span>{_number(metrics.get('shadow_min_hours'))}–{_number(metrics.get('shadow_max_hours'))} h · {_number(metrics.get('shadow_sunlit_pct'))}% sunlit</span></td>
<td><strong>{_number(metrics.get('utci_mean_c'))} °C mean UTCI</strong><span>{_number(metrics.get('utci_max_c'))} °C maximum · {_number(metrics.get('heat_stress_area_pct'))}% heat stress</span></td>
<td><strong>{_number(metrics.get('weather_air_temp_c'))} °C weather input</strong><span>RH {_number(metrics.get('weather_rh_pct'))}% · wind {_number(metrics.get('weather_wind_mps'))} m/s</span></td></tr>""")
    if _complete(metrics, "pile_count_load", "pile_count_grid", "pile_max_storeys", "pile_safe_spacing_m",
                 "pile_max_utilization_pct", "pile_load_kn_m2", "pile_capacity_kn", "pile_spacing_m"):
        rows.append(f"""<tr><th>Foundation screening</th><td><strong>{_number(metrics.get('pile_count_load'), 0)} load-based piles</strong><span>{_number(metrics.get('pile_count_grid'), 0)} on the grid option</span></td>
<td><strong>{_number(metrics.get('pile_max_utilization_pct'))}% maximum use</strong><span>Indicative maximum: {_number(metrics.get('pile_max_storeys'), 0)} storeys</span></td>
<td><strong>{_number(metrics.get('pile_spacing_m'))} m centres</strong><span>Safe {_number(metrics.get('pile_safe_spacing_m'))} m · {_number(metrics.get('pile_load_kn_m2'))} kN/m² · {_number(metrics.get('pile_capacity_kn'), 0)} kN/pile</span></td></tr>""")
    if not rows:
        return ""
    return "<table class='screening'><tbody>" + "".join(rows) + "</tbody></table>"


def _reference_labels(references: Any, elements: Any) -> str:
    object_labels = {item.get("object_id"): item.get("label") for item in elements if isinstance(item, dict)}
    labels = []
    for reference in references if isinstance(references, list) else []:
        if not isinstance(reference, str):
            continue
        kind, _, value = reference.partition(":")
        label = (VIEW_LABELS.get(value) if kind == "view" else
                 METRIC_LABELS.get(value) if kind == "metric" else
                 object_labels.get(value) if kind == "object" else None)
        if label and label not in labels:
            labels.append(label)
    return " · ".join(labels)


def _calculation_items(values: Any) -> str:
    rendered = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict) or not isinstance(value.get("tekst"), str):
            continue
        fields = [METRIC_LABELS.get(field, field) for field in value.get("metric_fields", []) if isinstance(field, str)]
        source = f"<span class='source'>{html.escape(' · '.join(fields))}</span>" if fields else ""
        rendered.append(f"<li><span>{html.escape(_text(value['tekst']))}</span>{source}</li>")
    return "".join(rendered)


def _observation_items(values: Any) -> str:
    rendered = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict) or not isinstance(value.get("tekst"), str):
            continue
        views = [VIEW_LABELS.get(view, view) for view in value.get("view_ids", []) if isinstance(view, str)]
        uncertainty = value.get("onzekerheid")
        note = f"<small>Uncertainty: {html.escape(_text(uncertainty))}</small>" if isinstance(uncertainty, str) else ""
        rendered.append(f"<li><span>{html.escape(_text(value['tekst']))}</span><span class='source'>{html.escape(' · '.join(views))}</span>{note}</li>")
    return "".join(rendered)


def _action_cards(actions: Any, elements: Any) -> str:
    rendered = []
    for action in actions if isinstance(actions, list) else []:
        if not isinstance(action, dict) or not isinstance(action.get("instructie"), str):
            continue
        refs = _reference_labels(action.get("evidence_refs"), elements)
        checks = " · ".join(METRIC_LABELS.get(field, field) for field in action.get("controle_metric_fields", []) if isinstance(field, str))
        rendered.append(f"""<article class='action-card'>
<div class='priority'>Priority {html.escape(str(action.get('prioriteit', '')))}</div>
<h3>{html.escape(_text(action['instructie']))}</h3>
<p><strong>Test:</strong> {html.escape(_text(action.get('testomvang', '')))} <strong>Goal:</strong> {html.escape(_text(action.get('ontwerpdoel', '')))}</p>
<p><strong>Hypothesis:</strong> {html.escape(_text(action.get('verwacht_effect', '')))} <strong>Trade-off:</strong> {html.escape(_text(action.get('afweging', '')))}</p>
<p class='action-footer'><strong>Rerun:</strong> {html.escape(checks)} <span>Evidence: {html.escape(refs)}</span></p></article>""")
    return "".join(rendered)


def _legacy_recommendations(values: Any, elements: Any) -> str:
    rendered = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict) or not isinstance(value.get("tekst"), str):
            continue
        refs = _reference_labels(value.get("evidence_refs"), elements)
        rendered.append(f"<li><span>{html.escape(_text(value['tekst']))}</span><span class='source'>{html.escape(refs)}</span></li>")
    return "".join(rendered)


def _gallery(data_dir: Path, manifest: Any, elements: Any) -> str:
    if not isinstance(manifest, dict):
        return ""
    images = []
    for view in manifest.get("views", []):
        if not isinstance(view, dict) or view.get("id") not in VIEW_LABELS or not isinstance(view.get("path"), str):
            continue
        path = (data_dir / view["path"]).resolve()
        if not path.is_relative_to(data_dir.resolve()) or not path.is_file():
            continue
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        images.append(f"<figure><div class='image-stage'><img src='data:image/png;base64,{encoded}' alt='{VIEW_LABELS[view['id']]}'></div><figcaption>{VIEW_LABELS[view['id']]}</figcaption></figure>")
    if not images:
        return ""
    legend = ""
    if manifest.get("render_style") == "volume-colors-v1" and isinstance(elements, list):
        entries = []
        for index, element in enumerate(elements[:len(VOLUME_COLORS)]):
            if isinstance(element, dict) and isinstance(element.get("label"), str):
                entries.append(f"<span><i style='background:{VOLUME_COLORS[index]}'></i>{html.escape(element['label'])}</span>")
        if entries:
            legend = f"<div class='volume-legend' aria-label='Volume colour legend'>{''.join(entries)}</div>"
    return legend + f"<div class='gallery'>{''.join(images)}</div>"


def _validated_manifest(data_dir: Path, manifest_path: Path, provenance: dict[str, Any]) -> dict[str, Any] | None:
    try:
        if manifest_path.stat().st_size > 2_000_000:
            return None
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            return None
        artifacts = {
            "scene_sha256": (data_dir / "scene.json", MAX_REPORT_SCENE_BYTES),
            "geometry_summary_sha256": (data_dir / "geometry-summary.json", MAX_REPORT_JSON_BYTES),
            "results_sha256": (data_dir / "latest.json", MAX_REPORT_JSON_BYTES),
            "weather_sha256": (data_dir.parent / "weather" / "NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw",
                               MAX_REPORT_JSON_BYTES),
        }
        for field, (path, maximum) in artifacts.items():
            if (not path.is_file() or path.stat().st_size > maximum
                    or manifest.get(field) != _sha256(path) or provenance.get(field) != manifest[field]):
                return None
        views = manifest.get("views")
        if not isinstance(views, list) or len(views) != 4:
            return None
        for view in views:
            if not isinstance(view, dict) or not isinstance(view.get("path"), str):
                return None
            path = (data_dir / view["path"]).resolve()
            if (not path.is_relative_to(data_dir.resolve()) or not path.is_file()
                    or path.stat().st_size > MAX_REPORT_IMAGE_BYTES
                    or path.stat().st_size != view.get("bytes") or _sha256(path) != view.get("image_sha256")):
                return None
        return manifest
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def build_report(project: dict[str, Any], job: dict[str, Any]) -> str:
    metrics = job.get("results") if isinstance(job.get("results"), dict) else {}
    data_dir = Path(job["data_dir"])
    advice_path = data_dir.parent / "ai-advice.json"
    advice = manifest = None
    try:
        if advice_path.stat().st_size <= MAX_REPORT_JSON_BYTES:
            advice = json.loads(advice_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    recommendations = ""
    if isinstance(advice, dict):
        manifest_path = data_dir / "view-evidence.json"
        provenance = advice.get("evidence_provenance") if isinstance(advice.get("evidence_provenance"), dict) else {}
        current_hash = (_sha256(manifest_path) if manifest_path.is_file()
                        and manifest_path.stat().st_size <= 2_000_000 else None)
        grounded = (advice.get("visual_evidence_used") is True or advice.get("model_view_evidence_used") is True) \
            and provenance.get("view_evidence_sha256") == current_hash \
            and advice.get("advice_policy_version") == ADVICE_POLICY_VERSION
        manifest = _validated_manifest(data_dir, manifest_path, provenance) if grounded else None
        grounded = grounded and manifest is not None
        if grounded and advice.get("output_language") == "en":
            elements = advice.get("design_elements") if isinstance(advice.get("design_elements"), list) else []
            if not elements:
                try:
                    geometry = json.loads((data_dir / "geometry-summary.json").read_text(encoding="utf-8-sig"))
                    elements = build_design_elements(geometry.get("objects", []), manifest.get("views", []))
                except (OSError, json.JSONDecodeError, AttributeError):
                    pass
            actions = _action_cards(advice.get("ontwerpacties"), elements)
            if actions:
                action_section = f"<h2>Priority design tests</h2><div class='actions'>{actions}</div>"
            else:
                legacy = _legacy_recommendations(advice.get("aanbevelingen"), elements)
                action_section = f"<h2>Priority design tests</h2><ul class='evidence-list'>{legacy}</ul>"
            limits = "".join(f"<li>{html.escape(_text(item))}</li>" for item in advice.get("beperkingen", []) if isinstance(item, str))
            recommendations = f"""<section class='advice'><div class='section-kicker'>Model-grounded design review</div>
<p class='summary'>{html.escape(_text(advice.get('samenvatting', '')))}</p>{action_section}
<div class='support-grid'><div><h2>Measured findings</h2><ul class='evidence-list'>{_calculation_items(advice.get('berekeningsbewijs'))}</ul></div>
<div><h2>Visual observations</h2><ul class='evidence-list'>{_observation_items(advice.get('visuele_observaties'))}</ul></div></div>
<div class='gallery-section'><h2>Model views used</h2>{_gallery(data_dir, manifest, elements)}</div>
<aside class='limits'><h2>Limitations and method</h2><ul>{limits}<li>No verified plot, access, tunnel, or other infrastructure envelope is available. Horizontal relocation and footprint-expansion advice is therefore withheld.</li><li>Climate screening covers one weather condition; it is not a year-round solar-access or thermal-comfort study.</li><li>Foundation screening is indicative. Not a ground investigation, foundation design, structural verification, or construction design.</li></ul>
<p>AI review using run metrics, labelled geometry, and verified view projections. Images are shown for human review but were not sent to AI. Effects are hypotheses; rerun every tested variant in Grasshopper.</p></aside></section>"""
        elif grounded:
            recommendations = "<section><h2>AI design review</h2><p class='notice'>The saved review uses the previous output language. Generate a new AI review to include it in this English report.</p></section>"
        else:
            recommendations = "<section><h2>AI design review</h2><p class='notice'>The saved AI review is not linked to the current model-view evidence and is therefore omitted.</p></section>"
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><title>ParkHaven report</title>
<style>
:root{{--ink:#173a32;--muted:#63776f;--line:#d9e2dd;--paper:#fff;--wash:#f3f6f2;--accent:#e36d35}}
@page{{size:A4;margin:11mm}}
*{{box-sizing:border-box}}body{{font:15px/1.55 Segoe UI,Arial,sans-serif;color:var(--ink);max-width:1040px;margin:38px auto;padding:0 32px;background:var(--paper)}}
h1{{font-size:42px;line-height:1.05;margin:10px 0 14px}}h2{{font-size:22px;margin:32px 0 14px}}h3{{font-size:18px;line-height:1.3;margin:7px 0 15px}}
.toolbar{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:16px}}button{{padding:9px 14px;border:0;background:var(--ink);color:white;border-radius:3px}}.print-help{{margin-left:auto;margin-right:12px;color:var(--muted);font-size:11px}}
.meta,.source,small,.section-kicker{{color:var(--muted);font-size:12px}}.section-kicker{{font-weight:700;letter-spacing:.09em;text-transform:uppercase;margin-top:40px}}
.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:18px}}.metric{{border:1px solid var(--line);padding:18px;background:var(--wash)}}.metric strong{{display:block;font-size:24px;margin-top:7px}}.metric small{{display:block;margin-top:5px}}.screening{{width:100%;border-collapse:collapse;margin-top:14px;border:1px solid var(--line)}}.screening th,.screening td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}.screening th{{width:19%;background:var(--wash)}}.screening td{{width:27%}}.screening strong,.screening span{{display:block}}.screening span{{color:var(--muted);font-size:12px;margin-top:2px}}
.summary{{font-size:20px;line-height:1.5;max-width:900px}}.actions{{display:grid;gap:14px}}.action-card{{border:1px solid var(--line);border-left:5px solid var(--accent);padding:18px 20px;break-inside:avoid}}
.priority{{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}}.action-card p{{margin:5px 0}}.action-footer{{display:flex;justify-content:space-between;gap:16px;color:var(--muted);font-size:12px}}
.support-grid{{display:grid;grid-template-columns:1fr 1fr;gap:30px}}.evidence-list{{padding-left:20px}}.evidence-list li{{margin:10px 0}}.evidence-list span{{display:block}}.evidence-list small{{margin-top:3px}}
.gallery-section h2,h2{{break-after:avoid}}.volume-legend{{display:flex;flex-wrap:wrap;gap:8px 18px;margin:0 0 10px;font-size:12px;font-weight:700}}.volume-legend span{{display:flex;align-items:center;gap:6px}}.volume-legend i{{display:inline-block;width:14px;height:14px;border:1px solid #173a3266;border-radius:2px}}.gallery{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}figure{{margin:0;border:1px solid var(--line);padding:7px;break-inside:avoid}}.image-stage{{position:relative;overflow:hidden}}figure img{{display:block;width:100%}}figcaption{{font-size:12px;font-weight:700;padding:6px 2px 1px}}
.limits,.notice{{background:#f7f3ed;border:1px solid #eadfce;padding:12px 18px;margin-top:18px}}.limits h2{{margin-top:0}}.limits p{{color:var(--muted);font-size:12px;margin-bottom:0}}p,li{{orphans:3;widows:3}}
@media(max-width:760px){{.metrics,.support-grid,.gallery{{grid-template-columns:1fr}}.screening,.screening tbody,.screening tr,.screening th,.screening td{{display:block;width:100%}}.action-footer{{display:block}}}}
@media print{{button,.print-help{{display:none}}body{{margin:0;max-width:none;padding:0;font-size:9.5pt;line-height:1.3}}h1{{font-size:25pt}}h2{{font-size:14pt;margin:12px 0 6px}}h3{{font-size:11pt;margin:2px 0 4px}}.section-kicker{{margin-top:18px}}.summary{{font-size:13pt;line-height:1.3;margin:5px 0 10px}}.metrics{{grid-template-columns:repeat(3,1fr);gap:7px}}.metric{{padding:7px}}.screening{{margin-top:8px}}.screening th,.screening td{{padding:5px 7px}}.screening span{{font-size:8pt}}.support-grid,.gallery{{grid-template-columns:1fr 1fr}}.actions{{gap:7px}}.action-card{{padding:6px 9px}}.action-card p{{margin:3px 0}}.action-footer{{font-size:8pt}}.gallery{{gap:6px}}figure{{padding:4px}}figure img{{max-height:50mm;object-fit:contain}}.action-card,figure{{break-inside:avoid}}.limits{{break-inside:auto}}}}
</style></head><body>
<div class='toolbar'><strong>ParkHaven design review</strong><span class='print-help'>The desktop app exports a clean A4 PDF.</span><button id='save-pdf' onclick='savePdf()'>Save as PDF</button></div>
<header><h1>{html.escape(project['name'])}</h1><p class='meta'>Analysis from {_analysis_date(job.get('created_at'))} · {html.escape({'completed': 'Completed', 'failed': 'Failed', 'running': 'Running'}.get(job.get('status'), 'Unknown'))}</p></header>
<section><h2>Current performance</h2><div class='metrics'><div class='metric'>Gross floor area<strong>{_number(metrics.get('bvo_m2'))} m²</strong></div><div class='metric'>Visibility<strong>{_number(metrics.get('sight_pct'))}%</strong></div><div class='metric'>Indicative cost<strong>€ {_number(metrics.get('indicative_cost_eur'), 0)}</strong></div></div><p class='meta'>Taken directly from the run-local Grasshopper export. Costs are indicative.</p>{_screening_results(metrics)}</section>
{recommendations}<script>function savePdf(){{if(window.chrome&&window.chrome.webview){{window.chrome.webview.postMessage({{type:'parkhaven.savePdf'}});}}else{{window.print();}}}}</script></body></html>"""
