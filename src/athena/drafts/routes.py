"""Routes over drafts (ADR 0007). Shaping is built; authoring, the preview, the key, the test run
and the verdict answer 501 until they are."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute, Route

from athena import engine as engine_mod
from athena import routes_turn
from athena.app import Daemon
from athena.drafts import shape
from athena.engine import Engine, EngineError
from athena.errors import ApiError
from athena.keys import KeyStore


async def _not_built(_: Request) -> Response:
    return ApiError("bad_request", "drafts are not built yet", status=501).response()


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


def _stream(events: Iterator[dict[str, Any]]) -> Response:
    first = next(events)  # takes the project's turn slot now, so a busy project answers 409

    def lines() -> Iterator[bytes]:
        yield _line(first)
        for event in events:
            yield _line(event)

    return StreamingResponse(lines(), media_type="application/x-ndjson")


def routes(daemon: Daemon) -> list[BaseRoute]:
    keys = KeyStore(daemon.data_dir)

    def engine() -> Engine:
        try:
            # The turn routes' transport, read per request so tests can inject a mock one.
            return engine_mod.build_engine(keys, transport=routes_turn.TRANSPORT)
        except EngineError as e:
            raise ApiError("engine_unavailable", e.reason) from e

    async def drafts(request: Request) -> Response:
        need = (await _body(request)).get("need")
        if not isinstance(need, str):
            raise ApiError("bad_request", "send the need as text")
        draft = shape.start(daemon, need)  # the first turn runs on the first say
        return JSONResponse(draft, status_code=201)

    async def draft(request: Request) -> Response:
        draft_id = request.path_params["id"]
        if request.method == "DELETE":
            shape.abandon(daemon, draft_id)
            return JSONResponse({"id": draft_id})
        return JSONResponse(daemon.drafts.get(draft_id))

    async def say(request: Request) -> Response:
        body = await _body(request)
        text, choice = body.get("text", ""), body.get("choice")
        if not isinstance(text, str) or not (choice is None or isinstance(choice, str)):
            raise ApiError("bad_request", "send text, and choice if you picked one, as text")
        daemon.drafts.get(request.path_params["id"])  # an unknown draft is a 404 before the engine
        return _stream(shape.say(daemon, engine(), request.path_params["id"], text, choice))

    async def confirm(request: Request) -> Response:
        node_ids = (await _body(request)).get("node_ids")
        if not isinstance(node_ids, list) or not all(isinstance(n, str) for n in node_ids):
            raise ApiError("bad_request", "send node_ids as a list of ids")
        return JSONResponse(shape.confirm(daemon, request.path_params["id"], node_ids))

    return [
        Route("/drafts", drafts, methods=["POST"]),
        Route("/drafts/{id}", draft, methods=["GET", "DELETE"]),
        Route("/drafts/{id}/say", say, methods=["POST"]),
        Route("/drafts/{id}/confirm", confirm, methods=["POST"]),
        Route("/drafts/{id}/write", _not_built, methods=["POST"]),
        Route("/drafts/{id}/preview", _not_built, methods=["POST"]),
        Route("/drafts/{id}/key", _not_built, methods=["PUT"]),
        Route("/drafts/{id}/rehearse", _not_built, methods=["POST"]),
        Route("/drafts/{id}/verdict", _not_built, methods=["POST"]),
    ]
