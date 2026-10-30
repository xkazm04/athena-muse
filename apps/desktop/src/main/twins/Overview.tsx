// The twins page (Passport): the stat strip, the wallet of closed documents with what waits for you
// beside it, and the ledger. A document opens in place as a spread (missions | drafts waiting); each
// waiting card opens its draft's own page, and each mission's beat dots open its script.

import type { ReactNode } from "react";
import type { Mission, TaskInbox, TwinDraft, TwinStats, TwinSummary } from "../../lib/contract";
import { Ledger, StatStrip, type LedgerColumn, type StatTile } from "../../ui";
import type { Route } from "../route";
import { barOf, beatAt, clearance, clearanceShort, handedBack, lastOf, money, num, rel, waitsOn } from "./format";
import { Icon, Meter, Portrait, Stamp } from "./marks";
import type { TwinsState } from "./types";
import { CHANNEL_LABEL, MISSION_BADGE, STATE_BADGE, WAIT, TWINS_WORDS as w } from "./words";

export interface OverviewProps {
  state: TwinsState;
  /** The twin opened in place, from the address (`#twin/<id>`). */
  open: string | null;
  now: Date;
  go: (route: Route) => void;
  onRetry: () => void;
  /** Plays the invented example instead of the daemon: offered on the first run and on a problem. */
  onExample?: () => void;
  /** Back to the daemon from the invented example. */
  onLive?: () => void;
  onSignIn: (twinId: string) => void;
  /** A paused twin goes live again. */
  onResume: (twinId: string) => void;
  onFlashOff: () => void;
}

type Mode = "loading" | "first" | "error" | "today";

/** The page as the person sees it: the daemon's twins with what they just did taken off. */
function rowsOf(state: TwinsState): TwinSummary[] {
  const page = state.page;
  if (!page) return [];
  return page.twins.map((t) => ({
    ...t,
    waiting: t.waiting.filter((d) => !state.done[d.id]),
    missions: t.missions.map((m) => (state.done[m.id] === "taken" ? { ...m, state: "resolved" as const, note: m.note } : m)),
  }));
}

const initial = (t: TwinSummary) => t.name.slice(0, 1).toUpperCase();

/** Its Gmail is no longer signed in: signing in again comes before anything else. */
const needsSignIn = (t: TwinSummary) => t.channels.some((c) => c.kind === "gmail" && c.status !== "connected");

