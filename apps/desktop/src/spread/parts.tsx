// The pieces a page is made of (ADR 0024): the receipts of what she did, the tally, her answer drawn
// from a turn's parts through the app's own renderers (Prose, CardView, the report's blocks), the
// stopped box and the still-working clock.

import { useEffect, useState, type ReactNode } from "react";
import { ReplyBlocks } from "../athena/ReplyBlocks";
import { useHer, type LivePart } from "../athena/store";
import * as api from "../lib/api";
import type { Card } from "../lib/contract";
import { CardView } from "../ui";
import { Prose } from "../ui/Prose";
import { motionStilled } from "../ui/look";
import { formatCost, isShort, secs, type Receipt } from "./model";

/** What she did, one line per step, with its moment when one was kept. */
export function Receipts({ items, live = false }: { items: readonly Receipt[]; live?: boolean }) {
  const rise = live && !motionStilled();
  return (
    <ol className="sp-receipts" data-role="receipts" aria-live={live ? "polite" : undefined}>
      {items.map((r, i) => (
        <li key={i} className={rise ? "sp-rc sp-rise" : "sp-rc"} data-sort={r.sort}>
          <span className="sp-rc-dot" aria-hidden="true" />
          <span className="sp-rc-t">{r.at === undefined ? "" : `after ${secs(r.at)}`}</span>
          <span className="sp-rc-x">
            {r.text}
            {r.sub && <small>{r.sub}</small>}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** "Took 1 min 52 s · est. $0.0330"; an unpriced turn says so, which is not free. */
export function Tally({ took, cost, stopped }: { took?: number; cost?: number; stopped: boolean }) {
  return (
    <p className="sp-tally" data-role="tally">
      {took !== undefined && (
        <span>
          Took <strong>{secs(took)}</strong>
        </span>
      )}
      <span>{cost !== undefined ? <strong>{formatCost(cost)}</strong> : stopped ? "no cost figure: this try stopped" : "no cost figure"}</span>
    </p>
  );
}

function InlineCard({ card }: { card: Card }) {
  const decided = useHer((s) => s.decided);
  return <CardView card={card} onDecide={(...answer) => api.decide(card.id, ...answer)} onResolved={decided} />;
}

/** Her answer from the turn's parts in the order they streamed. A tool line is a receipt, never part
 *  of the answer. `writing` reads the last run provisionally and fades in its new words. */
export function Answer({ parts, cards, writing = false }: { parts: readonly LivePart[]; cards: Record<string, Card>; writing?: boolean }) {
  const short = !writing && isShort(parts);
  return (
    <div className={short ? "sp-answer is-short" : "sp-answer"} data-role="answer">
      {parts.map((p, n) => {
        switch (p.kind) {
          case "text":
            return p.text.trim() ? <Prose key={n} text={p.text} live={writing && n === parts.length - 1} marks={p.marks} /> : null;
          case "card": {
            const card = cards[p.id];
            return card ? <InlineCard key={n} card={card} /> : null;
          }
          case "blocks":
            return <ReplyBlocks key={n} shown={p.shown} />;
          case "unknown":
            return (
              <p key={n} className="sp-unknown" data-part={p.what}>
                A part of this reply cannot be shown in this version of the app.
              </p>
            );
          case "tool":
            return null;
        }
      })}
    </div>
  );
}

/** The try stopped: why, that nothing changed, and the way on. */
export function Stopped({ reason, children }: { reason: string; children?: ReactNode }) {
  return (
    <div className="sp-stopped" role="alert" data-role="stopped">
      <p>
        <strong>This try stopped: </strong>
        {reason}
      </p>
      <p className="sp-note">Nothing changed. What she wrote before it stopped stays on this page.</p>
      {children}
    </div>
  );
}

/** Her still-working clock, in words, counted from when the page was sent. Only its words change. */
export function Clock({ started }: { started: number }) {
  const [now, setNow] = useState(() => performance.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(performance.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  const ms = Math.max(0, now - started);
  return (
    <p className="sp-clock" data-role="clock" role="status">
      <span className="sp-pulse" aria-hidden="true" />
      <span>{ms < 1000 ? "She has started." : `She is still working, ${secs(ms)}. You can turn the page; this one keeps writing.`}</span>
    </p>
  );
}
