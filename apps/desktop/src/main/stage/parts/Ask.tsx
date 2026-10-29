// The shaping frame's shared parts: the one question, its suggestions (keys 1-4) and "say it your own
// way", the "you said" echo, the reply's notices, what she still needs, the exit, and the banner
// that brings the person back to the sketch.

import { useState, type FormEvent, type KeyboardEvent } from "react";
import type { Ask, Coverage } from "../../../lib/contract";
import { missingFor, openSlots } from "../select";
import type { ReplyPhase } from "../types";
import type { StageWords } from "../words";

const list = (items: readonly string[]) =>
  items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;

/** The one question, with the part of the sketch it is about. */
export function Question({ ask, words }: { ask: Ask; words: StageWords }) {
  return (
    <div className="sp-question" data-role="question" data-slot={ask.slot}>
      <span className="sp-question__about">
        {words.about} {words.slot[ask.slot].toLowerCase()}
      </span>
      <h2 className="sp-question__text" data-role="ask-text">
        {ask.text}
      </h2>
    </div>
  );
}

export interface SuggestionsProps {
  suggestions: readonly string[];
  onPick: (choice: string) => void;
  disabled?: boolean;
  words: StageWords;
}

/** Her suggested answers; the stage's keymap picks them with 1 to 4. */
export function Suggestions({ suggestions, onPick, disabled = false, words }: SuggestionsProps) {
  return (
    <div className="sp-suggestions" role="group" aria-label={words.suggestions}>
      {suggestions.slice(0, 4).map((s, i) => (
        <button
          key={s}
          type="button"
          className="sp-suggestion"
          data-role="suggestion"
          aria-keyshortcuts={String(i + 1)}
          disabled={disabled}
          title={s}
          onClick={() => onPick(s)}
        >
          <kbd className="sp-suggestion__key" aria-hidden="true">
            {i + 1}
          </kbd>
          <span className="sp-suggestion__text">{s}</span>
        </button>
      ))}
    </div>
  );
}

export interface ComposerProps {
  onSay: (text: string) => void;
  disabled?: boolean;
  /** Shown in the field, for "say it differently" after a failed reply. */
  initial?: string;
  words: StageWords;
  label?: string;
}

/** "Or say it your own way": Enter sends, unless an input method is still composing. */
export function Composer({ onSay, disabled = false, initial = "", words, label }: ComposerProps) {
  const [text, setText] = useState(initial);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || disabled) return;
    onSay(t);
    setText("");
  };
  const guard = (e: KeyboardEvent<HTMLInputElement>) => {
    // Enter that ends an IME composition picks the word; it must not send the answer.
    if (e.key === "Enter" && (e.nativeEvent.isComposing || e.keyCode === 229)) e.preventDefault();
  };
  return (
    <form className="sp-composer" data-role="composer" onSubmit={submit}>
      <input
        className="field sp-composer__field"
        type="text"
        value={text}
        maxLength={2000}
        placeholder={words.ownWords}
        aria-label={label ?? words.ownWords}
        autoComplete="off"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={guard}
      />
      <button type="submit" className="btn btn-primary" disabled={disabled || !text.trim()}>
        {words.send}
      </button>
    </form>
  );
}

/** "You said ..." while she reads it. */
export function Echo({ text, words }: { text: string; words: StageWords }) {
  if (!text) return null;
  return (
    <p className="sp-echo" data-role="echo">
      <small className="sp-echo__who">{words.youSaid}</small>
      <span className="sp-echo__text">{text}</span>
    </p>
  );
}

export interface ReplyNoticeProps {
  phase: ReplyPhase;
  /** Plain words for a failure; the daemon's reason. */
  problem: string;
  onRetry: () => void;
  /** After a failure: put the person back in the composer. */
  onSayDifferently?: () => void;
  words: StageWords;
}

/** Thinking, slow past 8 s, or failed with a retry. Never shown as progress when it failed. */
export function ReplyNotice({ phase, problem, onRetry, onSayDifferently, words }: ReplyNoticeProps) {
  if (phase === "idle") return null;
  if (phase === "failed") {
    return (
      <div className="sp-notice" data-role="notice" data-phase="failed" role="alert">
        <p className="sp-notice__text">
          <strong>{words.failed}</strong>
          {problem && <span className="sp-notice__why">{problem}</span>}
        </p>
        <div className="sp-notice__actions">
          <button type="button" className="btn btn-primary" data-role="retry" onClick={onRetry}>
            {words.retry}
          </button>
          {onSayDifferently && (
            <button type="button" className="btn" onClick={onSayDifferently}>
              {words.sayDifferently}
            </button>
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="sp-notice" data-role="notice" data-phase={phase} role="status" aria-live="polite">
      <span className="sp-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span className="sp-notice__text">{phase === "slow" ? words.slow : words.thinking}</span>
    </div>
  );
}

/** "She still needs: ..." from coverage, or "Ready when you are." once agreed. */
export function StillNeeds({ coverage, words }: { coverage: Coverage; words: StageWords }) {
  const needs = missingFor(coverage);
  return (
    <p className="sp-still" data-role="still-needs" data-ready={needs.length ? undefined : "true"}>
      {needs.length ? (
        <>
          {words.stillNeeds}: <b>{list(needs.map((s) => words.needPhrase[s]))}</b>
        </>
      ) : (
        words.ready
      )}
    </p>
  );
}

export interface EnoughButtonProps {
  coverage: Coverage;
  agreed: boolean;
  onEnough: () => void;
  disabled?: boolean;
  words: StageWords;
}

/** "That's enough, write it", from the first frame; the slots it would leave open are named. */
export function EnoughButton({ coverage, agreed, onEnough, disabled = false, words }: EnoughButtonProps) {
  const open = openSlots(coverage);
  return (
    <div className="sp-enough">
      <button
        type="button"
        className={agreed ? "btn btn-primary" : "btn"}
        data-role="exit"
        data-ready={agreed ? "true" : undefined}
        disabled={disabled}
        onClick={onEnough}
      >
        {words.enough}
      </button>
      {open.length > 0 && (
        <p className="sp-enough__open">
          {words.leftOpen}: {list(open.map((s) => words.slot[s].toLowerCase()))}
        </p>
      )}
    </div>
  );
}

export interface RevisitBannerProps {
  /** "revise": the person said "Not quite"; "unwritten": two repairs did not fix the chore. */
  why: "revise" | "unwritten";
  note?: string;
  problems?: readonly string[];
  words: StageWords;
}

/** Back to the sketch, with the person's note or her problems in plain words. */
export function RevisitBanner({ why, note = "", problems = [], words }: RevisitBannerProps) {
  return (
    <div className="sp-revisit" data-role="revisit" data-why={why} role="status">
      <p>
        <b>{words.backToSketch}</b> {why === "unwritten" ? words.couldNotWrite : note}
      </p>
      {why === "unwritten" && problems.length > 0 && (
        <ul className="sp-revisit__problems">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
