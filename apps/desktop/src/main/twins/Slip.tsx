// The slip: the one working leaf clipped beside the document (sign in, samples, particulars, Notion
// key, pages, permits, clearance, endorsements, her pencil). It says which section the answer lands in.

import { useState, type ReactNode } from "react";
import type { Autonomy, Place } from "../../lib/contract";
import { useClock } from "../stage/hooks";
import { clock, day } from "./format";
import { Icon, Stamp } from "./marks";
import { PieceLine } from "./Document";
import { pencilOf } from "./select";
import { chosen, dialsShown } from "./store";
import type { ChoiceGroup, SetupState, TwinsAction } from "./types";
import { CONNECT_WORDS, LEVEL, RULE, SECTION } from "./words";

export interface SlipProps {
  s: SetupState;
  dispatch: (a: TwinsAction) => void;
  /** The example's words for the practice page. */
  where: string;
  playedBy: string;
  goliveLine: string;
  stays: readonly string[];
  onBack: () => void;
}

function Shell({ kind, lands, title, sub, children, foot }: { kind: string; lands?: Place | null; title: string; sub?: ReactNode; children: ReactNode; foot?: ReactNode }) {
  return (
    <aside className="slip" data-kind={kind} aria-label={title} data-role="slip">
      <header className="slip__h">
        {lands && (
          <span className="slip__k">
            <Icon name="arrow" />
            Lands in <b>{SECTION[lands]}</b>
          </span>
        )}
        <h2>{title}</h2>
        {sub && <p>{sub}</p>}
      </header>
      <div className="slip__b">{children}</div>
      {foot && <footer className="slip__f">{foot}</footer>}
    </aside>
  );
}

function Tick({ on, by }: { on: boolean; by: "you" | "athena" }) {
  return (
    <span className="tick" data-on={String(on)} data-by={by} aria-hidden="true">
      {on && <Icon name="check" />}
    </span>
  );
}

function Intro() {
  const step = (n: number, t: string, s: string) => (
    <li>
      <span className="num">{n}</span>
      <div>
        <b>{t}</b>
        <span>{s}</span>
      </div>
    </li>
  );
  return (
    <Shell kind="intro" title="How a twin gets its document">
      <ol className="howto">
        {step(1, "You say what it is for", "Athena fills in each section in pencil while you talk. You ink what is right.")}
        {step(2, "It takes a first trip", "A dress rehearsal on a Notion practice page, with Athena playing the other side.")}
        {step(3, "Go live", "The document is issued. Drafts you must sign wait for you on your twins page.")}
      </ol>
      <p className="slip__quiet">Nothing is sent to anyone while you set it up.</p>
    </Shell>
  );
}

function Pencil({ s, dispatch }: SlipProps) {
  const list = pencilOf(s.twin);
  const place = s.ask?.place ?? null;
  const ink = (id: string) => dispatch({ type: "ink", pieces: [id] });
  return (
    <Shell
      kind="pencil"
      lands={place}
      title={list.length ? `Her pencil: ${list.length} to ink` : "All inked"}
      sub={list.length ? "Her proposals are dashed. Ink one, or all of them, to make them yours. Answer her question below either way." : undefined}
      foot={
        list.length ? (
          <button type="button" className="btn" disabled={!!s.work} onClick={() => dispatch({ type: "ink_all" })}>
            <Icon name="nib" />
            Ink all {list.length}
          </button>
        ) : undefined
      }
    >
      {list.length ? (
        <ul className="pcs pcs--lines pcs--slip">
          {list.map((p) => (
            <PieceLine key={p.id} p={p} s={s} onInk={ink} evidence={false} />
          ))}
        </ul>
      ) : (
        <p className="slip__quiet">Nothing in her pencil. Everything on the document is inked.</p>
      )}
    </Shell>
  );
}

function Waited({ s, total }: { s: SetupState; total?: number }) {
  const secs = useClock(s.connectSince, true);
  return <>{total ? `${clock(secs)} of ${clock(total)}` : `${secs.toFixed(1)} s`}</>;
}

