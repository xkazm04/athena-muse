"""Athena's MCP server (ADR 0015): a lease is the only bearer, the class comes from the catalog, and a
gated tool files a card the caller cannot run."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import mcp
from athena.app import Daemon
from athena.browser.actions import Dispatched
from athena.contracts import CATALOG
from athena.errors import ApiError
from browser_kit import ORIGIN, FakeShell, trust
from conftest import TOKEN
from report_kit import project

URL = "http://127.0.0.1:9/mcp"


def _rpc(
    client: TestClient, token: str, method: str, params: dict[str, Any] | None = None, msg_id: int = 1
) -> Any:
    body: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if msg_id:
        body["id"] = msg_id
    return client.post("/mcp", json=body, headers={"Authorization": f"Bearer {token}"})


def _lease(client: TestClient, daemon: Daemon, apps: list[str] | None = None) -> tuple[str, str]:
    daemon.mcp_url = URL
    space = client.post("/spaces", json={"name": "Channel", "apps": apps or []}).json()["id"]
    lease = client.post("/mcp/lease", json={"space_id": space}).json()
    assert lease["url"] == URL and lease["space_id"] == space and lease["expires"]
    return space, lease["token"]


def test_the_daemon_token_is_not_a_lease_and_a_lease_is_not_the_daemon_token(
    client: TestClient, daemon: Daemon
) -> None:
    _, token = _lease(client, daemon)
    assert _rpc(client, TOKEN, "tools/list").status_code == 401
    assert client.get("/cards", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert _rpc(client, token, "tools/list").status_code == 200


def test_initialize_list_and_a_notification(client: TestClient, daemon: Daemon) -> None:
    _, token = _lease(client, daemon)
    init = _rpc(client, token, "initialize", {"protocolVersion": "2025-06-18"}).json()["result"]
    assert init["protocolVersion"] == "2025-06-18" and init["serverInfo"]["name"] == "athena"
    assert init["capabilities"]["tools"] == {"listChanged": False}
    note = _rpc(client, token, "notifications/initialized", msg_id=0)
    assert note.status_code == 202 and note.content == b""
    tools = {t["name"]: t for t in _rpc(client, token, "tools/list").json()["result"]["tools"]}
    assert set(tools) == {"recall", "remember", "forget", "propose_brief", "add_app"}
    assert tools["recall"]["annotations"]["readOnlyHint"] is True
    assert tools["add_app"]["annotations"]["destructiveHint"] is True
    assert _rpc(client, token, "server/discover").json()["error"]["code"] == -32601


def test_an_auto_tool_runs_and_a_gated_one_files_a_card_that_only_a_signature_runs(
    client: TestClient, daemon: Daemon
) -> None:
    space, token = _lease(client, daemon)
    kept = _rpc(
        client, token, "tools/call", {"name": "remember", "arguments": {"text": "Genres: lo-fi, synthwave"}}
    )
    assert kept.json()["result"]["content"][0]["text"] == "Kept."
    asked = _rpc(
        client,
        token,
        "tools/call",
        {"name": "add_app", "arguments": {"origin": "https://studio.youtube.com"}},
    )
    result = asked.json()["result"]
    card_id = result["structuredContent"]["pending"]["card_id"]
    assert daemon.spaces.get(space)["apps"] == []  # nothing changed until the person signs
    assert daemon.gate.get(card_id)["state"] == "waiting"
    signed = client.post(f"/decisions/{card_id}", json={"verdict": "approve"}).json()
    assert signed["state"] == "approved" and daemon.spaces.get(space)["apps"] == [
        "https://studio.youtube.com"
    ]
    assert signed["outcome"] == "Added https://studio.youtube.com to the project."


def test_a_tool_the_lease_does_not_offer_is_refused(client: TestClient, daemon: Daemon) -> None:
    _, token = _lease(client, daemon)
    for name in ("page_open", "twin_send", "portal_act", "sketch"):
        out = _rpc(client, token, "tools/call", {"name": name, "arguments": {}}).json()["result"]
        assert out["isError"] is True


def test_her_browser_tools_appear_while_the_shell_polls(client: TestClient, daemon: Daemon) -> None:
    space, token = _lease(client, daemon)
    trust(daemon, space)
    with FakeShell(daemon.relay):
        names = {t["name"] for t in _rpc(client, token, "tools/list").json()["result"]["tools"]}
        assert {"page_open", "page_read", "page_click", "page_upload", "wheel_handoff"} <= names
        opened = _rpc(
            client, token, "tools/call", {"name": "page_open", "arguments": {"url": f"{ORIGIN}/channel"}}
        )
        assert opened.json()["result"]["content"][0]["text"].startswith("Tab 1")


def test_an_expired_or_dropped_lease_is_refused(client: TestClient, daemon: Daemon) -> None:
    _, token = _lease(client, daemon)
    daemon.mcp.drop(token)
    assert _rpc(client, token, "ping").status_code == 401
    short = daemon.mcp.mint("", ttl=1)
    short.expires_at = 0
    assert daemon.mcp.get(short.token) is None


def test_a_lease_needs_a_project_and_a_serving_server(client: TestClient, daemon: Daemon) -> None:
    assert client.post("/mcp/lease", json={"space_id": "spc_nope"}).status_code == 404
    space = client.post("/spaces", json={"name": "P"}).json()["id"]
    assert client.post("/mcp/lease", json={"space_id": space}).status_code == 400  # no mcp_url yet


def test_every_catalog_action_says_whether_it_writes() -> None:
    assert set(mcp.WRITES) == set(CATALOG)


def test_read_only_means_it_changes_nothing_not_that_it_needs_no_signature(
    client: TestClient, daemon: Daemon
) -> None:
    daemon.mcp_url = URL
    space = project(daemon, kinds=["track"])
    token = client.post("/mcp/lease", json={"space_id": space}).json()["token"]
    trust(daemon, space)
    with FakeShell(daemon.relay):
        listed = _rpc(client, token, "tools/list").json()["result"]["tools"]
    hint = {t["name"]: t["annotations"]["readOnlyHint"] for t in listed}
    # AUTO actions that write are not read-only (remember, record_put, page_open, page_scroll).
    for name in ("remember", "record_put", "page_open", "page_scroll", "forget", "add_app", "page_click"):
        assert hint[name] is False, name
    for name in ("recall", "record_list", "page_read", "page_find", "page_wait", "tabs_read", "file_list"):
        assert hint[name] is True, name
    assert hint["show_report"] is True
    assert (
        mcp.as_mcp({"function": {"name": "peer__x", "description": "", "parameters": {}}})["annotations"][
            "readOnlyHint"
        ]
        is False
    )


def test_every_refusal_is_an_error_and_a_card_or_a_run_is_not(client: TestClient, daemon: Daemon) -> None:
    daemon.mcp_url = URL
    space = project(daemon, kinds=["track"])
    token = client.post("/mcp/lease", json={"space_id": space}).json()["token"]

    def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = _rpc(client, token, "tools/call", {"name": name, "arguments": arguments}).json()
        return out["result"]

    for name, arguments in (
        ("remember", {"text": "  "}),
        ("forget", {"id": "mem_nope"}),
        ("propose_brief", {"brief": ""}),
        ("add_app", {"origin": "not an address"}),
        ("record_list", {"kind": "planet"}),
        ("record_put", {"kind": "creator", "body": {"name": "X"}}),  # a kind the project does not keep
        ("no_such_tool", {}),
    ):
        out = call(name, arguments)
        assert out["isError"] is True, (name, out)
    assert call("remember", {"text": "Genres: lo-fi"})["isError"] is False
    assert call("record_list", {})["isError"] is False
    filed = call("add_app", {"origin": "https://studio.youtube.com"})
    assert filed["isError"] is False and filed["structuredContent"]["pending"]["card_id"]


@pytest.mark.parametrize(
    "answer",
    [
        # ADR 0023: the dispatch flags its refusal; the door reads the flag, not the missing line
        Dispatched("That action is not offered here.", refused=True),
        ApiError("unknown_ref", "that project is gone"),
    ],
)
def test_a_refusal_from_dispatch_is_an_error(
    client: TestClient, daemon: Daemon, monkeypatch: pytest.MonkeyPatch, answer: Dispatched | ApiError
) -> None:
    _, token = _lease(client, daemon)

    def dispatch(*_: object) -> Dispatched:
        if isinstance(answer, ApiError):
            raise answer
        return answer

    monkeypatch.setattr("athena.turn.dispatch", dispatch)
    out = _rpc(client, token, "tools/call", {"name": "recall", "arguments": {"query": "x"}}).json()["result"]
    assert out["isError"] is True
