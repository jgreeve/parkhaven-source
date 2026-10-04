"""Ephemeral model-grounded OpenAI-compatible review client."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from .ai_tls import open_ai_request
from .site_context import SiteContextError, load_site_context
from .view_evidence import MAX_IMAGE_BYTES, MAX_TOTAL_BYTES, VIEW_IDS


class AiError(ValueError):
    pass


SYSTEM_PROMPT = """Je bent de ParkHaven ontwerpbeoordelaar. Grasshopper is de enige
bron voor berekende waarden. Verander of herbereken die waarden niet. Gebruik alleen
de aangeleverde metrics, object-ID's en view-ID's. Schrijf in het Nederlands en
onderscheid berekeningsbewijs, visuele observatie, onzekerheid en aanbeveling.
Afbeeldingen bewijzen geen nieuwe BVO-, zicht-, zon-, hitte- of kostenmeting.
Noord, plot en maaiveld zijn alleen geldig wanneer het evidence-pakket dat bevestigt.
Antwoord uitsluitend als JSON volgens het gevraagde schema; verzin geen references."""


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AiError(f"{label} kan niet worden gelezen: {exc}") from exc
    if not isinstance(value, dict):
        raise AiError(f"{label} heeft geen geldig JSON-object.")
    return value


def load_model_evidence(job: dict[str, Any]) -> dict[str, Any]:
    if job.get("job_type", "analysis") != "analysis" or job.get("status") != "completed":
        raise AiError("Model-grounded AI-advies vereist een voltooide analyse.")
    data_dir = Path(job["data_dir"]).resolve()
    paths = {
        "scene": data_dir / "scene.json",
        "geometry": data_dir / "geometry-summary.json",
        "results": data_dir / "latest.json",
        "views": data_dir / "view-evidence.json",
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
        "definition_sha256": job.get("definition_sha256"),
        "site_context_sha256": site_context["manifest_sha256"],
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
    images = []
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
        images.append({"id": view_id, "data_url": "data:image/png;base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")})
        view_metadata.append({key: item.get(key) for key in (
            "id", "image_sha256", "width", "height", "projection", "fov_degrees",
            "camera_position", "camera_target", "camera_up", "visible_layers")})

    structured = {
        "evidence_schema_version": 1,
        "run": {key: manifest.get(key) for key in (
            "project_id", "run_id", "source_sha256", "input_sha256", "context_sha256",
            "scene_sha256", "geometry_summary_sha256", "results_sha256", "definition_sha256",
            "placement", "north_status", "plot_status", "ground_status")},
        "berekende_resultaten": metrics,
        "geometrie": {
            "id_strategy": geometry.get("id_strategy"),
            "objects_sha256": geometry.get("objects_sha256"),
            "total_objects": geometry.get("total_objects"),
            "omitted_objects": geometry.get("omitted_objects"),
            "objects": objects,
        },
        "views": view_metadata,
        "visual_site_context": {
            "context_id": site_context["context_id"],
            "manifest_sha256": site_context["manifest_sha256"],
            "image_sha256": site_context["image_sha256"],
            "source": site_context["source"],
            "alignment": site_context["alignment"],
            "rd_bbox": site_context["rd_bbox"],
            "local_corners_m": site_context["local_corners_m"],
        },
    }
    encoded = json.dumps(structured, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > 1_000_000:
        raise AiError("Het gestructureerde evidence-pakket is groter dan 1 MB.")
    return {
        "structured": structured,
        "images": images,
        "object_ids": object_ids,
        "view_ids": set(VIEW_IDS),
        "metric_fields": set(metrics),
        "provenance": {
            "view_evidence_sha256": _sha256(paths["views"]),
            **{key: expected[key] for key in ("scene_sha256", "geometry_summary_sha256", "results_sha256", "site_context_sha256")},
        },
    }


def _chat_url(endpoint: str) -> str:
    value = endpoint.strip().rstrip("/")
    parsed = parse.urlparse(value)
    if parsed.scheme not in {"https", "http"}:
        raise AiError("AI-endpoint moet een http- of https-URL zijn.")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise AiError("Externe AI-endpoints moeten HTTPS gebruiken.")
    return value if value.endswith("/chat/completions") else value + "/chat/completions"


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise AiError(f"AI-provider gaf een ongeldig veld terug: {field}.")
    return value


def _validate_review(review: Any, evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(review, dict) or not isinstance(review.get("samenvatting"), str):
        raise AiError("AI-provider gaf geen geldig gestructureerd advies terug.")
    calculations = review.get("berekeningsbewijs")
    observations = review.get("visuele_observaties")
    recommendations = review.get("aanbevelingen")
    limitations = _string_list(review.get("beperkingen"), "beperkingen")
    if not all(isinstance(value, list) for value in (calculations, observations, recommendations)):
        raise AiError("AI-provider gaf geen geldige adviesarrays terug.")
    for item in calculations:
        if not isinstance(item, dict) or not isinstance(item.get("tekst"), str):
            raise AiError("Ongeldig berekeningsbewijs in AI-antwoord.")
        fields = _string_list(item.get("metric_fields"), "metric_fields")
        if not fields or not set(fields) <= evidence["metric_fields"]:
            raise AiError("AI-antwoord verwijst naar een onbekend metricveld.")
    for item in observations:
        if not isinstance(item, dict) or not isinstance(item.get("tekst"), str) or not isinstance(item.get("onzekerheid"), str):
            raise AiError("Ongeldige visuele observatie in AI-antwoord.")
        views = _string_list(item.get("view_ids"), "view_ids")
        objects = _string_list(item.get("object_ids"), "object_ids")
        if not views or not set(views) <= evidence["view_ids"] or not set(objects) <= evidence["object_ids"]:
            raise AiError("AI-antwoord verwijst naar onbekend beeld- of objectbewijs.")
    allowed_refs = ({"view:" + value for value in evidence["view_ids"]}
                    | {"object:" + value for value in evidence["object_ids"]}
                    | {"metric:" + value for value in evidence["metric_fields"]})
    for item in recommendations:
        if not isinstance(item, dict) or not isinstance(item.get("tekst"), str):
            raise AiError("Ongeldige aanbeveling in AI-antwoord.")
        refs = _string_list(item.get("evidence_refs"), "evidence_refs")
        if not refs or not set(refs) <= allowed_refs:
            raise AiError("AI-aanbeveling verwijst naar onbekend bewijs.")
    return {"samenvatting": review["samenvatting"], "berekeningsbewijs": calculations,
            "visuele_observaties": observations, "aanbevelingen": recommendations,
            "beperkingen": limitations}


def request_review(*, endpoint: str, api_key: str, model: str, evidence: dict[str, Any], design_goal: str) -> dict[str, Any]:
    response_schema = {
        "samenvatting": "Nederlandse tekst",
        "berekeningsbewijs": [{"tekst": "tekst", "metric_fields": ["bestaand_metricveld"]}],
        "visuele_observaties": [{"tekst": "tekst", "view_ids": ["bestaand-view-id"],
                                  "object_ids": ["optioneel-bestaand-object-id"], "onzekerheid": "tekst"}],
        "aanbevelingen": [{"tekst": "tekst", "evidence_refs": ["view:<id>|object:<id>|metric:<veld>"]}],
        "beperkingen": ["tekst"],
    }
    content = [{"type": "text", "text": json.dumps({
        "ontwerpdoel": design_goal, "evidence": evidence["structured"], "response_schema": response_schema,
    }, ensure_ascii=False)}]
    for image in evidence["images"]:
        content.extend(({"type": "text", "text": "VIEW_ID: " + image["id"]},
                        {"type": "image_url", "image_url": {"url": image["data_url"], "detail": "high"}}))
    payload = {"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]}
    http_request = request.Request(_chat_url(endpoint), data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}, method="POST")
    try:
        with open_ai_request(http_request, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8"))
        provider_content = raw["choices"][0]["message"]["content"]
        review = json.loads(provider_content) if isinstance(provider_content, str) else provider_content
    except (error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
        raise AiError("AI-advies kon niet worden opgehaald: " + str(exc)) from exc
    validated = _validate_review(review, evidence)
    validated.update(provider_endpoint=endpoint, model=model, evidence_provenance=evidence["provenance"],
                     visual_evidence_used=True)
    return validated
