"""Turn and routes over the real daemon state. Skipped until WP1's bodies land."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient

from athena import routes_turn
from athena.app import Daemon
from athena.server import create_app

try:
    Daemon.open(None)
except NotImplementedError:
    pytest.skip("WP1 state not landed yet", allow_module_level=True)

H = {"Authorization": "Bearer t"}


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("META_MODEL", raising=False)
    yield
    routes_turn.TRANSPORT = None


@pytest.fixture
def daemon() -> Daemon:
    return Daemon.open(None)


@pytest.fixture
def client(daemon: Daemon) -> TestClient:
    return TestClient(create_app(daemon, "t"))


def run(client: TestClient, text: str, space_id: str = "") -> list[dict[str, Any]]:
    r = client.post("/run", json={"text": text, "space_id": space_id}, headers=H)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in r.text.splitlines() if line]


def test_scripted_turn_streams_and_writes_stamped_episode(client: TestClient, daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Tea"})["id"]
    events = run(client, "hello there", space)
    assert events[0]["type"] == "start" and events[0]["simulated"] is True
    assert any(e["type"] == "text" for e in events)
    assert events[-1]["type"] == "done" and events[-1]["waiting"] is False
    rows = daemon.memory.page(space, "episode", 10)["rows"]
    assert len(rows) == 1 and rows[0]["space_id"] == space and "hello there" in rows[0]["line"]
    assert [t["role"] for t in daemon.conversation.list(space)] == ["person", "athena"]
    assert daemon.ledger.page(10)["totals"]["calls"] == 1


def test_remember_stamps_the_active_space_and_recall_runs(client: TestClient, daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Tea"})["id"]
    events = run(client, "remember that I like oolong", space)
    tool = next(e for e in events if e["type"] == "tool")
    assert tool["name"] == "remember" and tool["class"] == "auto"
    facts = daemon.memory.page(space, "fact", 10)["rows"]
    assert len(facts) == 1 and facts[0]["space_id"] == space
    assert daemon.memory.page("", "fact", 10)["rows"] == []
    events = run(client, "what do you know about oolong", space)
    assert any(e["type"] == "tool" and e["name"] == "recall" for e in events)


def test_propose_brief_files_a_card_and_approval_updates_once(client: TestClient, daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Tea"})["id"]
    events = run(client, "brief: grow better tea", space)
    card = next(e["card"] for e in events if e["type"] == "card")
    assert events[-1]["waiting"] is True
    assert daemon.spaces.get(space)["brief"] == ""
    r = client.post(f"/decisions/{card['id']}", json={"verdict": "approve"}, headers=H)
    assert r.status_code == 200
    assert daemon.spaces.get(space)["brief"] == "grow better tea"
    again = client.post(f"/decisions/{card['id']}", json={"verdict": "approve"}, headers=H)
    assert again.status_code == 400


def test_gated_tools_not_offered_in_core(client: TestClient) -> None:
    events = run(client, "brief: nope", "")
    assert not [e for e in events if e["type"] == "card"]


def test_validation_is_a_4xx_before_streaming(client: TestClient) -> None:
    assert client.post("/run", json={"text": "  ", "space_id": ""}, headers=H).status_code == 400
    assert client.post("/run", json={"text": "hi", "space_id": "spc_nope"}, headers=H).status_code == 404


def sse_reply() -> httpx.Response:
    chunks = [
        {"choices": [{"delta": {"content": "Hi"}}]},
        {"choices": [], "usage": {"prompt_tokens": 1000, "completion_tokens": 200}},
    ]
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


def test_muse_turn_records_tokens_cost_and_latency_on_one_row(client: TestClient, daemon: Daemon) -> None:
    routes_turn.TRANSPORT = httpx.MockTransport(lambda _: sse_reply())
    client.post("/engine/key", json={"key": "sk-live-abc"}, headers=H)
    events = run(client, "hi")
    assert events[0]["engine"] == "muse" and events[0]["simulated"] is False
    rows = daemon.ledger.page(10)["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert (row["input_tokens"], row["output_tokens"], row["cost_estimated"], row["ok"]) == (
        1000,
        200,
        True,
        True,
    )
    assert row["cost_usd"] == pytest.approx(0.0021)
    assert "latency_ms" in row
    assert events[-1]["cost_usd"] == pytest.approx(0.0021)


def test_engine_error_mid_turn(client: TestClient, daemon: Daemon) -> None:
    routes_turn.TRANSPORT = httpx.MockTransport(lambda _: httpx.Response(401))
    client.post("/engine/key", json={"key": "sk-live-abc"}, headers=H)
    events = run(client, "hi")
    assert events[-1] == {"type": "error", "error": "engine_unavailable", "reason": "Meta refused the key"}
    assert [t["role"] for t in daemon.conversation.list("")] == ["person"]
    assert daemon.ledger.page(10)["rows"][0]["ok"] is False


def test_key_never_appears_in_responses_or_logs(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    secret = "sk-live-TOPSECRET123"
    routes_turn.TRANSPORT = httpx.MockTransport(lambda _: sse_reply())
    with caplog.at_level(logging.DEBUG):
        bodies = [
            client.post("/engine/key", json={"key": secret}, headers=H).text,
            client.get("/engine", headers=H).text,
            client.post("/engine/probe", headers=H).text,
            client.post("/run", json={"text": "hi", "space_id": ""}, headers=H).text,
            client.get("/ledger", headers=H).text,
            client.delete("/engine/key", headers=H).text,
        ]
    assert all(secret not in b for b in bodies)
    assert secret not in caplog.text


def test_probe_scripted_and_key_roundtrip(client: TestClient, daemon: Daemon) -> None:
    assert client.get("/engine", headers=H).json()["key"] == "absent"
    assert client.post("/engine/probe", headers=H).json() == {
        "ok": True,
        "model": "scripted",
        "latency_ms": 0,
    }
    row = daemon.ledger.page(10)["rows"][0]
    assert row["surface"] == "probe" and row["space_id"] == ""
    assert client.post("/engine/key", json={"key": "has space"}, headers=H).status_code == 400
    assert client.post("/engine/key", json={"key": "k1"}, headers=H).json()["key"] == "file"
    assert client.delete("/engine/key", headers=H).json()["key"] == "absent"
