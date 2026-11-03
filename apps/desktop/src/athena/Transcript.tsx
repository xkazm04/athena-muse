import { useLayoutEffect, useMemo, useRef } from "react";
import * as api from "../lib/api";
import type { Card, Turn, TurnPart } from "../lib/contract";
import { CardView } from "../ui";
import { Prose } from "../ui/Prose";
import { ReplyBlocks } from "./ReplyBlocks";
import { settledParts, useHer, type Live, type LivePart } from "./store";

/** Muse costs are estimates; every one on screen says so. */
export function formatCost(usd: number): string {
  if (usd > 0 && usd < 0.0001) return "est. under $0.0001";
  return `est. $${usd < 1 ? usd.toFixed(4) : usd.toFixed(2)}`;
}

// How close to the bottom still counts as "at the bottom" for sticking while she writes.
const STICK_PX = 32;

function InlineCard({ card }: { card: Card }) {
  const decided = useHer((s) => s.decided);
  return (
    <div className="her-card">
      <CardView card={card} onDecide={(...answer) => api.decide(card.id, ...answer)} onResolved={decided} />
    </div>
  );
}

function PersonLine({ text }: { text: string }) {
  return (
    <div className="her-line her-line--person">
      <p className="her-bubble">{text}</p>
    </div>
  );
}

interface AthenaLineProps {
  text: string;
  cost?: number;
  writing?: boolean;
  /** Still streaming: read provisionally, new words fade in (`marks` from the store). */
  live?: boolean;
  marks?: readonly number[];
  /** A later text run of the same turn: her name is not said again. */
  more?: boolean;
}

function AthenaLine({ text, cost, writing, live, marks, more }: AthenaLineProps) {
  return (
    <div className="her-line her-line--athena">
      {text.trim() ? (
        <Prose className={more ? "her-say her-say--more" : "her-say"} text={text} live={live} marks={marks} />
      ) : writing ? (
        <p className="her-say her-say--pending" aria-label="Athena is replying">
          <i />
          <i />
          <i />
        </p>
      ) : null}
      {cost !== undefined && <span className="her-cost">{formatCost(cost)}</span>}
    </div>
  );
}

function TurnView({ turn, cards }: { turn: Turn; cards: Record<string, Card> }) {
  if (turn.role === "person") return <PersonLine text={turn.text} />;
  // A settled turn with stored parts is drawn by the same parts renderer as the live one.
  if (turn.parts) return <SettledParts parts={turn.parts} cards={cards} cost={turn.cost_usd} />;
  // A turn stored before parts were kept: its words and its first card, as it always showed.
  const card = turn.card_id ? cards[turn.card_id] : undefined;
  return (
    <>
      <AthenaLine text={turn.text} cost={turn.cost_usd} />
      {card && <InlineCard card={card} />}
    </>
  );
}

function SettledParts({ parts, cards, cost }: { parts: readonly TurnPart[]; cards: Record<string, Card>; cost?: number }) {
  const drawn = useMemo(() => settledParts(parts), [parts]);
  return <PartsView parts={drawn} cards={cards} cost={cost} reveal={false} waiting={false} />;
}

interface PartsViewProps {
  parts: readonly LivePart[];
  cards: Record<string, Card>;
  /** Shown after the last words (or on a line of its own when the turn has none). */
  cost?: number;
  /** The last run is still being written: it reads provisionally and its new words fade in. */
  reveal: boolean;
  /** Dots: she is writing and no words are arriving yet. */
  waiting: boolean;
}

/** One turn's parts in the order they streamed (a tool line between two sentences stands between
 *  them): the one renderer for a live turn and a settled one. */
