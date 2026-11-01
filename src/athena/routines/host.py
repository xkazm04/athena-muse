"""The routine host: admission, single flight, catch-up, ceilings, runs. STUB (WP2.0) - WP2.1."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from athena.contracts import RoutineRun

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.engine import Engine


class Host:
    def __init__(self, daemon: Daemon, engine: Callable[[], Engine], tick_s: float = 30.0) -> None:
        self._daemon = daemon
        self._engine = engine
        self._tick_s = tick_s

    def start(self) -> None:
        """Tick on the running event loop. On the first tick a routine whose last completed run is older
        than its cadence runs once (catch-up, never back-fill)."""
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    def run_now(self, routine_id: str) -> RoutineRun:
        """Admit and run one routine now (the person's Run now, or a tick). Admission is the one
        decision: paused, already running, a chat turn live in its space -> a recorded skip."""
        raise NotImplementedError
