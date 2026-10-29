// The stage's preview script: the staged conversation (invented data) folded through the store's own
// `reduce`, one beat per state a reviewer must see (data/states.md), each with the seconds it takes
// in the staged timings. No daemon: every state is the fixture's streams replayed.

import type { DraftStep, TurnEvent } from "../lib/contract";
import { STAGED } from "../main/stage/fixture/staged";
import { withStress } from "../main/stage/drawing/stress";
import { EMPTY_FRAME, applyLocal, initialStage, reduce } from "../main/stage/store";
import type { ReplyPhase, StageEvent, StageState, StageWork } from "../main/stage/types";

export interface Beat {
  id: string;
  /** The step's group in the control, and a short name for the state. */
  group: DraftStep;
  label: string;
  state: StageState;
  /** Shown instead of the stored phase (slow is a reading of time, not a stored state). */
  phase?: ReplyPhase;
  /** Seconds since the previous beat in the staged timings. */
  wait: number;
  /** Seconds into the current long step (writing, the test run), for its clock. */
  clock?: number;
}

const fold = (state: StageState, events: readonly StageEvent[]) => events.reduce(reduce, state);
const working = (state: StageState, work: StageWork, extra: Partial<StageState> = {}): StageState => ({
  ...state,
  work,
  failed: null,
  frame: { ...state.frame, phase: "sending", problem: "" },
  ...extra,
});

