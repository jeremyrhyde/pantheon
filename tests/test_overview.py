import asyncio

import httpx
import pytest

from services.collectors import run_every
from services.history import History
from services.overview import overall_state, record_host

ON = {"enabled": True, "state": "online"}


def test_overall_state_rules():
    host = {"temp_c": 50, "throttle": None}
    assert overall_state([ON], [], host) == "online"
    assert overall_state([ON, {"enabled": False, "state": "disabled"}], [], host) == "online"
    assert overall_state([{"enabled": True, "state": "offline"}], [], host) == "offline"
    assert overall_state([{"enabled": True, "state": "degraded"}], [], host) == "degraded"
    # devices: listed problems → degraded, never offline; unlisted ignored
    assert overall_state([ON], [{"listed": True, "state": "offline"}], host) == "degraded"
    assert overall_state([ON], [{"listed": False, "state": "offline"}], host) == "online"
    assert overall_state([ON], [{"listed": True, "state": "kiosk_issue"}], host) == "degraded"
    assert overall_state([ON], [], {"temp_c": 80, "throttle": None}) == "degraded"
    assert overall_state([ON], [], {"temp_c": 79.9, "throttle": None}) == "online"
    # host warnings
    assert overall_state([ON], [], {"temp_c": 81, "throttle": None}) == "degraded"
    throttled = {"temp_c": 50, "throttle": {"now": {"under_voltage": True}}}
    assert overall_state([ON], [], throttled) == "degraded"


def test_record_host_feeds_history():
    h = History(window_s=100, clock=lambda: 10.0)
    record_host(h, {"cpu_percent": 20, "mem_used": 1, "mem_total": 4, "temp_c": None,
                    "net_rx_bps": 5, "net_tx_bps": 6})
    assert h.series("cpu") == [[10.0, 20.0]] and h.series("mem") == [[10.0, 25.0]]
    assert h.series("temp") == []


async def test_run_every_survives_a_failing_tick():
    calls = []

    async def tick():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    task = asyncio.create_task(run_every(0.01, tick, name="t"))
    await asyncio.sleep(0.06)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) >= 2


async def test_build_overview_shape(tmp_path):
    from schemas.devices import DeviceEntry, DevicesConfig
    from schemas.modules import ModuleEntry, ModulesConfig
    from services.access_log import AccessLog
    from services.devices import DeviceMonitor
    from services.module_monitor import ModuleMonitor
    from services.overview import build_overview

    entry = ModuleEntry(name="a", title="A", port=8001)
    modules = ModulesConfig(modules=[entry])
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200 if r.url.path == "/health" else 404)))
    monitor = ModuleMonitor(modules, client, timeout=0.5, clock=lambda: 100.0)
    async with client:
        await monitor.poll_once()
        await monitor.poll_gateway(8000)
    log = AccessLog(tmp_path / "a.log", {"a"}, clock=lambda: 100.0)

    async def ping(ip):
        return None

    async def resolve(host):
        return host

    devices = DeviceMonitor(DevicesConfig(devices=[DeviceEntry(name="d", host="10.0.0.2")]), log,
                            stale_s=150, ping=ping, resolve=resolve, clock=lambda: 100.0)
    out = build_overview(host={"temp_c": 40, "throttle": None}, history=History(window_s=100, clock=lambda: 100.0),
                         modules=modules, monitor=monitor, access_log=log, devices=devices, now=100.0)
    assert set(out) == {"generated_at", "overall", "host", "history", "modules", "devices"}
    assert out["host"]["units"] == {"gateway": True}
    assert {"name", "title", "path", "enabled", "state", "latency_ms", "last_ok", "status",
            "last_api_call", "last_visit", "req_per_min", "req_history"} <= set(out["modules"][0])
    assert out["devices"][0]["name"] == "d" and out["overall"] == "degraded"
