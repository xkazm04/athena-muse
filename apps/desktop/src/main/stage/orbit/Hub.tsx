// The hub: the one card at the centre of the orbit and the largest thing on screen. Whatever the
// person must do now is here and only that: her question while shaping, then the later steps, all
// built from the shared parts. The sketch keeps circling it as context.

import { useEffect, useMemo, useRef, useState, type FocusEvent, type ReactNode } from "react";
import type { Draft, Slot } from "../../../lib/contract";
import { useClock, useDraftProject } from "../hooks";
import {
  CheckCard,
  Composer,
  Echo,
  EnoughButton,
  FiledCards,
  LineAdder,
  NeedSentence,
  PhaseList,
  PracticeTile,
  ProblemList,
  Question,
  ReplyNotice,
  RevisitBanner,
  RunProgress,
  RunTestButton,
  SavedCard,
  ScoreLine,
  StageSeal,
  StillNeeds,
  Suggestions,
  VerdictActions,
  VerdictRows,
} from "../parts";
import { allMarked, appNameOf, authorOf, isPencil, runOf, scoreOf, sealOf, type NeedMark } from "../select";
import type { StageAction, StageFrame, StageState } from "../types";
import type { StageWords } from "../words";
import { ORBIT_WORDS } from "./words";

/** About how long writing and the test run take (measured, ADR 0007), for the clock's "of about". */
const WRITE_ABOUT_S = 90;
const RUN_ABOUT_S = 180;

export interface HubProps {
  draft: Draft;
  frame: StageFrame;
  state: StageState;
  dispatch: (a: StageAction) => void;
  words: StageWords;
  marks: readonly NeedMark[];
  /** The marks that just arrived, in the order their phrases light up (the reply's choreography). */
  arriving: boolean;
  /** Pointing at a phrase points at its piece. */
  onPoint: (id: string | null) => void;
  /** Pieces drawn, and how many are her pencil, for the whole-picture summary. */
  counts: { all: number; pencil: number };
}

const WAITING = new Set(["sending", "thinking", "slow"]);

function Head({ seal, eyebrow, title, sub }: { seal: ReactNode; eyebrow: string; title: string; sub?: string }) {
  return (
    <div className="ob-head">
      {seal}
      <div className="ob-head__words">
        <p className="ob-eyebrow">{eyebrow}</p>
        <h2 className="ob-title">{title}</h2>
        {sub && <p className="ob-sub">{sub}</p>}
      </div>
    </div>
  );
}

/** The card at the centre, for whichever step the draft is at. */
export function Hub(p: HubProps) {
  const { draft, frame, state, words } = p;
  const s = sealOf(state, frame.phase);
  const seal = <StageSeal state={s.state} count={s.count} size={44} label={s.count ? "Athena, waiting on you" : "Athena"} />;
  const step = draft.step;
  let body;
  if (step === "describe" || step === "shape") body = <ShapeCard {...p} seal={seal} />;
  else if (step === "author") body = <AuthorCard {...p} seal={seal} />;
  else if (step === "preview" && draft.expected?.length) body = <Deck {...p} seal={seal} expected={draft.expected} />;
  else if (step === "preview") body = <WrittenCard {...p} seal={seal} />;
  else if (step === "rehearse") body = <RunCard {...p} seal={seal} />;
  else if (step === "verdict") body = <VerdictCard {...p} seal={seal} />;
  else body = <SavedHub draft={draft} words={words} />;
  return (
    <div className="ob-hub" data-role="hub" data-step={step}>
      <div className="ob-hub__glass coat" aria-hidden="true" />
      <div className="ob-hub__body">{body}</div>
    </div>
  );
}

type CardProps = HubProps & { seal: ReactNode };

// ---- shaping ----------------------------------------------------------------------------------

