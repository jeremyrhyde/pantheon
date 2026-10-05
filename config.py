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

from schemas.modules import ModulesConfig


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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


def load_modules_config(
    path: str | Path | None = None, *, settings: Settings | None = None
) -> ModulesConfig:
    """Read and validate the module registry.

    A missing file yields an empty registry, so Pantheon boots before one is
    written. Raises ``ValueError`` if a module's port is one Pantheon itself
    uses.
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
    return config
