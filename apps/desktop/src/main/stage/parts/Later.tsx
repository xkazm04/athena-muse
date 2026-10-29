// The later steps' shared parts: a practice-app tile, the problems list, progress with a clock, the
// test run's phases and the cards she filed (shown, never signable).

import type { Card } from "../../../lib/contract";
import type { RunPhase } from "../select";
import type { StageWords } from "../words";

/** m:ss */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export interface PracticeTileProps {
  name: string;
  reads?: readonly string[];
  does?: readonly string[];
  /** Invented rows in it, when known. */
  rows?: number;
  /** Just made: the view may draw it arriving. */
  fresh?: boolean;
  words: StageWords;
}

/** One of her practice apps: made up for the test, never the person's real one. */
export function PracticeTile({ name, reads = [], does = [], rows, fresh = false, words }: PracticeTileProps) {
  return (
    <div className="sp-tile" data-role="practice-tile" data-fresh={fresh ? "true" : undefined} title={words.practiceTile}>
      <p className="sp-tile__name">{name}</p>
      {reads.length > 0 && (
        <p className="sp-tile__line">
          <b>{words.reads}:</b> {reads.join(", ")}
        </p>
      )}
      {(reads.length > 0 || does.length > 0) && (
        <p className="sp-tile__line">
          <b>{words.does}:</b> {does.length ? does.join(", ") : words.onlyLooks}
        </p>
      )}
      {rows !== undefined && (
        <span className="badge sp-tile__rows">
          {rows} {words.rows}
        </span>
      )}
    </div>
  );
}

export interface ProblemListProps {
  title: string;
  problems: readonly string[];
  /** "repair": her own check found these and she is fixing them; "failed": two repairs did not. */
  tone: "repair" | "failed";
}

/** Problems in plain words (the daemon already says them plainly). */
export function ProblemList({ title, problems, tone }: ProblemListProps) {
  return (
    <section className="sp-problems" data-role="problems" data-tone={tone} aria-label={title}>
      <h3 className="sp-problems__title">{title}</h3>
      <ul>
        {problems.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
    </section>
  );
}

export interface RunProgressProps {
  label: string;
  elapsedS: number;
  /** The measured time it usually takes; the bar never claims to be done before the daemon says so. */
  aboutS: number;
  words: StageWords;
}

/** A bar and a clock: "1:12 of about 1:30". */
export function RunProgress({ label, elapsedS, aboutS, words }: RunProgressProps) {
  const share = Math.min(0.95, aboutS > 0 ? elapsedS / aboutS : 0);
  return (
    <div className="sp-progress" data-role="progress">
      <div
        className="sp-progress__bar"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(share * 100)}
      >
        <i style={{ transform: `scaleX(${share})` }} />
      </div>
      <p className="sp-progress__clock">
        {clock(elapsedS)} {words.aboutTime} {clock(aboutS)}
      </p>
    </div>
  );
}

export interface PhaseListProps {
  phases: readonly RunPhase[];
  /** The run is over: every phase reads done. */
  done: boolean;
  /** Plain names for the practice apps by id, when known; the id otherwise. */
  appName?: (appId: string) => string;
  words: StageWords;
}

/** The test run's phases across her practice apps, the latest one current. */
export function PhaseList({ phases, done, appName = (a) => a, words }: PhaseListProps) {
  const current = phases.at(-1);
  return (
    <div className="sp-phases" data-role="phases">
      <ol className="sp-phases__list" aria-label={words.phases}>
        {phases.map((p) => {
          const now = !done && p === current;
          return (
            <li
              key={p.index}
              className="sp-phase"
              data-done={done || !now ? "true" : undefined}
              aria-current={now ? "step" : undefined}
              title={p.message}
            >
              {appName(p.app)}
            </li>
          );
        })}
      </ol>
      <p className="sp-phases__now">
        {done ? (
          <>
            <b>{words.done}</b> {words.ranAll}
          </>
        ) : (
          <>
            <b>{current ? words.now : words.starting}</b> {current ? `${appName(current.app)}: ${current.message}` : ""}
          </>
        )}
      </p>
    </div>
  );
}

/** The cards she filed in the test run: shown so the person sees them, never offered for signing. */
export function FiledCards({ cards, words }: { cards: readonly Card[]; words: StageWords }) {
  return (
    <section className="sp-filed" data-role="filed" aria-label={words.filed}>
      <h4 className="sp-filed__title">
        {words.filed}: {cards.length}
      </h4>
      <p className="sp-filed__never">{words.neverSigned}</p>
      {cards.length ? (
        <ul className="sp-filed__list">
          {cards.map((c) => (
            <li key={c.id} className="sp-slip" title={c.label}>
              {c.label}
            </li>
          ))}
        </ul>
      ) : (
        <p className="sp-filed__empty">{words.noneYet}</p>
      )}
    </section>
  );
}
