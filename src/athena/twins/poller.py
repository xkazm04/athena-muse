"""The poller (Twin module): while the daemon runs, it works the Gmail threads that have an open mission
of a live twin, every `POLL_SECONDS_DEFAULT`. Nothing runs while the daemon is closed.

It is started by the app's lifespan (`server.create_app`) unless `ATHENA_TWIN_POLL` is `0`; the tests
set it so. A whole number of seconds there sets the interval instead. Each check runs off the event
loop; one mission that fails is logged (its kind of failure, never a value) and keeps its state, and
the loop goes on. It stops at shutdown without waiting out the interval.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import Callable

from starlette.concurrency import run_in_threadpool

from athena.app import Daemon
from athena.contracts import POLL_SECONDS_DEFAULT
from athena.engine import Engine, EngineError
from athena.errors import ApiError
from athena.twins import missions

log = logging.getLogger(__name__)

ENV = "ATHENA_TWIN_POLL"


def interval() -> float | None:
    """Seconds between checks, or None when polling is off (`ATHENA_TWIN_POLL=0`)."""
    raw = os.environ.get(ENV, "").strip()
    if raw == "0":
        return None
    try:
        seconds = int(raw)
    except ValueError:
        return float(POLL_SECONDS_DEFAULT)
    return float(seconds) if seconds > 0 else float(POLL_SECONDS_DEFAULT)


def check(daemon: Daemon, engine: Callable[[], Engine]) -> int:
    """One pass over every open mission of a live twin: answers how many changed. A mission that fails
    is logged and left as it was; the pass goes on."""
    found = missions.open_ones(daemon)
    if not found:
        return 0
    try:
        built = engine()
    except (EngineError, ApiError) as e:
        log.warning("the twins' check has no engine: %s", type(e).__name__)
        return 0
    changed = 0
    for twin_id, mission_id in found:
        try:
            changed += missions.run(daemon, built, twin_id, mission_id)
        except Exception as e:  # one mission never stops the others
            log.warning("mission %s was not worked this time (%s)", mission_id, type(e).__name__)
    return changed


class Poller:
    def __init__(self, daemon: Daemon, engine: Callable[[], Engine], seconds: float) -> None:
        self._daemon = daemon
        self._engine = engine
        self._seconds = seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.get_running_loop().create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _loop(self) -> None:
        while not self._stop.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self._seconds)
            if self._stop.is_set():
                return
            try:
                await run_in_threadpool(check, self._daemon, self._engine)
            except Exception as e:  # the loop outlives any one check
                log.warning("the twins' check failed (%s)", type(e).__name__)
