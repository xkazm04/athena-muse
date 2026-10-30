// The new entry (Passport): giving a live twin a mission from its document. A nested page: on the left,
// who it is with (a recent Gmail conversation, the ones where they wrote last first, or someone new by
// their address); on the right, the working slip: the goal in the person's own words, up to three of
// Athena's suggestions in pencil, and which part of the send rule its first message meets. Start sends
// it to the daemon, and the new mission's script opens.

import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Autonomy, Mission, NewMissionBody, ThreadSummary, TwinSummary } from "../../lib/contract";
import type { Route } from "../route";
import { rel } from "./format";
import { Icon } from "./marks";
import { NestedPage } from "./Nested";
import { goalsKey } from "./store";
import type { EntryPick, EntryView, GoalsView } from "./types";
import { ENTRY_WORDS as e } from "./words";

export interface EntryPageProps {
  twin: TwinSummary;
  entry?: EntryView;
  goals: Record<string, GoalsView>;
  /** Her suggestions are labelled simulated on the scripted engine. */
  simulated: boolean;
  now: Date;
  go: (r: Route) => void;
  onThreads?: () => void;
  onGoals?: (pick: EntryPick) => void;
  onStart: (body: NewMissionBody) => Promise<{ mission?: Mission; problem: string }>;
}

const GOAL_MAX = 400;
const ADDRESS = /^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$/;

/** Which part of the send rule its first message here meets, in plain words. */
export function ruleFor(twin: TwinSummary, pick: EntryPick | null, thread?: ThreadSummary): string {
  const gmail = twin.channels.find((c) => c.kind === "gmail");
  if (!gmail) return e.noGmail;
  if (!pick) return e.ruleUnchosen;
  const kind = "to" in pick ? "first_message" : "reply";
  const level: Autonomy = gmail.split ? gmail.split[kind] : gmail.autonomy;
  const what = kind === "first_message" ? e.firstMessage : thread?.theirs_last === false ? e.answersNext : e.reply;
  const how = level === "auto" ? e.onAuto(gmail.bar) : level === "assist" ? e.onAssist : e.onReview;
  const paused = twin.state === "live" ? "" : ` ${e.paused}`;
  return `${what}: ${how}.${paused}`;
}

function ThreadRow({
  t,
  on,
  busy,
  now,
  onPick,
}: {
  t: ThreadSummary;
  on: boolean;
  busy: boolean;
  now: Date;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      className="row entry-row"
      aria-pressed={on}
      disabled={busy}
      data-role="entry-thread"
      data-id={t.id}
      onClick={onPick}
      title={busy ? e.hasMission : undefined}
    >
      <span className="tick tick--round" data-on={String(on)} data-by="you" aria-hidden="true">
        {on && <Icon name="check" />}
      </span>
      <span className="row__m">
        <span className="row__t">
          <b>{t.with}</b>
          <span>{t.subject}</span>
        </span>
        <span className="row__x">{t.snippet}</span>
      </span>
      <span className="entry-row__at">
        {busy ? <span className="tag">{e.hasMission}</span> : rel(t.last_at, now)}
      </span>
    </button>
  );
}

