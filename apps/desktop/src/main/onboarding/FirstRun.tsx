import { useState } from "react";
import { Backdrop, Seal } from "../../theme";
import { openExternal, toggleAthena } from "../../lib/windows";
import { useMain } from "../store";
import { DESCRIBE_A_NEED } from "../stage/door";
import { ProbeLine, sealFor, useProbe } from "./probe";

export const SKIP_KEY = "athena.firstRun.skipped";
export const META_DEV_URL = "https://dev.meta.ai";

/** A per-device convenience: the person chose to go on without a key. Storage may be blocked. */
export function readSkipped(): boolean {
  try {
    return localStorage.getItem(SKIP_KEY) === "1";
  } catch {
    return false;
  }
}

function markSkipped(): void {
  try {
    localStorage.setItem(SKIP_KEY, "1");
  } catch {
    // without storage the first run simply shows again next time
  }
}

type Step = "welcome" | "connect" | "ready";

export interface FirstRunProps {
  /** Leaves the first run; `toProjects` when the person asked for their projects. */
  onDone: (toProjects: boolean) => void;
}

export function FirstRun({ onDone }: FirstRunProps) {
  const [step, setStep] = useState<Step>("welcome");

  const skip = () => {
    markSkipped();
    onDone(true);
  };

  return (
    <div className="m-firstrun">
      <Backdrop />
      <main className="m-firstrun__stage">
        {step === "welcome" && <Welcome onNext={() => setStep("connect")} onSkip={skip} />}
        {step === "connect" && <Connect onConnected={() => setStep("ready")} onSkip={skip} />}
        {step === "ready" && <Ready onDone={onDone} />}
      </main>
    </div>
  );
}

function Welcome({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  return (
    <section className="plane m-step" aria-labelledby="fr-welcome">
      <Seal state="rest" size={96} label="Athena" />
      <h1 id="fr-welcome" className="m-step__title">
        Meet Athena
      </h1>
      <p className="m-step__lead">
        Athena works for you, here on your computer. She thinks with Meta&apos;s Muse, and you hold the key and the
        bill. Nothing she does to your work happens without your signature.
      </p>
      <div className="m-step__actions">
        <button type="button" className="btn btn-primary" onClick={onNext}>
          Connect Muse
        </button>
        <button type="button" className="btn btn-quiet" onClick={onSkip}>
          Continue without a key
        </button>
      </div>
    </section>
  );
}

function Connect({ onConnected, onSkip }: { onConnected: () => void; onSkip: () => void }) {
  const [key, setKey] = useState("");
  const { state, check, removeKey } = useProbe();
  const checking = state.phase === "checking";
  const failed = state.phase === "invalid" || state.phase === "network" || state.phase === "failed";
  // A failed probe after a save leaves the key kept; "Try again" re-asks Muse without re-saving.
  const saved = useMain((s) => s.engine?.key === "file");

  const submit = async () => {
    const trimmed = key.trim();
    if (!trimmed) return;
    await check(trimmed);
  };

  return (
    <section className="plane m-step" aria-labelledby="fr-connect">
      <Seal state={sealFor(state.phase)} size={72} label="Athena" />
      <h1 id="fr-connect" className="m-step__title">
        Connect Muse
      </h1>
      <ol className="m-steps">
        <li>
          <span className="m-steps__n" aria-hidden="true">
            1
          </span>
          <div>
            Open Meta&apos;s developer page.{" "}
            <button type="button" className="btn btn-quiet m-inline" onClick={() => void openExternal(META_DEV_URL)}>
              Open the page
            </button>
            <div className="m-muted m-mono">{META_DEV_URL}</div>
          </div>
        </li>
        <li>
          <span className="m-steps__n" aria-hidden="true">
            2
          </span>
          <div>Create an API key there.</div>
        </li>
        <li>
          <span className="m-steps__n" aria-hidden="true">
            3
          </span>
          <div>Paste it here.</div>
        </li>
      </ol>
      <form
        className="m-row"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <label className="m-sr" htmlFor="fr-key">
          Muse key
        </label>
        <input
          id="fr-key"
          className="field"
          type="password"
          autoComplete="off"
          spellCheck={false}
          placeholder="Paste your key"
          value={key}
          disabled={checking}
          onChange={(e) => setKey(e.target.value)}
        />
        <button type="submit" className="btn btn-primary" disabled={!key.trim() || checking}>
          Check the key
        </button>
      </form>
      <ProbeLine state={state} />
      {failed && saved && (
        <div className="m-step__actions">
          <button type="button" className="btn" onClick={() => void check()}>
            Try again
          </button>
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => {
              void removeKey();
              setKey("");
            }}
          >
            Remove the key
          </button>
        </div>
      )}
      {state.phase === "ok" && (
        <div className="m-step__actions">
          <button type="button" className="btn btn-primary" onClick={onConnected}>
            Continue
          </button>
        </div>
      )}
      {state.phase !== "ok" && (
        <p className="m-muted">
          <button type="button" className="m-link" onClick={onSkip}>
            Continue without a key
          </button>{" "}
          - Athena runs simulated, and says so.
        </p>
      )}
    </section>
  );
}

function Ready({ onDone }: { onDone: (toProjects: boolean) => void }) {
  const navigate = useMain((s) => s.navigate);
  const describe = () => {
    navigate({ view: "stage", id: null });
    onDone(false);
  };
  return (
    <section className="plane m-step" aria-labelledby="fr-ready">
      <Seal state="signed" size={96} label="Athena, connected" />
      <h1 id="fr-ready" className="m-step__title">
        Athena is connected
      </h1>
      <p className="m-step__lead">
        Tell her a chore you want handed off and watch her sketch it, or talk to her in her own window. Your projects
        keep what she learns apart.
      </p>
      <div className="m-step__actions">
        <button type="button" className="btn btn-primary" onClick={describe}>
          {DESCRIBE_A_NEED}
        </button>
        <button type="button" className="btn" onClick={() => void toggleAthena()}>
          Open her window
        </button>
        <button type="button" className="btn" onClick={() => onDone(true)}>
          Go to your projects
        </button>
      </div>
    </section>
  );
}
