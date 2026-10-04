import json
from urllib import error

import pytest

from app import ai


OBJECT_ID = "source:12345678-1234-1234-1234-123456789abc"


def evidence():
    return {
        "structured": {"berekende_resultaten": {"bvo_m2": 1000}, "geometrie": {"objects": [{"id": OBJECT_ID}]}},
        "images": [{"id": view_id, "data_url": "data:image/png;base64,AA=="}
                   for view_id in ("top", "overview", "facade-side", "park-side")],
        "object_ids": {OBJECT_ID},
        "view_ids": {"top", "overview", "facade-side", "park-side"},
        "metric_fields": {"bvo_m2"},
        "provenance": {"view_evidence_sha256": "1" * 64},
    }


def valid_review():
    return {
        "samenvatting": "Heldere basis.",
        "berekeningsbewijs": [{"tekst": "BVO uit Grasshopper.", "metric_fields": ["bvo_m2"]}],
        "visuele_observaties": [{"tekst": "De massa is zichtbaar.", "view_ids": ["overview"],
                                  "object_ids": [OBJECT_ID], "onzekerheid": "Geen noordpijl."}],
        "aanbevelingen": [{"tekst": "Onderzoek de parkzijde.",
                             "evidence_refs": ["view:park-side", "object:" + OBJECT_ID]}],
        "beperkingen": ["Noord is niet geverifieerd."],
    }


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        content = json.dumps(valid_review())
        return json.dumps({"choices": [{"message": {"content": content}}]}).encode()


def test_review_sends_four_labelled_images_without_returning_key(monkeypatch):
    captured = {}

    def fake_urlopen(http_request, timeout):
        captured["url"] = http_request.full_url
        captured["authorization"] = http_request.headers["Authorization"]
        captured["payload"] = json.loads(http_request.data)
        return FakeResponse()

    monkeypatch.setattr(ai, "open_ai_request", fake_urlopen)
    result = ai.request_review(endpoint="https://example.test/v1", api_key="secret-value",
        model="vision-model", evidence=evidence(), design_goal="Meer zicht")
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret-value"
    user_content = captured["payload"]["messages"][1]["content"]
    assert [item["text"] for item in user_content if item["type"] == "text" and item["text"].startswith("VIEW_ID:")] == [
        "VIEW_ID: top", "VIEW_ID: overview", "VIEW_ID: facade-side", "VIEW_ID: park-side"]
    assert len([item for item in user_content if item["type"] == "image_url"]) == 4
    assert result["visual_evidence_used"] is True
    assert result["evidence_provenance"] == evidence()["provenance"]
    assert "secret-value" not in json.dumps(result)


@pytest.mark.parametrize(("change", "message"), [
    (lambda value: value["berekeningsbewijs"][0].update(metric_fields=["invented"]), "metricveld"),
    (lambda value: value["visuele_observaties"][0].update(view_ids=["north"]), "beeld- of objectbewijs"),
    (lambda value: value["visuele_observaties"][0].update(object_ids=["source:00000000-0000-0000-0000-000000000000"]), "beeld- of objectbewijs"),
    (lambda value: value["aanbevelingen"][0].update(evidence_refs=["metric:invented"]), "onbekend bewijs"),
])
def test_review_rejects_invented_evidence_references(change, message):
    review = valid_review()
    change(review)
    with pytest.raises(ai.AiError, match=message):
        ai._validate_review(review, evidence())


def test_external_plain_http_endpoint_is_rejected():
    with pytest.raises(ai.AiError, match="HTTPS"):
        ai.request_review(endpoint="http://example.test/v1", api_key="key", model="model",
                          evidence=evidence(), design_goal="")


@pytest.mark.parametrize("provider_content", ["not json", json.dumps({"samenvatting": "Onvolledig"})])
def test_review_rejects_malformed_or_incomplete_provider_json(monkeypatch, provider_content):
    class InvalidResponse(FakeResponse):
        def read(self):
            return json.dumps({"choices": [{"message": {"content": provider_content}}]}).encode()
    monkeypatch.setattr(ai, "open_ai_request", lambda *_args, **_kwargs: InvalidResponse())
    with pytest.raises(ai.AiError, match="AI-(advies|provider)"):
        ai.request_review(endpoint="https://example.test/v1", api_key="key", model="model",
                          evidence=evidence(), design_goal="")


def test_provider_unsupported_image_error_is_exposed_without_fallback(monkeypatch):
    def unsupported(http_request, timeout):
        raise error.HTTPError(http_request.full_url, 400, "image input unsupported", None, None)
    monkeypatch.setattr(ai, "open_ai_request", unsupported)
    with pytest.raises(ai.AiError, match="HTTP Error 400"):
        ai.request_review(endpoint="https://example.test/v1", api_key="key", model="text-only",
                          evidence=evidence(), design_goal="")
