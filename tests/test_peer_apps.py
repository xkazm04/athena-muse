"""Apps offered across paired devices (ADR 0026): B offers a device-level app over its listener; A lists
it, calls its tools (B holds the floor on a gated one) and pulls a file from its output folder only.
Two daemons over a real loopback socket, B's app the stdio fake."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from apps_fake import stdio_argv
from athena.app import Daemon
from athena.apps import tools as apps_tools
from athena.engine import ToolCall
from athena.errors import ApiError
from athena.peer import apps as peer_apps
from athena.peer.listener import PeerHost
from athena.peer.overlay import Overlay
from athena.server import create_app
from athena.turn import dispatch

TOKEN = "t"
H = {"Authorization": f"Bearer {TOKEN}"}
NARROW = "dev_dddddddddddd"
WAV = bytes(range(256)) * 41 + b"\r\n\x00end"


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


def host(root: Path) -> PeerHost:
    up = Overlay("up", "127.0.0.1")
    return PeerHost(root, port=0, probe=lambda: up, seal=MemorySeal(), admit_loopback=True)  # type: ignore[arg-type]


class Rig:
    """A (asks, holds the project) and B (Studio-PC: offers `Queue`, keeps `Private` to itself)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.a = Daemon.open(root / "a")
        self.b = Daemon.open(root / "b")
        self.host_a, self.host_b = host(root / "pa"), host(root / "pb")
        self.a.peers, self.b.peers = self.host_a, self.host_b
        self.a_id = self.host_a.identity.identity.device_id
        self.b_id = self.host_b.identity.identity.device_id
        self.host_b.registry.admit(
            self.a_id, name="Laptop", kind="pc", grants=["chat", "apps"], token="tok-a", expires_days=None
        )
        self.host_b.registry.admit(
            NARROW, name="Old", kind="pc", grants=["chat"], token="tok-n", expires_days=None
        )
        self.host_a.registry.admit(
            self.b_id, name="Studio-PC", kind="pc", grants=["chat"], token="tok-b", expires_days=None
        )
        self.client_b = TestClient(create_app(self.b, TOKEN), headers=H)  # mounts B's peer routes
        self.client_a = TestClient(create_app(self.a, TOKEN), headers=H)
        self.host_b.reconcile()
        assert self.host_b.bound is not None
        self.url_b = f"http://127.0.0.1:{self.host_b.bound[1]}"
        self.host_a.keys.keep(self.b_id, self.url_b, "tok-a")
        self.out = root / "out"
        (self.out / "renders").mkdir(parents=True)
        (self.out / "renders" / "take1.wav").write_bytes(WAV)
        (root / "secret.txt").write_text("not yours", encoding="utf-8")
        self.app_id = self._wire("Queue", offered=True, output_dir=str(self.out))
        self.private_id = self._wire("Private", offered=False)

    def _wire(self, label: str, **kw: Any) -> str:
        made = self.b.apps.add("", {"kind": "mcp_stdio", "argv": stdio_argv(), "label": label, **kw})
        row = self.b.apps.get("", made["app_id"])
        found = self.b.app_clients.probe(row, None)
        assert found.status == "ok", found.reason
        self.b.apps.set_probe("", row.app_id, found.status, found.tools, found.reason)
        return made["app_id"]

    def audit(self) -> list[dict[str, Any]]:
        lines = self.host_b.audit.path.read_text(encoding="utf-8").splitlines()
        return [row for row in map(json.loads, lines) if row["act"] == "app_call"]

    def close(self) -> None:
        self.host_a.close()
        self.host_b.close()
        for d in (self.a, self.b):
            d.app_clients.shutdown()
            d.store.close()


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    made = Rig(tmp_path)
    yield made
    made.close()


