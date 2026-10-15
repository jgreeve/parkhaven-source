"""Ephemeral model-grounded OpenAI-compatible review client."""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from .ai_tls import EndpointTrustError, open_ai_request
from .site_context import SiteContextError, load_site_context
from .view_evidence import MAX_IMAGE_BYTES, MAX_TOTAL_BYTES, VIEW_IDS


class AiError(ValueError):
    pass


AI_TIMEOUT_SECONDS = 120
MAX_PROVIDER_RESPONSE_BYTES = 2_000_000
MAX_EVIDENCE_JSON_BYTES = 20_000_000
ADVICE_POLICY_VERSION = "site-constraints-v2"
SYSTEM_PROMPT = """/no_think
Return one JSON object matching response_schema. No Markdown, reasoning, or preamble.
Write concise English and use only supplied IDs and evidence.

Rules:
- Grasshopper values are authoritative: quote, never recalculate or infer causation.
- Labelled dimensions and view projections support relative spatial observations only;
  they do not prove appearance, quantities, orientation, plot, ground, or performance.
- Treat site_constraints as evidence limits. Horizontal moves may be proposed when
  horizontal_moves_allowed is true, but describe them as exploratory sensitivity tests.
  Never claim clearance from tunnels, plots, access routes, or other infrastructure when
  transport_infrastructure is unavailable; state that site verification is still required.
- Never expose raw IDs, schema keys, or layer names in prose.
- Use view-relative directions unless evidence explicitly verifies another meaning.
- Do not invent dimensions. Prefer a 5-10% sensitivity range; metres are allowed only
  when the exact dimension is supplied. A test range is not an optimum.
- Give one summary sentence, 1-3 measured findings, 1-2 spatial observations, exactly
  three different prioritised design tests, and 1-2 material limitations.
- Each design test names one labelled volume, an allowed operation, a view-relative
  direction, a 5-10% range, a clear objective, a may/might/could effect, one trade-off,
  rerun metrics, and evidence references. Effects are hypotheses, not results.
- Do not repeat headline values unless they directly support a finding or design test.
- Be direct, avoid generic advice, keep every field to one short sentence, and return immediately."""

VIEW_LABELS = {"top": "top view", "overview": "overview",
               "facade-side": "facade-side view", "park-side": "park-side view"}
OPERATIONS = {
    "widen": "Widen", "raise": "Raise", "lower": "Lower",
    "shift": "Shift", "set_back": "Set back", "open": "Open",
    "split": "Split", "narrow": "Narrow", "rotate": "Rotate",
}
OPERATION_ALIASES = {
    "verbreden": "widen", "uitbreiden": "widen", "verhogen": "raise",
    "ophogen": "raise", "verlagen": "lower", "verschuiven": "shift",
    "verplaatsen": "shift", "terugleggen": "set_back", "openen": "open",
    "insnijden": "open", "splitsen": "split", "versmallen": "narrow",
    "reduceren": "narrow", "draaien": "rotate",
}


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _read_json(path: Path, label: str, maximum_bytes: int = MAX_EVIDENCE_JSON_BYTES) -> dict[str, Any]:
    try:
        if path.stat().st_size > maximum_bytes:
            raise AiError(f"{label} overschrijdt de bestandsgroottelimiet.")
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AiError(f"{label} kan niet worden gelezen: {exc}") from exc
    if not isinstance(value, dict):
        raise AiError(f"{label} heeft geen geldig JSON-object.")
    return value


def _normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-9:
        raise AiError("Modelbeeld bevat een ongeldige camerarichting.")
    return [value / length for value in vector]


def _cross(left: list[float], right: list[float]) -> list[float]:
    return [left[1] * right[2] - left[2] * right[1],
            left[2] * right[0] - left[0] * right[2],
            left[0] * right[1] - left[1] * right[0]]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _screen_coordinates(center: list[float], view: dict[str, Any]) -> tuple[float, float] | None:
    try:
        position = [float(value) for value in view["camera_position"]]
        target = [float(value) for value in view["camera_target"]]
        up = _normalize([float(value) for value in view["camera_up"]])
        forward = _normalize([target[index] - position[index] for index in range(3)])
        right = _normalize(_cross(forward, up))
        camera_up = _cross(right, forward)
        relative = [center[index] - position[index] for index in range(3)]
        depth = _dot(relative, forward)
        if depth <= 0:
            return None
        tangent = math.tan(math.radians(float(view["fov_degrees"])) / 2)
        ndc_x = _dot(relative, right) / (depth * tangent * (float(view["width"]) / float(view["height"])))
        ndc_y = _dot(relative, camera_up) / (depth * tangent)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return ndc_x, ndc_y


