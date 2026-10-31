import { useEffect } from "react";
import * as api from "../../lib/api";
import type { LedgerRow } from "../../lib/contract";
import { CardView, Ledger, type LedgerColumn } from "../../ui";
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

export function AthenaView() {
  const loadCards = useMain((s) => s.loadCards);
  const loadLedger = useMain((s) => s.loadLedger);
  useEffect(() => {
    void loadCards();
    void loadLedger();
  }, [loadCards, loadLedger]);

  return (
    <div className="m-athena">
      <h1 className="m-title">Athena</h1>
      <Cards />
      <CoreLine />
      <Costs />
    </div>
  );
}

function Cards() {
  const waiting = useMain((s) => s.waiting);
  const resolved = useMain((s) => s.resolved);
  const spaces = useMain((s) => s.spaces);
  const loadCards = useMain((s) => s.loadCards);

  return (
    <>
      <section className="plane m-section" aria-labelledby="av-waiting">
        <h2 id="av-waiting" className="m-h2">
          Waiting on you{" "}
          {waiting.length > 0 && (
            <span className="badge" data-tone="human">
              {waiting.length}
            </span>
          )}
        </h2>
        {waiting.length === 0 ? (
          <p className="m-muted">Nothing waits on your signature.</p>
        ) : (
          <div className="m-cards">
            {waiting.map((c) => (
              <CardView
                key={c.id}
                card={c}
                where={whereName(spaces, c.space_id)}
                onDecide={(...answer) => api.decide(c.id, ...answer)}
                onResolved={() => void loadCards()}
              />
            ))}
          </div>
        )}
      </section>
      <section className="plane m-section" aria-labelledby="av-decided">
        <h2 id="av-decided" className="m-h2">
          Decided
        </h2>
        {resolved.length === 0 ? (
          <p className="m-muted">No decisions yet.</p>
        ) : (
          <div className="m-cards">
            {resolved.map((c) => (
              <CardView
                key={c.id}
                card={c}
                where={whereName(spaces, c.space_id)}
                onDecide={(...answer) => api.decide(c.id, ...answer)}
              />
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function CoreLine() {
  const counts = useMain((s) => s.coreCounts);
  return (
    <section className="plane m-section" aria-labelledby="av-core">
      <h2 id="av-core" className="m-h2">
        What she remembers everywhere
      </h2>
      <p>
        {counts ? `${counts.facts} facts and ${counts.episodes} episodes in core.` : "Counting..."}{" "}
        <a className="m-link" href="#projects/core/memory">
          See core memory
        </a>
      </p>
    </section>
  );
}

/** The Costs table's columns: one row per Muse call (Ledger's first caller; the twins page is its second). */
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
  {
    key: "cost",
    head: "est. $",
    className: "m-num",
    cell: (r) => (r.cost_usd === undefined ? "unpriced" : `est. ${money(r.cost_usd)}`),
  },
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

function Costs() {
  const ledger = useMain((s) => s.ledger);
  const problem = useMain((s) => s.ledgerProblem);
  const spaces = useMain((s) => s.spaces);
  const loadLedger = useMain((s) => s.loadLedger);

  const where = (r: LedgerRow) => whereName(spaces, r.space_id) + (r.surface === "probe" ? " (key check)" : "");

  return (
    <section className="plane m-section" aria-labelledby="av-cost">
      <h2 id="av-cost" className="m-h2">
        What it cost
      </h2>
      <p className="m-muted">Every cost here is an estimate, not a bill.</p>
      {problem && (
        <div className="m-problem" role="alert">
          <p>{problem}</p>
          <button type="button" className="btn" onClick={() => void loadLedger()}>
            Try again
          </button>
        </div>
      )}
      {!ledger && !problem && (
        <span className="badge" data-tone="info">
          reading
        </span>
      )}
      {ledger && (
        <>
          <p className="m-totals">
            {ledger.totals.calls} {ledger.totals.calls === 1 ? "call" : "calls"}, est. {money(ledger.totals.cost_usd)}
          </p>
          {ledger.rows.length === 0 ? (
            <p className="m-muted">No Muse calls yet.</p>
          ) : (
            <Ledger
              className="m-table"
              wrapClassName="m-table-wrap"
              columns={COST_COLUMNS(where)}
              rows={ledger.rows}
              rowKey={(r) => r.id}
            />
          )}
        </>
      )}
    </section>
  );
}
