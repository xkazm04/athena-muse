"""The drafts table: one row per draft, its JSON columns stored as text, erased with its space."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import typing
from pathlib import Path
from typing import Any, cast

from athena.clock import mint, now_iso
from athena.contracts import Coverage, Draft, Slot
from athena.drafts import DRAFT_PREFIX
from athena.drafts.rubric import SLOTS, agreed, coverage, open_slots
from athena.drafts.sketch import empty
from athena.errors import ApiError
from athena.store import Store

DRAFT_ID = re.compile(re.escape(DRAFT_PREFIX) + r"[0-9a-f]{12}")
_SLOT_NAMES = frozenset(typing.get_args(Slot))
_OPTIONAL = ("chore_id", "expected", "key", "bench", "verdict", "note")
_JSON_OPTIONAL = frozenset({"expected", "key", "bench"})


def folder(data_dir: Path | None, draft_id: str) -> Path | None:
    """`<data_dir>/drafts/<draft_id>/`, or None with nothing on disk or an id that is not a draft's."""
    if data_dir is None or not DRAFT_ID.fullmatch(draft_id):
        return None
    return data_dir / "drafts" / draft_id


def remove_folder(data_dir: Path | None, draft_id: str) -> None:
    path = folder(data_dir, draft_id)
    if path is not None and path.is_dir():
        shutil.rmtree(path)


def _slots(raw: str) -> frozenset[Slot]:
    return frozenset(cast("Slot", s) for s in json.loads(raw) if s in _SLOT_NAMES)


class Drafts:
    def __init__(self, store: Store, data_dir: Path | None = None) -> None:
        self._store = store
        self._data_dir = data_dir

    def folder(self, draft_id: str) -> Path | None:
        """Where the draft's authored files live; None with nothing on disk."""
        return folder(self._data_dir, draft_id)

    def _row(self, draft_id: str) -> sqlite3.Row:
        rows = self._store.query("SELECT * FROM drafts WHERE id = ?", (draft_id,))
        if not rows:
            raise ApiError("unknown_ref", "there is no such draft")
        return rows[0]

    @staticmethod
    def _draft(r: sqlite3.Row) -> Draft:
        cov = cast("Coverage", json.loads(r["coverage"]))
        out: Draft = {
            "id": r["id"],
            "space_id": r["space_id"],
            "step": r["step"],
            "need": r["need"],
            "sketch": json.loads(r["sketch"]),
            "coverage": cov,
            "agreed": agreed(cov),
            "created": r["created"],
            "updated": r["updated"],
        }
        loose = cast("dict[str, Any]", out)
        for col in _OPTIONAL:
            if r[col] is not None:
                loose[col] = json.loads(r[col]) if col in _JSON_OPTIONAL else r[col]
        return out

    def create(self, space_id: str, need: str) -> Draft:
        """A new draft at step `describe` with an empty sketch, in an existing space."""
        draft_id = mint(DRAFT_PREFIX)
        now = now_iso()
        sketch = empty()
        self._store.run(
            "INSERT INTO drafts(id, space_id, step, need, sketch, coverage, created, updated)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                draft_id,
                space_id,
                "describe",
                need,
                json.dumps(sketch),
                json.dumps(coverage(sketch)),
                now,
                now,
            ),
        )
        return self.get(draft_id)

    def get(self, draft_id: str) -> Draft:
        """The draft, or ApiError("unknown_ref")."""
        return self._draft(self._row(draft_id))

    def skipped(self, draft_id: str) -> frozenset[Slot]:
        """The slots the person waved through with "That's enough, write it"."""
        return _slots(self._row(draft_id)["skipped"])

    def asked(self, draft_id: str) -> dict[Slot, int]:
        """Questions asked per slot (the first, then follow-ups)."""
        raw = json.loads(self._row(draft_id)["asked"])
        return {cast("Slot", k): int(v) for k, v in raw.items() if k in _SLOT_NAMES}

    def put(
        self,
        draft: Draft,
        *,
        skipped: frozenset[Slot] | None = None,
        asked: dict[Slot, int] | None = None,
    ) -> Draft:
        """Writes the whole draft back, stamping `updated`; answers it as stored.

        Coverage is recomputed from the sketch and the skipped slots; `coverage` and `agreed` on the
        given draft are ignored. A skipped slot that gains a node (a new node, or one moved into it)
        is no longer skipped.
        """
        with self._store.tx():
            row = self._row(draft["id"])
            before = {n["id"]: n["slot"] for n in json.loads(row["sketch"])["nodes"]}
            skip = set(_slots(row["skipped"]) if skipped is None else skipped)
            for node in draft["sketch"]["nodes"]:
                if before.get(node["id"]) != node["slot"]:
                    skip.discard(node["slot"])
            asks = json.loads(row["asked"]) if asked is None else dict(asked)
            loose = cast("dict[str, Any]", draft)
            optional = [
                (json.dumps(loose[c]) if c in _JSON_OPTIONAL else loose[c]) if c in loose else None
                for c in _OPTIONAL
            ]
            self._store.run(
                "UPDATE drafts SET step = ?, need = ?, sketch = ?, coverage = ?, skipped = ?, asked = ?, "
                + "".join(f"{c} = ?, " for c in _OPTIONAL)
                + "updated = ? WHERE id = ?",
                (
                    draft["step"],
                    draft["need"],
                    json.dumps(draft["sketch"]),
                    json.dumps(coverage(draft["sketch"], frozenset(skip))),
                    json.dumps([s for s in SLOTS if s in skip]),
                    json.dumps(asks),
                    *optional,
                    now_iso(),
                    draft["id"],
                ),
            )
        return self.get(draft["id"])

    def skip_open(self, draft_id: str) -> Draft:
        """ "That's enough, write it": every slot at 0 or 0.5 (no confirmed node) becomes skipped."""
        with self._store.tx():
            draft = self.get(draft_id)
            skip = self.skipped(draft_id) | frozenset(open_slots(draft["coverage"]))
            return self.put(draft, skipped=skip)

    def delete(self, draft_id: str) -> None:
        """Abandons the draft: its row and its folder. Its Project stays."""
        if self._store.run("DELETE FROM drafts WHERE id = ?", (draft_id,)) == 0:
            raise ApiError("unknown_ref", "there is no such draft")
        remove_folder(self._data_dir, draft_id)

    def in_space(self, space_id: str) -> list[str]:
        """The ids of the drafts in a space."""
        return [r["id"] for r in self._store.query("SELECT id FROM drafts WHERE space_id = ?", (space_id,))]
