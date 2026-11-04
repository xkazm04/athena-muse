// The outside agents a person lets into a project (spark agent-leases): each one by the name the
// person gave it, what it says it is, where it stands, the calls it may still run without asking, the
// notes it left, and Revoke, which ends it at once. Before the first answer the list is "checking",
// and a read that failed says so: it is never shown as none. What an agent asks is a card in the
// ordinary stack, named "<name> asks: ..."; nothing here draws one.

import { useEffect, useRef, useState } from "react";
import * as api from "../../../lib/api";
import { AGENTS_MAX, type AgentLease, type AgentNote } from "../../../lib/contract";
import { whenAgo } from "../../../lib/time";
import { reasonOf } from "../../store";
import { Connect } from "./Connect";
import { useAgents } from "./useAgents";
import "./agents.css";
import { notesLine, standingOf, usedLine, usedUp } from "./words";

export function AgentsSection({ spaceId }: { spaceId: string }) {
  const { agents, read, problem, put, revoke, retry } = useAgents(spaceId);
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const live = agents.filter((a) => a.state !== "ended").length;
  const full = live >= AGENTS_MAX;

  const returning = useRef(false);
  const close = () => {
    returning.current = true;
    setOpen(false);
  };
  useEffect(() => {
    // The panel is gone and the button is back in the page: the focus goes where it came from.
    if (open || !returning.current) return;
    returning.current = false;
    opener.current?.focus();
  }, [open]);

  return (
    <section className="plane m-section" data-role="agents">
      <h2 className="m-h2">Agents</h2>
      <p className="m-muted">
        Another assistant, such as one on your computer that writes code, can work in this project through Athena. You see what it does,
        and it asks you first when Athena would.
      </p>
      {read === "checking" && (
        <p className="m-muted" role="status" data-role="checking">
          Checking for agents...
        </p>
      )}
      {read === "failed" && (
        <div className="m-row" data-role="unread">
          <p className="m-error" role="alert">
            Could not read the agents. {problem}
          </p>
          <button type="button" className="btn btn-quiet" onClick={retry}>
            Try again
          </button>
        </div>
      )}
      {read === "ok" &&
        (agents.length ? (
          <ul className="m-agents">
            {agents.map((a) => (
              <AgentRow key={a.id} lease={a} spaceId={spaceId} revoke={() => revoke(a.id)} />
            ))}
          </ul>
        ) : (
          <p className="m-muted" data-role="none">
            No agents yet.
          </p>
        ))}
      {read === "ok" && problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
      {open ? (
        <Connect spaceId={spaceId} onConnected={put} onClosed={close} />
      ) : (
        <div className="m-row">
          <button ref={opener} type="button" className="btn" disabled={full} onClick={() => setOpen(true)}>
            Let an agent use this project
          </button>
        </div>
      )}
      {full && <p className="m-muted">A project lets in at most {AGENTS_MAX} agents at once. Revoke one to let in another.</p>}
    </section>
  );
}

function AgentRow({ lease, spaceId, revoke }: { lease: AgentLease; spaceId: string; revoke: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState("");
  const standing = standingOf(lease);
  const used = usedLine(lease);

  const go = async () => {
    setBusy(true);
    setRefusal("");
    try {
      await revoke();
    } catch (e) {
      setRefusal(reasonOf(e, "Could not end it"));
    }
    setBusy(false);
  };

  return (
    <li className="m-agent" data-role="agent" data-state={lease.state} data-used-up={usedUp(lease) ? "yes" : undefined}>
      <div className="m-agent__head">
        <div className="m-agent__name">
          <p className="m-agent-wrap">
            <strong>{lease.label}</strong>
            {lease.client && <span className="m-muted"> · says it is {lease.client}</span>}
          </p>
          <p className="m-agent__standing" data-role="standing" data-tone={standing.tone}>
            {standing.words}
          </p>
        </div>
        {lease.state !== "ended" && (
          <button type="button" className="btn btn-quiet" disabled={busy} aria-label={`Revoke ${lease.label}`} onClick={() => void go()}>
            {busy ? "Ending..." : "Revoke"}
          </button>
        )}
      </div>
      {used && (
        <p className="m-muted" data-role="used">
          {used}
        </p>
      )}
      {refusal && (
        <p className="m-error" role="alert">
          {refusal}
        </p>
      )}
      <Notes lease={lease} spaceId={spaceId} />
    </li>
  );
}

type NotesView = { at: "closed" } | { at: "reading" } | { at: "read"; notes: AgentNote[] } | { at: "failed"; problem: string };

/** The notes it left, read when opened; their text is shown as text, never as markup. */
function Notes({ lease, spaceId }: { lease: AgentLease; spaceId: string }) {
  const [view, setView] = useState<NotesView>({ at: "closed" });
  const open = view.at !== "closed";

  const toggle = async () => {
    if (open) {
      setView({ at: "closed" });
      return;
    }
    setView({ at: "reading" });
    try {
      const all = (await api.listAgentNotes(spaceId)) ?? [];
      setView({ at: "read", notes: all.filter((n) => n.label === lease.label) });
    } catch (e) {
      setView({ at: "failed", problem: reasonOf(e, "Could not read the notes") });
    }
  };

  return (
    <div className="m-agent-notes" data-role="notes">
      <button type="button" className="btn btn-quiet m-agent-notes__toggle" aria-expanded={open} onClick={() => void toggle()}>
        {notesLine(lease.notes)}
      </button>
      {view.at === "reading" && <p className="m-muted">Reading the notes...</p>}
      {view.at === "failed" && (
        <p className="m-error" role="alert">
          {view.problem}
        </p>
      )}
      {view.at === "read" &&
        (view.notes.length ? (
          <ul className="m-agent-notes__list">
            {view.notes.map((n) => (
              <li key={n.id} className="m-agent-note" data-role="note">
                <p className="m-muted">{whenAgo(n.created)}</p>
                <p className="m-agent-note__text">{n.text}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="m-muted">No notes yet.</p>
        ))}
    </div>
  );
}
