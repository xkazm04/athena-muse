"""Stage turns: each reply is a frame (her line, sketch ops, at most one ask). Surface `design`."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from athena.app import Daemon
from athena.contracts import Draft
from athena.engine import Engine


def start(daemon: Daemon, engine: Engine, need: str) -> tuple[Draft, Iterator[dict[str, Any]]]:
    """Creates the Project and the draft, makes the Project active, and answers the first stage turn
    as a TurnEvent stream. Validates before returning so the route can answer a 4xx."""
    raise NotImplementedError


def say(
    daemon: Daemon, engine: Engine, draft_id: str, text: str, choice: str | None
) -> Iterator[dict[str, Any]]:
    """One stage turn: TurnEvents plus `sketch`, `ask` and `coverage`. Validates before returning."""
    raise NotImplementedError


def confirm(daemon: Daemon, draft_id: str, node_ids: list[str]) -> Draft:
    """The person accepts Athena's proposed nodes; coverage is recomputed."""
    raise NotImplementedError
