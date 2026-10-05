"""Pantheon entry point.

`make run` (and the background service) execute this file; `make run-dev`
imports `app` from it under uvicorn's reloader. Long-lived components (state
store, event bus, pollers, ...) belong in the lifespan, attached to
`app.state` so routes can reach them.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI

from config import Settings, load_modules_config
from core.api import create_app
from services.health import HealthChecker


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_app(
    settings: Settings | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """`transport` lets tests stand in for the modules' /health endpoints."""
    settings = settings or Settings()
    _configure_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.modules = load_modules_config(settings=settings)
        async with httpx.AsyncClient(transport=transport) as client:
            app.state.health_checker = HealthChecker(
                client, timeout=settings.MODULE_HEALTH_TIMEOUT_SECONDS
            )
            yield

    return create_app(settings, lifespan=lifespan)


app = build_app()


if __name__ == "__main__":
    s = Settings()
    uvicorn.run(app, host=s.HOST, port=s.PORT, log_level=s.LOG_LEVEL)
