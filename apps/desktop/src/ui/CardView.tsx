import { useState } from "react";
import type { Card, Verdict } from "../lib/contract";
import { DaemonError } from "../lib/daemon";
import "./ui.css";

export interface CardViewProps {
  card: Card;
  /** Sends the verdict (usually `api.decide`); the answer is the resolved card. */
  onDecide: (verdict: Verdict) => Promise<Card>;
  onResolved?: (card: Card) => void;
  /** Project name to show, when the card is listed outside its conversation. */
  where?: string;
}

const ACTION: Record<Card["action"], string> = {
  recall: "Look through memory",
  remember: "Remember",
  propose_brief: "Change the brief",
  add_app: "Add an app",
  forget: "Forget a memory",
  portal_read: "Read a page",
  portal_act: "Act on a page",
  sketch: "Draw the sketch",
  ask: "Ask a question",
};

/** A card Athena filed: nothing happens until the person signs it, and it runs once. */
export function CardView({ card, onDecide, onResolved, where }: CardViewProps) {
  const [busy, setBusy] = useState<Verdict | null>(null);
  const [problem, setProblem] = useState("");

  const decide = async (verdict: Verdict) => {
    setBusy(verdict);
    setProblem("");
    try {
      onResolved?.(await onDecide(verdict));
    } catch (e) {
      setProblem(e instanceof DaemonError ? e.reason : "Could not send your answer");
    } finally {
      setBusy(null);
    }
  };

  return (
    <article className={`card card--${card.state}`} aria-label={`Card: ${card.label}`}>
      <header className="card-head">
        <span className="badge" data-tone={card.state === "waiting" ? "human" : card.state === "approved" ? "success" : undefined}>
          {card.state === "waiting" ? "Needs your signature" : card.state === "approved" ? "Signed, ran once" : "Declined"}
        </span>
        <span className="card-action">{ACTION[card.action]}</span>
        {where && <span className="card-where">{where}</span>}
      </header>
      <p className="card-label">{card.label}</p>
      {card.state === "waiting" && (
        <div className="card-actions">
          <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={() => decide("approve")}>
            {busy === "approve" ? "Signing..." : "Sign"}
          </button>
          <button type="button" className="btn btn-quiet" disabled={busy !== null} onClick={() => decide("decline")}>
            {busy === "decline" ? "Declining..." : "Decline"}
          </button>
        </div>
      )}
      {problem && (
        <p className="card-problem" role="alert">
          {problem}
        </p>
      )}
    </article>
  );
}
