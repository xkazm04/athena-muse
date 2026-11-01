"""The routines and routine_runs tables. STUB (WP2.0) - WP2.1."""

from __future__ import annotations

from athena.contracts import Routine, RoutineBody, RoutineRun
from athena.store import Store


class Routines:
    def __init__(self, store: Store) -> None:
        self._store = store

    def of_space(self, space_id: str) -> list[Routine]:
        raise NotImplementedError

    def get(self, routine_id: str) -> Routine:
        raise NotImplementedError

    def change(self, routine_id: str, body: RoutineBody) -> Routine:
        raise NotImplementedError

    def runs(self, routine_id: str) -> list[RoutineRun]:
        raise NotImplementedError

    def ensure_defaults(self, space_id: str) -> list[Routine]:
        """The project's default routines for the kinds it keeps (watch: creator+track; inbox: thread;
        stats: stat; outreach: agreement+thread) and one `twin:<id>` routine per live twin; idempotent."""
        raise NotImplementedError