function ShapeCard({ draft, frame, state, dispatch, words, marks, arriving, onPoint, counts, seal }: CardProps) {
  const [differently, setDifferently] = useState(false);
  const busy = !!state.work || WAITING.has(frame.phase);
  const author = authorOf(state.author);
  const revisit = draft.step === "shape" && (draft.verdict === "revise" || author.status === "failed");
  const failed = frame.phase === "failed";
  const waiting = WAITING.has(frame.phase) || (failed && !differently);
  const pencil = draft.sketch.nodes.filter(isPencil).map((n) => n.id);
  const say = (text: string) => {
    setDifferently(false);
    dispatch({ type: "say", text });
  };
  return (
    <div className="ob-view ob-view--shape">
      <div className="ob-top">
        {revisit && (
          <RevisitBanner
            why={draft.verdict === "revise" ? "revise" : "unwritten"}
            note={draft.note}
            problems={author.status === "failed" ? author.problems : []}
            words={words}
          />
        )}
        <div className="ob-quote" data-arriving={arriving ? "true" : undefined}>
          <span className="ob-quote__you" aria-hidden="true">
            {ORBIT_WORDS.you}
          </span>
          <NeedSentence need={draft.need} marks={marks} words={words} onPoint={onPoint} />
        </div>
      </div>
      <div className="ob-speaker">
        {seal}
        <p className="ob-line" aria-live="polite">
          {draft.step === "describe" && !frame.line ? ORBIT_WORDS.reading : frame.line}
        </p>
      </div>
      <div className="ob-main">
        {waiting ? (
          <>
            {draft.step !== "describe" && <Echo text={frame.youSaid} words={words} />}
            <ReplyNotice
              phase={frame.phase}
              problem={frame.problem}
              onRetry={() => {
                setDifferently(false);
                dispatch({ type: "retry" });
              }}
              onSayDifferently={draft.step === "shape" ? () => setDifferently(true) : undefined}
              words={words}
            />
          </>
        ) : frame.ask ? (
          <div className="ob-ask">
            <Question ask={frame.ask} words={words} />
            <Suggestions suggestions={frame.ask.suggestions} onPick={(choice) => dispatch({ type: "pick", choice })} disabled={busy} words={words} />
          </div>
        ) : (
          <div className="ob-whole">
            <h2 className="ob-whole__title">{ORBIT_WORDS.whole}</h2>
            <p className="ob-whole__count">{ORBIT_WORDS.wholeCount(counts.all, counts.pencil)}</p>
          </div>
        )}
      </div>
      {!waiting && (frame.ask || differently) && (
        <Composer key={differently ? "again" : "own"} onSay={say} disabled={busy} initial={differently ? frame.youSaid : ""} words={words} />
      )}
      <div className="ob-foot">
        <StillNeeds coverage={draft.coverage} words={words} />
        <div className="ob-foot__row">
          {pencil.length > 0 && draft.step === "shape" && (
            <button type="button" className="btn btn-quiet ob-inkall" disabled={busy} onClick={() => dispatch({ type: "ink", node_ids: pencil })}>
              <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
                <path d="M3.2 12.4l.7-2.8 6.4-6.4a1.5 1.5 0 012.1 2.1l-6.4 6.4z" />
                <path d="M2.6 14.4h7.2" />
              </svg>
              {ORBIT_WORDS.inkAll(pencil.length)}
            </button>
          )}
          <EnoughButton coverage={draft.coverage} agreed={draft.agreed} onEnough={() => dispatch({ type: "enough" })} disabled={busy} words={words} />
        </div>
      </div>
    </div>
  );
}

// ---- writing ----------------------------------------------------------------------------------

function AuthorCard({ frame, state, dispatch, words, seal }: CardProps) {
  const author = authorOf(state.author);
  const elapsed = useClock(state.startedAt, state.work === "write");
  return (
    <div className="ob-view ob-view--author">
      <Head
        seal={seal}
        eyebrow={words.step.author}
        title={author.status === "repairing" ? words.repairing : words.writing}
        sub={words.writingHint}
      />
      <RunProgress label={words.writing} elapsedS={elapsed} aboutS={WRITE_ABOUT_S} words={words} />
      {author.status === "repairing" && <ProblemList title={words.problems} problems={author.problems} tone="repair" />}
      {frame.phase === "failed" && (
        <ReplyNotice phase="failed" problem={frame.problem} onRetry={() => dispatch({ type: "retry" })} words={words} />
      )}
    </div>
  );
}

function WrittenCard({ draft, frame, state, dispatch, words, seal }: CardProps) {
  const loading = state.work === "preview";
  return (
    <div className="ob-view ob-view--written">
      <Head seal={seal} eyebrow={words.step.author} title={words.written} sub={ORBIT_WORDS.writtenHint} />
      <div className="ob-tiles">
        {(draft.practice ?? []).map((a) => (
          <PracticeTile key={a.app_id} name={a.name} reads={a.reads} does={a.acts} rows={a.rows} fresh words={words} />
        ))}
      </div>
      <div className="ob-go">
        {frame.phase === "failed" ? (
          <ReplyNotice phase="failed" problem={frame.problem} onRetry={() => dispatch({ type: "retry" })} words={words} />
        ) : loading ? (
          <p className="ob-loading" role="status">
            <span className="sp-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            {words.checkLoading}
          </p>
        ) : (
          <button type="button" className="btn btn-primary ob-go__btn" disabled={!!state.work} onClick={() => dispatch({ type: "preview" })}>
            {words.showCards}
          </button>
        )}
      </div>
    </div>
  );
}

