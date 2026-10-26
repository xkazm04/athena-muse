"""One row per model call."""

from __future__ import annotations

import sqlite3

from athena.clock import now_iso
from athena.contracts import EngineId, LedgerPage, LedgerRow, Surface
from athena.store import Store


def _row(r: sqlite3.Row) -> LedgerRow:
    out: LedgerRow = {
        "id": r["id"],
        "ts": r["ts"],
        "surface": r["surface"],
        "space_id": r["space_id"],
        "engine": r["engine"],
        "model": r["model"],
        "cost_estimated": bool(r["cost_estimated"]),
        "latency_ms": r["latency_ms"],
        "ok": bool(r["ok"]),
    }
    if r["input_tokens"] is not None:
        out["input_tokens"] = r["input_tokens"]
    if r["output_tokens"] is not None:
        out["output_tokens"] = r["output_tokens"]
    if r["cost_usd"] is not None:
        out["cost_usd"] = float(r["cost_usd"])
    if r["error"] is not None:
        out["error"] = r["error"]
    return out


class Ledger:
    def __init__(self, store: Store) -> None:
        self._store = store

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
        with self._store.tx() as db:
            cur = db.execute(
                "INSERT INTO ledger(ts, surface, space_id, engine, model, input_tokens, output_tokens,"
                " cost_usd, cost_estimated, latency_ms, ok, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    now_iso(),
                    surface,
                    space_id,
                    engine,
                    model,
                    input_tokens,
                    output_tokens,
                    cost_usd,
                    int(cost_estimated),
                    latency_ms,
                    int(ok),
                    error,
                ),
            )
            row = db.execute("SELECT * FROM ledger WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row(row)

    def page(self, limit: int) -> LedgerPage:
        """Newest first; totals over every row, `cost_estimated` true if any priced row is."""
        rows = self._store.query("SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (limit,))
        t = self._store.query(
            "SELECT COUNT(*) AS calls, COALESCE(SUM(cost_usd), 0.0) AS cost,"
            " COALESCE(MAX(CASE WHEN cost_usd IS NOT NULL AND cost_estimated = 1 THEN 1 ELSE 0 END), 0)"
            " AS est"
            " FROM ledger"
        )[0]
        return {
            "rows": [_row(r) for r in rows],
            "totals": {"calls": t["calls"], "cost_usd": float(t["cost"]), "cost_estimated": bool(t["est"])},
        }
