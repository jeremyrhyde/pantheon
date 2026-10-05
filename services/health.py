"""Probe each module's /health on localhost, with a short cache so the home
screen's polling (every 10 s per open screen) doesn't fan out to every module
on every request."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from schemas.modules import ModuleEntry


class HealthChecker:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        timeout: float,
        ttl: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._timeout = timeout
        self._ttl = ttl
        self._clock = clock
        self._cache: dict[str, tuple[float, bool]] = {}

    async def check(self, module: ModuleEntry) -> bool:
        now = self._clock()
        cached = self._cache.get(module.name)
        if cached is not None and now - cached[0] < self._ttl:
            return cached[1]
        try:
            response = await self._client.get(
                f"http://localhost:{module.port}/health", timeout=self._timeout
            )
            healthy = response.status_code == 200
        except httpx.HTTPError:
            healthy = False
        self._cache[module.name] = (now, healthy)
        return healthy
