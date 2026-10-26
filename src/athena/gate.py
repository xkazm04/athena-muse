"""The gate: GATED actions file a card; a card resolves exactly once. Owned by WP1. Stub."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from athena.contracts import ActionName, Card, CardState, Verdict
from athena.events import Events
from athena.store import Store

# Runs an approved action and returns a plain-words outcome. Registered by the turn package (WP3).
Executor = Callable[[Card], str]


class Gate:
    def __init__(self, store: Store, events: Events) -> None:
        raise NotImplementedError

    def set_executor(self, executor: Executor) -> None:
        raise NotImplementedError

    def file(self, space_id: str, action: ActionName, args: dict[str, Any], label: str) -> Card:
        """Publishes `card_filed`."""
        raise NotImplementedError

    def resolve(self, card_id: str, verdict: Verdict) -> Card:
        """One conditional UPDATE (`WHERE state = 'waiting'`); the loser of a race gets
        ApiError("bad_request", "already decided"). Approve runs the executor once, after the
        UPDATE won. Publishes `card_resolved`."""
        raise NotImplementedError

    def get(self, card_id: str) -> Card:
        raise NotImplementedError

    def list(self, state: CardState | None = None) -> list[Card]:
        raise NotImplementedError
