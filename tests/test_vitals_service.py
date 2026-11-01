"""The service the daemon holds: GET /vitals, the sampler, and vitals through the hello and the
presence probe into GET /devices (ADR 0017). The probe reads fakes: nothing here spawns
``nvidia-smi`` or depends on this machine's load."""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.peer import devices as peer_devices
from athena.peer import routes as peer_routes
from athena.peer.identity import now_iso
from athena.peer.listener import PeerHost, PeerRequest
from athena.peer.overlay import Overlay
from athena.peer.registry import mint_token
from athena.server import create_app
from athena.vitals import VITALS_STALE_S, VitalsView
from athena.vitals.probe import Memory, Power, Probe, Readers
from athena.vitals.sampler import Sampler
from athena.vitals.service import VitalsService

TOKEN = "t"


class Ram:
    """The fake host's RAM, which a test turns up and down."""

    def __init__(self, pct: float = 40.0, total: int = 64_000) -> None:
        self.pct, self.total = pct, total

    def __call__(self) -> Memory:
        return Memory(self.total, round(self.total * (100 - self.pct) / 100))


class Seal:
    kind = "memory"

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def seal(self, name: str, value: str) -> None:
        self.values[name] = value

    def unseal(self, name: str) -> str | None:
        return self.values.get(name)

    def destroy(self, name: str) -> None:
        self.values.pop(name, None)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def ram() -> Ram:
    return Ram()


@pytest.fixture
def probe(tmp_path: Path, ram: Ram) -> Probe:
    return Probe(
        tmp_path,
        readers=Readers(memory=ram, power=lambda: Power("mains", None)),
        disk=lambda root: 200_000,
        nvidia_smi="nvidia-smi",
        run=lambda argv, timeout: "NVIDIA GeForce RTX 4090, 24564, 1391, 3\n",
        cores=lambda: 16,
    )


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def host(tmp_path: Path, clock: Clock) -> Iterator[PeerHost]:
    opened = PeerHost(
        tmp_path / "peer",
        port=0,
        probe=lambda: Overlay("absent"),
        seal=Seal(),  # type: ignore[arg-type]
        admit_loopback=True,
        now=clock,
    )
    yield opened
    opened.close()


def _pair_pc(host: PeerHost) -> str:
    peer_id = "dev_" + "a" * 12
    host.registry.admit(
        peer_id, name="Desk", kind="pc", grants=["chat"], token=mint_token(), expires_days=None
    )
    host.keys.keep(peer_id, "http://100.64.0.7:17491", mint_token())
    return peer_id


def test_get_vitals_answers_with_a_reading_before_the_sampler_ran(tmp_path: Path, probe: Probe) -> None:
    daemon = Daemon.open(tmp_path / "data", peers=True, peer_port=0)
    try:
        assert daemon.peers is not None
        service = VitalsService(data_dir=tmp_path, host=daemon.peers, probe=probe)
        app = create_app(daemon, token=TOKEN)
        client = TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"})
        # The wiring mounted its own service on the app; it answers with a real shape.
        body = client.get("/vitals").json()
        assert body["ok"] is True
        assert list(body["vitals"]) == list(VitalsView.__annotations__)
        assert service.gate.vitals() is None, "this service was never asked"
        assert TestClient(app).get("/vitals").status_code == 401
    finally:
        daemon.peers.close() if daemon.peers is not None else None
        daemon.store.close()


def test_the_service_serves_its_own_snapshot_on_the_hello_and_devices(host: PeerHost, probe: Probe) -> None:
    service = VitalsService(data_dir=Path("."), host=host, probe=probe)
    assert host.presence.own() is None, "before the first reading there is nothing to say"
    service.vitals()  # takes a reading now
    view = peer_devices.devices(host)[1]["self"]["vitals"]
    assert view is not None and view["room"] == "ok" and view["cores"] == 16
    hello = peer_routes.hello(host, PeerRequest.__new__(PeerRequest))[1]
    assert hello["vitals"] == view


def test_a_vitals_service_that_raises_says_null_never_500(host: PeerHost) -> None:
    def boom() -> VitalsView:
        raise RuntimeError("probe died")

    host.presence.own_vitals = boom
    assert host.presence.own() is None
    assert peer_devices.devices(host)[1]["self"]["vitals"] is None


def test_the_sampler_starts_and_stops_with_the_host_and_asks_the_gpu_on_its_cadence(
    host: PeerHost, tmp_path: Path
) -> None:
    asked: list[float] = []

    def smi(argv: Any, timeout: float) -> str:
        asked.append(timeout)
        return ""

    probe = Probe(tmp_path, readers=Readers(), nvidia_smi="nvidia-smi", run=smi, cores=lambda: 2)
    service = VitalsService(data_dir=tmp_path, host=host, probe=probe)
    service.sampler.every_s = 0.01
    assert service.gate.vitals() is None, "constructing it samples nothing"
    host.start()
    try:
        deadline = time.monotonic() + 5
        while service.gate.vitals() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.1)
    finally:
        host.close()
    view = service.gate.vitals()
    assert view is not None and view["gpus"] == []
    assert len(asked) == 1, "the GPU is asked every 30 s, not every reading"
    assert service.sampler._thread is None, "closing the host stops the sampler"