export function EntryPage({ twin, entry, goals, simulated, now, go, onThreads, onGoals, onStart }: EntryPageProps) {
  const [pick, setPick] = useState<EntryPick | null>(null);
  const [to, setTo] = useState("");
  const [goal, setGoal] = useState("");
  const [starting, setStarting] = useState(false);
  const [problem, setProblem] = useState("");
  const back: Route = { view: "twin", id: twin.id };

  // the conversations are read again each time the slip opens: new mail may have come in
  const read = useRef(onThreads);
  useEffect(() => read.current?.(), []);

  const threads = entry?.threads ?? [];
  const busy = new Set(twin.missions.filter((m) => m.state === "open" && m.thread).map((m) => m.thread!));
  const theirs = threads.filter((t) => t.theirs_last);
  const mine = threads.filter((t) => !t.theirs_last);
  const chosen = pick && "thread" in pick ? threads.find((t) => t.id === pick.thread) : undefined;
  const newOn = !!pick && "to" in pick;
  const shown = pick ? goals[goalsKey(twin.id, pick)] : undefined;
  const ready = !!pick && goal.trim().length > 0 && goal.trim().length <= GOAL_MAX && !starting;

  const choose = (p: EntryPick) => {
    setPick(p);
    setProblem("");
    onGoals?.(p);
  };
  const chooseNew = () => {
    const address = to.trim();
    if (!address || (pick && "to" in pick && pick.to === address)) return;
    if (!ADDRESS.test(address)) {
      setProblem(e.oneAddress);
      return;
    }
    choose({ to: address });
  };

  const start = async (ev?: FormEvent) => {
    ev?.preventDefault();
    if (!pick || !ready) return;
    setStarting(true);
    setProblem("");
    const body: NewMissionBody = { thread: "thread" in pick ? pick.thread : pick.to, goal: goal.trim() };
    const done = await onStart(body);
    setStarting(false);
    if (done.mission) go({ view: "twin_mission", id: twin.id, mission: done.mission.id });
    else setProblem(done.problem);
  };

  let list;
  if (!entry || (entry.load === "reading" && !entry.threads.length)) {
    list = (
      <p className="empty" role="status">
        <span className="spin" aria-hidden="true" /> {e.reading}
      </p>
    );
  } else if (entry.load === "problem") {
    list = (
      <div className="problem" role="alert">
        <Icon name="risk" />
        <div>
          <p>{entry.problem}</p>
          {onThreads && (
            <button type="button" className="btn" onClick={onThreads}>
              <Icon name="retry" />
              Try again
            </button>
          )}
        </div>
      </div>
    );
  } else {
    const group = (label: string, items: ThreadSummary[]) =>
      items.length > 0 && (
        <>
          <span className="rows__k">{label}</span>
          {items.map((t) => (
            <ThreadRow
              key={t.id}
              t={t}
              on={!!chosen && chosen.id === t.id}
              busy={busy.has(t.id)}
              now={now}
              onPick={() => choose({ thread: t.id })}
            />
          ))}
        </>
      );
    list = (
      <>
        {threads.length === 0 && <p className="empty">{e.noThreads}</p>}
        {group(e.theirsLast, theirs)}
        {group(e.mineLast, mine)}
      </>
    );
  }

  const left = (
    <>
      <h3>
        {e.withWhom} <span>{entry?.load === "ready" ? e.recent(threads.length) : ""}</span>
      </h3>
      <div className="rows entry-list" data-role="entry-threads">
        {list}
        <span className="rows__k">{e.someoneNew}</span>
        <div className="row entry-new" aria-pressed={newOn} data-role="entry-new">
          <span className="tick tick--round" data-on={String(newOn)} data-by="you" aria-hidden="true">
            {newOn && <Icon name="check" />}
          </span>
          <label className="sr" htmlFor="entry-to">
            {e.theirAddress}
          </label>
          <input
            id="entry-to"
            className="field"
            type="email"
            value={to}
            placeholder={e.theirAddress}
            onChange={(ev) => setTo(ev.target.value)}
            onBlur={chooseNew}
            onKeyDown={(ev) => {
              if (ev.key === "Enter") {
                ev.preventDefault();
                chooseNew();
              }
            }}
          />
          <button type="button" className="btn" onClick={chooseNew} disabled={!to.trim()}>
            {e.writeTo}
          </button>
        </div>
      </div>
    </>
  );

  const withLine = chosen ? (
    <>
      With <b>{chosen.with}</b>: {chosen.theirs_last ? e.answering : e.waitingOnThem}
    </>
  ) : pick && "to" in pick ? (
    <>
      With <b>{pick.to}</b>: {e.startsNew}
    </>
  ) : (
    e.chooseFirst
  );

  let pencil;
  if (!pick) pencil = <p className="slip__quiet">{e.pencilWaits}</p>;
  else if (!shown || shown.load === "reading")
    pencil = (
      <p className="slip__quiet" role="status">
        <span className="spin" aria-hidden="true" /> {e.thinking}
      </p>
    );
  else if (!shown.goals.length) pencil = <p className="slip__quiet">{e.noSuggestions}</p>;
  else
    pencil = (
      <ul className="pcs pcs--lines entry-pencil">
        {shown.goals.map((g) => (
          <li key={g} className="pc" data-state={goal.trim() === g ? "ink" : "pencil"} data-origin={goal.trim() === g ? "you" : "athena"}>
            <button type="button" className="entry-pencil__b" data-role="entry-suggestion" onClick={() => setGoal(g)}>
              {g}
            </button>
          </li>
        ))}
      </ul>
    );

  const right = (
    <form className="slip" data-kind="entry" data-role="slip" aria-label={e.title} onSubmit={(ev) => void start(ev)}>
      <header className="slip__h">
        <span className="slip__k">
          <Icon name="arrow" />
          Lands in <b>{e.lands}</b>
        </span>
        <h2>{e.title}</h2>
        <p data-role="entry-with">{withLine}</p>
      </header>
      <div className="slip__b">
        <label className="entry-k" htmlFor="entry-goal">
          {e.goalLabel}
        </label>
        <textarea
          id="entry-goal"
          className="field entry-goal"
          rows={3}
          maxLength={GOAL_MAX}
          value={goal}
          placeholder={e.goalPlaceholder}
          onChange={(ev) => setGoal(ev.target.value)}
        />
        <span className="entry-k">
          <Icon name="pencil" />
          {e.herPencil}
          {simulated && <span className="tag">simulated</span>}
        </span>
        {pencil}
        <p className="entry-rule" data-role="entry-rule">
          <Icon name="send" />
          <span>{ruleFor(twin, pick, chosen)}</span>
        </p>
        {problem && (
          <p className="entry-problem" role="alert">
            <Icon name="risk" />
            <span>{problem}</span>
          </p>
        )}
      </div>
      <footer className="slip__f">
        <button type="button" className="btn btn-quiet" onClick={() => go(back)}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" data-role="slip-go" disabled={!ready}>
          {starting ? <span className="spin" aria-hidden="true" /> : <Icon name="send" />}
          {e.start}
        </button>
      </footer>
    </form>
  );

  return (
    <NestedPage
      twin={twin}
      kicker={e.kicker}
      title={e.title}
      sub={e.sub}
      back={back}
      backLabel="Its document"
      go={go}
      left={left}
      right={right}
      role="entry-page"
    />
  );
}
