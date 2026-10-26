"""One row per model call. Owned by WP1. Stub: final signatures."""

from __future__ import annotations

from athena.contracts import EngineId, LedgerPage, LedgerRow, Surface
from athena.store import Store


class Ledger:
    def __init__(self, store: Store) -> None:
        raise NotImplementedError

    def record(
        self,
        *,
        surface: Surface,
        space_id: str,
        engine: EngineId,
        model: str,
        latency_ms: int,
        ok: bool,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: float | None = None,
        cost_estimated: bool = False,
        error: str | None = None,
    ) -> LedgerRow:
        raise NotImplementedError

    def page(self, limit: int) -> LedgerPage:
        """Newest first; totals over every row, `cost_estimated` true if any priced row is."""
        raise NotImplementedError
