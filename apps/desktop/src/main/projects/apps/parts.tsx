// Pieces shared by a project's apps and this computer's offered apps: the status badge, the tool list
// with each tool's mark, and removal confirmed in place.

import { useState } from "react";
import type { AppStatus, AppTool } from "../../../lib/contract";
import { reasonOf } from "../../store";
import { ACCESS_WORDS, statusOf } from "./words";

export function StatusBadge({ status }: { status: AppStatus }) {
  const state = statusOf(status);
  return (
    <span className="badge" data-tone={state.tone} data-status={status}>
      {state.words}
    </span>
  );
}

/** Each tool with what it does and whether she uses it on her own or asks first. */
export function ToolList({ tools }: { tools: AppTool[] }) {
  if (!tools.length) return null;
  return (
    <ul className="m-tools">
      {tools.map((t) => (
        <li key={t.name} className="m-tool" data-access={t.access}>
          <span className="m-mono">{t.name}</span>
          <span className="badge" data-tone={t.access === "gated" ? "warning" : "info"}>
            {ACCESS_WORDS[t.access]}
          </span>
          {t.description && <span className="m-muted m-tool__what">{t.description}</span>}
        </li>
      ))}
    </ul>
  );
}

/** "Remove", then a second press that says what goes; no browser dialog. */
export function RemoveInPlace({ label, remove, what }: { label: string; what: string; remove: () => Promise<unknown> }) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  const go = async () => {
    setBusy(true);
    setProblem("");
    try {
      await remove();
    } catch (e) {
      setProblem(reasonOf(e, "Could not remove it"));
      setBusy(false);
    }
  };

  if (!asking) {
    return (
      <button type="button" className="btn btn-quiet" aria-label={`Remove ${label}`} onClick={() => setAsking(true)}>
        Remove
      </button>
    );
  }
  return (
    <div className="m-confirm" role="group" aria-label={`Confirm removing ${label}`}>
      <p>{what}</p>
      <div className="m-row">
        <button type="button" className="btn m-btn-danger" disabled={busy} onClick={() => void go()}>
          {busy ? "Removing..." : `Remove ${label}`}
        </button>
        <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => setAsking(false)}>
          Keep it
        </button>
      </div>
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </div>
  );
}
