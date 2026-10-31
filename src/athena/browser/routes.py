"""Routes of her browser (ADR 0013): the shell's relay, the wheel's note, a project's files, and its
sites (ADR 0014: listed, looked at, signed in to again; never added here).

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
from athena.browser import sites
from athena.contracts import SignInStarted, WheelNote
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

    def _space(request: Request) -> str:
        space_id = str(request.path_params["id"])
        if not space_id or not daemon.spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        return space_id

    async def _origin(request: Request, space_id: str) -> str:
        origin = (await _body(request)).get("origin")
        if not isinstance(origin, str):
            raise ApiError("bad_request", "send the site's origin")
        daemon.sites.get(space_id, origin)  # unknown_ref for a site the project does not have
        return origin

    async def site_list(request: Request) -> Response:
        space_id = _space(request)
        sites.refresh(daemon, space_id)  # stale sites are looked at again; a change arrives as `site`
        return JSONResponse({"sites": daemon.sites.list(space_id)})

    async def site_check(request: Request) -> Response:
        space_id = _space(request)
        origin = await _origin(request, space_id)
        if not daemon.relay.connected():
            raise ApiError("bad_request", "Her browser is not open; the desktop app runs it.")
        site = await run_in_threadpool(lambda: sites.check(daemon, space_id, origin, force=True))
        return JSONResponse(site)

    async def site_sign_in(request: Request) -> Response:
        space_id = _space(request)
        origin = await _origin(request, space_id)
        tab = await run_in_threadpool(sites.sign_in, daemon, space_id, origin)
        started: SignInStarted = {"origin": origin, "tab": tab}
        return JSONResponse(started)

    return [
        Route("/browser/next", next_call, methods=["GET"]),
        Route("/browser/done", done, methods=["POST"]),
        Route("/browser/note", note, methods=["POST"]),
        Route("/spaces/{id}/files", files, methods=["GET"]),
        Route("/spaces/{id}/sites", site_list, methods=["GET"]),
        Route("/spaces/{id}/sites/check", site_check, methods=["POST"]),
        Route("/spaces/{id}/sites/sign_in", site_sign_in, methods=["POST"]),
    ]
