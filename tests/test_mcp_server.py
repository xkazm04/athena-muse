"""Athena's MCP server (ADR 0015): a lease is the only bearer, the class comes from the catalog, and a
gated tool files a card the caller cannot run."""

from __future__ import annotations

from typing import Any

from starlette.testclient import TestClient

from athena.app import Daemon
from conftest import TOKEN

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
    assert init["capabilities"] == {"tools": {"listChanged": False}}
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
