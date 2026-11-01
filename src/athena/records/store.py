"""The records table and its API. STUB (WP1.0) - WP1.1 fills it."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from athena.contracts import KindsBody, MayRender, RecordBy, RecordItem, RecordKind, TrackVerdictBody
from athena.store import Store


class Records:
    def __init__(self, store: Store) -> None:
        self._store = store
        #: Called after a put changes how many keys a kind has: (space_id, kind, before, after). The
        #: report's shape trigger hangs here (set by athena.report.routes); a verdict never changes a count.
        self.on_change: Callable[[str, RecordKind, int, int], None] | None = None

    def put(self, space_id: str, kind: RecordKind, body: dict[str, Any], by: RecordBy) -> RecordItem:
        """Validate, then append a revision (rev+1 of its key, or 1). An unchanged body appends nothing
        and answers the latest revision."""
        raise NotImplementedError

    def latest(
        self, space_id: str, kind: RecordKind | None = None, key: str | None = None
    ) -> list[RecordItem]:
        """The latest revision of every key (newest first), at most RECORDS_PAGE_MAX."""
        raise NotImplementedError

    def get(self, record_id: str) -> RecordItem:
        raise NotImplementedError

    def history(self, record_id: str) -> list[RecordItem]:
        """Every revision of that record's key, oldest first."""
        raise NotImplementedError

    def count(self, space_id: str, kind: RecordKind) -> int:
        """Keys of that kind (latest revisions), for the report's shape trigger."""
        raise NotImplementedError

    def verdict(self, record_id: str, body: TrackVerdictBody) -> RecordItem:
        """A track's verdict, as a new revision written by the person."""
        raise NotImplementedError

    def kinds(self, space_id: str) -> list[RecordKind]:
        raise NotImplementedError

    def set_kinds(self, space_id: str, body: KindsBody) -> KindsBody:
        raise NotImplementedError

    def erase(self, space_id: str) -> int:
        raise NotImplementedError


def may_render(records: Records, space_id: str, track_key: str) -> MayRender:
    """The rights rule (G13): kept, its creator's agreement agreed with a thread as evidence, a plan
    tier known and not free, and a file present. A function, not prose."""
    raise NotImplementedError
