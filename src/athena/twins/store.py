"""The twins tables: one row per twin, and one table per part of it (channels, dials, samples, pages,
chores picked, memory facts, voice examples, missions and their turns, and how it sounds: the preview
kept for its voice), each row's body JSON.

Every table carries `space_id`, so erasing a Project erases its twins whole. A twin is the only twin
of its Project: the setup conversation is the Project's conversation, and its costs are the
Project's ledger rows on surface `twin`.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, cast

from athena.clock import mint, now_iso
from athena.contracts import TWINS_MAX, Sketch, TwinAsk, TwinState
from athena.drafts.sketch import empty
from athena.errors import ApiError
from athena.store import Store
from athena.twins import TWIN_PREFIX

TWIN_ID = re.compile(re.escape(TWIN_PREFIX) + r"[0-9a-f]{12}")
PARTS = (
    "channels",
    "dials",
    "samples",
    "pages",
    "chores",
    "memory",
    "examples",
    "missions",
    "turns",
    "previews",
)


class Twins:
    def __init__(self, store: Store) -> None:
        self._store = store

    # --- the twin's own row -------------------------------------------------------------------------

    def create(self, space_id: str) -> str:
        """A new twin at `setting_up` with an empty sketch. One per Project, TWINS_MAX in all."""
        twin_id = mint(TWIN_PREFIX)
        now = now_iso()
        with self._store.tx() as db:
            if db.execute("SELECT COUNT(*) FROM twins").fetchone()[0] >= TWINS_MAX:
                raise ApiError("bad_request", f"at most {TWINS_MAX} twins")
            if db.execute("SELECT 1 FROM twins WHERE space_id = ?", (space_id,)).fetchone():
                raise ApiError("bad_request", "this project already has a twin; open that one")
            db.execute(
                "INSERT INTO twins(id, space_id, state, need, sketch, asked, created, updated)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (twin_id, space_id, "setting_up", "", json.dumps(empty()), "{}", now, now),
            )
        return twin_id

    def row(self, twin_id: str) -> sqlite3.Row:
        """The twin's row, or ApiError("unknown_ref")."""
        rows = self._store.query("SELECT * FROM twins WHERE id = ?", (twin_id,))
        if not rows:
            raise ApiError("unknown_ref", "there is no such twin")
        return rows[0]

    def ids(self) -> list[str]:
        return [r["id"] for r in self._store.query("SELECT id FROM twins ORDER BY created, rowid")]

    def sketch(self, twin_id: str) -> Sketch:
        return cast("Sketch", json.loads(self.row(twin_id)["sketch"]))

    def asked(self, twin_id: str) -> dict[str, int]:
        return {str(k): int(v) for k, v in json.loads(self.row(twin_id)["asked"]).items()}

    def ask(self, twin_id: str) -> TwinAsk | None:
        raw = self.row(twin_id)["ask"]
        return cast("TwinAsk", json.loads(raw)) if raw else None

    def put(
        self,
        twin_id: str,
        *,
        sketch: Sketch | None = None,
        asked: dict[str, int] | None = None,
        ask: TwinAsk | bool | None = False,
        need: str | None = None,
        state: TwinState | None = None,
        since: str | None = None,
        paused_because: str | bool | None = False,
    ) -> None:
        """Writes the fields given and stamps `updated`. `ask` and `paused_because`: False leaves them,
        None clears them."""
        sets: list[str] = []
        args: list[Any] = []
        for column, value in (
            ("sketch", json.dumps(sketch) if sketch is not None else None),
            ("asked", json.dumps(asked) if asked is not None else None),
            ("need", need),
            ("state", state),
            ("since", since),
        ):
            if value is not None:
                sets.append(f"{column} = ?")
                args.append(value)
        if ask is not False:
            sets.append("ask = ?")
            args.append(json.dumps(ask) if ask else None)
        if paused_because is not False:
            sets.append("paused_because = ?")
            args.append(paused_because or None)
        sets.append("updated = ?")
        args.append(now_iso())
        with self._store.tx():
            self.row(twin_id)
            self._store.run(f"UPDATE twins SET {', '.join(sets)} WHERE id = ?", (*args, twin_id))

    def touch(self, twin_id: str) -> None:
        self.put(twin_id)

    # --- the parts: (owner, id) -> body, in position order --------------------------------------------

    def rows(self, part: str, owner: str) -> list[dict[str, Any]]:
        """The bodies of one part, in order; each carries its `id`."""
        table = _table(part)
        found = self._store.query(
            f"SELECT id, body FROM {table} WHERE owner = ? ORDER BY position, id", (owner,)
        )
        return [{**json.loads(r["body"]), "id": r["id"]} for r in found]

    def one(self, part: str, owner: str, row_id: str) -> dict[str, Any] | None:
        table = _table(part)
        found = self._store.query(f"SELECT body FROM {table} WHERE owner = ? AND id = ?", (owner, row_id))
        return {**json.loads(found[0]["body"]), "id": row_id} if found else None

    def save(self, part: str, owner: str, space_id: str, row_id: str, body: dict[str, Any]) -> None:
        """Inserts or replaces one row; a new row goes last, a replaced one keeps its place."""
        table = _table(part)
        stored = json.dumps({k: v for k, v in body.items() if k != "id"})
        with self._store.tx() as db:
            had = db.execute(
                f"SELECT position FROM {table} WHERE owner = ? AND id = ?", (owner, row_id)
            ).fetchone()
            if had is not None:
                db.execute(f"UPDATE {table} SET body = ? WHERE owner = ? AND id = ?", (stored, owner, row_id))
                return
            last = db.execute(f"SELECT COALESCE(MAX(position), -1) FROM {table} WHERE owner = ?", (owner,))
            db.execute(
                f"INSERT INTO {table}(owner, space_id, id, position, body) VALUES (?,?,?,?,?)",
                (owner, space_id, row_id, last.fetchone()[0] + 1, stored),
            )

    def replace(self, part: str, owner: str, space_id: str, bodies: list[dict[str, Any]]) -> None:
        """The part's rows become `bodies`, in that order."""
        table = _table(part)
        with self._store.tx() as db:
            db.execute(f"DELETE FROM {table} WHERE owner = ?", (owner,))
            for i, body in enumerate(bodies):
                db.execute(
                    f"INSERT INTO {table}(owner, space_id, id, position, body) VALUES (?,?,?,?,?)",
                    (
                        owner,
                        space_id,
                        body["id"],
                        i,
                        json.dumps({k: v for k, v in body.items() if k != "id"}),
                    ),
                )

    def drop(self, part: str, owner: str, row_id: str | None = None) -> None:
        """Deletes one row, or every row of the owner."""
        table = _table(part)
        if row_id is None:
            self._store.run(f"DELETE FROM {table} WHERE owner = ?", (owner,))
        else:
            self._store.run(f"DELETE FROM {table} WHERE owner = ? AND id = ?", (owner, row_id))


def _table(part: str) -> str:
    if part not in PARTS:
        raise ValueError(f"a twin has no part {part!r}")
    return f"twin_{part}"
