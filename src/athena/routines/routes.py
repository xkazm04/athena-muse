"""space_routines, routine, routine_run, routine_runs. STUB (WP2.0) - WP2.1."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.routing import BaseRoute

if TYPE_CHECKING:
    from athena.app import Daemon


def routes(daemon: Daemon) -> list[BaseRoute]:
    return []
