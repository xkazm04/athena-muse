"""Composing, pins and the report's view.

The view reads the latest stored spec (or the default), passes it through the validation door and
computes every block's value from records now. A composition is one engine call (surface `report`)
whose answer passes the same door before it is stored as a new version; a failure keeps the last good
spec. The owner's pins are constraints: the composer is told about them and a pinned block it left out
is carried over by id, verbatim."""

from __future__ import annotations

import json
import logging
import threading
import weakref
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from athena.clock import now_iso
from athena.contracts import BLOCKS_MAX, RECOMPOSE_MIN_S, Block, PinsBody, RecordKind, ReportSpec, ReportView
from athena.drafts.author import call_model, first_object
from athena.engine import EngineError
from athena.errors import ApiError
from athena.report import compute
from athena.report.validate import check
from athena.report.vocab import composer_docs
from athena.store import Store

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.engine import Engine

log = logging.getLogger(__name__)

NO_RECORDS = "this project keeps no records"

#: Runs a shape-triggered composition off the caller's thread. Tests swap it to run inline.
SPAWN: Callable[[Callable[[], None]], None] = lambda fn: threading.Thread(  # noqa: E731
    target=fn, name="report-compose", daemon=True
).start()

#: Per daemon store: the projects with a composition in flight, and when a shape trigger last tried one
#: (a failure included, so a flaky engine is not asked again on every write).
_composing: weakref.WeakKeyDictionary[Store, set[str]] = weakref.WeakKeyDictionary()
_attempted: weakref.WeakKeyDictionary[Store, dict[str, str]] = weakref.WeakKeyDictionary()
_lock = threading.Lock()


def kinds_of(daemon: Daemon, space_id: str) -> list[RecordKind]:
    daemon.spaces.get(space_id)  # unknown_ref for a project that is not there
    kinds = daemon.records.kinds(space_id)
    if not kinds:
        raise ApiError("bad_request", NO_RECORDS)
    return kinds


def _stored(daemon: Daemon, space_id: str) -> tuple[Any, str] | None:
    """The latest composed spec (raw, as stored) and when it was composed; None when never."""
    rows = daemon.store.query(
        "SELECT spec, composed_at FROM reports WHERE space_id = ? ORDER BY version DESC LIMIT 1", (space_id,)
    )
    if not rows:
        return None
    try:
        raw = json.loads(rows[0]["spec"])
    except ValueError:
        raw = None
    return raw, rows[0]["composed_at"]


def _pins(daemon: Daemon, space_id: str) -> list[str]:
    rows = daemon.store.query(
        "SELECT block_id FROM report_pins WHERE space_id = ? ORDER BY pinned_at, block_id", (space_id,)
    )
    return [r["block_id"] for r in rows]


def _current(daemon: Daemon, space_id: str, kinds: list[RecordKind]) -> tuple[ReportSpec, bool, list[str]]:
    """(the spec on the page now, whether it is the default, the render-time drop reasons)."""
    name = daemon.spaces.get(space_id)["name"]
    stored = _stored(daemon, space_id)
    checked = check(stored[0] if stored else None, kinds, name)
    if stored is None:
        return checked.spec, True, []
    return checked.spec, checked.default, checked.reasons


def _view(
    daemon: Daemon, space_id: str, kinds: list[RecordKind], reasons: list[str] | None = None
) -> ReportView:
    spec, default, render_reasons = _current(daemon, space_id, kinds)
    reasons = render_reasons if reasons is None else reasons
    cards = [c for c in daemon.gate.list("waiting") if c["space_id"] == space_id]
    pins = set(_pins(daemon, space_id))
    out: ReportView = {
        "spec": spec,
        "default": default,
        "rendered_at": now_iso(),
        "dropped": len(reasons),
        "reasons": reasons,
        "values": {b["id"]: compute.value(daemon.records, space_id, b, cards) for b in spec["blocks"]},
        "pinned": [b["id"] for b in spec["blocks"] if b["id"] in pins],  # in the report's order
    }
    stored = _stored(daemon, space_id)
    if stored is not None:
        out["composed_at"] = stored[1]
    return out


def view(daemon: Daemon, space_id: str) -> ReportView:
    """The stored spec (or the default), validated, with every block's value computed now."""
    return _view(daemon, space_id, kinds_of(daemon, space_id))


def _prompt(daemon: Daemon, space_id: str, kinds: list[RecordKind]) -> list[dict[str, Any]]:
    space = daemon.spaces.get(space_id)
    spec, default, _ = _current(daemon, space_id, kinds)
    pinned = set(_pins(daemon, space_id))
    marked = dict(spec)
    marked["blocks"] = [{**b, "pinned": True} if b["id"] in pinned else dict(b) for b in spec["blocks"]]
    counts = "\n".join(f"- {k}: {daemon.records.count(space_id, k)}" for k in kinds)
    pins = ", ".join(f"`{p}`" for p in sorted(pinned)) or "none"
    user = "\n".join(
        [
            f"Project: {space['name']}",
            f"Brief: {space['brief'] or '(none)'}",
            "",
            "How many records of each kind it keeps today. This is context for choosing blocks only; "
            "never write these numbers anywhere in your answer.",
            counts,
            "",
            f"Pinned by the owner (keep each, unchanged, with its id): {pins}.",
            "",
            "The default layout, never arranged yet:" if default else "The current report:",
            json.dumps(marked, indent=2, ensure_ascii=False),
            "",
            "Arrange the report for where this project stands now. Answer with the JSON object only.",
        ]
    )
    return [{"role": "system", "content": composer_docs(list(kinds))}, {"role": "user", "content": user}]


