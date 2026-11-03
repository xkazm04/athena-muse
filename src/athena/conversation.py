"""A conversation per space."""

from __future__ import annotations

import builtins
import json
import sqlite3

from athena.clock import mint, now_iso
from athena.contracts import Role, Turn, TurnPart
from athena.store import Store


def _parts(raw: str | None) -> list[TurnPart] | None:
    """A turn's stored parts; None for a turn stored before parts were kept (or a row that does not
    read), which then shows as its text and card alone."""
    if not raw:
        return None
    try:
        parts = json.loads(raw)
    except ValueError:
        return None
    return parts if isinstance(parts, list) else None


def _turn(r: sqlite3.Row) -> Turn:
    t: Turn = {
        "id": r["id"],
        "space_id": r["space_id"],
        "role": r["role"],
        "text": r["text"],
        "created": r["created"],
    }
    if r["cost_usd"] is not None:
        t["cost_usd"] = float(r["cost_usd"])
    if r["card_id"] is not None:
        t["card_id"] = r["card_id"]
    parts = _parts(r["parts"])
    if parts is not None:
        t["parts"] = parts
    if r["duration_ms"] is not None:
        t["duration_ms"] = int(r["duration_ms"])
    if r["stopped"] is not None:
        t["stopped"] = r["stopped"]
    return t


class Conversation:
    def __init__(self, store: Store) -> None:
        self._store = store

    def append(
        self,
        space_id: str,
        role: Role,
        text: str,
        *,
        cost_usd: float | None = None,
        card_id: str | None = None,
        parts: list[TurnPart] | None = None,
        duration_ms: int | None = None,
        stopped: str | None = None,
    ) -> Turn:
        """`parts` is an Athena turn's text runs, tool lines and cards in the order they streamed;
        `text` stays the whole reply, which the next turn's history reads. `duration_ms` is how long
        the turn took; `stopped` is why the engine ended it early (ADR 0024)."""
        turn_id = mint("turn_")
        stored = json.dumps(parts, ensure_ascii=False) if parts is not None else None
        self._store.run(
            "INSERT INTO turns(id, space_id, role, text, created, cost_usd, card_id, parts, duration_ms,"
            " stopped) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (turn_id, space_id, role, text, now_iso(), cost_usd, card_id, stored, duration_ms, stopped),
        )
        return _turn(self._store.query("SELECT * FROM turns WHERE id = ?", (turn_id,))[0])

    def list(self, space_id: str, limit: int = 200) -> list[Turn]:
        """Oldest first, the last `limit` turns."""
        rows = self._store.query(
            "SELECT * FROM turns WHERE space_id = ? ORDER BY rowid DESC LIMIT ?", (space_id, limit)
        )
        return [_turn(r) for r in reversed(rows)]

    def said(self, space_id: str, limit: int) -> builtins.list[Turn]:
        """What was said, oldest first, for a model's history: the last `limit` turns without the ones
        the engine stopped (they hold no reply of hers, and an empty assistant line misleads a model)."""
        return [t for t in self.list(space_id, limit) if "stopped" not in t]

    def erase_space(self, space_id: str) -> int:
        return self._store.run("DELETE FROM turns WHERE space_id = ?", (space_id,))
