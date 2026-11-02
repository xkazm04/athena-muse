"""A draft's long steps as background jobs (ADR 0020): writing the chore, previewing its cards and the
test run each run on a daemon thread, never inside an HTTP request.

One `Jobs` per daemon keeps each draft's last job in memory: its events, so any window can follow it
from any index (`follow`), and a Stop (`stop`) that kills the model process. The job holds the
Project's turn slot for its whole life, as the steps always did; its state is kept on `Draft.job` at
start and at the end, published as a `draft_job` app event both times, and its end is told in one line
of the Project's conversation. Writing runs with no wall-clock limit; the preview and the test run keep
the default one. A job found `running` when the daemon starts was cut off by the app closing:
`recover` marks it `stopped`.

The work reports in events. A step's terminal event (written, author_failed, previewed, scored, error)
is held until the work has returned and the slot is free, so a window that hears it can start the next
step at once. An engine that cannot be killed mid-call (the Muse API over HTTP) ends its call after a
Stop: the job is told `stopped` after STOP_GRACE_S all the same, and the late answer is not used
(`author.call_model` checks for the Stop after every call).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, cast

from athena.clock import now_iso
from athena.contracts import AppEvent, Draft, DraftJob, DraftJobKind, DraftJobState
from athena.engine import cli
from athena.errors import ApiError

if TYPE_CHECKING:
    from athena.app import Daemon

log = logging.getLogger(__name__)

#: Plain words for a job's end; each is screen copy.
YOU_STOPPED = cli.STOPPED
APP_CLOSED = "The app closed while she was working."
NO_END = "She stopped without saying how it ended."
#: The line her window shows in the draft's Project when a job ends well.
DONE_LINES: dict[DraftJobKind, str] = {
    "write": "Your chore is written. Come back to the stage to check what she would file.",
    "preview": "Her cards are ready for you to mark.",
    "rehearse": "The test run is done; your score is waiting.",
}
_DONE = frozenset({"written", "previewed", "scored"})
_FAILED = frozenset({"author_failed", "error"})
_TERMINAL = _DONE | _FAILED | {"stopped"}
#: How long Stop waits for the work to end before the job is told `stopped` regardless.
STOP_GRACE_S = 5.0
#: How long one follow wait blocks before it looks again (a client that left is noticed then).
FOLLOW_WAIT_S = 1.0

Emit = Callable[[dict[str, Any]], None]
#: The job's work: a step's event generator, or a function handed `emit` (the test run's callback).
Work = Iterator[dict[str, Any]] | Callable[[Emit], None]


class Stopped(Exception):
    """Raised by `emit` once the person pressed Stop: work with no model call in flight ends there."""


class Job:
    def __init__(self, draft_id: str, space_id: str, kind: DraftJobKind) -> None:
        self.draft_id = draft_id
        self.space_id = space_id
        self.kind: DraftJobKind = kind
        self.cancel = threading.Event()
        #: Set once the job's end is kept, told and its terminal event is out to every follower.
        self.ended = threading.Event()
        self._cond = threading.Condition()
        self._events: list[dict[str, Any]] = []
        self._terminal: dict[str, Any] | None = None  # decided, not yet out
        self._record: DraftJob = {"kind": kind, "state": "running", "started": now_iso(), "events": 0}

    def snapshot(self) -> DraftJob:
        with self._cond:
            count = len(self._events) + (1 if self._terminal is not None and not self.ended.is_set() else 0)
            return cast("DraftJob", {**self._record, "events": count})

    def add(self, event: dict[str, Any]) -> None:
        with self._cond:
            if self._terminal is not None or self.ended.is_set():
                return  # a job told `stopped` early: what the work says after that is not heard
            self._events.append(event)
            self._cond.notify_all()

    def end(self, terminal: dict[str, Any], state: DraftJobState, reason: str | None) -> bool:
        """Decides the job's end once (False when it was already decided); `release` sends it out."""
        with self._cond:
            if self._terminal is not None or self.ended.is_set():
                return False
            self._terminal = terminal
            record = cast("dict[str, Any]", self._record)
            record.update(state=state, ended=now_iso())
            if reason:
                record["reason"] = reason
            return True

    def release(self) -> None:
        """The terminal event out to the followers, once the end is kept on the draft."""
        with self._cond:
            if self._terminal is not None:
                self._events.append(self._terminal)
                self._terminal = None
            self.ended.set()
            self._cond.notify_all()

    def wait(self, after: int, timeout: float) -> tuple[list[dict[str, Any]], bool]:
        """The events from `after` on, waiting up to `timeout` for one; and whether the job has ended."""
        with self._cond:
            if len(self._events) <= after and not self.ended.is_set():
                self._cond.wait(timeout)
            return self._events[after:], self.ended.is_set()


