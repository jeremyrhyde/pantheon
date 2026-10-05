from types import SimpleNamespace

from services.hoststats import HostSampler, decode_throttled

WIRELESS = """Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE
 face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22
 wlan0: 0000   70.  -52.  -256        0      0      0      0      0        0
"""


def _ps(rx: int):
    return SimpleNamespace(
        cpu_percent=lambda percpu=False: [10.0, 30.0, 20.0, 40.0],
        getloadavg=lambda: (0.5, 0.4, 0.3),
        virtual_memory=lambda: SimpleNamespace(total=4000, available=1000),
        swap_memory=lambda: SimpleNamespace(total=100, used=25),
        disk_usage=lambda path: SimpleNamespace(total=1000, used=400),
        boot_time=lambda: 1000.0,
        net_io_counters=lambda: SimpleNamespace(bytes_recv=rx, bytes_sent=rx // 2),
    )


def _fs(tmp_path, *, temp: str | None = "48250\n", wireless: str | None = WIRELESS):
    proc, sys_ = tmp_path / "proc", tmp_path / "sys"
    (proc / "net").mkdir(parents=True)
    zone = sys_ / "class" / "thermal" / "thermal_zone0"
    zone.mkdir(parents=True)
    if temp is not None:
        (zone / "temp").write_text(temp)
    if wireless is not None:
        (proc / "net" / "wireless").write_text(wireless)
    return str(proc), str(sys_)


def test_full_sample_on_a_pi(tmp_path):
    proc, sys_ = _fs(tmp_path)
    clock = iter([100.0, 103.0])
    rx = iter([1000, 4000])
    ps = _ps(0)
    ps.net_io_counters = lambda: SimpleNamespace(bytes_recv=(v := next(rx)), bytes_sent=v // 2)
    sampler = HostSampler(ps=ps, proc_root=proc, sys_root=sys_, run=lambda args: "throttled=0x50005",
                          clock=lambda: next(clock), wall=lambda: 4600.0, hostname=lambda: "pantheon-pi")
    first = sampler.sample()
    assert first["net_rx_bps"] is None                     # no previous counters yet
    s = sampler.sample()
    assert s["hostname"] == "pantheon-pi" and s["uptime_s"] == 3600
    assert s["cpu_percent"] == 25.0 and s["cpu_per_core"] == [10.0, 30.0, 20.0, 40.0]
    assert s["load"] == [0.5, 0.4, 0.3]
    assert (s["mem_used"], s["mem_total"]) == (3000, 4000)
    assert (s["swap_used"], s["swap_total"]) == (25, 100)
    assert (s["disk_used"], s["disk_total"]) == (400, 1000)
    assert s["temp_c"] == 48.2
    assert s["net_rx_bps"] == 1000.0 and s["net_tx_bps"] == 500.0
    assert s["wifi_dbm"] == -52.0
    assert s["throttle"]["now"] == {"under_voltage": True, "freq_capped": False,
                                    "throttled": True, "soft_temp_limit": False}
    assert s["throttle"]["since_boot"]["under_voltage"] is True
    assert s["throttle"]["since_boot"]["throttled"] is True


def test_missing_pi_features_are_null(tmp_path):
    proc, sys_ = _fs(tmp_path, temp=None, wireless=None)
    s = HostSampler(ps=_ps(0), proc_root=proc, sys_root=sys_, run=lambda args: None).sample()
    assert s["temp_c"] is None and s["wifi_dbm"] is None and s["throttle"] is None


def test_decode_throttled():
    assert decode_throttled(0)["raw"] == "0x0"
    assert decode_throttled(0x80008)["now"]["soft_temp_limit"] is True
    assert decode_throttled(0x80008)["since_boot"]["soft_temp_limit"] is True


def test_cpu_counters_are_primed_at_init():
    calls = []
    ps = _ps(0)
    ps.cpu_percent = lambda percpu=False: calls.append(percpu) or [10.0]
    HostSampler(ps=ps)
    assert calls == [True]
