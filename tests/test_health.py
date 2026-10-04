from fastapi.testclient import TestClient

from config import Settings
from main import build_app


def test_health_ok():
    client = TestClient(build_app(Settings()))
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ui_is_served():
    client = TestClient(build_app(Settings()))
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "<title>Pantheon</title>" in resp.text
