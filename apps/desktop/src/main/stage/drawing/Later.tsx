// The later steps in A/1's containers, built from the shared parts: the strip across the bottom while
// she writes and while the test runs, the drawer over the last two territories for the check step and
// the verdict, and the hand-off card once the chore is kept.

import { useLayoutEffect, useRef, type RefObject } from "react";
import type { Draft } from "../../../lib/contract";
import { useClock, useDraftProject } from "../hooks";
import {
  CheckCard,
  FiledCards,
  LineAdder,
  PhaseList,
  PracticeTile,
  ProblemList,
  ReplyNotice,
  RunProgress,
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
 * What the clocks measure against. Writing: "about a minute" (ADR 0007's authoring, one call plus up
 * to two repairs). The test run: 2-5 min on Claude Code (the plan's Risks, measured); the bar says
 * "of about 4:00" and never claims done before the daemon does.
 */
export const WRITE_ABOUT_S = 90;
export const RUN_ABOUT_S = 240;

interface LaterProps {
  draft: Draft;
  frame: StageFrame;
  state: StageState;
  dispatch: (action: StageAction) => void;
  words: StageWords;
}

/** Writing, the written chore's practice apps, and the test run: a strip where the note was. */
export function Strip({ draft, frame, state, dispatch, words }: LaterProps) {
  const running = state.work === "write" || state.work === "rehearse";
  const elapsed = useClock(state.startedAt, running);
  const author = authorOf(state.author);
  const run = runOf(state.rehearsal);
  const failed = frame.phase === "failed" && !state.work;
  const retry = failed && state.failed && (
    <button type="button" className="btn btn-primary" data-role="retry" onClick={() => dispatch({ type: "retry" })}>
      {words.retry}
    </button>
  );

  if (draft.step === "author") {
    const stopped = author.status === "stopped" || failed;
    const title = stopped ? words.unwritten : author.status === "repairing" ? words.repairing : words.writing;
    return (
      <section className="dr-strip" data-role="strip" data-step="author" aria-label={title}>
        <div className="dr-strip__lead">
          <h2 className="dr-strip__title">{title}</h2>
          <p className="dr-strip__sub">{stopped ? frame.problem || words.nothingLost : words.writingHint}</p>
          {!stopped && <RunProgress label={words.writing} elapsedS={elapsed} aboutS={WRITE_ABOUT_S} words={words} />}
        </div>
        <div className="dr-strip__body">
          {author.problems.length > 0 && (
            <ProblemList title={words.problems} problems={author.problems} tone={stopped ? "failed" : "repair"} />
          )}
          {!stopped && (
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
        </div>
        <div className="dr-strip__body">
          {(draft.practice ?? []).map((a) => (
            <PracticeTile key={a.app_id} name={a.name} reads={a.reads} does={a.acts} rows={a.rows} words={words} />
          ))}
        </div>
        <div className="dr-strip__act">
          {retry || (
            <button type="button" className="btn btn-primary dr-strip__go" disabled={!!state.work} onClick={() => dispatch({ type: "preview" })}>
              {words.showCards}
            </button>
          )}
        </div>
      </section>
    );
  }

  // the test run: phases across her practice apps, the cards she filed (shown, never signable)
  const stopped = !!run.stopped || failed;
  const idle = !state.work && !state.rehearsal.length;
  return (
    <section className="dr-strip" data-role="strip" data-step="rehearse" aria-label={words.running}>
      <div className="dr-strip__lead">
        <h2 className="dr-strip__title">{stopped ? words.stopped : words.running}</h2>
        <p className="dr-strip__sub">{stopped ? run.stopped || frame.problem : words.runningHint}</p>
        {!stopped && !idle && <RunProgress label={words.running} elapsedS={elapsed} aboutS={RUN_ABOUT_S} words={words} />}
      </div>
      <div className="dr-strip__body">
        <PhaseList phases={run.phases} done={false} appName={appNameOf(draft)} words={words} />
        <FiledCards cards={run.cards} words={words} />
      </div>
      <div className="dr-strip__act">
        {retry ||
          (idle ? (
            <button type="button" className="btn btn-primary dr-strip__go" onClick={() => dispatch({ type: "rehearse" })}>
              {words.startTest}
            </button>
          ) : (
            <p className="dr-strip__why">{dw.nothingNeeded}</p>
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
  const expected = draft.expected ?? [];
  const loading = !draft.expected;
  const left = expected.filter((c) => !state.marks[c.id]).length;
  const appName = appNameOf(draft);
  useFit(ref, [draft.expected, state.marks, state.missing, state.never, loading]);

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
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="dr-loadrow" aria-hidden="true" />
            ))}
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
