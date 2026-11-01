"""The loopback HTTP surface: auth, CORS, the route modules, and the launch handshake.

Binds 127.0.0.1 only. Every route needs `Authorization: Bearer <token>` except `GET /health` and
`/mcp`, whose bearer is an MCP lease the route checks itself (ADR 0015);
`GET /events` takes `?token=` because EventSource cannot send headers. The token and the port are
written to `<data>/daemon.json` (owner-only) for the desktop shell to read.
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import json
import os
import secrets
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena import engine as engine_mod
from athena import routes_mcp, routes_state, routes_turn
from athena.app import Daemon
from athena.browser import routes as routes_browser
from athena.chores import routes_chores
from athena.connectors import routes as routes_connectors
from athena.contracts import VERSION
from athena.drafts import routes as routes_drafts
from athena.engine import Engine
from athena.errors import ApiError
from athena.keys import KeyStore
from athena.peer import devices as peer_devices
from athena.peer import wiring as peer_wiring
from athena.peer.listener import DEFAULT_PEER_PORT as PEER_PORT
from athena.records import routes as routes_records
from athena.report import routes as routes_report
from athena.routines import routes as routes_routines
from athena.routines.host import TICK_S, Host
from athena.twins import poller
from athena.twins import routes as routes_twins

# The desktop's origins: Tauri on Windows/Linux and macOS, and the Vite dev server.
APP_ORIGINS = ("http://tauri.localhost", "tauri://localhost", "http://localhost:1420")
OPEN_PATHS = frozenset({"/health", routes_mcp.LEASE_PATH})
QUERY_TOKEN_PATHS = frozenset({"/events", peer_devices.EVENTS_PATH})


async def health(_: Request) -> Response:
    return JSONResponse({"ok": True, "version": VERSION})


def create_app(daemon: Daemon, token: str, origins: tuple[str, ...] = APP_ORIGINS) -> Starlette:
    routes: list[BaseRoute] = [
        Route("/health", health),
        *routes_state.routes(daemon),
        *routes_turn.routes(daemon),
        *routes_chores.routes(daemon),
        *routes_drafts.routes(daemon),
        *routes_twins.routes(daemon),
        *routes_connectors.routes(daemon),
        *routes_browser.routes(daemon),
        *routes_mcp.routes(daemon),
        *routes_records.routes(daemon),
        *routes_report.routes(daemon),
        *routes_routines.routes(daemon),
        *peer_wiring.install(daemon),
    ]

    async def guard(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS" or request.url.path in OPEN_PATHS:
            return await call_next(request)
        given = ""
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            given = header[7:].strip()
        elif request.url.path in QUERY_TOKEN_PATHS:
            given = request.query_params.get("token", "")
        if not given or not hmac.compare_digest(given, token):
            return ApiError("unauthorized", "missing or wrong token").response()
        try:
            return await call_next(request)
        except ApiError as e:
            return e.response()

    async def api_error(_: Request, exc: Exception) -> Response:
        assert isinstance(exc, ApiError)
        return exc.response()

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        """The routine host (the daemon's only background host, the twins' missions folded in) ticks
        while the app runs, unless ATHENA_TWIN_POLL is 0 (the tests); the peer host's tick and presence
        probe run while it does, when the daemon has one."""
        if daemon.peers is not None:
            await asyncio.to_thread(daemon.peers.start)
        try:
            seconds = poller.interval()
            if seconds is None:
                yield
                return
            keys = KeyStore(daemon.data_dir)

            def engine() -> Engine:
                return engine_mod.build_engine(
                    keys, stored=daemon.settings.engine_choice(), transport=routes_turn.TRANSPORT
                )

            running = Host(daemon, engine, tick_s=min(TICK_S, seconds))
            running.start()
            try:
                yield
            finally:
                await running.stop()
        finally:
            if daemon.peers is not None:
                await asyncio.to_thread(daemon.peers.close)

    return Starlette(
        lifespan=lifespan,
        routes=routes,
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=list(origins),
                allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                allow_headers=["authorization", "content-type"],
            ),
            Middleware(BaseHTTPMiddleware, dispatch=guard),
        ],
        exception_handlers={ApiError: api_error},
    )


def write_handshake(data_dir: Path, port: int, token: str) -> Path:
    """`daemon.json` = `{port, token, pid}`, owner-only, written whole."""
    path = data_dir / "daemon.json"
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"port": port, "token": token, "pid": os.getpid()}, f)
    os.replace(tmp, path)
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="athena-daemon")
    parser.add_argument("--data", type=Path, required=True, help="data directory (the app's data dir)")
    parser.add_argument("--port", type=int, default=0, help="0 = any free port")
    parser.add_argument(
        "--peer-port", type=int, default=PEER_PORT, help="port for other devices (overlay only)"
    )
    parser.add_argument("--no-peer", action="store_true", help="turn the whole multi-device surface off")
    args = parser.parse_args(argv)

    daemon = Daemon.open(args.data, peers=not args.no_peer, peer_port=args.peer_port)
    token = os.environ.get("ATHENA_TOKEN") or secrets.token_urlsafe(32)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", args.port))
    port = sock.getsockname()[1]
    daemon.mcp_url = f"http://127.0.0.1:{port}/mcp"
    write_handshake(args.data, port, token)
    print(f"athena-daemon listening on 127.0.0.1:{port}", flush=True)

    config = uvicorn.Config(create_app(daemon, token), log_level="warning", access_log=False)
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    main()
