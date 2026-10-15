import json
from io import BytesIO
from urllib import error

import pytest

from app import ai


OBJECT_ID = "source:12345678-1234-1234-1234-123456789abc"
ELEMENT = {"element_id": "volume-a", "label": "Volume A", "object_id": OBJECT_ID,
           "center_m": [0, 0, 10], "dimensions_m": [20, 30, 20], "height_m": 20,
           "view_positions": {"overview": "left in the overview"}}


def evidence():
    return {
        "structured": {"calculated_results": {"bvo_m2": 1000}, "geometry": {"objects": [{"id": OBJECT_ID}]}},
        "images": [{"id": view_id, "data_url": "data:image/png;base64,AA=="}
                   for view_id in ("top", "overview", "facade-side", "park-side")],
        "object_ids": {OBJECT_ID},
        "view_ids": {"top", "overview", "facade-side", "park-side"},
        "metric_fields": {"bvo_m2"},
        "design_elements": [ELEMENT],
        "element_ids": {"volume-a"},
        "horizontal_moves_allowed": True,
        "provenance": {"view_evidence_sha256": "1" * 64},
    }


def valid_review():
    return {
        "samenvatting": "The current massing provides a clear basis for focused design tests.",
        "berekeningsbewijs": [{"tekst": "Grasshopper reports the gross floor area.", "metric_fields": ["bvo_m2"]}],
        "visuele_observaties": [{"tekst": "The volume is clearly visible.", "view_ids": ["overview"],
                                  "object_ids": [OBJECT_ID], "onzekerheid": "No orientation marker is visible."}],
        "ontwerpacties": [{
            "prioriteit": priority, "element_id": "volume-a", "ingreep": operation,
            "richting": "to the right in the overview", "testomvang": "Test a 5-10% relative change.",
            "ontwerpdoel": "Improve spatial cohesion.", "verwacht_effect": "This may strengthen the cluster.",
            "afweging": "This could reduce the gap between volumes.", "controle_metric_fields": ["bvo_m2"],
            "evidence_refs": ["view:overview", "object:" + OBJECT_ID, "metric:bvo_m2"],
        } for priority, operation in enumerate(("widen", "raise", "shift"), 1)],
        "beperkingen": ["Orientation is not verified."],
    }


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _amount=-1):
        content = json.dumps(valid_review())
        return json.dumps({"choices": [{"message": {"content": content}}]}).encode()


def test_review_sends_rich_text_evidence_without_images_or_key(monkeypatch):
    captured = {}

    def fake_urlopen(http_request, timeout):
        captured["url"] = http_request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = http_request.headers["Authorization"]
        captured["payload"] = json.loads(http_request.data)
        return FakeResponse()

    monkeypatch.setattr(ai, "open_ai_request", fake_urlopen)
    result = ai.request_review(endpoint="https://example.test/v1", api_key="secret-value",
        model="vision-model", evidence=evidence(), design_goal="Meer zicht")
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret-value"
    assert captured["timeout"] == 120
    assert "temperature" not in captured["payload"]
    assert "response_format" not in captured["payload"]
    assert captured["payload"]["max_tokens"] == 1800
    assert captured["payload"]["stream"] is False
    user_content = captured["payload"]["messages"][1]["content"]
    assert isinstance(user_content, str)
    assert json.loads(user_content)["evidence"]["calculated_results"] == {"bvo_m2": 1000}
    assert "image_url" not in json.dumps(captured["payload"])
    assert len(json.dumps(captured["payload"])) < 10_000
    assert len(captured["payload"]["messages"][0]["content"]) < 1800
    assert result["visual_evidence_used"] is False
    assert result["model_view_evidence_used"] is True
    assert len(result["ontwerpacties"]) == 3
    schema = json.loads(user_content)["response_schema"]
    assert "ontwerpacties" in schema and "aanbevelingen" not in schema
    assert result["evidence_provenance"] == evidence()["provenance"]
    assert "secret-value" not in json.dumps(result)


def test_official_deepseek_request_disables_thinking_and_enables_json(monkeypatch):
    captured = {}

    def fake_urlopen(http_request, timeout):
        captured["payload"] = json.loads(http_request.data)
        return FakeResponse()

    monkeypatch.setattr(ai, "open_ai_request", fake_urlopen)
    result = ai.request_review(endpoint="https://api.deepseek.com/v1", api_key="secret-value",
        model="deepseek-flash", evidence=evidence(), design_goal="Improve daylight")

    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["payload"]["reasoning_effort"] == "none"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert result["model"] == "deepseek-flash"


