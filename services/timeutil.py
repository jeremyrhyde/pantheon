"""Timestamps as the API speaks them: ISO-8601 UTC with a trailing Z."""

from __future__ import annotations

from datetime import datetime, timezone


def iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
