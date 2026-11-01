"""The report routes: space_report, space_report_compose, space_report_pins; and the shape trigger's
wiring onto `daemon.records.on_change`. Everything that reads records or waits on a model runs off the
event loop."""

from __future__ import annotations

from typing import Any, cast

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena import engine as engine_mod
from athena import routes_turn
from athena.app import Daemon
from athena.contracts import ROUTES, PinsBody, RecordKind
from athena.engine import Engine, EngineError
from athena.errors import ApiError
from athena.keys import KeyStore
from athena.report import compose


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
            # The turn routes' transport, read per call so tests can inject a mock one (as drafts do).
            return engine_mod.build_engine(
                keys, stored=daemon.settings.engine_choice(), transport=routes_turn.TRANSPORT
            )
        except EngineError as e:
            raise ApiError("engine_unavailable", e.reason) from e

    def changed(space_id: str, kind: RecordKind, before: int, after: int) -> None:
        compose.on_records_changed(daemon, engine, space_id, kind, before, after)

    daemon.records.on_change = changed

    async def report(request: Request) -> Response:
        return JSONResponse(await run_in_threadpool(compose.view, daemon, request.path_params["id"]))

    async def compose_now(request: Request) -> Response:
        space_id = request.path_params["id"]
        await run_in_threadpool(compose.kinds_of, daemon, space_id)  # refusals come before the engine
        built = engine()
        return JSONResponse(await run_in_threadpool(compose.compose, daemon, built, space_id))

    async def pins(request: Request) -> Response:
        body = await _body(request)
        return JSONResponse(
            await run_in_threadpool(
                compose.set_pins, daemon, request.path_params["id"], cast("PinsBody", body)
            )
        )

    return [
        Route(ROUTES["space_report"], report, methods=["GET"]),
        Route(ROUTES["space_report_compose"], compose_now, methods=["POST"]),
        Route(ROUTES["space_report_pins"], pins, methods=["PUT"]),
    ]
