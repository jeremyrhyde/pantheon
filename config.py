"""Application configuration loaded from the environment or `.env`.

Field names are uppercase to match environment variables — setting `PORT=9000`
overrides the default. Add every new knob here (and to `.env.example`) rather
than reading `os.environ` at the call site, so settings stay discoverable in
one place.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the Pantheon server."""

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"
    WEB_DIR: str = "./web"
    DB_PATH: str = "./pantheon.db"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
