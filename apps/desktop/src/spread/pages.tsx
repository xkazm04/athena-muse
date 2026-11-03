// The book's own pages (ADR 0024): an exchange as a spread, the page being written, and the cards
// that wait for a signature on no page of this book. A window adds its back pages (`BackPage`).

import { forwardRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useHer } from "../athena/store";
import * as api from "../lib/api";
import { TEXT_MAX, type Card } from "../lib/contract";
import { ACTION_WORDS, CardView } from "../ui";
import { Answer, Clock, Receipts, Stopped, Tally } from "./parts";
import { dateShort, formatCost, receiptsOf, triedAgainNext, waitsWords, type Exchange } from "./model";
import { phaseOf, SHOWS } from "./phase";

/** A page of the book, as the book draws it and its ribbon names it. */
export interface Page {
  key: string;
  kind: "exchange" | "now" | "back";
  /** The tab's first line: "Page 3", or a back page's glyph. */
  num: string;
  label: string;
  sub: string;
  stopped?: boolean;
  /** One page wide (the right page is not drawn). */
  single?: boolean;
  /** Holds a card waiting for the person's signature (a pink dot on its tab). */
  waiting?: boolean;
  /** Being written now (a pulsing dot on its tab). */
  live?: boolean;
  left: ReactNode;
  right: ReactNode;
  /** What each page is, for a screen reader. */
  leftLabel: string;
  rightLabel: string;
}

/** A page a window adds after the conversation (the main window's report, chore, costs...). */
export type BackPage = Omit<Page, "kind" | "num" | "stopped" | "live"> & { glyph: string };

const SIM_BAND = "Simulated - connect Muse in the main window for real answers";

const words = (cards: Record<string, Card>) => (id: string) => {
  const c = cards[id];
  return c ? ACTION_WORDS[c.action] : undefined;
};

// --- an exchange ----------------------------------------------------------------------------

interface ExchangeProps {
  xs: readonly Exchange[];
  i: number;
  cards: Record<string, Card>;
  turn: (key: string) => void;
}

export function ExchangeLeft({ xs, i, cards, turn }: ExchangeProps) {
  const x = xs[i]!;
  const stoppedByYou = useHer((s) => s.stoppedByYou);
  const newest = i === xs.length - 1;
  const waitingHere = x.cards.some((id) => cards[id]?.state === "waiting");
  const youStopped = x.unanswered && newest && stoppedByYou !== "" && stoppedByYou === x.person?.text;
  const receipts = receiptsOf(x.parts, words(cards), x.stopped !== undefined ? { stopped: x.stopped, ...stopAt(x) } : {});
  return (
    <div>
      <p className="sp-kicker">
        <span className="eyebrow">{x.person ? "You asked" : "She began"}</span>
        {(x.stopped !== undefined || x.unanswered) && (
          <span className="badge" data-tone="error">
            This try stopped
          </span>
        )}
        {x.secondTry && (
          <span className="badge" data-tone="info">
            Second try
          </span>
        )}
        {waitingHere && (
          <span className="badge" data-tone="human">
            Waits for your signature
          </span>
        )}
      </p>
      <h2 className="sp-ask" data-role="ask">
        {x.person ? x.person.text : "She spoke first"}
      </h2>
      <p className="sp-when">{dateShort((x.person ?? x.reply)!.created)}</p>
      <h3 className="sp-h">What she did</h3>
      {receipts.length > 0 ? <Receipts items={receipts} /> : <p className="sp-foot">{youStopped ? "You stopped her before she wrote anything." : "No answer was kept for this question."}</p>}
      {x.reply && <Tally took={x.reply.duration_ms} cost={x.reply.cost_usd} stopped={x.stopped !== undefined} />}
      {triedAgainNext(xs, i) && (
        <p className="sp-foot">
          <button type="button" className="sp-linkish" onClick={() => turn(xs[i + 1]!.key)}>
            She tried again on the next page &rarr;
          </button>
        </p>
      )}
      {x.secondTry && (
        <p className="sp-foot">
          <button type="button" className="sp-linkish" onClick={() => turn(xs[i - 1]!.key)}>
            &larr; The try that stopped
          </button>
        </p>
      )}
      {newest && (
        <p className="sp-foot">
          <button type="button" className="sp-linkish" onClick={() => turn("now")}>
            Write a new page &rarr;
          </button>
        </p>
      )}
    </div>
  );
}

