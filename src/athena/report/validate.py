"""The one validation door for a spec. STUB (WP1.0) - WP1.2 fills it."""

from __future__ import annotations

from typing import Any

from athena.contracts import RecordKind, ReportSpec


def validate(raw: Any, kinds: list[RecordKind]) -> tuple[ReportSpec, list[str]]:
    """(what survives, why each dropped block was dropped). Unknown kinds, unbound bindings, kinds the
    project does not keep, spans outside 1..12, more than BLOCKS_MAX, and any digit in a title or the
    callout are dropped; a spec with nothing left is the default spec."""
    raise NotImplementedError