export function Overview({ state, open, now, go, onRetry, onExample, onLive, onSignIn, onResume, onFlashOff }: OverviewProps) {
  const mode: Mode =
    state.pageLoad === "problem" ? "error" : !state.page ? "loading" : state.page.twins.length === 0 ? "first" : "today";
  const rows = mode === "today" ? rowsOf(state) : [];
  const opened = rows.find((r) => r.id === open);
  const newTwin = () => go({ view: "twin", id: null });

  let shelf: ReactNode;
  if (mode === "loading") {
    shelf = (
      <>
        <div className="wallet" aria-busy="true">
          {[1, 2, 3].map((i) => (
            <div key={i} className="booklet booklet--sk">
              <span className="sk sk--pic" />
              <span className="sk" />
              <span className="sk sk--short" />
            </div>
          ))}
        </div>
        <aside className="queue queue--sk">
          <span className="sk" />
          <span className="sk" />
          <span className="sk" />
        </aside>
      </>
    );
  } else if (mode === "first") {
    shelf = (
      <div className="invite">
        <div className="booklet booklet--blank">
          <Portrait letter="" size={64} blank />
          <span>Twin document</span>
          <span className="muted">not issued</span>
        </div>
        <div className="invite__t">
          <h2>{w.firstRunTitle}</h2>
          <p>{w.firstRunLine}</p>
          <button type="button" className="btn btn-primary btn-big" onClick={newTwin}>
            <Icon name="plus" />
            {w.firstRunGo}
          </button>
          <span className="muted">{w.firstRunHint}</span>
          {onExample && (
            <button type="button" className="btn btn-quiet" data-role="show-example" onClick={onExample}>
              {w.showExample}
            </button>
          )}
        </div>
      </div>
    );
  } else if (mode === "error") {
    shelf = (
      <div className="problem" role="alert">
        <Icon name="risk" />
        <div>
          <h2>{w.loadProblem}</h2>
          <p>
            {w.loadProblemLine} {state.pageProblem && state.pageProblem !== w.loadProblemLine ? state.pageProblem : ""}
          </p>
          <div className="problem__acts">
            <button type="button" className="btn btn-primary" onClick={onRetry}>
              <Icon name="retry" />
              {w.retry}
            </button>
            {onExample && (
              <button type="button" className="btn" data-role="show-example" onClick={onExample}>
                {w.showExample}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  } else {
    shelf = (
      <>
        {opened ? (
          <Spread t={opened} state={state} now={now} go={go} onSignIn={onSignIn} onResume={onResume} />
        ) : (
          <div className="wallet">
            {rows.map((t) => (
              <Booklet key={t.id} t={t} fresh={state.issued === t.id} go={go} />
            ))}
          </div>
        )}
        <Queue rows={rows} go={go} />
      </>
    );
  }

  const stats = state.page?.stats;
  return (
    <div className="ov" data-mode={mode}>
      <div className="ov__top">
        <div className="ov__title">
          <h1>{w.title}</h1>
          <p>{w.lead}</p>
        </div>
        <Stats stats={stats} rows={rows} mode={mode} before={state.before} />
        {onLive ? (
          <button type="button" className="btn ov__new" data-role="back-to-live" onClick={onLive}>
            <Icon name="back" />
            {w.backToLive}
          </button>
        ) : (
          <button type="button" className="btn btn-primary ov__new" onClick={newTwin}>
            <Icon name="plus" />
            {w.newTwin}
          </button>
        )}
      </div>
      <div className="shelf" data-open={String(!!opened)}>
        {shelf}
      </div>
      {state.flash && (
        <p className="flash" role="status">
          <Icon name="check" />
          <span>{state.flash}</span>
          <button type="button" className="btn btn-quiet" onClick={onFlashOff} aria-label="Dismiss">
            <Icon name="close" />
          </button>
        </p>
      )}
      <TwinLedger rows={rows} stats={stats} mode={mode} open={open} issued={state.issued} now={now} go={go} />
    </div>
  );
}

// --- the stat strip -----------------------------------------------------------------------------

function Stats({ stats: st, rows, mode, before }: { stats?: TwinStats; rows: TwinSummary[]; mode: Mode; before: TwinStats | null }) {
  if (mode === "loading") return <StatStrip tiles={[]} busy={6} label="Twins at a glance" />;
  const dash = mode !== "today" || !st;
  const moved = (k: keyof TwinStats, fmt: (v: number | undefined) => string = num) =>
    before && st && before[k] !== st[k] ? <span className="moved">was {fmt(before[k])}</span> : null;
  const tiles: StatTile[] = dash
    ? ["Live", "Waiting for you", "Missions open", "Sent this week", "Held back", "Cost this week"].map((label) => ({ key: label, label }))
    : [
        {
          key: "live",
          label: "Live",
          value: st.live,
          unit: (
            <>
              of {rows.length} {rows.length === 1 ? "twin" : "twins"}{moved("live")}
            </>
          ),
          tone: before && before.live !== st.live ? "moved" : undefined,
          draw: rows.length ? (
            <span className="dots-row" aria-hidden="true">
              {rows.map((r) => (
                <i key={r.id} data-on={String(r.state === "live")} />
              ))}
            </span>
          ) : undefined,
        },
        {
          key: "waiting",
          label: "Waiting for you",
          value: st.waiting_for_you,
          unit: "drafts and hand-backs",
          tone: st.waiting_for_you ? "human" : undefined,
        },
        { key: "missions", label: "Missions open", value: st.missions_open, unit: "conversations" },
        {
          key: "sent",
          label: "Sent this week",
          value: st.sent_week,
          unit: `${num(st.sent_alone_week)} on their own`,
          draw:
            st.sent_week && st.sent_alone_week !== undefined ? (
              <span className="split" role="img" aria-label={`${st.sent_alone_week} of ${st.sent_week} went on their own`}>
                <i style={{ flex: st.sent_alone_week }} />
                <i style={{ flex: st.sent_week - st.sent_alone_week }} />
              </span>
            ) : undefined,
        },
        { key: "held", label: "Held back", value: st.held_by_risk_week, unit: "by its risk list" },
        {
          key: "cost",
          label: "Cost this week",
          value: st.cost_usd_week === undefined ? undefined : money(st.cost_usd_week),
          unit: <>est.{moved("cost_usd_week", money)}</>,
        },
      ];
  return <StatStrip tiles={tiles} label="Twins at a glance" />;
}

// --- the wallet ---------------------------------------------------------------------------------

function VisaMark({ c }: { c: TwinSummary["channels"][number] }) {
  const ok = c.status === "connected";
  return (
    <span className="vmark" data-ok={String(ok)} title={`${CHANNEL_LABEL[c.kind]}: ${ok ? c.account : "sign in again"}`}>
      <Icon name={c.kind} />
      {CHANNEL_LABEL[c.kind]}
      {!ok && <em>sign in again</em>}
    </span>
  );
}

function ClrLine({ t, full = false }: { t: TwinSummary; full?: boolean }) {
  if (!t.channels.length) return <span className="muted">No channels yet</span>;
  return (
    <>
      {t.channels.map((c) => (
        <span key={c.kind}>
          <b>{CHANNEL_LABEL[c.kind]}</b> {full ? clearance(c) : clearanceShort(c)}
        </span>
      ))}
    </>
  );
}

function StateBadge({ t }: { t: TwinSummary }) {
  const b = STATE_BADGE[t.state];
  return (
    <span className="badge" data-tone={b.tone}>
      {b.label}
    </span>
  );
}

function Booklet({ t, fresh, go }: { t: TwinSummary; fresh: boolean; go: (r: Route) => void }) {
  const wait = waitsOn(t);
  let foot: ReactNode;
  if (t.state === "paused")
    foot = needsSignIn(t) ? (
      <button type="button" className="btn booklet__act" onClick={() => go({ view: "twin", id: t.id })}>
        <Icon name="gmail" />
        Sign in with Google
      </button>
    ) : (
      <button type="button" className="btn booklet__act" onClick={() => go({ view: "twin", id: t.id })}>
        Paused: open it
        <Icon name="arrow" />
      </button>
    );
  else if (t.state === "setting_up")
    foot = (
      <button type="button" className="btn booklet__act" onClick={() => go({ view: "twin", id: t.id })}>
        Continue with Athena
        <Icon name="arrow" />
      </button>
    );
  else if (wait)
    foot = (
      <span className="badge" data-tone="human">
        {wait} wait{wait === 1 ? "s" : ""} for you
      </span>
    );
  else foot = <span className="booklet__quiet">Nothing waits for you</span>;
  return (
    <article className="booklet" data-state={t.state} data-role="wallet-doc">
      <button type="button" className="booklet__open" aria-label={`Open ${t.name}`} onClick={() => go({ view: "twin", id: t.id })} />
      <span className="booklet__top">
        <span className="booklet__kind">Twin document</span>
        <StateBadge t={t} />
      </span>
      <span className="booklet__pic">
        <Portrait letter={initial(t)} size={64} pencil={t.state === "setting_up"} />
        {fresh && <Stamp text="Issued today" tone="success" fresh className="booklet__issued" />}
      </span>
      <span className="booklet__name">{t.name}</span>
      <span className="booklet__purpose">{t.purpose}</span>
      <span className="booklet__visas">
        {t.channels.length ? t.channels.map((c) => <VisaMark key={c.kind} c={c} />) : <span className="vmark vmark--none">No visas yet</span>}
      </span>
      <span className="booklet__clr">
        <ClrLine t={t} />
      </span>
      <span className="booklet__ready">
        <Meter value={t.readiness} />
        Readiness {t.readiness}%
      </span>
      <span className="booklet__foot">
        {t.state === "paused" && t.paused_because && <span className="booklet__why">{t.paused_because}</span>}
        {foot}
      </span>
    </article>
  );
}

// --- an opened document ---------------------------------------------------------------------------

/** The mission's beats as dots: done, the one it is on, still to come. Opens the mission's script. */
export function BeatDots({ m, onOpen }: { m: Mission; onOpen: () => void }) {
  const at = beatAt(m);
  if (!m.beats.length) return null;
  const words = at > m.beats.length ? "every beat done" : `beat ${at} of ${m.beats.length}: ${m.beats[at - 1]!.label}`;
  return (
    <button type="button" className="beats" data-role="beat-dots" onClick={onOpen} title={`Open the script: ${words}`} aria-label={`Open the script, ${words}`}>
      {m.beats.map((b, i) => (
        <i key={i} data-done={String(b.done)} data-now={String(i + 1 === at)} />
      ))}
      <span className="beats__w">{at > m.beats.length ? "done" : `${at} of ${m.beats.length}`}</span>
    </button>
  );
}

function MissionRow({ m, t, now, go }: { m: Mission; t: TwinSummary; now: Date; go: (r: Route) => void }) {
  const badge = MISSION_BADGE[m.state];
  const open = () => go({ view: "twin_mission", id: t.id, mission: m.id });
  return (
    <li className="ms" data-state={m.state}>
      <div className="ms__h">
        <b>{m.title}</b>
        {m.source === "notion" && (
          <span className="tag" title="It took this one from the page it reads for new missions">
            from your inbox
          </span>
        )}
        <span className="badge" data-tone={badge.tone}>
          {badge.label}
        </span>
      </div>
      <div className="ms__m">
        {m.with} · {CHANNEL_LABEL[m.channel]} · <BeatDots m={m} onOpen={open} /> · {rel(m.last_at, now)}
      </div>
      {m.state === "handed_back" ? (
        <p className="ms__note ms__note--stop">
          <Icon name="hand" />
          <span>
            <b>It stopped:</b> {m.note}
          </span>
        </p>
      ) : (
        m.note && <p className="ms__note">{m.note}</p>
      )}
    </li>
  );
}

function DraftRow({ d, t, go }: { d: TwinDraft; t: TwinSummary; go: (r: Route) => void }) {
  const ms = t.missions.find((m) => m.id === d.mission);
  const bar = barOf(d, t);
  return (
    <li className="dr" data-why={d.reason === "risk" ? "held" : "below_bar"}>
      <button type="button" className="dr__btn" onClick={() => go({ view: "twin_draft", id: t.id, draft: d.id })}>
        <span className="dr__h">
          <b>{d.subject}</b>
          <DraftStamp d={d} bar={bar} />
        </span>
        <span className="dr__to">
          to {d.to}
          {ms && ms.with !== d.to ? ` · ${ms.with}` : ""}
        </span>
        <span className="dr__x">{d.text}</span>
      </button>
    </li>
  );
}

export function DraftStamp({ d, bar, fresh = false }: { d: TwinDraft; bar?: number; fresh?: boolean }) {
  if (d.reason === "risk") return <Stamp text="Held" tone="warning" sub="risk list" fresh={fresh} />;
  if (d.reason === "below_bar") return <Stamp text="Not sure enough" tone="human" sub={`${d.confidence} of ${bar ?? "-"}`} fresh={fresh} />;
  return <Stamp text="Waits for you" tone="human" sub="your signature" fresh={fresh} />;
}

function PausedCard({
  t,
  state,
  onSignIn,
  onResume,
}: {
  t: TwinSummary;
  state: TwinsState;
  onSignIn: (id: string) => void;
  onResume: (id: string) => void;
}) {
  const s = state.signin?.twin === t.id ? state.signin.state : "idle";
  const done = s === "connected" || t.state === "live";
  // Google asked to sign in again: that first. Else the person paused it, and it goes live again.
  const signIn = needsSignIn(t);
  let act: ReactNode = signIn ? (
    <>
      <button type="button" className="btn btn-primary btn-big" onClick={() => onSignIn(t.id)}>
        <Icon name="gmail" />
        Sign in with Google
      </button>
      <span className="muted">One press. It asks for the same things as before: read and send mail.</span>
    </>
  ) : (
    <>
      <button type="button" className="btn btn-primary btn-big" data-role="resume" onClick={() => onResume(t.id)}>
        <Icon name="arrow" />
        Go live again
      </button>
      <span className="muted">Its document stands as it was. Every draft still passes the send rule.</span>
    </>
  );
  if (s === "waiting")
    act = (
      <div className="cstate" data-state="waiting">
        <span className="spin" aria-hidden="true" />
        <div>
          <b>Waiting for you in the browser. Google&apos;s sign-in page opened there.</b>
          <span>It stops waiting after 10 minutes.</span>
        </div>
      </div>
    );
  if (done)
    act = (
      <div className="cstate" data-state="connected">
        <Stamp text="Stamped" tone="success" fresh />
        <div>
          <b>{signIn || s === "connected" ? `Signed in again as ${t.channels[0]?.account}` : "Live again"}</b>
          <span>{t.name} is live.</span>
        </div>
      </div>
    );
  return (
    <div className="paused" data-state={done ? "done" : s}>
      <span className="paused__k">
        <Icon name="risk" />
        {done ? "Back to work" : "Paused"}
      </span>
      <p>
        <b>{t.paused_because ?? "Google asked you to sign in again."}</b> {done ? "" : "It sends nothing while paused, and nothing was lost."}
      </p>
      {act}
    </div>
  );
}

/** The task inbox at work: the page it reads, what it took, and the lines it could not place. */
function InboxLine({ inbox, now }: { inbox: TaskInbox; now: Date }) {
  const n = inbox.unplaced.length;
  return (
    <div className="inbox" data-role="inbox" data-problem={String(!!inbox.problem || n > 0)}>
      <p className="inbox__l">
        <Icon name="notion" />
        <span>
          <b>Task inbox</b> reads &lsquo;{inbox.title}&rsquo; · {inbox.taken} taken
          {inbox.checked_at ? ` · read ${rel(inbox.checked_at, now)}` : " · not read yet"}
        </span>
      </p>
      {inbox.problem && <p className="inbox__x">{inbox.problem}</p>}
      {n > 0 && (
        <details className="inbox__x">
          <summary>
            {n} line{n === 1 ? "" : "s"} it could not place, left as you wrote {n === 1 ? "it" : "them"}
          </summary>
          <ul>
            {inbox.unplaced.map((u) => (
              <li key={u}>{u}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function Spread({
  t,
  state,
  now,
  go,
  onSignIn,
  onResume,
}: {
  t: TwinSummary;
  state: TwinsState;
  now: Date;
  go: (r: Route) => void;
  onSignIn: (id: string) => void;
  onResume: (id: string) => void;
}) {
  const missions = (
    <>
      {t.missions.length ? (
        <ul className="mss">
          {t.missions.map((m) => (
            <MissionRow key={m.id} m={m} t={t} now={now} go={go} />
          ))}
        </ul>
      ) : (
        <p className="empty">No missions yet.</p>
      )}
      {t.inbox && <InboxLine inbox={t.inbox} now={now} />}
    </>
  );
  // the document's entries: a live or paused twin takes a new mission from here
  const give =
    t.state !== "setting_up" && t.channels.some((c) => c.kind === "gmail") ? (
      <button type="button" className="btn ovpage__give" data-role="give-mission" onClick={() => go({ view: "twin_entry", id: t.id })}>
        <Icon name="plus" />
        {w.giveMission}
      </button>
    ) : null;
  const drafts = t.waiting.length ? (
    <ul className="drs">
      {t.waiting.map((d) => (
        <DraftRow key={d.id} d={d} t={t} go={go} />
      ))}
    </ul>
  ) : (
    <p className="empty">
      <Icon name="check" />
      Nothing waits for your signature.
    </p>
  );
  let left: ReactNode = (
    <section className="ovpage">
      <h3>
        Missions <span>{t.missions.length}</span>
        {give}
      </h3>
      {missions}
    </section>
  );
  let right: ReactNode = (
    <section className="ovpage">
      <h3>
        Waiting for your signature <span>{t.waiting.length}</span>
      </h3>
      {drafts}
    </section>
  );
  if (t.state === "paused" || state.signin?.twin === t.id) {
    left = (
      <section className="ovpage">
        <PausedCard t={t} state={state} onSignIn={onSignIn} onResume={onResume} />
      </section>
    );
    right = (
      <section className="ovpage">
        <h3>
          Missions <span>{t.missions.length}</span>
          {give}
        </h3>
        {missions}
      </section>
    );
  }
  if (t.state === "setting_up") {
    left = (
      <section className="ovpage">
        <div className="paused" data-tone="info">
          <span className="paused__k">
            <Icon name="pencil" />
            Being issued
          </span>
          <p>
            <b>Readiness {t.readiness}%.</b> Athena picks up where you left off.
          </p>
          <button type="button" className="btn btn-primary btn-big" onClick={() => go({ view: "twin", id: t.id })}>
            Continue with Athena
            <Icon name="arrow" />
          </button>
        </div>
      </section>
    );
  }
  return (
    <article className="ovspread" data-id={t.id}>
      <header className="ovspread__h">
        <Portrait letter={initial(t)} size={40} pencil={t.state === "setting_up"} />
        <div className="ovspread__t">
          <b>{t.name}</b>
          <span>{t.purpose}</span>
        </div>
        <StateBadge t={t} />
        {state.issued === t.id && <Stamp text="Issued today" tone="success" fresh />}
        <span className="ovspread__clr">
          <ClrLine t={t} full />
        </span>
        <button type="button" className="btn btn-quiet" aria-label="Close the document" onClick={() => go({ view: "twins" })}>
          <Icon name="close" />
          Close
        </button>
      </header>
      <div className="ovspread__pages">
        {left}
        {right}
      </div>
    </article>
  );
}

// --- waiting for you ----------------------------------------------------------------------------

/** A two-line waiting card: whose and why, then what. It opens the draft beside the message it answers. */
function WaitingCard({ kind, twin, why, what, onOpen }: { kind: "draft" | "hand" | "also"; twin: string; why: string; what: string; onOpen: () => void }) {
  return (
    <button type="button" className={`q ${kind === "hand" ? "q--hand" : kind === "also" ? "q--also" : ""}`} data-role="waiting-card" onClick={onOpen}>
      <span className="q__k">
        <Icon name={kind === "draft" ? "mail" : kind === "hand" ? "hand" : "risk"} />
        {twin}
        {why && <span className="q__s"> · {why}</span>}
      </span>
      <b>{what}</b>
    </button>
  );
}

function Queue({ rows, go }: { rows: TwinSummary[]; go: (r: Route) => void }) {
  const items: ReactNode[] = [];
  const also: ReactNode[] = [];
  for (const t of rows) {
    for (const d of t.waiting) {
      // why it waits: its risk list, how sure it was against the bar, or the level its message is on
      const why =
        d.reason === "risk"
          ? `Held: ${d.risks.length} on its risk list`
          : d.reason === "below_bar"
            ? `Not sure enough: ${d.confidence} of ${barOf(d, t) ?? "-"}`
            : WAIT[d.reason ?? "assist"];
      items.push(<WaitingCard key={d.id} kind="draft" twin={t.name} why={why} what={d.subject} onOpen={() => go({ view: "twin_draft", id: t.id, draft: d.id })} />);
    }
    for (const m of handedBack(t)) {
      items.push(
        <WaitingCard
          key={m.id}
          kind="hand"
          twin={t.name}
          why={`${(m.note ?? "").split(".")[0]}.`}
          what={`${m.with}: handed back to you`}
          onOpen={() => go({ view: "twin_mission", id: t.id, mission: m.id })}
        />,
      );
    }
    if (t.state === "paused")
      also.push(
        <WaitingCard
          key={t.id}
          kind="also"
          twin={`${t.name}: paused`}
          why=""
          what={needsSignIn(t) ? "Sign in with Google again" : "Go live again when you are ready"}
          onOpen={() => go({ view: "twin", id: t.id })}
        />,
      );
  }
  return (
    <aside className="queue" aria-label={w.waitingForYou}>
      <h2>
        {w.waitingForYou} <span className="count">{items.length}</span>
      </h2>
      {items.length ? (
        <div className="q__list">{items}</div>
      ) : (
        <p className="empty">
          <Icon name="check" />
          {w.nothingWaits}
        </p>
      )}
      {also.length > 0 && (
        <>
          <span className="q__also">{w.also}</span>
          <div className="q__list">{also}</div>
        </>
      )}
    </aside>
  );
}

// --- the ledger ---------------------------------------------------------------------------------

function TwinLedger({
  rows,
  stats,
  mode,
  open,
  issued,
  now,
  go,
}: {
  rows: TwinSummary[];
  stats?: TwinStats;
  mode: Mode;
  open: string | null;
  issued: string | null;
  now: Date;
  go: (r: Route) => void;
}) {
  const columns: LedgerColumn<TwinSummary>[] = [
    {
      key: "twin",
      head: "Twin",
      cellClassName: "lg__twin",
      cell: (t) => (
        <>
          <b>{t.name}</b>
          <span>{t.purpose}</span>
        </>
      ),
    },
    { key: "state", head: "State", cell: (t) => <StateBadge t={t} /> },
    {
      key: "where",
      head: "Where it speaks",
      cellClassName: "lg__ch",
      cell: (t) =>
        t.channels.length ? (
          t.channels.map((c) => (
            <span key={c.kind} className="lg__c" data-ok={String(c.status === "connected")} title={c.account}>
              <Icon name={c.kind} />
              {CHANNEL_LABEL[c.kind]}
              {c.status === "connected" ? <i data-health={c.health} aria-label={c.health} /> : <em>sign in</em>}
            </span>
          ))
        ) : (
          <span className="muted">-</span>
        ),
    },
    {
      key: "alone",
      head: "May send alone",
      cellClassName: "lg__clr",
      cell: (t) =>
        t.channels.length ? (
          t.channels.map((c) => (
            <span key={c.kind} title={clearance(c)}>
              {CHANNEL_LABEL[c.kind]}: {clearanceShort(c)}
            </span>
          ))
        ) : (
          <span className="muted">-</span>
        ),
    },
    {
      key: "ready",
      head: "Readiness",
      cellClassName: "lg__ready",
      cell: (t) => (
        <>
          <Meter value={t.readiness} />
          {t.readiness}%
        </>
      ),
    },
    {
      key: "waiting",
      head: "Waiting",
      cellClassName: "lg__n lg__wait",
      cell: (t) => {
        const wait = t.waiting.length;
        const hb = handedBack(t).length;
        if (!wait && !hb) return "0";
        return (
          <>
            {wait > 0 && (
              <b>
                {wait} draft{wait === 1 ? "" : "s"}
              </b>
            )}
            {hb > 0 && <b>{hb} handed back</b>}
          </>
        );
      },
    },
    { key: "missions", head: "Missions", cellClassName: "lg__n", cell: (t) => t.open_missions },
    {
      key: "week",
      head: "This week",
      cellClassName: "lg__wk",
      cell: (t) =>
        t.week.sent === undefined ? (
          "-"
        ) : (
          <>
            {t.week.sent} sent<span>{num(t.week.sent_alone)} alone</span>
          </>
        ),
    },
    { key: "last", head: "Last", cellClassName: "lg__last", cell: (t) => rel(lastOf(t), now) },
  ];
  const st = stats;
  const totals =
    mode === "today" && st
      ? [
          <b key="n">{rows.length} {rows.length === 1 ? "twin" : "twins"}</b>,
          `${st.live} live`,
          `${st.waiting_for_you} waiting for you · ${st.missions_open} missions open · ${num(st.sent_week)} sent this week, ${num(st.sent_alone_week)} on their own · ${num(st.held_by_risk_week)} held back · est. ${money(st.cost_usd_week)}`,
        ]
      : undefined;
  const empty = mode === "loading" ? undefined : mode === "first" ? w.noTwins : mode === "error" ? w.notLoaded : undefined;
  if (mode === "loading") {
    return (
      <table className="ledger" aria-busy="true" aria-label={w.ledger}>
        <tbody>
          {[1, 2, 3].map((i) => (
            <tr key={i} className="lg__row lg__sk">
              <td>
                <span className="sk" />
              </td>
              <td>
                <span className="sk" />
              </td>
              <td>
                <span className="sk" />
              </td>
              <td>
                <span className="sk" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  return (
    <Ledger
      className="ledger"
      label={w.ledger}
      columns={columns}
      rows={rows}
      rowKey={(t) => t.id}
      headClassName="lg__row lg__head"
      rowClassName="lg__row"
      rowProps={(t) => ({
        tabIndex: 0,
        "aria-expanded": open === t.id,
        "data-role": "ledger-row",
        "data-new": issued === t.id ? "true" : undefined,
        "data-human": waitsOn(t) ? "true" : undefined,
        onClick: () => go(open === t.id ? { view: "twins" } : { view: "twin", id: t.id }),
        onKeyDown: (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            go(open === t.id ? { view: "twins" } : { view: "twin", id: t.id });
          }
        },
      })}
      empty={empty}
      emptyClassName="lg__empty"
      totals={totals}
      totalsClassName="lg__row lg__total"
      totalsCellClassNames={[undefined, undefined, "lg__wide"]}
    />
  );
}

