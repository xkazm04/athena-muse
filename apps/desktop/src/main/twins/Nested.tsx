// The three nested pages (the owner's rule: in the main page a stat or a small part, on click a page
// designed for it). Its voice: a message from the other side and its reply in its current voice, with
// what changed it. A mission: the conversation as a script of beats beside its turns. A draft: the
// message it answers beside it, how sure it was against the bar, its risk list, sign / edit / decline.

import { useState, type ReactNode } from "react";
import type { Mission, MissionTurn, TwinDetail, TwinDraft, TwinSummary } from "../../lib/contract";
import type { Route } from "../route";
import { barOf, beatAt, day, rel } from "./format";
import { Icon, Portrait, Stamp, Sure } from "./marks";
import { DraftStamp } from "./Overview";
import { piecesAt } from "./select";
import { CHANNEL_LABEL, MISSION_BADGE, WAIT } from "./words";

interface PageProps {
  twin: TwinSummary;
  kicker: string;
  title: string;
  sub?: ReactNode;
  badge?: ReactNode;
  back: Route;
  backLabel: string;
  go: (r: Route) => void;
  left: ReactNode;
  right: ReactNode;
  role: string;
}

/** A nested page: the twin's header, then two facing pages, like its document. */
function NestedPage({ twin, kicker, title, sub, badge, back, backLabel, go, left, right, role }: PageProps) {
  return (
    <article className="npage" data-role={role} aria-label={`${kicker}: ${title}`}>
      <header className="npage__h">
        <Portrait letter={twin.name[0] ?? "T"} size={40} pencil={twin.state === "setting_up"} />
        <div className="npage__t">
          <span className="npage__k">
            {twin.name} · {kicker}
          </span>
          <b>{title}</b>
          {sub && <span className="npage__s">{sub}</span>}
        </div>
        {badge}
        <button type="button" className="btn btn-quiet npage__back" onClick={() => go(back)}>
          <Icon name="back" />
          {backLabel}
        </button>
      </header>
      <div className="npage__pages">
        <section className="npage__page">{left}</section>
        <section className="npage__page">{right}</section>
      </div>
    </article>
  );
}

function Missing({ what, back, go }: { what: string; back: Route; go: (r: Route) => void }) {
  return (
    <div className="problem" role="alert">
      <Icon name="risk" />
      <div>
        <h2>{what}</h2>
        <p>It may have been signed, declined or finished since. Nothing was changed.</p>
        <button type="button" className="btn btn-primary" onClick={() => go(back)}>
          <Icon name="back" />
          Back to your twins
        </button>
      </div>
    </div>
  );
}

