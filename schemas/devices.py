"""Edge devices: the optional registry (devices.yaml) and the heartbeat the
agent on each edge Pi posts every minute."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeviceEntry(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    # IP or hostname; pinged, and matched against heartbeat source IPs.
    host: str = Field(pattern=r"^[A-Za-z0-9.:-]+$", max_length=253)
    # What it should be showing: a module name or "status". Informational.
    module: str | None = Field(default=None, max_length=64)


class DevicesConfig(BaseModel):
    devices: list[DeviceEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self) -> "DevicesConfig":
        for attr in ("name", "host"):
            seen: set[str] = set()
            for device in self.devices:
                value = getattr(device, attr)
                if value in seen:
                    raise ValueError(f"duplicate device {attr}: {value}")
                seen.add(value)
        return self


class Heartbeat(BaseModel):
    """Body of POST /api/devices/heartbeat (web/kiosk/heartbeat.sh)."""

    model_config = ConfigDict(extra="ignore")

    hostname: str = Field(min_length=1, max_length=64)
    kiosk_url: str | None = Field(default=None, max_length=512)
    chromium_running: bool
    uptime_s: float | None = Field(default=None, ge=0)
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    mem_used_mb: float | None = Field(default=None, ge=0)
    mem_total_mb: float | None = Field(default=None, ge=0)
    temp_c: float | None = Field(default=None, ge=-40, le=150)
    throttled: str | None = Field(default=None, pattern=r"^0x[0-9a-fA-F]+$", max_length=18)
    agent_version: int = Field(default=1, ge=1, le=1000)
