// What both views read from the stage's one model, computed and never stored: the sketch as ops
// leave it, coverage and "she still needs", what the last reply changed, the reply's shown phase,
// the seal, the test run and the score. Pure; the store and the preview harness share it.

import {
  DETAIL_MAX,
  type AuthorEvent,
  type BenchSummary,
  type Card,
  type Coverage,
  type CoverageValue,
  type Draft,
  type DraftStep,
  type ExpectedCard,
  type KeyBody,
  type Mark,
  type RehearsalEvent,
  type Sketch,
  type SketchNode,
  type SketchOp,
  type Slot,
} from "../../lib/contract";
import type { SealState } from "../../theme";
import type { ReplyPhase, StageFrame, StageState, StageWork } from "./types";

export const SLOTS: readonly Slot[] = ["need", "apps", "inputs", "steps", "hand", "output", "never"];
/** The slots that must hold a piece the person agreed to (ADR 0007's rubric). */
export const REQUIRED: readonly Slot[] = ["need", "apps", "hand", "output"];

/** A reply heard nothing for this long reads "slow" (the measured 3-8 s, then some). */
export const SLOW_MS = 8000;
/** How long a rubbed-out guess waits for undo before the drop is sent. */
export const DROP_MS = 5000;
/** The daemon's caps on a missing or never line and on how many there are (drafts/key.py). */
export const LINE_MAX = DETAIL_MAX;
export const LINES_MAX = 20;

// --- the sketch --------------------------------------------------------------------------------

const sameEdge = (a: { from: string; to: string }, b: { from: string; to: string }) =>
  a.from === b.from && a.to === b.to;

/**
 * Applies streamed ops as the daemon applied them (drafts/sketch.py): add and change replace the
 * node by id (an op carries the whole node after it), remove takes a node with its links or one
 * link, link adds an edge once. Places never move: a new node is appended, a changed one stays put.
 */
export function applyOps(sketch: Sketch, ops: readonly SketchOp[]): Sketch {
  let nodes = sketch.nodes;
  let edges = sketch.edges;
  for (const op of ops) {
    if ((op.op === "add" || op.op === "change") && op.node) {
      const node = op.node;
      const at = nodes.findIndex((n) => n.id === node.id);
      nodes = at < 0 ? [...nodes, node] : nodes.map((n, i) => (i === at ? node : n));
    } else if (op.op === "remove" && op.node) {
      const id = op.node.id;
      nodes = nodes.filter((n) => n.id !== id);
      edges = edges.filter((e) => e.from !== id && e.to !== id);
    } else if (op.op === "remove" && op.edge) {
      const edge = op.edge;
      edges = edges.filter((e) => !sameEdge(e, edge));
    } else if (op.op === "link" && op.edge) {
      const edge = op.edge;
      if (!edges.some((e) => sameEdge(e, edge))) edges = [...edges, { from: edge.from, to: edge.to }];
    }
  }
  return nodes === sketch.nodes && edges === sketch.edges ? sketch : { nodes, edges };
}

/** Per slot: 1 = a piece the person agreed to, 0.5 = only her guesses, 0 = empty, or "skipped". */
export function coverageOf(sketch: Sketch, skipped: ReadonlySet<Slot> = new Set()): Coverage {
  const out = {} as Coverage;
  for (const slot of SLOTS) {
    const nodes = sketch.nodes.filter((n) => n.slot === slot);
    let v: CoverageValue = 0;
    if (nodes.some((n) => n.confirmed)) v = 1;
    else if (skipped.has(slot)) v = "skipped";
    else if (nodes.length) v = 0.5;
    out[slot] = v;
  }
  return out;
}

/** Agreed: the required slots at 1, the rest at 0.5, 1 or skipped. */
export function isAgreed(cov: Coverage): boolean {
  return SLOTS.every((slot) => (REQUIRED.includes(slot) ? cov[slot] === 1 : cov[slot] !== 0));
}

