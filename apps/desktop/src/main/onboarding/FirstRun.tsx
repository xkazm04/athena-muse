import { useState, type ReactNode } from "react";
import { Backdrop, Seal } from "../../theme";
import { openExternal, toggleAthena } from "../../lib/windows";
import { useMain } from "../store";
import { Mark, Rail } from "../shell/Depth";
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

  // After the variant's waking screen (ADR 0016): the mark and the rail, her seal large at the left with
  // a line about her, and the step at the right under its numbered pills and an eyebrow.
  return (
    <div className="m-firstrun m-wake">
      <Backdrop />
      <header className="m-bar m-wake__bar">
        <span className="m-bar__brand">
          <Mark />
          <span>Athena</span>
        </span>
      </header>
      <Rail depth={0} />
      <main className="m-wake__stage">
        {step === "welcome" && <Welcome onNext={() => setStep("connect")} onSkip={skip} />}
        {step === "connect" && <Connect onConnected={() => setStep("ready")} onSkip={skip} />}
        {step === "ready" && <Ready onDone={onDone} />}
      </main>
    </div>
  );
}

const STEPS: { key: Step; label: string; eyebrow: string }[] = [
  { key: "welcome", label: "Meet", eyebrow: "Step 1 of 3 · Meet her" },
  { key: "connect", label: "Connect", eyebrow: "Step 2 of 3 · Her mind" },
  { key: "ready", label: "Ready", eyebrow: "Step 3 of 3 · Ready" },
];

/** The step's head: the numbered pills, the current one outlined, and its eyebrow. */
function StepHead({ at }: { at: Step }) {
  const i = STEPS.findIndex((s) => s.key === at);
  return (
    <>
        <ol className="m-wake__steps" aria-label="Steps">
          {STEPS.map((s, n) => (
            <li key={s.key} aria-current={n === i ? "step" : undefined} data-done={n < i ? "true" : undefined}>
              <span className="m-wake__n" aria-hidden="true">
                {n + 1}
              </span>
              {s.label}
            </li>
          ))}
        </ol>
        <p className="eyebrow">{STEPS[i]!.eyebrow}</p>
    </>
  );
}

/** Her seal large at the left, and a line about her. */
function Art({ seal, line, sub }: { seal: ReactNode; line: string; sub: string }) {
  return (
    <aside className="m-wake__art">
      <div className="m-wake__seal">{seal}</div>
      <p className="marquee m-wake__line">{line}</p>
      <p className="m-wake__sub">{sub}</p>
    </aside>
  );
}

function Welcome({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  return (
    <>
      <Art seal={<Seal state="rest" size={280} label="Athena" />} line="She is waiting to meet you." sub="Nothing is set yet; each step lights a part of her." />
      <section className="m-step" aria-labelledby="fr-welcome">
        <StepHead at="welcome" />
        <h1 id="fr-welcome" className="m-step__title marquee">
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
    </>
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
    <>
      <Art
        seal={<Seal state={sealFor(state.phase)} size={280} label="Athena" />}
        line={state.phase === "ok" ? "She has a mind." : "She has no mind yet."}
        sub="Your key stays on this computer; every call is on your bill, and estimated on screen."
      />
      <section className="m-step" aria-labelledby="fr-connect">
        <StepHead at="connect" />
        <h1 id="fr-connect" className="m-step__title marquee">
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
    </>
  );
}

function Ready({ onDone }: { onDone: (toProjects: boolean) => void }) {
  const navigate = useMain((s) => s.navigate);
  const describe = () => {
    navigate({ view: "stage", id: null });
    onDone(false);
  };
  return (
    <>
      <Art seal={<Seal state="signed" size={280} label="Athena, connected" />} line="She is connected." sub="What she learns stays in the project it belongs to." />
      <section className="m-step" aria-labelledby="fr-ready">
        <StepHead at="ready" />
        <h1 id="fr-ready" className="m-step__title marquee">
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
    </>
  );
}
