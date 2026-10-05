"""In-memory ring buffers behind the status screen's sparklines.

Each named series keeps (time, value) points for `window_s` seconds; reads
are downsampled to at most `max_points` by averaging equal buckets, so a
3-second sampler's hour (1200 points) reaches the browser as ~120.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable


class History:
    def __init__(self, window_s: float, *, clock: Callable[[], float] = time.time) -> None:
        self._window = window_s
        self._clock = clock
        self._series: dict[str, deque[tuple[float, float]]] = {}

    def add(self, name: str, value: float | None, *, t: float | None = None) -> None:
        if value is None:
            return
        now = self._clock() if t is None else t
        points = self._series.setdefault(name, deque())
        points.append((now, float(value)))
        cutoff = now - self._window
        while points and points[0][0] < cutoff:
            points.popleft()

    def series(self, name: str, max_points: int = 120) -> list[list[float]]:
        points = list(self._series.get(name, ()))
        if len(points) <= max_points:
            return [[t, round(v, 2)] for t, v in points]
        step = len(points) / max_points
        out = []
        for i in range(max_points):
            bucket = points[int(i * step):int((i + 1) * step)]
            mean = sum(v for _, v in bucket) / len(bucket)
            out.append([bucket[-1][0], round(mean, 2)])
        return out
