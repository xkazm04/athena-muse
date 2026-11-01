// The small pieces the constellation and the wizard share: the words for a grant and a kind, a
// refusal under the control that made it, a labelled field, a list of facts, and the pending card.

import { useId, type ReactNode } from "react";
import { GRANTS, type DeviceKind, type Grant, type PendingView } from "../../../lib/fleet";
import { clockOf } from "../../../lib/time";
import { grantsOf, isArmed, type DevicesState } from "./store";

/** What the level reads: the store's state, the clock, and the acts. */
export interface DevicesModel {
  state: Pick<DevicesState, "view" | "loaded" | "problem" | "busy" | "errors" | "opened" | "seenAt" | "unticked" | "overlay"> & {
    /** Each paired computer's message box; absent in a model that draws none. */
    conversations?: DevicesState["conversations"];
  };
  now: number;
  actions: Pick<DevicesState, "load" | "rename" | "setBeacon" | "openPairing" | "join" | "toggleGrant" | "answer" | "revoke"> & {
    send?: DevicesState["send"];
  };
}

/** The plain word for each grant, as a person reads it on a card and in a device's details. */
export const GRANT_WORDS: Readonly<Record<Grant, string>> = {
  chat: "talk to Athena here",
  approve: "answer approvals",
  memory: "share memory",
};

export const KIND_WORD = { pc: "Computer", phone: "Phone" } as const;

export const JOIN_WORDS: Readonly<Record<string, string>> = {
  pending: "waiting for the person there to approve",
  claimed: "let in; approve it back here",
  declined: "declined there",
  expired: "the code ran out; ask for a new one",
};

/** What a person answered in the wizard, so the request leaving the list reads as Done. */
export interface Answered {
  pairingId: string;
  name: string;
  choice: "approve" | "decline";
}

/** A refusal in the daemon's words, under the control that made it. */
export function Refusal({ text }: { text: string | undefined | null }) {
  if (!text) return null;
  return (
    <p className="m-error" role="alert">
      {text}
    </p>
  );
}

/** A labelled text box with a hint, a refusal and an optional action beside it. */
export function Field({
  label,
  hint,
  error,
  action,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  action?: ReactNode;
  children: (props: { id: string; "aria-describedby"?: string; "aria-invalid"?: true }) => ReactNode;
}) {
  const id = useId();
  const describe = [hint ? `${id}-hint` : null, error ? `${id}-err` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="m-devices__field">
      <label htmlFor={id} className="m-devices__label">
        {label}
      </label>
      <div className="m-row">
        {children({ id, "aria-describedby": describe, ...(error ? { "aria-invalid": true as const } : {}) })}
        {action}
      </div>
      {hint ? (
        <p id={`${id}-hint`} className="m-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-err`} className="m-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** A definition list of what is known about a device. */
export function Facts({ children }: { children: ReactNode }) {
  return <dl className="m-devices__facts">{children}</dl>;
}

export function Fact({ label, mono, children }: { label: string; mono?: boolean; children: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? "m-mono" : undefined}>{children}</dd>
    </div>
  );
}

/**
 * One pending request: who asks, what it may do, Approve and Decline. The ticks can only be
 * *un*ticked (what the other device asked for is the most it can get), and Approve is armed ARM_MS
 * after the card first showed, so a request that appears under a moving pointer is not approved by
 * the click already on its way. Decline acts at once: saying no is never the dangerous direction.
 */
export function PendingCard({
  model,
  row,
  now = model.now,
  onAnswered,
}: {
  model: DevicesModel;
  row: PendingView;
  now?: number;
  onAnswered?: (answer: Answered) => void;
}) {
  const off = model.state.unticked[row.pairing_id] ?? [];
  const armed = isArmed(model.state.seenAt[row.pairing_id], now);
  const busy = Boolean(model.state.busy[row.pairing_id]);
  const granted = grantsOf(row, off);
  const who = row.pair_back
    ? `${row.name}, which this computer joined, asks to be let in here too`
    : `${row.name} asks to be let in`;
  const answer = (choice: "approve" | "decline") => {
    onAnswered?.({ pairingId: row.pairing_id, name: row.name, choice });
    void model.actions.answer(row.pairing_id, choice);
  };
  const blocked = busy
    ? "Answering..."
    : !armed
      ? "Read the request first; Approve wakes in a moment."
      : granted.length === 0
        ? "Leave at least one thing ticked, or decline."
        : undefined;
  return (
    <div className="m-devices__card" data-armed={armed ? "1" : undefined}>
      <p className="m-devices__ask">{who}</p>
      <p className="m-muted">
        {KIND_WORD[row.kind]}. {row.address ? `Asking from ${row.address}.` : "Its address unknown."} The request
        lapses at {clockOf(row.expires_at)} if nobody answers.
      </p>
      {row.replaces && (
        <p className="m-muted">
          Approving replaces your paired device {row.replaces.name}: its access ends and this one takes its place.
        </p>
      )}
      <div className="m-devices__ticks" role="group" aria-label={`What ${row.name} may do`}>
        {GRANTS.filter((g) => row.requested_grants.includes(g)).map((grant) => (
          <button
            key={grant}
            type="button"
            role="checkbox"
            aria-checked={!off.includes(grant)}
            className="m-devices__tick"
            onClick={() => model.actions.toggleGrant(row.pairing_id, grant)}
          >
            {GRANT_WORDS[grant]}
          </button>
        ))}
      </div>
      <div className="m-row">
        <button type="button" className="btn btn-primary" disabled={blocked !== undefined} onClick={() => answer("approve")}>
          Approve
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => answer("decline")}>
          Decline
        </button>
      </div>
      {blocked && !busy ? <p className="m-muted">{blocked}</p> : null}
      <Refusal text={model.state.errors[row.pairing_id]} />
    </div>
  );
}

/** A computer or a phone, drawn small. */
export function DeviceGlyph({ kind }: { kind: DeviceKind }) {
  return (
    <svg className="m-cnode__glyph" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      {kind === "pc" ? (
        <>
          <rect x="4" y="6" width="24" height="16" rx="2.5" />
          <path d="M12 27h8M16 22v5" />
        </>
      ) : (
        <>
          <rect x="10" y="3.5" width="12" height="25" rx="3" />
          <path d="M14.5 24.5h3" />
        </>
      )}
    </svg>
  );
}
