"""Rubrics (ADR 0010): the places a shaping conversation covers, in order, and when it is done.

Coverage comes from the sketch alone, never from what a model claims. The chore's seven slots are one
rubric (`CHORE_RUBRIC`); a twin's places are another, on the same code. The module-level `SLOTS`,
`REQUIRED`, `coverage`, `agreed` and `open_slots` are the chore's, kept for the drafts code that reads
them.
"""

from __future__ import annotations

import typing
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import cast

from athena.contracts import Coverage, CoverageValue, Sketch, SketchKind, Slot

REQUIRED_VALUES = (0, 0.5, 1)


@dataclass(frozen=True)
class Rubric:
    """One conversation's places.

    `places` in order (the frame and the screen list them so). `required` per place: 1 = a node the
    person confirmed, 0.5 = at least her proposal (or the person left it open), 0 = it may stay empty.
    `meaning` per place in plain words, for her frame. `kinds` every kind a node may be, in order;
    `allowed` per place the kinds a node there may be, the usual one first.
    """

    places: tuple[str, ...]
    required: Mapping[str, float]
    meaning: Mapping[str, str]
    kinds: tuple[str, ...]
    allowed: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        names = set(self.places)
        if not self.places or len(names) != len(self.places):
            raise ValueError("a rubric names each place once")
        for field, table in (
            ("required", self.required),
            ("meaning", self.meaning),
            ("allowed", self.allowed),
        ):
            if set(table) != names:
                raise ValueError(f"the rubric's {field} must name exactly its places")
        if any(v not in REQUIRED_VALUES for v in self.required.values()):
            raise ValueError("a place requires 0, 0.5 or 1")
        if any(not kinds or not set(kinds) <= set(self.kinds) for kinds in self.allowed.values()):
            raise ValueError("each place allows one or more of the rubric's kinds")

    def usual(self, place: str) -> str:
        """The kind a node in `place` usually is."""
        return self.allowed[place][0]

    def tally(
        self, placed: Iterable[tuple[str, bool]], skipped: frozenset[str] = frozenset()
    ) -> dict[str, CoverageValue]:
        """Per place, from (place, confirmed) pairs: 1 = a confirmed one, 0.5 = only Athena's
        proposals, 0 = empty, or "skipped".

        A confirmed one always wins. A place the person waved through ("That's enough") reads
        "skipped" while it holds nothing confirmed; the shaping turn drops a place from `skipped` once
        something lands in it afterwards, so a skip never hides later work.
        """
        seen: set[str] = set()
        confirmed: set[str] = set()
        for place, ok in placed:
            seen.add(place)
            if ok:
                confirmed.add(place)
        out: dict[str, CoverageValue] = {}
        for place in self.places:
            if place in confirmed:
                out[place] = 1
            elif place in skipped:
                out[place] = "skipped"
            elif place in seen:
                out[place] = 0.5
            else:
                out[place] = 0
        return out

    def coverage(self, sketch: Sketch, skipped: frozenset[str] = frozenset()) -> dict[str, CoverageValue]:
        """`tally` over the sketch's nodes, by their slot."""
        return self.tally(((n["slot"], n["confirmed"]) for n in sketch["nodes"]), skipped)

    @staticmethod
    def meets(value: object, need: float) -> bool:
        """Whether one place's coverage meets what it requires. "skipped" meets 0.5, never 1."""
        if need == 0:
            return True
        if value == "skipped":
            return need < 1
        return isinstance(value, int | float) and value >= need

    def missing(self, cov: Mapping[str, object]) -> list[str]:
        """The places that stand between the coverage and done, in rubric order."""
        return [p for p in self.places if not self.meets(cov[p], self.required[p])]

    def agreed(self, cov: Mapping[str, object]) -> bool:
        """Every place at what it requires or above."""
        return not self.missing(cov)

    def open_places(self, cov: Mapping[str, object]) -> list[str]:
        """Places with nothing confirmed and not skipped (at 0 or 0.5), in rubric order."""
        return [p for p in self.places if cov[p] in (0, 0.5)]


# --- the chore's rubric (ADR 0007) -----------------------------------------------------------------

SLOTS: tuple[Slot, ...] = ("need", "apps", "inputs", "steps", "hand", "output", "never")
REQUIRED: tuple[Slot, ...] = ("need", "apps", "hand", "output")
_CHORE_KINDS: tuple[str, ...] = typing.get_args(SketchKind)
_USUAL: dict[Slot, str] = {
    "need": "step",
    "apps": "app",
    "inputs": "source",
    "steps": "step",
    "hand": "gate",
    "output": "output",
    "never": "never",
}

CHORE_RUBRIC = Rubric(
    places=SLOTS,
    # REQUIRED slots at 1; the rest need her proposal at least, or the person's "leave it open".
    required={s: 1 if s in REQUIRED else 0.5 for s in SLOTS},
    meaning={
        "need": "the job, in the person's own words",
        "apps": "where it happens (the websites or apps)",
        "inputs": "what she reads (pages, mail, calls, letters)",
        "steps": "the order she works in",
        "hand": "what waits for the person's signature",
        "output": "what the person gets at the end",
        "never": "what she must never do or touch",
    },
    kinds=_CHORE_KINDS,
    # Any kind may sit in any slot; the usual one leads.
    allowed={s: (k, *(x for x in _CHORE_KINDS if x != k)) for s, k in _USUAL.items()},
)


def coverage(sketch: Sketch, skipped: frozenset[Slot] = frozenset()) -> Coverage:
    """The chore's coverage per slot (see `Rubric.tally`)."""
    return cast("Coverage", CHORE_RUBRIC.coverage(sketch, frozenset(skipped)))


def agreed(cov: Coverage) -> bool:
    """REQUIRED slots at 1; the rest at 0.5, 1 or "skipped"."""
    return CHORE_RUBRIC.agreed(cov)


def open_slots(cov: Coverage) -> list[Slot]:
    """Slots with no confirmed node and not skipped (at 0 or 0.5), in rubric order."""
    return cast("list[Slot]", CHORE_RUBRIC.open_places(cov))