@pytest.mark.parametrize(("change", "message"), [
    (lambda value: value["berekeningsbewijs"][0].update(metric_fields=["invented"]), "metricveld"),
    (lambda value: value["visuele_observaties"][0].update(view_ids=["north"]), "beeld- of objectbewijs"),
    (lambda value: value["visuele_observaties"][0].update(object_ids=["source:00000000-0000-0000-0000-000000000000"]), "beeld- of objectbewijs"),
    (lambda value: value["ontwerpacties"][0].update(evidence_refs=["metric:invented"]), "onbekend bewijs"),
])
def test_review_rejects_invented_evidence_references(change, message):
    review = valid_review()
    change(review)
    with pytest.raises(ai.AiError, match=message):
        ai._validate_review(review, evidence())


def test_review_accepts_dynamic_metric_fields_present_in_run_evidence():
    current_evidence = evidence()
    current_evidence["metric_fields"].add("shadow_mean_hours")
    review = valid_review()
    review["berekeningsbewijs"][0]["metric_fields"] = ["shadow_mean_hours"]
    review["ontwerpacties"][0]["controle_metric_fields"] = ["shadow_mean_hours"]
    review["ontwerpacties"][0]["evidence_refs"] = [
        "view:overview", "object:" + OBJECT_ID, "metric:shadow_mean_hours"]
    assert ai._validate_review(review, current_evidence)["berekeningsbewijs"][0]["metric_fields"] == ["shadow_mean_hours"]


def test_external_plain_http_endpoint_is_rejected():
    with pytest.raises(ai.AiError, match="HTTPS"):
        ai.request_review(endpoint="http://example.test/v1", api_key="key", model="model",
                          evidence=evidence(), design_goal="")


@pytest.mark.parametrize("endpoint", [
    "https://user:password@example.test/v1",
    "https://example.test/v1?api_key=secret",
    "https://example.test/v1#secret",
])
def test_endpoint_rejects_embedded_credentials_or_parameters(endpoint):
    with pytest.raises(ai.AiError, match="geen gebruikersgegevens, queryparameters of fragment"):
        ai.request_review(endpoint=endpoint, api_key="key", model="model",
                          evidence=evidence(), design_goal="")


@pytest.mark.parametrize("provider_content", ["not json", json.dumps({"samenvatting": "Onvolledig"})])
def test_review_rejects_malformed_or_incomplete_provider_json(monkeypatch, provider_content):
    class InvalidResponse(FakeResponse):
        def read(self, _amount=-1):
            return json.dumps({"choices": [{"message": {"content": provider_content}}]}).encode()
    monkeypatch.setattr(ai, "open_ai_request", lambda *_args, **_kwargs: InvalidResponse())
    with pytest.raises(ai.AiError, match="AI-(advies|provider)"):
        ai.request_review(endpoint="https://example.test/v1", api_key="key", model="model",
                          evidence=evidence(), design_goal="")


def test_provider_unsupported_image_error_is_exposed_without_fallback(monkeypatch):
    def unsupported(http_request, timeout):
        body = BytesIO(json.dumps({"error": {"message": "image input unsupported"}}).encode())
        raise error.HTTPError(http_request.full_url, 400, "bad request", None, body)
    monkeypatch.setattr(ai, "open_ai_request", unsupported)
    with pytest.raises(ai.AiError, match="HTTP 400.*image input unsupported"):
        ai.request_review(endpoint="https://example.test/v1", api_key="key", model="text-only",
                          evidence=evidence(), design_goal="")


@pytest.mark.parametrize("provider_content", [
    "```json\n" + json.dumps(valid_review()) + "\n```",
    [{"type": "text", "text": json.dumps(valid_review())}],
])
def test_review_accepts_common_compatible_json_content_formats(monkeypatch, provider_content):
    class CompatibleResponse(FakeResponse):
        def read(self, _amount=-1):
            return json.dumps({"choices": [{"message": {"content": provider_content}}]}).encode()
    monkeypatch.setattr(ai, "open_ai_request", lambda *_args, **_kwargs: CompatibleResponse())
    result = ai.request_review(endpoint="https://example.test/v1", api_key="key", model="model",
                               evidence=evidence(), design_goal="")
    assert result["samenvatting"].startswith("The current massing")


