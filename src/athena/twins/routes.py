"""Routes over twins: the overview, setup, the dress rehearsal, going live and missions.

Stubs for now: every route is registered and answers 501 naming the work package that builds it.
A package replaces its stubs with handlers and deletes their rows from `tests/test_twin_stubs.py`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Route

from athena.app import Daemon
from athena.contracts import ROUTES
from athena.errors import ApiError

# (route key, methods, the package that builds it)
STUBS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("twins", ("GET", "POST"), "WP3"),
    ("twin", ("GET",), "WP3"),
    ("twin_say", ("POST",), "WP3"),
    ("twin_confirm", ("POST",), "WP3"),
    ("twin_drop", ("POST",), "WP3"),
    ("twin_samples", ("POST",), "WP3"),
    ("twin_dials", ("POST",), "WP3"),
    ("twin_pages", ("POST",), "WP3"),
    ("twin_chores", ("POST",), "WP3"),
    ("twin_autonomy", ("POST",), "WP3"),
    ("twin_memory", ("POST",), "WP3"),
    ("twin_rehearse", ("POST",), "WP3"),
    ("twin_mark", ("POST",), "WP3"),
    ("twin_golive", ("POST",), "WP3"),
    ("twin_pause", ("POST",), "WP3"),
    ("twin_missions", ("POST",), "WP4"),
    ("twin_mission", ("GET",), "WP4"),
)


def not_built(package: str) -> Callable[[Request], Awaitable[Response]]:
    """A handler that answers 501 `{error: "bad_request", reason: "not built yet: <package>"}`."""

    async def stub(_: Request) -> Response:
        return ApiError("bad_request", f"not built yet: {package}", status=501).response()

    return stub


def routes(daemon: Daemon) -> list[BaseRoute]:
    del daemon  # the stubs need nothing yet
    return [Route(ROUTES[key], not_built(package), methods=list(methods)) for key, methods, package in STUBS]
