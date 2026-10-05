"""HTTP surface: routers plus the static web UI served at `/`.

Follows the sibling projects' shape — one `_build_<area>_router()` per area of
the API, all assembled in `create_app`. Same contract as the modules: API
under `/api/`, `/health` at the root, UI at `/` mounted last.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from config import Settings
from schemas.modules import ModulesConfig
from services.health import HealthChecker


def _build_health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok"}

    return router


def _build_modules_router() -> APIRouter:
    router = APIRouter(prefix="/modules", tags=["modules"])

    @router.get("/")
    async def list_modules(request: Request) -> list[dict[str, Any]]:
        """Every registered module, with `healthy` from its own /health
        (`null` when the module is disabled)."""
        modules: ModulesConfig = request.app.state.modules
        checker: HealthChecker = request.app.state.health_checker
        enabled = modules.enabled
        results = await asyncio.gather(*(checker.check(m) for m in enabled))
        healthy = {m.name: ok for m, ok in zip(enabled, results)}
        return [
            {
                "name": m.name,
                "title": m.title,
                "path": m.path,
                "enabled": m.enabled,
                "healthy": healthy.get(m.name),
            }
            for m in modules.modules
        ]

    return router


def create_app(
    settings: Settings, *, lifespan: Any = None, mount_static: bool = True
) -> FastAPI:
    app = FastAPI(title="Pantheon", lifespan=lifespan)
    app.include_router(_build_health_router())

    api = APIRouter(prefix="/api")
    api.include_router(_build_modules_router())
    app.include_router(api)

    web_dir = Path(settings.WEB_DIR)
    if mount_static and web_dir.is_dir():
        # Last: a mount at "/" shadows any route registered after it.
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="ui")

    return app
