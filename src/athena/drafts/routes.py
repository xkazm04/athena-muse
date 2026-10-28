"""Routes over drafts (ADR 0007). Stubs until the drafts are built: every route answers 501."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Route

from athena.app import Daemon
from athena.errors import ApiError


async def _not_built(_: Request) -> Response:
    return ApiError("bad_request", "drafts are not built yet", status=501).response()


def routes(daemon: Daemon) -> list[BaseRoute]:
    del daemon  # the built routes read it
    return [
        Route("/drafts", _not_built, methods=["POST"]),
        Route("/drafts/{id}", _not_built, methods=["GET", "DELETE"]),
        Route("/drafts/{id}/say", _not_built, methods=["POST"]),
        Route("/drafts/{id}/confirm", _not_built, methods=["POST"]),
        Route("/drafts/{id}/write", _not_built, methods=["POST"]),
        Route("/drafts/{id}/preview", _not_built, methods=["POST"]),
        Route("/drafts/{id}/key", _not_built, methods=["PUT"]),
        Route("/drafts/{id}/rehearse", _not_built, methods=["POST"]),
        Route("/drafts/{id}/verdict", _not_built, methods=["POST"]),
    ]
