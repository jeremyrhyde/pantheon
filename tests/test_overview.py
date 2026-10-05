import asyncio

from services.collectors import run_every
from services.history import History
from services.overview import overall_state, record_host

ON = {"enabled": True, "state": "online"}


def test_overall_state_rules():
    host = {"temp_c": 50, "throttle": None}
    assert overall_state([ON], [], host) == "online"
    assert overall_state([ON, {"enabled": False, "state": "disabled"}], [], host) == "online"
    assert overall_state([{"enabled": True, "state": "offline"}], [], host) == "offline"
    assert overall_state([{"enabled": True, "state": "degraded"}], [], host) == "degraded"
    # devices: listed problems → degraded, never offline; unlisted ignored
    assert overall_state([ON], [{"listed": True, "state": "offline"}], host) == "degraded"
    assert overall_state([ON], [{"listed": False, "state": "offline"}], host) == "online"
    # host warnings
    assert overall_state([ON], [], {"temp_c": 81, "throttle": None}) == "degraded"
    throttled = {"temp_c": 50, "throttle": {"now": {"under_voltage": True}}}
    assert overall_state([ON], [], throttled) == "degraded"


def test_record_host_feeds_history():
    h = History(window_s=100, clock=lambda: 10.0)
    record_host(h, {"cpu_percent": 20, "mem_used": 1, "mem_total": 4, "temp_c": None,
                    "net_rx_bps": 5, "net_tx_bps": 6})
    assert h.series("cpu") == [[10.0, 20.0]] and h.series("mem") == [[10.0, 25.0]]
    assert h.series("temp") == []


async def test_run_every_survives_a_failing_tick():
    calls = []

    async def tick():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    task = asyncio.create_task(run_every(0.01, tick, name="t"))
    await asyncio.sleep(0.06)
    task.cancel()
    assert len(calls) >= 2
