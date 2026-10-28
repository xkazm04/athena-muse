"""The seven-slot rubric. Coverage comes from the sketch alone, never from what a model claims."""

from __future__ import annotations

from athena.contracts import Coverage, CoverageValue, Sketch, Slot

SLOTS: tuple[Slot, ...] = ("need", "apps", "inputs", "steps", "hand", "output", "never")
REQUIRED: tuple[Slot, ...] = ("need", "apps", "hand", "output")


def coverage(sketch: Sketch, skipped: frozenset[Slot] = frozenset()) -> Coverage:
    """Per slot: 1 = a confirmed node, 0.5 = only Athena's proposals, 0 = empty, or "skipped".

    A confirmed node always wins. A slot the person waved through ("That's enough, write it") reads
    "skipped" while it holds no confirmed node; the shaping turn drops a slot from `skipped` once a
    node lands in it afterwards, so a skip never hides later work.
    """
    out: dict[Slot, CoverageValue] = {}
    for slot in SLOTS:
        nodes = [n for n in sketch["nodes"] if n["slot"] == slot]
        if any(n["confirmed"] for n in nodes):
            out[slot] = 1
        elif slot in skipped:
            out[slot] = "skipped"
        elif nodes:
            out[slot] = 0.5
        else:
            out[slot] = 0
    return {
        "need": out["need"],
        "apps": out["apps"],
        "inputs": out["inputs"],
        "steps": out["steps"],
        "hand": out["hand"],
        "output": out["output"],
        "never": out["never"],
    }


def agreed(cov: Coverage) -> bool:
    """REQUIRED slots at 1; the rest at 0.5, 1 or "skipped"."""
    for slot in SLOTS:
        value = cov[slot]
        if slot in REQUIRED:
            if value != 1:
                return False
        elif value not in (0.5, 1, "skipped"):
            return False
    return True


def open_slots(cov: Coverage) -> list[Slot]:
    """Slots with no confirmed node and not skipped (at 0 or 0.5), in rubric order."""
    return [s for s in SLOTS if cov[s] in (0, 0.5)]