def test_a_lists_what_b_offers_and_never_its_address(rig: Rig) -> None:
    offered = peer_apps.offers(rig.a, rig.b_id)
    assert [(o["app_id"], o["label"], o["kind"], o["has_output"]) for o in offered] == [
        (rig.app_id, "Queue", "mcp_stdio", True)
    ]
    assert {t["name"]: t["access"] for t in offered[0]["tools"]} == {"look": "auto", "erase": "gated"}
    assert offered[0]["tools"][0]["input_schema"]["type"] == "object"
    got = rig.client_a.get(f"/devices/{rig.b_id}/apps")
    assert got.status_code == 200
    assert got.json() == {"offered": offered}
    for item in got.json()["offered"]:
        assert set(item) == {"app_id", "kind", "label", "tools", "has_output"}
    text = got.text
    for secret in (
        "address",
        "argv",
        "token",
        "output_dir",
        "apps_fake",
        "tok-a",
        json.dumps(str(rig.out))[1:-1],
    ):
        assert secret not in text


def test_without_the_apps_grant_the_refusal_is_plain(rig: Rig) -> None:
    rig.host_a.keys.keep(rig.b_id, rig.url_b, "tok-n")
    with pytest.raises(ApiError) as refused:
        peer_apps.offers(rig.a, rig.b_id)
    assert refused.value.reason == "Studio-PC has not given this computer its apps"
    assert refused.value.status == 403
    got = rig.client_a.get(f"/devices/{rig.b_id}/apps")
    assert got.status_code == 403 and got.json()["reason"] == "Studio-PC has not given this computer its apps"
    with pytest.raises(ApiError, match="has not given this computer its apps"):
        peer_apps.call_remote(rig.a, rig.b_id, rig.app_id, "look", {}, None)


def test_an_auto_tool_runs_and_a_gated_one_needs_the_approval(rig: Rig) -> None:
    ran = peer_apps.call_remote(rig.a, rig.b_id, rig.app_id, "look", {"q": "mix"}, None)
    assert ran == {"text": 'look ran with {"q": "mix"}', "is_error": False}
    with pytest.raises(ApiError) as refused:
        peer_apps.call_remote(rig.a, rig.b_id, rig.app_id, "erase", {}, None)
    assert refused.value.status == 403 and "signature" in refused.value.reason
    signed = peer_apps.call_remote(rig.a, rig.b_id, rig.app_id, "erase", {}, "card_0123abcd")
    assert signed == {"text": "erase ran with {}", "is_error": False}
    rows = rig.audit()
    assert [(r["tool"], r["outcome"], r.get("approval_id")) for r in rows] == [
        ("look", "ran", None),
        ("erase", "approval_missing", None),
        ("erase", "ran", "card_0123abcd"),
    ]
    assert all(r["peer"] == rig.a_id and r["app"] == rig.app_id for r in rows)


def test_an_unlisted_tool_and_an_app_not_offered_are_refused(rig: Rig) -> None:
    with pytest.raises(ApiError) as no_tool:
        peer_apps.call_remote(rig.a, rig.b_id, rig.app_id, "format_disk", {}, "card_1")
    assert no_tool.value.status == 404 and no_tool.value.reason == "Studio-PC's app does not list that tool"
    with pytest.raises(ApiError) as hidden:
        peer_apps.call_remote(rig.a, rig.b_id, rig.private_id, "look", {}, None)
    assert hidden.value.status == 404 and hidden.value.reason == "Studio-PC no longer offers that app"
    assert [r["outcome"] for r in rig.audit()] == ["no_such_tool", "not_offered"]
    with pytest.raises(ApiError) as unknown:
        peer_apps.offers(rig.a, "dev_eeeeeeeeeeee")
    assert unknown.value.status == 404


