"""Routes over the engine and the turn: /engine, /engine/key, /engine/probe, /run.

Owned by WP3. Stub: every route answers 501 until WP3 lands.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena.app import Daemon


async def _todo(_: Request) -> Response:
    return JSONResponse({"error": "bad_request", "reason": "not built yet"}, status_code=501)


def routes(daemon: Daemon) -> list[BaseRoute]:
    del daemon
    return [
        Route("/engine", _todo, methods=["GET"]),
        Route("/engine/key", _todo, methods=["POST", "DELETE"]),
        Route("/engine/probe", _todo, methods=["POST"]),
        Route("/run", _todo, methods=["POST"]),
    ]
