"""Several devices (ADR 0017): the ceremony between two hosts over real sockets, the registry's laws,
the loopback routes through the real app."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.peer import devices as peer_devices
from athena.peer.classify import peer_class
from athena.peer.client import call
from athena.peer.listener import PeerHost
from athena.peer.overlay import Overlay, parse_status
from athena.peer.pairing import PairingBook, PairingRefused
from athena.peer.registry import PeerRegistry, fingerprint
from athena.server import create_app

TOKEN = "t"


class MemorySeal:
    kind = "memory"

    def __init__(self) -> None:
        self.held: dict[str, str] = {}

    def seal(self, name: str, value: str) -> None:
        self.held[name] = value

    def unseal(self, name: str) -> str | None:
        return self.held.get(name)

    def destroy(self, name: str) -> None:
        self.held.pop(name, None)


def host(root: Path, overlay: Overlay | None = None) -> PeerHost:
    up = overlay or Overlay("up", "127.0.0.1")
    return PeerHost(root, port=0, probe=lambda: up, seal=MemorySeal(), admit_loopback=True)  # type: ignore[arg-type]


@pytest.fixture
def pair(tmp_path: Path) -> Iterator[tuple[PeerHost, PeerHost]]:
    a, b = host(tmp_path / "a"), host(tmp_path / "b")
    yield a, b
    a.close()
    b.close()


def test_address_classes() -> None:
    assert peer_class("100.64.0.1") == "overlay"
    assert peer_class("100.127.255.254") == "overlay"
    assert peer_class("::ffff:100.100.1.2") == "overlay"
    assert peer_class("fd7a:115c:a1e0::1") == "overlay"
    assert peer_class("127.0.0.1") == "loopback"
    for refused in ("192.168.1.5", "10.0.0.2", "8.8.8.8", "169.254.1.1", "100.128.0.1", "nonsense", ""):
        assert peer_class(refused) == "refused", refused


def test_registry_keeps_a_fingerprint_and_revokes_at_once(tmp_path: Path) -> None:
    registry = PeerRegistry(tmp_path)
    row = registry.admit(
        "dev_aaaaaaaaaaaa", name="Desk", kind="pc", grants=["memory", "chat"], token="tok", expires_days=None
    )
    assert row.grants == ("chat", "memory")
    on_disk = (tmp_path / "peers.json").read_text(encoding="utf-8")
    assert '"tok"' not in on_disk and fingerprint("tok") in on_disk
    assert registry.authenticate("tok") is not None and registry.authenticate("nope") is None
    assert "token_sha256" not in row.view()
    assert registry.revoke("dev_aaaaaaaaaaaa") and registry.authenticate("tok") is None
    assert PeerRegistry(tmp_path).rows() == []


def test_an_unreadable_registry_admits_nobody(tmp_path: Path) -> None:
    (tmp_path / "peers.json").write_text("{not json", encoding="utf-8")
    assert PeerRegistry(tmp_path).rows() == []
    assert (tmp_path / "peers.json.unreadable").exists()


def test_a_wrong_code_five_times_closes_the_window() -> None:
    book = PairingBook()
    window = book.open_window("pc")
    for _ in range(5):
        with pytest.raises(PairingRefused) as refused:
            book.request(code="AAAAAA", kind="pc")
        assert refused.value.error == "wrong_code"
    assert book.get(window.pairing_id) is not None and book.get(window.pairing_id).state == "expired"  # type: ignore[union-attr]


def test_grants_only_narrow_and_a_token_is_claimed_once() -> None:
    book = PairingBook()
    window = book.open_window("phone")
    record, secret = book.request(
        pairing_id=window.pairing_id, nonce=window.nonce, kind="phone", requested_grants=["chat"]
    )
    with pytest.raises(PairingRefused) as wider:
        book.approve(record.pairing_id, ["chat", "memory"], None)
    assert wider.value.error == "grant_not_requested"
    book.approve(record.pairing_id, ["chat"], 30)
    claimed = book.claim(pairing_id=window.pairing_id, nonce=window.nonce, claim_secret=secret)
    assert claimed.token
    with pytest.raises(PairingRefused) as spent:
        book.claim(pairing_id=window.pairing_id, nonce=window.nonce, claim_secret=secret)
    assert spent.value.error == "claim_spent" and spent.value.status == 410


def test_two_computers_pair_both_ways_and_a_revoke_is_a_401(pair: tuple[PeerHost, PeerHost]) -> None:
    a, b = pair
    # A opens a window for a PC; its listener comes up on the overlay address.
    opened = peer_devices.open_pairing(a, {"kind": "pc"})[1]
    assert a.bound is not None and opened["url"]
    port = a.bound[1]

    # B types A's code. A's person sees the request, with the address that asked.
    joined = b.join("127.0.0.1", port, opened["code"], ["chat", "approve", "memory"])
    assert joined[0] == 200, joined
    pending = peer_devices.devices(a)[1]["pending"]
    assert [p["name"] for p in pending] == [b.identity.identity.name]
    assert pending[0]["address"] == "127.0.0.1" and pending[0]["replaces"] is None

    # A approves (narrowing the memory grant away). Nothing is a peer until a person does this.
    assert a.registry.rows() == []
    approved = peer_devices.answer_pending(
        a, {"choice": "approve", "grants": ["chat", "approve"]}, pending[0]["pairing_id"]
    )
    assert approved[0] == 200 and approved[1]["peer"]["grants"] == ["chat", "approve"]
    assert "token_sha256" not in approved[1]["peer"]

    # B's tick claims the token (once) and B's person is asked in return.
    b.tick()
    b_view = peer_devices.devices(b)[1]
    assert [j["state"] for j in b_view["joining"]] == ["claimed"]
    assert len(b_view["pending"]) == 1 and b_view["pending"][0]["pair_back"] is True
    assert b.keys.token(a.identity.identity.device_id)

    # B approves the pair-back: its token is delivered to A, and A can now call B.
    back = peer_devices.answer_pending(b, {"choice": "approve"}, b_view["pending"][0]["pairing_id"])
    assert back[0] == 200
    assert a.keys.token(b.identity.identity.device_id)

    # Presence: A says hello to B with the key B minted, and finds it online.
    a.presence.probe_all()
    peers = peer_devices.devices(a)[1]["peers"]
    assert peers[0]["presence"] == "online" and peers[0]["link"]["state"] == "online"
    assert peers[0]["memory"] is None and "token_sha256" not in peers[0]

    # A keeps another peer, so its listener stays up (with none it closes, and B reads it as asleep).
    a.registry.admit(
        "dev_bbbbbbbbbbbb", name="Other", kind="phone", grants=["chat"], token="x", expires_days=None
    )
    # A revokes B: B's next hello is a 401, and B's probe reads it as "removed there".
    assert peer_devices.revoke(a, b.identity.identity.device_id)[0] == 200
    assert [row.peer_id for row in a.registry.rows()] == ["dev_bbbbbbbbbbbb"]
    b.presence.probe_all()
    link = peer_devices.devices(b)[1]["peers"][0]["link"]
    assert link["state"] == "removed_there"


def test_the_listener_answers_a_stranger_401_and_knows_no_routes_to_them(
    pair: tuple[PeerHost, PeerHost],
) -> None:
    a, _ = pair
    peer_devices.open_pairing(a, {"kind": "pc"})
    assert a.bound is not None
    url = f"http://127.0.0.1:{a.bound[1]}"
    for path in ("/peer/hello", "/peer/nothing-here"):
        answer = call(url, "GET", path)
        assert answer.status == 401 and answer.body["error"] == "unauthorized"
    wrong = call(url, "POST", "/peer/pair/request", {"code": "ZZZZZZ", "kind": "pc"})
    assert wrong.status == 403 and wrong.body["error"] == "wrong_code"
    assert call(url, "GET", "/peer/hello", token="made-up").status == 401


def test_the_listener_is_down_with_nothing_to_trust_and_with_no_overlay(tmp_path: Path) -> None:
    quiet = host(tmp_path / "q")
    assert quiet.bound is None
    quiet.reconcile()
    assert quiet.bound is None and not (tmp_path / "q" / "peers.json").exists()
    no_overlay = host(tmp_path / "n", Overlay("absent"))
    peer_devices.open_pairing(no_overlay, {"kind": "pc"})
    assert no_overlay.bound is None
    assert peer_devices.devices(no_overlay)[1]["overlay"]["state"] == "absent"
    quiet.close()
    no_overlay.close()


def test_tailscale_status_is_read_defensively() -> None:
    status = parse_status(
        json.dumps(
            {
                "BackendState": "Running",
                "Self": {"TailscaleIPs": ["100.64.0.9", "fd7a:115c:a1e0::9"]},
                "Peer": {
                    "x": {
                        "HostName": "Laptop",
                        "TailscaleIPs": ["100.64.0.2"],
                        "OS": "windows",
                        "Online": True,
                    },
                    "y": {"HostName": "Phone", "TailscaleIPs": ["8.8.8.8"], "Online": True},
                },
            }
        )
    )
    assert status.logged_in and status.ip == "100.64.0.9"
    assert [(p.name, p.ip) for p in status.peers] == [("Laptop", "100.64.0.2"), ("Phone", None)]
    assert not parse_status("not json").logged_in


@pytest.fixture
def devices_client(daemon: Daemon, tmp_path: Path) -> Iterator[TestClient]:
    daemon.peers = host(tmp_path / "peer")
    yield TestClient(create_app(daemon, token=TOKEN), headers={"Authorization": f"Bearer {TOKEN}"})
    daemon.peers.close()


def test_the_loopback_routes(devices_client: TestClient) -> None:
    view: dict[str, Any] = devices_client.get("/devices").json()
    assert view["peers"] == [] and view["pending"] == [] and view["listener"]["up"] is False
    assert view["self"]["device_id"].startswith("dev_")

    assert devices_client.put("/devices/self", json={"name": "Desk"}).json()["self"]["name"] == "Desk"
    refused = devices_client.put("/devices/self", json={"name": "   "})
    assert (
        refused.status_code == 400 and refused.json()["error"] == "bad_request" and refused.json()["reason"]
    )

    opened = devices_client.post("/devices/pairing", json={"kind": "pc"}).json()
    assert len(opened["code"]) == 6 and opened["pairing_id"].startswith("pair_")
    assert devices_client.post("/devices/pairing", json={"kind": "tablet"}).status_code == 400

    gone = devices_client.delete("/devices/dev_000000000000")
    assert gone.status_code == 404 and gone.json()["error"] == "unknown_ref"
    assert (
        devices_client.post("/devices/pending/pair_000000000000", json={"choice": "approve"}).status_code
        == 404
    )
    assert devices_client.put("/devices/beacon", json={"on": "yes"}).status_code == 400
    assert devices_client.get("/devices/overlay").json()["state"] in ("no_overlay", "logged_out", "up")
    assert (
        devices_client.post("/devices/join", json={"address": "192.168.1.4", "code": "ABC234"}).status_code
        == 400
    )


def test_the_devices_routes_need_the_token(daemon: Daemon, tmp_path: Path) -> None:
    daemon.peers = host(tmp_path / "peer")
    bare = TestClient(create_app(daemon, token=TOKEN))
    assert bare.get("/devices").status_code == 401
    assert bare.get("/devices/events").status_code == 401
    daemon.peers.close()


def test_without_a_peer_host_there_are_no_device_routes(client: TestClient) -> None:
    assert client.get("/devices").status_code == 404


def test_the_event_bus_ends_a_quiet_stream_and_says_when_to_retry(tmp_path: Path) -> None:
    h = host(tmp_path)
    frames = h.bus.frames(quiet_s=0.05)
    assert "retry: 1000" in next(frames)
    h.publish("peer.changed", peer_id=None)
    assert "event: peer.changed" in next(frames)
    assert list(frames) == []
    h.close()
