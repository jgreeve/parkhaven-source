from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import ssl
import threading

import pytest
import trustme

from app import ai


EVIDENCE = {
    "structured": {"berekende_resultaten": {"bvo_m2": 1000}},
    "images": [{"id": view_id, "data_url": "data:image/png;base64,AA=="}
               for view_id in ("top", "overview", "facade-side", "park-side")],
    "object_ids": set(), "view_ids": {"top", "overview", "facade-side", "park-side"},
    "metric_fields": {"bvo_m2"}, "provenance": {"view_evidence_sha256": "1" * 64},
}


VALID_REVIEW = {"samenvatting": "TLS werkt.",
                "berekeningsbewijs": [{"tekst": "BVO.", "metric_fields": ["bvo_m2"]}],
                "visuele_observaties": [],
                "aanbevelingen": [{"tekst": "Behouden.", "evidence_refs": ["metric:bvo_m2"]}],
                "beperkingen": ["Geen noordbewijs."]}


@pytest.fixture
def private_server(tmp_path, monkeypatch):
    servers = []
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")

    def start(*, expired=False, pin=None, origin_override=None, redirect=None):
        ca = trustme.CA()
        dates = {}
        if expired:
            dates = {"not_before": datetime.now(timezone.utc) - timedelta(days=2),
                     "not_after": datetime.now(timezone.utc) - timedelta(days=1)}
        certificate = ca.issue_cert("private-service.test", **dates)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        certificate.configure_cert(context)
        received = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                received.append({"path": self.path, "key": self.headers.get("Authorization"),
                                 "payload": json.loads(self.rfile.read(int(self.headers["Content-Length"])))})
                body = json.dumps({"choices": [{"message": {"content": json.dumps(VALID_REVIEW)}}]}).encode()
                self.send_response(302 if redirect else 200)
                if redirect:
                    self.send_header("Location", redirect)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        origin = f"https://127.0.0.1:{server.server_port}"
        ca.cert_pem.write_to_path(tmp_path / "ca.pem")
        leaf = ssl.PEM_cert_to_DER_cert(certificate.cert_chain_pems[0].bytes().decode())
        config = tmp_path / "ai-trust.json"
        config.write_text(json.dumps({"endpoints": [{
            "origin": origin_override(origin) if origin_override else origin,
            "ca_file": "ca.pem", "certificate_sha256": pin or hashlib.sha256(leaf).hexdigest(),
        }]}), encoding="utf-8")
        monkeypatch.setenv("PARKHAVEN_AI_TRUST_CONFIG", str(config))
        return origin + "/spark/v1", received

    yield start
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def review(endpoint):
    return ai.request_review(endpoint=endpoint, api_key="dummy-test-key", model="test-model",
                             evidence=EVIDENCE, design_goal="Meer zicht")


def test_private_ca_and_pin_accept_ip_despite_certificate_name(private_server):
    endpoint, received = private_server()
    result = review(endpoint)
    assert result["samenvatting"] == "TLS werkt."
    assert received[0]["path"] == "/spark/v1/chat/completions"
    assert received[0]["key"] == "Bearer dummy-test-key"
    assert received[0]["payload"]["model"] == "test-model"
    assert "dummy-test-key" not in json.dumps(result)


def test_changed_certificate_pin_blocks_before_api_key_is_sent(private_server):
    endpoint, received = private_server(pin="0" * 64)
    with pytest.raises(ai.AiError, match="certificaat is gewijzigd"):
        review(endpoint)
    assert received == []


@pytest.mark.parametrize("change", [lambda origin: origin.replace("127.0.0.1", "localhost"),
                                     lambda origin: origin.rsplit(":", 1)[0] + ":1",
                                     lambda origin: origin.replace("https:", "http:")])
def test_trust_never_applies_to_another_host_port_or_protocol(private_server, change):
    endpoint, received = private_server(origin_override=change)
    with pytest.raises(ai.AiError, match="CERTIFICATE_VERIFY_FAILED"):
        review(endpoint)
    assert received == []


def test_pinned_certificate_still_requires_valid_dates(private_server):
    endpoint, received = private_server(expired=True)
    with pytest.raises(ai.AiError, match="certificate has expired"):
        review(endpoint)
    assert received == []


def test_redirect_cannot_send_api_key_to_another_origin(private_server):
    endpoint, received = private_server(redirect="http://127.0.0.1:1/steal")
    with pytest.raises(ai.AiError, match="andere host, poort of protocol"):
        review(endpoint)
    assert len(received) == 1  # Only the original, authenticated TLS request.


def test_invalid_pin_configuration_does_not_disable_verification(private_server):
    endpoint, received = private_server(pin="not-a-fingerprint")
    with pytest.raises(ai.AiError, match="ongeldige SHA-256"):
        review(endpoint)
    assert received == []
