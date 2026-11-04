"""The agents routes (spark agent-leases), behind the daemon's token like every /spaces route:
connect an outside agent to a project, list and end them, and read the notes they left."""

from __future__ import annotations

from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena.app import Daemon
from athena.contracts import ROUTES, AgentList, AgentNoteList
from athena.errors import ApiError


async def _body(request: Request) -> Any:
    try:
        return await request.json()
    except ValueError:
        return None


def routes(daemon: Daemon) -> list[BaseRoute]:
    agents = daemon.agents

    async def index(request: Request) -> Response:
        space_id = str(request.path_params["id"])
        if request.method == "GET":
            listed: AgentList = {"agents": await run_in_threadpool(agents.list, daemon, space_id)}
            return JSONResponse(listed)
        body = await _body(request)
        made = await run_in_threadpool(agents.connect, daemon, space_id, body)
        return JSONResponse(made, status_code=201)

    async def item(request: Request) -> Response:
        space_id, lease_id = str(request.path_params["id"]), str(request.path_params["lease_id"])
        if not daemon.spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        return JSONResponse(await run_in_threadpool(agents.revoke, daemon, space_id, lease_id))

    async def notes(request: Request) -> Response:
        space_id = str(request.path_params["id"])
        if space_id == "" or not daemon.spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        listed: AgentNoteList = {"notes": agents.notes.list(space_id)}
        return JSONResponse(listed)

    return [
        Route(ROUTES["space_agents"], index, methods=["GET", "POST"]),
        Route(ROUTES["space_agent"], item, methods=["DELETE"]),
        Route(ROUTES["space_agent_notes"], notes, methods=["GET"]),
    ]
