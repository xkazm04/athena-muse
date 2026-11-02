// The later steps in A/1's containers, built from the shared parts: the strip across the bottom while
// she writes and while the test runs, the drawer over the last two territories for the check step and
// the verdict, and the hand-off card once the chore is kept.

import { useLayoutEffect, useRef, type RefObject } from "react";
import type { Draft } from "../../../lib/contract";
import { useDraftProject, useJob } from "../hooks";
import {
  AccessList,
  CheckCard,
  FiledCards,
  JobStatus,
  LineAdder,
  Meanwhile,
  PhaseList,
  PracticeTile,
  ProblemList,
  ReplyNotice,
  RunTestButton,
  SavedCard,
  ScoreLine,
  VerdictActions,
  VerdictRows,
} from "../parts";
import { appNameOf, authorOf, runOf, scoreOf } from "../select";
import type { StageAction, StageFrame, StageState } from "../types";
import type { StageWords } from "../words";
import { DRAWING_WORDS as dw } from "./words";

/**
 * What the test run's clock measures against: 1-4 min (measured, onboarding-jobs); the bar says "of
 * about 4:00" until then and never claims done before the daemon does, then the clock alone. Writing
 * shows no estimate at all: 15 s to 5 min, so any promise would read as broken.
 */
export const RUN_ABOUT_S = 240;

interface LaterProps {
  draft: Draft;
  frame: StageFrame;
  state: StageState;
  dispatch: (action: StageAction) => void;
  words: StageWords;
}

/**
 * Writing, the written chore's practice apps, and the test run: a strip where the note was. While she
 * works the strip stays compact (a clock, Stop, Leave for now) and her two "meanwhile" questions sit
 * beside it in the last column; nothing waits on them.
 */
export function Strip({ draft, frame, state, dispatch, words }: LaterProps) {
  const write = useJob(state, dispatch, "write", words);
  const preview = useJob(state, dispatch, "preview", words);
  const test = useJob(state, dispatch, "rehearse", words, RUN_ABOUT_S);
  const author = authorOf(state.author);
  const run = runOf(state.rehearsal);
  const failed = frame.phase === "failed" && !state.work;
  const retry = failed && state.failed && (
    <button type="button" className="btn btn-primary" data-role="retry" onClick={() => dispatch({ type: "retry" })}>
      {words.retry}
    </button>
  );

  if (draft.step === "author") {
    const halted = write.status?.state === "stopped";
    const stopped = !halted && (author.status === "stopped" || failed);
    const title = halted
      ? write.status?.byYou === false
        ? words.sheStopped
        : words.youStopped
      : stopped
        ? words.unwritten
        : author.status === "repairing"
          ? words.repairing
          : words.writing;
    const aside = write.meanwhile && <Meanwhile {...write.meanwhile} />;
    return (
      <section className="dr-strip" data-role="strip" data-step="author" data-meanwhile={aside ? "true" : undefined} aria-label={title}>
        <div className="dr-strip__lead">
          <h2 className="dr-strip__title">{title}</h2>
          {!halted && <p className="dr-strip__sub">{stopped ? frame.problem || words.nothingLost : words.writingHint}</p>}
          {write.status && <JobStatus {...write.status} />}
        </div>
        <div className="dr-strip__body">
          {author.problems.length > 0 && (
            <ProblemList title={words.problems} problems={author.problems} tone={stopped ? "failed" : "repair"} />
          )}
          {!stopped && !halted && (
            <div className="dr-tile-next">
              <span className="sp-dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              {dw.nextApp}
            </div>
          )}
        </div>
        <div className="dr-strip__act">
          {aside}
          {retry}
          {stopped && <p className="dr-strip__why">{words.nothingLost}</p>}
        </div>
      </section>
    );
  }

  if (draft.step === "preview") {
    return (
      <section className="dr-strip" data-role="strip" data-step="written" aria-label={words.written}>
        <div className="dr-strip__lead">
          <h2 className="dr-strip__title">{words.written}</h2>
          <p className="dr-strip__sub">{failed ? frame.problem : dw.writtenHint}</p>
          {preview.status && <JobStatus {...preview.status} />}
        </div>
        <div className="dr-strip__body">
          {(draft.practice ?? []).map((a) => (
            <PracticeTile key={a.app_id} name={a.name} reads={a.reads} does={a.acts} rows={a.rows} words={words} />
          ))}
        </div>
        <div className="dr-strip__act">
          {retry ||
            (!preview.status && (
              <button type="button" className="btn btn-primary dr-strip__go" disabled={!!state.work} onClick={() => dispatch({ type: "preview" })}>
                {words.showCards}
              </button>
            ))}
        </div>
      </section>
    );
  }

  // the test run: phases across her practice apps, the cards she filed (shown, never signable)
  const halted = test.status?.state === "stopped";
  const stopped = !halted && (!!run.stopped || failed);
  const idle = !state.work && !state.rehearsal.length && !halted;
  const aside = test.meanwhile && <Meanwhile {...test.meanwhile} />;
  return (
    <section className="dr-strip" data-role="strip" data-step="rehearse" data-meanwhile={aside ? "true" : undefined} aria-label={words.running}>
      <div className="dr-strip__lead">
        <h2 className="dr-strip__title">{stopped || halted ? words.stopped : words.running}</h2>
        {!halted && <p className="dr-strip__sub">{stopped ? run.stopped || frame.problem : words.runningHint}</p>}
        {test.status && <JobStatus {...test.status} />}
      </div>
      <div className="dr-strip__body">
        <PhaseList phases={run.phases} done={false} appName={appNameOf(draft)} words={words} />
        <FiledCards cards={run.cards} words={words} />
      </div>
      <div className="dr-strip__act">
        {retry ||
          aside ||
          (idle ? (
            <button type="button" className="btn btn-primary dr-strip__go" onClick={() => dispatch({ type: "rehearse" })}>
              {words.startTest}
            </button>
          ) : (
            !halted && <p className="dr-strip__why">{dw.nothingNeeded}</p>
          ))}
      </div>
    </section>
  );
}

