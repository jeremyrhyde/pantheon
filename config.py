"""Application configuration loaded from the environment or `.env`.

Field names are uppercase to match environment variables — setting `PORT=9000`
overrides the default. Add every new knob here (and to `.env.example`) rather
than reading `os.environ` at the call site, so settings stay discoverable in
one place.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from schemas.devices import DevicesConfig
from schemas.modules import ModulesConfig

# This file sits at the repo root; icon paths and default files hang off it.
REPO_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Runtime settings for the Pantheon server."""

    HOST: str = "0.0.0.0"
    # Pantheon's own app; on a full install it sits behind the gateway.
    PORT: int = 8010
    # Where the Caddy gateway listens — the one address clients use.
    GATEWAY_PORT: int = 8000
    LOG_LEVEL: str = "info"
    WEB_DIR: str = "./web"
    DB_PATH: str = "./pantheon.db"
    MODULES_CONFIG_PATH: str = "./modules.yaml"
    MODULE_HEALTH_TIMEOUT_SECONDS: float = Field(default=1.0, gt=0)

    # Status collectors (all in memory).
    HOST_SAMPLE_SECONDS: float = Field(default=3.0, gt=0)
    MODULE_POLL_SECONDS: float = Field(default=10.0, gt=0)
    DEVICE_PING_SECONDS: float = Field(default=60.0, gt=0)
    HEARTBEAT_STALE_SECONDS: float = Field(default=150.0, gt=0)
    HISTORY_SECONDS: float = Field(default=3600.0, gt=0)
    DEVICES_CONFIG_PATH: str = "./devices.yaml"
    # Caddy's JSON access log. Empty → $XDG_RUNTIME_DIR/pantheon/access.log
    # (tmpfs, no SD-card wear), or ./build/access.log without a runtime dir.
    ACCESS_LOG_PATH: str = ""
    # Set by systemd/logind for the user; read here, never at a call site.
    XDG_RUNTIME_DIR: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def access_log_path(self) -> Path:
        if self.ACCESS_LOG_PATH:
            path = Path(self.ACCESS_LOG_PATH)
        elif self.XDG_RUNTIME_DIR:
            path = Path(self.XDG_RUNTIME_DIR) / "pantheon" / "access.log"
        else:
            path = Path("build") / "access.log"
        return path if path.is_absolute() else REPO_ROOT / path


def load_modules_config(
    path: str | Path | None = None, *, settings: Settings | None = None
) -> ModulesConfig:
    """Read and validate the module registry.

    A missing file yields an empty registry, so Pantheon boots before one is
    written. Raises ``ValueError`` if a module's port is one Pantheon itself
    uses, or its icon path points outside the repo.
    """

    settings = settings or Settings()
    p = Path(path or settings.MODULES_CONFIG_PATH)
    if not p.exists():
        return ModulesConfig()

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    config = ModulesConfig.model_validate(raw)

    reserved = {settings.PORT: "PORT", settings.GATEWAY_PORT: "GATEWAY_PORT"}
    for module in config.modules:
        if module.port in reserved:
            raise ValueError(
                f"module {module.name!r} port {module.port} clashes with "
                f"Pantheon's {reserved[module.port]}"
            )
        if module.icon is not None:
            icon = (REPO_ROOT / module.icon).resolve()
            if not icon.is_relative_to(REPO_ROOT):
                raise ValueError(
                    f"module {module.name!r} icon {module.icon!r} is outside the Pantheon repo"
                )
    return config


def load_devices_config(
    path: str | Path | None = None, *, settings: Settings | None = None
) -> DevicesConfig:
    """Read and validate devices.yaml; a missing file is an empty list."""

    settings = settings or Settings()
    p = Path(path or settings.DEVICES_CONFIG_PATH)
    if not p.exists():
        return DevicesConfig()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return DevicesConfig.model_validate(raw)
