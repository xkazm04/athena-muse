"""Every number on the report, computed from records. STUB (WP1.0) - WP1.2 fills it."""

from __future__ import annotations

from athena.contracts import Block, BlockValue, Card
from athena.records.store import Records


def value(records: Records, space_id: str, block: Block, cards: list[Card]) -> BlockValue:
    raise NotImplementedError
