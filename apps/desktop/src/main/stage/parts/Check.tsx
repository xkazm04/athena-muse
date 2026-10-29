// The check step's shared parts: one expected card with its yes/no and note, the "she missed one" and
// "she must never..." rows, and "Run the test". The stage's keymap marks with Y and N and moves with
// the arrows; it finds the card by `data-role="check-card"` and `data-expected-id`.

import { useState, type FormEvent } from "react";
import type { ExpectedCard, Mark } from "../../../lib/contract";
import { LINE_MAX } from "../select";
import type { StageWords } from "../words";

export interface CheckCardProps {
  card: ExpectedCard;
  mark?: Mark;
  note?: string;
  onMark: (mark: Mark) => void;
  onUnmark: () => void;
  onNote: (note: string) => void;
  /** The practice app's plain name, when known. */
  appName?: string;
  words: StageWords;
}

/** One card she expects to file: yes means she should, no means she must leave it (with a note). */
export function CheckCard({ card, mark, note = "", onMark, onUnmark, onNote, appName, words }: CheckCardProps) {
  const press = (m: Mark) => (mark === m ? onUnmark() : onMark(m));
  return (
    <article className="sp-check" data-role="check-card" data-expected-id={card.id} data-mark={mark} tabIndex={-1}>
      <div className="sp-check__text">
        <p className="sp-check__label">{card.label}</p>
        <p className="sp-check__why">{card.why}</p>
        {appName && <p className="sp-check__app">{appName}</p>}
      </div>
      <div className="sp-check__marks" role="group" aria-label={words.shouldFile}>
        <button type="button" className="sp-mark" data-role="mark-yes" data-v="yes" aria-pressed={mark === "yes"} onClick={() => press("yes")}>
          {words.yes}
        </button>
        <button type="button" className="sp-mark" data-role="mark-no" data-v="no" aria-pressed={mark === "no"} onClick={() => press("no")}>
          {words.no}
        </button>
      </div>
      {mark === "no" && (
        <input
          className="field sp-check__note"
          data-role="note"
          type="text"
          maxLength={LINE_MAX}
          placeholder={words.whyNot}
          aria-label={words.whyNot}
          defaultValue={note}
          onBlur={(e) => onNote(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.nativeEvent.isComposing) onNote(e.currentTarget.value);
          }}
        />
      )}
    </article>
  );
}

export interface LineAdderProps {
  kind: "missing" | "never";
  lines: readonly string[];
  onAdd: (text: string) => void;
  onRemove: (index: number) => void;
  words: StageWords;
}

/** "She missed one" or "She must never...": the person's own lines, added and removed. */
export function LineAdder({ kind, lines, onAdd, onRemove, words }: LineAdderProps) {
  const [text, setText] = useState("");
  const title = kind === "missing" ? words.missed : words.never;
  const hint = kind === "missing" ? words.missedHint : words.neverHint;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    onAdd(text);
    setText("");
  };
  return (
    <section className="sp-lines" data-role={kind === "missing" ? "missed" : "never-line"} data-kind={kind} aria-label={title}>
      <h4 className="sp-lines__title">{title}</h4>
      {lines.length > 0 && (
        <ul className="sp-lines__list">
          {lines.map((l, i) => (
            <li key={l}>
              <span>{l}</span>
              <button type="button" className="btn btn-quiet" aria-label={`${words.remove}: ${l}`} onClick={() => onRemove(i)}>
                {words.remove}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form className="sp-lines__add" onSubmit={submit}>
        <input
          className="field"
          type="text"
          value={text}
          maxLength={LINE_MAX}
          placeholder={hint}
          aria-label={title}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && e.nativeEvent.isComposing) e.preventDefault();
          }}
        />
        <button type="submit" className="btn" disabled={!text.trim()}>
          {words.add}
        </button>
      </form>
    </section>
  );
}

export interface RunTestButtonProps {
  /** Cards still unmarked; the test runs once every card has a yes or a no. */
  left: number;
  total: number;
  onRun: () => void;
  busy?: boolean;
  words: StageWords;
}

/** "Run the test": the marks become the key and the test run starts, in one press. */
export function RunTestButton({ left, total, onRun, busy = false, words }: RunTestButtonProps) {
  return (
    <div className="sp-runtest">
      <span className="sp-runtest__left" aria-live="polite">
        {left ? `${left} ${words.toMark}` : `${total - left} ${words.of} ${total} ${words.marked}`}
      </span>
      <button type="button" className="btn btn-primary" data-role="run-test" disabled={left > 0 || busy} onClick={onRun}>
        {words.runTest}
      </button>
    </div>
  );
}
