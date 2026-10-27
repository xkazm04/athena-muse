"""The bench: rehearse a chore headless against its invented portals and score the cards (ADR 0005).

Stub: WP4 fills the bodies, keeping every name and signature. `python -m athena.bench <id>
[--engine E] [--model M] [--no-write]` runs one chore and, unless told not to, writes
`playbooks/<id>/bench.json` (a `BenchSummary` plus the cards it filed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from athena.chores.spec import Chore
from athena.contracts import BenchSummary, Card
from athena.engine import Engine


@dataclass(frozen=True)
class Score:
    eligible: int
    found: int
    exact: int
    value_total_usd: float
    value_found_usd: float
    false_claims: int
    duplicates: int
    traps_filed: int
    missed: tuple[str, ...] = ()
    ledger: tuple[dict[str, Any], ...] = field(default_factory=tuple)  # one row per card judged


def score(chore: Chore, cards: list[Card]) -> Score:
    raise NotImplementedError


def verdict(chore: Chore, s: Score, minutes: float) -> tuple[str, list[str]]:
    """(`exceeds` | `meets` | `short`, reasons) against the chore's own `expectation`."""
    raise NotImplementedError


def run_bench(chore: Chore, engine: Engine, *, write: bool = True) -> BenchSummary:
    raise NotImplementedError