def _signature(block: Block) -> str:
    return json.dumps([block["kind"], block.get("binding"), block["config"]], sort_keys=True)


def _carry_pins(fresh: ReportSpec, current: ReportSpec, pinned: list[str]) -> ReportSpec:
    """Pinned blocks verbatim by id, in their old place; a fresh block that only repeats a pinned one
    goes, so respecting a pin never shows the same thing twice."""
    old = {b["id"]: (i, b) for i, b in enumerate(current["blocks"]) if b["id"] in pinned}
    if not old:
        return fresh
    kept_sigs = {_signature(b) for _, b in old.values()}
    blocks = [b for b in fresh["blocks"] if b["id"] not in old and _signature(b) not in kept_sigs]
    for i, b in sorted(old.values(), key=lambda p: p[0]):
        blocks.insert(min(i, len(blocks)), b)
    # The cap still holds; unpinned blocks give way from the tail.
    while len(blocks) > BLOCKS_MAX:
        last = max(i for i, b in enumerate(blocks) if b["id"] not in old)
        blocks.pop(last)
    out = fresh.copy()
    out["blocks"] = blocks
    return out


def compose(daemon: Daemon, engine: Engine, space_id: str) -> ReportView:
    """One engine call; the answer passes the validation door before it is stored (a failure keeps the
    last good spec); pinned blocks are kept by id; one ledger row, surface `report`."""
    kinds = kinds_of(daemon, space_id)
    name = daemon.spaces.get(space_id)["name"]
    messages = _prompt(daemon, space_id, kinds)
    try:
        answer = call_model(daemon, engine, space_id, messages, "report")
    except EngineError as e:
        raise ApiError("engine_unavailable", f"She could not arrange the report: {e.reason}") from e
    raw = first_object(answer, "blocks")
    checked = check(raw if isinstance(raw, dict) else None, kinds, name)
    if checked.rejected is not None:
        raise ApiError(
            "engine_unavailable",
            f"She did not answer with a report ({checked.rejected}); the last one stands",
        )
    if checked.default:
        raise ApiError(
            "engine_unavailable",
            f"None of the blocks she chose could be shown ({len(checked.reasons)} dropped);"
            " the last report stands",
        )
    with daemon.store.tx() as db:
        # Read-modify-write in one transaction: pins set while she was thinking still hold.
        current, _, _ = _current(daemon, space_id, kinds)
        spec = _carry_pins(checked.spec, current, _pins(daemon, space_id))
        version = db.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM reports WHERE space_id = ?", (space_id,)
        ).fetchone()["v"]
        db.execute(
            "INSERT INTO reports(space_id, version, spec, composed_at, by) VALUES (?,?,?,?,?)",
            (space_id, version, json.dumps(spec, ensure_ascii=False), now_iso(), "athena"),
        )
    daemon.events.publish({"type": "report", "space_id": space_id})
    return _view(daemon, space_id, kinds, checked.reasons)


def set_pins(daemon: Daemon, space_id: str, body: PinsBody) -> ReportView:
    """Replaces the project's pins with `body.pinned`; each must be a block on the report now."""
    kinds = kinds_of(daemon, space_id)
    pinned = body.get("pinned") if isinstance(body, dict) else None
    if not isinstance(pinned, list) or not all(isinstance(p, str) for p in pinned):
        raise ApiError("bad_request", "send pinned as a list of block ids")
    spec, _, _ = _current(daemon, space_id, kinds)
    ids = {b["id"] for b in spec["blocks"]}
    missing = [p for p in pinned if p not in ids]
    if missing:
        raise ApiError("bad_request", f"there is no block “{missing[0]}” on this report")
    at = now_iso()
    with daemon.store.tx() as db:
        db.execute("DELETE FROM report_pins WHERE space_id = ?", (space_id,))
        db.executemany(
            "INSERT INTO report_pins(space_id, block_id, pinned_at) VALUES (?,?,?)",
            [(space_id, p, at) for p in dict.fromkeys(pinned)],
        )
    daemon.events.publish({"type": "report", "space_id": space_id})
    return _view(daemon, space_id, kinds)


def _age_s(iso: str) -> float:
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    return (datetime.now(UTC) - then).total_seconds()


def on_records_changed(
    daemon: Daemon, engine: Callable[[], Engine], space_id: str, kind: str, before: int, after: int
) -> bool:
    """The shape trigger: a kind going 0 -> >=1 or >=1 -> 0 recomposes, at most once per RECOMPOSE_MIN_S;
    a verdict alone never does. Runs off the caller's thread and never raises into it. `engine` is built
    only when a composition starts. Answers whether it started one."""
    try:
        if not ((before == 0 and after >= 1) or (before >= 1 and after == 0)):
            return False
        if not daemon.records.kinds(space_id):
            return False
        stored = _stored(daemon, space_id)
        if stored is not None and _age_s(stored[1]) < RECOMPOSE_MIN_S:
            return False
        with _lock:
            busy = _composing.setdefault(daemon.store, set())
            tried = _attempted.setdefault(daemon.store, {})
            last = tried.get(space_id)
            if space_id in busy or (last is not None and _age_s(last) < RECOMPOSE_MIN_S):
                return False
            busy.add(space_id)
            tried[space_id] = now_iso()
    except Exception:  # the trigger hangs off a records write: it never fails that write
        log.exception("report shape trigger for %s", space_id)
        return False

    def run() -> None:
        try:
            compose(daemon, engine(), space_id)
        except Exception as e:  # off-thread: the last good report stands
            log.warning("report recompose for %s (%s changed shape): %s", space_id, kind, e)
        finally:
            with _lock:
                busy.discard(space_id)

    SPAWN(run)
    return True
