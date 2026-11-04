"""The apps routes (ADR 0025, 0026): a project's apps by kind, and this device's apps outside every
project (`/apps`, not `/spaces/core/apps`).

A probe asks each kind its own way: a web page is looked at through her browser when the project has
its site and her browser is open, else reached with one plain GET (that answer is shown, not kept); a
process app is asked for its tools by the app clients, and what they found is kept.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any, cast

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena.app import Daemon
from athena.apps.store import PROCESS_KINDS, AppRow
from athena.browser import sites
from athena.clock import now_iso
from athena.contracts import App, AppList, AppNew, AppPatch, AppRemote, AppStatus
from athena.errors import ApiError

#: Seconds a plain look at a web page waits for an answer.
REACH_TIMEOUT_S = 5.0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def reach(origin: str) -> str | None:
    """One GET of the page: None when it answered (any HTTP status), else why not in plain words."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(origin + "/", method="GET"), timeout=REACH_TIMEOUT_S):
            return None
    except urllib.error.HTTPError:
        return None  # it answered; a sign-in or an error page is still the page answering
    except (urllib.error.URLError, OSError, ValueError) as exc:
        why = getattr(exc, "reason", None) or exc
        return f"Athena could not reach {origin}: {str(why)[:120] or 'no answer'}"


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ApiError("bad_request", "send a JSON object")
    return data


def probe(daemon: Daemon, space_id: str, row: AppRow) -> App:
    """Looks at one app the way its kind is reached, and answers what was found."""
    if row.kind in PROCESS_KINDS:
        found = daemon.app_clients.probe(row, daemon.apps.token(space_id, row.app_id))
        return daemon.apps.set_probe(space_id, row.app_id, found.status, found.tools, found.reason)
    if daemon.sites.trusted(space_id, row.address) and daemon.relay.connected():
        sites.check(daemon, space_id, row.address, force=True)
        return daemon.apps.view(space_id, row.app_id)
    view = daemon.apps.view(space_id, row.app_id)
    why = reach(row.address)
    status: AppStatus = "ok" if why is None else "unreachable"
    view["status"] = status
    view["checked_at"] = now_iso()
    if why is None:
        view.pop("reason", None)
    else:
        view["reason"] = why
    return view


def routes(daemon: Daemon) -> list[BaseRoute]:
    def _project(request: Request) -> str:
        space_id = str(request.path_params["id"])
        if not space_id or not daemon.spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        return space_id

    async def _list_or_add(request: Request, space_id: str) -> Response:
        if request.method == "GET":
            listed: AppList = {"apps": daemon.apps.views(space_id)}
            return JSONResponse(listed)
        body = cast("AppNew", await _body(request))
        added = await run_in_threadpool(daemon.apps.add, space_id, body)
        return JSONResponse(added, status_code=201)

    async def _remove(request: Request, space_id: str) -> Response:
        await run_in_threadpool(daemon.apps.remove, space_id, str(request.path_params["app_id"]))
        return JSONResponse({})

    async def _probe(request: Request, space_id: str) -> Response:
        row = daemon.apps.get(space_id, str(request.path_params["app_id"]))
        found = await run_in_threadpool(probe, daemon, space_id, row)
        return JSONResponse(found)

    async def space_apps(request: Request) -> Response:
        return await _list_or_add(request, _project(request))

    async def space_app(request: Request) -> Response:
        return await _remove(request, _project(request))

    async def space_app_probe(request: Request) -> Response:
        return await _probe(request, _project(request))

    async def space_app_remotes(request: Request) -> Response:
        space_id = _project(request)
        app_id = str(request.path_params["app_id"])
        row = daemon.apps.get(space_id, app_id)  # unknown_ref first
        if row.kind not in PROCESS_KINDS:
            raise ApiError("bad_request", "a web page has no copy on another device to attach")
        data = await _body(request)
        peer_id, remote_app_id = data.get("peer_id"), data.get("remote_app_id")
        if not isinstance(peer_id, str) or not isinstance(remote_app_id, str):
            raise ApiError("bad_request", "send the device and its app")
        if daemon.peers is None:
            raise ApiError("bad_request", "this computer is not set up to work with other devices", 409)
        peer = daemon.peers.registry.get(peer_id)
        if peer is None:
            raise ApiError("unknown_ref", "that device is not paired with this one")
        from athena.peer import apps as peer_apps

        offers = await run_in_threadpool(peer_apps.offers, daemon, peer_id)
        offer = next((o for o in offers if o["app_id"] == remote_app_id), None)
        if offer is None:
            raise ApiError("unknown_ref", f"{peer.name} does not offer that app")
        remote: AppRemote = {
            "peer_id": peer_id,
            "device": peer.name,
            "remote_app_id": remote_app_id,
            "status": "ok",
            "tools": list(offer["tools"]),
            "checked_at": now_iso(),
        }
        return JSONResponse(await run_in_threadpool(daemon.apps.put_remote, space_id, app_id, remote))

    async def device_apps(request: Request) -> Response:
        return await _list_or_add(request, "")

    async def space_app_remote(request: Request) -> Response:
        space_id = _project(request)
        app_id = str(request.path_params["app_id"])
        daemon.apps.get(space_id, app_id)  # unknown_ref first
        await run_in_threadpool(
            daemon.apps.drop_remote, space_id, app_id, str(request.path_params["peer_id"])
        )
        listed: AppList = {"apps": daemon.apps.views(space_id)}
        return JSONResponse(listed)

    async def device_app(request: Request) -> Response:
        if request.method == "POST":
            body = cast("AppPatch", await _body(request))
            changed = await run_in_threadpool(daemon.apps.patch, str(request.path_params["app_id"]), body)
            return JSONResponse(changed)
        return await _remove(request, "")

    async def device_app_probe(request: Request) -> Response:
        return await _probe(request, "")

    return [
        Route("/spaces/{id}/apps", space_apps, methods=["GET", "POST"]),
        Route("/spaces/{id}/apps/{app_id}", space_app, methods=["DELETE"]),
        Route("/spaces/{id}/apps/{app_id}/probe", space_app_probe, methods=["POST"]),
        Route("/spaces/{id}/apps/{app_id}/remotes", space_app_remotes, methods=["POST"]),
        Route("/spaces/{id}/apps/{app_id}/remotes/{peer_id}", space_app_remote, methods=["DELETE"]),
        Route("/apps", device_apps, methods=["GET", "POST"]),
        Route("/apps/{app_id}", device_app, methods=["POST", "DELETE"]),
        Route("/apps/{app_id}/probe", device_app_probe, methods=["POST"]),
    ]
