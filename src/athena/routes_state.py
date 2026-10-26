"""Routes over the daemon's state: spaces, memory, settings, conversation, cards, ledger, events.

Errors are raised as ApiError; server.py turns them into the `{error, reason}` body.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, cast

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute, Route

from athena.app import Daemon
from athena.contracts import (
    CORE,
    CORE_ITEM,
    LEDGER_LIMIT_DEFAULT,
    MEMORY_LIMIT_DEFAULT,
    MEMORY_LIMIT_MAX,
    MemoryKind,
    Verdict,
)
from athena.errors import ApiError

LEDGER_LIMIT_MAX = 500
CONVERSATION_LIMIT = 200
PING_SECONDS = 15.0


async def _body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        raise ApiError("bad_request", "the body must be JSON") from None
    if not isinstance(body, dict):
        raise ApiError("bad_request", "the body must be a JSON object")
    return cast("dict[str, Any]", body)


def _space_arg(raw: str) -> str:
    return CORE if raw == CORE_ITEM else raw


def _limit(request: Request, default: int, maximum: int) -> int:
    raw = request.query_params.get("limit")
    if raw is None:
        return default
    try:
        n = int(raw)
    except ValueError:
        raise ApiError("bad_request", "limit must be a whole number") from None
    if not 1 <= n <= maximum:
        raise ApiError("bad_request", f"limit must be from 1 to {maximum}")
    return n


def routes(daemon: Daemon) -> list[BaseRoute]:
    spaces, memory, events = daemon.spaces, daemon.memory, daemon.events

    async def spaces_index(request: Request) -> Response:
        if request.method == "GET":
            return JSONResponse({"spaces": spaces.list()})
        created = spaces.create(await _body(request))
        events.publish({"type": "space_changed", "space_id": created["id"]})
        return JSONResponse(created, status_code=201)

    async def space_item(request: Request) -> Response:
        space_id = request.path_params["id"]
        if request.method == "GET":
            return JSONResponse(spaces.get(space_id))
        if request.method == "DELETE":
            erased = spaces.erase(space_id)
            events.publish({"type": "space_changed", "space_id": space_id, "erased": True})
            return JSONResponse(erased)
        updated = spaces.update(space_id, await _body(request))
        events.publish({"type": "space_changed", "space_id": space_id})
        return JSONResponse(updated)

    async def space_memory(request: Request) -> Response:
        space_id = _space_arg(request.path_params["id"])
        if not spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        kind = request.query_params.get("kind")
        if kind is not None and kind not in ("episode", "fact"):
            raise ApiError("bad_request", "kind must be episode or fact")
        limit = _limit(request, MEMORY_LIMIT_DEFAULT, MEMORY_LIMIT_MAX)
        return JSONResponse(memory.page(space_id, cast("MemoryKind | None", kind), limit))

    async def memory_core(request: Request) -> Response:
        source = _space_arg(request.path_params["id"])
        row = memory.make_core(source, request.path_params["mem_id"])
        events.publish({"type": "space_changed", "space_id": source})
        return JSONResponse({"id": row["id"], "kind": row["kind"]})

    async def active_space(request: Request) -> Response:
        if request.method == "GET":
            return JSONResponse({"space_id": daemon.active_space()})
        body = await _body(request)
        target = body.get("space_id")
        if not isinstance(target, str):
            raise ApiError("bad_request", "space_id must be text")
        if not spaces.exists(target):
            raise ApiError("unknown_ref", "no such project")
        if daemon.busy.any_running():
            raise ApiError("space_busy", "Athena is working; try again when she is done")
        daemon.settings.set("active_space_id", target)
        events.publish({"type": "active_space", "space_id": target})
        return JSONResponse({"space_id": target})

    async def conversation(request: Request) -> Response:
        space_id = _space_arg(request.query_params.get("space_id", CORE))
        if not spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        return JSONResponse({"turns": daemon.conversation.list(space_id, CONVERSATION_LIMIT)})

    async def cards(request: Request) -> Response:
        state = request.query_params.get("state")
        if state not in (None, "waiting", "resolved"):
            raise ApiError("bad_request", "state must be waiting or resolved")
        found = daemon.gate.list("waiting" if state == "waiting" else None)
        if state == "resolved":
            found = [c for c in found if c["state"] != "waiting"]
        return JSONResponse({"cards": found})

    async def decision(request: Request) -> Response:
        verdict = (await _body(request)).get("verdict")
        if verdict not in ("approve", "decline"):
            raise ApiError("bad_request", "verdict must be approve or decline")
        return JSONResponse(daemon.gate.resolve(request.path_params["card_id"], cast("Verdict", verdict)))

    async def ledger(request: Request) -> Response:
        return JSONResponse(daemon.ledger.page(_limit(request, LEDGER_LIMIT_DEFAULT, LEDGER_LIMIT_MAX)))

    async def stream(_: Request) -> Response:
        async def frames() -> AsyncIterator[str]:
            yield ": ready\n\n"
            it = events.subscribe()
            pending: asyncio.Future[Any] | None = None
            try:
                while True:
                    if pending is None:
                        pending = asyncio.ensure_future(anext(it))
                    # Wait on the same pending read across pings: cancelling it would end the generator.
                    done, _ = await asyncio.wait({pending}, timeout=PING_SECONDS)
                    if not done:
                        yield ": ping\n\n"
                        continue
                    event = pending.result()
                    pending = None
                    yield f"data: {json.dumps(event)}\n\n"
            finally:
                if pending is not None:
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                await it.aclose()  # type: ignore[attr-defined]  # AsyncIterator has no aclose in typeshed

        return StreamingResponse(
            frames(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    return [
        Route("/spaces", spaces_index, methods=["GET", "POST"]),
        Route("/spaces/{id}", space_item, methods=["GET", "POST", "DELETE"]),
        Route("/spaces/{id}/memory", space_memory, methods=["GET"]),
        Route("/spaces/{id}/memory/{mem_id}/core", memory_core, methods=["POST"]),
        Route("/settings/active-space", active_space, methods=["GET", "POST"]),
        Route("/conversation", conversation, methods=["GET"]),
        Route("/cards", cards, methods=["GET"]),
        Route("/decisions/{card_id}", decision, methods=["POST"]),
        Route("/ledger", ledger, methods=["GET"]),
        Route("/events", stream, methods=["GET"]),
    ]