/** Every state, in the order the conversation reaches them. */
export function stageBeats(): Beat[] {
  const beats: Beat[] = [];
  const add = (b: Beat) => beats.push(b);
  const need = STAGED.need;

  let s = initialStage();
  add({ id: "describe-empty", group: "describe", label: "Nothing typed yet", state: s, wait: 0 });
  s = working(s, "describe", { frame: { ...EMPTY_FRAME, youSaid: need, phase: "sending" } });
  add({ id: "describe-sending", group: "describe", label: "Sending the need", state: s, wait: 1 });
  s = { ...reduce(s, { type: "draft", draft: STAGED.created }), work: "say" };

  STAGED.frames.forEach((f, i) => {
    const said = f.say.choice ?? (f.say.text || need);
    const start = f.events.find((e): e is Extract<TurnEvent, { type: "start" }> => e.type === "start")!;
    if (i > 0) s = working(s, "say", { lastSay: f.say, frame: { ...s.frame, youSaid: said, phase: "sending" } });
    const thinking = reduce(s, start);
    if (i === 2) {
      add({ id: "shape-thinking", group: "shape", label: "She is thinking", state: thinking, wait: 0.4 });
      add({ id: "shape-slow", group: "shape", label: "Slow: still thinking", state: thinking, phase: "slow", wait: 8 });
      const failed = reduce(thinking, { type: "error", error: "engine_unavailable", reason: "Muse did not answer in time." });
      add({
        id: "shape-failed",
        group: "shape",
        label: "No usable reply, retry",
        state: { ...failed, failed: { type: "pick", choice: said } },
        wait: 1,
      });
    }
    s = fold(thinking, f.events);
    const name =
      i === 1 ? "Her guesses wait for your yes" : f.draft.agreed && !STAGED.frames[i - 1]?.draft.agreed ? "Agreed: write it is open" : `Reply ${i + 1}`;
    const id = i === 1 ? "shape-proposal" : f.draft.agreed && !STAGED.frames[i - 1]?.draft.agreed ? "shape-agreed" : `shape-${i + 1}`;
    add({ id, group: i === 0 ? "describe" : "shape", label: i === 0 ? "Her first reply" : name, state: s, wait: f.elapsed_s });
    if (f.confirm) {
      s = { ...reduce(s, { type: "draft", draft: f.confirm.draft }), inked: f.confirm.node_ids };
      add({ id: `shape-${i + 1}-inked`, group: "shape", label: `You inked ${f.confirm.node_ids.length}`, state: s, wait: 2 });
    }
  });
  const agreed = s;

  // writing: a repair, then written; or two repairs that do not fix it
  s = working(agreed, "write", { author: [] });
  let clock = 0;
  for (const t of STAGED.author) {
    s = reduce(s, t.event);
    const kind = t.event.type;
    add({
      id: `author-${kind}`,
      group: kind === "written" ? "preview" : "author",
      label: kind === "writing" ? "Writing the chore" : kind === "repair" ? "Fixing what her check found" : "Written",
      state: s,
      wait: t.at_s - clock,
      clock: t.at_s,
    });
    clock = t.at_s;
  }
  const written = s;
  let f = working(agreed, "write", { author: [] });
  f = fold(f, STAGED.authorFailed.map((t) => t.event));
  add({ id: "author-failed", group: "shape", label: "Could not be written", state: f, wait: 1 });

  // the check step
  s = working(written, "preview");
  add({ id: "preview-loading", group: "preview", label: "Working out the cards", state: s, wait: 1 });
  s = { ...reduce(s, { type: "expected", expected: STAGED.preview.expected }), work: null, frame: { ...s.frame, phase: "idle" } };
  add({ id: "preview-ready", group: "preview", label: "Cards wait for yes or no", state: s, wait: 11 });
  for (const m of STAGED.key.marks) s = applyLocal(s, { type: "mark", expected_id: m.expected_id, mark: m.mark, note: m.note });
  for (const t of STAGED.key.missing) s = applyLocal(s, { type: "add_missing", text: t });
  for (const t of STAGED.key.never) s = applyLocal(s, { type: "add_never", text: t });
  add({ id: "preview-marked", group: "preview", label: "Marked, plus missed and never", state: s, wait: 20 });

  // the test run
  s = working(reduce(s, { type: "draft", draft: STAGED.keyed }), "rehearse", { rehearsal: [] });
  clock = 0;
  let cards = 0;
  for (const t of STAGED.rehearsal) {
    s = reduce(s, t.event);
    const e = t.event;
    if (e.type === "card") cards++;
    const label = e.type === "phase" ? `Running: phase ${e.index}` : e.type === "card" ? `Card ${cards} filed` : "Scored: she found fewer";
    const id = e.type === "scored" ? "verdict-short" : e.type === "card" && cards === 1 ? "rehearse-running" : `rehearse-${beats.length}`;
    add({
      id,
      group: e.type === "scored" ? "verdict" : "rehearse",
      label,
      state: s,
      wait: t.at_s - clock,
      clock: t.at_s,
    });
    clock = t.at_s;
  }
  const scored = s;

  add({ id: "saved", group: "saved", label: "Kept: handed off to the Project", state: reduce(scored, { type: "draft", draft: STAGED.saved }), wait: 9 });
  const revised = reduce(scored, { type: "draft", draft: STAGED.revised });
  add({
    id: "shape-revisit",
    group: "shape",
    label: "Not quite: back to the sketch",
    state: { ...revised, frame: { ...revised.frame, line: "", ask: null, lastOps: [] } },
    wait: 1,
  });
  // beyond the example: 13 more pieces (36 in all), to see the drawing hold them (harness only)
  add({ id: "shape-36", group: "shape", label: "Beyond the example: 36 pieces", state: { ...agreed, draft: withStress(agreed.draft!) }, wait: 1 });
  return beats;
}

/** The rows of data/states.md, each with the beat that shows it. */
export const STATES_MD: readonly { state: string; beat: string }[] = [
  { state: "describe: empty", beat: "describe-empty" },
  { state: "describe: sending the need", beat: "describe-sending" },
  { state: "shape: thinking", beat: "shape-thinking" },
  { state: "shape: slow engine", beat: "shape-slow" },
  { state: "shape: failed reply, with a retry", beat: "shape-failed" },
  { state: "shape: a proposal waiting for the person", beat: "shape-proposal" },
  { state: "shape: agreed, the exit is open", beat: "shape-agreed" },
  { state: "author: writing the chore", beat: "author-writing" },
  { state: "author: repairing", beat: "author-repair" },
  { state: "author: could not be written", beat: "author-failed" },
  { state: "preview: expected cards waiting", beat: "preview-ready" },
  { state: "preview: marked, missed and never lines", beat: "preview-marked" },
  { state: "rehearse: running, cards arriving", beat: "rehearse-running" },
  { state: "rehearse: short score", beat: "verdict-short" },
  { state: "verdict: score, her cards beside your marks", beat: "verdict-short" },
  { state: "saved: handed off to the Project", beat: "saved" },
];