function Gmail({ s, dispatch }: SlipProps) {
  const g = CONNECT_WORDS.gmail;
  const st = s.connect.gmail;
  const [client, setClient] = useState({ id: "", secret: "" });
  const [steps, setSteps] = useState(false);
  const account = s.twin?.channels.find((c) => c.kind === "gmail")?.account ?? "";
  let state: ReactNode = null;
  let foot: ReactNode = (
    <button
      type="button"
      className="btn btn-primary"
      disabled={!!s.work}
      onClick={() => dispatch(client.id && client.secret ? { type: "gmail", client_id: client.id, client_secret: client.secret } : { type: "gmail" })}
    >
      <Icon name="gmail" />
      {g.signIn}
    </button>
  );
  if (st === "waiting") {
    state = (
      <div className="cstate" data-state="waiting">
        <span className="spin" aria-hidden="true" />
        <div>
          <b>{g.waiting}</b>
          <span>
            Waiting <Waited s={s} total={600} />. {g.waitingFor}
          </span>
        </div>
      </div>
    );
    foot = (
      <button type="button" className="btn" onClick={() => dispatch({ type: "gmail_cancel" })}>
        {g.cancel}
      </button>
    );
  } else if (st === "connected") {
    state = (
      <div className="cstate" data-state="connected">
        <Stamp text="Stamped" tone="success" fresh />
        <div>
          <b>{g.connected(account)}</b>
          <span>{g.stamped}</span>
        </div>
      </div>
    );
    foot = null;
  } else if (st === "failed") {
    state = (
      <div className="cstate" data-state="failed">
        <Icon name="risk" />
        <div>
          <b>{g.failed}</b>
          <span>{g.failedHint}</span>
        </div>
      </div>
    );
    foot = (
      <button type="button" className="btn btn-primary" onClick={() => dispatch({ type: "gmail" })}>
        <Icon name="retry" />
        Try again
      </button>
    );
  }
  return (
    <Shell kind="gmail" lands="channels" title={g.title} sub={g.sub} foot={foot}>
      <div className="perm">
        <div>
          <span className="perm__k">It asks Google for</span>
          {g.asksFor.map((x) => (
            <span key={x} className="perm__i" data-ok="true">
              <Icon name="check" />
              {x}
            </span>
          ))}
        </div>
        <div>
          <span className="perm__k">It never asks for</span>
          {g.neverAsksFor.map((x) => (
            <span key={x} className="perm__i" data-ok="false">
              <Icon name="x" />
              {x}
            </span>
          ))}
        </div>
      </div>
      {st !== "connected" && st !== "waiting" && (
        <details className="client" open={steps} onToggle={(e) => setSteps((e.target as HTMLDetailsElement).open)}>
          <summary>
            <Icon name="key" />
            {g.client}
          </summary>
          <p className="client__hint">{g.clientHint}</p>
          <ol className="where">
            {g.clientSteps.map((x, i) => (
              <li key={x}>
                <span className="num">{i + 1}</span>
                {x}
              </li>
            ))}
          </ol>
          <div className="client__f">
            <label>
              <span>{g.clientId}</span>
              <input className="field" value={client.id} autoComplete="off" spellCheck={false} onChange={(e) => setClient({ ...client, id: e.target.value })} />
            </label>
            <label>
              <span>{g.clientSecret}</span>
              <input className="field" type="password" value={client.secret} autoComplete="off" onChange={(e) => setClient({ ...client, secret: e.target.value })} />
            </label>
          </div>
        </details>
      )}
      {state}
    </Shell>
  );
}

