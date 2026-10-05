"""web/kiosk/heartbeat.sh --print, against fixture /proc and /sys files and
fake pgrep / vcgencmd / hostname on PATH."""

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

KIOSK = Path(__file__).resolve().parent.parent / "web" / "kiosk"


def _exe(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def run_agent(
    tmp_path: Path,
    *,
    chromium: bool,
    vcgencmd_out: str = "throttled=0x50000",
    hostname: str = "edge-1",
    second_stat: str | None = None,
    temp: str = "51234",
    proc_hostname: str = "proc-host",
) -> dict:
    repo = tmp_path / "repo"
    (repo / "web" / "kiosk").mkdir(parents=True)
    for name in ("heartbeat.sh", "start-kiosk.sh"):
        shutil.copy(KIOSK / name, repo / "web" / "kiosk" / name)
    (repo / "kiosk.env").write_text("KIOSK_MODULE=apollo\nSERVER_IP_ADDRESS=10.0.0.1\n")

    root = tmp_path / "root"
    (root / "proc").mkdir(parents=True)
    (root / "proc" / "stat").write_text("cpu  100 0 100 800 0 0 0 0 0 0\n")
    (root / "proc" / "meminfo").write_text("MemTotal:  2000000 kB\nMemAvailable:  500000 kB\n")
    (root / "proc" / "uptime").write_text("3600.42 100.0\n")
    zone = root / "sys" / "class" / "thermal" / "thermal_zone0"
    zone.mkdir(parents=True)
    (zone / "temp").write_text(temp + "\n")
    (root / "proc" / "sys" / "kernel").mkdir(parents=True)
    (root / "proc" / "sys" / "kernel" / "hostname").write_text(proc_hostname + "\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _exe(bin_dir / "pgrep", "exit 0" if chromium else "exit 1")
    _exe(bin_dir / "vcgencmd", f'echo "{vcgencmd_out}"')
    (tmp_path / "hostname.txt").write_text(hostname)
    _exe(bin_dir / "hostname", f'cat "{tmp_path / "hostname.txt"}"')
    if second_stat is not None:
        # The agent's gap between the two CPU reads: change /proc/stat there.
        _exe(bin_dir / "sleep", f'echo "{second_stat}" > "{root}/proc/stat"')

    out = subprocess.run(
        ["bash", str(repo / "web" / "kiosk" / "heartbeat.sh"), "--print"],
        env={"PATH": f"{bin_dir}:{os.environ['PATH']}", "HEARTBEAT_ROOT": str(root),
             "HEARTBEAT_CPU_SAMPLE_S": "0"},
        capture_output=True, text=True, check=True, timeout=20,
    )
    return json.loads(out.stdout)


def test_heartbeat_body(tmp_path):
    body = run_agent(tmp_path, chromium=True)
    assert body == {
        "hostname": "edge-1",
        "kiosk_url": "http://10.0.0.1:8000/apollo/",
        "chromium_running": True,
        "uptime_s": 3600.42,
        "cpu_percent": None,          # both /proc/stat reads identical → no delta
        "mem_used_mb": 1464.8,
        "mem_total_mb": 1953.1,
        "temp_c": 51.2,
        "throttled": "0x50000",
        "agent_version": 1,
    }


def test_heartbeat_without_chromium(tmp_path):
    assert run_agent(tmp_path, chromium=False)["chromium_running"] is False


def test_heartbeat_validates_against_the_server_schema(tmp_path):
    from schemas.devices import Heartbeat
    Heartbeat.model_validate(run_agent(tmp_path, chromium=True))


def test_throttled_that_is_not_hex_is_sent_as_null(tmp_path):
    from schemas.devices import Heartbeat
    body = run_agent(tmp_path, chromium=True, vcgencmd_out="error")
    assert body["throttled"] is None
    Heartbeat.model_validate(body)


def test_cpu_percent_is_clamped_to_0_100(tmp_path):
    from schemas.devices import Heartbeat
    # Idle went *down* while total went up → raw figure is 200 %.
    body = run_agent(tmp_path, chromium=True, second_stat="cpu  300 0 100 700 0 0 0 0 0 0")
    assert body["cpu_percent"] == 100
    Heartbeat.model_validate(body)


def test_long_hostname_is_truncated_to_64(tmp_path):
    from schemas.devices import Heartbeat
    body = run_agent(tmp_path, chromium=True, hostname="h" * 100)
    assert body["hostname"] == "h" * 64
    Heartbeat.model_validate(body)


def test_normal_cpu_delta(tmp_path):
    # total 1000 → 1100 (+100), idle 800 → 875 (+75): 25 % busy.
    body = run_agent(tmp_path, chromium=True, second_stat="cpu  125 0 100 875 0 0 0 0 0 0")
    assert body["cpu_percent"] == 25.0


def test_hostname_with_tab_and_quote_is_valid_json(tmp_path):
    from schemas.devices import Heartbeat
    body = run_agent(tmp_path, chromium=True, hostname='a\tb"c')
    assert body["hostname"] == 'a\tb"c'
    Heartbeat.model_validate(body)


def test_temp_out_of_range_is_null(tmp_path):
    assert run_agent(tmp_path / "hot", chromium=True, temp="200000")["temp_c"] is None
    assert run_agent(tmp_path / "cold", chromium=True, temp="-50000")["temp_c"] is None


def test_empty_hostname_falls_back_to_proc(tmp_path):
    assert run_agent(tmp_path, chromium=True, hostname="")["hostname"] == "proc-host"