def test_vitals_changed_rides_the_host_bus_when_the_room_moves(
    host: PeerHost, probe: Probe, ram: Ram
) -> None:
    told: list[tuple[str, dict[str, Any]]] = []
    real = host.bus.publish
    host.bus.publish = lambda kind, **fields: (told.append((kind, fields)), real(kind, **fields))[1]  # type: ignore[method-assign]
    service = VitalsService(data_dir=Path("."), host=host, probe=probe)
    sampler = Sampler(probe, service.gate)
    sampler.sample()
    sampler.sample()
    ram.pct = 95.0
    sampler.sample()
    kinds = [(kind, fields["room"]) for kind, fields in told if kind == "vitals.changed"]
    assert kinds == [("vitals.changed", "ok"), ("vitals.changed", "full")]


def test_a_reading_that_raises_does_not_end_the_sampler(probe: Probe) -> None:
    from athena.vitals.gate import Gate

    calls: list[int] = []

    class Flaky(Sampler):
        def sample(self) -> Any:
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("first reading broke")
            return super().sample()

    sampler = Flaky(probe, Gate(), every_s=0.01)
    sampler.start()
    try:
        deadline = time.monotonic() + 5
        while len(calls) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        sampler.stop()
    assert len(calls) >= 3


def test_a_memory_reader_that_breaks_is_said_once_and_its_recovery_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from athena.vitals.gate import Gate

    broken = {"on": True}
    ram = Ram()

    def memory() -> Memory:
        if broken["on"]:
            raise OSError("GlobalMemoryStatusEx failed")
        return ram()

    probe = Probe(tmp_path, readers=Readers(memory=memory), disk=lambda root: 1, cores=lambda: 2)
    sampler = Sampler(probe, Gate())
    for _ in range(10):
        sampler.sample()
    broken["on"] = False
    for _ in range(3):
        sampler.sample()
    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 2, lines
    assert "RAM could not be read" in lines[0] and "readable again" in lines[1]


def test_a_peers_vitals_ride_the_hello_into_devices_and_go_stale(
    host: PeerHost, probe: Probe, clock: Clock
) -> None:
    service = VitalsService(data_dir=Path("."), host=host, probe=probe)
    service.vitals()
    peer_id = _pair_pc(host)
    phone = "dev_" + "b" * 12
    host.registry.admit(
        phone, name="Phone", kind="phone", grants=["chat"], token=mint_token(), expires_days=None
    )
    told: list[tuple[str, dict[str, Any]]] = []
    host.bus.publish = lambda kind, **fields: told.append((kind, fields))  # type: ignore[method-assign]

    peer_view: dict[str, Any] = dict(service.gate.vitals() or {})
    peer_view["room"] = "tight"
    peer_view["junk"] = "dropped"
    host.presence.hello = lambda url, token: (200, {"ok": True, "vitals": peer_view})
    host.presence.probe_all()

    rows = {row["peer_id"]: row for row in peer_devices.devices(host)[1]["peers"]}
    shown = rows[peer_id]["vitals"]
    assert shown is not None and shown["room"] == "tight" and "junk" not in shown
    assert rows[phone]["vitals"] is None, "a phone says no hello"
    assert ("peer.changed", {"peer_id": peer_id}) in told

    # Only the room or the held reason moving is news: a figure that moves is not.
    told.clear()
    peer_view["cpu_pct"] = 55.5
    host.presence.probe_all()
    assert [kind for kind, _ in told if kind == "peer.changed"] == []
    peer_view["room"] = "full"
    peer_view["held"] = "Waiting for room: RAM is at 93% (resumes below 85%)."
    host.presence.probe_all()
    assert ("peer.changed", {"peer_id": peer_id}) in told

    # Older than the staleness line it is not shown: a stale "room ok" is worse than none.
    clock.now += timedelta(seconds=VITALS_STALE_S + 1)
    assert host.presence.vitals(peer_id) is None
    assert peer_devices.devices(host)[1]["peers"][0]["vitals"] is None


def test_a_hello_without_vitals_clears_the_peers_snapshot(host: PeerHost, probe: Probe) -> None:
    VitalsService(data_dir=Path("."), host=host, probe=probe)
    peer_id = _pair_pc(host)
    host.presence.hello = lambda url, token: (200, {"vitals": {"room": "ok", "slots": 2}})
    host.presence.probe_all()
    assert host.presence.vitals(peer_id) is not None
    host.presence.hello = lambda url, token: (200, {"ok": True})
    host.presence.probe_all()
    assert host.presence.vitals(peer_id) is None
    assert now_iso(datetime(2026, 1, 1, tzinfo=UTC))  # the helper the probe stamps with
