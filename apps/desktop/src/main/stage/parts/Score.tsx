// The verdict's shared parts: the score in items, her cards beside the person's marks, the choice
// ("This is it" / "Not quite"), and the saved Project card.

import { useState } from "react";
import { hueColor } from "../../../ui";
import type { Score, ScoreRow } from "../select";
import type { StageWords } from "../words";

/** "4 of 5": the counts are the daemon's; the reasons are its plain words. */
export function ScoreLine({ score, words }: { score: Score; words: StageWords }) {
  return (
    <section className="sp-score" data-role="score" data-short={score.short ? "true" : undefined} aria-label={score.headline}>
      <p className="sp-score__num" aria-hidden="true">
        {score.found}
        <small>
          {words.of} {score.eligible}
        </small>
      </p>
      <div className="sp-score__words">
        <h2 className="sp-score__headline">{score.headline}</h2>
        <p>{score.short ? words.short : words.allFound}</p>
        {score.reasons.length > 0 && (
          <ul className="sp-score__reasons">
            {score.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

type Tone = "success" | "warning" | "info" | undefined;

function said(row: ScoreRow, words: StageWords): { result: string; tone: Tone; sub: string } {
  if (!row.scored) return { result: words.unscored, tone: "info", sub: words.yourLine };
  const sub = row.kind === "missing" ? words.yourLine : row.mark === "no" ? row.note || words.youSaidNo : words.youExpected;
  if (row.mark === "yes") return row.filed ? { result: words.filedIt, tone: "success", sub } : { result: words.missedIt, tone: "warning", sub };
  return row.filed ? { result: words.filedNo, tone: "warning", sub } : { result: words.leftAlone, tone: "success", sub };
}

/** Each card she expected, or the person added, with what the person said and what she did. */
export function VerdictRows({ score, words }: { score: Score; words: StageWords }) {
  return (
    <ul className="sp-vrows" data-role="verdict-rows" aria-label={words.verdictTitle}>
      {score.rows.map((row) => {
        const r = said(row, words);
        return (
          <li key={row.id} className="sp-vrow" data-kind={row.kind} data-filed={row.filed ? "true" : undefined}>
            <div>
              <p className="sp-vrow__label">{row.label}</p>
              <p className="sp-vrow__sub">{r.sub}</p>
            </div>
            <span className="badge" data-tone={r.tone}>
              {r.result}
            </span>
          </li>
        );
      })}
      {score.never.map((n) => (
        <li key={n.text} className="sp-vrow" data-kind="never">
          <div>
            <p className="sp-vrow__label">{n.text}</p>
            <p className="sp-vrow__sub">{words.neverLine}</p>
          </div>
          <span className="badge" data-tone={n.tool ? "success" : "info"}>
            {n.tool ? `${words.forbids} ${n.tool}` : words.keptAsWords}
          </span>
        </li>
      ))}
    </ul>
  );
}

export interface VerdictActionsProps {
  onKeep: () => void;
  onRevise: (note: string) => void;
  busy?: boolean;
  words: StageWords;
}

/** "This is it" keeps the chore; "Not quite" (with an optional note) goes back to the sketch. */
export function VerdictActions({ onKeep, onRevise, busy = false, words }: VerdictActionsProps) {
  const [noting, setNoting] = useState(false);
  const [note, setNote] = useState("");
  return (
    <div className="sp-verdict" data-role="verdict-actions">
      {noting ? (
        <form
          className="sp-verdict__note"
          onSubmit={(e) => {
            e.preventDefault();
            onRevise(note);
          }}
        >
          <input
            className="field"
            type="text"
            value={note}
            placeholder={words.reviseNote}
            aria-label={words.reviseNote}
            onChange={(e) => setNote(e.target.value)}
          />
          <button type="submit" className="btn" data-role="revise" disabled={busy}>
            {words.revise}
          </button>
        </form>
      ) : (
        <button type="button" className="btn" data-role="revise" disabled={busy} onClick={() => setNoting(true)}>
          {words.revise}
        </button>
      )}
      <button type="button" className="btn btn-primary" data-role="keep" disabled={busy} onClick={onKeep}>
        {words.keep}
      </button>
    </div>
  );
}

export interface SavedCardProps {
  name: string;
  brief?: string;
  apps?: readonly string[];
  hue?: number;
  /** The kept chore's title, when the library has it. */
  chore?: string;
  onOpen?: () => void;
  words: StageWords;
}

/** The hand-off: the new Project with the chore attached, in the person's own library. */
export function SavedCard({ name, brief = "", apps = [], hue, chore, onOpen, words }: SavedCardProps) {
  const style = hue === undefined ? undefined : { ["--sp-project" as string]: hueColor(hue) };
  return (
    <section className="sp-saved" data-role="saved" aria-label={words.savedTitle}>
      <h2 className="sp-saved__title">{words.savedTitle}</h2>
      <p className="sp-saved__hint">{words.savedHint}</p>
      <div className="sp-saved__project" style={style}>
        <h3>
          <i aria-hidden="true" />
          {name}
        </h3>
        {brief && <p>{brief}</p>}
        {apps.length > 0 && (
          <ul className="sp-saved__apps">
            {apps.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        )}
      </div>
      <p className="sp-saved__row">
        <span className="badge" data-tone="success">
          {words.choreKept}
        </span>
        {chore && <strong>{chore}</strong>}
      </p>
      {onOpen && (
        <button type="button" className="btn btn-primary" data-role="open-project" onClick={onOpen}>
          {words.openProject}
        </button>
      )}
    </section>
  );
}
