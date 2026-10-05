"""Pantheon entry point.

`make run` (and the background service) execute this file; `make run-dev`
imports `app` from it under uvicorn's reloader. Long-lived components live in
the lifespan, attached to `app.state` so routes can reach them: the module
registry, and the status collectors (host sampler, module monitor, gateway
access log, device monitor), each running in its own background loop.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI

from config import Settings, load_devices_config, load_modules_config
from core.api import create_app
from services.access_log import AccessLog
from services.collectors import run_every
from services.devices import DeviceMonitor, ping_host, resolve_host
from services.history import History
from services.hoststats import HostSampler
from services.module_monitor import ModuleMonitor
from services.overview import record_host

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_app(
    settings: Settings | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    host_sampler: Any = None,
    ping: Callable[[str], Awaitable[float | None]] = ping_host,
    resolve: Callable[[str], Awaitable[str | None]] = resolve_host,
    background: bool = True,
) -> FastAPI:
    """`transport`, `host_sampler`, `ping` and `resolve` let tests stand in for
    the network and the hardware; `background=False` skips the repeating
    loops (each collector still runs once at startup, except the gateway
    probe, which stays unknown (None) until the server is up)."""
    settings = settings or Settings()
    _configure_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        modules = load_modules_config(settings=settings)
        history = History(settings.HISTORY_SECONDS)
        access_log = AccessLog(settings.access_log_path, [m.name for m in modules.enabled])
        sampler = host_sampler or HostSampler()
        async with httpx.AsyncClient(transport=transport) as client:
            monitor = ModuleMonitor(modules, client, timeout=settings.MODULE_HEALTH_TIMEOUT_SECONDS)
            devices = DeviceMonitor(
                load_devices_config(settings=settings),
                access_log,
                stale_s=settings.HEARTBEAT_STALE_SECONDS,
                ping=ping,
                resolve=resolve,
            )

            async def sample_host() -> None:
                sample = await asyncio.to_thread(sampler.sample)
                app.state.host = sample
                record_host(history, sample)

            async def poll_modules() -> None:
                await monitor.poll_once()
                for module in modules.enabled:
                    history.add(f"req:{module.name}", access_log.req_per_min(module.name))

            async def poll_gateway() -> None:
                await monitor.poll_gateway(settings.GATEWAY_PORT)

            async def gateway_loop() -> None:
                # The probe goes through Caddy back to Pantheon's own /health, so
                # it can't succeed until the server is up: wait a moment first.
                await asyncio.sleep(1.0)
                try:
                    await poll_gateway()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("collector gateway failed")
                await run_every(settings.MODULE_POLL_SECONDS, poll_gateway, name="gateway")

            app.state.settings = settings
            app.state.modules = modules
            app.state.history = history
            app.state.access_log = access_log
            app.state.monitor = monitor
            app.state.devices = devices
            app.state.clock = time.time

            app.state.host = {}
            # A failing first tick must not keep the server from starting.
            for tick in (sample_host, poll_modules, devices.ping_round):
                try:
                    await tick()
                except Exception:
                    logger.exception("startup tick %s failed", getattr(tick, "__name__", tick))

            tasks: list[asyncio.Task[None]] = []
            if background:
                tasks = [
                    asyncio.create_task(run_every(settings.HOST_SAMPLE_SECONDS, sample_host, name="host")),
                    asyncio.create_task(run_every(settings.MODULE_POLL_SECONDS, poll_modules, name="modules")),
                    asyncio.create_task(gateway_loop()),
                    asyncio.create_task(run_every(settings.DEVICE_PING_SECONDS, devices.ping_round, name="devices")),
                    asyncio.create_task(access_log.follow()),
                ]
            try:
                yield
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    return create_app(settings, lifespan=lifespan)


app = build_app()


if __name__ == "__main__":
    s = Settings()
    # Behind Caddy every request comes from 127.0.0.1; uvicorn's proxy headers
    # (on by default, trusting 127.0.0.1) give the heartbeat the real device IP.
    uvicorn.run(app, host=s.HOST, port=s.PORT, log_level=s.LOG_LEVEL)
