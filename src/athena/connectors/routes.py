"""Routes over connected accounts (ADR 0008): the list, connect (Google sign-in or a Notion key),
the sign-in flow, disconnect and probe.

`GET /connectors` -> `ConnectionList`; `POST /connectors/{kind}/connect {client_id, client_secret}`
or `{key}` -> `ConnectFlow`; `GET /connectors/{kind}/flow` -> `ConnectFlow`;
`POST /connectors/{kind}/disconnect` and `/probe` -> `Connection`. Connecting, disconnecting and
probing may dial a service, so they run off the event loop. Nothing here is, returns or logs a
credential: the body's values go to the vault and nowhere else.
"""

from __future__ import annotations

from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena.app import Daemon
from athena.connectors.part import KINDS
from athena.contracts import ROUTES, ChannelKind, ConnectBody
from athena.errors import ApiError

BODY_KEYS = ("client_id", "client_secret", "key")


def _kind(request: Request) -> ChannelKind:
    kind = request.path_params["kind"]
    for known in KINDS:
        if kind == known:
            return known
    raise ApiError("unknown_ref", f"there is no {kind} to connect; one of {', '.join(KINDS)}")


async def _connect_body(request: Request) -> ConnectBody:
    try:
        data: Any = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ApiError("bad_request", "send a JSON object")
    if set(data) - set(BODY_KEYS) or not all(isinstance(v, str) for v in data.values()):
        raise ApiError("bad_request", "send client_id and client_secret, or key, as text")
    body: ConnectBody = {}
    for name in BODY_KEYS:
        if name in data:
            body[name] = data[name]  # type: ignore[literal-required]
    return body


def routes(daemon: Daemon) -> list[BaseRoute]:
    async def connections(_: Request) -> Response:
        return JSONResponse(daemon.connectors.connections())

    async def connect(request: Request) -> Response:
        kind = _kind(request)
        body = await _connect_body(request)
        return JSONResponse(await run_in_threadpool(daemon.connectors.connect, kind, body))

    async def flow(request: Request) -> Response:
        return JSONResponse(daemon.connectors.flow(_kind(request)))

    async def disconnect(request: Request) -> Response:
        return JSONResponse(await run_in_threadpool(daemon.connectors.disconnect, _kind(request)))

    async def probe(request: Request) -> Response:
        return JSONResponse(await run_in_threadpool(daemon.connectors.probe, _kind(request)))

    return [
        Route(ROUTES["connectors"], connections, methods=["GET"]),
        Route(ROUTES["connector_connect"], connect, methods=["POST"]),
        Route(ROUTES["connector_flow"], flow, methods=["GET"]),
        Route(ROUTES["connector_disconnect"], disconnect, methods=["POST"]),
        Route(ROUTES["connector_probe"], probe, methods=["POST"]),
    ]
