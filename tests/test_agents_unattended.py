"""An agent's unattended calls through the MCP server (spark agent-leases): one grant card at the
connect, nothing unattended until it is signed, then a gated app tool runs without a card while the
signed limits allow it, and every other call files the ordinary card. The app is the stdlib HTTP fake."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from agents_kit import connect, project, text, tool
from apps_fake import HttpApp
from athena import mcp
from athena.agents.ceiling import USED_UP
from athena.app import Daemon

ERASE = {"tools": ["queue__erase"], "max_calls": 2, "minutes": 30}


@pytest.fixture
def app() -> Iterator[HttpApp]:
    with HttpApp() as served:
        yield served


def _grant(daemon: Daemon, lease_id: str) -> str:
    lease = daemon.mcp.agent(lease_id)
    assert lease is not None and lease.ceiling is not None and lease.ceiling.card_id is not None
    return lease.ceiling.card_id


def _signed(client: TestClient, daemon: Daemon, space: str, **ceiling: Any) -> dict[str, Any]:
    made = connect(client, space, label="Claude", ceiling={**ERASE, **ceiling})
    signed = client.post(f"/decisions/{_grant(daemon, made['lease']['id'])}", json={"verdict": "approve"})
    assert signed.status_code == 200, signed.text
    return made


def test_the_connect_files_one_grant_card_in_the_persons_words(
    client: TestClient, daemon: Daemon, app: HttpApp
) -> None:
    space = project(daemon, app.url)
    made = connect(client, space, label="Claude", ceiling={**ERASE, "max_calls": 5, "minutes": 45})
    lease = made["lease"]
    assert lease["state"] == "waiting"
    assert lease["ceiling"]["signed"] is False and lease["ceiling"]["used"] == 0
    card = daemon.gate.get(lease["ceiling"]["card_id"])
    assert card["action"] == "agent_grant" and card["state"] == "waiting"
    assert card["label"] == "Let Claude run erase in Queue up to 5 times for 45 minutes without asking"
    # nothing runs unattended before the signature: the call files the ordinary card
    filed = tool(client, made["token"], "queue__erase")
    assert filed["structuredContent"]["pending"]["card_id"] and app.calls == []
    signed = client.post(f"/decisions/{card['id']}", json={"verdict": "approve"}).json()
    assert signed["outcome"].startswith("Claude may now run those calls without asking")
    listed = client.get(f"/spaces/{space}/agents").json()["agents"][0]
    assert listed["state"] == "connected" and listed["ceiling"]["signed"] is True


def test_a_declined_grant_leaves_the_agent_working_with_cards(
    client: TestClient, daemon: Daemon, app: HttpApp
) -> None:
    space = project(daemon, app.url)
    made = connect(client, space, ceiling=ERASE)
    client.post(f"/decisions/{_grant(daemon, made['lease']['id'])}", json={"verdict": "decline"})
    listed = client.get(f"/spaces/{space}/agents").json()["agents"][0]
    assert listed["state"] == "connected" and listed["ceiling"]["signed"] is False
    filed = tool(client, made["token"], "queue__erase")
    assert "structuredContent" in filed and app.calls == []


def test_signed_calls_run_without_a_card_until_they_are_used_up(
    client: TestClient, daemon: Daemon, app: HttpApp
) -> None:
    space = project(daemon, app.url)
    made = _signed(client, daemon, space)
    token = made["token"]
    before = len(daemon.gate.list())
    for _ in range(2):
        ran = tool(client, token, "queue__erase")
        assert "structuredContent" not in ran and ran["isError"] is False
        assert "erase ran with {}" in text(ran) and "not instructions" in text(ran)
    assert len(app.calls) == 2 and len(daemon.gate.list()) == before
    third = tool(client, token, "queue__erase")
    card = daemon.gate.get(third["structuredContent"]["pending"]["card_id"])
    assert text(third).startswith(USED_UP)
    assert card["label"] == "Claude asks: Queue: erase" and len(app.calls) == 2
    assert client.get(f"/spaces/{space}/agents").json()["agents"][0]["ceiling"]["used"] == 2


def test_a_read_only_app_tool_runs_as_always_and_spends_nothing(
    client: TestClient, daemon: Daemon, app: HttpApp
) -> None:
    space = project(daemon, app.url)
    made = _signed(client, daemon, space, tools=["queue__erase", "queue__look"])
    for _ in range(3):
        assert tool(client, made["token"], "queue__look", q="x")["isError"] is False
    lease = daemon.mcp.agent(made["lease"]["id"])
    assert lease is not None and lease.ceiling is not None and lease.ceiling.used == 0


def test_eight_calls_at_once_against_five_allowed_run_five_and_file_three(
    client: TestClient, daemon: Daemon, app: HttpApp
) -> None:
    space = project(daemon, app.url)
    made = _signed(client, daemon, space, max_calls=5)
    lease = daemon.mcp.get(made["token"])
    assert lease is not None
    start = threading.Barrier(8)
    results: list[dict[str, Any]] = []
    lock = threading.Lock()

    def one() -> None:
        start.wait()
        out = mcp.call_tool(daemon, lease, "queue__erase", {})
        with lock:
            results.append(out)

    threads = [threading.Thread(target=one) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    cards = [r for r in results if "structuredContent" in r]
    assert len(results) == 8 and len(cards) == 3 and len(app.calls) == 5
    assert lease.ceiling is not None and lease.ceiling.used == 5


@pytest.mark.parametrize("why", ["not_named", "expired", "unsigned", "inside"])
def test_anything_outside_the_signed_limits_files_the_ordinary_card(
    client: TestClient, daemon: Daemon, app: HttpApp, why: str
) -> None:
    space = project(daemon, app.url)
    if why == "unsigned":
        made = connect(client, space, ceiling=ERASE)
    elif why == "not_named":
        made = _signed(client, daemon, space, tools=["queue__look"])
    else:
        made = _signed(client, daemon, space)
    lease = daemon.mcp.agent(made["lease"]["id"])
    assert lease is not None and lease.ceiling is not None
    if why == "expired":
        lease.ceiling.deadline = 0.0
    filed = tool(client, made["token"], "queue__erase")
    if why == "inside":  # the control: inside the limits it runs
        assert "structuredContent" not in filed and len(app.calls) == 1
        return
    assert filed["structuredContent"]["pending"]["card_id"] and app.calls == []
    assert not text(filed).startswith(USED_UP)


def test_no_non_app_action_runs_unattended_even_if_sent(client: TestClient, daemon: Daemon) -> None:
    space = project(daemon)
    for name in ("add_app", "page_click", "remember", "record_put", "agent_grant", "twin_send"):
        got = client.post(
            f"/spaces/{space}/agents",
            json={
                "label": "C",
                "tools": ["queue__erase", "add_app", "remember"],
                "ceiling": {"tools": [name], "max_calls": 5, "minutes": 5},
            },
        )
        assert got.status_code == 400, name
        assert "Only an app's own tools" in got.json()["reason"] or "cannot use" in got.json()["reason"]
    made = connect(client, space, tools=["queue__erase", "add_app"], ceiling=ERASE)
    lease = daemon.mcp.agent(made["lease"]["id"])
    assert lease is not None and lease.ceiling is not None
    lease.ceiling.signed = True
    lease.ceiling.tools.append("add_app")  # even a ceiling that somehow names one never runs it
    filed = tool(client, made["token"], "add_app", origin="https://example.com")
    assert filed["structuredContent"]["pending"]["card_id"]
    assert daemon.spaces.get(space)["apps"] == []


def test_the_file_allowance_stops_app_fetch(client: TestClient, daemon: Daemon, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    for name in ("a.wav", "b.wav", "c.wav"):
        (out / name).write_bytes(b"x" * 600 * 1024)
    d = Daemon.open(tmp_path / "data")
    try:
        from athena.server import create_app
        from conftest import TOKEN

        c = TestClient(create_app(d, TOKEN), headers={"Authorization": f"Bearer {TOKEN}"})
        space = project(d, output_dir=str(out))
        capped = connect(c, space, ceiling={**ERASE, "file_mb": 1})
        assert tool(c, capped["token"], "app_fetch", app="queue", path="a.wav")["isError"] is False
        over = tool(c, capped["token"], "app_fetch", app="queue", path="b.wav")
        assert over["isError"] is True and "larger than the agent may still bring in" in text(over)
        listed = c.get(f"/spaces/{space}/agents").json()["agents"][0]
        assert listed["ceiling"]["file_bytes"] == 1024 * 1024
        # without an allowance, app_fetch is as it always was
        free = connect(c, space, label="Free")
        for name in ("b.wav", "c.wav"):
            assert tool(c, free["token"], "app_fetch", app="queue", path=name)["isError"] is False
    finally:
        d.store.close()
