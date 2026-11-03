"""Refusals are flagged where they are decided (ADR 0023): the dispatch says `refused`, and the MCP door
answers every refusal `isError: true`, even one that streams a line saying so (a site signed out, a
browser call that failed). A run and a filed card are not errors."""

from __future__ import annotations

from typing import Any

from starlette.testclient import TestClient

from athena.app import Daemon
from browser_kit import ORIGIN, FakeShell, trust

URL = "http://127.0.0.1:9/mcp"


def _lease(client: TestClient, daemon: Daemon, access: str = "signed_in") -> tuple[str, str]:
    daemon.mcp_url = URL
    space: str = daemon.spaces.create({"name": "Channel"})["id"]
    trust(daemon, space, ORIGIN, access)
    token: str = client.post("/mcp/lease", json={"space_id": space}).json()["token"]
    return space, token


def _call(client: TestClient, token: str, name: str, **arguments: Any) -> dict[str, Any]:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    result: dict[str, Any] = client.post(
        "/mcp", json=body, headers={"Authorization": f"Bearer {token}"}
    ).json()["result"]
    return result


def _text(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


def test_page_open_on_a_site_signed_out_is_an_error(client: TestClient, daemon: Daemon) -> None:
    _, token = _lease(client, daemon, access="signed_out")
    with FakeShell(daemon.relay) as shell:
        out = _call(client, token, "page_open", url=f"{ORIGIN}/channel")
        assert out["isError"] is True and "not signed in" in _text(out)
        assert not any(c["hand"] == "open" for c in shell.calls)  # nothing was opened


def test_an_auto_page_hand_whose_browser_call_fails_is_an_error(client: TestClient, daemon: Daemon) -> None:
    _, token = _lease(client, daemon)
    with FakeShell(daemon.relay) as shell:
        assert _call(client, token, "page_open", url=f"{ORIGIN}/channel")["isError"] is False
        assert _call(client, token, "page_read", tab=1)["isError"] is False
        shell.refuse["page_read"] = {"ok": False, "reason": "failed", "output": "the page did not answer"}
        out = _call(client, token, "page_read", tab=1)
        assert out["isError"] is True and _text(out) == "the page did not answer"


def test_page_open_whose_browser_call_fails_is_an_error_and_says_so(
    client: TestClient, daemon: Daemon
) -> None:
    space, _ = _lease(client, daemon)
    heard: list[dict[str, Any]] = []
    lease = daemon.mcp.mint(space, sink=heard.append)
    with FakeShell(daemon.relay) as shell:
        shell.refuse["open"] = {"ok": False, "reason": "failed", "output": "the tab would not open"}
        out = _call(client, lease.token, "page_open", url=f"{ORIGIN}/channel")
        assert out["isError"] is True and "the tab would not open" in _text(out)
        # the line it streams says what happened, never "Opened"
        assert [e["label"] for e in heard if e["type"] == "tool"] == [f"Could not open {ORIGIN}/channel"]


def test_a_read_and_a_filed_card_are_not_errors(client: TestClient, daemon: Daemon) -> None:
    _, token = _lease(client, daemon)
    with FakeShell(daemon.relay):
        opened = _call(client, token, "page_open", url=f"{ORIGIN}/channel")
        assert opened["isError"] is False and _text(opened).startswith("Tab 1")
        assert _call(client, token, "tabs_read")["isError"] is False
        filed = _call(client, token, "page_click", tab=1, ref="ref_ab12cd_1", expect="Play")
        assert filed["isError"] is False and filed["structuredContent"]["pending"]["card_id"]
        assert _call(client, token, "page_read", tab=9)["isError"] is True  # no such tab


def test_tabs_read_without_an_answer_from_her_browser_is_an_error(client: TestClient, daemon: Daemon) -> None:
    _, token = _lease(client, daemon)
    with FakeShell(daemon.relay) as shell:
        shell.refuse["tabs"] = {"ok": False, "reason": "failed", "output": "no answer"}
        assert _call(client, token, "tabs_read")["isError"] is True
