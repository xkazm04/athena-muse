"""The test run: the bench runner plays the written chore's phases on a throwaway daemon, streaming
progress and cards, scored against the person's key. Ledger rows carry surface `rehearsal`.

The run is a draft job (ADR 0020): it happens on the job's thread, which holds the draft's Project
busy for the whole run, and any window follows its events, so a person who stops listening changes
nothing: the run still finishes and its score and cost are kept. A run that ends early (an engine
error, the wall clock, Stop) is not a verdict: it ends `error` (or `stopped`) and the step stays
`rehearse`. Nothing is retried automatically.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import Any, cast

from athena.app import Daemon
from athena.bench import runner
from athena.chores.spec import Chore
from athena.contracts import Draft
from athena.drafts import jobs
from athena.drafts.author import load_written, not_busy
from athena.engine import Engine, cli
from athena.errors import ApiError

log = logging.getLogger(__name__)


def check(daemon: Daemon, draft_id: str) -> Chore:
    """Validates a test run before it starts (the key, the written chore, a free Project); its chore."""
    draft = daemon.drafts.get(draft_id)
    if draft["step"] != "rehearse" or "key" not in draft:
        raise ApiError("bad_request", "the test run comes after your marks and before your verdict")
    chore = load_written(daemon, draft)
    not_busy(daemon, draft)
    return chore


def rehearse(daemon: Daemon, engine: Engine, draft_id: str) -> Iterator[dict[str, Any]]:
    """RehearsalEvents: `phase`, `card`, then `scored` (or `error`, or `stopped`). Never retried
    automatically. Validates and starts the run as a draft job before returning; the iterator follows it."""
    chore = check(daemon, draft_id)
    job = daemon.jobs.start(
        daemon, draft_id, "rehearse", work(daemon, engine, draft_id, chore), timeout_s=cli.CLI_TIMEOUT_S
    )
    follow = jobs.follow(job)
    next(follow)  # the snapshot: a caller here reads only the run's events
    return follow


def work(
    daemon: Daemon, engine: Engine, draft_id: str, chore: Chore
) -> Callable[[Callable[[dict[str, Any]], None]], None]:
    """The run as a job's work: handed the job's `emit`, it runs on the job's thread."""

    def run(emit: Callable[[dict[str, Any]], None]) -> None:
        _run(daemon, engine, draft_id, chore, emit)

    return run


def _run(
    daemon: Daemon, engine: Engine, draft_id: str, chore: Chore, emit: Callable[[dict[str, Any]], None]
) -> None:
    space_id = daemon.drafts.get(draft_id)["space_id"]
    try:
        run = runner.rehearse(chore, engine, on_event=emit)
        runner.copy_calls(run.calls, daemon.ledger, space_id)
        if run.ended:
            emit({"type": "error", "error": "engine_unavailable", "reason": _ended(run.ended)})
            return
        cli.check_stopped()  # an engine that finished its call after a Stop: not a verdict
        runner.write_bench(chore, run)
        stored = cast("dict[str, Any]", dict(daemon.drafts.get(draft_id)))
        stored.update(bench=run.summary, step="verdict")
        stored.pop("verdict", None)
        daemon.drafts.put(cast("Draft", stored))
        emit({"type": "scored", "bench": run.summary})
    except jobs.Stopped:
        raise
    except Exception as e:  # the run must end its stream whatever happened
        log.exception("test run of %s failed", draft_id)
        emit({"type": "error", "error": "engine_unavailable", "reason": f"The test run stopped: {e}"})


def _ended(why: str) -> str:
    return "The test run stopped before the end, so it is not scored: " + why.removeprefix(
        "the run ended on "
    )