/** The slots that stand between the sketch and agreed, in rubric order: "she still needs". */
export function missingFor(cov: Coverage): Slot[] {
  return SLOTS.filter((slot) => (REQUIRED.includes(slot) ? cov[slot] !== 1 : cov[slot] === 0));
}

/** Slots with no agreed piece and not skipped: what "That's enough, write it" leaves open. */
export function openSlots(cov: Coverage): Slot[] {
  return SLOTS.filter((slot) => cov[slot] === 0 || cov[slot] === 0.5);
}

/** Her guesses: pieces she wrote that the person has not inked. Only these can be inked or rubbed out. */
export const isPencil = (n: SketchNode): boolean => n.origin === "athena" && !n.confirmed;

/** The sketch as the views draw it: the pieces being rubbed out (and their links) are hidden. */
export function shownSketch(sketch: Sketch, dropping: readonly string[]): Sketch {
  if (!dropping.length) return sketch;
  const gone = new Set(dropping);
  return {
    nodes: sketch.nodes.filter((n) => !gone.has(n.id)),
    edges: sketch.edges.filter((e) => !gone.has(e.from) && !gone.has(e.to)),
  };
}

export interface Overlay {
  /** Arrived in the last reply. */
  added: ReadonlySet<string>;
  /** Reworded in the last reply. */
  changed: ReadonlySet<string>;
  /** Inked by the person since the last reply. */
  inked: ReadonlySet<string>;
}

/** What the last reply and the person's inking changed: the views animate exactly these. */
export function overlayOf(frame: StageFrame, inked: readonly string[]): Overlay {
  const added = new Set<string>();
  const changed = new Set<string>();
  for (const op of frame.lastOps) {
    if (!op.node) continue;
    if (op.op === "add") added.add(op.node.id);
    else if (op.op === "change" && !added.has(op.node.id)) changed.add(op.node.id);
  }
  return { added, changed, inked: new Set(inked) };
}

// --- the person's sentence ---------------------------------------------------------------------

export interface NeedMark {
  node_id: string;
  start: number;
  end: number;
}

