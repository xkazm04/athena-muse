"""What is left of the Twins poller (business Phase 2 folded it into the routine host).

The daemon's background work on a twin is now its `twin:<twin_id>` routine (`routines/twin.py`): the
host runs it on its cadence (POLL_SECONDS_DEFAULT, or `ATHENA_TWIN_POLL` seconds), never during a chat
turn in its space, with a ceiling. `ATHENA_TWIN_POLL=0` keeps the host from ticking at all (the tests
set it so); `interval` reads it for the app's lifespan. `check` is one global pass over every live twin,
kept for the tests that drive a twin's inbox and missions by hand; the daemon itself never calls it.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

from athena.app import Daemon
from athena.contracts import POLL_SECONDS_DEFAULT
from athena.engine import Engine, EngineError
from athena.errors import ApiError
from athena.twins import inbox, missions

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
    """One pass: the task inboxes, then every open mission of a live twin. Answers how many missions
    started or changed. A mission that fails is logged and left as it was; the pass goes on."""
    started = inbox.check(daemon)
    found = missions.open_ones(daemon)
    if not found:
        return started
    try:
        built = engine()
    except (EngineError, ApiError) as e:
        log.warning("the twins' check has no engine: %s", type(e).__name__)
        return started
    changed = started
    for twin_id, mission_id in found:
        try:
            changed += missions.run(daemon, built, twin_id, mission_id)
        except Exception as e:  # one mission never stops the others
            log.warning("mission %s was not worked this time (%s)", mission_id, type(e).__name__)
    return changed
