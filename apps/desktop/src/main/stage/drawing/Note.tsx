// The question, pinned as a note across the bottom of the drawing (A/1's dock): her line, the one
// question with its suggestions and "say it your own way", or what she is doing with your answer; and
// beside it "That's enough, write it" with what she still needs.

import { useState } from "react";
import type { Draft } from "../../../lib/contract";
import { Composer, Echo, EnoughButton, Question, ReplyNotice, StageSeal, StillNeeds, Suggestions } from "../parts";
import { sealOf } from "../select";
import type { StageAction, StageFrame, StageState } from "../types";
import type { StageWords } from "../words";
import { DRAWING_WORDS as dw } from "./words";

export interface NoteProps {
  draft: Draft;
  frame: StageFrame;
  state: StageState;
  /** Her guesses still in pencil, for "Ink her N pencil ideas first". */
  pencil: readonly string[];
  /** Back at the sketch after "Not quite" or a chore that could not be written. */
  revisit: boolean;
  dispatch: (action: StageAction) => void;
  words: StageWords;
}

export function Note({ draft, frame, state, pencil, revisit, dispatch, words }: NoteProps) {
  const phase = frame.phase;
  // "Say it differently" after a failed reply: the question opens again for this attempt only
  const [againAt, setAgainAt] = useState(-1);
  const again = phase === "failed" && !!frame.ask && againAt === state.startedAt;
  const mode = phase !== "idle" && !again ? phase : frame.ask ? "ask" : "done";
  const seal = sealOf(state, phase);
  const working = !!state.work;
  const ask = frame.ask;

  return (
    <section className="dr-note" data-role="note" data-mode={mode} aria-label={dw.note}>
      <div className="dr-note__main">
        <div className="dr-note__row1">
          <StageSeal state={seal.state} count={0} label="Athena" />
          <p className="dr-note__line" aria-live="polite" title={frame.line}>
            {frame.line}
          </p>
        </div>
        {mode === "ask" && ask && (
          <div className="dr-note__ask" data-cov={String(draft.coverage[ask.slot])}>
            <Question ask={ask} words={words} />
            <div className="dr-note__answers">
              <Suggestions suggestions={ask.suggestions} onPick={(choice) => dispatch({ type: "pick", choice })} disabled={working} words={words} />
              <Composer
                key={again ? `again-${state.startedAt}` : ask.text}
                onSay={(text) => dispatch({ type: "say", text })}
                initial={again ? frame.youSaid : ""}
                disabled={working}
                words={words}
              />
            </div>
          </div>
        )}
        {mode !== "ask" && mode !== "done" && (
          <div className="dr-note__wait">
            <Echo text={frame.youSaid} words={words} />
            <ReplyNotice
              phase={phase}
              problem={frame.problem}
              onRetry={() => dispatch({ type: "retry" })}
              onSayDifferently={ask ? () => setAgainAt(state.startedAt) : undefined}
              words={words}
            />
          </div>
        )}
        {mode === "done" && (
          <div className="dr-note__done">
            <p className="dr-note__whole">{revisit ? dw.lookAgain : dw.wholePicture}</p>
            <div className="dr-note__cta">
              <button type="button" className="btn btn-primary" data-role="exit" data-ready="true" disabled={working} onClick={() => dispatch({ type: "enough" })}>
                {revisit ? dw.writeAgain : dw.writeIt}
              </button>
              {pencil.length > 0 && (
                <button type="button" className="btn" disabled={working} onClick={() => dispatch({ type: "ink", node_ids: [...pencil] })}>
                  {dw.inkFirst(pencil.length)}
                </button>
              )}
              <span className="dr-note__hint">{dw.pointAtAny}</span>
            </div>
          </div>
        )}
      </div>
      {mode !== "done" && (
        <div className="dr-note__exit" data-role="exit-side">
          <EnoughButton coverage={draft.coverage} agreed={draft.agreed} onEnough={() => dispatch({ type: "enough" })} disabled={working} words={words} />
          <StillNeeds coverage={draft.coverage} words={words} />
        </div>
      )}
    </section>
  );
}
