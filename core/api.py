"""HTTP surface: routers plus the static web UI mounted at `/ui`.

Follows the sibling projects' shape — one `_build_<area>_router()` per area of
the API, all assembled in `create_app`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import Settings


def _build_health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok"}

    return router


def create_app(
    settings: Settings, *, lifespan: Any = None, mount_static: bool = True
) -> FastAPI:
    app = FastAPI(title="Pantheon", lifespan=lifespan)
    app.include_router(_build_health_router())

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/ui/")

    web_dir = Path(settings.WEB_DIR)
    if mount_static and web_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=web_dir, html=True), name="ui")

    return app
