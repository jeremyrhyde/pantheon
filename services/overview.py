"""Assemble GET /api/overview — the one snapshot both pages poll."""

from __future__ import annotations

from typing import Any

from schemas.modules import ModulesConfig
from services.access_log import AccessLog
from services.devices import DeviceMonitor
from services.history import History
from services.module_monitor import ModuleMonitor
from services.timeutil import iso

HOST_TEMP_WARN_C = 80.0  # the Pi starts throttling here


def record_host(history: History, sample: dict[str, Any]) -> None:
    history.add("cpu", sample.get("cpu_percent"))
    if sample.get("mem_total"):
        history.add("mem", 100 * sample["mem_used"] / sample["mem_total"])
    if sample.get("disk_total"):
        history.add("disk", 100 * sample["disk_used"] / sample["disk_total"])
    history.add("temp", sample.get("temp_c"))
    history.add("net_rx", sample.get("net_rx_bps"))
    history.add("net_tx", sample.get("net_tx_bps"))


def overall_state(
    modules: list[dict[str, Any]], devices: list[dict[str, Any]], host: dict[str, Any]
) -> str:
    enabled = [m for m in modules if m["enabled"]]
    if any(m["state"] == "offline" for m in enabled):
        return "offline"
    throttle = host.get("throttle")
    host_warn = (host.get("temp_c") or 0) >= HOST_TEMP_WARN_C or bool(
        throttle and any(throttle["now"].values())
    )
    if (
        host_warn
        or any(m["state"] == "degraded" for m in enabled)
        or any(d["listed"] and d["state"] in ("kiosk_issue", "offline") for d in devices)
    ):
        return "degraded"
    return "online"


def build_overview(
    *,
    host: dict[str, Any],
    history: History,
    modules: ModulesConfig,
    monitor: ModuleMonitor,
    access_log: AccessLog,
    devices: DeviceMonitor,
    now: float,
) -> dict[str, Any]:
    module_rows = []
    for module in modules.modules:
        activity = access_log.module_activity(module.name)
        module_rows.append(
            monitor.snapshot(module)
            | {
                "last_api_call": iso(activity["last_api_call"]),
                "last_visit": iso(activity["last_visit"]),
                "req_per_min": activity["req_per_min"],
                "req_history": history.series(f"req:{module.name}"),
            }
        )
    device_rows = devices.snapshot()
    host_row = host | {"units": {"gateway": monitor.gateway_ok}}
    return {
        "generated_at": iso(now),
        "overall": overall_state(module_rows, device_rows, host_row),
        "host": host_row,
        "history": {name: history.series(name) for name in ("cpu", "mem", "temp", "net_rx", "net_tx", "disk")},
        "modules": module_rows,
        "devices": device_rows,
    }
