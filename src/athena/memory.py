"""The memory wall.

Every memory is stamped with the space it was written in (CORE = ""). A view sees
`visible_spaces(active)`: core sees ("",), a project sees ("", project).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Mapping
from typing import Any

from athena.clock import mint, now_iso
from athena.contracts import MemoryKind, MemoryPage, MemoryRow, SpaceCounts
from athena.errors import ApiError
from athena.store import Store

LINE_MAX = 240
TERMS_MAX = 12
#: What replicates between devices (ADR 0017): write-once kinds in the core space, ids shaped like our own.
REPLICATED_KINDS = ("episode", "fact")
_MEM_ID = re.compile(r"^mem_[0-9a-f]{12}$")
_STAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
RECEIVE_TEXT_MAX = 1_048_576


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

    # --- replication (ADR 0017): core episodes and facts only; a project's space ids are per-device ---

    def replicable_page(self, since: str | None, after: str | None, limit: int) -> list[dict[str, Any]]:
        """Core episodes and facts from `since` (inclusive; past `after` when given) by (created, id)."""
        marks = ",".join("?" * len(REPLICATED_KINDS))
        where, params = f"space_id = '' AND kind IN ({marks})", list(REPLICATED_KINDS)
        if since is not None and after is not None:
            where += " AND (created > ? OR (created = ? AND id > ?))"
            params += [since, since, after]
        elif since is not None:
            where += " AND created >= ?"
            params.append(since)
        rows = self._store.query(
            f"SELECT id, kind, text, created FROM memory WHERE {where} ORDER BY created, id LIMIT ?",
            (*params, limit),
        )
        return [{"id": r["id"], "kind": r["kind"], "text": r["text"], "created": r["created"]} for r in rows]

    def replicable(self, mem_id: str) -> dict[str, Any] | None:
        """One core episode or fact as a replication row, or None for anything else."""
        rows = self._store.query(
            "SELECT id, kind, text, created FROM memory WHERE id = ? AND space_id = ''", (mem_id,)
        )
        if not rows or rows[0]["kind"] not in REPLICATED_KINDS:
            return None
        r = rows[0]
        return {"id": r["id"], "kind": r["kind"], "text": r["text"], "created": r["created"]}

    def receive(self, row: Mapping[str, Any]) -> str:
        """File a memory another device wrote, under its own id and stamp: `added`, `same` or `differs`.

        Idempotent. Core space only, episodes and facts only, an id shaped like ours: anything else is
        ValueError. An id already held with other text (or kept in a project) stays as it is and answers
        `differs`. It goes through the same insert as a local write, so the FTS triggers keep recall honest.
        """
        mem_id, kind, text, created = (row.get(k) for k in ("id", "kind", "text", "created"))
        if not (isinstance(mem_id, str) and _MEM_ID.match(mem_id)):
            raise ValueError("not a memory id")
        if kind not in REPLICATED_KINDS:
            raise ValueError("only an episode or a fact is received")
        if not isinstance(text, str) or not text or len(text) > RECEIVE_TEXT_MAX:
            raise ValueError("a memory has text")
        if not isinstance(created, str) or not _STAMP.match(created):
            raise ValueError("created is a UTC stamp")
        with self._store.tx() as db:
            have = db.execute("SELECT kind, text, space_id FROM memory WHERE id = ?", (mem_id,)).fetchone()
            if have is not None:
                same = have["text"] == text and have["kind"] == kind and have["space_id"] == ""
                return "same" if same else "differs"
            db.execute(
                "INSERT INTO memory(id, kind, text, space_id, created) VALUES (?,?,?,?,?)",
                (mem_id, kind, text, "", created),
            )
        return "added"


def memory_sha(text: str) -> str:
    """The digest two devices compare a memory by."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
