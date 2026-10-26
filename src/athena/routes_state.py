"""Routes over the daemon's state: spaces, memory, settings, conversation, cards, ledger, events.

Owned by WP1. Stub: every route answers 501 until WP1 lands.
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
        Route("/spaces", _todo, methods=["GET", "POST"]),
        Route("/spaces/{id}", _todo, methods=["GET", "POST", "DELETE"]),
        Route("/spaces/{id}/memory", _todo, methods=["GET"]),
        Route("/spaces/{id}/memory/{mem_id}/core", _todo, methods=["POST"]),
        Route("/settings/active-space", _todo, methods=["GET", "POST"]),
        Route("/conversation", _todo, methods=["GET"]),
        Route("/cards", _todo, methods=["GET"]),
        Route("/decisions/{card_id}", _todo, methods=["POST"]),
        Route("/ledger", _todo, methods=["GET"]),
        Route("/events", _todo, methods=["GET"]),
    ]