def test_review_normalizes_grounded_gemma_style_fields():
    review = valid_review()
    review["beperkingen"] = "Orientation is not verified."
    review["berekeningsbewijs"] = [{"berekening": "Grasshopper reports the gross floor area.", "metric_field": "bvo_m2"}]
    review["visuele_observaties"] = [{"observatie": "The volume is visible.", "view_id": "overview"}]

    result = ai._validate_review(review, evidence())

    assert result["berekeningsbewijs"] == [{"tekst": "Grasshopper reports the gross floor area.", "metric_fields": ["bvo_m2"]}]
    assert result["visuele_observaties"] == [{
        "tekst": "The volume is visible.", "view_ids": ["overview"], "object_ids": [],
        "onzekerheid": "Not specified by the AI model.",
    }]
    assert result["ontwerpacties"][0]["instructie"] == "Widen Volume A to the right in the overview."
    assert result["beperkingen"] == ["Orientation is not verified."]


def test_review_normalizes_grounded_deepseek_evidence_aliases():
    review = valid_review()
    review["berekeningsbewijs"][0]["metric_fields"] = ["metric:bvo_m2"]
    review["visuele_observaties"][0].update(
        view_ids=["view:overview"], object_ids=["volume-a"])
    for action in review["ontwerpacties"]:
        action["element_id"] = "Volume A"
        action["controle_metric_fields"] = ["metric:bvo_m2"]
        action["evidence_refs"] = ["view:overview", "object:volume-a", "metric:bvo_m2"]

    result = ai._validate_review(review, evidence())

    assert result["berekeningsbewijs"][0]["metric_fields"] == ["bvo_m2"]
    assert result["visuele_observaties"][0]["view_ids"] == ["overview"]
    assert result["visuele_observaties"][0]["object_ids"] == [OBJECT_ID]
    assert result["ontwerpacties"][0]["element_id"] == "volume-a"
    assert result["ontwerpacties"][0]["controle_metric_fields"] == ["bvo_m2"]
    assert result["ontwerpacties"][0]["evidence_refs"] == [
        "view:overview", "object:" + OBJECT_ID, "metric:bvo_m2"]


def test_review_adds_grounded_view_anchor_to_concrete_direction():
    review = valid_review()
    review["ontwerpacties"][0]["richting"] = "to the right"

    result = ai._validate_review(review, evidence())

    assert result["ontwerpacties"][0]["richting"] == "to the right in the overview"
    assert result["ontwerpacties"][0]["instructie"] == "Widen Volume A to the right in the overview."


def test_review_rejects_invalid_answer_without_slow_second_generation(monkeypatch):
    invalid = valid_review()
    invalid["ontwerpacties"][0]["richting"] = "adjust somewhere"
    payloads = []

    class SequencedResponse(FakeResponse):
        def read(self, _amount=-1):
            content = json.dumps(invalid)
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def fake_urlopen(http_request, timeout):
        payloads.append(json.loads(http_request.data))
        return SequencedResponse()

    monkeypatch.setattr(ai, "open_ai_request", fake_urlopen)
    with pytest.raises(ai.AiError, match="bruikbaar gestructureerd advies"):
        ai.request_review(endpoint="https://example.test/v1", api_key="secret-value",
                          model="vision-model", evidence=evidence(), design_goal="Meer zicht")
    assert len(payloads) == 1
    assert "image_url" not in payloads[0]["messages"][1]["content"]
    assert "secret-value" not in json.dumps(payloads[0])


@pytest.mark.parametrize(("body", "message"), [
    (b"", "leeg HTTP-antwoord"),
    (b"   \r\n", "leeg HTTP-antwoord"),
    (b"<html>gateway error</html>", "geen geldig chat-completion-antwoord"),
    (b'[]', "ongeldig chat-completion-antwoord"),
    (b'{"choices":[]}', "geen antwoordkeuze"),
])
def test_provider_returns_stable_errors_for_invalid_success_responses(monkeypatch, body, message):
    class Response(FakeResponse):
        def read(self, _amount=-1):
            return body

    monkeypatch.setattr(ai, "open_ai_request", lambda *_args, **_kwargs: Response())
    with pytest.raises(ai.AiError, match=message) as caught:
        ai.request_review(endpoint="https://example.test/v1", api_key="key", model="model",
                          evidence=evidence(), design_goal="")
    assert "Expecting value" not in str(caught.value)


