// Letting an outside agent use a project, in one short form (spark agent-leases): a name, how long,
// what it may use, and, if the person wants, a few named calls it may run without asking, signed once
// on a card. On connect the daemon answers the agent's config: drawn once in a code block with Copy,
// never a title, an accessible name, a field's value or a list row (as the pairing address in the
// devices wizard). It lives only in this panel's state; closing the panel unmounts it and it is gone.
//
// The panel keeps the keyboard as the devices wizard does: it takes the focus when it opens, Tab wraps
// inside it, and Escape closes it (the section returns the focus to the button that opened it).

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import * as api from "../../../lib/api";
import { AGENT_CALLS_MAX, AGENT_FILE_MB_MAX, AGENT_LABEL_MAX, type AgentLease, type App } from "../../../lib/contract";
import { reasonOf } from "../../store";
import { useAppList } from "../apps/useApps";
import "./agents.css";
import {
  GROUP_ORDER,
  GROUP_WORDS,
  LENGTHS,
  askingTools,
  bodyOf,
  emptyForm,
  problemOf,
  whereOf,
  type ConnectForm,
  type Group,
} from "./words";

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), [tabindex="0"]';

type Phase = { at: "form" } | { at: "minting" } | { at: "shown"; config: string };

export interface ConnectProps {
  spaceId: string;
  /** The lease the daemon answered (it carries no secret): put in the list at once. */
  onConnected: (lease: AgentLease) => void;
  /** Escape, Cancel or Done: the section unmounts the panel and returns the focus. */
  onClosed: () => void;
}

export function Connect({ spaceId, onConnected, onClosed }: ConnectProps) {
  const { apps, problem: appsProblem, loaded } = useAppList(spaceId, () => api.spaceApps(spaceId), "Could not read the project's apps");
  const [phase, setPhase] = useState<Phase>({ at: "form" });
  const [form, setForm] = useState<ConnectForm>(emptyForm);
  const [refusal, setRefusal] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    heading.current?.focus();
  }, [phase.at]);

  const appsRead = loaded && !appsProblem;
  const needsApps = form.unattended || (form.groups.apps && !GROUP_ORDER.every((g) => form.groups[g]));
  const wrong = problemOf(form) || (needsApps && !appsRead ? (loaded ? appsProblem : "Reading the project's apps...") : "");

  const submit = async () => {
    if (wrong || phase.at !== "form") return;
    setRefusal("");
    setPhase({ at: "minting" });
    try {
      const answer = await api.connectAgent(spaceId, bodyOf(form, apps));
      onConnected(answer.lease);
      setPhase({ at: "shown", config: answer.config });
    } catch (e) {
      setRefusal(reasonOf(e, "Could not connect the agent"));
      setPhase({ at: "form" });
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      // While the daemon is answering, the panel stays: closing would lose the one showing.
      if (phase.at !== "minting") onClosed();
      return;
    }
    if (e.key !== "Tab") return;
    const stops = [...e.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)];
    const first = stops[0];
    const last = stops[stops.length - 1];
    if (!first || !last) return;
    const here = document.activeElement;
    if (e.shiftKey && (here === first || here === heading.current)) last.focus();
    else if (!e.shiftKey && here === last) first.focus();
    else return;
    e.preventDefault();
  };

  const titleId = useId();
  return (
    <div className="m-agent-connect" role="dialog" aria-modal="true" aria-labelledby={titleId} data-phase={phase.at} onKeyDown={onKeyDown}>
      <h3 id={titleId} ref={heading} tabIndex={-1} className="m-agent-connect__title">
        {phase.at === "shown" ? "Paste this into the agent" : "Let an agent use this project"}
      </h3>
      {phase.at === "shown" ? (
        <Shown config={phase.config} onDone={onClosed} />
      ) : (
        <Form
          form={form}
          apps={apps}
          appsRead={appsRead}
          appsProblem={loaded ? appsProblem : ""}
          busy={phase.at === "minting"}
          wrong={wrong}
          refusal={refusal}
          onChange={(patch) => setForm((f) => ({ ...f, ...patch }))}
          onSubmit={() => void submit()}
          onCancel={onClosed}
        />
      )}
    </div>
  );
}

interface FormProps {
  form: ConnectForm;
  apps: App[];
  appsRead: boolean;
  appsProblem: string;
  busy: boolean;
  wrong: string;
  refusal: string;
  onChange: (patch: Partial<ConnectForm>) => void;
  onSubmit: () => void;
  onCancel: () => void;
}

