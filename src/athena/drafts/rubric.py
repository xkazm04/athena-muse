"""The seven-slot rubric. Coverage comes from the sketch alone, never from what a model claims."""

from __future__ import annotations

from athena.contracts import Coverage, Sketch, Slot

SLOTS: tuple[Slot, ...] = ("need", "apps", "inputs", "steps", "hand", "output", "never")
REQUIRED: tuple[Slot, ...] = ("need", "apps", "hand", "output")


def coverage(sketch: Sketch, skipped: frozenset[Slot] = frozenset()) -> Coverage:
    """Per slot: 1 = a confirmed node, 0.5 = only Athena's proposals, 0 = empty, or "skipped"."""
    raise NotImplementedError


def agreed(cov: Coverage) -> bool:
    """REQUIRED slots at 1; the rest at 0.5, 1 or "skipped"."""
    raise NotImplementedError
