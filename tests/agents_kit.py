"""Shared helpers for the outside-agent tests (spark agent-leases): a project whose app is the stdlib
HTTP fake (`apps_fake`, built from captured real answers), a connect through the route, and MCP calls
with the agent's token."""

from __future__ import annotations

from typing import Any

from starlette.testclient import TestClient

from apps_fake import TOOLS, FakeApps
from athena.app import Daemon
from athena.apps.client import access_of
from athena.apps.store import AppRow
from athena.contracts import AppTool

URL = "http://127.0.0.1:9/mcp"

LISTED: list[AppTool] = [
    {
        "name": t["name"],
        "description": t["description"],
        "access": access_of(t["annotations"]),
        "input_schema": t["inputSchema"],
    }
    for t in TOOLS
]


def project(daemon: Daemon, app_url: str = "http://127.0.0.1:9/mcp", **row: Any) -> str:
    """A project with one HTTP app, `Queue` (`queue__look` reads, `queue__erase` is gated)."""
    daemon.mcp_url = URL
    space = daemon.spaces.create({"name": "Mix"})["id"]
    fields: dict[str, Any] = {"status": "ok", "tools": LISTED, **row}
    fake = FakeApps([AppRow("app_q", space, "mcp_http", "Queue", "queue", app_url, **fields)])
    daemon.apps = fake  # type: ignore[assignment]
    return space


def connect(client: TestClient, space: str, **body: Any) -> dict[str, Any]:
    body.setdefault("label", "Claude")
    got = client.post(f"/spaces/{space}/agents", json=body)
    assert got.status_code == 201, got.text
    made: dict[str, Any] = got.json()
    return made


def rpc(client: TestClient, token: str, method: str, params: dict[str, Any] | None = None) -> Any:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post("/mcp", json=body, headers={"Authorization": f"Bearer {token}"})


def tool(client: TestClient, token: str, name: str, **arguments: Any) -> dict[str, Any]:
    got = rpc(client, token, "tools/call", {"name": name, "arguments": arguments})
    assert got.status_code == 200, got.text
    result: dict[str, Any] = got.json()["result"]
    return result


def names(client: TestClient, token: str) -> list[str]:
    return [t["name"] for t in rpc(client, token, "tools/list").json()["result"]["tools"]]


def text(result: dict[str, Any]) -> str:
    said: str = result["content"][0]["text"]
    return said
