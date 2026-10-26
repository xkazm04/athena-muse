"""The gate: GATED actions file a card; a card resolves exactly once."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import Any

from athena.clock import mint, now_iso
from athena.contracts import ActionName, Card, CardState, Verdict
from athena.errors import ApiError
from athena.events import Events
from athena.store import Store

# Runs an approved action and returns a plain-words outcome. Registered by the turn package (WP3).
Executor = Callable[[Card], str]


def _card(r: sqlite3.Row) -> Card:
    c: Card = {
        "id": r["id"],
        "space_id": r["space_id"],
        "action": r["action"],
        "label": r["label"],
        "args": json.loads(r["args"]),
        "state": r["state"],
        "created": r["created"],
    }
    if r["resolved"] is not None:
        c["resolved"] = r["resolved"]
    return c


class Gate:
    def __init__(self, store: Store, events: Events) -> None:
        self._store = store
        self._events = events
        self._executor: Executor | None = None

    def set_executor(self, executor: Executor) -> None:
        self._executor = executor

    def file(self, space_id: str, action: ActionName, args: dict[str, Any], label: str) -> Card:
        """Publishes `card_filed`."""
        card_id = mint("card_")
        self._store.run(
            "INSERT INTO cards(id, space_id, action, label, args, state, created) "
            "VALUES (?,?,?,?,?,'waiting',?)",
            (card_id, space_id, action, label, json.dumps(args), now_iso()),
        )
        card = self.get(card_id)
        self._events.publish({"type": "card_filed", "card": card})
        return card

    def resolve(self, card_id: str, verdict: Verdict) -> Card:
        """One conditional UPDATE (`WHERE state = 'waiting'`); the loser of a race gets
        ApiError("bad_request", "already decided"). Approve runs the executor once, after the
        UPDATE won. Publishes `card_resolved`."""
        state = "approved" if verdict == "approve" else "declined"
        changed = self._store.run(
            "UPDATE cards SET state = ?, resolved = ? WHERE id = ? AND state = 'waiting'",
            (state, now_iso(), card_id),
        )
        card = self.get(card_id)  # unknown_ref when absent
        if changed == 0:
            raise ApiError("bad_request", "already decided")
        if verdict == "approve" and self._executor is not None:
            self._executor(card)
        self._events.publish({"type": "card_resolved", "card": card})
        return card

    def get(self, card_id: str) -> Card:
        rows = self._store.query("SELECT * FROM cards WHERE id = ?", (card_id,))
        if not rows:
            raise ApiError("unknown_ref", "no such card")
        return _card(rows[0])

    def list(self, state: CardState | None = None) -> list[Card]:
        if state is None:
            rows = self._store.query("SELECT * FROM cards ORDER BY rowid DESC")
        else:
            rows = self._store.query("SELECT * FROM cards WHERE state = ? ORDER BY rowid DESC", (state,))
        return [_card(r) for r in rows]
