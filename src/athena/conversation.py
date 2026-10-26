"""A conversation per space."""

from __future__ import annotations

import sqlite3

from athena.clock import mint, now_iso
from athena.contracts import Role, Turn
from athena.store import Store


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
    ) -> Turn:
        turn_id = mint("turn_")
        self._store.run(
            "INSERT INTO turns(id, space_id, role, text, created, cost_usd, card_id) VALUES (?,?,?,?,?,?,?)",
            (turn_id, space_id, role, text, now_iso(), cost_usd, card_id),
        )
        return _turn(self._store.query("SELECT * FROM turns WHERE id = ?", (turn_id,))[0])

    def list(self, space_id: str, limit: int = 200) -> list[Turn]:
        """Oldest first, the last `limit` turns."""
        rows = self._store.query(
            "SELECT * FROM turns WHERE space_id = ? ORDER BY rowid DESC LIMIT ?", (space_id, limit)
        )
        return [_turn(r) for r in reversed(rows)]

    def erase_space(self, space_id: str) -> int:
        return self._store.run("DELETE FROM turns WHERE space_id = ?", (space_id,))