/** The stop's moment is the turn's length: it stopped when the turn ended. */
const stopAt = (x: Exchange): { stoppedAt?: number } => (x.reply?.duration_ms === undefined ? {} : { stoppedAt: x.reply.duration_ms });

export function ExchangeRight({ xs, i, cards, turn }: ExchangeProps) {
  const x = xs[i]!;
  const send = useHer((s) => s.send);
  const streaming = useHer((s) => s.streaming);
  const failed = x.stopped !== undefined || x.unanswered;
  const again = x.person && !triedAgainNext(xs, i) && !streaming ? () => {
    turn("now");
    void send(x.person!.text);
  } : null;
  return (
    <div>
      <p className="sp-her">
        <span className="eyebrow">{failed ? "Her words before it stopped" : "Her answer"}</span>
      </p>
      <Answer parts={x.parts} cards={cards} />
      {failed && (
        <Stopped reason={x.stopped ?? "No answer was kept for this question."}>
          {triedAgainNext(xs, i) ? (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => turn(xs[i + 1]!.key)}>
              See her second try
            </button>
          ) : (
            again && (
              <button type="button" className="btn btn-primary btn-sm" onClick={again}>
                Try again
              </button>
            )
          )}
        </Stopped>
      )}
      {x.reply?.cost_usd !== undefined && <p className="sp-cost">{formatCost(x.reply.cost_usd)}</p>}
    </div>
  );
}

export function exchangePage(xs: readonly Exchange[], i: number, cards: Record<string, Card>, turn: (key: string) => void): Page {
  const x = xs[i]!;
  const failed = x.stopped !== undefined || x.unanswered;
  const cost = x.reply?.cost_usd;
  return {
    key: x.key,
    kind: "exchange",
    num: `Page ${x.num}`,
    label: x.person ? x.person.text : "She spoke first",
    sub: failed ? "stopped" : cost !== undefined ? formatCost(cost) : "",
    stopped: failed,
    waiting: x.cards.some((id) => cards[id]?.state === "waiting"),
    left: <ExchangeLeft xs={xs} i={i} cards={cards} turn={turn} />,
    right: <ExchangeRight xs={xs} i={i} cards={cards} turn={turn} />,
    leftLabel: "Left page: what you asked and what she did",
    rightLabel: "Right page: her answer",
  };
}

// --- the page being written --------------------------------------------------------------------

const COUNT_FROM = TEXT_MAX - 400;

/** Where the person writes. Enter sends, Shift+Enter is a new line. */
export const Composer = forwardRef<HTMLTextAreaElement>(function Composer(_, ref) {
  const text = useHer((s) => s.draft);
  const setText = useHer((s) => s.setDraft);
  const [said, setSaid] = useState("");
  const ready = useHer((s) => s.status === "ready");
  const send = useHer((s) => s.send);

  const submit = () => {
    const value = text.trim();
    if (!value) {
      setSaid("Write something first.");
      return;
    }
    if (!ready) return;
    setText("");
    setSaid("");
    void send(value);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };
  return (
    <>
      <form
        className="sp-composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <textarea
          ref={ref}
          className="field"
          rows={2}
          value={text}
          maxLength={TEXT_MAX}
          placeholder="Message Athena"
          aria-label="Your words to Athena"
          disabled={!ready}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className="btn btn-primary" disabled={!ready}>
          Send
        </button>
      </form>
      <p className="sp-said" aria-live="polite">
        {said || (text.length >= COUNT_FROM ? `${text.length}/${TEXT_MAX}` : "")}
      </p>
    </>
  );
});

