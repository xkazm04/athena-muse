"""Routes of her browser (ADR 0013): the shell's relay, the wheel's note, and a project's files.

The protocol is in contracts.py: `GET /browser/next` is a long-poll the shell repeats, each call is
answered once with `POST /browser/done`, and a late or unknown answer is `accepted: false`.
"""

from __future__ import annotations

from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena.app import Daemon
from athena.contracts import WheelNote
from athena.errors import ApiError


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ApiError("bad_request", "send a JSON object")
    return data


def routes(daemon: Daemon) -> list[BaseRoute]:
    async def next_call(request: Request) -> Response:
        try:
            wait = float(request.query_params.get("wait", "20"))
        except ValueError:
            raise ApiError("bad_request", "wait is a number of seconds") from None
        call = await run_in_threadpool(daemon.relay.next, wait)
        return JSONResponse({"call": call} if call is not None else {})

    async def done(request: Request) -> Response:
        data = await _body(request)
        call_id, result = data.get("id"), data.get("result")
        if not isinstance(call_id, str) or not isinstance(result, dict):
            raise ApiError("bad_request", "send the call's id and its result")
        if not isinstance(result.get("ok"), bool):
            result = {
                "ok": False,
                "reason": "failed",
                "output": "Her browser answered in a shape Athena cannot read.",
            }
        accepted = daemon.relay.done(call_id, result)
        return JSONResponse({"accepted": accepted})

    async def note(request: Request) -> Response:
        data = await _body(request)
        tab, state = data.get("tab"), data.get("state")
        if not isinstance(tab, int) or state not in ("back", "closed", "timeout"):
            raise ApiError("bad_request", "send the tab and back, closed or timeout")
        wheel: WheelNote = {"tab": tab, "state": state}
        daemon.events.publish({"type": "wheel", "wheel": wheel})
        return JSONResponse({})

    async def files(request: Request) -> Response:
        space_id = request.path_params["id"]
        if not daemon.spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        return JSONResponse({"files": daemon.files.list(space_id)})

    return [
        Route("/browser/next", next_call, methods=["GET"]),
        Route("/browser/done", done, methods=["POST"]),
        Route("/browser/note", note, methods=["POST"]),
        Route("/spaces/{id}/files", files, methods=["GET"]),
    ]
