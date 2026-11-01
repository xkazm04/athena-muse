"""The routines and routine_runs tables (business Phase 2), and the host's in-process claims.

A routine's `last_run` and `next_at` are computed on read. History is keyed on completions: the next
run is due a cadence after the last run that did its work (ran, partial or failed), never after a skip
and never after an in-progress marker (a run is written once, when it ends). Each routine keeps its
newest RUNS_KEPT runs; older ones are pruned on write. Both tables are erased with the space.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit

from athena.clock import mint, now_iso
from athena.contracts import (
    CADENCE_MIN_S,
    ROUTINE_CEILING_CENTS,
    RUNS_KEPT,
    RecordKind,
    Routine,
    RoutineBody,
    RoutineKind,
    RoutineRun,
)
from athena.errors import ApiError
from athena.store import Store

if TYPE_CHECKING:
    from athena.events import Events

ROUTINE_PREFIX = "rtn_"
RUN_PREFIX = "run_"
TWIN_PREFIX = "twin:"
URL_MAX = 500
#: The kinds a project must keep for each default routine.
NEEDS: dict[RoutineKind, tuple[RecordKind, ...]] = {
    "watch": ("creator", "track"),
    "inbox": ("thread",),
    "stats": ("stat",),
    "outreach": ("agreement", "thread"),
}
#: Outcomes that are a completion: the cadence counts from them.
COMPLETED = ("ran", "partial", "failed")
TWIN_POLL_ENV = "ATHENA_TWIN_POLL"


def twin_cadence() -> int | None:
    """The twin routines' cadence `ATHENA_TWIN_POLL` sets (a whole number of seconds), else None."""
    raw = os.environ.get(TWIN_POLL_ENV, "").strip()
    try:
        seconds = int(raw)
    except ValueError:
        return None
    return seconds if seconds > 0 else None


def _parse(at: str) -> datetime:
    return datetime.fromisoformat(at.replace("Z", "+00:00"))


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _run(r: Any) -> RoutineRun:
    run = cast("RoutineRun", json.loads(r["body"]))
    return run


def min_cadence(kind: RoutineKind) -> int:
    """The shortest cadence a person may set: CADENCE_MIN_S, or the kind's own default when that is
    shorter (a twin's 300 s, so it can be set back to what it was)."""
    from athena.routines.kinds import CADENCE_S

    return min(CADENCE_MIN_S, CADENCE_S[kind])


