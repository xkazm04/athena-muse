"""The records table and its API: append-only revisions of a project's records, and the rights rule.

A put validates the body under its kind, computes the key, and appends revision rev+1 of that key
(1 for a new key). A body equal to the latest one appends nothing. Nothing here edits or deletes a
row, except erasing a whole project.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from typing import Any

from athena.clock import mint, now_iso
from athena.contracts import (
    RECORDS_PAGE_MAX,
    KindsBody,
    MayRender,
    RecordBy,
    RecordItem,
    RecordKind,
    TrackVerdict,
    TrackVerdictBody,
)
from athena.errors import ApiError
from athena.events import Events
from athena.records.kinds import KINDS, check_kind, key_of, no_such_kind, normalise_ref, validate
from athena.store import Store

log = logging.getLogger(__name__)

RECORD_PREFIX = "rec_"
_BY: tuple[RecordBy, ...] = ("person", "athena", "routine", "daemon")
_VERDICTS: tuple[TrackVerdict, ...] = ("keep", "pass", "later")


def _item(r: sqlite3.Row) -> RecordItem:
    return {
        "id": r["id"],
        "space_id": r["space_id"],
        "kind": r["kind"],
        "key": r["key"],
        "rev": r["rev"],
        "body": json.loads(r["body"]),
        "by": r["by"],
        "created": r["created"],
    }


class Records:
    def __init__(self, store: Store, events: Events | None = None) -> None:
        self._store = store
        self._events = events
        #: Called after a put changes how many keys a kind has: (space_id, kind, before, after). The
        #: report's shape trigger hangs here (set by athena.report.routes); a verdict never changes a count.
        self.on_change: Callable[[str, RecordKind, int, int], None] | None = None

    # --- writing ------------------------------------------------------------------------------------

    def _space(self, space_id: str) -> None:
        if not space_id or not self._store.query("SELECT 1 FROM spaces WHERE id = ?", (space_id,)):
            raise ApiError("unknown_ref", "no such project")

    def _file_row(self, space_id: str, file_id: str) -> bool:
        return bool(
            self._store.query("SELECT 1 FROM files WHERE id = ? AND space_id = ?", (file_id, space_id))
        )

    def prepare(self, space_id: str, kind: RecordKind, body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """(key, cleaned body), or ApiError in plain words: the kind's validator, its key rule, and
        that every file id it names is one of this project's files. A thread's key comes in
        `body["key"]`."""
        self._space(space_id)
        kind = check_kind(kind)
        cleaned = validate(kind, body)
        given = body.get("key") if kind == "thread" and isinstance(body, dict) else None
        key = key_of(kind, {**cleaned, "key": given} if given is not None else cleaned)
        for field in ("file_id", "output_file_id"):
            file_id = cleaned.get(field)
            if file_id is not None and not self._file_row(space_id, str(file_id)):
                raise ApiError(
                    "bad_request", f"a {kind} record: {file_id} is not one of this project's files"
                )
        return key, cleaned

    def put(self, space_id: str, kind: RecordKind, body: dict[str, Any], by: RecordBy) -> RecordItem:
        """Validate, then append a revision (rev+1 of its key, or 1). An unchanged body appends nothing
        and answers the latest revision."""
        if by not in _BY:
            raise ApiError("bad_request", f"by must be one of {', '.join(_BY)}")
        key, cleaned = self.prepare(space_id, kind, body)
        return self._append(space_id, kind, key, cleaned, by)

    def _append(
        self, space_id: str, kind: RecordKind, key: str, body: dict[str, Any], by: RecordBy
    ) -> RecordItem:
        record_id = mint(RECORD_PREFIX)
        with self._store.tx() as db:
            latest = db.execute(
                "SELECT * FROM records WHERE space_id = ? AND kind = ? AND key = ? ORDER BY rev DESC LIMIT 1",
                (space_id, kind, key),
            ).fetchone()
            if latest is not None and json.loads(latest["body"]) == body:
                return _item(latest)
            before = self._count(db, space_id, kind)
            db.execute(
                "INSERT INTO records(id, space_id, kind, key, rev, body, by, created) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    record_id,
                    space_id,
                    kind,
                    key,
                    1 if latest is None else latest["rev"] + 1,
                    json.dumps(body, ensure_ascii=False, sort_keys=True),
                    by,
                    now_iso(),
                ),
            )
            after = self._count(db, space_id, kind)
        if after != before and self.on_change is not None:
            try:
                self.on_change(space_id, kind, before, after)
            except Exception:  # the report's trigger never fails a put
                log.exception("records.on_change failed for %s %s", space_id, kind)
        return self.get(record_id)

    def verdict(self, record_id: str, body: TrackVerdictBody) -> RecordItem:
        """A track's verdict, as a new revision written by the person."""
        record = self.get(record_id)
        if record["kind"] != "track":
            raise ApiError("bad_request", "only a track takes a verdict")
        if not isinstance(body, dict) or body.get("verdict") not in _VERDICTS:
            raise ApiError("bad_request", "the verdict must be keep, pass or later")
        current = self.latest(record["space_id"], "track", record["key"])[0]["body"]
        merged = {**current, "verdict": body["verdict"]}
        for field in ("genre", "note"):
            if field in body:
                merged[field] = body[field]
        cleaned = validate("track", merged)
        return self._append(record["space_id"], "track", record["key"], cleaned, "person")

    # --- reading ------------------------------------------------------------------------------------

    def latest(
        self, space_id: str, kind: RecordKind | None = None, key: str | None = None
    ) -> list[RecordItem]:
        """The latest revision of every key (newest first), at most RECORDS_PAGE_MAX."""
        where, params = ["space_id = ?"], [space_id]
        if kind is not None:
            where.append("kind = ?")
            params.append(check_kind(kind))
        if key is not None:
            where.append("key = ?")
            params.append(normalise_ref(key))
        rows = self._store.query(
            "SELECT r.* FROM records r JOIN ("
            f"  SELECT kind, key, MAX(rev) AS rev FROM records WHERE {' AND '.join(where)} GROUP BY kind, key"
            ") m ON r.kind = m.kind AND r.key = m.key AND r.rev = m.rev "
            "WHERE r.space_id = ? ORDER BY r.rowid DESC LIMIT ?",
            (*params, space_id, RECORDS_PAGE_MAX),
        )
        return [_item(r) for r in rows]

    def get(self, record_id: str) -> RecordItem:
        rows = self._store.query("SELECT * FROM records WHERE id = ?", (record_id,))
        if not rows:
            raise ApiError("unknown_ref", "no such record")
        return _item(rows[0])

    def history(self, record_id: str) -> list[RecordItem]:
        """Every revision of that record's key, oldest first."""
        record = self.get(record_id)
        rows = self._store.query(
            "SELECT * FROM records WHERE space_id = ? AND kind = ? AND key = ? ORDER BY rev ASC",
            (record["space_id"], record["kind"], record["key"]),
        )
        return [_item(r) for r in rows]

    @staticmethod
    def _count(db: sqlite3.Connection, space_id: str, kind: RecordKind) -> int:
        row = db.execute(
            "SELECT COUNT(DISTINCT key) FROM records WHERE space_id = ? AND kind = ?", (space_id, kind)
        ).fetchone()
        return int(row[0])

    def count(self, space_id: str, kind: RecordKind) -> int:
        """Keys of that kind (latest revisions), for the report's shape trigger."""
        rows = self._store.query(
            "SELECT COUNT(DISTINCT key) AS n FROM records WHERE space_id = ? AND kind = ?",
            (space_id, check_kind(kind)),
        )
        return int(rows[0]["n"])

    def has_file(self, space_id: str, file_id: str) -> bool:
        return self._file_row(space_id, file_id)

    # --- the kinds a project keeps ------------------------------------------------------------------

    def kinds(self, space_id: str) -> list[RecordKind]:
        self._space(space_id)
        rows = self._store.query("SELECT kinds FROM spaces WHERE id = ?", (space_id,))
        kept: list[RecordKind] = json.loads(rows[0]["kinds"] or "[]")
        return kept

    def set_kinds(self, space_id: str, body: KindsBody) -> KindsBody:
        self._space(space_id)
        given = body.get("kinds") if isinstance(body, dict) else None
        if not isinstance(given, list):
            raise ApiError("bad_request", "send kinds as a list")
        kinds: list[RecordKind] = []
        for kind in given:
            if kind not in KINDS:
                raise ApiError("bad_request", no_such_kind(kind))
            if kind not in kinds:
                kinds.append(kind)
        self._store.run(
            "UPDATE spaces SET kinds = ?, updated = ? WHERE id = ?", (json.dumps(kinds), now_iso(), space_id)
        )
        if self._events is not None:
            self._events.publish({"type": "space_changed", "space_id": space_id})
        return {"kinds": kinds}

    def erase(self, space_id: str) -> int:
        """Removes every record of the project; answers how many rows went (spaces.erase does this too)."""
        return self._store.run("DELETE FROM records WHERE space_id = ?", (space_id,))


