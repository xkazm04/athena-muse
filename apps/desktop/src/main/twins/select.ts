// What the twins page reads from its one model, computed and never stored: the pieces as ops leave
// them, coverage as the twin rubric counts it, her pencil, the rehearsal's step and each turn with
// the person's mark on it. Pure; the store, the example and the views share it.

import type {
  ChannelKind,
  CoverageValue,
  MissionTurn,
  Piece,
  PieceOp,
  Place,
  PlaceCoverage,
  Sample,
  StyleDial,
  TwinDetail,
  TwinSummary,
} from "../../lib/contract";
import { meets } from "../stage/select";
import { TWIN_RUBRIC } from "./format";
import type { RehearsalState, SetupState } from "./types";
import { isWebChannel, WEB_CHANNELS } from "./words";

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

/**
 * The draft the person goes through now: the daemon plays the whole conversation in one stream, then
 * each draft that waited is marked in turn, oldest first. A draft they edited stays current until they
 * move on from it ("Send it": a rehearsal sends nothing to anyone).
 */
function pendingOf(turns: readonly MissionTurn[], continued: readonly string[]): MissionTurn | undefined {
  return turns.find(
    (t) => t.side === "twin" && t.decision === "waits" && (!t.mark || (t.mark === "edited" && !continued.includes(t.id))),
  );
}

/** Where the rehearsal is, from its turns: who is writing, which draft waits, what came of it. */
export function rehearsalStep(s: SetupState): RehearsalStep {
  const r = s.rehearsal;
  if (s.sealed) return "golive";
  if (!r) return "intro";
  if (r.editing) return "editing";
  const turns = turnsOf(r, s.twin);
  const last = turns.at(-1);
  if (r.streaming) return !last || last.side === "other" ? "writing" : last.decision === "sent_alone" ? "sent" : "typing";
  const pending = pendingOf(turns, r.continued);
  if (pending) return pending.mark === "edited" ? "edited" : pending.kind === "first_message" ? "waits" : "held";
  if (r.outcome?.state === "resolved") return "resolved";
  if (r.outcome?.state === "handed_back") return "handed";
  return turns.length ? "typing" : "intro";
}

/** The twin turn the person acts on now, if any. */
export function currentTurn(s: SetupState): MissionTurn | undefined {
  if (!s.rehearsal) return undefined;
  const step = rehearsalStep(s);
  const turns = turnsOf(s.rehearsal, s.twin);
  if (step === "editing") return turns.find((t) => t.id === s.rehearsal!.editing);
  if (step === "waits" || step === "held" || step === "edited") return pendingOf(turns, s.rehearsal.continued);
  if (step === "sent") return [...turns].reverse().find((t) => t.side === "twin");
  return undefined;
}

// --- web channels (business Phase 2) ---------------------------------------------------------------

/** The daemon's words for a web channel on its pieces and pasted messages ("Business mail"). */
const WEB_PIECE: Record<string, ChannelKind> = { "business mail": "mail_web", "bio links": "bio", comments: "comment" };

/** The web channels a twin speaks on: its open channels, else the channel pieces that name one. */
export function webChannelsOf(t: TwinDetail | TwinSummary | null | undefined): ChannelKind[] {
  if (!t) return [];
  const open = t.channels.map((c) => c.kind).filter(isWebChannel);
  const named = "pieces" in t ? t.pieces.filter((p) => p.place === "channels").map((p) => WEB_PIECE[p.label.toLowerCase()]) : [];
  return WEB_CHANNELS.filter((k) => open.includes(k) || named.includes(k));
}

/** A message the person pasted for a web channel (the daemon keeps it among the samples). */
export const isPasted = (x: Sample): boolean => x.id.startsWith("ps_") || /^Pasted for /i.test(x.to);

/** Which web channel a pasted message is for, from the daemon's "Pasted for business mail". */
export function pastedChannel(x: Sample): ChannelKind | undefined {
  return WEB_PIECE[x.to.replace(/^Pasted for\s+/i, "").toLowerCase()];
}

/** The sent mail its Gmail voice is learned from: every sample but the pasted ones. */
export const mailSamplesOf = (t: TwinDetail | null | undefined): Sample[] => (t?.samples ?? []).filter((x) => !isPasted(x));
export const pastedOf = (t: TwinDetail | null | undefined): Sample[] => (t?.samples ?? []).filter(isPasted);