function Notion({ s, dispatch }: SlipProps) {
  const n = CONNECT_WORDS.notion;
  const st = s.connect.notion;
  const [key, setKey] = useState("");
  const account = s.twin?.channels.find((c) => c.kind === "notion")?.account ?? "";
  const where =
    s.where || st === "rejected" ? (
      <ol className="where">
        {n.steps.map((x, i) => (
          <li key={x}>
            <span className="num">{i + 1}</span>
            {x}
          </li>
        ))}
      </ol>
    ) : (
      <button type="button" className="btn btn-quiet where__btn" onClick={() => dispatch({ type: "where" })}>
        <Icon name="eye" />
        {n.whereToFind}
      </button>
    );
  let state: ReactNode = null;
  if (st === "checking")
    state = (
      <div className="cstate" data-state="waiting">
        <span className="spin" aria-hidden="true" />
        <div>
          <b>{n.checking}</b>
          <span>
            <Waited s={s} />
          </span>
        </div>
      </div>
    );
  if (st === "connected")
    state = (
      <div className="cstate" data-state="connected">
        <Stamp text="Stamped" tone="success" fresh />
        <div>
          <b>{n.connected(account)}</b>
          <span>{CONNECT_WORDS.gmail.stamped}</span>
        </div>
      </div>
    );
  if (st === "rejected")
    state = (
      <div className="cstate" data-state="failed">
        <Icon name="risk" />
        <div>
          <b>{n.rejected}</b>
          <span>{n.rejectedHint}</span>
        </div>
      </div>
    );
  return (
    <Shell kind="notion" lands="channels" title={n.title} sub={n.sub}>
      {st !== "connected" && (
        <form
          className="keyform"
          autoComplete="off"
          onSubmit={(e) => {
            e.preventDefault();
            if (key.trim()) dispatch({ type: "notion", key });
          }}
        >
          <label htmlFor="notion-key">{n.key}</label>
          <div className="keyform__row">
            <input id="notion-key" className="field" type="password" value={key} placeholder={n.keyPlaceholder} disabled={st === "checking"} onChange={(e) => setKey(e.target.value)} />
            <button className="btn btn-primary" type="submit" disabled={st === "checking" || !key.trim()}>
              <Icon name="key" />
              {n.check}
            </button>
          </div>
        </form>
      )}
      {state}
      {st !== "connected" && where}
    </Shell>
  );
}

function Rows<T extends { id: string }>({
  items,
  group,
  s,
  dispatch,
  on,
  render,
  className = "",
}: {
  items: readonly T[];
  group: ChoiceGroup;
  s: SetupState;
  dispatch: (a: TwinsAction) => void;
  on: (x: T) => boolean;
  render: (x: T) => ReactNode;
  className?: string;
}) {
  return (
    <>
      {items.map((x) => {
        const isOn = on(x);
        const by = s.choices[group][x.id] !== undefined ? "you" : "athena";
        return (
          <button
            key={x.id}
            type="button"
            className={`row ${className}`.trim()}
            aria-pressed={isOn}
            onClick={() => dispatch({ type: "choose", group, id: x.id, on: !isOn })}
          >
            <Tick on={isOn} by={by} />
            <span className="row__m">{render(x)}</span>
          </button>
        );
      })}
    </>
  );
}

function Samples({ s, dispatch }: SlipProps) {
  const list = s.twin?.samples ?? [];
  const on = (x: (typeof list)[number]) => chosen(s.choices, "samples", x.id, x.picked);
  const n = list.filter(on).length;
  return (
    <Shell
      kind="samples"
      lands="voice"
      title={`${list.length === 6 ? "Six" : list.length} mails you sent`}
      sub="Its voice comes only from mail you wrote yourself. Dashed ticks are her pencil."
      foot={
        <>
          <span className="slip__count">{n} kept</span>
          <button type="button" className="btn btn-primary" disabled={!n || !!s.work} onClick={() => dispatch({ type: "panel_go" })}>
            Learn from these {n}
          </button>
        </>
      }
    >
      <div className="rows">
        <Rows
          items={list}
          group="samples"
          s={s}
          dispatch={dispatch}
          on={on}
          render={(x) => (
            <>
              <span className="row__t">
                <b>{x.to}</b>
                <span>{x.subject}</span>
              </span>
              <span className="row__d">
                {day(x.date)} · {x.words} words
              </span>
              {x.why_not ? <span className="row__why">Not suggested: {x.why_not}</span> : <span className="row__x">{x.excerpt}</span>}
            </>
          )}
        />
      </div>
    </Shell>
  );
}

const SRC = { learned: "your mail", preset: "preset", you: "you" } as const;