@pytest.mark.parametrize(("finish_reason", "message"), [
    ("length", "uitvoerlimiet"),
    ("content_filter", "content_filter"),
    ("stop", "leeg advies"),
])
def test_provider_explains_empty_model_content(monkeypatch, finish_reason, message):
    class Response(FakeResponse):
        def read(self, _amount=-1):
            return json.dumps({"choices": [{"finish_reason": finish_reason,
                "message": {"content": "", "reasoning_content": "not exposed"}}]}).encode()

    monkeypatch.setattr(ai, "open_ai_request", lambda *_args, **_kwargs: Response())
    with pytest.raises(ai.AiError, match=message) as caught:
        ai.request_review(endpoint="https://example.test/v1", api_key="key", model="model",
                          evidence=evidence(), design_goal="")
    assert "not exposed" not in str(caught.value)


def test_provider_rejects_truncated_partial_content_before_json_parsing(monkeypatch):
    class Response(FakeResponse):
        def read(self, _amount=-1):
            return json.dumps({"choices": [{"finish_reason": "length",
                "message": {"content": '{"samenvatting":"partial'}}]}).encode()

    monkeypatch.setattr(ai, "open_ai_request", lambda *_args, **_kwargs: Response())
    with pytest.raises(ai.AiError, match="uitvoerlimiet") as caught:
        ai.request_review(endpoint="https://example.test/v1", api_key="key", model="model",
                          evidence=evidence(), design_goal="")
    assert "JSON" not in str(caught.value)


def test_review_rejects_plain_text_without_parser_details(monkeypatch):
    class Response(FakeResponse):
        def read(self, _amount=-1):
            return json.dumps({"choices": [{"message": {"content": "not json"}}]}).encode()

    monkeypatch.setattr(ai, "open_ai_request", lambda *_args, **_kwargs: Response())
    with pytest.raises(ai.AiError, match="geen geldig JSON-advies") as caught:
        ai.request_review(endpoint="https://example.test/v1", api_key="key", model="model",
                          evidence=evidence(), design_goal="")
    assert "line 1 column 1" not in str(caught.value)


def test_design_elements_are_stably_labelled_and_projected():
    objects = [{
        "id": OBJECT_ID, "classification": "analysis_volume",
        "bounds_m": {"min": [-10, -20, 0], "max": [10, 20, 30]},
    }]
    views = [{"id": "overview", "width": 1200, "height": 800, "fov_degrees": 40,
              "camera_position": [100, -100, 100], "camera_target": [0, 0, 15],
              "camera_up": [0, 0, 1]}]
    elements = ai.build_design_elements(objects, views)
    assert elements[0]["element_id"] == "volume-a"
    assert elements[0]["label"] == "Volume A"
    assert elements[0]["dimensions_m"] == [20.0, 40.0, 30.0]
    assert "overview" in elements[0]["view_positions"]["overview"]
    assert set(elements[0]["image_coordinates_pct"]["overview"]) == {"x", "y"}


def test_massa_fase_2_three_volumes_get_distinct_spatial_labels():
    objects = [
        {"id": "source:155cb401-0af6-449d-98c5-42c06b65e63c", "classification": "analysis_volume",
         "bounds_m": {"min": [51.48, -100.52, 0], "max": [120.17, -11.04, 58]}},
        {"id": "source:5ce77872-eb3a-4742-8353-86f8050d54b4", "classification": "analysis_volume",
         "bounds_m": {"min": [-7.63, -24.51, 2.35], "max": [75.47, 109.10, 58.35]}},
        {"id": "source:a25e9128-a38a-4cd0-8746-5c33ed0f1428", "classification": "analysis_volume",
         "bounds_m": {"min": [-60.79, 139.76, 4.07], "max": [12.84, 227.78, 60.07]}},
    ]
    views = [{"id": "overview", "width": 1200, "height": 800, "fov_degrees": 40,
              "camera_position": [730.48, -1025.54, 766.59], "camera_target": [0.23, -3.20, 36.35],
              "camera_up": [0, 0, 1]}]
    elements = ai.build_design_elements(objects, views)
    assert [item["label"] for item in elements] == ["Volume A", "Volume B", "Volume C"]
    assert [item["object_id"] for item in elements] == [item["id"] for item in objects]
    assert {item["view_positions"]["overview"].split()[0] for item in elements} == {"left", "centre", "right"}


