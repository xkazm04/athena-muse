"""Routes over Settings (ADR 0012): GET /settings, POST /settings/look, POST /settings/engine.

The active project keeps its own route (`/settings/active-space`, in routes_state.py). The engine is
built per request, so a stored choice reaches the next turn without restarting anything.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena import engine as engine_mod
from athena.app import Daemon
from athena.contracts import EngineId, EngineStatus, SettingsView
from athena.engine import EngineError
from athena.errors import ApiError
from athena.keys import KeyStore
from athena.settings import ENGINE_IDS, ENGINE_KEY


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ApiError("bad_request", "send a JSON object")
    return cast("dict[str, Any]", data)


def view(daemon: Daemon, keys: KeyStore) -> SettingsView:
    stored = daemon.settings.engine_choice()
    try:
        engine_id, source = engine_mod.decide(keys, stored)
    except EngineError as e:  # a bad ATHENA_ENGINE: say how to fix it
        raise ApiError("engine_unavailable", e.reason) from e
    out: SettingsView = {
        "look": daemon.settings.look(),
        "engine": engine_id,
        "source": source,
        "engines": engine_mod.options(keys),
    }
    if stored:
        out["choice"] = cast("EngineId", stored)
    if daemon.data_dir is not None:
        out["data_dir"] = str(daemon.data_dir)
    return out


def routes(daemon: Daemon, keys: KeyStore, announce: Callable[[], EngineStatus]) -> list[BaseRoute]:
    """`announce` publishes the engine status the windows' lamps show (routes_turn owns it)."""

    async def settings(_: Request) -> Response:
        return JSONResponse(view(daemon, keys))

    async def look(request: Request) -> Response:
        chosen = daemon.settings.set_look(await _body(request))
        daemon.events.publish({"type": "settings", "look": chosen})
        return JSONResponse(view(daemon, keys))

    async def engine(request: Request) -> Response:
        wanted = (await _body(request)).get("engine")
        if wanted not in ENGINE_IDS:
            raise ApiError("bad_request", f"engine must be one of {', '.join(ENGINE_IDS)}")
        option = next(o for o in engine_mod.options(keys) if o["id"] == wanted)
        if option["readiness"] in ("no_key", "not_installed"):
            raise ApiError("engine_unavailable", option.get("reason", "that engine cannot run here"))
        daemon.settings.set(ENGINE_KEY, cast("str", wanted))
        announce()
        return JSONResponse(view(daemon, keys))

    return [
        Route("/settings", settings, methods=["GET"]),
        Route("/settings/look", look, methods=["POST"]),
        Route("/settings/engine", engine, methods=["POST"]),
    ]