const SMALL = new Set(["a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "for", "my", "i", "is", "it"]);
const WORD = /[\p{L}\p{N}$']+/gu;

/**
 * Where the person's own pieces sit in their sentence: the piece's quote, found verbatim (the daemon
 * proved it is the person's words). A piece without one (an older draft) falls back to the longest
 * run of two or more words its label shares with the sentence. Marks never overlap; the earlier wins.
 */
/** A practice app's plain name by its id, from the written chore; the id when it is not known. */
export function appNameOf(draft: Draft | null): (appId: string) => string {
  const names = new Map((draft?.practice ?? []).map((a) => [a.app_id, a.name]));
  return (appId) => names.get(appId) ?? appId;
}

export function needMarks(need: string, nodes: readonly SketchNode[]): NeedMark[] {
  const words = [...need.matchAll(WORD)].map((m) => ({ w: norm(m[0]), start: m.index, end: m.index + m[0].length }));
  const found: NeedMark[] = [];
  const lower = need.toLowerCase();
  for (const node of nodes) {
    if (node.origin !== "you") continue;
    if (node.quote) {
      const at = lower.indexOf(node.quote.toLowerCase());
      if (at >= 0) found.push({ node_id: node.id, start: at, end: at + node.quote.length });
      if (at >= 0) continue;
    }
    const label = [...node.label.matchAll(WORD)].map((m) => norm(m[0]));
    let best: { i: number; n: number } | null = null;
    for (let i = 0; i < words.length; i++) {
      for (let j = 0; j < label.length; j++) {
        let n = 0;
        while (i + n < words.length && j + n < label.length && words[i + n]!.w === label[j + n]) n++;
        const strong = words.slice(i, i + n).some((x) => !SMALL.has(x.w));
        if (n >= 2 && strong && (!best || n > best.n)) best = { i, n };
      }
    }
    if (best) found.push({ node_id: node.id, start: words[best.i]!.start, end: words[best.i + best.n - 1]!.end });
  }
  found.sort((a, b) => a.start - b.start);
  const out: NeedMark[] = [];
  for (const m of found) if (!out.length || m.start >= out[out.length - 1]!.end) out.push(m);
  return out;
}

function norm(word: string): string {
  return word.toLowerCase().replace(/'s$/, "");
}

// --- the reply, the seal, the rail -------------------------------------------------------------

/** Only a reply goes slow; writing and the test run take minutes by design and show a clock. */
const TALKING: ReadonlySet<StageWork> = new Set(["describe", "say"]);

/** The phase the person sees: "slow" when a reply has been silent for SLOW_MS. */
export function shownPhase(frame: StageFrame, work: StageWork | null, heardAt: number, now: number): ReplyPhase {
  const waiting = frame.phase === "sending" || frame.phase === "thinking";
  if (waiting && work && TALKING.has(work) && now - heardAt >= SLOW_MS) return "slow";
  return frame.phase;
}

export const STEPS: readonly DraftStep[] = ["describe", "shape", "author", "preview", "rehearse", "verdict", "saved"];

/** The rail's place: the step, or describe before there is a draft. */
export const stepOf = (draft: Draft | null): DraftStep => draft?.step ?? "describe";

/**
 * The seal, one derivation for both views: signed when kept; working while she works; waiting (with
 * a count) when the person owes her something; at rest otherwise, and after a failure.
 */
export function sealOf(state: StageState, phase: ReplyPhase): { state: SealState; count: number } {
  const step = stepOf(state.draft);
  if (step === "saved") return { state: "signed", count: 0 };
  if (state.work || phase === "sending" || phase === "thinking" || phase === "slow") return { state: "working", count: 0 };
  if (phase === "failed") return { state: "rest", count: 0 };
  if (step === "preview" && state.draft?.expected) {
    const left = state.draft.expected.filter((c) => !state.marks[c.id]).length;
    return { state: "waiting", count: Math.max(1, left) };
  }
  if (step === "describe" || step === "shape" || step === "verdict" || step === "preview") return { state: "waiting", count: 1 };
  return { state: "rest", count: 0 };
}

// --- writing ----------------------------------------------------------------------------------

export type AuthorStatus = "idle" | "writing" | "repairing" | "written" | "failed" | "stopped";

/** Where the writing is, read from its events: problems are the latest round's, in plain words. */
export function authorOf(events: readonly AuthorEvent[]): { status: AuthorStatus; problems: string[]; rounds: number } {
  let status: AuthorStatus = "idle";
  let problems: string[] = [];
  let rounds = 0;
  for (const e of events) {
    if (e.type === "writing") status = "writing";
    else if (e.type === "repair") {
      status = "repairing";
      problems = e.problems;
      rounds++;
    } else if (e.type === "written") status = "written";
    else if (e.type === "author_failed") {
      status = "failed";
      problems = e.problems;
    } else if (e.type === "error") {
      status = "stopped";
      problems = [e.reason];
    }
  }
  return { status, problems, rounds };
}

// --- the test run -----------------------------------------------------------------------------

export interface RunPhase {
  index: number;
  app: string;
  message: string;
}

/** The test run so far: phases in order, filed cards (never signable), the score or why it stopped. */
export function runOf(events: readonly RehearsalEvent[]): {
  phases: RunPhase[];
  cards: Card[];
  bench: BenchSummary | null;
  stopped: string;
} {
  const phases: RunPhase[] = [];
  const cards: Card[] = [];
  let bench: BenchSummary | null = null;
  let stopped = "";
  for (const e of events) {
    if (e.type === "phase") phases.push({ index: e.index, app: e.app, message: e.message });
    else if (e.type === "card") cards.push(e.card);
    else if (e.type === "scored") bench = e.bench;
    else stopped = e.reason;
  }
  return { phases, cards, bench, stopped };
}

/** The case a filed card names: its params' values (the daemon's shape) or a `line` (older fixtures). */
function casesOf(card: Card): string[] {
  const out: string[] = [];
  const args = card.args;
  const params = args.params;
  if (params && typeof params === "object") {
    for (const v of Object.values(params as Record<string, unknown>)) if (typeof v === "string") out.push(v);
  }
  if (typeof args.line === "string") out.push(args.line);
  return out.map((v) => v.toLowerCase());
}

/** Whether she filed the card the person expected: same app, same act, same case. */
export function filedFor(expected: ExpectedCard, cards: readonly Card[]): Card | undefined {
  const key = expected.key.toLowerCase();
  return cards.find(
    (c) => c.args.app === expected.app && c.args.tool === expected.tool && casesOf(c).includes(key),
  );
}

export interface ScoreRow {
  id: string;
  label: string;
  /** "card" from her preview, "missing" from the person's "she missed one" line. */
  kind: "card" | "missing";
  /** The person's mark; a placed missing line counts as yes. Unplaced lines are kept unscored. */
  mark: Mark | null;
  note: string;
  filed: boolean;
  scored: boolean;
}

export interface NeverRow {
  text: string;
  /** The act it forbids, when Athena could name one; otherwise it was kept as words. */
  tool?: string;
}

export interface Score {
  found: number;
  eligible: number;
  short: boolean;
  headline: string;
  reasons: string[];
  rows: ScoreRow[];
  never: NeverRow[];
}

/**
 * Her cards beside the person's marks. The counts are the daemon's (the bench is the truth); the
 * rows say, per card, what the person said and whether she filed it.
 */
export function scoreOf(draft: Draft, cards: readonly Card[]): Score | null {
  const bench = draft.bench;
  if (!bench) return null;
  const marks = new Map((draft.key?.marks ?? []).map((m) => [m.expected_id, m]));
  const rows: ScoreRow[] = (draft.expected ?? []).map((c) => {
    const m = marks.get(c.id);
    return {
      id: c.id,
      label: c.label,
      kind: "card",
      mark: m?.mark ?? null,
      note: m?.note ?? "",
      filed: !!filedFor(c, cards),
      scored: true,
    };
  });
  (draft.key?.missing ?? []).forEach((m, i) => {
    rows.push({
      id: m.expected?.id ?? `missing-${i}`,
      label: m.expected?.label ?? m.text,
      kind: "missing",
      mark: m.expected ? "yes" : null,
      note: m.text,
      filed: m.expected ? !!filedFor(m.expected, cards) : false,
      scored: !!m.expected,
    });
  });
  return {
    found: bench.found,
    eligible: bench.eligible,
    short: bench.found < bench.eligible,
    headline: `She found ${bench.found} of the ${bench.eligible} you expected`,
    reasons: bench.reasons,
    rows,
    never: (draft.key?.never ?? []).map((n) => (n.tool ? { text: n.text, tool: n.tool } : { text: n.text })),
  };
}

// --- the check step ---------------------------------------------------------------------------

/** Every card she expects carries a yes or a no. */
export function allMarked(state: StageState): boolean {
  const expected = state.draft?.expected ?? [];
  return expected.length > 0 && expected.every((c) => state.marks[c.id]);
}

/** The key as sent: marks in her order, then the person's own lines. */
export function keyOf(state: StageState): KeyBody {
  const marks = (state.draft?.expected ?? []).flatMap((c) => {
    const m = state.marks[c.id];
    if (!m) return [];
    return [m.note ? { expected_id: c.id, mark: m.mark, note: m.note } : { expected_id: c.id, mark: m.mark }];
  });
  return { marks, missing: [...state.missing], never: [...state.never] };
}