function Style({ s, dispatch }: SlipProps) {
  const dials = dialsShown(s);
  return (
    <Shell
      kind="style"
      lands="voice"
      title="Its particulars"
      sub="Eight dials, set from your four mails. Each says where its value came from. Change any; or swap to a preset."
      foot={
        <button type="button" className="btn btn-primary" disabled={!!s.work} onClick={() => dispatch({ type: "panel_go" })}>
          Keep this style
        </button>
      }
    >
      <div className="presets">
        <span>Swap to</span>
        {(s.twin?.style_presets ?? []).map((p) => (
          <button key={p} type="button" className="chip" aria-pressed={s.choices.preset === p} onClick={() => dispatch({ type: "preset", name: p })}>
            {p}
          </button>
        ))}
      </div>
      <div className="dials">
        {dials.map((d) => (
          <div key={d.id} className="dialrow" data-src={d.source}>
            <span className="dialrow__l">{d.label}</span>
            <span className="dialrow__lo">
              {d.low} to {d.high}
            </span>
            <span className="dialrow__p" role="group" aria-label={d.label}>
              {[1, 2, 3, 4, 5].map((v) => (
                <button key={v} type="button" data-on={String(v <= d.value)} aria-label={String(v)} aria-pressed={v === d.value} onClick={() => dispatch({ type: "dial", id: d.id, value: v })} />
              ))}
            </span>
            <span className="dialrow__s">{SRC[d.source]}</span>
          </div>
        ))}
      </div>
    </Shell>
  );
}

function Pages({ s, dispatch }: SlipProps) {
  const list = s.twin?.pages ?? [];
  const on = (x: (typeof list)[number]) => chosen(s.choices, "pages", x.id, x.picked);
  const n = list.filter(on).length;
  return (
    <Shell
      kind="pages"
      lands="knowledge"
      title="Pages it can see"
      sub="It answers only from the pages you tick, and nothing else."
      foot={
        <>
          <span className="slip__count">{n} chosen</span>
          <button type="button" className="btn btn-primary" disabled={!!s.work} onClick={() => dispatch({ type: "panel_go" })}>
            Read from these {n}
          </button>
        </>
      }
    >
      <div className="rows">
        <Rows
          items={list}
          group="pages"
          s={s}
          dispatch={dispatch}
          on={on}
          className="row--1"
          render={(x) => (
            <>
              <span className="row__t">
                <b>{x.title}</b>
                <span>{x.kind === "database" ? "Notion database" : "Notion page"}</span>
              </span>
              {x.why_not && <span className="row__why">Not suggested: {x.why_not}</span>}
            </>
          )}
        />
      </div>
    </Shell>
  );
}

function Chores({ s, dispatch }: SlipProps) {
  const all = s.twin?.chores ?? [];
  const ready = all.filter((c) => !c.coming);
  const coming = all.filter((c) => c.coming);
  const on = (x: (typeof all)[number]) => chosen(s.choices, "chores", x.id, x.picked);
  const n = ready.filter(on).length;
  const toolName = (tool: string) => tool.slice(0, 1).toUpperCase() + tool.slice(1);
  return (
    <Shell
      kind="chores"
      lands="chores"
      title="Permits: ready-made chores"
      sub="Things it can do in Notion besides answering. More tools arrive later."
      foot={
        <>
          <span className="slip__count">{n} to issue</span>
          <button type="button" className="btn btn-primary" disabled={!!s.work} onClick={() => dispatch({ type: "panel_go" })}>
            Issue {n} permit{n === 1 ? "" : "s"}
          </button>
        </>
      }
    >
      <div className="rows">
        <span className="rows__k">
          <Icon name="notion" />
          Notion
        </span>
        <Rows
          items={ready}
          group="chores"
          s={s}
          dispatch={dispatch}
          on={on}
          className="permit-row"
          render={(c) => (
            <>
              <span className="row__t">
                <b>{c.name}</b>
                {c.later && <span className="tag">for later</span>}
              </span>
              <span className="row__x row__x--wrap">{c.does}</span>
            </>
          )}
        />
        {coming.length > 0 && <span className="rows__k">Coming</span>}
        {coming.map((c) => (
          <div key={c.id} className="row permit-row permit-row--blank" aria-disabled="true">
            <span className="tick" data-on="false" aria-hidden="true" />
            <span className="row__m">
              <span className="row__t">
                <b>{c.name}</b>
                <span className="tag">coming</span>
              </span>
              <span className="row__x">{toolName(c.tool)} is not connected in this app yet</span>
            </span>
          </div>
        ))}
      </div>
    </Shell>
  );
}