const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter((x) => /^[A-Za-z]/.test(x))
    .map((x) => x[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

function Bubble({ t, twin, other, now }: { t: MissionTurn; twin: TwinSummary; other: string; now: Date }) {
  const mine = t.side === "twin";
  const text = t.edited_text ?? t.text;
  let stamp: ReactNode = null;
  if (mine && t.decision === "sent_alone") stamp = <Stamp text="Sent on its own" tone="success" />;
  else if (mine && t.mark === "edited") stamp = <Stamp text="You edited" tone="human" sub="and signed" />;
  else if (mine && t.decision === "waits") stamp = <Stamp text={t.mark ? "Signed" : t.reason === "risk" ? "Held" : "Waits for you"} tone={t.mark ? "human" : t.reason === "risk" ? "warning" : "human"} />;
  return (
    <li className={`nturn ${mine ? "nturn--twin" : "nturn--other"}`}>
      <span className="nturn__who">
        {mine ? <Portrait letter={twin.name[0] ?? "T"} size={22} /> : <span className="av">{initials(other)}</span>}
        <b>{mine ? twin.name : other}</b>
        <span>{rel(t.at, now)}</span>
        {stamp}
      </span>
      <p className="nturn__text">{text}</p>
      {mine && t.learned && (
        <p className="learned">
          <Icon name="layers" />
          <span>
            <b>It learned:</b> {t.learned}
          </span>
        </p>
      )}
    </li>
  );
}

// --- its voice ------------------------------------------------------------------------------------

/** The latest exchange it took part in: the other side's message and its reply. */
function exchangeOf(d: TwinDetail | undefined, t: TwinSummary): { theirs?: MissionTurn; mine?: MissionTurn; with: string } {
  const sources: Mission[] = [...(d?.rehearsal ? [d.rehearsal] : []), ...t.missions];
  for (const m of sources) {
    const i = m.turns.map((x) => x.side).lastIndexOf("twin");
    if (i < 0) continue;
    const learned = m.turns.findIndex((x) => x.side === "twin" && x.learned);
    const at = learned >= 0 ? learned : i;
    const theirs = [...m.turns.slice(0, at)].reverse().find((x) => x.side === "other");
    return { theirs, mine: m.turns[at], with: m.with.replace(/\s*\(practice\)$/, "") };
  }
  return { with: "" };
}

export function VoicePage({ twin, detail, now, go }: { twin: TwinSummary; detail?: TwinDetail; now: Date; go: (r: Route) => void }) {
  const back: Route = { view: "twin", id: twin.id };
  const ex = exchangeOf(detail, twin);
  const traits = piecesAt(detail ?? null, "voice");
  const sample = detail?.samples.find((s) => s.picked);
  const own = (detail?.dials ?? []).filter((d) => d.source !== "learned");
  const left = (
    <>
      <h3>
        Their message <span>{ex.with || "no one yet"}</span>
      </h3>
      {ex.theirs ? (
        <ul className="nturns">
          <Bubble t={ex.theirs} twin={twin} other={ex.with} now={now} />
        </ul>
      ) : (
        <p className="empty">It has not answered anyone yet. Its first draft shows here once it rehearses.</p>
      )}
      {sample && (
        <blockquote className="specimen">
          <span className="specimen__t">
            <span className="specimen__k">
              Learned from your mail to {sample.to}, {day(sample.date)}:
            </span>{" "}
            {sample.excerpt}
          </span>
        </blockquote>
      )}
    </>
  );
  const right = (
    <>
      <h3>
        Its reply, in its voice now <span>{ex.mine ? rel(ex.mine.at, now) : ""}</span>
      </h3>
      {ex.mine && (
        <ul className="nturns">
          <Bubble t={ex.mine} twin={twin} other={ex.with} now={now} />
        </ul>
      )}
      <h4 className="npage__k">What shapes it</h4>
      {traits.length ? (
        <ul className="pcs pcs--lines pcs--voice">
          {traits.map((p) => (
            <li key={p.id} className="pc" data-state={p.confirmed ? "ink" : "pencil"} data-origin={p.origin}>
              <span className="pc__l">{p.label}</span>
              {p.evidence?.length ? <span className="pc__ev">from {p.evidence.length} of your mails</span> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty">Its voice lines show once it has learned from your sent mail.</p>
      )}
      {own.length > 0 && (
        <p className="npage__own">
          Set by you or a preset, not your mail:{" "}
          {own.map((d) => `${d.label.toLowerCase()} ${d.value} of 5 (${d.source === "you" ? "you" : "preset"})`).join(", ")}
        </p>
      )}
    </>
  );
  return (
    <NestedPage
      twin={twin}
      kicker="Voice"
      title="How it sounds"
      sub="A message from the other side and its reply, in its voice now, with what shapes it."
      back={back}
      backLabel="Its document"
      go={go}
      left={left}
      right={right}
      role="voice-page"
    />
  );
}

// --- a mission's script ---------------------------------------------------------------------------

export function MissionPage({
  twin,
  mission,
  now,
  go,
  onTakeOver,
}: {
  twin: TwinSummary;
  mission?: Mission;
  now: Date;
  go: (r: Route) => void;
  onTakeOver: (id: string) => void;
}) {
  const back: Route = { view: "twin", id: twin.id };
  if (!mission) return <Missing what="That mission is not here" back={{ view: "twins" }} go={go} />;
  const at = beatAt(mission);
  const badge = MISSION_BADGE[mission.state];
  const draft = mission.turns.find((t) => t.draft && t.decision === "waits" && !t.mark);
  const left = (
    <>
      <h3>
        The script <span>{at > mission.beats.length ? "every beat done" : `beat ${at} of ${mission.beats.length}`}</span>
      </h3>
      <ol className="script">
        {mission.beats.map((b, i) => (
          <li key={i} className="beat" data-done={String(b.done)} data-now={String(i + 1 === at)}>
            <span className="beat__n">{b.done ? <Icon name="check" /> : i + 1}</span>
            <span className="beat__l">{b.label}</span>
            {i + 1 === at && mission.state !== "resolved" && (
              <span className="beat__w">{mission.state === "handed_back" ? "handed back to you" : draft ? "waits for your signature" : "it is on this one"}</span>
            )}
          </li>
        ))}
      </ol>
      {mission.note && (
        <p className={`ms__note ${mission.state === "handed_back" ? "ms__note--stop" : ""}`.trim()}>
          {mission.state === "handed_back" && <Icon name="hand" />}
          <span>
            {mission.state === "handed_back" && <b>It stopped: </b>}
            {mission.note}
          </span>
        </p>
      )}
      {mission.state === "handed_back" && (
        <div className="ms__act">
          <button type="button" className="btn btn-primary" onClick={() => onTakeOver(mission.id)}>
            <Icon name="hand" />
            Take it over
          </button>
        </div>
      )}
    </>
  );
  const right = (
    <>
      <h3>
        The conversation <span>{mission.turns.length ? `${mission.turns.length} turns kept` : ""}</span>
      </h3>
      {mission.turns.length ? (
        <ul className="nturns">
          {mission.turns.map((t) => (
            <Bubble key={t.id} t={t} twin={twin} other={mission.with.replace(/\s*\(practice\)$/, "")} now={now} />
          ))}
        </ul>
      ) : (
        <p className="empty">The messages of this mission live in your mail; none are kept here.</p>
      )}
      {draft?.draft && (
        <button type="button" className="btn btn-primary npage__go" onClick={() => go({ view: "twin_draft", id: twin.id, draft: draft.draft! })}>
          Open the draft that waits
          <Icon name="arrow" />
        </button>
      )}
    </>
  );
  return (
    <NestedPage
      twin={twin}
      kicker="Mission"
      title={mission.title}
      sub={`${mission.with} · ${CHANNEL_LABEL[mission.channel]} · ${rel(mission.last_at, now)}`}
      badge={
        <span className="badge" data-tone={badge.tone}>
          {badge.label}
        </span>
      }
      back={back}
      backLabel="Its document"
      go={go}
      left={left}
      right={right}
      role="mission-page"
    />
  );
}

// --- a draft beside the message it answers --------------------------------------------------------

export function DraftPage({
  twin,
  draft,
  now,
  go,
  onSign,
  onDecline,
}: {
  twin: TwinSummary;
  draft?: TwinDraft;
  now: Date;
  go: (r: Route) => void;
  onSign: (d: TwinDraft, text?: string) => Promise<void>;
  onDecline: (d: TwinDraft) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(draft?.text ?? "");
  const [busy, setBusy] = useState(false);
  if (!draft) return <Missing what="That draft no longer waits" back={{ view: "twins" }} go={go} />;
  const bar = barOf(draft, twin);
  const ms = twin.missions.find((m) => m.id === draft.mission);
  const why =
    draft.reason === "risk"
      ? `It was ${draft.confidence} sure${bar !== undefined ? ` (your bar ${bar})` : ""}, but its risk list is not empty, so it waits for your signature.`
      : draft.reason === "below_bar"
        ? `Its risk list is empty, but ${draft.confidence} is below your bar of ${bar ?? "-"}, so it waits for your signature.`
        : `${WAIT[draft.reason ?? "assist"]}.`;
  const act = async (run: () => Promise<void>) => {
    setBusy(true);
    await run();
    setBusy(false);
    go({ view: "twins" });
  };
  const left = (
    <>
      <h3>
        Their message <span>{ms ? ms.with : draft.to}</span>
      </h3>
      {draft.answers ? (
        <blockquote className="theirs">
          <span className="theirs__who">
            {ms?.with ?? draft.to} · {rel(ms?.last_at ?? draft.created, now)}
          </span>
          <p>{draft.answers}</p>
        </blockquote>
      ) : (
        <p className="empty">The message it answers was not kept with this draft. Its subject: {draft.subject}.</p>
      )}
      {ms && (
        <p className="ms__note">
          Part of the mission &quot;{ms.title}&quot;. {ms.note}
        </p>
      )}
    </>
  );
  const right = (
    <>
      <h3>
        Its draft <span>to {draft.to}</span>
      </h3>
      {editing ? (
        <>
          <label className="sr" htmlFor="draft-edit">
            Your version
          </label>
          <textarea id="draft-edit" className="field editbox" rows={5} value={text} onChange={(e) => setText(e.target.value)} />
        </>
      ) : (
        <p className="dr__full">{draft.text}</p>
      )}
      <div className="dr__grid">
        <Sure value={draft.confidence} bar={bar} />
        {draft.risks.length ? (
          <ul className="risks" aria-label="Its risk list">
            {draft.risks.map((x) => (
              <li key={x}>
                <Icon name="risk" />
                {x}
              </li>
            ))}
          </ul>
        ) : (
          <p className="risks risks--none">
            <Icon name="check" />
            Its risk list is empty.
          </p>
        )}
      </div>
      <p className="dr__why">{why}</p>
      <div className="dr__act">
        {editing ? (
          <>
            <button type="button" className="btn btn-primary" disabled={busy || !text.trim()} onClick={() => void act(() => onSign(draft, text))}>
              <Icon name="send" />
              Sign and send yours
            </button>
            <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void act(() => onSign(draft))}>
              <Icon name="send" />
              Sign and send
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => setEditing(true)}>
              <Icon name="pencil" />
              Edit
            </button>
            <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => void act(() => onDecline(draft))}>
              Decline
            </button>
          </>
        )}
      </div>
    </>
  );
  return (
    <NestedPage
      twin={twin}
      kicker="Draft"
      title={draft.subject}
      sub={`to ${draft.to}${ms ? ` · ${ms.with} mission` : " · no mission"}`}
      badge={<DraftStamp d={draft} bar={bar} />}
      back={{ view: "twins" }}
      backLabel="Your twins"
      go={go}
      left={left}
      right={right}
      role="draft-page"
    />
  );
}
