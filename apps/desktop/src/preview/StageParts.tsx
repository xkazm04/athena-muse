// Every shared part of the stage on one state, in a neutral layout: what the preview shows until the
// Drawing and Orbit views land, and a reference composition for them. Data comes from the state only.

import type { ReactNode } from "react";
import {
  CheckCard,
  Composer,
  Describe,
  Echo,
  EnoughButton,
  FiledCards,
  LineAdder,
  NeedSentence,
  PhaseList,
  PieceCard,
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
  StepRail,
  StillNeeds,
  Suggestions,
  UndoToast,
  VerdictActions,
  VerdictRows,
} from "../main/stage/parts";
import { appNameOf, authorOf, isPencil, needMarks, runOf, scoreOf, sealOf, shownSketch, stepOf } from "../main/stage/select";
import type { ReplyPhase, StageAction, StageState } from "../main/stage/types";
import { STAGE_WORDS } from "../main/stage/words";
import type { SpaceSummary } from "../lib/contract";

export interface PartsBoardProps {
  state: StageState;
  phase: ReplyPhase;
  /** Seconds into writing or the test run, from the staged timings. */
  clock: number;
  dispatch: (action: StageAction) => void;
  project?: SpaceSummary;
  chore?: string;
}

function Slot({ name, children }: { name: string; children: ReactNode }) {
  return (
    <figure className="pv-part">
      <figcaption>{name}</figcaption>
      {children}
    </figure>
  );
}

