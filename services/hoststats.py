"""Sample the main Pi's health for the status screen.

psutil covers CPU, memory, disk and network; the Pi-specific bits come from
files and `vcgencmd`. Anything a host doesn't have (a laptop has no
`vcgencmd`, a wired Pi no /proc/net/wireless) comes back as None, and the UI
hides that readout. Every source is injectable for tests.
"""

from __future__ import annotations

import socket
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil

# vcgencmd get_throttled bits: low nibble = now, the same bits << 16 = since boot.
_THROTTLE_FLAGS = (
    ("under_voltage", 0),
    ("freq_capped", 1),
    ("throttled", 2),
    ("soft_temp_limit", 3),
)


def decode_throttled(value: int) -> dict[str, Any]:
    return {
        "raw": hex(value),
        "now": {name: bool(value >> bit & 1) for name, bit in _THROTTLE_FLAGS},
        "since_boot": {name: bool(value >> (bit + 16) & 1) for name, bit in _THROTTLE_FLAGS},
    }


def _run(args: list[str]) -> str | None:
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


class HostSampler:
    def __init__(
        self,
        *,
        ps: Any = psutil,
        proc_root: str = "/proc",
        sys_root: str = "/sys",
        run: Callable[[list[str]], str | None] = _run,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], float] = time.time,
        hostname: Callable[[], str] = socket.gethostname,
    ) -> None:
        self._ps = ps
        self._proc = Path(proc_root)
        self._sys = Path(sys_root)
        self._run = run
        self._clock = clock
        self._wall = wall
        self._hostname = hostname
        self._prev_net: tuple[float, int, int] | None = None
        self._ps.cpu_percent(percpu=True)  # prime the counters so the first sample isn't a fake 0

    def sample(self) -> dict[str, Any]:
        per_core = [round(v, 1) for v in self._ps.cpu_percent(percpu=True)]
        vm = self._ps.virtual_memory()
        swap = self._ps.swap_memory()
        disk = self._ps.disk_usage("/")
        rx_bps, tx_bps = self._net_rates()
        return {
            "hostname": self._hostname(),
            "uptime_s": round(self._wall() - self._ps.boot_time()),
            "cpu_percent": round(sum(per_core) / len(per_core), 1) if per_core else None,
            "cpu_per_core": per_core,
            "load": [round(v, 2) for v in self._ps.getloadavg()],
            "mem_used": vm.total - vm.available,
            "mem_total": vm.total,
            "swap_used": swap.used,
            "swap_total": swap.total,
            "disk_used": disk.used,
            "disk_total": disk.total,
            "temp_c": self._temp(),
            "net_rx_bps": rx_bps,
            "net_tx_bps": tx_bps,
            "wifi_dbm": self._wifi(),
            "throttle": self._throttle(),
        }

    def _net_rates(self) -> tuple[float | None, float | None]:
        counters = self._ps.net_io_counters()
        now = self._clock()
        prev, self._prev_net = self._prev_net, (now, counters.bytes_recv, counters.bytes_sent)
        if prev is None or now <= prev[0]:
            return None, None
        elapsed = now - prev[0]
        return (
            round((counters.bytes_recv - prev[1]) / elapsed, 1),
            round((counters.bytes_sent - prev[2]) / elapsed, 1),
        )

    def _temp(self) -> float | None:
        try:
            raw = (self._sys / "class/thermal/thermal_zone0/temp").read_text().strip()
            return round(int(raw) / 1000, 1)
        except (OSError, ValueError):
            return None

    def _wifi(self) -> float | None:
        try:
            lines = (self._proc / "net/wireless").read_text().splitlines()[2:]
        except OSError:
            return None
        for line in lines:
            fields = line.split()
            if len(fields) >= 4:
                try:
                    return float(fields[3].rstrip("."))
                except ValueError:
                    continue
        return None

    def _throttle(self) -> dict[str, Any] | None:
        out = self._run(["vcgencmd", "get_throttled"])
        if not out or "=" not in out:
            return None
        try:
            return decode_throttled(int(out.strip().split("=", 1)[1], 16))
        except ValueError:
            return None
