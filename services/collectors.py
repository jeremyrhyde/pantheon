"""The loop every status collector runs in."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def run_every(interval: float, tick: Callable[[], Awaitable[None]], *, name: str) -> None:
    """Sleep, tick, repeat — forever. A failing tick is logged, not fatal."""
    while True:
        await asyncio.sleep(interval)
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("collector %s failed", name)
