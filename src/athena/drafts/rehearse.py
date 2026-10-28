"""The test run: the bench runner plays the written chore's phases on a throwaway daemon, streaming
progress and cards, scored against the person's key. Ledger rows carry surface `rehearsal`."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from athena.app import Daemon
from athena.engine import Engine


def rehearse(daemon: Daemon, engine: Engine, draft_id: str) -> Iterator[dict[str, Any]]:
    """RehearsalEvents: `phase`, `card`, then `scored` (or `error`). Never retried automatically."""
    raise NotImplementedError