class Jobs:
    """Every draft's last job, in memory for the daemon's life."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}

    def get(self, draft_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(draft_id)

    def start(
        self, daemon: Daemon, draft_id: str, kind: DraftJobKind, work: Work, *, timeout_s: float | None
    ) -> Job:
        """Starts `work` (already validated by its step) on a daemon thread; 409 while one runs."""
        space_id = daemon.drafts.get(draft_id)["space_id"]
        with self._lock:
            last = self._jobs.get(draft_id)
            if last is not None and not last.ended.is_set():
                raise ApiError("space_busy", "Athena is still working on this; try again when she is done")
            slot = daemon.busy.turn(space_id)
            slot.__enter__()  # held by the job's thread until the work has returned
            job = Job(draft_id, space_id, kind)
            self._jobs[draft_id] = job
        try:
            _keep(daemon, job)
            _publish(daemon, job)
            limits = cli.CallLimits(timeout_s, job.cancel)
            thread = threading.Thread(
                target=self._run, args=(daemon, job, work, slot, limits), name=f"draft-{kind}-{draft_id}"
            )
            thread.daemon = True
            thread.start()
        except BaseException:
            slot.__exit__(None, None, None)
            job.end({"type": "error", "error": "engine_unavailable", "reason": NO_END}, "failed", NO_END)
            job.release()
            raise
        return job

    def _run(
        self,
        daemon: Daemon,
        job: Job,
        work: Work,
        slot: AbstractContextManager[None],
        limits: cli.CallLimits,
    ) -> None:
        terminal: list[dict[str, Any]] = []

        def emit(event: dict[str, Any]) -> None:
            if job.cancel.is_set():
                raise Stopped
            if event.get("type") in _TERMINAL:
                terminal.append(event)  # held until the slot is free
            else:
                job.add(event)

        try:
            with cli.call_limits(limits):
                if callable(work):
                    work(emit)
                else:
                    for event in work:
                        if event.get("type") in _TERMINAL:
                            terminal.append(event)
                        else:
                            job.add(event)
        except Stopped:
            pass
        except Exception as e:  # the job must end whatever happened
            log.exception("draft job %s on %s failed", job.kind, job.draft_id)
            terminal.append({"type": "error", "error": "engine_unavailable", "reason": f"She stopped: {e}"})
        finally:
            slot.__exit__(None, None, None)
            self._finish(daemon, job, terminal[-1] if terminal else None)

    def _finish(self, daemon: Daemon, job: Job, terminal: dict[str, Any] | None) -> None:
        kind = terminal.get("type") if terminal else None
        if job.cancel.is_set() and kind not in _DONE:
            terminal, state, reason = {"type": "stopped", "reason": YOU_STOPPED}, "stopped", YOU_STOPPED
        elif terminal is None:
            terminal = {"type": "error", "error": "engine_unavailable", "reason": NO_END}
            state, reason = "failed", NO_END
        elif kind in _DONE:
            state, reason = "done", None
        else:
            state, reason = "failed", _reason(terminal)
        _close(daemon, job, terminal, cast("DraftJobState", state), reason)

    def stop(self, daemon: Daemon, draft_id: str) -> Job:
        """Stop: the model process is killed (its whole tree) and the job ends `stopped`. A 409 when
        nothing runs. Blocks up to STOP_GRACE_S for the work to end."""
        job = self.get(draft_id)
        if job is None or job.ended.is_set():
            raise ApiError("bad_request", "She is not working on this draft.", status=409)
        job.cancel.set()
        if not job.ended.wait(STOP_GRACE_S):
            # The call cannot be killed (an HTTP engine): told stopped now; its late answer is dropped.
            _close(daemon, job, {"type": "stopped", "reason": YOU_STOPPED}, "stopped", YOU_STOPPED)
        return job


def follow(job: Job, after: int = 0) -> Iterator[dict[str, Any]]:
    """The follow stream, blocking: the snapshot, then the job's events from `after` to its end."""
    yield {"type": "job", "job": job.snapshot()}
    i = max(0, after)
    while True:
        events, ended = job.wait(i, FOLLOW_WAIT_S)
        yield from events
        i += len(events)
        if ended and not events:
            return


def recover(daemon: Daemon) -> int:
    """At daemon start: a stored job still `running` was cut off by the app closing (no thread
    survives a restart); it becomes `stopped`, a write back at the sketch as on any failed write.
    Answers how many were found."""
    rows = daemon.store.query("SELECT id FROM drafts WHERE job LIKE '%\"running\"%'")
    found = 0
    for row in rows:
        draft = cast("dict[str, Any]", dict(daemon.drafts.get(row["id"])))
        job = draft.get("job")
        if not isinstance(job, dict) or job.get("state") != "running":
            continue
        draft["job"] = {**job, "state": "stopped", "ended": now_iso(), "reason": APP_CLOSED}
        if job.get("kind") == "write" and draft["step"] == "author":
            draft["step"] = "shape"
        daemon.drafts.put(cast("Draft", draft))
        daemon.conversation.append(draft["space_id"], "athena", f"I stopped: {APP_CLOSED}")
        found += 1
    return found


# --- helpers --------------------------------------------------------------------------------------


def _reason(terminal: dict[str, Any]) -> str:
    if terminal.get("type") == "author_failed":
        problems = [str(p) for p in terminal.get("problems") or []]
        return " ".join(problems) or "Her answer could not be used."
    return str(terminal.get("reason") or "Something went wrong.")


def _close(
    daemon: Daemon, job: Job, terminal: dict[str, Any], state: DraftJobState, reason: str | None
) -> None:
    if not job.end(terminal, state, reason):
        return
    try:
        _keep(daemon, job)
        line = DONE_LINES[job.kind] if state == "done" else f"I stopped: {reason or NO_END}"
        daemon.conversation.append(job.space_id, "athena", line)
        _publish(daemon, job)
    except ApiError:  # the draft was abandoned while she worked: nothing left to keep it on
        log.info("draft %s went away before its %s job ended", job.draft_id, job.kind)
    finally:
        job.release()  # a follower that hears the end finds it kept


def _keep(daemon: Daemon, job: Job) -> None:
    """`Draft.job` as it stands, written over the draft as stored now."""
    stored = cast("dict[str, Any]", dict(daemon.drafts.get(job.draft_id)))
    stored["job"] = job.snapshot()
    daemon.drafts.put(cast("Draft", stored))


def _publish(daemon: Daemon, job: Job) -> None:
    event: AppEvent = {
        "type": "draft_job",
        "space_id": job.space_id,
        "draft_id": job.draft_id,
        "job": job.snapshot(),
    }
    daemon.events.publish(event)