const LEVELS: Autonomy[] = ["review", "assist", "auto"];

function Seg({ value, onPick, sm = false, label }: { value: Autonomy; onPick: (v: Autonomy) => void; sm?: boolean; label: string }) {
  return (
    <span className={`seg ${sm ? "seg--sm" : ""}`.trim()} role="group" aria-label={label}>
      {LEVELS.map((l) => (
        <button key={l} type="button" aria-pressed={value === l} onClick={() => onPick(l)}>
          {LEVEL[l].label}
        </button>
      ))}
    </span>
  );
}

function AutonomySlip({ s, dispatch }: SlipProps) {
  const a = s.choices.autonomy;
  const by = a.touched ? "you" : "athena";
  const anyAuto = a.first === "auto" || (a.split && a.reply === "auto");
  const gmail = s.twin?.channels.some((c) => c.kind === "gmail") ?? true;
  const notion = s.twin?.channels.some((c) => c.kind === "notion") ?? true;
  return (
    <Shell
      kind="autonomy"
      lands="autonomy"
      title="Clearance per channel"
      foot={
        <button type="button" className="btn btn-primary" disabled={!!s.work} onClick={() => dispatch({ type: "panel_go" })}>
          Set clearance
        </button>
      }
    >
      {gmail && (
        <div className="clr" data-by={by}>
          <div className="clr__h">
            <Icon name="gmail" />
            <b>Gmail</b>
            <label className="switch">
              <input type="checkbox" checked={a.split} onChange={() => dispatch({ type: "split" })} /> Different for replies
            </label>
          </div>
          <div className="clr__r">
            <span>{a.split ? "First message" : "Every send"}</span>
            <Seg value={a.first} label={a.split ? "First message" : "Every send"} onPick={(v) => dispatch({ type: "level", which: "first", value: v })} />
          </div>
          {a.split && (
            <div className="clr__r">
              <span>Replies</span>
              <Seg value={a.reply} label="Replies" onPick={(v) => dispatch({ type: "level", which: "reply", value: v })} />
            </div>
          )}
          <p className="clr__says">{LEVEL[a.split && a.reply === "auto" ? "auto" : a.first].says}</p>
          {anyAuto && (
            <div className="clr__bar">
              <span>Sends alone at</span>
              <button type="button" className="btn" aria-label="Lower the bar" onClick={() => dispatch({ type: "bar", delta: -5 })}>
                -
              </button>
              <b>{a.bar}</b>
              <button type="button" className="btn" aria-label="Raise the bar" onClick={() => dispatch({ type: "bar", delta: 5 })}>
                +
              </button>
              <span>or more sure, risk list empty</span>
            </div>
          )}
        </div>
      )}
      {notion && (
        <div className="clr" data-by="athena">
          <div className="clr__h">
            <Icon name="notion" />
            <b>Notion</b>
            <span className="clr__scope">practice page only</span>
          </div>
          <div className="clr__r">
            <span>Practice page</span>
            <Seg value={a.notion} label="Practice page" onPick={(v) => dispatch({ type: "level", which: "notion", value: v })} />
          </div>
          <p className="clr__says">Nothing leaves Notion; it sends alone at 60 or more.</p>
        </div>
      )}
      <p className="rule">{RULE}</p>
    </Shell>
  );
}

