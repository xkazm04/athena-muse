import { useEffect } from "react";
import type { ChoreSummary } from "../../lib/contract";
import type { Load } from "../store";
import { useMain } from "../store";
import { ENGINE_WORD, SENSE_WORD, STATUS, VERDICT, arrange } from "./words";

/** How many quiet placeholders stand in for tiles on the first read. */
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

/** Pure: the preview renders it with fixtures. */
export function Catalogue({ chores, load, problem = "", onRetry, onOpen }: CatalogueProps) {
  const { featured, others } = arrange(chores);
  const reading = load === "idle" || load === "reading";

  return (
    <div className="m-chores">
      <div className="m-field__head">
        <h1 className="m-title">Chores</h1>
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
      {reading && (
        <div className="m-chores__band" role="status" aria-label="Reading the chores">
          {Array.from({ length: GHOSTS }, (_, i) => (
            <div key={i} className="m-chores__tile m-chores__ghost" aria-hidden="true" />
          ))}
        </div>
      )}
      {load === "ready" && chores.length === 0 && <p className="m-lead">No chores yet.</p>}
      {load === "ready" && featured.length > 0 && (
        <section aria-labelledby="chores-featured" className="m-section">
          <h2 id="chores-featured" className="m-eyebrow">
            Featured
          </h2>
          <ul className="m-chores__band">
            {featured.map((c) => (
              <li key={c.id}>
                <ChoreTile chore={c} onOpen={onOpen} />
              </li>
            ))}
          </ul>
        </section>
      )}
      {load === "ready" && others.length > 0 && (
        <ul className="m-chores__list" aria-label="Every other chore">
          {others.map((c) => (
            <li key={c.id}>
              <button type="button" className="m-chores__row" onClick={() => onOpen(c.id)}>
                <span className="m-chores__name">{c.short_title}</span>
                <span className="m-muted m-chores__promise" title={c.promise}>
                  {c.promise}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ChoreTile({ chore, onOpen }: { chore: ChoreSummary; onOpen: (id: string) => void }) {
  const status = STATUS[chore.featured];
  const bench = chore.bench;
  return (
    <button type="button" className="m-chores__tile" data-status={chore.featured} onClick={() => onOpen(chore.id)}>
      <span className="m-chores__name">{chore.short_title}</span>
      <span className="m-muted m-chores__promise" title={chore.promise}>
        {chore.promise}
      </span>
      <span className="m-chores__senses">
        {chore.senses.map((s) => (
          <span key={s} className="badge m-chores__sense">
            {SENSE_WORD[s]}
          </span>
        ))}
      </span>
      <span className="badge m-chores__status" data-tone={status.tone}>
        <i className="m-chores__dot" aria-hidden="true" />
        {status.word}
      </span>
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
    </button>
  );
}
