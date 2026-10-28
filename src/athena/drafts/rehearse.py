"""The test run: the bench runner plays the written chore's phases on a throwaway daemon, streaming
progress and cards, scored against the person's key. Ledger rows carry surface `rehearsal`.

The run happens on a worker thread; the stream reads its events from a queue, so each line goes out
as it happens. The draft's Project is held busy for the whole run, even if the person stops
listening: the run then still finishes, and its score and cost are kept. A run that ends early (an
engine error, the wall clock) is not a verdict: it streams `error` and the step stays `rehearse`.
Nothing is retried automatically.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Any, cast

from athena.app import Daemon
from athena.bench import runner
from athena.chores.spec import Chore
from athena.contracts import Draft
from athena.drafts.author import load_written, not_busy
from athena.engine import Engine
from athena.errors import ApiError

log = logging.getLogger(__name__)

_END = object()


def rehearse(daemon: Daemon, engine: Engine, draft_id: str) -> Iterator[dict[str, Any]]:
    """RehearsalEvents: `phase`, `card`, then `scored` (or `error`). Never retried automatically.
    Validates and starts the run before returning."""
    draft = daemon.drafts.get(draft_id)
    if draft["step"] != "rehearse" or "key" not in draft:
        raise ApiError("bad_request", "the test run comes after your marks and before your verdict")
    chore = load_written(daemon, draft)
    not_busy(daemon, draft)
    events: queue.Queue[object] = queue.Queue()
    slot = daemon.busy.turn(draft["space_id"])
    slot.__enter__()  # held by the worker until the run is over
    try:
        worker = threading.Thread(
            target=_run, args=(daemon, engine, draft_id, chore, events, slot), name=f"rehearse-{draft_id}"
        )
        worker.daemon = True
        worker.start()
    except BaseException:
        slot.__exit__(None, None, None)
        raise
    return _drain(events)


def _drain(events: queue.Queue[object]) -> Iterator[dict[str, Any]]:
    while True:
        item = events.get()
        if item is _END:
            return
        yield cast("dict[str, Any]", item)


def _run(
    daemon: Daemon,
    engine: Engine,
    draft_id: str,
    chore: Chore,
    events: queue.Queue[object],
    slot: AbstractContextManager[None],
) -> None:
    space_id = daemon.drafts.get(draft_id)["space_id"]
    try:
        run = runner.rehearse(chore, engine, on_event=events.put)
        runner.copy_calls(run.calls, daemon.ledger, space_id)
        if run.ended:
            events.put({"type": "error", "error": "engine_unavailable", "reason": _ended(run.ended)})
            return
        runner.write_bench(chore, run)
        stored = cast("dict[str, Any]", dict(daemon.drafts.get(draft_id)))
        stored.update(bench=run.summary, step="verdict")
        stored.pop("verdict", None)
        daemon.drafts.put(cast("Draft", stored))
        events.put({"type": "scored", "bench": run.summary})
    except Exception as e:  # the run must end its stream whatever happened
        log.exception("test run of %s failed", draft_id)
        events.put({"type": "error", "error": "engine_unavailable", "reason": f"The test run stopped: {e}"})
    finally:
        slot.__exit__(None, None, None)
        events.put(_END)


def _ended(why: str) -> str:
    return "The test run stopped before the end, so it is not scored: " + why.removeprefix(
        "the run ended on "
    )
