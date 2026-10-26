import { useLayoutEffect, useRef } from "react";
import * as api from "../lib/api";
import type { Card, Turn } from "../lib/contract";
import { CardView } from "../ui";
import { useHer, type Live } from "./store";

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
      <CardView card={card} onDecide={(verdict) => api.decide(card.id, verdict)} onResolved={decided} />
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

function AthenaLine({ text, cost, writing }: { text: string; cost?: number; writing?: boolean }) {
  return (
    <div className="her-line her-line--athena">
      {text ? (
        <p className="her-say">{text}</p>
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
  const card = turn.card_id ? cards[turn.card_id] : undefined;
  return (
    <>
      <AthenaLine text={turn.text} cost={turn.cost_usd} />
      {card && <InlineCard card={card} />}
    </>
  );
}

function LiveView({ live, sent, cards, streaming }: { live: Live; sent: string; cards: Record<string, Card>; streaming: boolean }) {
  const retry = useHer((s) => s.retry);
  return (
    <>
      <PersonLine text={sent} />
      {live.items.flatMap((i, n) =>
        i.kind === "tool"
          ? [
              <p key={n} className="her-tool">
                {i.label}
              </p>,
            ]
          : [],
      )}
      <AthenaLine text={live.text} cost={live.done ? live.cost : undefined} writing={streaming} />
      {live.items.map((i) => {
        const card = i.kind === "card" ? cards[i.id] : undefined;
        return card ? <InlineCard key={card.id} card={card} /> : null;
      })}
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
