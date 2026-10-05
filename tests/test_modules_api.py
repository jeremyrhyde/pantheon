import httpx
from fastapi.testclient import TestClient

from config import Settings
from main import build_app

YAML = (
    "modules:\n"
    "  - {name: apollo, title: Apollo, port: 8001}\n"
    "  - {name: hermes, title: Hermes, port: 8002}\n"
    "  - {name: hestia, title: Hestia, port: 8003}\n"
    "  - {name: pluto, title: Pluto, port: 8004, enabled: false}\n"
)


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.port == 8001:
            return httpx.Response(200, json={"status": "ok"})
        if request.url.port == 8002:
            return httpx.Response(500)
        raise httpx.ConnectTimeout("timed out", request=request)

    return httpx.MockTransport(handler)


def test_list_modules_with_health(tmp_path):
    (tmp_path / "modules.yaml").write_text(YAML)
    settings = Settings(
        _env_file=None, PORT=8010, GATEWAY_PORT=8000,
        MODULES_CONFIG_PATH=str(tmp_path / "modules.yaml"),
        DEVICES_CONFIG_PATH=str(tmp_path / "devices.yaml"),
        ACCESS_LOG_PATH=str(tmp_path / "access.log"),
    )
    with TestClient(build_app(settings, transport=_transport(), background=False)) as client:
        resp = client.get("/api/modules/")
    assert resp.status_code == 200
    assert resp.json() == [
        {"name": "apollo", "title": "Apollo", "path": "apollo/", "enabled": True, "healthy": True},
        {"name": "hermes", "title": "Hermes", "path": "hermes/", "enabled": True, "healthy": False},
        {"name": "hestia", "title": "Hestia", "path": "hestia/", "enabled": True, "healthy": False},
        {"name": "pluto", "title": "Pluto", "path": "pluto/", "enabled": False, "healthy": None},
    ]
