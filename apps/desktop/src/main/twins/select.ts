// What the twins page reads from its one model, computed and never stored: the pieces as ops leave
// them, coverage as the twin rubric counts it, her pencil, the rehearsal's step and each turn with
// the person's mark on it. Pure; the store, the example and the views share it.

import type {
  CoverageValue,
  MissionTurn,
  Piece,
  PieceOp,
  Place,
  PlaceCoverage,
  StyleDial,
  TwinDetail,
} from "../../lib/contract";
import { meets } from "../stage/select";
import { TWIN_RUBRIC } from "./format";
import type { RehearsalState, SetupState } from "./types";

/** Applies streamed ops as the daemon applied them: add and change carry the whole piece after it,
 * remove takes it away, dial carries the whole dial after it. Order is kept; nothing moves. */
export function applyPieceOps(
  pieces: readonly Piece[],
  dials: readonly StyleDial[],
  ops: readonly PieceOp[],
): { pieces: Piece[]; dials: StyleDial[] } {
  let ps = [...pieces];
  let ds = [...dials];
  for (const op of ops) {
    if ((op.op === "add" || op.op === "change") && op.piece) {
      const p = op.piece;
      ps = ps.some((x) => x.id === p.id) ? ps.map((x) => (x.id === p.id ? p : x)) : [...ps, p];
    } else if (op.op === "remove" && op.piece) {
      const id = op.piece.id;
      ps = ps.filter((x) => x.id !== id);
    } else if (op.op === "dial" && op.dial) {
      const d = op.dial;
      ds = ds.some((x) => x.id === d.id) ? ds.map((x) => (x.id === d.id ? d : x)) : [...ds, d];
    }
  }
  return { pieces: ps, dials: ds };
}

/** The twin rubric's count (the daemon's, mirrored for the example): a place with a piece the person
 * agreed to is 1, with only her pencil 0.5, empty 0. */
export function coverageOf(pieces: readonly Piece[]): PlaceCoverage {
  const out = {} as Record<Place, CoverageValue>;
  for (const p of TWIN_RUBRIC.places) {
    const mine = pieces.filter((x) => x.place === p);
    out[p] = mine.some((x) => x.confirmed) ? 1 : mine.length ? 0.5 : 0;
  }
  return out;
}

/** Whole percent: the mean coverage over the places setup requires. */
export function readinessOf(cov: PlaceCoverage): number {
  const core = TWIN_RUBRIC.places.filter((p) => TWIN_RUBRIC.required[p] > 0);
  const sum = core.reduce((s, p) => s + (cov[p] === "skipped" ? 0.5 : cov[p]), 0);
  return Math.round((100 * sum) / core.length);
}

export const isReady = (cov: PlaceCoverage) => TWIN_RUBRIC.places.every((p) => meets(cov[p], TWIN_RUBRIC.required[p]));

/** Her proposals not yet inked. */
export const pencilOf = (twin: TwinDetail | null): Piece[] => (twin ? twin.pieces.filter((p) => !p.confirmed) : []);

export const piecesAt = (twin: TwinDetail | null, place: Place): Piece[] =>
  twin ? twin.pieces.filter((p) => p.place === place) : [];

/** The section her question is about; on the describe step, identity. Nothing during the rehearsal. */
export function litPlace(s: SetupState): Place | null {
  if (s.rehearsal || s.sealed) return null;
  if (!s.twin || !s.twin.pieces.length) return "who";
  return s.ask?.place ?? null;
}

/** A turn as shown: the stream's facts with the person's mark from the twin's rehearsal on it. */
export function turnsOf(r: RehearsalState, twin: TwinDetail | null): MissionTurn[] {
  const marked = new Map((twin?.rehearsal?.turns ?? []).map((t) => [t.id, t]));
  return r.turns.map((t) => {
    const m = marked.get(t.id);
    return m ? { ...t, ...pick(m) } : t;
  });
}

function pick(t: MissionTurn): Partial<MissionTurn> {
  const out: Partial<MissionTurn> = {};
  if (t.mark) out.mark = t.mark;
  if (t.edited_text) out.edited_text = t.edited_text;
  if (t.learned) out.learned = t.learned;
  return out;
}

export type RehearsalStep =
  | "intro"
  | "writing"
  | "typing"
  | "waits"
  | "held"
  | "editing"
  | "edited"
  | "sent"
  | "resolved"
  | "handed"
  | "golive";

/** Where the rehearsal is, from its turns: who is writing, which draft waits, what came of it. */
export function rehearsalStep(s: SetupState): RehearsalStep {
  const r = s.rehearsal;
  if (s.sealed) return "golive";
  if (!r) return "intro";
  if (r.outcome?.state === "resolved") return "resolved";
  if (r.outcome?.state === "handed_back") return "handed";
  if (r.editing) return "editing";
  const turns = turnsOf(r, s.twin);
  const last = turns.at(-1);
  if (r.streaming) return !last || last.side === "other" ? "writing" : last.decision === "sent_alone" ? "sent" : "typing";
  const twin = [...turns].reverse().find((t) => t.side === "twin");
  if (!twin) return r.streaming ? "writing" : "intro";
  if (twin.mark === "edited" && !r.continued.includes(twin.id)) return "edited";
  if (twin.decision === "waits" && !twin.mark) return twin.kind === "first_message" ? "waits" : "held";
  if (twin.decision === "sent_alone") return "sent";
  return "typing";
}

/** The twin turn the person acts on now, if any. */
export function currentTurn(s: SetupState): MissionTurn | undefined {
  if (!s.rehearsal) return undefined;
  const step = rehearsalStep(s);
  if (!["waits", "held", "editing", "edited", "sent"].includes(step)) return undefined;
  return [...turnsOf(s.rehearsal, s.twin)].reverse().find((t) => t.side === "twin");
}