// ---- the check step: one card at a time --------------------------------------------------------

function Deck({ draft, state, dispatch, words, seal, expected }: CardProps & { expected: NonNullable<Draft["expected"]> }) {
  const [cursor, setCursor] = useState<number | null>(null);
  const [lines, setLines] = useState(() => allMarked(state));
  const deck = useRef<HTMLDivElement>(null);
  const appName = useMemo(() => appNameOf(draft), [draft]);
  const firstOpen = expected.findIndex((c) => !state.marks[c.id]);
  const at = Math.min(expected.length - 1, cursor ?? (firstOpen < 0 ? expected.length - 1 : firstOpen));
  const left = expected.filter((c) => !state.marks[c.id]).length;

  const nextOpen = (from: number) => {
    for (let k = 1; k <= expected.length; k++) {
      const i = (from + k) % expected.length;
      if (!state.marks[expected[i]!.id]) return i;
    }
    return -1;
  };

  // A yes on the card in front deals the next one (Y from the keymap or the button alike).
  const seen = useRef(state.marks);
  useEffect(() => {
    const was = seen.current;
    seen.current = state.marks;
    const card = expected[at];
    if (!card || state.marks[card.id]?.mark !== "yes" || was[card.id]?.mark === "yes") return;
    const next = nextOpen(at);
    if (next >= 0) setCursor(next);
    else setLines(true);
    // nextOpen reads the same marks; the deal follows a change of marks only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.marks]);

  // The card in front holds the focus, so Y and N mark it and the arrows deal the next.
  useEffect(() => {
    if (lines) return;
    const el = deck.current?.querySelectorAll<HTMLElement>('[data-role="check-card"]')[at];
    if (el && !el.contains(document.activeElement)) el.focus({ preventScroll: true });
  }, [at, lines]);

  const onFocus = (e: FocusEvent<HTMLDivElement>) => {
    const id = (e.target as HTMLElement).closest<HTMLElement>('[data-role="check-card"]')?.dataset.expectedId;
    const i = expected.findIndex((c) => c.id === id);
    if (i >= 0 && i !== at) setCursor(i);
  };

  const advance = () => {
    if (at < expected.length - 1) setCursor(at + 1);
    else if (!left) setLines(true);
    else setCursor(firstOpen);
  };

  return (
    <div className="ob-view ob-view--check">
      <Head seal={seal} eyebrow={words.step.preview} title={lines ? ORBIT_WORDS.linesTitle : ORBIT_WORDS.cardsTitle} sub={lines ? ORBIT_WORDS.linesHint : undefined} />
      <div className="ob-dots" role="group" aria-label={words.checkTitle}>
        {expected.map((c, i) => {
          const m = state.marks[c.id]?.mark;
          return (
            <button
              key={c.id}
              type="button"
              className="ob-dot"
              data-mark={m ?? "ask"}
              aria-current={!lines && i === at ? "true" : undefined}
              aria-label={ORBIT_WORDS.cardDot(i + 1, expected.length, m === "yes" ? words.yes : m === "no" ? words.no : ORBIT_WORDS.waiting)}
              onClick={() => {
                setLines(false);
                setCursor(i);
              }}
            >
              {i + 1}
            </button>
          );
        })}
      </div>
      {lines ? (
        <div className="ob-lines">
          <LineAdder
            kind="missing"
            lines={state.missing}
            onAdd={(text) => dispatch({ type: "add_missing", text })}
            onRemove={(index) => dispatch({ type: "remove_missing", index })}
            words={words}
          />
          <LineAdder
            kind="never"
            lines={state.never}
            onAdd={(text) => dispatch({ type: "add_never", text })}
            onRemove={(index) => dispatch({ type: "remove_never", index })}
            words={words}
          />
          <div className="ob-lines__go">
            <button type="button" className="btn btn-quiet" onClick={() => setLines(false)}>
              {ORBIT_WORDS.backToCards}
            </button>
            <RunTestButton left={left} total={expected.length} onRun={() => dispatch({ type: "send_key" })} busy={!!state.work} words={words} />
          </div>
        </div>
      ) : (
        <>
          <div className="ob-deck" ref={deck} onFocus={onFocus}>
            {expected.map((c, i) => (
              <div key={c.id} className="ob-deck__slot" data-front={i === at ? "true" : undefined} data-behind={i > at ? Math.min(2, i - at) : undefined}>
                <p className="ob-deck__n">{ORBIT_WORDS.cardOf(i + 1, expected.length)}</p>
                <CheckCard
                  card={c}
                  mark={state.marks[c.id]?.mark}
                  note={state.marks[c.id]?.note}
                  onMark={(mark) => dispatch({ type: "mark", expected_id: c.id, mark })}
                  onUnmark={() => dispatch({ type: "unmark", expected_id: c.id })}
                  onNote={(note) => dispatch({ type: "mark", expected_id: c.id, mark: "no", note })}
                  appName={appName(c.app)}
                  words={words}
                />
              </div>
            ))}
          </div>
          <div className="ob-deck__nav">
            <button type="button" className="btn btn-quiet" disabled={at === 0} onClick={() => setCursor(at - 1)}>
              {ORBIT_WORDS.earlier}
            </button>
            <span className="ob-deck__hint">{ORBIT_WORDS.keysHint}</span>
            <button type="button" className="btn btn-quiet" onClick={advance}>
              {!left && at === expected.length - 1 ? ORBIT_WORDS.toLines : ORBIT_WORDS.next}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ---- the test run and the verdict -------------------------------------------------------------

function RunCard({ draft, frame, state, dispatch, words, seal }: CardProps) {
  const run = useMemo(() => runOf(state.rehearsal), [state.rehearsal]);
  const elapsed = useClock(state.startedAt, state.work === "rehearse");
  const appName = useMemo(() => appNameOf(draft), [draft]);
  return (
    <div className="ob-view ob-view--run">
      <div className="ob-pane">
        <Head seal={seal} eyebrow={words.step.rehearse} title={words.running} sub={words.runningHint} />
        <RunProgress label={words.running} elapsedS={elapsed} aboutS={RUN_ABOUT_S} words={words} />
        <PhaseList phases={run.phases} done={!!run.bench} appName={appName} words={words} />
        {frame.phase === "failed" && (
          <ReplyNotice phase="failed" problem={run.stopped || frame.problem} onRetry={() => dispatch({ type: "retry" })} words={words} />
        )}
      </div>
      <div className="ob-pane ob-pane--side">
        <FiledCards cards={run.cards} words={words} />
      </div>
    </div>
  );
}

function VerdictCard({ draft, state, dispatch, words, seal }: CardProps) {
  const run = useMemo(() => runOf(state.rehearsal), [state.rehearsal]);
  const score = useMemo(() => scoreOf(draft, run.cards), [draft, run.cards]);
  if (!score) return null;
  return (
    <div className="ob-view ob-view--verdict">
      <div className="ob-pane">
        <Head seal={seal} eyebrow={words.step.verdict} title={words.verdictTitle} />
        <VerdictRows score={score} words={words} />
      </div>
      <div className="ob-pane ob-pane--side">
        <ScoreLine score={score} words={words} />
        <VerdictActions
          onKeep={() => dispatch({ type: "verdict", verdict: "keep" })}
          onRevise={(note) => dispatch({ type: "verdict", verdict: "revise", note })}
          busy={!!state.work}
          words={words}
        />
      </div>
    </div>
  );
}

function SavedHub({ draft, words }: { draft: Draft; words: StageWords }) {
  const { project, openProject } = useDraftProject(draft);
  return (
    <div className="ob-view ob-view--saved">
      <SavedCard
        name={project?.name ?? draft.need}
        brief={project?.brief}
        apps={project?.apps}
        hue={project?.hue}
        onOpen={openProject}
        words={words}
      />
    </div>
  );
}

/** For the arcs' tips: what each place holds. */
export function countsBySlot(nodes: Draft["sketch"]["nodes"]): Record<Slot, { all: number; pencil: number }> {
  const out = {} as Record<Slot, { all: number; pencil: number }>;
  for (const slot of ["need", "apps", "inputs", "steps", "hand", "output", "never"] as const) out[slot] = { all: 0, pencil: 0 };
  for (const n of nodes) {
    out[n.slot].all++;
    if (isPencil(n)) out[n.slot].pencil++;
  }
  return out;
}
