// The dress rehearsal's practice page: the conversation beside the trip page, a stamp on every twin
// turn (waits for your signature, held with its risk list, you edited, sent on its own), and what came
// of it: the row filed to Notion, or the conversation handed back.

import { useEffect, useRef, type ReactNode } from "react";
import type { MissionTurn, TwinFiled } from "../../lib/contract";
import { useClock } from "../stage/hooks";
import { clock } from "./format";
import { Icon, Portrait, Stamp, Sure } from "./marks";
import type { RehearsalStep } from "./select";
import type { SetupState, TwinsAction } from "./types";
import { WAIT } from "./words";

export interface PracticeProps {
  s: SetupState;
  step: RehearsalStep;
  turns: readonly MissionTurn[];
  current?: MissionTurn;
  /** The twin's name and its first letter. */
  name: string;
  signsAs: string;
  /** The other side, as the practice page names them. */
  other: string;
  playedBy: string;
  goal: string;
  /** The chore that files the outcome, by its preset id. */
  choreName: (id: string) => string;
  dispatch: (a: TwinsAction) => void;
}

const para = (text: string) =>
  text.split("\n\n").map((chunk, i) => (
    <span key={i}>
      {i > 0 && (
        <>
          <br />
          <br />
        </>
      )}
      {chunk.split("\n").map((line, j) => (
        <span key={j}>
          {j > 0 && <br />}
          {line}
        </span>
      ))}
    </span>
  ));

