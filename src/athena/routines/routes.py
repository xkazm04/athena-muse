"""space_routines, routine, routine_run, routine_runs (business Phase 2). Everything that reads the
tables or runs a routine is off the event loop; Run now may take a minute (a hidden page read and a
model call), and answers the run it recorded."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena import engine as engine_mod
from athena import routes_turn
from athena.contracts import ROUTES, RoutineBody, RoutineList, RunList
from athena.engine import Engine, EngineError
from athena.errors import ApiError
from athena.keys import KeyStore
from athena.routines.host import Host

if TYPE_CHECKING:
    from athena.app import Daemon


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ApiError("bad_request", "send a JSON object")
    return data


def routes(daemon: Daemon) -> list[BaseRoute]:
    keys = KeyStore(daemon.data_dir)

    def engine() -> Engine:
        try:
            # The turn routes' transport, read per call so tests can inject a mock one.
            return engine_mod.build_engine(
                keys, stored=daemon.settings.engine_choice(), transport=routes_turn.TRANSPORT
            )
        except EngineError as e:
            raise ApiError("engine_unavailable", e.reason) from e

    # The claims are the daemon's (daemon.routines), so this host and the lifespan's never overlap.
    host = Host(daemon, engine)

    def listed(space_id: str) -> RoutineList:
        if not daemon.spaces.exists(space_id) or space_id == "":
            raise ApiError("unknown_ref", "no such project")
        return {"routines": daemon.routines.ensure_defaults(space_id)}

    def runs(routine_id: str) -> RunList:
        return {"runs": daemon.routines.runs(routine_id)}

    async def space_routines(request: Request) -> Response:
        return JSONResponse(await run_in_threadpool(listed, request.path_params["id"]))

    async def routine(request: Request) -> Response:
        body = await _body(request)
        return JSONResponse(
            await run_in_threadpool(
                daemon.routines.change, request.path_params["id"], cast("RoutineBody", body)
            )
        )

    async def routine_run(request: Request) -> Response:
        return JSONResponse(await run_in_threadpool(host.run_now, request.path_params["id"]))

    async def routine_runs(request: Request) -> Response:
        return JSONResponse(await run_in_threadpool(runs, request.path_params["id"]))

    return [
        Route(ROUTES["space_routines"], space_routines, methods=["GET"]),
        Route(ROUTES["routine"], routine, methods=["PATCH"]),
        Route(ROUTES["routine_run"], routine_run, methods=["POST"]),
        Route(ROUTES["routine_runs"], routine_runs, methods=["GET"]),
    ]
