"""Poll every enabled module's /health and optional /api/status.

State rules (spec §1): online = /health OK and status ok/absent; degraded =
/health OK but status degraded/error, or exactly one missed check after an
earlier success (stale); offline = two misses in a row, or never reached;
disabled = enabled: false. One module's odd failure never affects another.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from schemas.modules import ModuleEntry, ModulesConfig
from schemas.status import ModuleStatus
from services.timeutil import iso

logger = logging.getLogger(__name__)


@dataclass
class _Probe:
    failures: int = 0
    ever_ok: bool = False
    last_ok: float | None = None
    latency_ms: float | None = None
    status: dict[str, Any] | None = None


class ModuleMonitor:
    def __init__(
        self,
        modules: ModulesConfig,
        client: httpx.AsyncClient,
        *,
        timeout: float,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._modules = modules
        self._client = client
        self._timeout = timeout
        self._clock = clock
        self._probes = {m.name: _Probe() for m in modules.enabled}
        self._invalid_logged: set[str] = set()
        self.gateway_ok: bool | None = None

    async def poll_once(self) -> None:
        await asyncio.gather(*(self._poll(m) for m in self._modules.enabled))

    async def poll_gateway(self, port: int) -> None:
        self.gateway_ok = await self._get_ok(f"http://localhost:{port}/health")

    async def _poll(self, module: ModuleEntry) -> None:
        probe = self._probes[module.name]
        started = time.perf_counter()
        if not await self._get_ok(f"http://localhost:{module.port}/health"):
            probe.failures += 1
            if probe.failures >= 2:
                probe.status = None
                probe.latency_ms = None
            return
        probe.failures = 0
        probe.ever_ok = True
        probe.last_ok = self._clock()
        probe.latency_ms = round((time.perf_counter() - started) * 1000, 1)
        probe.status = await self._fetch_status(module)

    async def _get_ok(self, url: str) -> bool:
        try:
            response = await self._client.get(url, timeout=self._timeout)
        except Exception:  # any failure is just "not OK" for this one target
            return False
        return response.status_code == 200

    async def _fetch_status(self, module: ModuleEntry) -> dict[str, Any] | None:
        try:
            response = await self._client.get(
                f"http://localhost:{module.port}/api/status", timeout=self._timeout
            )
        except Exception:
            return None
        if response.status_code != 200:
            return None
        try:
            return ModuleStatus.model_validate(response.json()).model_dump()
        except Exception:
            if module.name not in self._invalid_logged:
                logger.warning("module %s: /api/status has an unexpected shape; ignoring it", module.name)
                self._invalid_logged.add(module.name)
            return None

    def state(self, module: ModuleEntry) -> str:
        if not module.enabled:
            return "disabled"
        probe = self._probes.get(module.name)
        if probe is None or not probe.ever_ok or probe.failures >= 2:
            return "offline"
        if probe.failures == 1:
            return "degraded"
        if probe.status and probe.status["state"] in ("degraded", "error"):
            return "degraded"
        return "online"

    def snapshot(self, module: ModuleEntry) -> dict[str, Any]:
        probe = self._probes.get(module.name)
        return {
            "name": module.name,
            "title": module.title,
            "path": module.path,
            "enabled": module.enabled,
            "state": self.state(module),
            "latency_ms": probe.latency_ms if probe else None,
            "last_ok": iso(probe.last_ok) if probe else None,
            "status": probe.status if probe else None,
        }
