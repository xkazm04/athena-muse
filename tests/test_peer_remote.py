"""The remote composer (ADR 0017): a peer's message runs as a turn on the receiving daemon, its
events are buffered and streamed back, its cards are answered through /peer/decisions, and the
asking PC relays all of it through loopback routes. Two daemons over a real loopback socket."""

from __future__ import annotations

import json
from collections.abc import Iterator
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.peer import remote
from athena.peer.listener import PeerHost
from athena.peer.overlay import Overlay
from athena.peer.registry import PeerRow
from athena.server import create_app

TOKEN = "t"
H = {"Authorization": f"Bearer {TOKEN}"}
ASKER = "dev_bbbbbbbbbbbb"
OTHER = "dev_cccccccccccc"
NARROW = "dev_dddddddddddd"
MESSAGE = "hello there"


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
    """The receiving daemon (A, with a listener) and the asking PC's daemon (B, with a key for A)."""

    def __init__(self, root: Path) -> None:
        self.a = Daemon.open(None)
        self.b = Daemon.open(None)
        self.host_a = host(root / "a")
        self.host_b = host(root / "b")
        self.a.peers, self.b.peers = self.host_a, self.host_b
        for peer_id, grants, token in (
            (ASKER, ["chat", "approve"], "tok"),
            (OTHER, ["chat"], "tok-other"),
            (NARROW, ["memory"], "tok-narrow"),
        ):
            self.host_a.registry.admit(
                peer_id, name=f"Peer {peer_id[-1]}", kind="pc", grants=grants, token=token, expires_days=None
            )
        self.host_a.reconcile()
        assert self.host_a.bound is not None
        self.port = self.host_a.bound[1]
        self.a_id = self.host_a.identity.identity.device_id
        self.host_b.keys.keep(self.a_id, f"http://127.0.0.1:{self.port}", "tok")
        self.client_a = TestClient(create_app(self.a, TOKEN), headers=H)
        self.client_b = TestClient(create_app(self.b, TOKEN), headers=H)

    def get(self, path: str, token: str | None = "tok") -> tuple[int, str]:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            connection.request("GET", path, headers=headers)
            answer = connection.getresponse()
            return answer.status, answer.read().decode("utf-8")
        finally:
            connection.close()

    def post(self, path: str, body: dict[str, Any], token: str = "tok") -> tuple[int, dict[str, Any]]:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request(
                "POST",
                path,
                body=json.dumps(body),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            answer = connection.getresponse()
            return answer.status, json.loads(answer.read() or b"{}")
        finally:
            connection.close()

    def close(self) -> None:
        self.host_a.close()
        self.host_b.close()
        self.a.store.close()
        self.b.store.close()


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    made = Rig(tmp_path)
    yield made
    made.close()


def frames(text: str) -> list[tuple[int | None, dict[str, Any]]]:
    out: list[tuple[int | None, dict[str, Any]]] = []
    for block in text.split("\n\n"):
        lines = block.splitlines()
        data = [line[6:] for line in lines if line.startswith("data: ")]
        if data:
            ident = next((int(line[4:]) for line in lines if line.startswith("id: ")), None)
            out.append((ident, json.loads(data[0])))
    return out


def send(rig: Rig, text: str = MESSAGE, token: str = "tok") -> str:
    status, body = rig.post("/peer/message", {"text": text}, token)
    assert status == 200, body
    assert body["ok"] and body["request_id"].startswith("job_")
    return str(body["request_id"])


def test_a_message_runs_as_a_turn_and_its_events_stream_back(rig: Rig) -> None:
    request_id = send(rig)
    status, text = rig.get(f"/peer/turns/{request_id}")
    assert status == 200
    got = frames(text)
    kinds = [event["kind"] for _, event in got]
    assert kinds[0] == "turn.started" and "text.delta" in kinds
    assert kinds[-2:] == ["turn.finished", "remote.closed"]
    assert [i for i, _ in got[:-1]] == list(range(len(got) - 1))  # every event carries its index
    closed = got[-1][1]
    assert closed["reason"] == "finished" and closed["footer"] == "" and closed["showing"] == closed["total"]
    finished = got[-2][1]
    assert finished["waiting"] is False and finished["text"]
    # The daemon ran it: it is in Athena's own conversation.
    assert [t["role"] for t in rig.a.conversation.list("")] == ["person", "athena"]


def test_a_reader_resumes_from_the_count_it_has(rig: Rig) -> None:
    request_id = send(rig)
    _, whole = rig.get(f"/peer/turns/{request_id}")
    everything = frames(whole)
    _, rest = rig.get(f"/peer/turns/{request_id}?from=2")
    assert [i for i, _ in frames(rest)] == [i for i, _ in everything[2:]]
    _, junk = rig.get(f"/peer/turns/{request_id}?from=%C2%B2")  # "squared" is not a number
    assert frames(junk)[0][0] == 0


def test_only_the_sender_reads_its_turn_and_it_needs_chat(rig: Rig) -> None:
    request_id = send(rig)
    status, body = rig.get(f"/peer/turns/{request_id}", token="tok-other")
    assert status == 403 and json.loads(body)["error"] == "not_sender"
    status, body = rig.get(f"/peer/turns/{request_id}", token="tok-narrow")
    assert status == 403 and json.loads(body)["error"] == "grant_missing"
    assert rig.get(f"/peer/turns/{request_id}", token=None)[0] == 401
    assert rig.get("/peer/turns/job_000000000000")[0] == 404
    assert rig.get("/peer/turns/..%2fhello")[0] == 404
    assert rig.post("/peer/message", {"text": "x"}, "tok-narrow")[0] == 403


def test_a_message_is_checked_before_a_turn_starts(rig: Rig) -> None:
    assert rig.post("/peer/message", {})[0] == 400
    assert rig.post("/peer/message", {"text": "   "})[0] == 400
    assert rig.post("/peer/message", {"text": 7})[0] == 400
    too_long = rig.post("/peer/message", {"text": "x" * (remote.MAX_TEXT_CHARS + 1)})
    assert too_long[0] == 400 and "8000" in too_long[1]["reason"]
    assert rig.a.conversation.list("") == []
    assert rig.post("/peer/message", {"text": "x" * remote.MAX_TEXT_CHARS})[0] == 200


def test_no_engine_is_a_503_and_leaves_nothing_behind(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATHENA_ENGINE", "muse")  # chosen, with no key
    status, body = rig.post("/peer/message", {"text": MESSAGE})
    assert status == 503 and body["error"] == "engine_unavailable" and body["reason"]
    assert rig.a.conversation.list("") == []


def test_a_waiting_card_is_listed_and_answered_through_the_gate(rig: Rig) -> None:
    space = rig.a.spaces.create({"name": "Tea"})["id"]
    run = rig.client_a.post("/run", json={"text": "brief: grow better tea", "space_id": space})
    card = next(e["card"] for e in map(json.loads, run.text.splitlines()) if e["type"] == "card")

    status, body = rig.get("/peer/decisions")
    pending = json.loads(body)["pending"]
    assert status == 200 and [c["id"] for c in pending] == [card["id"]]
    assert pending[0]["action"] == "propose_brief" and pending[0]["rationale"] and pending[0]["params"]

    assert rig.post(f"/peer/decisions/{card['id']}", {"choice": "maybe"})[0] == 400
    assert rig.post(f"/peer/decisions/{card['id']}", {"choice": "approve"}, "tok-other")[0] == 403
    status, answered = rig.post(f"/peer/decisions/{card['id']}", {"choice": "approve"})
    assert status == 200 and answered["state"] == "approved"
    assert rig.a.spaces.get(space)["brief"] == "grow better tea"  # the executor ran in the daemon
    again = rig.post(f"/peer/decisions/{card['id']}", {"choice": "approve"})
    assert again[0] == 409 and again[1]["error"] == "already_decided"
    assert rig.post("/peer/decisions/card_000000000000", {"choice": "approve"})[0] == 404
    assert json.loads(rig.get("/peer/decisions")[1])["pending"] == []


def test_a_peer_without_approve_cannot_list_cards(rig: Rig) -> None:
    status, body = rig.get("/peer/decisions", token="tok-other")
    assert status == 403 and json.loads(body)["error"] == "grant_missing"


def test_the_asking_pc_sends_and_reads_through_its_loopback(rig: Rig) -> None:
    sent = rig.client_b.post(f"/devices/{rig.a_id}/message", json={"text": MESSAGE})
    assert sent.status_code == 200, sent.text
    request_id = sent.json()["request_id"]
    assert sent.json()["peer_id"] == rig.a_id
    relayed = rig.client_b.get(f"/devices/{rig.a_id}/turns/{request_id}?from=0")
    assert relayed.status_code == 200 and relayed.headers["content-type"].startswith("text/event-stream")
    got = frames(relayed.text)
    assert got[-1][1]["kind"] == "remote.closed" and got[-1][1]["reason"] == "finished"
    assert any(event["kind"] == "text.delta" for _, event in got)
    tail = rig.client_b.get(f"/devices/{rig.a_id}/turns/{request_id}?from=2")
    assert [i for i, _ in frames(tail.text)] == [i for i, _ in got[2:]]


def test_the_relay_says_why_it_could_not(rig: Rig) -> None:
    assert rig.client_b.post(f"/devices/{ASKER}/message", json={"text": "x"}).status_code == 404
    assert rig.client_b.post(f"/devices/{rig.a_id}/message", json={"text": ""}).status_code == 400
    assert rig.client_b.post(f"/devices/{rig.a_id}/message", content=b"nope").status_code == 400
    assert rig.client_b.get(f"/devices/{ASKER}/turns/job_000000000000").status_code == 404
    assert rig.client_b.get(f"/devices/{rig.a_id}/turns/not-an-id").status_code == 400
    missing = rig.client_b.get(f"/devices/{rig.a_id}/turns/job_000000000000")
    assert missing.status_code == 404 and missing.json()["error"] == "not_found"
    # A peer that has stopped listening is "unreachable", reported as a word, not a hang.
    rig.host_a.close()
    down = rig.client_b.post(f"/devices/{rig.a_id}/message", json={"text": "x"})
    assert down.status_code == 502 and down.json()["error"] == "peer_unreachable"
    gone = rig.client_b.get(f"/devices/{rig.a_id}/turns/job_000000000000")
    assert gone.status_code == 502 and gone.json()["error"] == "peer_unreachable"


def test_the_loopback_relay_needs_the_daemon_token(rig: Rig) -> None:
    bare = TestClient(create_app(rig.b, TOKEN))
    assert bare.post(f"/devices/{rig.a_id}/message", json={"text": "x"}).status_code == 401
    assert bare.get(f"/devices/{rig.a_id}/turns/job_000000000000").status_code == 401


# --- the buffer, without sockets ---------------------------------------------------------------


def row(peer_id: str = ASKER) -> PeerRow:
    return PeerRow(  # type: ignore[call-arg]
        peer_id=peer_id, name="P", kind="pc", grants=("chat",), token_sha256="x", created="", expires=None
    )


def test_one_peer_may_have_only_a_few_turns_running() -> None:
    turns = remote.RemoteTurns()
    held = [turns.file(row()) for _ in range(remote.MAX_WAITING_PER_PEER)]
    with pytest.raises(remote.PeerBusy):
        turns.file(row())
    turns.file(row(OTHER))  # another peer is not held up by it
    turns.close(held[0], "finished")
    turns.file(row())  # a closed one no longer counts


def test_the_buffer_keeps_a_cap_and_says_what_it_dropped() -> None:
    turns = remote.RemoteTurns()
    turn = turns.file(row())
    for n in range(remote.MAX_EVENTS + 5):
        turns.append(turn, {"kind": "text.delta", "text": str(n)})
    turns.close(turn, "finished")
    turns.append(turn, {"kind": "text.delta", "text": "late"})  # a closed turn takes no more
    assert turn.closed is not None and turn.total == remote.MAX_EVENTS + 5
    assert turn.closed["footer"] == f"(showing {remote.MAX_EVENTS} of {remote.MAX_EVENTS + 5})"


def test_a_turn_nobody_touched_is_forgotten_and_a_quiet_stream_ends_open() -> None:
    now = [0.0]
    turns = remote.RemoteTurns(clock=lambda: now[0], ttl_s=10.0, quiet_s=0.05)
    turn = turns.file(row())
    out = list(turns.frames(turn))
    assert len(out) == 1 and "retry: 1000" in out[0]  # no events, not closed: ended, reader returns
    now[0] = 11.0
    assert turns.get(turn.request_id) is None and turn.closed is not None
    assert turn.closed["reason"] == "expired"


def test_shape_translates_the_daemons_events_to_the_peer_wire() -> None:
    assert remote.shape({"type": "text", "delta": "hi"}) == {"kind": "text.delta", "text": "hi"}
    error = remote.shape({"type": "error", "error": "engine_unavailable", "reason": "no"})
    assert error == {"kind": "turn.error", "reason": "engine_unavailable", "detail": "no"}
    card = remote.shape({"type": "card", "card": {"id": "card_1", "action": "propose_brief", "label": "L"}})
    assert card is not None and card["kind"] == "decision.requested" and card["id"] == "card_1"
    assert remote.shape({"type": "sketch"}) is None