/**
 * The drawer tightens itself when the window is short (A/1 `fitDrawer`): first the heading's hint,
 * and the practice app on each card, then each card's reason, then the rows' padding. Read from the
 * drawer's body after it is drawn; past the last tier the body scrolls inside, never the page.
 */
function useFit(ref: RefObject<HTMLElement | null>, deps: readonly unknown[]) {
  useLayoutEffect(() => {
    const el = ref.current;
    const body = el?.querySelector<HTMLElement>(".dr-drawer__body");
    if (!el || !body) return;
    // each tier keeps the ones before it: fit1, then fit2, then fit3
    for (const t of [1, 2, 3]) delete el.dataset[`fit${t}`];
    for (let t = 1; t <= 3 && body.scrollHeight > body.clientHeight + 1; t++) el.dataset[`fit${t}`] = "true";
    // the deps are the drawer's content; the ref is stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/** The check step: the cards she expects to file, each marked yes or no, and the person's own lines. */
export function CheckDrawer({ draft, frame, state, dispatch, words }: LaterProps) {
  const ref = useRef<HTMLElement>(null);
  const job = useJob(state, dispatch, "preview", words);
  const expected = draft.expected ?? [];
  const loading = !draft.expected;
  const left = expected.filter((c) => !state.marks[c.id]).length;
  const appName = appNameOf(draft);
  useFit(ref, [draft.expected, state.marks, state.missing, state.never, loading, job.meanwhile?.left.length]);

  return (
    <aside className="dr-drawer" data-role="drawer" data-step="preview" ref={ref} aria-label={words.checkTitle}>
      <header className="dr-drawer__head">
        <div className="dr-drawer__grow">
          <h2>{loading ? words.checkLoading : words.checkTitle}</h2>
          <p>{loading ? dw.previewHint : words.checkHint}</p>
        </div>
        {!loading && (
          <span className="badge" data-tone={left ? "human" : "success"}>
            {expected.length - left} {words.of} {expected.length} {words.marked}
          </span>
        )}
      </header>
      <div className="dr-drawer__body">
        {loading ? (
          <>
            {job.status && <JobStatus {...job.status} />}
            {job.meanwhile?.left.length ? (
              <Meanwhile {...job.meanwhile} />
            ) : (
              [0, 1, 2, 3, 4].map((i) => <div key={i} className="dr-loadrow" aria-hidden="true" />)
            )}
            <ReplyNotice
              phase={frame.phase === "failed" ? "failed" : "thinking"}
              problem={frame.problem}
              onRetry={() => dispatch({ type: "retry" })}
              words={words}
            />
          </>
        ) : (
          <>
            {expected.map((c) => (
              <CheckCard
                key={c.id}
                card={c}
                mark={state.marks[c.id]?.mark}
                note={state.marks[c.id]?.note}
                appName={appName(c.app)}
                onMark={(mark) => dispatch({ type: "mark", expected_id: c.id, mark })}
                onUnmark={() => dispatch({ type: "unmark", expected_id: c.id })}
                onNote={(note) => dispatch({ type: "mark", expected_id: c.id, mark: "no", note })}
                words={words}
              />
            ))}
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
          </>
        )}
      </div>
      {!loading && (
        <footer className="dr-drawer__foot">
          <button
            type="button"
            className="btn btn-quiet"
            data-role="revise"
            disabled={!!state.work}
            onClick={() => dispatch({ type: "verdict", verdict: "revise" })}
          >
            {dw.backToSketch}
          </button>
          <RunTestButton left={left} total={expected.length} onRun={() => dispatch({ type: "send_key" })} busy={!!state.work} words={words} />
        </footer>
      )}
    </aside>
  );
}

/** The verdict: the score in items, her cards beside the person's marks, then keep it or not quite. */
export function VerdictDrawer({ draft, state, dispatch, words }: LaterProps) {
  const ref = useRef<HTMLElement>(null);
  const run = runOf(state.rehearsal);
  const score = scoreOf(draft, run.cards);
  useFit(ref, [score]);
  if (!score) return null;
  return (
    <aside className="dr-drawer" data-role="drawer" data-step="verdict" ref={ref} aria-label={words.verdictTitle}>
      <header className="dr-drawer__head">
        <ScoreLine score={score} words={words} />
      </header>
      <div className="dr-drawer__body">
        <VerdictRows score={score} words={words} />
      </div>
      <footer className="dr-drawer__foot">
        <VerdictActions
          onKeep={() => dispatch({ type: "verdict", verdict: "keep" })}
          onRevise={(note) => dispatch({ type: "verdict", verdict: "revise", note })}
          busy={!!state.work}
          words={words}
        />
      </footer>
    </aside>
  );
}

/** Signing in to the real sites the chore needs (ADR 0014), after the keep. */
export function AccessDrawer({ draft, state, dispatch, words }: LaterProps) {
  const ref = useRef<HTMLElement>(null);
  const sites = draft.sites ?? [];
  useFit(ref, [sites]);
  return (
    <aside className="dr-drawer" data-role="drawer" data-step="access" ref={ref} aria-label={words.accessTitle}>
      <header className="dr-drawer__head">
        <div className="dr-drawer__grow">
          <h2>{words.accessTitle}</h2>
          <p>{words.accessHint}</p>
        </div>
      </header>
      <div className="dr-drawer__body">
        <AccessList sites={sites} busy={!!state.work} onAct={(origin, act) => dispatch({ type: "access", origin, act })} words={words} />
      </div>
    </aside>
  );
}

/** The hand-off: the new Project with the chore in it, over the dimmed drawing. */
export function Finale({ draft, words }: { draft: Draft; words: StageWords }) {
  const { project, openProject } = useDraftProject(draft);
  return (
    <div className="dr-finale">
      <div className="dr-finale__card">
        <SavedCard
          name={project?.name ?? draft.need}
          brief={project?.brief}
          apps={project?.apps}
          hue={project?.hue}
          onOpen={openProject}
          words={words}
        />
      </div>
    </div>
  );
}
