import json

import httpx
from fastapi.testclient import TestClient

from config import Settings
from main import build_app

YAML = (
    "modules:\n"
    "  - {name: apollo, title: Apollo, port: 8001, icon: web/icon.svg}\n"
    "  - {name: hermes, title: Hermes, port: 8002, icon: web/missing.png}\n"
    "  - {name: pluto, title: Pluto, port: 8004, enabled: false}\n"
)
HOST = {"hostname": "test-pi", "cpu_percent": 12.0, "mem_used": 1, "mem_total": 4,
        "temp_c": 50.0, "net_rx_bps": None, "net_tx_bps": None, "throttle": None}


class FakeSampler:
    def sample(self):
        return dict(HOST)


def transport():
    def handler(request):
        if request.url.port == 8001 and request.url.path == "/health":
            return httpx.Response(200)
        if request.url.port == 8001 and request.url.path == "/api/status":
            return httpx.Response(200, json={"state": "ok", "stats": [{"label": "x", "value": 1}]})
        raise httpx.ConnectError("down", request=request)
    return httpx.MockTransport(handler)


def make(tmp_path, client=("testclient", 50000)):
    (tmp_path / "modules.yaml").write_text(YAML)
    settings = Settings(_env_file=None, PORT=8010, GATEWAY_PORT=8000,
                        MODULES_CONFIG_PATH=str(tmp_path / "modules.yaml"),
                        DEVICES_CONFIG_PATH=str(tmp_path / "devices.yaml"),
                        ACCESS_LOG_PATH=str(tmp_path / "access.log"))
    app = build_app(settings, transport=transport(), host_sampler=FakeSampler(), background=False)
    return TestClient(app, client=client)


def test_overview_snapshot(tmp_path):
    with make(tmp_path) as c:
        body = c.get("/api/overview").json()
    assert body["overall"] == "offline"                    # hermes is down
    # the gateway probe hasn't run yet: unknown, not red
    assert body["host"]["hostname"] == "test-pi" and body["host"]["units"] == {"gateway": None}
    assert body["history"]["cpu"][0][1] == 12.0
    states = {m["name"]: m["state"] for m in body["modules"]}
    assert states == {"apollo": "online", "hermes": "offline", "pluto": "disabled"}
    apollo = body["modules"][0]
    assert apollo["status"]["stats"][0]["label"] == "x" and apollo["req_per_min"] == 0
    assert body["devices"] == []


def test_heartbeat_registers_the_sender_ip(tmp_path):
    with make(tmp_path, client=("192.168.1.42", 50000)) as c:
        ok = c.post("/api/devices/heartbeat", json={"hostname": "edge", "chromium_running": True})
        assert ok.status_code == 200
        assert c.post("/api/devices/heartbeat", json={"hostname": ""}).status_code == 422
        device = c.get("/api/overview").json()["devices"][0]
    assert device["host"] == "192.168.1.42" and device["listed"] is False
    assert device["state"] == "kiosk_issue" and device["issue"] == "no traffic"


def test_module_icon(tmp_path):
    with make(tmp_path) as c:
        assert c.get("/api/modules/apollo/icon").status_code == 200
        assert c.get("/api/modules/hermes/icon").status_code == 404
        assert c.get("/api/modules/pluto/icon").status_code == 404
        assert c.get("/api/modules/nope/icon").status_code == 404


def test_heartbeat_hostname_over_64_chars_is_rejected(tmp_path):
    with make(tmp_path, client=("192.168.1.42", 50000)) as c:
        assert c.post("/api/devices/heartbeat", json={"hostname": "h" * 64, "chromium_running": True}).status_code == 200
        assert c.post("/api/devices/heartbeat", json={"hostname": "h" * 65, "chromium_running": True}).status_code == 422


def test_heartbeat_posts_do_not_count_as_device_traffic(tmp_path):
    ip = "192.168.1.42"
    with make(tmp_path, client=(ip, 50000)) as c:
        assert c.post("/api/devices/heartbeat", json={"hostname": "edge", "chromium_running": True}).status_code == 200
        line = json.dumps({"ts": 1000.0, "status": 200, "request": {
            "uri": "/api/devices/heartbeat", "method": "POST", "client_ip": ip}}) + "\n"
        (tmp_path / "access.log").write_text(line)
        c.app.state.access_log.ingest(line)
        device = c.get("/api/overview").json()["devices"][0]
    assert device["host"] == ip and device["last_traffic"] is None


def test_failing_host_sampler_does_not_abort_startup(tmp_path):
    class Broken:
        def sample(self):
            raise RuntimeError("no sensors")

    (tmp_path / "modules.yaml").write_text(YAML)
    settings = Settings(_env_file=None, PORT=8010, GATEWAY_PORT=8000,
                        MODULES_CONFIG_PATH=str(tmp_path / "modules.yaml"),
                        DEVICES_CONFIG_PATH=str(tmp_path / "devices.yaml"),
                        ACCESS_LOG_PATH=str(tmp_path / "access.log"))
    app = build_app(settings, transport=transport(), host_sampler=Broken(), background=False)
    with TestClient(app) as c:
        res = c.get("/api/overview")
        assert res.status_code == 200
        assert res.json()["host"]["units"] == {"gateway": None}
