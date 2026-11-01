// What Athena does on her own in a project (business Phase 2), under the report on its front page: one
// row per routine in the variant's table idiom (eyebrow heads, light rules) - its name and when it runs
// next, the last run in plain words with the daemon's note as given, what it spent (est.), Pause or
// Resume and Run now, and a fold with its last runs. The strip folds to its head, so a short window
// keeps the report in view. Every figure is the daemon's.

import { useEffect, useState } from "react";
import * as api from "../../lib/api";
import type { Routine, RoutineBody, RoutineRun, SpaceSummary } from "../../lib/contract";
import { reasonOf, ROUTINES_IDLE, useMain, type RoutinesState } from "../store";
import { rel } from "./format";
import { needsUrl, nextLine, runLine, spentLine, toneOf, URL_LABEL } from "./routineWords";
import "./routines.css";

export interface RoutinesBodyProps {
  state: RoutinesState;
  now: Date;
  onChange: (routineId: string, body: RoutineBody) => Promise<unknown>;
  onRun: (routineId: string) => Promise<unknown>;
  onRuns: (routineId: string) => Promise<RoutineRun[]>;
  /** A signed-out run: the project's own "Sign in again". */
  onSignIn: () => void;
  onRetry: () => void;
  /** Folded to its head at first (a short window). */
  folded?: boolean;
}

export const STRIP_TITLE = "What Athena does on her own";

/** The strip as the person sees it, from its state alone (the preview drives it with no daemon). */
export function RoutinesBody({ state, now, onChange, onRun, onRuns, onSignIn, onRetry, folded = false }: RoutinesBodyProps) {
  const [open, setOpen] = useState(!folded);
  // A project without routines shows nothing at all; a first read shows nothing until it answers.
  if (state.load !== "problem" && state.list.length === 0) return null;
  const on = state.list.filter((r) => r.state === "on").length;
  const needs = state.list.filter((r) => toneOf(r) === "warn" || needsUrl(r)).length;
  const sum = [`${on} of ${state.list.length} on`, needs ? `${needs} ${needs === 1 ? "needs" : "need"} you` : ""].filter(Boolean).join(" · ");

  return (
    <section className="rt" data-role="routines" data-open={String(open)} aria-labelledby="rt-title">
      <header className="rt-head">
        <h2 id="rt-title" className="rt-title">
          {STRIP_TITLE}
        </h2>
        {state.list.length > 0 && <p className="rt-sum">{sum}</p>}
        <button type="button" className="rt-fold" aria-expanded={open} aria-controls="rt-list" onClick={() => setOpen(!open)}>
          {open ? "Fold" : "Show"}
        </button>
      </header>
      {open &&
        (state.load === "problem" && state.list.length === 0 ? (
          <div className="rt-problem" role="alert">
            <p>
              <b>This could not be read.</b> {state.problem}
            </p>
            <button type="button" className="btn" onClick={onRetry}>
              Try again
            </button>
          </div>
        ) : (
          <div className="rt-table" id="rt-list">
            <div className="rt-heads" aria-hidden="true">
              <span>What</span>
              <span>Last time</span>
              <span className="rt-num">Spent</span>
              <span />
            </div>
            <ul className="rt-rows">
              {state.list.map((r) => (
                <Row key={r.id} routine={r} now={now} onChange={onChange} onRun={onRun} onRuns={onRuns} onSignIn={onSignIn} />
              ))}
            </ul>
          </div>
        ))}
    </section>
  );
}

type Busy = "run" | "state" | "url" | null;

