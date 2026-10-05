"""HTTP surface: routers plus the static web UI served at `/`.

Follows the sibling projects' shape — one `_build_<area>_router()` per area of
the API, all assembled in `create_app`. Same contract as the modules: API
under `/api/`, `/health` at the root, UI at `/` mounted last.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import REPO_ROOT, Settings
from schemas.devices import Heartbeat
from services.overview import build_overview


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
        """Every registered module, `healthy` = online or degraded (`null`
        when disabled). Kept for older clients; the pages use /api/overview."""
        state = request.app.state
        rows = []
        for m in state.modules.modules:
            status = state.monitor.state(m)
            rows.append({
                "name": m.name,
                "title": m.title,
                "path": m.path,
                "enabled": m.enabled,
                "healthy": None if status == "disabled" else status in ("online", "degraded"),
            })
        return rows

    @router.get("/{name}/icon")
    async def module_icon(name: str, request: Request) -> FileResponse:
        module = next((m for m in request.app.state.modules.modules if m.name == name), None)
        if module is None or module.icon is None:
            raise HTTPException(status_code=404, detail="no icon")
        path = REPO_ROOT / module.icon
        if not path.is_file():
            raise HTTPException(status_code=404, detail="no icon")
        return FileResponse(path)

    return router


def _build_overview_router() -> APIRouter:
    router = APIRouter(tags=["status"])

    @router.get("/overview")
    async def overview(request: Request) -> dict[str, Any]:
        state = request.app.state
        return build_overview(
            host=state.host,
            history=state.history,
            modules=state.modules,
            monitor=state.monitor,
            access_log=state.access_log,
            devices=state.devices,
            now=state.clock(),
        )

    return router


def _build_devices_router() -> APIRouter:
    router = APIRouter(prefix="/devices", tags=["devices"])

    @router.post("/heartbeat")
    async def heartbeat(body: Heartbeat, request: Request) -> dict[str, bool]:
        ip = request.client.host if request.client else "unknown"
        request.app.state.devices.record_heartbeat(ip, body)
        return {"ok": True}

    return router


def create_app(
    settings: Settings, *, lifespan: Any = None, mount_static: bool = True
) -> FastAPI:
    app = FastAPI(title="Pantheon", lifespan=lifespan)
    app.include_router(_build_health_router())

    api = APIRouter(prefix="/api")
    for build in (_build_modules_router, _build_overview_router, _build_devices_router):
        api.include_router(build())
    app.include_router(api)

    web_dir = Path(settings.WEB_DIR)
    if mount_static and web_dir.is_dir():
        # Last: a mount at "/" shadows any route registered after it.
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="ui")

    return app
