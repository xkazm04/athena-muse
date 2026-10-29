"""The loopback HTTP surface: auth, CORS, the route modules, and the launch handshake.

Binds 127.0.0.1 only. Every route needs `Authorization: Bearer <token>` except `GET /health`;
`GET /events` takes `?token=` because EventSource cannot send headers. The token and the port are
written to `<data>/daemon.json` (owner-only) for the desktop shell to read.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import socket
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena import routes_state, routes_turn
from athena.app import Daemon
from athena.chores import routes_chores
from athena.connectors import routes as routes_connectors
from athena.contracts import VERSION
from athena.drafts import routes as routes_drafts
from athena.errors import ApiError
from athena.twins import routes as routes_twins

# The desktop's origins: Tauri on Windows/Linux and macOS, and the Vite dev server.
APP_ORIGINS = ("http://tauri.localhost", "tauri://localhost", "http://localhost:1420")
OPEN_PATHS = frozenset({"/health"})
QUERY_TOKEN_PATHS = frozenset({"/events"})


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

    return Starlette(
        routes=routes,
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=list(origins),
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
    args = parser.parse_args(argv)

    daemon = Daemon.open(args.data)
    token = os.environ.get("ATHENA_TOKEN") or secrets.token_urlsafe(32)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", args.port))
    port = sock.getsockname()[1]
    write_handshake(args.data, port, token)
    print(f"athena-daemon listening on 127.0.0.1:{port}", flush=True)

    config = uvicorn.Config(create_app(daemon, token), log_level="warning", access_log=False)
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    main()
