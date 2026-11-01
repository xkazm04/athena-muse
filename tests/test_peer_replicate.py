"""Memory replication between two devices (ADR 0017): the manifest, the pull, the laws."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from athena.memory import Memory, memory_sha
from athena.peer import replicate
from athena.peer.client import call
from athena.peer.listener import PeerHost
from athena.peer.overlay import Overlay
from athena.store import Store

TOKEN = "tok-from-the-serving-device-0123456789"
PUSHER = "dev_aaaaaaaaaaaa"
SERVER = "dev_bbbbbbbbbbbb"


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


@dataclass
class Side:
    host: PeerHost
    memory: Memory
    store: Store
    puller: replicate.Puller


def side(root: Path) -> Side:
    store = Store(":memory:")
    memory = Memory(store)
    peers = host(root)
    peers.add_routes(replicate.peer_routes(peers, memory))
    return Side(peers, memory, store, replicate._PULLERS[peers])


@dataclass
class Fleet:
    server: Side  # the device that is pulled
    client: Side  # the device that pulls
    url: str


@pytest.fixture
def fleet(tmp_path: Path) -> Iterator[Fleet]:
    server, client = side(tmp_path / "server"), side(tmp_path / "client")
    # The server lets the client in, with memory; the client holds the server's token.
    server.host.registry.admit(
        PUSHER, name="Client", kind="pc", grants=["memory"], token=TOKEN, expires_days=None
    )
    server.host.reconcile()
    assert server.host.bound is not None
    url = f"http://127.0.0.1:{server.host.bound[1]}"
    client.host.registry.admit(
        SERVER, name="Server", kind="pc", grants=["memory"], token="x", expires_days=None
    )
    client.host.keys.keep(SERVER, url, TOKEN)
    yield Fleet(server, client, url)
    server.host.close()
    client.host.close()


def pull(fleet: Fleet) -> replicate.PassResult:
    return fleet.client.puller.pull(SERVER, fleet.url, TOKEN)


def put(memory: Memory, mem_id: str, text: str, created: str, kind: str = "episode") -> None:
    assert memory.receive({"id": mem_id, "kind": kind, "text": text, "created": created}) == "added"


def test_the_manifest_pages_by_created_then_id(fleet: Fleet) -> None:
    for n in range(5):
        put(fleet.server.memory, f"mem_{n:012x}", f"m{n}", "2026-01-01T00:00:00Z")
    first = replicate.manifest(fleet.server.memory, None, None, limit=2)
    assert [i["id"] for i in first["items"]] == ["mem_000000000000", "mem_000000000001"]
    assert first["truncated"] and first["next"] == "2026-01-01T00:00:00Z"
    assert first["next_after"] == "mem_000000000001"
    second = replicate.manifest(fleet.server.memory, first["next"], first["next_after"], limit=10)
    assert [i["id"] for i in second["items"]] == [f"mem_{n:012x}" for n in (2, 3, 4)]
    assert not second["truncated"] and second["next"] is None
    assert second["items"][0]["sha256"] == memory_sha("m2")
    assert set(second["items"][0]) == {"id", "kind", "created", "sha256"}


def test_a_pull_files_new_rows_once_and_recall_finds_them(fleet: Fleet) -> None:
    put(fleet.server.memory, "mem_0000000000a1", "the cat sat on the mat", "2026-01-01T00:00:00Z")
    put(fleet.server.memory, "mem_0000000000a2", "she prefers tea", "2026-01-01T00:00:05Z", "fact")
    result = pull(fleet)
    assert (result.state, result.pulled) == ("ok", 2)
    assert [r["id"] for r in fleet.client.memory.recall("", "cat")] == ["mem_0000000000a1"]
    again = pull(fleet)
    assert again.pulled == 0 and again.skipped >= 1
    view = fleet.client.puller.view(SERVER)
    assert view is not None and view["pulled"] == 2 and view["conflicts"] == 0 and view["state"] == "ok"
    assert replicate.memory_view(fleet.client.host, SERVER) == view


def test_project_rows_are_never_served(fleet: Fleet) -> None:
    fleet.server.memory.append_episode("proj_aaaaaaaaaaaa", "secret project episode")
    core = fleet.server.memory.write_fact("", "core fact")
    listed = call(fleet.url, "GET", "/peer/brain/manifest", token=TOKEN).body["items"]
    assert [i["id"] for i in listed] == [core["id"]]
    project = fleet.server.store.query("SELECT id FROM memory WHERE space_id != ''")[0]["id"]
    assert call(fleet.url, "GET", f"/peer/brain/file?id={project}", token=TOKEN).status == 404
    served = call(fleet.url, "GET", f"/peer/brain/file?id={core['id']}", token=TOKEN)
    assert served.status == 200 and served.body["text"] == "core fact" and served.body["kind"] == "fact"
    assert call(fleet.url, "GET", "/peer/brain/file?id=nope", token=TOKEN).body["error"] == "not_found"


def test_a_conflict_keeps_the_local_row_and_the_remote_copy(fleet: Fleet) -> None:
    put(fleet.server.memory, "mem_0000000000c1", "their words", "2026-01-01T00:00:00Z")
    put(fleet.client.memory, "mem_0000000000c1", "my words", "2026-01-01T00:00:00Z")
    result = pull(fleet)
    assert result.conflicts == 1 and result.pulled == 0
    kept_row = fleet.client.memory.replicable("mem_0000000000c1")
    assert kept_row is not None and kept_row["text"] == "my words"
    kept = fleet.client.host.root / "conflicts" / f"mem_0000000000c1.{SERVER}.json"
    assert json.loads(kept.read_text(encoding="utf-8"))["text"] == "their words"
    assert pull(fleet).conflicts == 0  # counted once
    view = fleet.client.puller.view(SERVER)
    assert view is not None and view["conflicts"] == 1


def test_the_cursor_is_held_back_by_the_skew_margin_and_the_oldest_failure(fleet: Fleet) -> None:
    put(fleet.server.memory, "mem_0000000000d1", "one", "2026-01-01T10:00:00Z")
    put(fleet.server.memory, "mem_0000000000d2", "two", "2026-01-01T11:00:00Z")
    pull(fleet)
    cursors = json.loads(fleet.client.host.root.joinpath("cursors.json").read_text(encoding="utf-8"))
    assert cursors == {SERVER: "2026-01-01T10:50:00Z"}
    # A reload of the file gives the next puller the same cursor.
    assert replicate.Puller(fleet.client.host, fleet.client.memory).cursor(SERVER) == "2026-01-01T10:50:00Z"
    # An item that cannot be fetched holds the cursor at its own stamp (minus the margin).
    put(fleet.server.memory, "mem_0000000000d3", "three", "2026-01-01T12:00:00Z")
    original = fleet.client.puller._fetch
    fleet.client.puller._fetch = lambda *_: None  # type: ignore[method-assign]
    assert pull(fleet).failed == 1
    fleet.client.puller._fetch = original  # type: ignore[method-assign]
    assert fleet.client.puller.cursor(SERVER) == "2026-01-01T11:50:00Z"


def test_a_paged_manifest_is_followed_to_the_end(fleet: Fleet, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(replicate, "MANIFEST_PAGE", 2)
    for n in range(5):
        put(fleet.server.memory, f"mem_{n:012x}", f"m{n}", "2026-01-01T00:00:00Z")
    assert pull(fleet).pulled == 5


def test_grants_and_removal_are_states(fleet: Fleet) -> None:
    # The server withdraws the grant: 403 -> not_shared.
    fleet.server.host.registry.admit(
        PUSHER, name="Client", kind="pc", grants=["chat"], token=TOKEN, expires_days=None
    )
    assert pull(fleet).state == "not_shared"
    # The server no longer knows this token: 401 -> removed_there, and the link says so.
    fleet.server.host.registry.admit(
        PUSHER, name="Other", kind="pc", grants=["memory"], token="other", expires_days=None
    )
    assert pull(fleet).state == "removed_there"
    link = fleet.client.host.presence.link(SERVER)
    assert link is not None and link["state"] == "removed_there"
    assert link["evidence"]["memory"] == "removed_there"


def test_an_unreachable_peer_is_a_state(fleet: Fleet) -> None:
    result = fleet.client.puller.pull(SERVER, "http://127.0.0.1:1", TOKEN)
    assert result.state == "unreachable"
    view = fleet.client.puller.view(SERVER)
    assert view is not None and view["state"] == "unreachable"


def test_the_manifest_asks_for_a_token_and_a_sane_query(fleet: Fleet) -> None:
    assert call(fleet.url, "GET", "/peer/brain/manifest").status == 401
    assert call(fleet.url, "GET", "/peer/brain/manifest?since=nonsense", token=TOKEN).status == 400
    assert call(fleet.url, "GET", "/peer/brain/manifest?after=mem_000000000001", token=TOKEN).status == 400


def test_receive_is_idempotent_and_strict() -> None:
    memory = Memory(Store(":memory:"))
    row = {"id": "mem_0000000000e1", "kind": "fact", "text": "t", "created": "2026-01-01T00:00:00Z"}
    assert memory.receive(row) == "added" and memory.receive(row) == "same"
    assert memory.receive({**row, "text": "other"}) == "differs"
    for bad in (
        {**row, "id": "mem_short"},
        {**row, "id": "ep_0000000000e1"},
        {**row, "kind": "case"},
        {**row, "text": ""},
        {**row, "created": "yesterday"},
    ):
        with pytest.raises(ValueError):
            memory.receive(bad)
    assert memory.counts("") == {"episodes": 0, "facts": 1}


def test_the_status_is_null_until_the_first_pull(fleet: Fleet) -> None:
    assert replicate.memory_view(fleet.client.host, SERVER) is None


def test_stamps_compare_as_this_daemon_writes_them() -> None:
    skewed = datetime(2026, 1, 1, tzinfo=UTC) - timedelta(minutes=10)
    assert replicate._stamp(skewed) == "2025-12-31T23:50:00Z"


def test_the_thread_pulls_at_start_and_on_peer_changed_and_stops_on_close(fleet: Fleet) -> None:
    import time

    put(fleet.server.memory, "mem_0000000000f1", "first", "2026-01-01T00:00:00Z")
    puller = fleet.client.puller
    puller.start()

    def wait(done: object) -> None:
        end = time.monotonic() + 10
        while time.monotonic() < end and not done():  # type: ignore[operator]
            time.sleep(0.05)

    wait(lambda: fleet.client.memory.replicable("mem_0000000000f1") is not None)
    assert fleet.client.memory.replicable("mem_0000000000f1") is not None
    put(fleet.server.memory, "mem_0000000000f2", "second", "2026-01-01T00:01:00Z")
    fleet.client.host.publish("peer.changed", peer_id=SERVER)
    wait(lambda: fleet.client.memory.replicable("mem_0000000000f2") is not None)
    assert fleet.client.memory.replicable("mem_0000000000f2") is not None
    puller.close()
    assert puller._thread is not None and not puller._thread.is_alive()
