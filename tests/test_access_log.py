
import asyncio
import json

from services.access_log import AccessLog


def line(uri: str, ip: str = "10.0.0.5", ts: float = 1000.0, method: str = "GET") -> str:
    return json.dumps({"ts": ts, "status": 200,
                       "request": {"uri": uri, "method": method, "client_ip": ip}}) + "\n"


def test_api_calls_page_loads_and_viewing(tmp_path):
    log = AccessLog(tmp_path / "a.log", {"apollo", "hermes"}, clock=lambda: 1030.0)
    log.ingest(line("/apollo/", ts=1000))
    log.ingest(line("/apollo/api/today?x=1", ts=1010))
    log.ingest(line("/apollo/assets/x.js", ts=1011))
    act = log.module_activity("apollo")
    assert act == {"last_api_call": 1010.0, "last_visit": 1000.0, "req_per_min": 3}
    assert log.module_activity("hermes") == {"last_api_call": None, "last_visit": None, "req_per_min": 0}
    assert log.last_seen("10.0.0.5") == 1011.0 and log.viewing("10.0.0.5") == "apollo"


def test_pantheon_paths_and_heartbeats(tmp_path):
    log = AccessLog(tmp_path / "a.log", {"apollo"}, clock=lambda: 1000.0)
    log.ingest(line("/status/", ip="10.0.0.6"))
    assert log.viewing("10.0.0.6") == "status"
    log.ingest(line("/api/overview", ip="10.0.0.7"))
    assert log.viewing("10.0.0.7") == "status"
    log.ingest(line("/api/overview?from=home", ip="10.0.0.8"))
    assert log.viewing("10.0.0.8") == "home"
    log.ingest(line("/api/devices/heartbeat", ip="10.0.0.9", method="POST"))
    assert log.last_seen("10.0.0.9") is None            # heartbeats aren't traffic


def test_requests_older_than_a_minute_drop_out(tmp_path):
    now = [1000.0]
    log = AccessLog(tmp_path / "a.log", {"apollo"}, clock=lambda: now[0])
    log.ingest(line("/apollo/api/a", ts=950))
    log.ingest(line("/apollo/api/b", ts=999))
    assert log.module_activity("apollo")["req_per_min"] == 2
    now[0] = 1020.0
    assert log.module_activity("apollo")["req_per_min"] == 1


def test_garbage_is_skipped(tmp_path):
    log = AccessLog(tmp_path / "a.log", {"apollo"})
    for bad in ["not json\n", "{}\n", json.dumps({"ts": "x", "request": {}}) + "\n"]:
        log.ingest(bad)
    assert log.module_activity("apollo")["req_per_min"] == 0


async def test_follow_reads_new_lines_and_survives_rotation(tmp_path):
    path = tmp_path / "access.log"
    path.write_text(line("/apollo/api/old", ts=1))          # before startup: skipped
    log = AccessLog(path, {"apollo"}, clock=lambda: 1000.0)
    task = asyncio.create_task(log.follow(poll_s=0.01))
    await asyncio.sleep(0.05)
    with path.open("a") as f:
        f.write(line("/apollo/api/new", ts=990))
    await asyncio.sleep(0.05)
    assert log.module_activity("apollo")["last_api_call"] == 990.0
    path.rename(tmp_path / "access-1.log")                   # Caddy rolls the file
    path.write_text(line("/apollo/api/rolled", ts=995))
    await asyncio.sleep(0.05)
    task.cancel()
    assert log.module_activity("apollo")["last_api_call"] == 995.0
    assert log.module_activity("apollo")["req_per_min"] == 2


async def test_follow_drains_the_old_file_before_switching_on_rotation(tmp_path):
    path = tmp_path / "access.log"
    path.write_text("")
    log = AccessLog(path, {"apollo"}, clock=lambda: 1000.0)
    task = asyncio.create_task(log.follow(poll_s=0.2))
    await asyncio.sleep(0.05)                                # first pass done, now sleeping
    with path.open("a") as f:
        f.write(line("/apollo/api/last-words", ts=990))
    path.rename(tmp_path / "access-1.log")
    path.write_text(line("/apollo/api/fresh", ts=995))
    await asyncio.sleep(0.4)
    task.cancel()
    assert log.module_activity("apollo")["req_per_min"] == 2


def test_ingest_prunes_old_requests_without_a_reader(tmp_path):
    log = AccessLog(tmp_path / "a.log", {"apollo"}, clock=lambda: 1000.0)
    log.ingest(line("/apollo/api/a", ts=100))
    log.ingest(line("/apollo/api/b", ts=200))
    assert len(log._activity["apollo"].requests) == 1
