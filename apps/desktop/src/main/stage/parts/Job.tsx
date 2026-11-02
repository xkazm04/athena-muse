// Her background work, as both views show it (onboarding-jobs): the compact status of a running job
// (a clock with no promise, Stop, Leave for now) or of one the person stopped, and "meanwhile", the
// two questions asked while she works. Nothing here waits on the person; Skip is always there.

import { useState, type FormEvent } from "react";
import type { DraftJobKind } from "../../../lib/contract";
import { LINE_MAX } from "../select";
import type { MeanwhileQuestion } from "../types";
import type { StageWords } from "../words";
import { RunProgress } from "./Later";

export interface JobStatusProps {
  kind: DraftJobKind;
  /** Running: the clock and the two ways out. Stopped: what happened and the way back in. */
  state: "running" | "stopped";
  elapsedS?: number;
  /** The usual time, shown only until it is passed; writing shows none (it can take five minutes). */
  aboutS?: number;
  /** Stop was pressed and the job has not ended yet. */
  stopping?: boolean;
  /** The person pressed Stop (else the daemon closed while it ran). */
  byYou?: boolean;
  reason?: string;
  onStop: () => void;
  onLeave: () => void;
  onAgain: () => void;
  words: StageWords;
}

/** The strip's job line: `[data-role=job][data-kind][data-state]`. */
export function JobStatus(p: JobStatusProps) {
  const { kind, state, words } = p;
  if (state === "stopped") {
    return (
      <div className="sp-job" data-role="job" data-kind={kind} data-state="stopped" role="status">
        <p className="sp-job__said">
          <b>{p.byYou === false ? words.sheStopped : words.youStopped}</b>
          {p.byYou === false && p.reason && <span className="sp-job__why">{p.reason}</span>}
          {kind === "write" && <span className="sp-job__why">{words.nothingLostStop}</span>}
        </p>
        <div className="sp-job__acts">
          <button type="button" className="btn btn-primary" data-role="job-again" onClick={p.onAgain}>
            {kind === "write" ? words.writeAgain : words.retry}
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="sp-job" data-role="job" data-kind={kind} data-state="running">
      <RunProgress label={words.jobHint[kind]} elapsedS={p.elapsedS ?? 0} aboutS={p.aboutS} words={words} />
      <p className="sp-job__hint">{words.jobHint[kind]}</p>
      <div className="sp-job__acts">
        <button type="button" className="btn" data-role="job-stop" disabled={p.stopping} onClick={p.onStop}>
          {p.stopping ? words.stopping : words.stop}
        </button>
        <button type="button" className="btn btn-quiet" data-role="job-leave" onClick={p.onLeave}>
          {words.leaveForNow}
        </button>
      </div>
    </div>
  );
}

export interface MeanwhileProps {
  /** The questions still to ask, in order; the first is shown. Nothing is drawn when none are left. */
  left: readonly MeanwhileQuestion[];
  expect: readonly string[];
  /** The never lines: what the person said, or the sketch's never pieces before they said anything. */
  never: readonly string[];
  /** The whole lines of one question after a change; the store sends the whole notes. */
  onLines: (question: MeanwhileQuestion, lines: string[]) => void;
  /** Done keeps what is there; skip keeps only what the person already said. */
  onDone: (question: MeanwhileQuestion, skip: boolean) => void;
  words: StageWords;
}

/** One question at a time while she works, in the stage's question-card style. */
export function Meanwhile({ left, expect, never, onLines, onDone, words }: MeanwhileProps) {
  const q = left[0];
  if (!q) return null;
  const lines = q === "expect" ? expect : never;
  return (
    <section className="sp-meanwhile" data-role="meanwhile" aria-label={words.meanwhile}>
      <div className="sp-question" data-role={q === "expect" ? "meanwhile-expect" : "meanwhile-never"}>
        <span className="sp-question__about">{words.meanwhile}</span>
        <h3 className="sp-question__text sp-meanwhile__q">{q === "expect" ? words.expectQ : words.neverQ}</h3>
        <p className="sp-meanwhile__hint">{q === "expect" ? words.expectHint : lines.length ? words.neverFromSketch : ""}</p>
      </div>
      <MeanwhileLines
        key={q}
        lines={lines}
        placeholder={q === "expect" ? words.expectAdd : words.neverAdd}
        onChange={(next) => onLines(q, next)}
        words={words}
      />
      <div className="sp-meanwhile__acts">
        <button type="button" className="btn btn-quiet" data-role="meanwhile-skip" onClick={() => onDone(q, true)}>
          {words.skip}
        </button>
        <button type="button" className="btn" data-role="meanwhile-done" disabled={!lines.length} onClick={() => onDone(q, false)}>
          {q === "expect" ? words.thatsAll : words.keepThese}
        </button>
      </div>
    </section>
  );
}

function MeanwhileLines({
  lines,
  placeholder,
  onChange,
  words,
}: {
  lines: readonly string[];
  placeholder: string;
  onChange: (lines: string[]) => void;
  words: StageWords;
}) {
  const [text, setText] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    onChange([...lines, t]);
    setText("");
  };
  return (
    <>
      {lines.length > 0 && (
        <ul className="sp-meanwhile__lines">
          {lines.map((l, i) => (
            <li key={l} className="sp-meanwhile__line" data-role="meanwhile-line">
              <span>{l}</span>
              <button
                type="button"
                className="btn btn-quiet"
                aria-label={`${words.remove}: ${l}`}
                onClick={() => onChange(lines.filter((_, k) => k !== i))}
              >
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
          placeholder={placeholder}
          aria-label={placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && e.nativeEvent.isComposing) e.preventDefault();
          }}
        />
        <button type="submit" className="btn" disabled={!text.trim()}>
          {words.add}
        </button>
      </form>
    </>
  );
}