export const NowLeft = forwardRef<HTMLTextAreaElement, { empty: boolean }>(function NowLeft({ empty }, ref) {
  const streaming = useHer((s) => s.streaming);
  const live = useHer((s) => s.live);
  const sent = useHer((s) => s.sent);
  const cards = useHer((s) => s.cards);
  const stop = useHer((s) => s.stop);
  const retry = useHer((s) => s.retry);
  const dismiss = useHer((s) => s.dismiss);
  const phase = phaseOf({ streaming, live });
  const shows = SHOWS[phase];

  if (shows.composer) {
    return (
      <div>
        <p className="sp-kicker">
          <span className="eyebrow">A new page</span>
        </p>
        <h2 className="sp-ask">Ask her</h2>
        <Composer ref={ref} />
        {empty && <p className="sp-foot">Ask Athena anything. In a project, she remembers it there.</p>}
      </div>
    );
  }
  const parts = live?.parts ?? [];
  const receipts = receiptsOf(parts, words(cards), { writing: shows.clock, ...(live?.error !== undefined ? { stopped: live.error } : {}) });
  return (
    <div>
      <p className="sp-kicker">
        <span className="eyebrow">Writing now</span>
        {shows.retry && (
          <span className="badge" data-tone="error">
            This try stopped
          </span>
        )}
      </p>
      <h2 className="sp-ask" data-role="ask">
        {sent || "She begins"}
      </h2>
      <p className="sp-when">{sent ? "You asked just now" : "Just now"}</p>
      <h3 className="sp-h">What she is doing</h3>
      <Receipts items={receipts} live />
      {shows.clock && live && <Clock started={live.started} />}
      <div className="sp-controls">
        {shows.stop && streaming && (
          <button type="button" className="btn btn-sm" onClick={stop}>
            Stop
          </button>
        )}
        {shows.retry && (
          <>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => void retry()}>
              Try again
            </button>
            <button type="button" className="btn btn-sm" onClick={dismiss}>
              Write another page
            </button>
          </>
        )}
      </div>
    </div>
  );
});

export function NowRight() {
  const streaming = useHer((s) => s.streaming);
  const live = useHer((s) => s.live);
  const cards = useHer((s) => s.cards);
  const simulated = useHer((s) => s.engine?.simulated === true);
  const phase = phaseOf({ streaming, live });
  const parts = live?.parts ?? [];
  const begun = parts.some((p) => p.kind !== "tool");
  return (
    <div>
      <p className="sp-her">
        <span className="eyebrow">Her answer</span>
      </p>
      {simulated && (
        <p className="sp-band" role="status">
          {SIM_BAND}
        </p>
      )}
      {phase === "ask" && <p className="sp-placeholder">Ask her something and she writes this page while you watch. You can turn to another page; this one keeps writing.</p>}
      {phase !== "ask" && !begun && phase === "writing" && <p className="sp-placeholder">Her answer will be written here.</p>}
      {phase !== "ask" && <Answer parts={parts} cards={cards} writing={phase === "writing"} />}
      {phase === "failed" && live?.error !== undefined && <Stopped reason={live.error} />}
    </div>
  );
}

// --- cards waiting on no page of this book ------------------------------------------------------

export function WaitingLeft({ stray }: { stray: readonly Card[] }) {
  return (
    <div>
      <p className="sp-kicker">
        <span className="eyebrow">Waiting for your signature</span>
      </p>
      <h2 className="sp-ask">{waitsWords(stray.length)}</h2>
      <p className="sp-when">On no page of this conversation: in another project, or filed by a routine.</p>
      <p className="sp-foot">Nothing she asks for here happens until you sign it.</p>
    </div>
  );
}

export function WaitingRight({ stray }: { stray: readonly Card[] }) {
  const spaces = useHer((s) => s.spaces);
  const decided = useHer((s) => s.decided);
  const where = (id: string) => (id === "" ? "Core" : (spaces.find((s) => s.id === id)?.name ?? "A project"));
  return (
    <div className="sp-cards" data-role="waiting-cards">
      {stray.map((c) => (
        <CardView key={c.id} card={c} where={where(c.space_id)} onDecide={(...answer) => api.decide(c.id, ...answer)} onResolved={decided} />
      ))}
    </div>
  );
}
