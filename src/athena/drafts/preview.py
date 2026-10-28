"""The preview: one call in which Athena reads her practice apps and lists the cards she would file."""

from __future__ import annotations

from athena.app import Daemon
from athena.contracts import ExpectedCard
from athena.engine import Engine


def preview(daemon: Daemon, engine: Engine, draft_id: str) -> list[ExpectedCard]:
    """Every card names a real act tool of the written chore; one that does not is dropped."""
    raise NotImplementedError
