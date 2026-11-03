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

/** Each action's heading on its card, in plain words (the book's receipts say them too). */
export const ACTION_WORDS: Record<Card["action"], string> = {
  recall: "Look through memory",
  remember: "Remember",
  propose_brief: "Change the brief",
  add_app: "Add an app",
  forget: "Forget a memory",
  portal_read: "Read a page",
  portal_act: "Act on a page",
  sketch: "Draw the sketch",
  ask: "Ask a question",
  // Read-only, offered to outside agents only (ADR 0021); never filed as a card, named for completeness.
  show_report: "Show the project's report",
  // Read-only report parts in a chat reply (ADR 0022); never filed as a card, named for completeness.
  show_blocks: "Show parts of the report",
  twin_send: "Send this email",
  twin_note: "Write this to Notion",
  // Her browser (ADR 0013): a read is a card only on a site that is not one of the project's apps.
  page_open: "Open a page in her browser",
  page_read: "Read a page in her browser",
  page_find: "Look over a page in her browser",
  page_wait: "Wait on a page in her browser",
  page_scroll: "Scroll a page in her browser",
  tabs_read: "Look at her browser's tabs",
  file_list: "Look at the project's files",
  page_click: "Click on a page",
  page_fill: "Type on a page",
  page_select: "Choose on a page",
  page_submit: "Send a form",
  page_upload: "Upload a file",
  page_download: "Download a file",
  wheel_handoff: "Take over her browser",
  setup_read: "Look at the private network",
  setup_act: "Set up this computer",
  // A project's records (business Phase 1): a find is kept at once, anything else waits here.
  record_list: "Look through what the project keeps",
  record_put: "Keep this in the project",
  twin_send_web: "Send this message",
};

/** A twin's draft (ADR 0009) carries its text, which the person may rewrite before signing. */
function draftText(card: Card): string | null {
  if (card.action !== "twin_send" && card.action !== "twin_note" && card.action !== "twin_send_web") return null;
  return typeof card.args.text === "string" ? card.args.text : null;
}

/** Where a twin's message on a web channel goes (business Phase 2), in plain words. A comment names
 *  its track as the card's label does ("Comment on <track>"). */
export function webChannelLine(card: Card): string | null {
  if (card.action !== "twin_send_web") return null;
  const channel = card.args.channel;
  if (channel === "mail_web") return "By mail in her browser";
  if (channel === "bio") return "Through their bio link - you will send it yourself";
  if (channel === "comment") {
    const track = card.label.replace(/^Comment on\s+/i, "").trim();
    const named = track && track !== card.label ? track : typeof card.args.to === "string" ? card.args.to : "their track";
    return `As a comment on ${named}`;
  }
  return null;
}

/** A card Athena filed: nothing happens until the person signs it, and it runs once. A twin's draft
 *  shows its text in a field: signing sends the person's words only when they changed them. */
export function CardView({ card, onDecide, onResolved, where }: CardViewProps) {
  const [busy, setBusy] = useState<Verdict | null>(null);
  const [problem, setProblem] = useState("");
  const drafted = draftText(card);
  const web = webChannelLine(card);
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
        <span className="card-action">{ACTION_WORDS[card.action]}</span>
        {where && <span className="card-where">{where}</span>}
      </header>
      <p className="card-label">{card.label}</p>
      {web && (
        <p className="card-channel" data-role="web-channel" data-channel={String(card.args.channel)}>
          {web}
        </p>
      )}
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
            className="btn card-sign"
            disabled={busy !== null || (drafted !== null && text.trim() === "")}
            onClick={() => decide("approve")}
          >
            {busy === "approve" ? "Signing..." : changed ? "Sign your words" : "Sign"}
          </button>
          <button type="button" className="btn card-decline" disabled={busy !== null} onClick={() => decide("decline")}>
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
