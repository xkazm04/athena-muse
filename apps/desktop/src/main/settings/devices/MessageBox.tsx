// The box in a paired computer's drawer that sends it a message (ADR 0017). The other computer's Athena
// runs the message as a turn, with her own approvals there, and what she says comes back under the box.
// A pure function of the model: the store holds the conversation and does the sending.

import { useState } from "react";
import type { PeerView } from "../../../lib/fleet";
import { Field, Refusal, type DevicesModel } from "./parts";
import { IDLE } from "./conversation";
import "./talk.css";

export function MessageBox({ model, peer }: { model: DevicesModel; peer: PeerView }) {
  const [draft, setDraft] = useState("");
  const send = model.actions.send;
  const conversation = model.state.conversations?.[peer.peer_id] ?? IDLE;
  if (!send) return null;
  const working = conversation.phase === "sending" || conversation.phase === "waiting";
  const go = () => {
    if (!draft.trim() || working) return;
    void send(peer.peer_id, draft);
    setDraft("");
  };
  return (
    <div className="m-talk" role="group" aria-label={`Send a message to ${peer.name}`}>
      <Field
        label={`Send a message to ${peer.name}`}
        hint="Athena there runs it as her own turn, with her own approvals, and her reply shows here."
        action={
          <button
            type="button"
            className={draft.trim() && !working ? "btn btn-primary" : "btn"}
            disabled={working || !draft.trim()}
            title={working ? "Waiting for the answer..." : draft.trim() ? undefined : "Type a message first."}
            onClick={go}
          >
            Send
          </button>
        }
      >
        {(input) => (
          <input
            {...input}
            className="field"
            value={draft}
            maxLength={8000}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") go();
            }}
          />
        )}
      </Field>
      {conversation.lines.length > 0 || conversation.problem ? (
        <div className="m-talk__log" aria-live="polite">
          {conversation.dropped > 0 ? (
            <p className="m-muted">{`(showing ${conversation.lines.length} of ${conversation.lines.length + conversation.dropped})`}</p>
          ) : null}
          {conversation.lines.map((line, n) => (
            <p key={n} className={`m-talk__line m-talk__line--${line.kind}`}>
              {line.kind === "you" ? `You: ${line.text}` : line.text}
            </p>
          ))}
          {conversation.phase === "waiting" ? (
            <p className="m-muted" role="status">{`${peer.name} is working...`}</p>
          ) : null}
          <Refusal text={conversation.problem} />
        </div>
      ) : null}
    </div>
  );
}
