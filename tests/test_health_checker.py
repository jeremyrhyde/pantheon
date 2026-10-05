import httpx

from schemas.modules import ModuleEntry
from services.health import HealthChecker

UP = ModuleEntry(name="up", title="Up", port=8001)
ERR = ModuleEntry(name="err", title="Err", port=8002)
SLOW = ModuleEntry(name="slow", title="Slow", port=8003)


def _client(calls: list[int]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.port)
        assert request.url.path == "/health"
        if request.url.port == 8001:
            return httpx.Response(200, json={"status": "ok"})
        if request.url.port == 8002:
            return httpx.Response(500)
        raise httpx.ConnectTimeout("timed out", request=request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_check_reports_up_error_and_timeout():
    async with _client([]) as client:
        checker = HealthChecker(client, timeout=0.5)
        assert await checker.check(UP) is True
        assert await checker.check(ERR) is False
        assert await checker.check(SLOW) is False


async def test_results_are_cached_for_ttl():
    calls: list[int] = []
    now = [100.0]
    async with _client(calls) as client:
        checker = HealthChecker(client, timeout=0.5, ttl=5.0, clock=lambda: now[0])
        await checker.check(UP)
        await checker.check(UP)
        assert calls == [8001]
        now[0] += 6.0
        await checker.check(UP)
        assert calls == [8001, 8001]


async def test_any_probe_failure_marks_only_that_module_unhealthy():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.port == 8001:
            return httpx.Response(200)
        raise RuntimeError("client is closing")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        checker = HealthChecker(client, timeout=0.5)
        assert await checker.check(ERR) is False
        assert await checker.check(UP) is True