const initials = (name: string) =>
  name
    .replace(/\(.*\)/, "")
    .trim()
    .split(/\s+/)
    .map((x) => x[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

/** Seconds since the rehearsal's first turn, for the turn's own clock. */
function atOf(t: MissionTurn, first: MissionTurn | undefined): number {
  if (!first) return 0;
  return Math.max(0, (new Date(t.at).getTime() - new Date(first.at).getTime()) / 1000);
}

function Who({ name, sub, at, stamp, letter }: { name: string; sub: ReactNode; at?: string; stamp?: ReactNode; letter?: string }) {
  return (
    <div className="turn__who">
      {letter !== undefined ? <Portrait letter={letter} size={26} /> : <span className="av">{initials(name)}</span>}
      <b>{name}</b>
      {sub}
      {at !== undefined && <span className="turn__at">{at}</span>}
      {stamp}
    </div>
  );
}

function Writing({ label, name, s }: { label: string; name: string; s: SetupState }) {
  const secs = useClock(s.startedAt, true);
  return (
    <li className="turn turn--twin turn--writing">
      <Who name={name} sub={<span>as you</span>} letter={name[0] ?? "T"} />
      <div className="ghost" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
      <p className="turn__status">
        <span className="spin" aria-hidden="true" />
        {label} <span>{secs.toFixed(1)} s</span>
      </p>
    </li>
  );
}

function TwinTurn({ t, p, current, at }: { t: MissionTurn; p: PracticeProps; current: boolean; at: string }) {
  const { s, step, dispatch } = p;
  const name = p.name;
  const why = t.reason ? WAIT[t.reason] : t.decision === "sent_alone" ? "Auto: sure enough and nothing on its risk list" : "";
  const sure = (
    <div className="turn__why">
      <Sure value={t.confidence ?? 0} bar={t.bar} compact />
      <span>{why}.</span>
    </div>
  );
  const risks = t.risks?.length ? (
    <ul className="risks" aria-label="Its risk list">
      {t.risks.map((x) => (
        <li key={x}>
          <Icon name="risk" />
          {x}
        </li>
      ))}
    </ul>
  ) : null;
  let stamp: ReactNode = null;
  let body: ReactNode = <p className="turn__text">{para(t.text)}</p>;
  let extra: ReactNode = null;
  let actions: ReactNode = null;
  const busy = !!s.work;
  if (t.decision === "waits" && t.kind === "first_message") {
    stamp = <Stamp text="Waits for your signature" tone="human" fresh={current && step === "waits"} />;
    extra = sure;
    if (current && step === "waits") {
      actions = (
        <div className="turn__act">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => dispatch({ type: "reh_mark", mark: "me" })}>
            <Icon name="check" />
            That&apos;s me
          </button>
          <button type="button" className="btn" disabled={busy} onClick={() => dispatch({ type: "reh_mark", mark: "not_me" })}>
            Not me
          </button>
        </div>
      );
    } else if (t.mark) {
      extra = (
        <span className="mark" data-v={t.mark}>
          <Icon name="check" />
          {t.mark === "me" ? "You: that's me, signed" : t.mark === "edited" ? "You edited it" : "You: not me"}
        </span>
      );
    }
  } else if (t.decision === "waits") {
    stamp = <Stamp text="Held" tone="warning" sub="waits for you" fresh={current && step === "held"} />;
    if (current && step === "editing") {
      body = (
        <>
          <label className="sr" htmlFor="edit-box">
            Your version
          </label>
          <textarea
            id="edit-box"
            className="field editbox"
            rows={5}
            value={s.rehearsal?.editText ?? t.text}
            onChange={(e) => dispatch({ type: "reh_text", text: e.target.value })}
          />
        </>
      );
      actions = (
        <div className="turn__act">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => dispatch({ type: "reh_save" })}>
            Save my version
          </button>
        </div>
      );
      extra = risks;
    } else if (t.mark === "edited") {
      body = (
        <>
          <p className="turn__text turn__text--mine">{para(t.edited_text ?? t.text)}</p>
          {current && (
            <p className="turn__was">
              <span>It wrote:</span> {t.text.split("\n")[0]}
            </p>
          )}
        </>
      );
      stamp = <Stamp text="You edited" tone="human" sub="and signed" fresh={current && step === "edited"} />;
      extra = t.learned ? (
        <p className="learned">
          <Icon name="layers" />
          <span>
            <b>It learned:</b> {t.learned}
          </span>
        </p>
      ) : null;
      if (current && step === "edited") {
        actions = (
          <div className="turn__act">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => dispatch({ type: "reh_send" })}>
              <Icon name="send" />
              Send it
            </button>
            <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => dispatch({ type: "reh_edit" })}>
              Edit again
            </button>
          </div>
        );
      }
    } else {
      extra = (
        <>
          {sure}
          {risks}
          {t.mark && (
            <span className="mark" data-v={t.mark}>
              <Icon name="check" />
              {t.mark === "me" ? "You: that's me, as it is" : "You: not me"}
            </span>
          )}
        </>
      );
      if (current && step === "held") {
        actions = (
          <div className="turn__act">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => dispatch({ type: "reh_edit" })}>
              <Icon name="pencil" />
              Edit it
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => dispatch({ type: "reh_mark", mark: "me" })}>
              Send it as it is
            </button>
            <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => dispatch({ type: "reh_mark", mark: "not_me" })}>
              Not me
            </button>
          </div>
        );
      }
    }
  } else {
    stamp = <Stamp text="Sent on its own" tone="success" fresh={current && step === "sent"} />;
    extra = sure;
  }
  return (
    <li className={`turn turn--twin ${current ? "is-current is-new" : "turn--past"}`} data-turn={t.id}>
      <Who name={name} sub={<span>as {p.signsAs}</span>} at={at} stamp={stamp} letter={name[0] ?? "T"} />
      {body}
      {extra}
      {actions}
    </li>
  );
}

