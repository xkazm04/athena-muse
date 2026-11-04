// Adding an app, kind first (ADR 0025): the person picks what it is, then fills that kind's short
// form. On submit the app is wired, then looked at once, and the screen says what was found: its
// tools, or why it could not be reached. A refusal stays in place beside the form.

import { useId, useState } from "react";
import type { App, AppKind, AppNew } from "../../../lib/contract";
import { reasonOf } from "../../store";
import { ToolList } from "./parts";
import "./apps.css";
import { EMPTY_FORM, KIND_HINTS, KIND_WORDS, bodyOf, isProcess, ready, statusOf, type AppForm } from "./words";

type Phase = { at: "closed" } | { at: "choosing" } | { at: "form"; kind: AppKind } | { at: "adding"; kind: AppKind };

export interface AddAppProps {
  kinds: readonly AppKind[];
  /** Device level: the form carries the offer switch, and an output folder for both program kinds. */
  device?: boolean;
  /** At the cap: nothing more may be added. */
  full?: boolean;
  add: (body: AppNew) => Promise<App>;
  probe: (appId: string) => Promise<App>;
  /** Called once the app is wired (and again once it was looked at). */
  onAdded?: (app: App) => void;
}

export function AddApp({ kinds, device = false, full = false, add, probe, onAdded }: AddAppProps) {
  const [phase, setPhase] = useState<Phase>({ at: "closed" });
  const [form, setForm] = useState<AppForm>(EMPTY_FORM);
  const [problem, setProblem] = useState("");
  const [looking, setLooking] = useState(false);
  const [found, setFound] = useState<{ app: App; problem: string } | null>(null);

  const reset = () => {
    setPhase({ at: "closed" });
    setForm(EMPTY_FORM);
    setProblem("");
  };

  const submit = async (kind: AppKind) => {
    setProblem("");
    setPhase({ at: "adding", kind });
    let app: App;
    try {
      app = await add(bodyOf(kind, form, device));
    } catch (e) {
      setProblem(reasonOf(e, "Could not add the app"));
      setPhase({ at: "form", kind });
      return;
    }
    onAdded?.(app);
    reset();
    setFound({ app, problem: "" });
    setLooking(true);
    try {
      const looked = await probe(app.app_id);
      onAdded?.(looked);
      setFound({ app: looked, problem: "" });
    } catch (e) {
      setFound({ app, problem: reasonOf(e, "Athena could not look at it") });
    }
    setLooking(false);
  };

  return (
    <div className="m-addapp" data-role="add-app">
      {found && <Found app={found.app} problem={found.problem} looking={looking} onDone={() => setFound(null)} />}
      {phase.at === "closed" && !found && (
        <div className="m-row">
          <button type="button" className="btn" disabled={full} onClick={() => setPhase({ at: "choosing" })}>
            Add app
          </button>
        </div>
      )}
      {phase.at === "choosing" && <Chooser kinds={kinds} onPick={(kind) => setPhase({ at: "form", kind })} onCancel={reset} />}
      {(phase.at === "form" || phase.at === "adding") && (
        <KindForm
          kind={phase.kind}
          device={device}
          form={form}
          busy={phase.at === "adding"}
          onChange={(patch) => setForm((f) => ({ ...f, ...patch }))}
          onSubmit={() => void submit(phase.kind)}
          onBack={() => {
            setProblem("");
            setPhase({ at: "choosing" });
          }}
        />
      )}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </div>
  );
}

