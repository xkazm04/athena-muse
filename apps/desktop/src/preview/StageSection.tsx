// The stage in the preview: the staged conversation replayed through the store's `reduce`, timed by
// its own seconds or stepped to any state, in either view, at either window size. No daemon. The
// person's local acts (marks, lines, a rubbed-out guess) apply to the shown state; anything that
// would talk to the daemon steps to the next beat instead.

import { useEffect, useMemo, useState } from "react";
import type { StageView } from "../lib/contract";
import { STAGED } from "../main/stage/fixture/staged";
import { StageScreen } from "../main/stage/Stage";
import { applyLocal, withPlace } from "../main/stage/store";
import type { StageAction, StageState } from "../main/stage/types";
import { STAGE_WORDS } from "../main/stage/words";
import { PartsBoard } from "./StageParts";
import { stageBeats } from "./stageBeats";

const LOCAL: ReadonlySet<StageAction["type"]> = new Set([
  "mark",
  "unmark",
  "add_missing",
  "add_never",
  "remove_missing",
  "remove_never",
  "drop",
  "undo_drop",
  "open_card",
  "close_card",
]);
const SIZES = ["1280x800", "1024x700"] as const;
const PACES = [1, 8, 32] as const;

export function StageSection() {
  const beats = useMemo(stageBeats, []);
  const [at, setAt] = useState(0);
  const [local, setLocal] = useState<StageState | null>(null);
  const [view, setView] = useState<StageView>("drawing");
  const [places, setPlaces] = useState<StageState["places"]>({ drawing: {}, orbit: {} });
  const [playing, setPlaying] = useState(false);
  const [pace, setPace] = useState<(typeof PACES)[number]>(8);
  const [size, setSize] = useState<(typeof SIZES)[number]>("1280x800");

  const beat = beats[at]!;
  const state: StageState = { ...(local ?? beat.state), view, places };
  const phase = beat.phase ?? state.frame.phase;

  const go = (i: number) => {
    setAt(Math.max(0, Math.min(beats.length - 1, i)));
    setLocal(null);
  };

  // The harness's own timeline: the staged seconds between beats, sped up by the pace.
  useEffect(() => {
    if (!playing) return;
    const next = beats[at + 1];
    if (!next) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => go(at + 1), (next.wait * 1000) / pace);
    return () => clearTimeout(t);
    // go only sets state; the timer restarts when the beat or the pace changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, at, pace, beats]);

  const dispatch = (action: StageAction) => {
    if (action.type === "switch_view") setView(action.view);
    else if (LOCAL.has(action.type)) setLocal(applyLocal(state, action));
    else go(at + 1);
  };

  return (
    <section className="pv-section" aria-labelledby="pv-stage">
      <h2 id="pv-stage">Stage (invented example, no daemon)</h2>
      <div className="pv-row" role="group" aria-label="Stage state">
        <button type="button" className="btn" onClick={() => go(at - 1)} disabled={at === 0}>
          Back
        </button>
        <label className="pv-pick">
          <span className="m-sr">Go to a state</span>
          <select className="field" value={beat.id} onChange={(e) => go(beats.findIndex((b) => b.id === e.target.value))}>
            {(["describe", "shape", "author", "preview", "rehearse", "verdict", "saved"] as const).map((g) => (
              <optgroup key={g} label={STAGE_WORDS.step[g]}>
                {beats
                  .filter((b) => b.group === g)
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.label}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
        </label>
        <button type="button" className="btn" onClick={() => go(at + 1)} disabled={at === beats.length - 1}>
          Next
        </button>
        <button type="button" className="btn btn-primary" aria-pressed={playing} onClick={() => setPlaying((p) => !p)}>
          {playing ? "Pause" : "Play"}
        </button>
        {PACES.map((p) => (
          <button key={p} type="button" className={p === pace ? "btn btn-primary" : "btn"} aria-pressed={p === pace} onClick={() => setPace(p)}>
            {p === 1 ? "real time" : `${p}x`}
          </button>
        ))}
        {SIZES.map((s) => (
          <button key={s} type="button" className={s === size ? "btn btn-primary" : "btn"} aria-pressed={s === size} onClick={() => setSize(s)}>
            {s}
          </button>
        ))}
      </div>
      <p className="pv-note">
        {at + 1} of {beats.length}: {beat.label}. {STAGED.invented}
      </p>
      <div className="pv-stage-scroll">
        <div className="pv-stage" data-size={size} data-beat={beat.id}>
          <StageScreen
            state={state}
            dispatch={dispatch}
            place={(v, id, p) => setPlaces((prev) => withPlace({ ...state, places: prev }, v, id, p).places)}
            invented={STAGED.invented}
            phase={phase}
          />
        </div>
      </div>
      <h3 className="pv-sub">Shared parts on this state</h3>
      <PartsBoard state={state} phase={phase} clock={beat.clock ?? 0} dispatch={dispatch} project={STAGED.project} chore={STAGED.chore.title} />
    </section>
  );
}