function Outcome({ filed, choreName, dispatch }: { filed?: TwinFiled; choreName: (id: string) => string; dispatch: (a: TwinsAction) => void }) {
  return (
    <div className="outcome is-new" data-state="resolved">
      <div className="outcome__h">
        <Stamp text="Resolved" tone="success" fresh />
        <b>They said yes.</b>
      </div>
      {filed && (
        <>
          <p className="outcome__s">
            <Icon name="notion" />
            The &quot;{choreName(filed.chore)}&quot; chore added a row to <b>{filed.where}</b>
          </p>
          <table className="filed">
            <thead>
              <tr>
                {Object.keys(filed.row).map((k) => (
                  <th key={k}>{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {Object.values(filed.row).map((v, i) => (
                  <td key={i}>{v}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </>
      )}
      <div className="turn__act">
        <button type="button" className="btn btn-primary" onClick={() => dispatch({ type: "golive" })}>
          Go live: issue the document
          <Icon name="arrow" />
        </button>
        <button type="button" className="btn btn-quiet" onClick={() => dispatch({ type: "reh_alt" })}>
          Try it another way
        </button>
      </div>
    </div>
  );
}

function Handed({ why, dispatch }: { why: string; dispatch: (a: TwinsAction) => void }) {
  return (
    <div className="outcome is-new" data-state="handed">
      <div className="outcome__h">
        <Stamp text="Handed back to you" tone="human" fresh />
        <b>It stopped instead of answering.</b>
      </div>
      <p className="outcome__s">{why}</p>
      <div className="turn__act">
        <button type="button" className="btn btn-primary" onClick={() => dispatch({ type: "golive" })}>
          Good. Go live
          <Icon name="arrow" />
        </button>
        <button type="button" className="btn" onClick={() => dispatch({ type: "reh_alt" })}>
          <Icon name="retry" />
          Replay the usual path
        </button>
      </div>
    </div>
  );
}

export function PracticePage(p: PracticeProps) {
  const { s, step, turns, current } = p;
  const list = useRef<HTMLOListElement>(null);
  const first = turns[0];
  const last = turns.at(-1);
  // keep the newest turn in view inside the practice page; the page itself never scrolls
  useEffect(() => {
    const el = list.current;
    if (!el) return;
    const cur = el.querySelector<HTMLElement>(".is-current") ?? (el.lastElementChild as HTMLElement | null);
    if (!cur) return;
    const top = cur.offsetTop - 8;
    const bottom = cur.offsetTop + cur.offsetHeight - el.clientHeight + 12;
    el.scrollTop = Math.max(0, Math.min(top, bottom));
  }, [turns.length, step]);
  const lastAt = last ? atOf(last, first) : 0;
  return (
    <section className="practice" aria-label="Practice page">
      <header className="practice__h">
        <span className="practice__icon">
          <Icon name="notion" />
        </span>
        <div>
          <b>Practice: {p.other}</b>
          <span>
            Notion practice page · {p.playedBy} · {clock(lastAt)} in
          </span>
        </div>
        <span className="practice__m">
          <span>Mission</span>
          {p.goal}
        </span>
      </header>
      <ol className="turns" ref={list}>
        {turns.map((t) =>
          t.side === "other" ? (
            <li key={t.id} className={`turn turn--creator ${t === last && step === "writing" ? "is-new" : ""}`.trim()}>
              <Who name={p.other} sub={<span className="tag">played by Athena</span>} at={clock(atOf(t, first))} />
              <p className="turn__text">{para(t.text)}</p>
            </li>
          ) : (
            <TwinTurn key={t.id} t={t} p={p} current={t.id === current?.id} at={clock(atOf(t, first))} />
          ),
        )}
        {step === "writing" && <Writing label={turns.length ? "Writing a reply" : "Writing its first message"} name={p.name} s={s} />}
        {step === "typing" && (
          <li className="turn turn--creator turn--typing">
            <Who name={p.other} sub={<span className="tag">played by Athena</span>} />
            <p className="dots" aria-label={`${p.other} is typing`}>
              <i />
              <i />
              <i />
            </p>
          </li>
        )}
      </ol>
      {step === "resolved" && <Outcome filed={s.rehearsal?.outcome?.filed} choreName={p.choreName} dispatch={p.dispatch} />}
      {step === "handed" && <Handed why={s.twin?.rehearsal?.note ?? "It handed the conversation back to you."} dispatch={p.dispatch} />}
    </section>
  );
}
