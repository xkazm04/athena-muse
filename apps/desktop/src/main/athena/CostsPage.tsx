// What running her cost, as a spread of the book (ADR 0024): the total on the left, one row per model
// call on the right. Every figure is the ledger's estimate, never a bill.

import type { LedgerRow } from "../../lib/contract";
import { Ledger, type LedgerColumn } from "../../ui";
import { useMain, whereName } from "../store";

/** "$0.0123" under a dollar (4 decimals), "$1.23" above. Callers add "est.". */
export function money(usd: number): string {
  return usd < 1 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
}

const latency = (ms: number) => (ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);
const time = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
};
const tokens = (n?: number) => (n === undefined ? "-" : n.toLocaleString());

/** The costs table's columns: one row per model call. */
export const COST_COLUMNS = (where: (r: LedgerRow) => string): LedgerColumn<LedgerRow>[] => [
  { key: "time", head: "Time", cell: (r) => time(r.ts) },
  { key: "where", head: "Where", cell: where },
  {
    key: "model",
    head: "Model",
    cellClassName: "m-mono",
    cell: (r) => (
      <>
        {r.model}
        {r.engine === "scripted" && " (simulated)"}
      </>
    ),
  },
  {
    key: "tokens",
    head: "Tokens in / out",
    className: "m-num",
    cell: (r) => (
      <>
        {tokens(r.input_tokens)} / {tokens(r.output_tokens)}
      </>
    ),
  },
  { key: "cost", head: "est. $", className: "m-num", cell: (r) => (r.cost_usd === undefined ? "unpriced" : `est. ${money(r.cost_usd)}`) },
  { key: "latency", head: "Latency", className: "m-num", cell: (r) => latency(r.latency_ms) },
  {
    key: "result",
    head: "Result",
    cell: (r) =>
      r.ok ? (
        <span className="badge" data-tone="success">
          ok
        </span>
      ) : (
        <span className="badge" data-tone="error" title={r.error}>
          {r.error ?? "failed"}
        </span>
      ),
  },
];

export function CostsLeft() {
  const ledger = useMain((s) => s.ledger);
  return (
    <div>
      <p className="sp-kicker">
        <span className="eyebrow">What it cost</span>
      </p>
      <h2 className="sp-ask">{ledger ? `est. ${money(ledger.totals.cost_usd)}` : "Reading..."}</h2>
      {ledger && (
        <p className="sp-when m-totals">
          {ledger.totals.calls} {ledger.totals.calls === 1 ? "call" : "calls"}, est. {money(ledger.totals.cost_usd)}
        </p>
      )}
      <p className="sp-foot">Every cost here is an estimate, not a bill: list prices times the words she read and wrote. A call with no figure was not priced, which is not free.</p>
    </div>
  );
}

export function CostsRight() {
  const ledger = useMain((s) => s.ledger);
  const problem = useMain((s) => s.ledgerProblem);
  const spaces = useMain((s) => s.spaces);
  const loadLedger = useMain((s) => s.loadLedger);
  const where = (r: LedgerRow) => whereName(spaces, r.space_id) + (r.surface === "probe" ? " (key check)" : "");
  return (
    <div>
      <p className="sp-her">
        <span className="eyebrow">Every call</span>
      </p>
      {problem && (
        <div className="sp-stopped" role="alert">
          <p>{problem}</p>
          <button type="button" className="btn btn-sm" onClick={() => void loadLedger()}>
            Try again
          </button>
        </div>
      )}
      {ledger && ledger.rows.length === 0 && <p className="sp-note">No model calls yet.</p>}
      {ledger && ledger.rows.length > 0 && <Ledger className="m-grid m-grid--auto" wrapClassName="m-ledger" columns={COST_COLUMNS(where)} rows={ledger.rows} rowKey={(r) => r.id} />}
    </div>
  );
}
