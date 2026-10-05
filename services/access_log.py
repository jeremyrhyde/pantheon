"""Follow Caddy's JSON access log to see activity Pantheon can't see itself.

Every request through the gateway is one line. From them: per module, the
last API call, the last page load ("last user visit") and requests in the
last minute; per client IP, when it was last seen and what it was viewing —
which is how an edge kiosk shows as connected. Caddy logs the original
(pre-strip) URI, so the module is the first path segment. The heartbeat
endpoint is ignored: the agent sends it whether or not the kiosk works.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

HEARTBEAT_PATH = "/api/devices/heartbeat"
_WINDOW_S = 60.0


@dataclass
class _Activity:
    last_api_call: float | None = None
    last_visit: float | None = None
    requests: deque[float] = field(default_factory=deque)


class AccessLog:
    def __init__(
        self,
        path: str | Path,
        module_names: Iterable[str],
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._path = Path(path)
        self._modules = set(module_names)
        self._clock = clock
        self._activity: dict[str, _Activity] = {}
        self._clients: dict[str, tuple[float, str]] = {}

    def ingest(self, line: str) -> None:
        try:
            entry = json.loads(line)
            request = entry["request"]
            uri = str(request["uri"])
            ts = float(entry["ts"])
        except (ValueError, KeyError, TypeError):
            return
        ip = request.get("client_ip") or request.get("remote_ip")
        method = request.get("method", "GET")
        path, _, query = uri.partition("?")
        if path == HEARTBEAT_PATH:
            return

        first = path.lstrip("/").split("/", 1)[0]
        if first in self._modules:
            rest = path[len(first) + 1:]
            activity = self._activity.setdefault(first, _Activity())
            activity.requests.append(ts)
            while activity.requests and activity.requests[0] < ts - _WINDOW_S:
                activity.requests.popleft()
            if rest.startswith("/api/"):
                activity.last_api_call = max(ts, activity.last_api_call or ts)
            elif method == "GET" and rest in ("", "/", "/index.html"):
                activity.last_visit = max(ts, activity.last_visit or ts)
            viewing = first
        elif first == "status" or (path == "/api/overview" and "from=home" not in query):
            viewing = "status"
        else:
            viewing = "home"
        if ip:
            self._clients[ip] = (ts, viewing)

    def module_activity(self, name: str) -> dict[str, float | int | None]:
        activity = self._activity.get(name)
        if activity is None:
            return {"last_api_call": None, "last_visit": None, "req_per_min": 0}
        cutoff = self._clock() - _WINDOW_S
        while activity.requests and activity.requests[0] < cutoff:
            activity.requests.popleft()
        return {
            "last_api_call": activity.last_api_call,
            "last_visit": activity.last_visit,
            "req_per_min": len(activity.requests),
        }

    def req_per_min(self, name: str) -> int:
        return int(self.module_activity(name)["req_per_min"] or 0)

    def last_seen(self, ip: str | None) -> float | None:
        seen = self._clients.get(ip) if ip else None
        return seen[0] if seen else None

    def viewing(self, ip: str | None) -> str | None:
        seen = self._clients.get(ip) if ip else None
        return seen[1] if seen else None

    def _drain(self, handle, partial: str) -> str:
        """Ingest the complete lines available from `handle`; return the
        trailing incomplete fragment."""
        while True:
            chunk = handle.readline()
            if not chunk:
                return partial
            if not chunk.endswith("\n"):
                return partial + chunk
            self.ingest(partial + chunk)
            partial = ""

    async def follow(self, poll_s: float = 1.0) -> None:
        """Tail the log forever: skip what's there at startup, reopen on
        rotation, wait quietly while the file doesn't exist."""

        handle = None
        inode = None
        skip_existing = True
        partial = ""
        warned = False
        try:
            while True:
                try:
                    stat = os.stat(self._path)
                    if handle is None or stat.st_ino != inode or stat.st_size < handle.tell():
                        if handle is not None:
                            self._drain(handle, partial)
                            handle.close()
                            handle = None
                        handle = open(self._path, encoding="utf-8", errors="replace")
                        if skip_existing:
                            handle.seek(0, os.SEEK_END)
                        inode = stat.st_ino
                        partial = ""
                    partial = self._drain(handle, partial)
                except FileNotFoundError:
                    pass
                except (OSError, ValueError):
                    if not warned:
                        logger.warning("access log %s: read failed; retrying", self._path, exc_info=True)
                        warned = True
                skip_existing = False
                await asyncio.sleep(poll_s)
        finally:
            if handle is not None:
                handle.close()
