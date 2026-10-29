// Beyond the example: the staged final sketch plus 13 more pieces (36 in all), to prove the drawing
// holds a bigger chore without a page scroll and without moving a piece. Invented data, for the
// preview harness and the tests only (A/1 kept the same stress set behind its States menu).

import type { Draft, SketchEdge, SketchNode } from "../../../lib/contract";
import { coverageOf, isAgreed } from "../select";

const you = (id: string, kind: SketchNode["kind"], slot: SketchNode["slot"], label: string, detail?: string): SketchNode => ({
  id,
  kind,
  slot,
  label,
  origin: "you",
  confirmed: true,
  ...(detail ? { detail } : {}),
});
const hers = (id: string, kind: SketchNode["kind"], slot: SketchNode["slot"], label: string): SketchNode => ({
  id,
  kind,
  slot,
  label,
  origin: "athena",
  confirmed: false,
});

/** Thirteen invented pieces for a second club, spread over every territory and the fence. */
export const STRESS_NODES: readonly SketchNode[] = [
  you("s1", "app", "apps", "Swim club invoice email", "PDF, mid-month"),
  you("s2", "app", "apps", "Harbour Swim parents portal"),
  hers("s3", "app", "apps", "Music school portal"),
  you("s4", "source", "inputs", "Swim lesson register"),
  hers("s5", "source", "inputs", "Pool closure notices"),
  hers("s6", "source", "inputs", "Music lesson bookings"),
  hers("s7", "step", "steps", "Compare swim fees with lessons attended"),
  hers("s8", "step", "steps", "Check swim fees for closed weeks"),
  you("s9", "step", "steps", "Flag any lesson billed twice"),
  hers("s10", "step", "steps", "File a swim billing query per extra lesson"),
  you("s11", "gate", "hand", "Your yes on each swim query"),
  hers("s12", "output", "output", "Swim fees: list and total"),
  you("s13", "never", "never", "Never switch a lesson time"),
];

export const STRESS_EDGES: readonly SketchEdge[] = [
  ["s1", "s7"],
  ["s4", "s7"],
  ["s5", "s8"],
  ["s7", "s8"],
  ["s2", "s10"],
  ["s8", "s10"],
  ["s9", "s10"],
  ["s3", "s6"],
  ["s6", "s9"],
  ["s10", "s11"],
  ["s11", "s12"],
  ["n19", "s7"],
].map(([from, to]) => ({ from: from!, to: to! }));

/** The draft with the stress pieces added after its own, as if a longer conversation drew them. */
export function withStress(draft: Draft, count = STRESS_NODES.length): Draft {
  const nodes = [...draft.sketch.nodes, ...STRESS_NODES.slice(0, count)];
  const ids = new Set(nodes.map((n) => n.id));
  const edges = [...draft.sketch.edges, ...STRESS_EDGES.filter((e) => ids.has(e.from) && ids.has(e.to))];
  const coverage = coverageOf({ nodes, edges });
  return { ...draft, sketch: { nodes, edges }, coverage, agreed: isAgreed(coverage) };
}
