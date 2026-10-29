// The frame's shared parts: the step rail and the stage's seal (one derivation, select.sealOf).

import type { DraftStep } from "../../../lib/contract";
import { Seal, type SealState } from "../../../theme";
import { STEPS } from "../select";
import type { StageWords } from "../words";

/** Describe, Shape, Write, Check, Test, Verdict, Keep: done, current, still to come. */
export function StepRail({ step, words }: { step: DraftStep; words: StageWords }) {
  const at = STEPS.indexOf(step);
  return (
    <ol className="sp-rail" data-role="rail" aria-label={words.rail}>
      {STEPS.map((s, i) => (
        <li
          key={s}
          className="sp-rail__step"
          data-step={s}
          data-done={i < at || step === "saved" ? "true" : undefined}
          aria-current={i === at ? "step" : undefined}
        >
          <span className="sp-rail__n" aria-hidden="true">
            {i + 1}
          </span>
          <span className="sp-rail__label">{words.step[s]}</span>
        </li>
      ))}
    </ol>
  );
}

export interface StageSealProps {
  state: SealState;
  count: number;
  size?: number;
  label: string;
}

/** Her seal on the stage, from `sealOf`, so both views agree on it. */
export function StageSeal({ state, count, size = 36, label }: StageSealProps) {
  return (
    <span className="sp-seal" data-role="seal" data-state={state}>
      <Seal state={state} count={count} size={size} label={label} />
    </span>
  );
}
