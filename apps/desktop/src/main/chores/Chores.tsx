// The Chores depth (ADR 0016), after the variant's chores: a heavy title with the library's totals on
// one line, the way in to a new chore at the right, a tab per area with its count, a chip per job, a
// segmented order, and a table with eyebrow heads and the bench's figures to the right.

import { useEffect, useMemo, useState } from "react";
import type { ChoreSummary } from "../../lib/contract";
import type { Load } from "../store";
import { DescribeDoor } from "../stage/door";
import { useMain } from "../store";
import { AreaGlyph } from "./areas";
import {
  AREAS,
  ENGINE_WORD,
  JOBS,
  ORDER_WORD,
  SENSE_WORD,
  STATUS,
  VERDICT,
  count,
  jobOf,
  ordered,
  usd,
  type Order,
} from "./words";

/** How many quiet placeholder rows stand in for the table on the first read. */
const GHOSTS = 4;

/** The catalogue, read from the store; the daemon is asked once per visit. */
export function Chores() {
  const chores = useMain((s) => s.chores);
  const load = useMain((s) => s.choresLoad);
  const problem = useMain((s) => s.choresProblem);
  const loadChores = useMain((s) => s.loadChores);
  const navigate = useMain((s) => s.navigate);

  useEffect(() => {
    void loadChores();
  }, [loadChores]);

  return (
    <Catalogue
      chores={chores}
      load={load}
      problem={problem}
      onRetry={() => void loadChores()}
      onOpen={(id) => navigate({ view: "chore", id })}
    />
  );
}

interface CatalogueProps {
  chores: ChoreSummary[];
  load: Load;
  problem?: string;
  onRetry?: () => void;
  onOpen: (id: string) => void;
}

/** The totals line beside the title: how many, how many proven, and what the bench found. */
export function totals(chores: ChoreSummary[]): string {
  const proven = chores.filter((c) => c.featured === "proven").length;
  const benched = chores.filter((c) => c.bench);
  const found = benched.reduce((n, c) => n + (c.bench?.value_found_usd ?? 0), 0);
  const parts = [count(chores.length, "chore", "chores"), proven ? `${proven} proven on Meta` : "none proven on Meta yet"];
  if (benched.length) parts.push(`${usd(found)} found in bench runs on invented cases`);
  return parts.join(" · ");
}

