// "Set up with Athena", the bottom of the Devices level (ADR 0017, portable ADR 0140 WP4).
//
// For a person who is not technical: one press opens a conversation in her window. She speaks first,
// says what she found, explains what Tailscale is before she proposes installing it, and walks the
// steps; every step that changes this computer is a card the person signs. Nothing here decides
// anything: this section only opens the door (`lib/setup.ts`) and says when it could not.

import { useState } from "react";
import { beginSetup } from "../../../lib/setup";
import "./setup.css";

export function SetupSection({ begin = beginSetup }: { begin?: () => Promise<unknown> }) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const press = async () => {
    setBusy(true);
    setProblem(null);
    try {
      await begin();
    } catch (e) {
      setProblem(e instanceof Error ? e.message : "Athena could not open the setup conversation.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="m-setup" aria-labelledby="devices-setup">
      <h3 id="devices-setup" className="m-setup__title">
        Set up with Athena
      </h3>
      <p className="m-muted">
        She walks you through it in her window, one step at a time: the private network that lets your computers and
        phone reach each other, signing in to it, and pairing. Nothing on this computer changes until you sign her
        card for that step.
      </p>
      <div className="m-setup__row">
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void press()}>
          {busy ? "Opening her window..." : "Set up with Athena"}
        </button>
      </div>
      {problem ? (
        <p className="m-setup__problem" role="alert">
          {problem}
        </p>
      ) : null}
    </section>
  );
}
