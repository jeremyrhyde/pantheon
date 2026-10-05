import httpx

from schemas.modules import ModuleEntry, ModulesConfig
from services.module_monitor import ModuleMonitor

A = ModuleEntry(name="a", title="A", port=8001)
OFF = ModuleEntry(name="off", title="Off", port=8009, enabled=False)


def monitor(handler) -> tuple[ModuleMonitor, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ModuleMonitor(ModulesConfig(modules=[A, OFF]), client, timeout=0.5, clock=lambda: 100.0), client


def ok_health(status_body=None, status_code=404):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(status_code, json=status_body)
    return handler


async def test_online_without_api_status():
    m, client = monitor(ok_health())
    async with client:
        await m.poll_once()
    snap = m.snapshot(A)
    assert snap["state"] == "online" and snap["status"] is None
    assert snap["last_ok"] == "1970-01-01T00:01:40Z" and snap["latency_ms"] is not None
    assert m.state(OFF) == "disabled"


async def test_api_status_degraded_makes_the_module_yellow():
    m, client = monitor(ok_health({"state": "degraded", "stats": [{"label": "x", "value": 1}]}, 200))
    async with client:
        await m.poll_once()
    assert m.state(A) == "degraded"
    assert m.snapshot(A)["status"]["stats"][0] == {"label": "x", "value": 1, "kind": "number", "warn": False}


async def test_invalid_api_status_is_ignored():
    m, client = monitor(ok_health({"state": "fine"}, 200))
    async with client:
        await m.poll_once()
    assert m.state(A) == "online" and m.snapshot(A)["status"] is None


async def test_one_miss_is_stale_two_is_offline():
    up = [True]

    def handler(request):
        if not up[0]:
            raise httpx.ConnectError("down", request=request)
        return httpx.Response(200 if request.url.path == "/health" else 404)

    m, client = monitor(handler)
    async with client:
        await m.poll_once()
        assert m.state(A) == "online"
        up[0] = False
        await m.poll_once()
        assert m.state(A) == "degraded"
        await m.poll_once()
        assert m.state(A) == "offline"


async def test_never_reached_is_offline():
    m, client = monitor(lambda r: httpx.Response(500))
    async with client:
        await m.poll_once()
    assert m.state(A) == "offline"


async def test_gateway_probe():
    def handler(request):
        return httpx.Response(200 if request.url.port == 8000 else 500)
    m, client = monitor(handler)
    async with client:
        await m.poll_gateway(8000)
    assert m.gateway_ok is True