function Memory({ s, dispatch }: SlipProps) {
  const facts = s.twin?.memory ?? [];
  const on = (id: string, f: (typeof facts)[number]) => s.choices.memory[id] ?? f.keep ?? f.suggest === "keep";
  const n = facts.filter((f) => on(f.id, f)).length;
  return (
    <Shell
      kind="memory"
      lands="memory"
      title="What she noticed about you"
      sub="It only uses the facts you keep. Dashed: her suggestion."
      foot={
        <>
          <span className="slip__count">{n} kept</span>
          <button type="button" className="btn btn-primary" disabled={!!s.work} onClick={() => dispatch({ type: "panel_go" })}>
            Keep {n}, drop {facts.length - n}
          </button>
        </>
      }
    >
      <div className="facts">
        {facts.map((f) => {
          const isOn = on(f.id, f);
          const by = s.choices.memory[f.id] !== undefined || f.keep !== undefined ? "you" : "athena";
          return (
            <div key={f.id} className="fact" data-by={by} data-on={String(isOn)}>
              <b className="fact__f">{f.fact}</b>
              <div className="fact__row">
                <span>{f.from}</span>
                <span className="seg seg--sm" role="group" aria-label="Keep or drop">
                  <button type="button" aria-pressed={isOn} disabled={isOn} onClick={() => dispatch({ type: "choose", group: "memory", id: f.id, on: true })}>
                    Keep
                  </button>
                  <button type="button" aria-pressed={!isOn} disabled={!isOn} onClick={() => dispatch({ type: "choose", group: "memory", id: f.id, on: false })}>
                    Drop
                  </button>
                </span>
              </div>
              {f.reason && <span className="row__why">She&apos;d drop it: {f.reason}</span>}
            </div>
          );
        })}
      </div>
    </Shell>
  );
}

function Rehearsal({ s, dispatch, where, playedBy }: SlipProps) {
  return (
    <Shell
      kind="rehearsal"
      title="Dress rehearsal"
      foot={
        <button type="button" className="btn btn-primary" disabled={!!s.work} onClick={() => dispatch({ type: "rehearse" })}>
          Start the rehearsal
          <Icon name="arrow" />
        </button>
      }
    >
      <div className="practice-card">
        <Icon name="notion" />
        <div>
          <b>{where}</b>
          <span>{playedBy}. Nothing reaches a real person.</span>
        </div>
      </div>
      <ol className="howto howto--tight">
        <li>
          <span className="num">1</span>
          <div>
            <b>It writes as you</b>
            <span>Each draft gets a stamp: waits for you, held with its risk list, or sent on its own.</span>
          </div>
        </li>
        <li>
          <span className="num">2</span>
          <div>
            <b>You mark each draft</b>
            <span>&quot;That&apos;s me&quot; or &quot;not me&quot;. Anything you change teaches it.</span>
          </div>
        </li>
        <li>
          <span className="num">3</span>
          <div>
            <b>Then go live</b>
            <span>The document is sealed and issued.</span>
          </div>
        </li>
      </ol>
    </Shell>
  );
}

function GoLive({ goliveLine, stays, onBack }: SlipProps) {
  return (
    <Shell
      kind="golive"
      title="Issued"
      sub={goliveLine}
      foot={
        <button type="button" className="btn btn-primary" onClick={onBack}>
          Back to your twins
          <Icon name="arrow" />
        </button>
      }
    >
      <span className="rows__k">What stays as you set it</span>
      <ul className="stays">
        {stays.map((x) => (
          <li key={x}>
            <Icon name="check" />
            {x}
          </li>
        ))}
      </ul>
      <p className="slip__quiet">Standing rules, like how much it may ever give, come in a later step.</p>
    </Shell>
  );
}

/** The slip for the frame's panel; her pencil when there is none; the issue note once sealed. */
export function Slip(props: SlipProps) {
  const { s } = props;
  if (s.sealed) return <GoLive {...props} />;
  if (!s.twin || !s.twin.pieces.length) return <Intro />;
  const panel = s.ask?.panel;
  if (!panel) return <Pencil {...props} />;
  if (panel === "connect") return s.ask?.channel === "notion" ? <Notion {...props} /> : <Gmail {...props} />;
  const SLIPS = { samples: Samples, style: Style, pages: Pages, chores: Chores, autonomy: AutonomySlip, memory: Memory, rehearsal: Rehearsal };
  const One = SLIPS[panel];
  return <One {...props} />;
}
