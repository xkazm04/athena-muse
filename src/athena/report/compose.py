"""Composing, pins and the report's view. STUB (WP1.0) - WP1.2 fills it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from athena.contracts import PinsBody, ReportView

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.engine import Engine


def view(daemon: Daemon, space_id: str) -> ReportView:
    """The stored spec (or the default), validated, with every block's value computed now."""
    raise NotImplementedError


def compose(daemon: Daemon, engine: Engine, space_id: str) -> ReportView:
    """One engine call; the answer passes the validation door before it is stored (a failure keeps the
    last good spec); pinned blocks are kept by id; one ledger row, surface `report`."""
    raise NotImplementedError


def set_pins(daemon: Daemon, space_id: str, body: PinsBody) -> ReportView:
    raise NotImplementedError


def on_records_changed(
    daemon: Daemon, engine: Engine, space_id: str, kind: str, before: int, after: int
) -> bool:
    """The shape trigger: a kind going 0 -> >=1 or >=1 -> 0 recomposes, at most once per RECOMPOSE_MIN_S;
    a verdict alone never does. Answers whether it recomposed."""
    raise NotImplementedError
