"""Routes over twins: the overview, setup and its slips, the dress rehearsal, going live and pausing.

Every setup change answers the whole `TwinDetail`. The two streams (`say`, `rehearse`) and every call
that waits on a model or a connected account run off the event loop. Missions (WP4) still answer 501
naming their package; it replaces those stubs and deletes their rows from `tests/test_twin_stubs.py`.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterator
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute, Route

from athena import engine as engine_mod
from athena import routes_turn
from athena.app import Daemon
from athena.contracts import ROUTES
from athena.engine import Engine, EngineError
from athena.errors import ApiError
from athena.keys import KeyStore
from athena.twins import panels, rehearse, setup, view

# (route key, methods, the package that builds it)
STUBS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("twin_missions", ("POST",), "WP4"),
    ("twin_mission", ("GET",), "WP4"),
)


def not_built(package: str) -> Callable[[Request], Awaitable[Response]]:
    """A handler that answers 501 `{error: "bad_request", reason: "not built yet: <package>"}`."""

    async def stub(_: Request) -> Response:
        return ApiError("bad_request", f"not built yet: {package}", status=501).response()

    return stub


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ApiError("bad_request", "send a JSON object")
    return data


def _line(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


async def _stream(events: Iterator[dict[str, Any]]) -> Response:
    # The first line takes the Project's turn slot now, off the loop, as every line is.
    first = await run_in_threadpool(next, events)

    def lines() -> Iterator[bytes]:
        yield _line(first)
        for event in events:
            yield _line(event)

    return StreamingResponse(lines(), media_type="application/x-ndjson")


def _pieces(body: dict[str, Any]) -> list[str]:
    pieces = body.get("pieces")
    if not isinstance(pieces, list) or not all(isinstance(p, str) for p in pieces):
        raise ApiError("bad_request", "send pieces as a list of ids")
    return pieces


def routes(daemon: Daemon) -> list[BaseRoute]:
    keys = KeyStore(daemon.data_dir)

    def engine() -> Engine:
        try:
            # The turn routes' transport, read per request so tests can inject a mock one.
            return engine_mod.build_engine(keys, transport=routes_turn.TRANSPORT)
        except EngineError as e:
            raise ApiError("engine_unavailable", e.reason) from e

    async def detail(twin_id: str) -> Response:
        return JSONResponse(await run_in_threadpool(view.detail, daemon, twin_id))

    async def twins(request: Request) -> Response:
        if request.method == "GET":
            return JSONResponse(await run_in_threadpool(view.page, daemon))
        twin_id = setup.create(daemon, (await _body(request)).get("space_id"))
        return JSONResponse(await run_in_threadpool(view.detail, daemon, twin_id), status_code=201)

    async def twin(request: Request) -> Response:
        return await detail(request.path_params["id"])

    async def say(request: Request) -> Response:
        body = await _body(request)
        text, choice = body.get("text", ""), body.get("choice")
        if not isinstance(text, str) or not (choice is None or isinstance(choice, str)):
            raise ApiError("bad_request", "send text, and choice if you picked one, as text")
        twin_id = request.path_params["id"]
        daemon.twins.row(twin_id)  # an unknown twin is a 404 before the engine
        return await _stream(await run_in_threadpool(setup.say, daemon, engine(), twin_id, text, choice))

    def change(
        act: Callable[..., None], *, with_engine: bool = False
    ) -> Callable[[Request], Awaitable[Response]]:
        """A slip or a mark: the act off the loop, then the whole twin."""

        async def handler(request: Request) -> Response:
            body = await _body(request)
            twin_id = request.path_params["id"]
            daemon.twins.row(twin_id)
            args = (engine(),) if with_engine else ()
            await run_in_threadpool(act, daemon, *args, twin_id, body)
            return await detail(twin_id)

        return handler

    async def rehearsal(request: Request) -> Response:
        body = await _body(request)
        twin_id = request.path_params["id"]
        daemon.twins.row(twin_id)
        return await _stream(rehearse.rehearse(daemon, engine(), twin_id, body.get("goal")))

    async def plain(request: Request, act: Callable[[Daemon, str], None]) -> Response:
        twin_id = request.path_params["id"]
        await run_in_threadpool(act, daemon, twin_id)
        return await detail(twin_id)

    async def golive(request: Request) -> Response:
        return await plain(request, rehearse.go_live)

    async def pause(request: Request) -> Response:
        return await plain(request, rehearse.pause)

    return [
        Route(ROUTES["twins"], twins, methods=["GET", "POST"]),
        Route(ROUTES["twin"], twin, methods=["GET"]),
        Route(ROUTES["twin_say"], say, methods=["POST"]),
        Route(
            ROUTES["twin_confirm"], change(lambda d, t, b: setup.confirm(d, t, _pieces(b))), methods=["POST"]
        ),
        Route(ROUTES["twin_drop"], change(lambda d, t, b: setup.drop(d, t, _pieces(b))), methods=["POST"]),
        Route(
            ROUTES["twin_samples"],
            change(lambda d, e, t, b: panels.pick_samples(d, e, t, b.get("ids")), with_engine=True),
            methods=["POST"],
        ),
        Route(
            ROUTES["twin_dials"],
            change(lambda d, t, b: panels.set_dials(d, t, b.get("dials", {}), b.get("preset"))),
            methods=["POST"],
        ),
        Route(
            ROUTES["twin_pages"],
            change(lambda d, t, b: panels.pick_pages(d, t, b.get("ids"))),
            methods=["POST"],
        ),
        Route(
            ROUTES["twin_chores"],
            change(lambda d, t, b: panels.pick_chores(d, t, b.get("ids"))),
            methods=["POST"],
        ),
        Route(ROUTES["twin_autonomy"], change(panels.set_autonomy), methods=["POST"]),
        Route(ROUTES["twin_memory"], change(panels.set_memory), methods=["POST"]),
        Route(ROUTES["twin_rehearse"], rehearsal, methods=["POST"]),
        Route(ROUTES["twin_mark"], change(rehearse.mark), methods=["POST"]),
        Route(ROUTES["twin_golive"], golive, methods=["POST"]),
        Route(ROUTES["twin_pause"], pause, methods=["POST"]),
        *(Route(ROUTES[key], not_built(package), methods=list(methods)) for key, methods, package in STUBS),
    ]
