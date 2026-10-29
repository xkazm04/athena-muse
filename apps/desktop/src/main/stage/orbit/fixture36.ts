// A 36-piece sketch for the Orbit view's tests and its size checks: the staged conversation's final
// 23 pieces plus 13 more, added as one reply's ops would add them. Invented data, like the staged
// conversation it extends (a second club and a music school join the same chore).

import type { SketchNode, SketchOp } from "../../../lib/contract";

const node = (id: string, kind: SketchNode["kind"], slot: SketchNode["slot"], label: string, origin: SketchNode["origin"]): SketchNode => ({
  id,
  kind,
  slot,
  label,
  origin,
  confirmed: origin === "you",
});

/** The 13 pieces past the staged 23, in the order they arrive. */
export const MORE_NODES: readonly SketchNode[] = [
  node("s1", "app", "apps", "Swim club invoice email", "you"),
  node("s2", "app", "apps", "Harbour Swim parents portal", "you"),
  node("s3", "app", "apps", "Music school portal", "athena"),
  node("s4", "source", "inputs", "Swim lesson register", "you"),
  node("s5", "source", "inputs", "Pool closure notices", "athena"),
  node("s6", "source", "inputs", "Music lesson bookings", "athena"),
  node("s7", "step", "steps", "Compare swim fees with lessons attended", "athena"),
  node("s8", "step", "steps", "Check swim fees for closed weeks", "athena"),
  node("s9", "step", "steps", "Flag any lesson billed twice", "you"),
  node("s10", "step", "steps", "File a swim billing query per extra lesson", "athena"),
  node("s11", "gate", "hand", "Your yes on each swim query", "you"),
  node("s12", "output", "output", "Swim fees: list and total", "athena"),
  node("s13", "never", "never", "Never switch a lesson time", "you"),
];

const LINKS: readonly [string, string][] = [
  ["s1", "s7"],
  ["s4", "s7"],
  ["s5", "s8"],
  ["s7", "s10"],
  ["s8", "s10"],
  ["s9", "s10"],
  ["s10", "s11"],
  ["s11", "s12"],
  ["s3", "s6"],
];

/** The ops of one reply that grows the staged sketch to 36 pieces. */
export const MORE_OPS: readonly SketchOp[] = [
  ...MORE_NODES.map((n): SketchOp => ({ op: "add", node: n })),
  ...LINKS.map(([from, to]): SketchOp => ({ op: "link", edge: { from, to } })),
];
