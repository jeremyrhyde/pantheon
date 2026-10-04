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

import uvicorn
from fastapi import FastAPI

from config import Settings
from core.api import create_app


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    _configure_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        # Start components here; stop them after the yield.
        yield

    return create_app(settings, lifespan=lifespan)


app = build_app()


if __name__ == "__main__":
    s = Settings()
    uvicorn.run(app, host=s.HOST, port=s.PORT, log_level=s.LOG_LEVEL)