def test_a_file_comes_byte_identical_from_the_output_folder_only(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = rig.root / "got.wav"
    size = peer_apps.fetch_remote(rig.a, rig.b_id, rig.app_id, "renders/take1.wav", dest)
    assert size == len(WAV) and dest.read_bytes() == WAV
    for escape in ("../secret.txt", str(rig.root / "secret.txt"), "renders/../../secret.txt"):
        target = rig.root / "never.txt"
        with pytest.raises(ApiError) as outside:
            peer_apps.fetch_remote(rig.a, rig.b_id, rig.app_id, escape, target)
        assert outside.value.status == 403 and "outside" in outside.value.reason
        assert not target.exists()
    link = rig.out / "link.txt"
    try:
        os.symlink(rig.root / "secret.txt", link)
    except OSError:
        pass  # a Windows account without the right to make links; the resolve is the same code
    else:
        with pytest.raises(ApiError, match="outside"):
            peer_apps.fetch_remote(rig.a, rig.b_id, rig.app_id, "link.txt", rig.root / "never.txt")
    with pytest.raises(ApiError) as missing:
        peer_apps.fetch_remote(rig.a, rig.b_id, rig.app_id, "renders/none.wav", rig.root / "never.txt")
    assert missing.value.status == 404
    monkeypatch.setattr(peer_apps, "APP_FILE_MAX_BYTES", 100)
    with pytest.raises(ApiError) as big:
        peer_apps.fetch_remote(rig.a, rig.b_id, rig.app_id, "renders/take1.wav", rig.root / "big.wav")
    assert big.value.status == 413 and "larger" in big.value.reason
    assert not (rig.root / "big.wav").exists()


def test_her_tools_reach_b_and_bring_its_output_home(rig: Rig) -> None:
    space = rig.a.spaces.create({"name": "Mix"})["id"]
    mine = rig.a.apps.add(space, {"kind": "mcp_stdio", "argv": stdio_argv(), "label": "Queue"})
    attached = rig.client_a.post(
        f"/spaces/{space}/apps/{mine['app_id']}/remotes",
        json={"peer_id": rig.b_id, "remote_app_id": rig.app_id},
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["remotes"][0]["device"] == "Studio-PC"
    names = {t["function"]["name"] for t in apps_tools.offered(rig.a, space)}
    assert {"queue_on_studio_pc__look", "queue_on_studio_pc__erase", "app_fetch"} <= names
    done = dispatch(rig.a, space, ToolCall("c1", "queue_on_studio_pc__look", {"q": "split"}))
    assert not done.refused and 'look ran with {"q": "split"}' in done.result
    assert "Queue on Studio-PC answered" in done.result
    kept = dispatch(
        rig.a, space, ToolCall("c2", "app_fetch", {"app": "queue_on_studio_pc", "path": "renders/take1.wav"})
    )
    assert not kept.refused, kept.result
    file_id = kept.result.rsplit(" ", 1)[-1].rstrip(".")
    item = rig.a.files.get(space, file_id)
    assert item["name"] == "take1.wav" and item["origin"] == "Queue on Studio-PC"
    detached = rig.client_a.delete(f"/spaces/{space}/apps/{mine['app_id']}/remotes/{rig.b_id}")
    assert detached.status_code == 200
    assert [a["remotes"] for a in detached.json()["apps"] if a["app_id"] == mine["app_id"]] == [[]]


def test_the_owner_changes_the_offer_and_its_folder(rig: Rig) -> None:
    got = rig.client_b.post(f"/apps/{rig.app_id}", json={"offered": False})
    assert got.status_code == 200 and got.json()["offered"] is False
    assert peer_apps.offers(rig.a, rig.b_id) == []
    again = rig.client_b.post(f"/apps/{rig.app_id}", json={"offered": True, "output_dir": ""})
    assert again.status_code == 200 and "output_dir" not in again.json()
    assert [o["has_output"] for o in peer_apps.offers(rig.a, rig.b_id)] == [False]
    bad = rig.client_b.post(f"/apps/{rig.app_id}", json={"output_dir": "relative/folder"})
    assert bad.status_code == 400
    back = rig.client_b.post(f"/apps/{rig.app_id}", json={"output_dir": str(rig.out)})
    assert back.json()["output_dir"] == str(rig.out)
    assert rig.client_b.post("/apps/app_nope", json={"offered": True}).status_code == 404


def test_without_devices_the_offers_route_is_absent() -> None:
    d = Daemon.open(None)
    try:
        got = TestClient(create_app(d, TOKEN), headers=H).get("/devices/dev_eeeeeeeeeeee/apps")
        assert got.status_code == 404
    finally:
        d.store.close()
