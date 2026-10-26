"""The memory wall.

Every memory is stamped with the space it was written in (CORE = ""). A view sees
`visible_spaces(active)`: core sees ("",), a project sees ("", project).
"""

from __future__ import annotations

import re
import sqlite3

from athena.clock import mint, now_iso
from athena.contracts import MemoryKind, MemoryPage, MemoryRow, SpaceCounts
from athena.errors import ApiError
from athena.store import Store

LINE_MAX = 240
TERMS_MAX = 12


def visible_spaces(active: str) -> tuple[str, ...]:
    return ("",) if active == "" else ("", active)


def _line(text: str) -> str:
    one = " ".join(text.split())
    return one if len(one) <= LINE_MAX else one[: LINE_MAX - 1].rstrip() + "…"


def _row(r: sqlite3.Row) -> MemoryRow:
    return {
        "id": r["id"],
        "kind": r["kind"],
        "line": _line(r["text"]),
        "created": r["created"],
        "space_id": r["space_id"],
    }


def _terms(query: str) -> list[str]:
    seen: list[str] = []
    for t in re.findall(r"\w+", query.lower()):
        if t not in seen:
            seen.append(t)
    return seen[:TERMS_MAX]


class Memory:
    def __init__(self, store: Store) -> None:
        self._store = store

    def _insert(self, kind: MemoryKind, space_id: str, text: str) -> MemoryRow:
        mem_id = mint("mem_")
        self._store.run(
            "INSERT INTO memory(id, kind, text, space_id, created) VALUES (?,?,?,?,?)",
            (mem_id, kind, text, space_id, now_iso()),
        )
        return self.get(mem_id)

    def append_episode(self, space_id: str, text: str) -> MemoryRow:
        return self._insert("episode", space_id, text)

    def write_fact(self, space_id: str, text: str) -> MemoryRow:
        return self._insert("fact", space_id, text)

    def recall(self, space_id: str, query: str, limit: int = 8) -> list[MemoryRow]:
        """Full-text over episodes and facts inside `visible_spaces(space_id)`."""
        terms = _terms(query)
        if not terms:
            return []
        visible = visible_spaces(space_id)
        marks = ",".join("?" * len(visible))
        if self._store.fts:
            match = " OR ".join(f'"{t}"' for t in terms)
            rows = self._store.query(
                "SELECT m.* FROM memory_fts JOIN memory m ON m.rowid = memory_fts.rowid "
                f"WHERE memory_fts MATCH ? AND m.space_id IN ({marks}) ORDER BY memory_fts.rank LIMIT ?",
                (match, *visible, limit),
            )
        else:
            like = " OR ".join("lower(m.text) LIKE ?" for _ in terms)
            rows = self._store.query(
                f"SELECT m.* FROM memory m WHERE ({like}) AND m.space_id IN ({marks}) "
                "ORDER BY m.rowid DESC LIMIT ?",
                (*(f"%{t}%" for t in terms), *visible, limit),
            )
        return [_row(r) for r in rows]

    def kept(self, space_id: str, limit: int = 12) -> list[MemoryRow]:
        """Exactly this space's facts (core's when ""), newest first: the frame's kept lines."""
        rows = self._store.query(
            "SELECT * FROM memory WHERE space_id = ? AND kind = 'fact' ORDER BY rowid DESC LIMIT ?",
            (space_id, limit),
        )
        return [_row(r) for r in rows]

    def page(self, space_id: str, kind: MemoryKind | None, limit: int) -> MemoryPage:
        """Exactly this space's memory (core's when ""), newest first."""
        where, params = "space_id = ?", [space_id]
        if kind is not None:
            where += " AND kind = ?"
            params.append(kind)
        with self._store.tx():  # one snapshot for the rows and the total
            rows = self._store.query(
                f"SELECT * FROM memory WHERE {where} ORDER BY rowid DESC LIMIT ?", (*params, limit)
            )
            total = self._store.query(f"SELECT COUNT(*) AS n FROM memory WHERE {where}", tuple(params))[0][
                "n"
            ]
        return {"rows": [_row(r) for r in rows], "showing": len(rows), "total": total}

    def get(self, mem_id: str) -> MemoryRow:
        """ApiError("unknown_ref") when absent."""
        rows = self._store.query("SELECT * FROM memory WHERE id = ?", (mem_id,))
        if not rows:
            raise ApiError("unknown_ref", "no such memory")
        return _row(rows[0])

    def make_core(self, space_id: str, mem_id: str) -> MemoryRow:
        """Facts only: ApiError("bad_request") for an episode, ("unknown_ref") when not in that space."""
        with self._store.tx() as db:
            row = db.execute("SELECT * FROM memory WHERE id = ?", (mem_id,)).fetchone()
            if row is None or space_id == "" or row["space_id"] != space_id:
                raise ApiError("unknown_ref", "no such memory in this project")
            if row["kind"] != "fact":
                raise ApiError("bad_request", "only a fact can be made core")
            db.execute("UPDATE memory SET space_id = '' WHERE id = ?", (mem_id,))
        return self.get(mem_id)

    def forget(self, mem_id: str) -> None:
        if self._store.run("DELETE FROM memory WHERE id = ?", (mem_id,)) == 0:
            raise ApiError("unknown_ref", "no such memory")

    def counts(self, space_id: str) -> SpaceCounts:
        rows = self._store.query(
            "SELECT kind, COUNT(*) AS n FROM memory WHERE space_id = ? GROUP BY kind", (space_id,)
        )
        by = {r["kind"]: r["n"] for r in rows}
        return {"episodes": by.get("episode", 0), "facts": by.get("fact", 0)}

    def erase_space(self, space_id: str) -> SpaceCounts:
        """Deletes every memory stamped with the space; answers what went."""
        with self._store.tx():
            gone = self.counts(space_id)
            self._store.run("DELETE FROM memory WHERE space_id = ?", (space_id,))
        return gone
