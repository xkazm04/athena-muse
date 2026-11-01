"""The report routes: space_report, space_report_compose, space_report_pins; and the shape trigger's
wiring onto `daemon.records.on_change`. STUB (WP1.0) - WP1.2."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.routing import BaseRoute

if TYPE_CHECKING:
    from athena.app import Daemon


def routes(daemon: Daemon) -> list[BaseRoute]:
    return []
