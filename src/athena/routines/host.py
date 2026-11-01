"""The routine host: admission, single flight, catch-up, ceilings, runs (business Phase 2).

It is the daemon's only background host (the Twins poller is folded into it as `twin:<id>` routines).
It ticks every `tick_s` on the event loop and does its work on the thread pool. Each tick first makes
sure every project that keeps records or has a twin has its default routines, then runs each routine
that is on and due: due means a cadence has passed since its last COMPLETED run (ran, partial or
failed), so the first tick after a start runs each overdue routine once and never back-fills the
intervals the daemon was closed for.

`run_now` holds the one admission decision, each refusal recorded as a skipped run by name:
paused -> `paused`; a run of it already going in this process -> `running`; a chat turn open in its
space -> `live_turn` (it stays due, so the next tick runs it once the turn ends). Then the kind runs
over a RunContext; what it raises becomes the outcome: Skip -> skipped (its reason), Partial and
CeilingReached -> partial, anything else -> failed, each with a plain note. A tick records a skip only
when its reason differs from the last run's or a cadence has passed since it, so a routine skipping
`no_browser` every tick writes it once. The person's Run now always records. Every written run is
published as the `routine` app event.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from starlette.concurrency import run_in_threadpool

from athena.clock import now_iso
from athena.contracts import Routine, RoutineRun, SkipReason
from athena.engine import EngineError
from athena.errors import ApiError
from athena.routines.context import CeilingReached, Partial, RunContext, Skip
from athena.routines.store import new_run

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.engine import Engine

log = logging.getLogger(__name__)

TICK_S = 30.0
NOTE_MAX = 280

SKIP_NOTES: dict[SkipReason, str] = {
    "paused": "It is paused.",
    "running": "It was already running.",
    "live_turn": "A conversation with Athena was open in this project; it runs when that ends.",
    "no_engine": "Athena has no engine to work with.",
}


def _note(*parts: str) -> str:
    text = " ".join(p.strip() for p in parts if p and p.strip())
    return text if len(text) <= NOTE_MAX else text[: NOTE_MAX - 1].rstrip() + "…"


def _parse(at: str) -> datetime:
    return datetime.fromisoformat(at.replace("Z", "+00:00"))


class Host:
    def __init__(self, daemon: Daemon, engine: Callable[[], Engine], tick_s: float = TICK_S) -> None:
        self._daemon = daemon
        self._engine = engine
        self._tick_s = tick_s
        self._stop: asyncio.Event | None = None
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Tick on the running event loop. On the first tick a routine whose last completed run is older
        than its cadence runs once (catch-up, never back-fill)."""
        self._stop = asyncio.Event()
        self._task = asyncio.get_running_loop().create_task(self._loop())

    async def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _loop(self) -> None:
        assert self._stop is not None
        while not self._stop.is_set():
            try:
                await run_in_threadpool(self.tick)
            except Exception as e:  # the loop outlives any one tick
                log.warning("a routine tick failed (%s)", type(e).__name__)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self._tick_s)

    # --- a tick ---------------------------------------------------------------------------------------

    def tick(self) -> list[RoutineRun]:
        """One pass: the defaults of every project with work, then every routine that is on and due.
        Answers the runs it wrote."""
        routines = self._daemon.routines
        for space_id in routines.spaces_with_work():
            try:
                routines.ensure_defaults(space_id)
            except Exception as e:  # one project never stops the others
                log.warning("the routines of a project were not set up (%s)", type(e).__name__)
        wrote: list[RoutineRun] = []
        for routine_id in routines.ids():
            try:
                if not routines.due(routine_id):
                    continue
                run, written = self._run(routine_id, quiet=True)
            except ApiError:  # gone between the list and the run
                continue
            if written:
                wrote.append(run)
        return wrote

    def run_now(self, routine_id: str) -> RoutineRun:
        """Admit and run one routine now (the person's Run now, or a tick). Admission is the one
        decision: paused, already running, a chat turn live in its space -> a recorded skip."""
        return self._run(routine_id, quiet=False)[0]

    # --- one run --------------------------------------------------------------------------------------

    def _run(self, routine_id: str, *, quiet: bool) -> tuple[RoutineRun, bool]:
        routines = self._daemon.routines
        routine = routines.get(routine_id)
        run = new_run(routine_id)
        if routine["state"] == "paused":
            return self._skipped(routine, run, "paused", "", quiet)
        if not routines.claim(routine_id):
            return self._skipped(routine, run, "running", "", quiet)
        try:
            if self._daemon.busy.live(routine["space_id"]):
                return self._skipped(routine, run, "live_turn", "", quiet)
            ctx = RunContext(self._daemon, routine["space_id"], routine, engine_of=self._engine)
            self._work(routine, ctx, run)
            return self._finish(routine, run, quiet)
        finally:
            routines.release(routine_id)

    def _work(self, routine: Routine, ctx: RunContext, run: RoutineRun) -> None:
        from athena.routines import kinds, twin

        try:
            if routine["kind"] == "twin":
                twin.run(ctx)
            else:
                kinds.RUN[routine["kind"]](ctx)
            run["outcome"] = "ran"
            note = ctx.note
        except Skip as e:
            run["outcome"] = "skipped"
            run["reason"] = e.reason
            note = _note(ctx.note, e.note or SKIP_NOTES.get(e.reason, ""))
        except (Partial, CeilingReached) as e:
            run["outcome"] = "partial"
            note = _note(ctx.note, str(e))
        except (ApiError, EngineError) as e:
            run["outcome"] = "failed"
            note = _note(ctx.note, e.reason)
        except Exception as e:
            log.warning("routine %s failed (%s)", routine["id"], type(e).__name__)
            run["outcome"] = "failed"
            note = _note(ctx.note, f"It stopped on an unexpected error ({type(e).__name__}).")
        run["ended"] = now_iso()
        run["found"] = ctx.found
        run["kept"] = ctx.kept
        run["cards"] = ctx.cards
        if ctx.of is not None:
            run["of"] = ctx.of
        if ctx.spent_usd is not None:
            run["spent_usd"] = round(ctx.spent_usd, 6)
        if note:
            run["note"] = _note(note)

    def _skipped(
        self, routine: Routine, run: RoutineRun, reason: SkipReason, note: str, quiet: bool
    ) -> tuple[RoutineRun, bool]:
        run["outcome"] = "skipped"
        run["reason"] = reason
        run["ended"] = run["started"]
        run["note"] = note or SKIP_NOTES.get(reason, "")
        if not run["note"]:
            del run["note"]
        return self._finish(routine, run, quiet)

    def _finish(self, routine: Routine, run: RoutineRun, quiet: bool) -> tuple[RoutineRun, bool]:
        """Writes the run and publishes the routine, unless a tick's skip repeats the last one."""
        routines = self._daemon.routines
        if quiet and run["outcome"] == "skipped" and self._repeats(routine, run):
            return run, False
        if not routines.write_run(run):
            return run, False
        with contextlib.suppress(ApiError):
            routines.publish(routines.get(routine["id"]))
        return run, True

    def _repeats(self, routine: Routine, run: RoutineRun) -> bool:
        last = self._daemon.routines.last(routine["id"])
        if last is None or last["outcome"] != "skipped" or last.get("reason") != run.get("reason"):
            return False
        since = datetime.now(UTC) - _parse(last["started"])
        return since < timedelta(seconds=routine["cadence_s"])
