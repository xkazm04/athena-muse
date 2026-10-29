import { useState } from "react";
import type { Card, DecisionEdit, Verdict } from "../lib/contract";
import { DaemonError } from "../lib/daemon";
import "./ui.css";

export interface CardViewProps {
  card: Card;
  /** Sends the verdict (usually `api.decide`), with the person's words when they changed a twin's
   *  draft; the answer is the resolved card. */
  onDecide: (verdict: Verdict, edited?: DecisionEdit) => Promise<Card>;
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
  twin_send: "Send this email",
  twin_note: "Write this to Notion",
};

/** A twin's draft (ADR 0009) carries its text, which the person may rewrite before signing. */
function draftText(card: Card): string | null {
  if (card.action !== "twin_send" && card.action !== "twin_note") return null;
  return typeof card.args.text === "string" ? card.args.text : null;
}

/** A card Athena filed: nothing happens until the person signs it, and it runs once. A twin's draft
 *  shows its text in a field: signing sends the person's words only when they changed them. */
export function CardView({ card, onDecide, onResolved, where }: CardViewProps) {
  const [busy, setBusy] = useState<Verdict | null>(null);
  const [problem, setProblem] = useState("");
  const drafted = draftText(card);
  const [text, setText] = useState(drafted ?? "");
  const changed = drafted !== null && text.trim() !== drafted.trim();
  const waiting = card.state === "waiting";

  const decide = async (verdict: Verdict) => {
    setBusy(verdict);
    setProblem("");
    try {
      const edited = verdict === "approve" && changed ? { text: text.trim() } : undefined;
      // Decided first: `onResolved?.(await ...)` would skip the call itself when there is no listener.
      const resolved = await (edited ? onDecide(verdict, edited) : onDecide(verdict));
      onResolved?.(resolved);
    } catch (e) {
      setProblem(e instanceof DaemonError ? e.reason : "Could not send your answer");
    } finally {
      setBusy(null);
    }
  };

  const fieldId = `card-text-${card.id}`;
  const noun = card.action === "twin_note" ? "note" : "message";

  return (
    <article className={`card card--${card.state}`} aria-label={`Card: ${card.label}`}>
      <header className="card-head">
        <span className="badge" data-tone={waiting ? "human" : card.state === "approved" ? "success" : undefined}>
          {waiting ? "Needs your signature" : card.state === "approved" ? "Signed, ran once" : "Declined"}
        </span>
        <span className="card-action">{ACTION[card.action]}</span>
        {where && <span className="card-where">{where}</span>}
      </header>
      <p className="card-label">{card.label}</p>
      {drafted !== null &&
        (waiting ? (
          <>
            <label className="card-action" htmlFor={fieldId}>
              {changed ? `Your words: they are sent as the ${noun}` : `The ${noun}: change it if you like`}
            </label>
            <textarea
              id={fieldId}
              className="field"
              rows={Math.min(10, Math.max(3, text.split("\n").length + 1))}
              value={text}
              disabled={busy !== null}
              onChange={(e) => setText(e.target.value)}
            />
            {changed && (
              <button type="button" className="btn btn-quiet" disabled={busy !== null} onClick={() => setText(drafted)}>
                Put its words back
              </button>
            )}
          </>
        ) : (
          <p className="card-label">{drafted}</p>
        ))}
      {waiting && (
        <div className="card-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy !== null || (drafted !== null && text.trim() === "")}
            onClick={() => decide("approve")}
          >
            {busy === "approve" ? "Signing..." : changed ? "Sign your words" : "Sign"}
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
