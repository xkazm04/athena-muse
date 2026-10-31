"""Routes of Athena's MCP server (ADR 0015): `POST /mcp` behind a lease, `POST /mcp/lease` behind the
daemon's token. The protocol is in contracts.py and mcp.py."""

from __future__ import annotations

import hmac
import json

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena import mcp
from athena.app import Daemon
from athena.errors import ApiError

#: The route that checks its own bearer (a lease), not the daemon's token.
LEASE_PATH = "/mcp"


def routes(daemon: Daemon) -> list[BaseRoute]:
    async def serve(request: Request) -> Response:
        header = request.headers.get("authorization", "")
        given = header[7:].strip() if header.lower().startswith("bearer ") else ""
        lease = daemon.mcp.get(given) if given else None
        if lease is None or not hmac.compare_digest(lease.token, given):
            return ApiError("unauthorized", "missing, wrong or expired lease").response()
        if request.method != "POST":
            return Response(status_code=405, headers={"Allow": "POST"})
        try:
            message = json.loads(await request.body())
        except ValueError:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "not JSON"}}
            )
        answer = await run_in_threadpool(mcp.handle, daemon, lease, message)
        if answer is None:
            return Response(status_code=202)
        return JSONResponse(answer)

    async def lease(request: Request) -> Response:
        try:
            data = await request.json()
        except ValueError:
            data = None
        space_id = data.get("space_id") if isinstance(data, dict) else None
        if not isinstance(space_id, str) or not daemon.spaces.exists(space_id):
            raise ApiError("unknown_ref", "name a project the lease is for")
        if daemon.mcp_url is None:
            raise ApiError("bad_request", "the MCP server is not serving")
        held = daemon.mcp.mint(space_id)
        return JSONResponse(
            {"url": daemon.mcp_url, "token": held.token, "space_id": space_id, "expires": held.expires}
        )

    return [
        Route(LEASE_PATH, serve, methods=["POST", "GET", "DELETE"]),
        Route("/mcp/lease", lease, methods=["POST"]),
    ]
