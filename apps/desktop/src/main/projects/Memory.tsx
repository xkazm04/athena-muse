import { useCallback, useEffect, useState } from "react";
import * as api from "../../lib/api";
import { CORE, type MemoryKind, type MemoryPage } from "../../lib/contract";
import { reasonOf, useMain, whereName } from "../store";

/** The daemon's largest memory page (MEMORY_LIMIT_MAX in contracts.py; not exported to TS). */
const PAGE = 200;

const FILTERS: { kind: MemoryKind | undefined; label: string }[] = [
  { kind: undefined, label: "All" },
  { kind: "episode", label: "Episodes" },
  { kind: "fact", label: "Facts" },
];

const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
};

export function CoreLevel() {
  const counts = useMain((s) => s.coreCounts);
  const loadCoreCounts = useMain((s) => s.loadCoreCounts);
  const navigate = useMain((s) => s.navigate);
  useEffect(() => {
    void loadCoreCounts();
  }, [loadCoreCounts]);

  return (
    <div className="m-level">
      <button type="button" className="btn btn-quiet m-back" onClick={() => navigate({ view: "projects" })}>
        All projects
      </button>
      <section className="plane m-section">
        <p className="m-eyebrow">Core</p>
        <h1 className="m-title">What Athena knows everywhere</h1>
        <p className="m-lead">
          Core memory is visible in every project. A project&apos;s own memory stays inside that project.
        </p>
        <p>
          {counts ? `${counts.episodes} episodes, ${counts.facts} facts.` : "Counting..."}{" "}
          <a className="m-link" href="#projects/core/memory">
            See core memory
          </a>
        </p>
      </section>
    </div>
  );
}

export function Memory({ id }: { id: string }) {
  const spaces = useMain((s) => s.spaces);
  const navigate = useMain((s) => s.navigate);
  const [kind, setKind] = useState<MemoryKind | undefined>(undefined);
  const [page, setPage] = useState<MemoryPage | null>(null);
  const [problem, setProblem] = useState("");
  const [asking, setAsking] = useState<string | null>(null);
  const [rowProblem, setRowProblem] = useState("");
  const isCore = id === CORE;
  // Counts move when a turn writes memory or a fact goes core; the page follows them live.
  const stamp = useMain((s) => {
    const c = id === CORE ? s.coreCounts : s.spaces.find((x) => x.id === id)?.counts;
    return c ? `${c.episodes}/${c.facts}` : "";
  });

  const load = useCallback(async () => {
    setProblem("");
    try {
      setPage(await api.memory(id, kind, PAGE));
    } catch (e) {
      setProblem(reasonOf(e, "Could not read the memory"));
    }
  }, [id, kind]);

  useEffect(() => {
    void load();
  }, [load, stamp]);

  const makeCore = async (memId: string) => {
    setRowProblem("");
    try {
      await api.makeCore(id, memId);
      setAsking(null);
      await load();
    } catch (e) {
      setRowProblem(reasonOf(e, "Could not make it core"));
    }
  };

  return (
    <div className="m-level">
      <button
        type="button"
        className="btn btn-quiet m-back"
        onClick={() => navigate(isCore ? { view: "core" } : { view: "project", id })}
      >
        Back to {whereName(spaces, id)}
      </button>
      <section className="plane m-section">
        <p className="m-eyebrow">Memory</p>
        <h1 className="m-title">{whereName(spaces, id)}</h1>
        <div className="m-row" role="radiogroup" aria-label="Show">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              type="button"
              role="radio"
              aria-checked={kind === f.kind}
              className={`btn${kind === f.kind ? " m-on" : " btn-quiet"}`}
              onClick={() => setKind(f.kind)}
            >
              {f.label}
            </button>
          ))}
          {page && (
            <span className="m-muted m-push">
              (showing {page.showing} of {page.total})
            </span>
          )}
        </div>
        {problem && (
          <div className="m-problem" role="alert">
            <p>{problem}</p>
            <button type="button" className="btn" onClick={() => void load()}>
              Try again
            </button>
          </div>
        )}
        {!page && !problem && (
          <span className="badge" data-tone="info">
            reading
          </span>
        )}
        {page && page.rows.length === 0 && <p className="m-muted">Nothing remembered here yet.</p>}
        {page && page.rows.length > 0 && (
          <ul className="m-memory">
            {page.rows.map((r) => (
              <li key={r.id} className="m-memory__row">
                <span className="badge" data-tone={r.kind === "fact" ? "info" : undefined}>
                  {r.kind === "fact" ? "fact" : "episode"}
                </span>
                <p className="m-memory__line">{r.line}</p>
                <span className="m-muted m-memory__when">{when(r.created)}</span>
                {!isCore && r.kind === "fact" && asking !== r.id && (
                  <button type="button" className="btn btn-quiet" onClick={() => setAsking(r.id)}>
                    Make core
                  </button>
                )}
                {asking === r.id && (
                  <div className="m-confirm m-memory__ask" role="group" aria-label="Confirm make core">
                    <p>This fact leaves this project and becomes visible in every project. Make it core?</p>
                    <div className="m-row">
                      <button type="button" className="btn btn-primary" onClick={() => void makeCore(r.id)}>
                        Make it core
                      </button>
                      <button type="button" className="btn btn-quiet" onClick={() => setAsking(null)}>
                        Cancel
                      </button>
                    </div>
                    {rowProblem && (
                      <p className="m-error" role="alert">
                        {rowProblem}
                      </p>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
