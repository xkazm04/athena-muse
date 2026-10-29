import { useState } from "react";
import { ChoreDetailView } from "../main/chores/ChoreScene";
import { Catalogue } from "../main/chores/Chores";
import { FIXTURE_CHORES, fixtureDetail } from "../main/chores/fixtures";
import type { Load } from "../main/store";
import { StageSection } from "./StageSection";
import { Backdrop, Seal, SPEED_REST, SPEED_WORKING, applyTheme, type SealState, type ThemeChoice } from "../theme";

const STATES: SealState[] = ["rest", "working", "waiting", "signed"];

const SWATCHES = [
  "background",
  "card-bg",
  "card-raised",
  "recessed",
  "foreground",
  "muted-foreground",
  "muted",
  "btn-primary",
  "primary",
  "accent",
  "role-human",
  "role-agent",
  "status-success",
  "status-warning",
  "status-error",
  "status-info",
];

const TRANSCRIPT: { who: "person" | "athena"; text: string }[] = [
  { who: "person", text: "Remind me what we decided about the invoice run." },
  { who: "athena", text: "You chose to send them on the first of the month. I can draft this month's batch." },
  { who: "person", text: "Yes, draft it." },
  { who: "athena", text: "I have one thing for you to sign before I send anything." },
];

export function Preview() {
  const [state, setState] = useState<SealState>("rest");
  const [working, setWorking] = useState(false);
  const [theme, setTheme] = useState<ThemeChoice>("auto");

  const pick = (t: ThemeChoice) => {
    setTheme(t);
    applyTheme(t);
  };
  const cycle = () => setState((s) => STATES[(STATES.indexOf(s) + 1) % STATES.length]!);

  return (
    <main className="pv">
      <header className="pv-head">
        <h1>Loop Tide</h1>
        <div className="pv-row" role="group" aria-label="Theme">
          {(["auto", "dark", "light"] as const).map((t) => (
            <button
              key={t}
              type="button"
              className={t === theme ? "btn btn-primary" : "btn"}
              aria-pressed={t === theme}
              onClick={() => pick(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </header>

      <section className="pv-section">
        <h2>Palette</h2>
        <div className="pv-swatches">
          {SWATCHES.map((name) => (
            <div key={name} className="pv-swatch">
              <span className="pv-chip" style={{ background: `var(--${name})` }} />
              <code>--{name}</code>
            </div>
          ))}
        </div>
      </section>

      <section className="pv-section">
        <h2>Seal</h2>
        <div className="pv-row pv-seals">
          {STATES.map((s) => (
            <figure key={s} className="pv-seal">
              <Seal state={s} count={s === "waiting" ? 2 : 0} label={`Athena, ${s}`} />
              <figcaption>{s}</figcaption>
            </figure>
          ))}
          <figure className="pv-seal">
            <Seal state={state} count={state === "waiting" ? 3 : 0} label={`Athena, ${state}`} onClick={cycle} />
            <figcaption>click to cycle: {state}</figcaption>
          </figure>
        </div>
      </section>

      <section className="pv-section">
        <h2>Her window (400 by 620)</h2>
        <div className="pv-desk">
          <div className="coat pv-coat">
            <div className="pv-coat-head">
              <Seal state={state} size={44} label="Athena" />
              <span>Athena</span>
              <span className="badge" data-tone="human">
                1 waiting
              </span>
            </div>
            <ol className="pv-transcript">
              {TRANSCRIPT.map((t, i) => (
                <li key={i} data-who={t.who}>
                  {t.text}
                </li>
              ))}
            </ol>
            <div className="pv-coat-foot">
              <input className="field" placeholder="Say something" aria-label="Say something" />
              <button type="button" className="btn btn-primary">
                Send
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="pv-section">
        <h2>Backdrop</h2>
        <div className="pv-backdrop">
          <Backdrop speed={working ? SPEED_WORKING : SPEED_REST} />
          <div className="pv-backdrop-bar">
            <button type="button" className="btn" onClick={() => setWorking((w) => !w)}>
              speed: {working ? "working" : "rest"}
            </button>
          </div>
        </div>
      </section>

      <ChoresSection />

      <StageSection />

      <section className="pv-section">
        <h2>Primitives</h2>
        <div className="pv-row">
          <button type="button" className="btn">
            Button
          </button>
          <button type="button" className="btn btn-primary">
            Primary
          </button>
          <button type="button" className="btn btn-quiet">
            Quiet
          </button>
          <button type="button" className="btn" disabled>
            Disabled
          </button>
        </div>
        <div className="pv-row">
          <span className="badge">plain</span>
          <span className="badge" data-tone="info">
            info
          </span>
          <span className="badge" data-tone="success">
            done
          </span>
          <span className="badge" data-tone="warning">
            check
          </span>
          <span className="badge" data-tone="error">
            failed
          </span>
          <span className="badge" data-tone="human">
            waiting on you
          </span>
        </div>
        <div className="pv-fields">
          <input className="field" placeholder="A line of text" aria-label="A line of text" />
          <textarea className="field" rows={3} placeholder="A longer note" aria-label="A longer note" />
        </div>
        <div className="plane">
          <strong>A plane</strong>
          <p>
            Cards sit on planes. The pink is the person&apos;s alone; green, amber and red only ever mean status.
          </p>
        </div>
      </section>
    </main>
  );
}

const CHORE_STATES: { name: string; load: Load; empty?: boolean }[] = [
  { name: "ready", load: "ready" },
  { name: "reading", load: "reading" },
  { name: "empty", load: "ready", empty: true },
  { name: "problem", load: "problem" },
];

/** The Chores scene on fixture data: the catalogue in each state, and one chore opened from it. */
function ChoresSection() {
  const [state, setState] = useState(CHORE_STATES[0]!);
  const [open, setOpen] = useState(FIXTURE_CHORES[1]!.id);
  const chore = FIXTURE_CHORES.find((c) => c.id === open) ?? FIXTURE_CHORES[0]!;
  return (
    <section className="pv-section" aria-labelledby="pv-chores">
      <h2 id="pv-chores">Chores (fixture data, not bench results)</h2>
      <div className="pv-row" role="group" aria-label="Catalogue state">
        {CHORE_STATES.map((s) => (
          <button
            key={s.name}
            type="button"
            className={s === state ? "btn btn-primary" : "btn"}
            aria-pressed={s === state}
            onClick={() => setState(s)}
          >
            {s.name}
          </button>
        ))}
      </div>
      <Catalogue
        chores={state.empty ? [] : FIXTURE_CHORES}
        load={state.load}
        problem="Athena's background service is not reachable"
        onRetry={() => setState(CHORE_STATES[0]!)}
        onOpen={setOpen}
      />
      <div className="pv-chore">
        <ChoreDetailView detail={fixtureDetail({ chore })} />
      </div>
    </section>
  );
}
