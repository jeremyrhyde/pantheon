"""Edge devices: ping + heartbeat + gateway traffic → a state per device.

online      fresh heartbeat, Chromium running, gateway traffic in 5 min
kiosk_issue reachable (ping or fresh heartbeat) but one of those is missing
offline     no ping answer and no fresh heartbeat
Listed devices come from devices.yaml and are pinged; a heartbeat from an
unknown IP adds an unlisted device (never pinged, never counted against the
overall state).
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from schemas.devices import DevicesConfig, Heartbeat
from services.access_log import AccessLog
from services.timeutil import iso

_PING_TIME = re.compile(r"time[=<]([\d.]+)\s*ms")
_TRAFFIC_WINDOW_S = 300.0
_MAX_TRANSITIONS = 20


async def ping_host(ip: str) -> float | None:
    """One ICMP echo with a 1 s wait; the round-trip in ms, or None."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "1", ip,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        return None
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    match = _PING_TIME.search(out.decode(errors="replace"))
    return float(match.group(1)) if match else 0.0


async def resolve_host(host: str) -> str | None:
    """An IPv4 address for `host` (returned as-is if it already is one)."""
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, family=socket.AF_INET)
    except OSError:
        return None
    return infos[0][4][0] if infos else None


@dataclass
class _Device:
    name: str
    host: str
    module: str | None
    listed: bool
    ip: str | None = None
    ping_ms: float | None = None
    ping_ok: bool = False
    heartbeat: Heartbeat | None = None
    heartbeat_at: float | None = None
    state: str | None = None
    issue: str | None = None
    transitions: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=_MAX_TRANSITIONS)
    )


class DeviceMonitor:
    def __init__(
        self,
        config: DevicesConfig,
        access_log: AccessLog,
        *,
        stale_s: float,
        ping: Callable[[str], Awaitable[float | None]] = ping_host,
        resolve: Callable[[str], Awaitable[str | None]] = resolve_host,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._listed = [_Device(d.name, d.host, d.module, True) for d in config.devices]
        self._unlisted: dict[str, _Device] = {}
        self._log = access_log
        self._stale_s = stale_s
        self._ping = ping
        self._resolve = resolve
        self._clock = clock

    async def ping_round(self) -> None:
        async def one(device: _Device) -> None:
            device.ip = await self._resolve(device.host) or device.ip
            device.ping_ms = await self._ping(device.ip) if device.ip else None
            device.ping_ok = device.ping_ms is not None

        await asyncio.gather(*(one(d) for d in self._listed))
        self.refresh()

    def record_heartbeat(self, ip: str, heartbeat: Heartbeat) -> None:
        device = next((d for d in self._listed if ip in (d.ip, d.host)), None)
        if device is None:
            device = self._unlisted.get(ip)
            if device is None:
                device = _Device(heartbeat.hostname, ip, None, False, ip=ip)
                self._unlisted[ip] = device
        device.heartbeat = heartbeat
        device.heartbeat_at = self._clock()
        self.refresh()

    def _evaluate(self, device: _Device) -> tuple[str, str | None]:
        now = self._clock()
        fresh = device.heartbeat_at is not None and now - device.heartbeat_at < self._stale_s
        last = self._log.last_seen(device.ip)
        traffic = last is not None and now - last < _TRAFFIC_WINDOW_S
        if not fresh and not device.ping_ok:
            return "offline", None
        if not fresh:
            return "kiosk_issue", "agent silent"
        if device.heartbeat is not None and not device.heartbeat.chromium_running:
            return "kiosk_issue", "kiosk not running"
        if not traffic:
            return "kiosk_issue", "no traffic"
        return "online", None

    def refresh(self) -> None:
        now = self._clock()
        for device in [*self._listed, *self._unlisted.values()]:
            state, device.issue = self._evaluate(device)
            if device.state is not None and state != device.state:
                device.transitions.append({"at": iso(now), "from": device.state, "to": state})
            device.state = state

    def snapshot(self) -> list[dict[str, Any]]:
        self.refresh()
        return [
            {
                "name": d.name,
                "host": d.host,
                "ip": d.ip,
                "module": d.module,
                "listed": d.listed,
                "state": d.state,
                "issue": d.issue,
                "ping_ms": d.ping_ms,
                "last_heartbeat": iso(d.heartbeat_at),
                "heartbeat": d.heartbeat.model_dump() if d.heartbeat else None,
                "last_seen_module": self._log.viewing(d.ip),
                "last_traffic": iso(self._log.last_seen(d.ip)),
                "transitions": list(d.transitions),
            }
            for d in [*self._listed, *self._unlisted.values()]
        ]