def may_render(records: Records, space_id: str, track_key: str) -> MayRender:
    """The rights rule (G13): kept, its creator's agreement agreed with a thread as evidence, a plan
    tier known and not free, and a file present. A function, not prose.

    Reasons come in this order. With no agreement at all, the three reasons about the agreement
    (agreed, thread, plan) are not added: "no agreement" already says it."""
    reasons: list[str] = []
    found = records.latest(space_id, "track", track_key)
    track = found[0]["body"] if found else {}
    if track.get("verdict") != "keep":
        reasons.append("not kept")
    creator_key = track.get("creator_key")
    agreements = records.latest(space_id, "agreement", creator_key) if creator_key else []
    if not agreements:
        reasons.append("no agreement")
    else:
        agreement = agreements[0]["body"]
        if agreement.get("state") != "agreed":
            reasons.append("agreement not agreed")
        thread_key = agreement.get("thread_key")
        if not thread_key or not records.latest(space_id, "thread", thread_key):
            reasons.append("no thread as evidence")
        plan = agreement.get("plan")
        if plan in (None, "unknown"):
            reasons.append("plan tier unknown")
        elif plan == "free":
            reasons.append("free plan cannot be licensed")
    file_id = track.get("file_id")
    if not file_id or not records.has_file(space_id, str(file_id)):
        reasons.append("no file")
    return {"ok": not reasons, "reasons": reasons}
