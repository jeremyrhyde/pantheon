from pathlib import Path

import pytest

from config import REPO_ROOT, Settings, load_devices_config
from schemas.devices import Heartbeat
from schemas.status import ModuleStatus


def _settings(tmp_path: Path, text: str | None) -> Settings:
    path = tmp_path / "devices.yaml"
    if text is not None:
        path.write_text(text)
    return Settings(_env_file=None, DEVICES_CONFIG_PATH=str(path))


def test_missing_devices_file_is_empty(tmp_path):
    assert load_devices_config(settings=_settings(tmp_path, None)).devices == []


def test_example_devices_file_loads():
    config = load_devices_config(REPO_ROOT / "devices.yaml.example")
    assert [(d.name, d.module) for d in config.devices] == [("bathroom", "apollo"), ("desk", "status")]


@pytest.mark.parametrize("text, message", [
    ("devices:\n  - {name: a, host: 10.0.0.1}\n  - {name: a, host: 10.0.0.2}\n", "duplicate device name: a"),
    ("devices:\n  - {name: a, host: 10.0.0.1}\n  - {name: b, host: 10.0.0.1}\n", "duplicate device host: 10.0.0.1"),
    ("devices:\n  - {name: a, host: 'x;y'}\n", "host"),
])
def test_rejects_bad_device_files(tmp_path, text, message):
    with pytest.raises(ValueError, match=message):
        load_devices_config(settings=_settings(tmp_path, text))


def test_heartbeat_accepts_the_agent_body_and_ignores_extras():
    hb = Heartbeat.model_validate({
        "hostname": "edge-1", "kiosk_url": "http://10.0.0.1:8000/apollo/",
        "chromium_running": True, "uptime_s": 12, "cpu_percent": 3.5,
        "mem_used_mb": 400, "mem_total_mb": 1900, "temp_c": 48.2,
        "throttled": "0x0", "agent_version": 1, "future_field": "ignored"})
    assert hb.chromium_running and hb.temp_c == 48.2


@pytest.mark.parametrize("body", [
    {"chromium_running": True},                                   # no hostname
    {"hostname": "x" * 65, "chromium_running": True},             # too long
    {"hostname": "a", "chromium_running": True, "throttled": "zz"},
    {"hostname": "a", "chromium_running": True, "cpu_percent": 250},
])
def test_heartbeat_rejects_junk(body):
    with pytest.raises(ValueError):
        Heartbeat.model_validate(body)


def test_module_status_shape():
    status = ModuleStatus.model_validate({"state": "ok", "stats": [{"label": "x", "value": 3}]})
    assert status.stats[0].kind == "number" and status.stats[0].warn is False
    with pytest.raises(ValueError):
        ModuleStatus.model_validate({"state": "fine"})
