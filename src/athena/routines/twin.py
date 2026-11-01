"""The `twin` routine (business Phase 2): one pass of the old Twins poller for ONE twin.

A routine `twin:<twin_id>` reads that twin's task inbox page (`twins.inbox.read`, which takes one twin;
the global `inbox.check` is no longer run by the daemon), then works each of its open Gmail missions
once (`missions.run`, which keeps its own per-mission lock and holds `busy.turn` while it drafts). A
mission that fails is logged and keeps its state; the pass goes on. The run's ceiling is checked
before each mission against the ledger rows the missions wrote (a mission calls the model itself, so
one mission may pass it; the next does not start).
"""

from __future__ import annotations

import logging

from athena.errors import ApiError
from athena.routines.context import Partial, RunContext, Skip
from athena.routines.store import TWIN_PREFIX
from athena.twins import inbox, missions
from athena.twins.catalogue import INBOX

log = logging.getLogger(__name__)


def open_of(ctx: RunContext, twin_id: str) -> list[str]:
    """The twin's open missions on Gmail (what the poller worked for it)."""
    return [m for t, m in missions.open_ones(ctx.daemon) if t == twin_id]


def run(ctx: RunContext) -> None:
    daemon = ctx.daemon
    twin_id = ctx.routine["id"].removeprefix(TWIN_PREFIX)
    try:
        row = daemon.twins.row(twin_id)
    except ApiError:
        raise Skip("no_twin", "This project's twin is gone.") from None
    if row["state"] != "live":
        raise Skip("no_twin", "The twin is not live, so its conversations wait.")
    started = 0
    chore = daemon.twins.one("chores", twin_id, INBOX)
    if chore is not None and chore.get("page"):
        try:
            started = inbox.read(daemon, twin_id)
        except Exception as e:  # its inbox never stops its missions
            log.warning("the task inbox of %s was not read this time (%s)", twin_id, type(e).__name__)
    found = open_of(ctx, twin_id)
    ctx.of = len(found)
    if not found:
        ctx.note = _said(started, 0, 0)
        if started == 0 and chore is None:
            raise Skip("nothing_to_do", "The twin has no open conversation to work.")
        return
    try:
        engine = ctx.engine()
    except Skip:
        if started:
            said = _said(started, 0, 0)
            raise Partial(f"{said} Athena has no engine, so no conversation was worked.") from None
        raise
    changed = 0
    for mission_id in found:
        ctx.check_ceiling()
        mark = ctx.ledger_mark()
        try:
            if missions.run(daemon, engine, twin_id, mission_id):
                changed += 1
        except Exception as e:  # one mission never stops the others
            log.warning("mission %s was not worked this time (%s)", mission_id, type(e).__name__)
        finally:
            ctx.charge_since(mark, ("twin",))
        ctx.found += 1
    ctx.note = _said(started, ctx.found, changed)


def _said(started: int, worked: int, changed: int) -> str:
    parts: list[str] = []
    if started:
        parts.append(f"It took {started} new task{'s' if started != 1 else ''} from its inbox.")
    if worked:
        parts.append(f"It worked {worked} conversation{'s' if worked != 1 else ''}; {changed} moved on.")
    return " ".join(parts) or "Nothing new for the twin."