function PartsView({ parts, cards, cost, reveal, waiting }: PartsViewProps) {
  const said = (n: number) => {
    const p = parts[n];
    return p?.kind === "text" && p.text.trim() !== "";
  };
  const firstText = parts.findIndex((_, n) => said(n));
  let lastText = parts.length - 1;
  while (lastText >= 0 && !said(lastText)) lastText--;
  // A turn with no words (only a card, say) still shows what it cost, on a line of its own.
  const costAlone = lastText === -1 ? cost : undefined;
  return (
    <>
      {parts.map((p, n) => {
        switch (p.kind) {
          case "text":
            return p.text.trim() ? (
              <AthenaLine
                key={`p${n}`}
                text={p.text}
                live={reveal && n === parts.length - 1}
                marks={p.marks}
                more={n !== firstText}
                cost={n === lastText ? cost : undefined}
              />
            ) : null;
          case "tool":
            return (
              <p key={`p${n}`} className="her-tool">
                {p.label}
              </p>
            );
          case "card": {
            const card = cards[p.id];
            return card ? <InlineCard key={`p${n}`} card={card} /> : null;
          }
          case "blocks":
            return <ReplyBlocks key={`p${n}`} shown={p.shown} />;
          case "unknown":
            return (
              <p key={`p${n}`} className="her-tool her-tool--unknown" data-part={p.what}>
                A part of this reply cannot be shown in this version of the app.
              </p>
            );
        }
      })}
      {(waiting || costAlone !== undefined) && <AthenaLine text="" writing={waiting} cost={costAlone} />}
    </>
  );
}

/** The reply as it streams, then the cost once the turn is done, or the failure and "Try again". */
function LiveView({ live, sent, cards, streaming }: { live: Live; sent: string; cards: Record<string, Card>; streaming: boolean }) {
  const retry = useHer((s) => s.retry);
  const { parts } = live;
  // Only the run still being written reads provisionally and fades in; a run a tool line or a card
  // followed is finished, and reads as settled text.
  const reveal = streaming && !live.done;
  const tail = parts[parts.length - 1];
  // Dots while she writes and no words are arriving yet (before the first, or after a tool line).
  const waiting = streaming && (tail === undefined || tail.kind !== "text" || tail.text.trim() === "");
  return (
    <>
      <PersonLine text={sent} />
      <PartsView parts={parts} cards={cards} cost={live.done ? live.cost : undefined} reveal={reveal} waiting={waiting} />
      {live.error && (
        <div className="her-note" role="alert">
          <p>{live.error}</p>
          <button type="button" className="btn btn-quiet" onClick={() => void retry()}>
            Try again
          </button>
        </div>
      )}
    </>
  );
}

export function Transcript() {
  const status = useHer((s) => s.status);
  const turns = useHer((s) => s.turns);
  const cards = useHer((s) => s.cards);
  const live = useHer((s) => s.live);
  const sent = useHer((s) => s.sent);
  const streaming = useHer((s) => s.streaming);
  const problem = useHer((s) => s.problem);
  const boot = useHer((s) => s.boot);

  const box = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  const onScroll = () => {
    const el = box.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_PX;
  };

  // A new message from the person always brings the view down to it.
  useLayoutEffect(() => {
    if (sent) stick.current = true;
  }, [sent]);

  useLayoutEffect(() => {
    const el = box.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [turns, live, sent, cards]);

  const empty = status === "ready" && turns.length === 0 && !live;

  return (
    <div className="her-transcript" ref={box} onScroll={onScroll} aria-live="polite" aria-busy={streaming}>
      {status === "reading" && <p className="her-quiet">Reading...</p>}
      {status === "offline" && (
        <div className="her-note" role="alert">
          <p>{problem}</p>
          <button type="button" className="btn btn-quiet" onClick={() => void boot()}>
            Try again
          </button>
        </div>
      )}
      {empty && <p className="her-quiet her-empty">Ask Athena anything. In a project, she remembers it there.</p>}
      {turns.map((t) => (
        <TurnView key={t.id} turn={t} cards={cards} />
      ))}
      {live && <LiveView live={live} sent={sent} cards={cards} streaming={streaming} />}
      {status === "ready" && problem && (
        <p className="her-note her-note--quiet" role="status">
          {problem}
        </p>
      )}
    </div>
  );
}