class Routines:
    def __init__(self, store: Store, events: Events | None = None) -> None:
        self._store = store
        self._events = events
        self._claims: set[str] = set()
        self._claims_lock = threading.Lock()

    # --- the in-process single-flight claim ---------------------------------------------------------

    def claim(self, routine_id: str) -> bool:
        """Takes the routine's claim: False when a run of it is already going in this process."""
        with self._claims_lock:
            if routine_id in self._claims:
                return False
            self._claims.add(routine_id)
            return True

    def release(self, routine_id: str) -> None:
        with self._claims_lock:
            self._claims.discard(routine_id)

    def running(self, routine_id: str) -> bool:
        with self._claims_lock:
            return routine_id in self._claims

    # --- reading ------------------------------------------------------------------------------------

    def _routine(self, r: Any) -> Routine:
        out: Routine = {
            "id": r["id"],
            "space_id": r["space_id"],
            "kind": cast("RoutineKind", r["kind"]),
            "name": r["name"],
            "cadence_s": int(r["cadence_s"]),
            "ceiling_usd": float(r["ceiling_usd"]),
            "state": "paused" if r["state"] == "paused" else "on",
        }
        if r["url"]:
            out["url"] = r["url"]
        last = self.last(r["id"])
        if last is not None:
            out["last_run"] = last
        if out["state"] == "on":
            out["next_at"] = _iso(self.due_at(r["id"], int(r["cadence_s"]), r["created"]))
        return out

    def of_space(self, space_id: str) -> list[Routine]:
        rows = self._store.query(
            "SELECT * FROM routines WHERE space_id = ? ORDER BY created, rowid", (space_id,)
        )
        return [self._routine(r) for r in rows]

    def ids(self) -> list[str]:
        return [r["id"] for r in self._store.query("SELECT id FROM routines ORDER BY created, rowid")]

    def get(self, routine_id: str) -> Routine:
        rows = self._store.query("SELECT * FROM routines WHERE id = ?", (routine_id,))
        if not rows:
            raise ApiError("unknown_ref", "there is no such routine")
        return self._routine(rows[0])

    def runs(self, routine_id: str) -> list[RoutineRun]:
        self.get(routine_id)
        rows = self._store.query(
            "SELECT body FROM routine_runs WHERE routine_id = ? ORDER BY started DESC, rowid DESC LIMIT ?",
            (routine_id, RUNS_KEPT),
        )
        return [_run(r) for r in rows]

    def last(self, routine_id: str) -> RoutineRun | None:
        rows = self._store.query(
            "SELECT body FROM routine_runs WHERE routine_id = ? ORDER BY started DESC, rowid DESC LIMIT 1",
            (routine_id,),
        )
        return _run(rows[0]) if rows else None

    def last_completed(self, routine_id: str) -> RoutineRun | None:
        marks = ",".join("?" for _ in COMPLETED)
        rows = self._store.query(
            f"SELECT body FROM routine_runs WHERE routine_id = ? AND outcome IN ({marks}) "
            "ORDER BY started DESC, rowid DESC LIMIT 1",
            (routine_id, *COMPLETED),
        )
        return _run(rows[0]) if rows else None

    def due_at(self, routine_id: str, cadence_s: int, created: str) -> datetime:
        """A cadence after the last completed run; at once (its creation) when it never completed."""
        done = self.last_completed(routine_id)
        if done is None:
            return _parse(created)
        return _parse(done["started"]) + timedelta(seconds=cadence_s)

    def due(self, routine_id: str, now: datetime | None = None) -> bool:
        rows = self._store.query("SELECT * FROM routines WHERE id = ?", (routine_id,))
        if not rows or rows[0]["state"] != "on":
            return False
        at = self.due_at(routine_id, int(rows[0]["cadence_s"]), rows[0]["created"])
        return at <= (now or datetime.now(UTC))

    # --- writing ------------------------------------------------------------------------------------

    def change(self, routine_id: str, body: RoutineBody) -> Routine:
        found = self.get(routine_id)
        if not isinstance(body, dict):
            raise ApiError("bad_request", "send a JSON object")
        unknown = set(body) - {"state", "cadence_s", "url"}
        if unknown:
            raise ApiError("bad_request", f"a routine has no field {sorted(unknown)[0]}")
        sets: dict[str, Any] = {}
        if "state" in body:
            if body["state"] not in ("on", "paused"):
                raise ApiError("bad_request", "state is on or paused")
            sets["state"] = body["state"]
        if "cadence_s" in body:
            cadence = body["cadence_s"]
            least = min_cadence(found["kind"])
            if isinstance(cadence, bool) or not isinstance(cadence, int) or cadence < least:
                raise ApiError(
                    "bad_request",
                    f"a routine runs at most every {least // 60} minutes (cadence_s >= {least})",
                )
            sets["cadence_s"] = cadence
        if "url" in body:
            url = body["url"].strip() if isinstance(body["url"], str) else ""
            parts = urlsplit(url)
            if parts.scheme.lower() not in ("http", "https") or not parts.netloc or len(url) > URL_MAX:
                raise ApiError(
                    "bad_request", "a routine's page is a web address starting with http:// or https://"
                )
            sets["url"] = url
        if sets:
            assigns = ", ".join(f"{k} = ?" for k in sets)
            self._store.run(f"UPDATE routines SET {assigns} WHERE id = ?", (*sets.values(), routine_id))
        after = self.get(routine_id)
        if sets:
            self.publish(after)
        return after

    def write_run(self, run: RoutineRun) -> bool:
        """Appends a finished run and prunes the routine's oldest past RUNS_KEPT. False when the routine
        is gone (its space was erased while it ran): nothing is written."""
        with self._store.tx() as db:
            found = db.execute("SELECT space_id FROM routines WHERE id = ?", (run["routine_id"],)).fetchone()
            if found is None:
                return False
            db.execute(
                "INSERT INTO routine_runs(id, space_id, routine_id, started, ended, outcome, body) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    run["id"],
                    found["space_id"],
                    run["routine_id"],
                    run["started"],
                    run.get("ended"),
                    run["outcome"],
                    json.dumps(run, ensure_ascii=False),
                ),
            )
            db.execute(
                "DELETE FROM routine_runs WHERE routine_id = ? AND id NOT IN (SELECT id FROM routine_runs "
                "WHERE routine_id = ? ORDER BY started DESC, rowid DESC LIMIT ?)",
                (run["routine_id"], run["routine_id"], RUNS_KEPT),
            )
        return True

    def publish(self, routine: Routine) -> None:
        if self._events is not None:
            self._events.publish({"type": "routine", "space_id": routine["space_id"], "routine": routine})

    def _insert(self, space_id: str, routine_id: str, kind: RoutineKind, cadence_s: int) -> None:
        from athena.routines.kinds import NAME

        self._store.run(
            "INSERT INTO routines(id, space_id, kind, name, cadence_s, ceiling_usd, state, url, created) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                routine_id,
                space_id,
                kind,
                NAME[kind],
                cadence_s,
                ROUTINE_CEILING_CENTS / 100,
                "on",
                None,
                now_iso(),
            ),
        )

    def _retire(self, routine_id: str) -> None:
        """A default the project no longer needs: removed when it never ran, else paused (its runs stay)."""
        ran = self._store.query("SELECT 1 FROM routine_runs WHERE routine_id = ? LIMIT 1", (routine_id,))
        if ran:
            self._store.run("UPDATE routines SET state = 'paused' WHERE id = ?", (routine_id,))
        else:
            self._store.run("DELETE FROM routines WHERE id = ?", (routine_id,))

    def ensure_defaults(self, space_id: str) -> list[Routine]:
        """The project's default routines for the kinds it keeps (watch: creator+track; inbox: thread;
        stats: stat; outreach: agreement+thread) and one `twin:<id>` routine per live twin; idempotent."""
        from athena.routines.kinds import CADENCE_S

        rows = self._store.query("SELECT kinds FROM spaces WHERE id = ?", (space_id,))
        if not rows or space_id == "":
            raise ApiError("unknown_ref", "no such project")
        kept = set(json.loads(rows[0]["kinds"] or "[]"))
        have = {
            r["kind"]: r for r in self._store.query("SELECT * FROM routines WHERE space_id = ?", (space_id,))
        }
        for kind, needs in NEEDS.items():
            wanted = all(k in kept for k in needs)
            row = have.get(kind)
            if wanted and row is None:
                self._insert(space_id, mint(ROUTINE_PREFIX), kind, CADENCE_S[kind])
            elif not wanted and row is not None and row["state"] == "on":
                self._retire(row["id"])
        # One routine per live twin of the project; a twin that is gone takes its routine with it. A
        # twin that is paused keeps its routine, which skips `no_twin` until it is live again.
        twins = {
            r["id"]: r["state"]
            for r in self._store.query("SELECT id, state FROM twins WHERE space_id = ?", (space_id,))
        }
        set_cadence = twin_cadence()
        for r in self._store.query(
            "SELECT id, cadence_s FROM routines WHERE space_id = ? AND kind = 'twin'", (space_id,)
        ):
            twin_id = r["id"].removeprefix(TWIN_PREFIX)
            if twin_id not in twins:
                with self._store.tx() as db:
                    db.execute("DELETE FROM routine_runs WHERE routine_id = ?", (r["id"],))
                    db.execute("DELETE FROM routines WHERE id = ?", (r["id"],))
            elif set_cadence is not None and r["cadence_s"] != set_cadence:
                self._store.run("UPDATE routines SET cadence_s = ? WHERE id = ?", (set_cadence, r["id"]))
        for twin_id, state in twins.items():
            routine_id = TWIN_PREFIX + twin_id
            if state == "live" and not self._store.query(
                "SELECT 1 FROM routines WHERE id = ?", (routine_id,)
            ):
                self._insert(space_id, routine_id, "twin", set_cadence or CADENCE_S["twin"])
        return self.of_space(space_id)

    def spaces_with_work(self) -> list[str]:
        """Every project that keeps a kind, has a twin, or already has routines: what a tick ensures."""
        rows = self._store.query(
            "SELECT id FROM spaces WHERE id != '' AND ((kinds IS NOT NULL AND kinds != '[]') "
            "OR id IN (SELECT space_id FROM twins) OR id IN (SELECT space_id FROM routines)) "
            "ORDER BY created, rowid"
        )
        return [r["id"] for r in rows]


def new_run(routine_id: str) -> RoutineRun:
    return {
        "id": mint(RUN_PREFIX),
        "routine_id": routine_id,
        "started": now_iso(),
        "outcome": "ran",
        "found": 0,
        "kept": 0,
        "cards": 0,
    }
