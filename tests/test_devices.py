import json

from schemas.devices import DeviceEntry, DevicesConfig, Heartbeat
from services.access_log import AccessLog
from services.devices import DeviceMonitor


class World:
    def __init__(self, tmp_path):
        self.now = 1000.0
        self.pingable: set[str] = set()
        self.log = AccessLog(tmp_path / "a.log", {"apollo"}, clock=lambda: self.now)
        config = DevicesConfig(devices=[DeviceEntry(name="bath", host="10.0.0.42", module="apollo")])

        async def ping(ip):
            return 3.2 if ip in self.pingable else None

        async def resolve(host):
            return host

        self.devices = DeviceMonitor(config, self.log, stale_s=150, ping=ping, resolve=resolve,
                                     clock=lambda: self.now)

    def traffic(self, ip="10.0.0.42"):
        self.log.ingest(json.dumps({"ts": self.now, "request": {"uri": "/apollo/api/x", "client_ip": ip}}))

    def beat(self, ip="10.0.0.42", chromium=True):
        self.devices.record_heartbeat(ip, Heartbeat(hostname="bath-pi", chromium_running=chromium))

    def row(self, name="bath"):
        return next(d for d in self.devices.snapshot() if d["name"] == name)


async def test_online_kiosk_issue_offline_and_transitions(tmp_path):
    w = World(tmp_path)
    await w.devices.ping_round()
    assert w.row()["state"] == "offline"

    w.pingable.add("10.0.0.42")
    await w.devices.ping_round()
    assert w.row()["state"] == "kiosk_issue" and w.row()["issue"] == "agent silent"

    w.beat(chromium=False)
    assert w.row()["issue"] == "kiosk not running"

    w.beat()
    assert w.row()["issue"] == "no traffic"

    w.traffic()
    row = w.row()
    assert row["state"] == "online" and row["issue"] is None
    assert row["last_seen_module"] == "apollo" and row["ping_ms"] == 3.2

    w.now += 400                     # heartbeat and traffic go stale, ping still answers
    assert w.row()["state"] == "kiosk_issue"
    w.pingable.clear()
    await w.devices.ping_round()
    assert w.row()["state"] == "offline"
    assert [t["to"] for t in w.row()["transitions"]] == ["kiosk_issue", "online", "kiosk_issue", "offline"]


async def test_unlisted_device_appears_from_its_heartbeat(tmp_path):
    w = World(tmp_path)
    w.beat(ip="10.0.0.99")
    row = w.row("bath-pi")
    assert row["listed"] is False and row["host"] == "10.0.0.99"
    assert row["heartbeat"]["hostname"] == "bath-pi"


async def test_transitions_are_capped_at_20(tmp_path):
    w = World(tmp_path)
    for i in range(30):
        w.pingable = {"10.0.0.42"} if i % 2 else set()
        await w.devices.ping_round()
    assert len(w.row()["transitions"]) == 20