function Chooser({ kinds, onPick, onCancel }: { kinds: readonly AppKind[]; onPick: (k: AppKind) => void; onCancel: () => void }) {
  return (
    <div className="m-kinds" role="group" aria-label="What kind of app is it?">
      <p className="m-label">What kind of app is it?</p>
      <ul className="m-kinds__list">
        {kinds.map((k) => (
          <li key={k}>
            <button type="button" className="m-kind" data-kind={k} onClick={() => onPick(k)}>
              <span className="m-kind__name">{KIND_WORDS[k]}</span>
              <span className="m-muted">{KIND_HINTS[k]}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="m-row">
        <button type="button" className="btn btn-quiet" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

interface KindFormProps {
  kind: AppKind;
  device: boolean;
  form: AppForm;
  busy: boolean;
  onChange: (patch: Partial<AppForm>) => void;
  onSubmit: () => void;
  onBack: () => void;
}

function KindForm({ kind, device, form, busy, onChange, onSubmit, onBack }: KindFormProps) {
  const id = useId();
  const field = (name: string) => `${id}-${name}`;
  return (
    <form
      className="m-appform"
      aria-label={KIND_WORDS[kind]}
      onSubmit={(e) => {
        e.preventDefault();
        if (ready(kind, form)) onSubmit();
      }}
    >
      <p className="m-label">{KIND_WORDS[kind]}</p>
      {kind === "mcp_stdio" ? (
        <>
          <label htmlFor={field("command")}>Command</label>
          <p className="m-muted" id={field("command-help")}>
            One part per line, the program first. A single line is split at its spaces.
          </p>
          <textarea
            id={field("command")}
            className="field m-mono"
            rows={3}
            aria-describedby={field("command-help")}
            value={form.command}
            disabled={busy}
            onChange={(e) => onChange({ command: e.target.value })}
          />
        </>
      ) : (
        <>
          <label htmlFor={field("address")}>Address</label>
          <input
            id={field("address")}
            className="field"
            placeholder={kind === "website" ? "https://example.com" : kind === "local_page" ? "http://localhost:3000" : "http://127.0.0.1:8080/"}
            value={form.address}
            disabled={busy}
            onChange={(e) => onChange({ address: e.target.value })}
          />
        </>
      )}
      {kind === "mcp_http" && (
        <>
          <label htmlFor={field("key")}>Access key (optional)</label>
          <p className="m-muted" id={field("key-help")}>
            Kept locked on this computer. It is never shown again.
          </p>
          <input
            id={field("key")}
            className="field"
            type="password"
            autoComplete="off"
            aria-describedby={field("key-help")}
            value={form.key}
            disabled={busy}
            onChange={(e) => onChange({ key: e.target.value })}
          />
        </>
      )}
      {isProcess(kind) && (
        <>
          <label htmlFor={field("label")}>Name (optional)</label>
          <input
            id={field("label")}
            className="field"
            value={form.label}
            disabled={busy}
            onChange={(e) => onChange({ label: e.target.value })}
          />
          <label htmlFor={field("output")}>Output folder (optional)</label>
          <p className="m-muted" id={field("output-help")}>
            The one folder Athena may bring files from.
          </p>
          <input
            id={field("output")}
            className="field m-mono"
            aria-describedby={field("output-help")}
            value={form.outputDir}
            disabled={busy}
            onChange={(e) => onChange({ outputDir: e.target.value })}
          />
        </>
      )}
      {device && (
        <div className="m-row">
          <button
            type="button"
            role="switch"
            aria-checked={form.offered}
            aria-label="Offer to paired computers"
            className="btn btn-pill"
            disabled={busy}
            onClick={() => onChange({ offered: !form.offered })}
          >
            {form.offered ? "On" : "Off"}
          </button>
          <span>Offer to paired computers</span>
        </div>
      )}
      <div className="m-row">
        <button type="submit" className="btn btn-primary" disabled={busy || !ready(kind, form)}>
          {busy ? "Adding..." : "Add this app"}
        </button>
        <button type="button" className="btn btn-quiet" disabled={busy} onClick={onBack}>
          Choose another kind
        </button>
      </div>
    </form>
  );
}

/** What the first look found: the tools with their marks, the page answering, or why not. */
function Found({ app, problem, looking, onDone }: { app: App; problem: string; looking: boolean; onDone: () => void }) {
  const state = statusOf(app.status);
  return (
    <div className="m-confirm" role="status" data-role="found">
      {looking ? (
        <p>
          <strong>{app.label}</strong> is added. Athena is looking at what it offers...
        </p>
      ) : (
        <>
          <p>
            <strong>{app.label}</strong> is added.{" "}
            <span className="badge" data-tone={state.tone}>
              {state.words}
            </span>
          </p>
          {app.reason && <p className="m-muted">{app.reason}</p>}
          {problem && <p className="m-error">{problem}</p>}
          {isProcess(app.kind) && app.status === "ok" && (
            <>
              <p>
                Found {app.tools.length} {app.tools.length === 1 ? "tool" : "tools"}.
              </p>
              <ToolList tools={app.tools} />
            </>
          )}
          {!isProcess(app.kind) && app.status === "ok" && <p>The page answers.</p>}
          <div className="m-row">
            <button type="button" className="btn" onClick={onDone}>
              Done
            </button>
          </div>
        </>
      )}
    </div>
  );
}
