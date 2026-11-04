"""Fake apps for the app client and her app tools (ADR 0025): a stdlib HTTP app on 127.0.0.1:0, a stdio
app (this file run as a script with sys.executable), and a fake `daemon.apps` holding rows by hand.

Each app lists one read-only tool (`look`) and one destructive tool (`erase`).

Run as a script it is the stdio app: one JSON-RPC message per line on stdin, answers on stdout.
`--crash-on-call` makes it write a line to stderr and exit on a tools/call.
"""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass, field, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "name": "look",
        "description": "Reads the queue.",
        "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "erase",
        "description": "Erases the queue.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"destructiveHint": True},
    },
]
SCRIPT = str(Path(__file__).resolve())


def answer(message: dict[str, Any]) -> dict[str, Any] | None:
    """The fake's reply to one message (None for a notification)."""
    if "id" not in message:
        return None
    method = message.get("method")
    if method == "initialize":
        result: dict[str, Any] = {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fake", "version": "0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params") or {}
        said = json.dumps(params.get("arguments") or {}, sort_keys=True)
        result = {"content": [{"type": "text", "text": f"{params.get('name')} ran with {said}"}]}
    else:
        return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "no such method"}}
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


# --- HTTP ------------------------------------------------------------------------------------------


@dataclass
class HttpApp:
    """A loopback HTTP app. `echo_auth` makes every call answer an error quoting the Authorization
    header it got (a server that quotes the token back)."""

    echo_auth: bool = False
    calls: list[dict[str, Any]] = field(default_factory=list)
    auth: list[str] = field(default_factory=list)
    server: ThreadingHTTPServer | None = None

    @property
    def url(self) -> str:
        assert self.server is not None
        return f"http://127.0.0.1:{self.server.server_address[1]}/mcp"

    def __enter__(self) -> HttpApp:
        app = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_: Any) -> None:
                return

            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                message = json.loads(body)
                app.auth.append(self.headers.get("Authorization", ""))
                if message.get("method") == "tools/call":
                    app.calls.append(message["params"])
                    if app.echo_auth:
                        said = f"bad request from {self.headers.get('Authorization', '')}"
                        error = {
                            "jsonrpc": "2.0",
                            "id": message["id"],
                            "error": {"code": -1, "message": said},
                        }
                        return self._send(200, error)
                reply = answer(message)
                if reply is None:
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return None
                return self._send(200, reply)

            def _send(self, status: int, payload: dict[str, Any]) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Mcp-Session-Id", "sess-1")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *_: Any) -> None:
        assert self.server is not None
        self.server.shutdown()
        self.server.server_close()


def stdio_argv(*flags: str) -> list[str]:
    return [sys.executable, SCRIPT, *flags]


# --- a fake daemon.apps ----------------------------------------------------------------------------


class FakeApps:
    """Stands in for `daemon.apps` (WP1's store): rows by hand, probes and remotes recorded."""

    def __init__(self, rows: list[Any], remotes: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._rows = rows
        self._remotes = remotes or {}
        self.probes: list[tuple[str, str, str | None]] = []
        self.tokens: dict[str, str] = {}

    def rows(self, space_id: str) -> list[Any]:
        return [r for r in self._rows if r.space_id == space_id]

    def get(self, space_id: str, app_id: str) -> Any:
        from athena.errors import ApiError

        for r in self.rows(space_id):
            if r.app_id == app_id:
                return r
        raise ApiError("not_found", "no such app")

    def remotes(self, space_id: str, app_id: str) -> list[dict[str, Any]]:
        return list(self._remotes.get(app_id, []))

    def token(self, space_id: str, app_id: str) -> str | None:
        return self.tokens.get(app_id)

    def set_probe(
        self, space_id: str, app_id: str, status: str, tools: list[Any], reason: str | None
    ) -> None:
        self.probes.append((app_id, status, reason))
        self._rows = [
            replace(r, status=status, reason=reason) if r.app_id == app_id else r for r in self._rows
        ]

    def put_remote(self, space_id: str, app_id: str, remote: dict[str, Any]) -> None:
        kept = [r for r in self._remotes.get(app_id, []) if r["peer_id"] != remote["peer_id"]]
        self._remotes[app_id] = [*kept, remote]


# --- the stdio app ---------------------------------------------------------------------------------


def _serve_stdio(flags: list[str]) -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        if message.get("method") == "tools/call" and "--crash-on-call" in flags:
            sys.stderr.write("the fake fell over\n")
            sys.stderr.flush()
            sys.exit(3)
        reply = answer(message)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    _serve_stdio(sys.argv[1:])
