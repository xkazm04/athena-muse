"""The records routes: space_records, record_history, record_verdict, space_kinds. STUB (WP1.0) - WP1.1."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.routing import BaseRoute

if TYPE_CHECKING:
    from athena.app import Daemon


def routes(daemon: Daemon) -> list[BaseRoute]:
    return []