def build_design_elements(objects: list[dict[str, Any]], views: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    candidates = []
    for item in objects:
        bounds = item.get("bounds_m") if isinstance(item, dict) else None
        minimum = bounds.get("min") if isinstance(bounds, dict) else None
        maximum = bounds.get("max") if isinstance(bounds, dict) else None
        if (item.get("classification") != "analysis_volume" or not isinstance(item.get("id"), str)
                or not all(isinstance(value, list) and len(value) == 3 for value in (minimum, maximum))):
            continue
        try:
            center = [(float(minimum[index]) + float(maximum[index])) / 2 for index in range(3)]
            dimensions = [float(maximum[index]) - float(minimum[index]) for index in range(3)]
        except (TypeError, ValueError):
            continue
        if (any(not math.isfinite(value) or value < 0 for value in dimensions)
                or any(not math.isfinite(value) for value in center)):
            continue
        candidates.append((dimensions[0] * dimensions[1] * dimensions[2], center, dimensions, item["id"]))
    selected = sorted(candidates, key=lambda value: (-value[0], value[3]))[:limit]
    selected.sort(key=lambda value: (value[1][1], value[1][0], value[3]))
    elements = []
    for index, (_size, center, dimensions, object_id) in enumerate(selected):
        element_id = "volume-" + chr(ord("a") + index)
        elements.append({
            "element_id": element_id,
            "label": "Volume " + chr(ord("A") + index),
            "object_id": object_id,
            "center_m": [round(value, 2) for value in center],
            "dimensions_m": [round(value, 2) for value in dimensions],
            "height_m": round(dimensions[2], 2),
            "view_positions": {},
            "image_coordinates_pct": {},
        })
    for view in views:
        if not isinstance(view, dict) or not isinstance(view.get("id"), str):
            continue
        projected = []
        for element in elements:
            coordinates = _screen_coordinates(element["center_m"], view)
            if coordinates is not None:
                projected.append((coordinates[0], coordinates[1], element))
                element["image_coordinates_pct"][view["id"]] = {
                    "x": round(max(3, min(97, (coordinates[0] + 1) * 50)), 1),
                    "y": round(max(3, min(97, (1 - coordinates[1]) * 50)), 1),
                }
        projected.sort(key=lambda value: (value[0], value[2]["element_id"]))
        count = len(projected)
        for rank, (_x, _y, element) in enumerate(projected):
            if count == 1:
                horizontal = "centre"
            elif rank < count / 3:
                horizontal = "left"
            elif rank >= count * 2 / 3:
                horizontal = "right"
            else:
                horizontal = "centre"
            element["view_positions"][view["id"]] = f"{horizontal} in the {VIEW_LABELS.get(view['id'], view['id'])}"
    return elements


def load_model_evidence(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("job_type", "analysis") != "analysis" or job.get("status") != "completed":
        raise AiError("Model-grounded AI-advies vereist een voltooide analyse.")
    data_dir = Path(job["data_dir"]).resolve()
    paths = {
        "scene": data_dir / "scene.json",
        "geometry": data_dir / "geometry-summary.json",
        "results": data_dir / "latest.json",
        "views": data_dir / "view-evidence.json",
        "weather": data_dir.parent / "weather" / "NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw",
    }
    if any(not path.is_file() for path in paths.values()):
        raise AiError("Leg eerst vier geldige modelbeelden vast voor deze voltooide run.")
    manifest = _read_json(paths["views"], "View-evidence")
    geometry = _read_json(paths["geometry"], "Geometriesamenvatting")
    metrics = _read_json(paths["results"], "Grasshopper-resultaten")
    try:
        site_context = load_site_context()
    except SiteContextError as exc:
        raise AiError(str(exc)) from exc
    expected = {
        "project_id": job["project_id"], "run_id": job["run_id"],
        "source_sha256": job["source_sha256"], "input_sha256": job["input_sha256"],
        "context_sha256": job["context_sha256"], "placement": job["placement"],
        "scene_sha256": _sha256(paths["scene"]),
        "geometry_summary_sha256": _sha256(paths["geometry"]),
        "results_sha256": _sha256(paths["results"]),
        "weather_sha256": _sha256(paths["weather"]),
        "definition_sha256": job.get("definition_sha256"),
        "site_context_sha256": site_context["manifest_sha256"],
        "render_style": "volume-colors-v1",
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise AiError("View-evidence is verouderd of hoort niet bij deze run en plaatsing.")
    geometry_expected = {key: expected[key] for key in (
        "project_id", "run_id", "source_sha256", "input_sha256", "context_sha256", "placement")}
    if any(geometry.get(key) != value for key, value in geometry_expected.items()):
        raise AiError("Geometriesamenvatting is verouderd of hoort niet bij deze run.")

    objects = geometry.get("objects")
    if not isinstance(objects, list) or len(objects) > 5000:
        raise AiError("Geometriesamenvatting overschrijdt de objectlimiet.")
    object_ids = set()
    for item in objects:
        object_id = item.get("id") if isinstance(item, dict) else None
        try:
            valid_object_id = isinstance(object_id, str) and object_id == "source:" + str(uuid.UUID(object_id.removeprefix("source:")))
        except (ValueError, AttributeError):
            valid_object_id = False
        if not valid_object_id or object_id in object_ids:
            raise AiError("Geometriesamenvatting bevat ongeldige of dubbele object-ID's.")
        object_ids.add(object_id)

    raw_views = manifest.get("views")
    if (not isinstance(raw_views, list) or len(raw_views) != len(VIEW_IDS)
            or {item.get("id") for item in raw_views if isinstance(item, dict)} != set(VIEW_IDS)):
        raise AiError("View-evidence bevat niet exact de vier vereiste view-ID's.")
    view_metadata = []
    total_bytes = 0
    for view_id in VIEW_IDS:
        item = next(item for item in raw_views if item.get("id") == view_id)
        relative = item.get("path")
        if not isinstance(relative, str):
            raise AiError("View-evidence bevat een ongeldig afbeeldingspad.")
        image_path = (data_dir / relative).resolve()
        if not image_path.is_relative_to(data_dir) or not image_path.is_file():
            raise AiError("Een evidence-afbeelding ontbreekt of valt buiten de runmap.")
        size = image_path.stat().st_size
        total_bytes += size
        if size > MAX_IMAGE_BYTES or total_bytes > MAX_TOTAL_BYTES or item.get("bytes") != size or item.get("image_sha256") != _sha256(image_path):
            raise AiError("Een evidence-afbeelding is gewijzigd of overschrijdt de limiet.")
        view_metadata.append({key: item.get(key) for key in (
            "id", "image_sha256", "width", "height", "projection", "fov_degrees",
            "camera_position", "camera_target", "camera_up", "visible_layers")})

    design_elements = build_design_elements(objects, view_metadata)
    if not design_elements:
        raise AiError("Geen gelabelde analysevolumes beschikbaar voor concreet AI-advies.")
    model_elements = [{key: item[key] for key in (
        "element_id", "label", "object_id", "dimensions_m", "height_m", "view_positions")}
        for item in design_elements]
    structured = {
        "calculated_results": metrics,
        "design_elements": model_elements,
        "views": [{"id": view_id, "label": VIEW_LABELS[view_id]} for view_id in VIEW_IDS],
        "evidence_status": {
            "north": manifest.get("north_status"),
            "plot": manifest.get("plot_status"),
            "ground": manifest.get("ground_status"),
            "site_alignment": site_context["alignment"].get("status"),
        },
        "site_constraints": {
            "status": "unavailable",
            "transport_infrastructure": "unavailable",
            "horizontal_moves_allowed": True,
            "reason": "Exploratory horizontal tests are allowed, but no verified plot, access, tunnel, or other infrastructure envelope is available.",
        },
    }
    encoded = json.dumps(structured, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > 1_000_000:
        raise AiError("Het gestructureerde evidence-pakket is groter dan 1 MB.")
    return {
        "structured": structured,
        "images": [],
        "object_ids": {item["object_id"] for item in design_elements},
        "view_ids": set(VIEW_IDS),
        "metric_fields": set(metrics),
        "design_elements": design_elements,
        "element_ids": {item["element_id"] for item in design_elements},
        "horizontal_moves_allowed": True,
        "provenance": {
            "view_evidence_sha256": _sha256(paths["views"]),
            **{key: expected[key] for key in ("scene_sha256", "geometry_summary_sha256", "results_sha256", "weather_sha256", "site_context_sha256")},
        },
    }


def _chat_url(endpoint: str) -> str:
    value = endpoint.strip().rstrip("/")
    parsed = parse.urlparse(value)
    if parsed.scheme not in {"https", "http"}:
        raise AiError("AI-endpoint moet een http- of https-URL zijn.")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise AiError("AI-endpoint mag geen gebruikersgegevens, queryparameters of fragment bevatten.")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise AiError("Externe AI-endpoints moeten HTTPS gebruiken.")
    return value if value.endswith("/chat/completions") else value + "/chat/completions"


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise AiError(f"AI-provider gaf een ongeldig veld terug: {field}.")
    return value


def _item_text(item: dict[str, Any], *fields: str) -> str | None:
    for field in fields:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _reference_list(item: dict[str, Any], plural: str, singular: str, *, default=None) -> list[str]:
    value = item.get(plural)
    if value is None and isinstance(item.get(singular), str):
        value = [item[singular]]
    if value is None and default is not None:
        value = default
    return _string_list(value, plural)


def _canonical_ids(values: list[str], kind: str, evidence: dict[str, Any]) -> list[str]:
    if kind == "view":
        aliases = {value.lower(): value for value in evidence["view_ids"]}
        aliases.update({label.lower(): value for value, label in VIEW_LABELS.items()
                        if value in evidence["view_ids"]})
    elif kind == "metric":
        aliases = {value.lower(): value for value in evidence["metric_fields"]}
    else:
        aliases = {value.lower(): value for value in evidence["object_ids"]}
        for element in evidence.get("design_elements", []):
            if not isinstance(element, dict) or element.get("object_id") not in evidence["object_ids"]:
                continue
            for alias in (element.get("element_id"), element.get("label")):
                if isinstance(alias, str):
                    aliases[alias.lower()] = element["object_id"]
    normalized = []
    for value in values:
        candidate = value.strip()
        prefix = kind + ":"
        if candidate.lower().startswith(prefix):
            candidate = candidate[len(prefix):]
        canonical = aliases.get(candidate.lower(), candidate)
        if canonical not in normalized:
            normalized.append(canonical)
    return normalized


def _canonical_evidence_refs(values: list[str], evidence: dict[str, Any]) -> list[str]:
    normalized = []
    for value in values:
        kind, separator, candidate = value.strip().partition(":")
        if separator and kind.lower() in {"view", "object", "metric"}:
            canonical = _canonical_ids([candidate], kind.lower(), evidence)[0]
            reference = kind.lower() + ":" + canonical
        else:
            matches = []
            for candidate_kind in ("view", "object", "metric"):
                canonical = _canonical_ids([value], candidate_kind, evidence)[0]
                allowed = evidence[candidate_kind + "_ids"] if candidate_kind != "metric" else evidence["metric_fields"]
                if canonical in allowed:
                    matches.append(candidate_kind + ":" + canonical)
            reference = matches[0] if len(matches) == 1 else value
        if reference not in normalized:
            normalized.append(reference)
    return normalized


def _reader_text(value: str, field: str, maximum: int) -> str:
    text = value.strip()
    if not text or len(text) > maximum:
        raise AiError(f"AI output field {field} must contain at most {maximum} characters.")
    if re.search(r"\b(?:PH|PDOK)_[A-Z0-9_]+\b|\b(?:source|view|metric):\S+|\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b",
                 text, re.IGNORECASE):
        raise AiError(f"AI output field {field} exposes a raw evidence identifier.")
    if re.search(r"\b([A-Za-z][A-Za-z-]{2,})\s+\1\b", text, re.IGNORECASE):
        raise AiError(f"AI output field {field} repeats a word.")
    return text


def _evidenced_dimensions(evidence: dict[str, Any]) -> set[float]:
    values: set[float] = set()
    for element in evidence.get("design_elements", []):
        if not isinstance(element, dict):
            continue
        for value in [*(element.get("dimensions_m") or []), element.get("height_m")]:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.add(round(float(value), 3))
    return values


_UNSUPPORTED_MOVE_TERM = (
    r"(?:shift(?:s|ed|ing)?|mov(?:e|es|ed|ing|ements?)|relocat\w*|"
    r"set\s*back|setback|backwards?|outwards?|footprint\s+expansion)"
)
_UNSUPPORTED_MOVE = re.compile(rf"\b{_UNSUPPORTED_MOVE_TERM}\b", re.IGNORECASE)
_NEGATED_UNSUPPORTED_MOVE = re.compile(
    rf"\b(?:no|without|avoid(?:s|ed|ing)?|prevent(?:s|ed|ing)?|forbid(?:s|den|ding)?|"
    rf"geen|zonder|vermijd(?:t|en)?|voorkom(?:t|en)?|verbied(?:t|en)?)\s+"
    rf"(?:\w+[ -]){{0,3}}{_UNSUPPORTED_MOVE_TERM}\b|"
    rf"\b(?:does|do|did|will|would|should|must|is|are)\s+not\s+"
    rf"(?:\w+[ -]){{0,3}}{_UNSUPPORTED_MOVE_TERM}\b|"
    rf"\b{_UNSUPPORTED_MOVE_TERM}\b\s+(?:is|are|remains?|wordt|blijft)\s+"
    rf"(?:not\s+(?:allowed|permitted|proposed|recommended|required)|prohibited|forbidden|disallowed|withheld|"
    rf"niet\s+toegestaan|verboden|tegengehouden)",
    re.IGNORECASE,
)


def _proposes_unsupported_move(value: str) -> bool:
    """Distinguish a movement proposal from an explicit movement prohibition."""
    return _UNSUPPORTED_MOVE.search(_NEGATED_UNSUPPORTED_MOVE.sub("", value)) is not None


def _validate_review(review: Any, evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(review, dict) or not isinstance(review.get("samenvatting"), str):
        raise AiError("AI-provider gaf geen geldig gestructureerd advies terug.")
    calculations = review.get("berekeningsbewijs")
    observations = review.get("visuele_observaties")
    actions = review.get("ontwerpacties")
    raw_limitations = review.get("beperkingen")
    limitations = _string_list([raw_limitations] if isinstance(raw_limitations, str) else raw_limitations,
                               "beperkingen")
    if not isinstance(calculations, list) or not isinstance(observations, list):
        raise AiError("AI-provider gaf geen geldige adviesarrays terug.")
    if not 1 <= len(calculations) <= 3 or not 1 <= len(observations) <= 3 or not 1 <= len(limitations) <= 3:
        raise AiError("AI output must contain 1-3 findings, observations, and limitations.")
    summary = _reader_text(review["samenvatting"], "samenvatting", 450)
    if not evidence.get("horizontal_moves_allowed", True) and _proposes_unsupported_move(summary):
        raise AiError("AI-samenvatting stelt een niet-geverifieerde horizontale verplaatsing voor.")
    limitations = [_reader_text(value, "beperkingen", 220) for value in limitations]
    normalized_calculations = []
    for item in calculations:
        text = _item_text(item, "tekst", "berekening", "uitleg") if isinstance(item, dict) else None
        if text is None:
            raise AiError("Ongeldig berekeningsbewijs in AI-antwoord.")
        text = _reader_text(text, "berekeningsbewijs.tekst", 240)
        fields = _canonical_ids(_reference_list(item, "metric_fields", "metric_field"), "metric", evidence)
        if not fields or not set(fields) <= evidence["metric_fields"]:
            raise AiError("AI-antwoord verwijst naar een onbekend metricveld.")
        normalized_calculations.append({"tekst": text, "metric_fields": fields})
    normalized_observations = []
    for item in observations:
        text = _item_text(item, "tekst", "observatie") if isinstance(item, dict) else None
        if text is None:
            raise AiError("Ongeldige visuele observatie: tekst ontbreekt.")
        text = _reader_text(text, "visuele_observaties.tekst", 240)
        views = _canonical_ids(_reference_list(item, "view_ids", "view_id"), "view", evidence)
        objects = _canonical_ids(_reference_list(item, "object_ids", "object_id", default=[]), "object", evidence)
        if not views or not set(views) <= evidence["view_ids"] or not set(objects) <= evidence["object_ids"]:
            raise AiError("AI-antwoord verwijst naar onbekend beeld- of objectbewijs.")
        uncertainty = _item_text(item, "onzekerheid", "beperking") or "Not specified by the AI model."
        uncertainty = _reader_text(uncertainty, "visuele_observaties.onzekerheid", 180)
        normalized_observations.append({"tekst": text, "view_ids": views,
                                        "object_ids": objects, "onzekerheid": uncertainty})
    allowed_refs = ({"view:" + value for value in evidence["view_ids"]}
                    | {"object:" + value for value in evidence["object_ids"]}
                    | {"metric:" + value for value in evidence["metric_fields"]})
    if not isinstance(actions, list) or len(actions) != 3:
        raise AiError("AI-provider gaf geen geldige ontwerpacties terug.")
    elements = {item["element_id"]: item for item in evidence["design_elements"]}
    element_aliases = {item["label"].lower(): item for item in evidence["design_elements"]}
    normalized_actions = []
    priorities = set()
    action_keys = set()
    for item in actions:
        if not isinstance(item, dict):
            raise AiError("Ongeldige ontwerpactie in AI-antwoord.")
        priority = item.get("prioriteit")
        element_value = item.get("element_id")
        element = elements.get(element_value)
        if element is None and isinstance(element_value, str):
            element = element_aliases.get(element_value.lower())
        operation = item.get("ingreep")
        operation = OPERATION_ALIASES.get(operation, operation) if isinstance(operation, str) else None
        direction = _item_text(item, "richting")
        magnitude = _item_text(item, "testomvang", "omvang")
        goal = _item_text(item, "ontwerpdoel", "doel")
        effect = _item_text(item, "verwacht_effect", "effect")
        tradeoff = _item_text(item, "afweging", "risico")
        if (isinstance(priority, bool) or not isinstance(priority, int) or priority not in {1, 2, 3}
                or priority in priorities or element is None or operation not in OPERATIONS
                or None in (direction, magnitude, goal, effect, tradeoff)):
            raise AiError("Ontwerpactie mist prioriteit, volume, ingreep, richting, testomvang, doel, effect of afweging.")
        if not evidence.get("horizontal_moves_allowed", True) and operation in {"shift", "set_back", "widen", "rotate"}:
            raise AiError("Ontwerpactie vergroot of verplaatst de footprint terwijl plot- en infrastructuurconstraints ontbreken.")
        direction = re.sub(rf"\b{re.escape(element['label'])}\b", "", direction,
                           flags=re.IGNORECASE).strip(" ,.-")
        direction = _reader_text(direction, "ontwerpacties.richting", 120)
        magnitude = _reader_text(magnitude, "ontwerpacties.testomvang", 140)
        goal = _reader_text(goal, "ontwerpacties.ontwerpdoel", 180)
        effect = _reader_text(effect, "ontwerpacties.verwacht_effect", 180)
        tradeoff = _reader_text(tradeoff, "ontwerpacties.afweging", 180)
        if (not evidence.get("horizontal_moves_allowed", True)
                and any(_proposes_unsupported_move(text) for text in (goal, effect, tradeoff))):
            raise AiError("Ontwerpactie stelt in de toelichting een niet-geverifieerde horizontale verplaatsing voor.")
        checks = _canonical_ids(_reference_list(item, "controle_metric_fields", "controle_metric_field"), "metric", evidence)
        if not checks or not set(checks) <= evidence["metric_fields"]:
            raise AiError("Ontwerpactie bevat een onbekende controlemetric.")
        refs = _canonical_evidence_refs(_reference_list(item, "evidence_refs", "evidence_ref"), evidence)
        if not refs or not set(refs) <= allowed_refs:
            raise AiError("Ontwerpactie verwijst naar onbekend bewijs.")
        required_object_ref = "object:" + element["object_id"]
        if required_object_ref not in refs or not any(ref.startswith("view:") for ref in refs):
            raise AiError("Ontwerpactie moet het gekozen volume en minstens één modelbeeld onderbouwen.")
        direction_lower = direction.lower()
        if (not evidence.get("horizontal_moves_allowed", True)
                and re.search(r"\b(?:left|right|backwards?|forwards?|outwards?|away|links|rechts|achteruit|vooruit|buitenwaarts)\b",
                              direction_lower, re.IGNORECASE)):
            raise AiError("Ontwerpactie bevat een horizontale richting terwijl plot- en infrastructuurconstraints ontbreken.")
        spatial_terms = ("left", "right", "toward", "away", "inward", "up", "down", "above", "below",
                         "centre", "center", "view", "volume", "facade", "park",
                         "links", "rechts", "richting", "omhoog", "omlaag", "voor", "achter")
        if not any(term in direction_lower for term in spatial_terms):
            raise AiError("Ontwerpactie moet een concrete ruimtelijke richting bevatten.")
        anchors = ("view", "volume", "beeld", "aanzicht")
        if not any(term in direction_lower for term in anchors):
            view_id = next(ref.removeprefix("view:") for ref in refs if ref.startswith("view:"))
            direction = f"{direction.rstrip('.')} in the {VIEW_LABELS.get(view_id, view_id)}"
        if not re.search(r"\d|one|two|three|storey|story|bay|metre|meter|percent|%|één|bouwlaag|beuk|procent", magnitude.lower()):
            raise AiError("Ontwerpactie moet een concrete testomvang bevatten.")
        metre_values = re.findall(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*-?\s*(?:m|metres?|meters?)\b", magnitude,
                                  flags=re.IGNORECASE)
        dimensions = _evidenced_dimensions(evidence)
        if any(round(float(value.replace(",", ".")), 3) not in dimensions for value in metre_values):
            raise AiError("An absolute test dimension is not present in the supplied evidence; use a relative sensitivity range.")
        if not re.search(r"\b5\s*(?:-|–|—|to)\s*10\s*(?:%|percent)(?!\w)", magnitude, re.IGNORECASE):
            raise AiError("Ontwerpactie moet de gevraagde relatieve gevoeligheidsrange van 5-10% gebruiken.")
        if not re.search(r"\b(?:may|might|could)\b", effect, re.IGNORECASE):
            raise AiError("Expected effects must be written as a conditional hypothesis using may, might, or could.")
        action_key = (element["element_id"], operation, direction.lower())
        if action_key in action_keys:
            raise AiError("AI-provider moet drie verschillende ontwerpacties geven.")
        action_keys.add(action_key)
        priorities.add(priority)
        normalized_actions.append({
            "prioriteit": priority,
            "element_id": element["element_id"],
            "element_label": element["label"],
            "object_id": element["object_id"],
            "ingreep": operation,
            "instructie": f"{OPERATIONS[operation]} {element['label']} {direction.rstrip('.')}.",
            "richting": direction,
            "testomvang": magnitude,
            "ontwerpdoel": goal,
            "verwacht_effect": effect,
            "afweging": tradeoff,
            "controle_metric_fields": checks,
            "evidence_refs": refs,
        })
    normalized_actions.sort(key=lambda item: item["prioriteit"])
    return {"samenvatting": summary, "berekeningsbewijs": normalized_calculations,
            "visuele_observaties": normalized_observations, "ontwerpacties": normalized_actions,
            "beperkingen": limitations}


def _decode_provider_content(content: Any) -> Any:
    if isinstance(content, dict):
        return content
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    if not isinstance(content, str):
        raise AiError("AI-provider gaf geen tekst of JSON terug.")
    value = content.strip()
    if not value:
        raise AiError("AI-provider gaf een leeg antwoord terug.")
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, count=1, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value, count=1)
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise AiError("AI-provider gaf geen geldig JSON-advies terug.") from exc


def _http_error_message(exc: error.HTTPError, api_key: str) -> str:
    message = ""
    try:
        body = json.loads(exc.read(4096).decode("utf-8"))
        candidate = body.get("detail") or body.get("message") or body.get("error")
        if isinstance(candidate, dict):
            candidate = candidate.get("message") or candidate.get("detail")
        if isinstance(candidate, str):
            message = candidate.strip().replace(api_key, "[redacted]")[:500]
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    suffix = f": {message}" if message else ""
    return f"AI-provider weigerde het verzoek (HTTP {exc.code}){suffix}"


def _provider_request(endpoint: str, api_key: str, model: str, messages: list[dict[str, Any]]) -> Any:
    payload = {"model": model, "messages": messages, "max_tokens": 1800, "stream": False}
    if parse.urlparse(endpoint.strip()).hostname == "api.deepseek.com":
        # DeepSeek enables high-effort thinking by default. Its reasoning tokens share
        # max_tokens and can exhaust the budget before the requested JSON is emitted.
        payload.update(thinking={"type": "disabled"}, reasoning_effort="none",
                       response_format={"type": "json_object"})
    http_request = request.Request(_chat_url(endpoint), data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}, method="POST")
    try:
        with open_ai_request(http_request, timeout=AI_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
    except error.HTTPError as exc:
        raise AiError(_http_error_message(exc, api_key)) from exc
    except EndpointTrustError as exc:
        raise AiError(str(exc)) from exc
    except error.URLError as exc:
        detail = str(exc.reason).replace(api_key, "[redacted]")[:500]
        raise AiError("AI-provider is niet bereikbaar: " + detail) from exc
    except (TimeoutError, OSError) as exc:
        raise AiError("AI-provider is niet bereikbaar of reageerde niet op tijd.") from exc
    if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
        raise AiError("AI-provider gaf een onverwacht groot antwoord terug.")
    if not body.strip():
        raise AiError("AI-provider gaf een leeg HTTP-antwoord terug. Probeer het opnieuw of kies een ander model.")
    try:
        raw = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AiError("AI-provider gaf geen geldig chat-completion-antwoord terug.") from exc
    if not isinstance(raw, dict):
        raise AiError("AI-provider gaf een ongeldig chat-completion-antwoord terug.")
    provider_error = raw.get("error")
    if provider_error:
        message = provider_error.get("message") if isinstance(provider_error, dict) else provider_error
        suffix = f": {str(message).replace(api_key, '[redacted]')[:500]}" if message else ""
        raise AiError("AI-provider meldde een fout" + suffix)
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AiError("AI-provider gaf geen antwoordkeuze terug.")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise AiError("AI-provider gaf geen geldig antwoordbericht terug.")
    content = message.get("content")
    finish_reason = choice.get("finish_reason")
    if finish_reason == "length":
        raise AiError("AI-provider brak het antwoord af door de uitvoerlimiet. Kies een niet-redenerend model of probeer opnieuw.")
    if content is None or (isinstance(content, str) and not content.strip()):
        refusal = message.get("refusal")
        if isinstance(refusal, str) and refusal.strip():
            detail = refusal.strip().replace(api_key, "[redacted]")[:500]
            raise AiError("AI-provider weigerde het advies: " + detail)
        if finish_reason in {"content_filter", "insufficient_system_resource", "aborted"}:
            raise AiError(f"AI-provider gaf geen advies terug (reden: {finish_reason}).")
        raise AiError("AI-provider gaf een leeg advies terug. Probeer het opnieuw of kies een ander model.")
    return content


def _field_overview(value: Any) -> str:
    if not isinstance(value, dict):
        return type(value).__name__
    parts = [", ".join(sorted(str(key) for key in value))]
    actions = value.get("ontwerpacties")
    if isinstance(actions, list):
        for index, action in enumerate(actions[:3], 1):
            if isinstance(action, dict):
                parts.append(f"actie {index}: {', '.join(sorted(str(key) for key in action))}")
    return "; ".join(parts)[:700]


def request_review(*, endpoint: str, api_key: str, model: str, evidence: dict[str, Any], design_goal: str) -> dict[str, Any]:
    allowed_operations = ("widen|raise|lower|shift|set_back|open|split|narrow|rotate"
                          if evidence.get("horizontal_moves_allowed", True)
                          else "raise|lower|open|split|narrow")
    response_schema = {
        "samenvatting": "one short English sentence",
        "berekeningsbewijs": [{"tekst": "measured finding", "metric_fields": ["metric ID"]}],
        "visuele_observaties": [{"tekst": "spatial observation from labelled dimensions or view_positions", "view_ids": ["view ID"],
                                  "object_ids": [], "onzekerheid": "specific uncertainty"}],
        "ontwerpacties": [{
            "prioriteit": "integer 1, 2, or 3; use each once",
            "element_id": "design element ID",
            "ingreep": allowed_operations,
            "richting": "short view-relative direction",
            "testomvang": "5-10% relative sensitivity range, not an optimum",
            "ontwerpdoel": "short design objective",
            "verwacht_effect": "short hypothesis using may, might, or could",
            "afweging": "short trade-off",
            "controle_metric_fields": ["metric ID to rerun"],
            "evidence_refs": ["view:<id>", "object:<id>", "optional metric:<id>"],
        }],
        "beperkingen": ["material limitation"],
    }
    content = json.dumps({
        "design_goal": design_goal, "evidence": evidence["structured"], "response_schema": response_schema,
    }, ensure_ascii=False, separators=(",", ":"))
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]
    provider_content = _provider_request(endpoint, api_key, model, messages)
    try:
        review = _decode_provider_content(provider_content)
        validated = _validate_review(review, evidence)
    except (AiError, ValueError) as exc:
        raise AiError(f"AI-provider gaf geen bruikbaar gestructureerd advies: {exc}") from exc
    validated.update(provider_endpoint=endpoint, model=model, evidence_provenance=evidence["provenance"],
                      design_elements=evidence["design_elements"], visual_evidence_used=False,
                      model_view_evidence_used=True, output_language="en",
                      advice_policy_version=ADVICE_POLICY_VERSION)
    return validated
