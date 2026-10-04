from io import StringIO

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.desktop_server import read_configuration


TOKEN = "a" * 64
ORIGIN = "http://127.0.0.1:54321"


@pytest.fixture
def desktop_client(monkeypatch):
    monkeypatch.setattr(app.state, "desktop_session", {"token": TOKEN, "authority": "127.0.0.1:54321", "origin": ORIGIN})
    with TestClient(app, base_url=ORIGIN) as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/app.js", "/viewer.js", "/styles.css", "/viewer-assets/three.module.min.js",
                                    "/api/health", "/api/developer/status", "/api/projects",
                                    "/api/site-context", "/api/site-context/aerial.jpg",
                                   "/api/projects/test/runs/test/scene.json",
                                   "/api/projects/test/runs/test/view-evidence",
                                   "/api/projects/test/placement-previews/test/scene.json",
                                   "/projects/test/runs/test/report"])
def test_all_desktop_routes_require_session(desktop_client, path):
    response = desktop_client.get(path)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert desktop_client.get(path, headers={"X-ParkHaven-Session": "b" * 64}).status_code == 401


def test_session_allows_assets_and_health_without_echoing_token(desktop_client):
    for path in ("/", "/app.js", "/viewer.js", "/viewer-assets/OrbitControls.js", "/api/health"):
        response = desktop_client.get(path, headers={"X-ParkHaven-Session": TOKEN})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert TOKEN not in response.text
        assert TOKEN not in str(response.headers)


def test_cross_origin_host_and_unauthenticated_mutations_rejected(desktop_client):
    auth = {"X-ParkHaven-Session": TOKEN}
    assert desktop_client.post("/api/projects", json={}).status_code == 401
    assert desktop_client.get("/api/health", headers={**auth, "Host": "evil.test:54321"}).status_code == 403
    assert desktop_client.post("/api/projects", headers={**auth, "Origin": "http://evil.test"}, json={}).status_code == 403
    assert desktop_client.get("/api/health", headers={**auth, "Origin": ORIGIN}).status_code == 200


@pytest.mark.parametrize("text", ['{}', '{"token": "short"}', '[]', '{', '{"token": null}', '{"token": 42}'])
def test_private_configuration_rejects_invalid_tokens(text):
    with pytest.raises((ValueError, TypeError)):
        read_configuration(StringIO(text))