export function PartsBoard({ state, phase, clock, dispatch, project, chore }: PartsBoardProps) {
  const w = STAGE_WORDS;
  const d = state.draft;
  const step = stepOf(d);
  const seal = sealOf(state, phase);
  const busy = !!state.work || phase !== "idle";
  const sketch = d ? shownSketch(d.sketch, state.dropping) : null;
  const pencil = sketch?.nodes.find((n) => n.id === state.card) ?? sketch?.nodes.find(isPencil) ?? sketch?.nodes[0];
  const author = authorOf(state.author);
  const run = runOf(state.rehearsal);
  const score = d ? scoreOf(d, run.cards) : null;
  const dropping = d?.sketch.nodes.filter((n) => state.dropping.includes(n.id)).map((n) => n.label) ?? [];
  const revisit = d?.step === "shape" && (d.verdict === "revise" || author.status === "failed");

  return (
    <div className="pv-parts">
      <Slot name="Step rail and seal">
        <div className="pv-row">
          <StageSeal state={seal.state} count={seal.count} label="Athena" />
          <StepRail step={step} words={w} />
        </div>
      </Slot>

      {!d && (
        <Slot name="Describe">
          <Describe sending={state.work === "describe"} sent={state.frame.youSaid} onDescribe={(need) => dispatch({ type: "describe", need })} words={w} />
        </Slot>
      )}

      {d && sketch && (
        <Slot name="The person's sentence">
          <NeedSentence need={d.need} marks={needMarks(d.need, sketch.nodes)} words={w} />
        </Slot>
      )}

      {d && (step === "describe" || step === "shape") && (
        <>
          {revisit && (
            <Slot name="Revisit banner">
              <RevisitBanner
                why={d.verdict === "revise" ? "revise" : "unwritten"}
                note={d.note}
                problems={author.status === "failed" ? author.problems : []}
                words={w}
              />
            </Slot>
          )}
          {state.frame.line && phase === "idle" && (
            <Slot name="Her line">
              <p className="pv-line">{state.frame.line}</p>
            </Slot>
          )}
          {phase !== "idle" && (
            <Slot name="You said, and the reply's notice">
              <Echo text={state.frame.youSaid} words={w} />
              <ReplyNotice
                phase={phase}
                problem={state.frame.problem}
                onRetry={() => dispatch({ type: "retry" })}
                onSayDifferently={() => undefined}
                words={w}
              />
            </Slot>
          )}
          {state.frame.ask && phase === "idle" && (
            <Slot name="The question, suggestions (1-4) and your own way">
              <Question ask={state.frame.ask} words={w} />
              <Suggestions suggestions={state.frame.ask.suggestions} onPick={(choice) => dispatch({ type: "pick", choice })} disabled={busy} words={w} />
              <Composer onSay={(text) => dispatch({ type: "say", text })} disabled={busy} words={w} />
            </Slot>
          )}
          <Slot name="She still needs, and the exit">
            <StillNeeds coverage={d.coverage} words={w} />
            <EnoughButton coverage={d.coverage} agreed={d.agreed} onEnough={() => dispatch({ type: "enough" })} disabled={busy} words={w} />
          </Slot>
          {pencil && (
            <Slot name="A piece's card">
              <PieceCard
                node={pencil}
                step={step}
                busy={busy}
                onInk={(id) => dispatch({ type: "ink", node_ids: [id] })}
                onDrop={(id) => dispatch({ type: "drop", node_ids: [id] })}
                onClose={() => dispatch({ type: "close_card" })}
                words={w}
              />
            </Slot>
          )}
        </>
      )}

      {d && step === "author" && (
        <>
          <Slot name={author.status === "repairing" ? w.repairing : w.writing}>
            <RunProgress label={w.writing} elapsedS={clock} aboutS={90} words={w} />
            {author.status === "repairing" && <ProblemList title={w.problems} problems={author.problems} tone="repair" />}
          </Slot>
          <Slot name="Practice-app tiles">
            <div className="pv-row">
              {(d.practice ?? []).map((a) => (
                <PracticeTile key={a.app_id} name={a.name} reads={a.reads} does={a.acts} rows={a.rows} words={w} />
              ))}
            </div>
          </Slot>
        </>
      )}

      {d && step === "preview" && !d.expected && (
        <Slot name={state.work === "preview" ? w.checkLoading : w.written}>
          {state.work === "preview" ? (
            <ReplyNotice phase="thinking" problem="" onRetry={() => undefined} words={w} />
          ) : (
            <button type="button" className="btn btn-primary" onClick={() => dispatch({ type: "preview" })}>
              {w.showCards}
            </button>
          )}
        </Slot>
      )}

      {d && step === "preview" && d.expected && (
        <Slot name={w.checkTitle}>
          <div className="pv-checks">
            {d.expected.map((c) => (
              <CheckCard
                key={c.id}
                card={c}
                mark={state.marks[c.id]?.mark}
                note={state.marks[c.id]?.note}
                onMark={(mark) => dispatch({ type: "mark", expected_id: c.id, mark })}
                onUnmark={() => dispatch({ type: "unmark", expected_id: c.id })}
                onNote={(note) => dispatch({ type: "mark", expected_id: c.id, mark: "no", note })}
                words={w}
              />
            ))}
            <LineAdder
              kind="missing"
              lines={state.missing}
              onAdd={(text) => dispatch({ type: "add_missing", text })}
              onRemove={(index) => dispatch({ type: "remove_missing", index })}
              words={w}
            />
            <LineAdder
              kind="never"
              lines={state.never}
              onAdd={(text) => dispatch({ type: "add_never", text })}
              onRemove={(index) => dispatch({ type: "remove_never", index })}
              words={w}
            />
            <RunTestButton
              left={d.expected.filter((c) => !state.marks[c.id]).length}
              total={d.expected.length}
              onRun={() => dispatch({ type: "send_key" })}
              busy={busy}
              words={w}
            />
          </div>
        </Slot>
      )}

      {d && step === "rehearse" && (
        <Slot name={w.running}>
          <RunProgress label={w.running} elapsedS={clock} aboutS={240} words={w} />
          <PhaseList phases={run.phases} done={false} appName={appNameOf(d)} words={w} />
          <FiledCards cards={run.cards} words={w} />
        </Slot>
      )}

      {d && step === "verdict" && score && (
        <Slot name="Score, her cards beside your marks">
          <ScoreLine score={score} words={w} />
          <PhaseList phases={run.phases} done appName={appNameOf(d)} words={w} />
          <VerdictRows score={score} words={w} />
          <VerdictActions
            onKeep={() => dispatch({ type: "verdict", verdict: "keep" })}
            onRevise={(note) => dispatch({ type: "verdict", verdict: "revise", note })}
            words={w}
          />
        </Slot>
      )}

      {d && step === "saved" && (
        <Slot name="Saved">
          <SavedCard
            name={project?.name ?? d.need}
            brief={project?.brief}
            apps={project?.apps}
            hue={project?.hue}
            chore={chore}
            onOpen={() => undefined}
            words={w}
          />
        </Slot>
      )}

      {dropping.length > 0 && (
        <Slot name="Undo toast">
          <UndoToast labels={dropping} onUndo={() => dispatch({ type: "undo_drop" })} words={w} />
        </Slot>
      )}
    </div>
  );
}
