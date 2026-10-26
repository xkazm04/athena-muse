"""The state routes through the real app: auth, CORS, every route's happy path."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from starlette.testclient import TestClient

from athena.app import Daemon
from athena.server import create_app


def test_no_token_is_401_and_health_is_open(daemon: Daemon) -> None:
    bare = TestClient(create_app(daemon, token="t"))
    r = bare.get("/spaces")
    assert r.status_code == 401 and r.json()["error"] == "unauthorized"
    assert bare.get("/spaces", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert bare.get("/health").json()["ok"] is True


def test_cors_preflight(client: TestClient) -> None:
    def pre(origin: str) -> Any:
        return client.options(
            "/spaces",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert "access-control-allow-origin" not in pre("http://evil.example").headers
    assert pre("http://tauri.localhost").headers["access-control-allow-origin"] == "http://tauri.localhost"


def test_spaces_crud(client: TestClient) -> None:
    r = client.post("/spaces", json={"name": "Launch", "brief": "ship it", "apps": ["https://X.com:443"]})
    assert r.status_code == 201
    sp = r.json()
    assert sp["apps"] == ["https://x.com"] and sp["counts"] == {"episodes": 0, "facts": 0}
    assert client.get("/spaces").json()["spaces"][0]["id"] == sp["id"]
    assert client.get(f"/spaces/{sp['id']}").json()["name"] == "Launch"
    patched = client.post(f"/spaces/{sp['id']}", json={"name": "Launch 2", "hue": 10})
    assert patched.json()["name"] == "Launch 2" and patched.json()["hue"] == 10
    gone = client.delete(f"/spaces/{sp['id']}")
    assert gone.json() == {"id": sp["id"], "episodes": 0, "facts": 0, "turns": 0}
    assert client.get(f"/spaces/{sp['id']}").status_code == 404
    assert client.delete("/spaces/core").json()["error"] == "unknown_ref"


def test_bad_bodies(client: TestClient) -> None:
    assert client.post("/spaces", content=b"not json").json()["error"] == "bad_request"
    assert client.post("/spaces", json=["x"]).status_code == 400
    assert client.post("/spaces", json={"name": 5}).status_code == 400
    assert client.post("/spaces", json={"name": "x" * 61}).status_code == 400
    assert client.post("/decisions/card_x", json={"verdict": "maybe"}).status_code == 400
    assert client.post("/settings/active-space", json={"space_id": 3}).status_code == 400


def test_memory_routes(client: TestClient, daemon: Daemon) -> None:
    a = client.post("/spaces", json={"name": "A"}).json()["id"]
    fact = daemon.memory.write_fact(a, "a fact")
    daemon.memory.append_episode(a, "an episode")
    page = client.get(f"/spaces/{a}/memory").json()
    assert page["total"] == 2 and page["showing"] == 2
    assert client.get(f"/spaces/{a}/memory?kind=fact&limit=1").json()["rows"][0]["id"] == fact["id"]
    assert client.get("/spaces/core/memory").json()["total"] == 0
    for bad in ("kind=nope", "limit=0", "limit=201", "limit=x"):
        assert client.get(f"/spaces/{a}/memory?{bad}").status_code == 400
    assert client.get("/spaces/spc_nope/memory").status_code == 404
    moved = client.post(f"/spaces/{a}/memory/{fact['id']}/core")
    assert moved.json() == {"id": fact["id"], "kind": "fact"}
    assert client.get("/spaces/core/memory").json()["total"] == 1


def test_active_space_routes(client: TestClient, daemon: Daemon) -> None:
    assert client.get("/settings/active-space").json() == {"space_id": ""}
    a = client.post("/spaces", json={"name": "A"}).json()["id"]
    assert client.post("/settings/active-space", json={"space_id": a}).json() == {"space_id": a}
    assert client.get("/settings/active-space").json() == {"space_id": a}
    assert client.post("/settings/active-space", json={"space_id": "spc_nope"}).status_code == 404
    with daemon.busy.turn(a):
        r = client.post("/settings/active-space", json={"space_id": ""})
        assert r.status_code == 409 and r.json()["error"] == "space_busy"
        assert client.delete(f"/spaces/{a}").status_code == 409
    assert client.post("/settings/active-space", json={"space_id": ""}).json() == {"space_id": ""}
    client.post("/settings/active-space", json={"space_id": a})
    client.delete(f"/spaces/{a}")
    assert client.get("/settings/active-space").json() == {"space_id": ""}


def test_conversation_cards_decisions_ledger(client: TestClient, daemon: Daemon) -> None:
    a = client.post("/spaces", json={"name": "A"}).json()["id"]
    daemon.conversation.append(a, "person", "hi")
    daemon.conversation.append(a, "athena", "hello")
    assert [t["text"] for t in client.get(f"/conversation?space_id={a}").json()["turns"]] == ["hi", "hello"]
    assert client.get("/conversation").json() == {"turns": []}
    assert client.get("/conversation?space_id=spc_nope").status_code == 404

    c1 = daemon.gate.file(a, "add_app", {"origin": "https://x.com"}, "add x")
    c2 = daemon.gate.file(a, "forget", {}, "forget y")
    assert [c["id"] for c in client.get("/cards").json()["cards"]] == [c2["id"], c1["id"]]
    assert len(client.get("/cards?state=waiting").json()["cards"]) == 2
    assert client.get("/cards?state=resolved").json()["cards"] == []
    assert client.get("/cards?state=bogus").status_code == 400
    done = client.post(f"/decisions/{c1['id']}", json={"verdict": "approve"})
    assert done.json()["state"] == "approved"
    assert client.post(f"/decisions/{c2['id']}", json={"verdict": "decline"}).json()["state"] == "declined"
    assert (
        client.post(f"/decisions/{c1['id']}", json={"verdict": "approve"}).json()["reason"]
        == "already decided"
    )
    assert client.post("/decisions/card_nope", json={"verdict": "approve"}).status_code == 404
    assert len(client.get("/cards?state=resolved").json()["cards"]) == 2
    assert client.get("/cards?state=waiting").json()["cards"] == []

    daemon.ledger.record(
        surface="turn",
        space_id=a,
        engine="muse",
        model="m",
        latency_ms=5,
        ok=True,
        cost_usd=0.1,
        cost_estimated=True,
    )
    page = client.get("/ledger").json()
    assert page["totals"]["calls"] == 1 and page["totals"]["cost_estimated"] is True
    assert client.get("/ledger?limit=501").status_code == 400


def test_events_route_headers_and_stream(daemon: Daemon) -> None:
    """Drive the ASGI app directly: TestClient buffers a body that never ends."""
    app = create_app(daemon, token="t")
    seen: list[dict[str, Any]] = []

    async def main() -> str:
        sent = asyncio.Event()
        body = b""

        async def receive() -> dict[str, Any]:
            await sent.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            nonlocal body
            seen.append(message)
            if message["type"] == "http.response.body":
                body += message.get("body", b"")
                if b"card_filed" in body:
                    sent.set()

        scope = {
            "type": "http", "method": "GET", "path": "/events", "raw_path": b"/events", "root_path": "",
            "query_string": b"token=t", "headers": [], "scheme": "http", "server": ("127.0.0.1", 1),
            "client": ("127.0.0.1", 2), "http_version": "1.1",
        }  # fmt: skip
        task = asyncio.ensure_future(app(scope, receive, send))
        await asyncio.sleep(0.1)
        daemon.gate.file("", "forget", {}, "x")  # publishes card_filed from this loop's thread
        await asyncio.wait_for(task, 3)
        return body.decode()

    text = asyncio.run(main())
    start = next(m for m in seen if m["type"] == "http.response.start")
    assert start["status"] == 200
    assert dict(start["headers"])[b"content-type"].startswith(b"text/event-stream")
    assert text.startswith(": ready\n\n")
    data = next(line for line in text.splitlines() if line.startswith("data: "))
    assert json.loads(data[6:])["type"] == "card_filed"
    assert daemon.events._subs == []