function Row({
  routine,
  now,
  onChange,
  onRun,
  onRuns,
  onSignIn,
}: {
  routine: Routine;
  now: Date;
  onChange: RoutinesBodyProps["onChange"];
  onRun: RoutinesBodyProps["onRun"];
  onRuns: RoutinesBodyProps["onRuns"];
  onSignIn: () => void;
}) {
  const [busy, setBusy] = useState<Busy>(null);
  const [problem, setProblem] = useState("");
  const [url, setUrl] = useState("");
  const [runs, setRuns] = useState<RoutineRun[] | null>(null);
  const [runsOpen, setRunsOpen] = useState(false);
  const [runsProblem, setRunsProblem] = useState("");
  const run = routine.last_run;
  const paused = routine.state === "paused";
  const ask = needsUrl(routine) ? URL_LABEL[routine.kind] : undefined;
  const spent = spentLine(run);
  const urlId = `rt-url-${routine.id}`;

  const readRuns = async () => {
    try {
      setRuns(await onRuns(routine.id));
      setRunsProblem("");
    } catch (e) {
      setRunsProblem(reasonOf(e, "Its runs could not be read"));
    }
  };

  // A new last run (Run now, or the daemon's own) reads the open fold again.
  useEffect(() => {
    if (runsOpen) void readRuns();
    // readRuns is recreated each render; the last run alone decides when to read
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.id, runsOpen]);

  const doing = async (what: Exclude<Busy, null>, act: () => Promise<unknown>, fallback: string) => {
    setBusy(what);
    setProblem("");
    try {
      await act();
      return true;
    } catch (e) {
      setProblem(reasonOf(e, fallback));
      return false;
    } finally {
      setBusy(null);
    }
  };

  return (
    <li
      className="rt-row"
      data-role="routine"
      data-kind={routine.kind}
      data-outcome={run?.outcome ?? "none"}
      data-reason={run?.reason}
      data-state={routine.state}
      data-tone={toneOf(routine)}
      data-busy={busy === "run" ? "true" : undefined}
      aria-busy={busy === "run"}
    >
      <div className="rt-what">
        <b className="rt-name">{routine.name}</b>
        <span className="rt-next" data-role="routine-next">
          {nextLine(routine, now)}
        </span>
      </div>
      <div className="rt-last">
        <p className="rt-line" data-role="routine-line">
          {busy === "run" ? "running now..." : run ? runLine(routine, run, now) : "has not run yet"}
        </p>
        {busy !== "run" && run?.note && <p className="rt-note">{run.note}</p>}
        {busy !== "run" && run?.reason === "signed_out" && (
          <button type="button" className="rt-link" data-role="routine-sign-in" onClick={onSignIn}>
            Sign in again
          </button>
        )}
      </div>
      <span className="rt-num rt-spent">{spent ?? ""}</span>
      <div className="rt-acts">
        <button
          type="button"
          className="btn rt-btn"
          data-role="routine-pause"
          disabled={busy !== null}
          onClick={() => void doing("state", () => onChange(routine.id, { state: paused ? "on" : "paused" }), "It could not be changed")}
        >
          {busy === "state" ? (paused ? "Resuming..." : "Pausing...") : paused ? "Resume" : "Pause"}
        </button>
        <button
          type="button"
          className="btn btn-primary rt-btn"
          data-role="routine-run-now"
          disabled={busy !== null}
          aria-busy={busy === "run"}
          onClick={() => void doing("run", () => onRun(routine.id), "It could not run")}
        >
          {busy === "run" ? "Running..." : "Run now"}
        </button>
      </div>
      {ask && (
        <form
          className="rt-url"
          data-role="routine-url"
          onSubmit={(e) => {
            e.preventDefault();
            const clean = url.trim();
            if (clean) void doing("url", () => onChange(routine.id, { url: clean }), "The address could not be kept").then((ok) => ok && setUrl(""));
          }}
        >
          <label htmlFor={urlId}>{ask.label}</label>
          <input id={urlId} className="field" type="url" placeholder={ask.placeholder} value={url} disabled={busy !== null} onChange={(e) => setUrl(e.target.value)} />
          <button type="submit" className="btn rt-btn" disabled={busy !== null || !url.trim()}>
            {busy === "url" ? "Keeping..." : "Keep"}
          </button>
        </form>
      )}
      {problem && (
        <p className="m-error rt-problem-line" role="alert">
          {problem}
        </p>
      )}
      <details className="rt-runs" data-role="routine-runs" onToggle={(e) => setRunsOpen(e.currentTarget.open)}>
        <summary>Last runs</summary>
        {runsProblem ? (
          <p className="m-error" role="alert">
            {runsProblem}
          </p>
        ) : runs === null ? (
          <p className="rt-quiet">Reading...</p>
        ) : runs.length === 0 ? (
          <p className="rt-quiet">It has not run yet.</p>
        ) : (
          <table className="m-grid rt-runs__t">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">What happened</th>
                <th scope="col" className="m-num">
                  Spent
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.map((x) => (
                <tr key={x.id} data-outcome={x.outcome}>
                  <td>{rel(x.started, now)}</td>
                  <td>
                    {runLine(routine, x)}
                    {x.note && <span className="rt-runs__note">{x.note}</span>}
                  </td>
                  <td className="m-num">{spentLine(x) ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>
    </li>
  );
}

/** The project's own "Sign in again": the band of blocked sites above the report, brought into view. */
export function toSignIn(): void {
  const band = document.querySelector<HTMLElement>('[data-role="blockers"]');
  if (!band) return;
  band.scrollIntoView?.({ block: "nearest" });
  band.querySelector<HTMLButtonElement>('[data-role="sign-in-again"]')?.focus();
}

/** A project's routines, read when its page opens and kept live by the `routine` event. */
export function Routines({ space }: { space: SpaceSummary }) {
  const state = useMain((s) => s.routines[space.id]) ?? ROUTINES_IDLE;
  const loadRoutines = useMain((s) => s.loadRoutines);
  const changeRoutine = useMain((s) => s.changeRoutine);
  const runRoutine = useMain((s) => s.runRoutine);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    void loadRoutines(space.id);
  }, [space.id, loadRoutines]);

  // "12 min ago" and "next in 4 h" move on by themselves.
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);

  const short = typeof window !== "undefined" && window.innerHeight < 760;
  return (
    <RoutinesBody
      state={state}
      now={now}
      folded={short}
      onChange={changeRoutine}
      onRun={async (id) => {
        await runRoutine(id);
        setNow(new Date());
      }}
      onRuns={api.routineRuns}
      onSignIn={toSignIn}
      onRetry={() => void loadRoutines(space.id)}
    />
  );
}