/** Pure: the preview renders it with fixtures. */
export function Catalogue({ chores, load, problem = "", onRetry, onOpen }: CatalogueProps) {
  const [area, setArea] = useState<string | null>(null);
  const [job, setJob] = useState<string | null>(null);
  const [order, setOrder] = useState<Order>("fit");
  const reading = load === "idle" || load === "reading";

  const inArea = useMemo(() => (area ? chores.filter((c) => c.category === area) : chores), [chores, area]);
  const shown = useMemo(() => ordered(job ? inArea.filter((c) => c.job === job) : inArea, order), [inArea, job, order]);
  const where = area ? (AREAS.find((a) => a.id === area)?.label ?? area) : "all areas";

  return (
    <div className="m-chores">
      <div className="m-depth-head">
        <h1 className="title-depth">Chores</h1>
        {load === "ready" && chores.length > 0 && <p className="m-depth-head__totals">{totals(chores)}</p>}
        <div className="m-depth-head__act">
          <DescribeDoor primary />
        </div>
      </div>
      {load === "problem" && (
        <div className="plane m-problem" role="alert">
          <p>{problem || "Could not read the chores"}</p>
          {onRetry && (
            <button type="button" className="btn" onClick={onRetry}>
              Try again
            </button>
          )}
        </div>
      )}
      <nav className="m-areas" aria-label="Areas">
        <AreaTab id="all" label="All" title="All areas" n={chores.length} current={area === null} onPick={() => setArea(null)} />
        {AREAS.map((a) => {
          const n = chores.filter((c) => c.category === a.id).length;
          return (
            <AreaTab key={a.id} id={a.id} label={a.short} title={a.label} n={n} current={area === a.id} onPick={() => setArea(a.id)} />
          );
        })}
      </nav>
      <div className="m-filterbar">
        <div className="m-jobs" role="group" aria-label="Job">
          <button type="button" className="m-chip-toggle" aria-pressed={job === null} onClick={() => setJob(null)}>
            All jobs
          </button>
          {JOBS.map((j) => (
            <button
              key={j.id}
              type="button"
              className="m-chip-toggle"
              aria-pressed={job === j.id}
              style={{ ["--tone" as string]: j.tone }}
              onClick={() => setJob(job === j.id ? null : j.id)}
            >
              <i className="m-dot" aria-hidden="true" />
              {j.label}
            </button>
          ))}
        </div>
        <div className="m-segmented" role="group" aria-label="Order">
          {(Object.keys(ORDER_WORD) as Order[]).map((o) => (
            <button key={o} type="button" aria-pressed={order === o} title={ORDER_WORD[o].hint} onClick={() => setOrder(o)}>
              {ORDER_WORD[o].word}
            </button>
          ))}
        </div>
      </div>
      {reading && (
        <div className="m-chores__ghosts" role="status" aria-label="Reading the chores">
          {Array.from({ length: GHOSTS }, (_, i) => (
            <div key={i} className="m-chores__ghost" aria-hidden="true" />
          ))}
        </div>
      )}
      {load === "ready" && chores.length === 0 && <p className="m-lead">No chores yet.</p>}
      {load === "ready" && chores.length > 0 && (
        <>
          <p className="m-shown">
            {count(shown.length, "chore", "chores")} in {where}
          </p>
          <div className="m-ledger">
            <table className="m-grid m-chores__table">
              <caption className="m-sr">Pick a chore to open its page.</caption>
              <thead>
                <tr>
                  <th scope="col">Chore</th>
                  <th scope="col">Job</th>
                  <th scope="col">Status</th>
                  <th scope="col">Bench</th>
                  <th scope="col" className="m-num">
                    Found
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((c) => (
                  <ChoreRow key={c.id} chore={c} onOpen={onOpen} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function AreaTab(props: { id: string; label: string; title: string; n: number; current: boolean; onPick: () => void }) {
  const { id, label, title, n, current, onPick } = props;
  return (
    <button
      type="button"
      className="m-area"
      aria-current={current ? "page" : undefined}
      disabled={n === 0 && !current}
      title={title}
      aria-label={`${title}, ${n}`}
      onClick={onPick}
    >
      <span className="m-area__count">{n}</span>
      <AreaGlyph area={id} />
      <span className="m-area__label">{label}</span>
    </button>
  );
}

/** One chore as a row: its name opens it (the promise is its tooltip), then job, status, bench, money. */
export function ChoreRow({ chore, onOpen }: { chore: ChoreSummary; onOpen: (id: string) => void }) {
  const status = STATUS[chore.featured];
  const bench = chore.bench;
  const job = jobOf(chore.job);
  return (
    <tr onClick={() => onOpen(chore.id)}>
      <td>
        <button type="button" className="m-rowname m-chores__tile" data-status={chore.featured} title={chore.promise} onClick={(e) => (e.stopPropagation(), onOpen(chore.id))}>
          <span className="m-chores__name">{chore.short_title}</span>
        </button>
        {chore.senses.length > 0 && (
          <span className="m-chores__senses">{chore.senses.map((s) => SENSE_WORD[s]).join(" · ")}</span>
        )}
      </td>
      <td>
        {job ? (
          <span className="m-job" style={{ ["--tone" as string]: job.tone }}>
            <i className="m-dot" aria-hidden="true" />
            {job.label}
          </span>
        ) : (
          <span className="m-muted">-</span>
        )}
      </td>
      <td>
        <span className="badge m-chores__status" data-tone={status.tone}>
          <i className="m-chores__dot" aria-hidden="true" />
          {status.word}
        </span>
      </td>
      <td>
        {bench ? (
          <span className="m-chores__bench">
            <span className="badge" data-tone={VERDICT[bench.verdict].tone}>
              {VERDICT[bench.verdict].word}
            </span>
            <span className="m-muted">
              found {bench.found} of {bench.eligible}, {ENGINE_WORD[bench.engine]}
            </span>
          </span>
        ) : (
          <span className="m-muted m-chores__bench">Not rehearsed yet</span>
        )}
      </td>
      <td className="m-num">
        {bench ? (
          <span className="m-figure" title="Found by its latest bench run, on invented cases">
            <span className="m-figure__n">{usd(bench.value_found_usd)}</span>
            <span className="m-figure__per">invented</span>
          </span>
        ) : (
          <span className="m-muted">-</span>
        )}
      </td>
    </tr>
  );
}