@pytest.mark.parametrize(("field", "value", "message"), [
    ("richting", "adjust somewhere", "richting"),
    ("testomvang", "slightly larger", "concrete testomvang"),
])
def test_review_rejects_vague_design_actions(field, value, message):
    review = valid_review()
    review["ontwerpacties"][0][field] = value
    with pytest.raises(ai.AiError, match=message):
        ai._validate_review(review, evidence())


@pytest.mark.parametrize(("field", "value", "message"), [
    ("testomvang", "Test an 8 m reduction.", "absolute test dimension"),
    ("verwacht_effect", "This improves visibility.", "conditional hypothesis"),
    ("ontwerpdoel", "Improve PH_TARGET visibility.", "raw evidence identifier"),
    ("ontwerpdoel", "Improve sight_pct.", "raw evidence identifier"),
    ("ontwerpdoel", "Improve visibility visibility.", "repeats a word"),
])
def test_review_rejects_unsupported_or_unedited_prose(field, value, message):
    review = valid_review()
    review["ontwerpacties"][0][field] = value
    with pytest.raises(ai.AiError, match=message):
        ai._validate_review(review, evidence())


def test_review_rejects_legacy_compact_recommendations():
    review = valid_review()
    review["aanbevelingen"] = review.pop("ontwerpacties")
    with pytest.raises(ai.AiError, match="ontwerpacties"):
        ai._validate_review(review, evidence())


def test_review_rejects_duplicate_design_actions():
    review = valid_review()
    review["ontwerpacties"][1] = dict(review["ontwerpacties"][0], prioriteit=2)
    with pytest.raises(ai.AiError, match="verschillende ontwerpacties"):
        ai._validate_review(review, evidence())


def test_review_rejects_horizontal_move_without_verified_site_constraints():
    current_evidence = evidence()
    current_evidence["horizontal_moves_allowed"] = False
    review = valid_review()
    with pytest.raises(ai.AiError, match="plot- en infrastructuurconstraints ontbreken"):
        ai._validate_review(review, current_evidence)


def test_review_accepts_within_footprint_tests_without_site_constraints():
    current_evidence = evidence()
    current_evidence["horizontal_moves_allowed"] = False
    review = valid_review()
    for action, operation, direction in zip(review["ontwerpacties"], ("raise", "lower", "narrow"),
                                             ("up in the overview", "down in the overview", "inward in the overview")):
        action.update(ingreep=operation, richting=direction)
    assert len(ai._validate_review(review, current_evidence)["ontwerpacties"]) == 3


def test_review_accepts_explicitly_negated_horizontal_move_wording():
    current_evidence = evidence()
    current_evidence["horizontal_moves_allowed"] = False
    review = valid_review()
    review["samenvatting"] = "The proposal does not require moving volumes and remains within the current footprint."
    for action, operation, direction in zip(review["ontwerpacties"], ("raise", "lower", "narrow"),
                                             ("up in the overview", "down in the overview", "inward in the overview")):
        action.update(ingreep=operation, richting=direction,
                      ontwerpdoel="Improve performance without moving the volume horizontally.")
    assert len(ai._validate_review(review, current_evidence)["ontwerpacties"]) == 3


def test_review_rejects_move_proposal_after_negated_move_wording():
    current_evidence = evidence()
    current_evidence["horizontal_moves_allowed"] = False
    review = valid_review()
    review["samenvatting"] = "No relocation is proposed for Volume A; shift Volume B toward the park."
    with pytest.raises(ai.AiError, match="AI-samenvatting.*horizontale verplaatsing"):
        ai._validate_review(review, current_evidence)


def test_review_rejects_hidden_horizontal_move_in_action_prose():
    current_evidence = evidence()
    current_evidence["horizontal_moves_allowed"] = False
    review = valid_review()
    for action, operation, direction in zip(review["ontwerpacties"], ("raise", "lower", "narrow"),
                                             ("up in the overview", "down in the overview", "inward in the overview")):
        action.update(ingreep=operation, richting=direction)
    review["ontwerpacties"][0]["ontwerpdoel"] = "Shift the volume away from the tunnel."
    with pytest.raises(ai.AiError, match="toelichting.*horizontale verplaatsing"):
        ai._validate_review(review, current_evidence)