function Form({ form, apps, appsRead, appsProblem, busy, wrong, refusal, onChange, onSubmit, onCancel }: FormProps) {
  const id = useId();
  const field = (name: string) => `${id}-${name}`;
  const asking = askingTools(apps);

  const setLength = (minutes: number) => {
    const free = Number(form.freeMinutes.trim());
    // The time without asking follows the length while it was the length, and never outlasts it.
    const freeMinutes = !Number.isFinite(free) || free === form.minutes || free > minutes ? String(minutes) : form.freeMinutes;
    onChange({ minutes, freeMinutes });
  };
  const toggleGroup = (g: Group) => onChange({ groups: { ...form.groups, [g]: !form.groups[g] } });
  const toggleFree = (name: string) =>
    onChange({ free: form.free.includes(name) ? form.free.filter((n) => n !== name) : [...form.free, name] });

  return (
    <form
      className="m-agent-form"
      aria-label="Let an agent use this project"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <p className="m-muted">It works through Athena: what asks you first still asks you first, and you can end it at any time.</p>

      <label htmlFor={field("label")}>Name</label>
      <p className="m-muted" id={field("label-help")}>
        You choose it. It is the name on everything it asks you.
      </p>
      <input
        id={field("label")}
        className="field"
        maxLength={AGENT_LABEL_MAX}
        autoComplete="off"
        aria-describedby={field("label-help")}
        value={form.label}
        disabled={busy}
        onChange={(e) => onChange({ label: e.target.value })}
      />

      <fieldset className="m-agent-fieldset" disabled={busy}>
        <legend className="m-label">For how long</legend>
        <div className="m-row">
          {LENGTHS.map((l) => (
            <label key={l.minutes} className="m-agent-choice">
              <input type="radio" name={field("length")} checked={form.minutes === l.minutes} onChange={() => setLength(l.minutes)} />
              {l.words}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="m-agent-fieldset" disabled={busy}>
        <legend className="m-label">What it may use</legend>
        <ul className="m-agent-ticks">
          {GROUP_ORDER.map((g) => (
            <li key={g}>
              <label className="m-agent-tick" data-group={g}>
                <input type="checkbox" checked={form.groups[g]} onChange={() => toggleGroup(g)} />
                <span className="m-agent-tick__words">
                  <span>{GROUP_WORDS[g].name}</span>
                  <span className="m-muted">{GROUP_WORDS[g].hint}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
        <p className="m-muted">It can always see your answers to what it asks.</p>
      </fieldset>

      <label className="m-agent-tick">
        <input type="checkbox" checked={form.unattended} disabled={busy} onChange={() => onChange({ unattended: !form.unattended })} />
        <span>Let it run some calls without asking</span>
      </label>
      {form.unattended && (
        <fieldset className="m-agent-fieldset m-agent-free" disabled={busy} data-role="without-asking">
          <legend className="m-sr">Calls it may run without asking</legend>
          <p className="m-muted">
            You sign once, on a card Athena shows you. Until you sign, and for anything else, it still asks you.
          </p>
          {appsProblem && (
            <p className="m-error" role="alert">
              {appsProblem}
            </p>
          )}
          {appsRead && !asking.length && <p className="m-muted">None of the project&apos;s apps has a call that asks you first.</p>}
          {asking.length > 0 && (
            <ul className="m-agent-ticks">
              {asking.map((t) => (
                <li key={t.name}>
                  <label className="m-agent-tick" data-tool={t.name}>
                    <input type="checkbox" checked={form.free.includes(t.name)} onChange={() => toggleFree(t.name)} />
                    <span className="m-agent-tick__words">
                      <span>
                        <span className="m-mono">{t.tool.name}</span> <span className="m-muted">{whereOf(t)}</span>
                      </span>
                      {t.tool.description && <span className="m-muted m-agent-wrap">{t.tool.description}</span>}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          <div className="m-agent-limits">
            <label htmlFor={field("calls")}>Up to this many calls</label>
            <input
              id={field("calls")}
              className="field"
              type="number"
              inputMode="numeric"
              min={1}
              max={AGENT_CALLS_MAX}
              value={form.calls}
              onChange={(e) => onChange({ calls: e.target.value })}
            />
            <label htmlFor={field("minutes")}>For this many minutes</label>
            <input
              id={field("minutes")}
              className="field"
              type="number"
              inputMode="numeric"
              min={1}
              max={form.minutes}
              value={form.freeMinutes}
              onChange={(e) => onChange({ freeMinutes: e.target.value })}
            />
            <label htmlFor={field("mb")}>Files up to this many MB (optional)</label>
            <input
              id={field("mb")}
              className="field"
              type="number"
              inputMode="numeric"
              min={1}
              max={AGENT_FILE_MB_MAX}
              aria-describedby={field("mb-help")}
              value={form.fileMb}
              onChange={(e) => onChange({ fileMb: e.target.value })}
            />
          </div>
          <p className="m-muted" id={field("mb-help")}>
            Empty: it asks you before bringing any file home.
          </p>
        </fieldset>
      )}

      {wrong && !busy && (
        <p className="m-muted" data-role="not-ready">
          {wrong}
        </p>
      )}
      <div className="m-row">
        <button type="submit" className="btn btn-primary" disabled={busy || !!wrong}>
          {busy ? "Connecting..." : "Connect"}
        </button>
        <button type="button" className="btn btn-quiet" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
      {refusal && (
        <p className="m-error" role="alert">
          {refusal}
        </p>
      )}
    </form>
  );
}

/** The config, once, with Copy. A refused copy is said, never a press that does nothing. */
function Shown({ config, onDone }: { config: string; onDone: () => void }) {
  const [copied, setCopied] = useState<boolean | null>(null);
  const copy = () => {
    const write = navigator.clipboard?.writeText(config) ?? Promise.reject(new Error("no clipboard"));
    void write.then(
      () => setCopied(true),
      () => setCopied(false),
    );
  };
  return (
    <div className="m-agent-shown" data-role="shown">
      <p>Shown once. Paste it into the agent&apos;s settings. Revoke ends it.</p>
      <figure className="m-agent-config">
        <figcaption className="m-muted">MCP config</figcaption>
        <pre className="m-agent-config__text" data-role="config">
          <code>{config}</code>
        </pre>
      </figure>
      <div className="m-row">
        <button type="button" className="btn" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </button>
        <button type="button" className="btn btn-primary" onClick={onDone}>
          Done
        </button>
      </div>
      {copied === false && (
        <p className="m-error" role="alert">
          Could not copy it; select it and copy it by hand.
        </p>
      )}
    </div>
  );
}
