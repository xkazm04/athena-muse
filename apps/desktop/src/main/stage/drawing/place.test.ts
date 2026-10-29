// @vitest-environment node
// A piece never moves: the Drawing view places each new piece once, and the store keeps that place,
// whatever arrives after it, including when a lane fills and the drawing grows a row.
import { describe, expect, it } from "vitest";
import type { Draft, Sketch, SketchNode } from "../../../lib/contract";
import { STAGED } from "../fixture/staged";
import type { Place } from "../types";
import { LANES, MIN_ROWS, boxOf, densityOf, layout, pathFor } from "./place";
import { STRESS_NODES, withStress } from "./stress";

type Memo = Record<string, Place>;

/** What the store does with a view's places: keeps them, and forgets the pieces no longer drawn. */
function keep(memo: Memo, sketch: Sketch, fresh: [string, Place][]): Memo {
  const ids = new Set(sketch.nodes.map((n) => n.id));
  const out: Memo = {};
  for (const [id, p] of Object.entries(memo)) if (ids.has(id)) out[id] = p;
  for (const [id, p] of fresh) out[id] = p;
  return out;
}

/** Walks drafts in order like the store would, asserting that no kept place ever changes. */
function walk(drafts: readonly Draft[], start: Memo = {}): { memo: Memo; rows: number[] } {
  let memo = start;
  const rows: number[] = [];
  for (const d of drafts) {
    const lay = layout(d.sketch, memo);
    for (const [id, p] of Object.entries(memo)) {
      if (d.sketch.nodes.some((n) => n.id === id)) expect(lay.places[id], `${id} moved`).toEqual(p);
    }
    memo = keep(memo, d.sketch, lay.fresh);
    rows.push(lay.rows);
  }
  return { memo, rows };
}

const node = (id: string, slot: SketchNode["slot"]): SketchNode => ({ id, kind: "step", slot, label: id, origin: "athena", confirmed: false });

describe("the Drawing view's placement", () => {
  it("places every staged reply's new pieces without moving one already drawn", () => {
    const drafts = STAGED.frames.flatMap((f) => (f.confirm ? [f.draft, f.confirm.draft] : [f.draft]));
    const { memo, rows } = walk(drafts);
    const final = drafts.at(-1)!.sketch.nodes;
    // every piece but the person's sentence has a place: a lane and row, or the fence
    for (const n of final) {
      if (n.slot === "need") expect(memo[n.id]).toBeUndefined();
      else expect(memo[n.id]?.area).toBe(n.slot);
    }
    expect(rows.every((r) => r === MIN_ROWS)).toBe(true);
    // no two pieces share a row in a lane
    const seen = new Set(Object.values(memo).map((p) => `${p.area}:${p.index}`));
    expect(seen.size).toBe(Object.keys(memo).length);
  });

  it("appends a row when a lane fills, and still moves nothing (the 36-piece sketch, one piece at a time)", () => {
    const base = STAGED.frames.at(-1)!.confirm!.draft;
    const drafts = [base, ...STRESS_NODES.map((_, i) => withStress(base, i + 1))];
    expect(drafts.at(-1)!.sketch.nodes).toHaveLength(36);
    const { memo, rows } = walk(drafts);
    // the steps lane holds 10 pieces: the drawing grew from 6 rows to 10, a row at a time
    expect(rows[0]).toBe(MIN_ROWS);
    expect(rows.at(-1)).toBe(10);
    for (let i = 1; i < rows.length; i++) expect(rows[i]! - rows[i - 1]!).toBeLessThanOrEqual(1);
    // a full lane's new piece takes the appended row
    const steps = Object.values(memo).filter((p) => p.area === "steps").map((p) => p.index);
    expect(steps.sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });

  it("keeps every other place when a piece is rubbed out, and gives its row to the next arrival", () => {
    const base = STAGED.frames.at(-1)!.confirm!.draft;
    const { memo } = walk([base]);
    const dropped: Draft = {
      ...base,
      sketch: { nodes: base.sketch.nodes.filter((n) => n.id !== "n21"), edges: base.sketch.edges.filter((e) => e.from !== "n21" && e.to !== "n21") },
    };
    const after = walk([dropped], memo).memo;
    expect(after.n21).toBeUndefined();
    const freed = memo.n21!;
    const next: Draft = { ...dropped, sketch: { ...dropped.sketch, nodes: [...dropped.sketch.nodes, node("x1", "steps")] } };
    const again = walk([next], after).memo;
    expect(again.x1).toEqual(freed); // the only free row in a lane of six
  });

  it("puts a new piece in the free row nearest the pieces it links to, the middle when it links to none", () => {
    const sketch: Sketch = {
      nodes: [node("a", "apps"), node("b", "steps"), node("c", "steps")],
      edges: [{ from: "a", to: "c" }],
    };
    const memo: Memo = { a: { area: "apps", index: 5 } };
    const lay = layout(sketch, memo);
    expect(lay.places.b).toEqual({ area: "steps", index: 2 }); // (6 - 1) / 2, the lower of the two middles
    expect(lay.places.c).toEqual({ area: "steps", index: 5 }); // beside its link
    expect(lay.fresh.map(([id]) => id)).toEqual(["b", "c"]);
  });

  it("places a piece again when its territory changed, and keeps the fence in arrival order", () => {
    const memo: Memo = { a: { area: "apps", index: 1 }, n: { area: "never", index: 0 } };
    const lay = layout({ nodes: [node("a", "inputs"), node("n", "never"), node("m", "never")], edges: [] }, memo);
    expect(lay.places.a?.area).toBe("inputs");
    expect(lay.places.n).toEqual({ area: "never", index: 0 });
    expect(lay.places.m).toEqual({ area: "never", index: 1 });
  });
});

describe("the Drawing view's links and density", () => {
  const lanes = LANES.map((_, i) => ({ x: i * 200, top: 30, w: 170, h: 360 }));

  it("routes a forward link through the gutter between rows of each lane it crosses", () => {
    const a = boxOf({ area: "apps", index: 0 }, lanes, 6, 7)!;
    const b = boxOf({ area: "hand", index: 5 }, lanes, 6, 7)!;
    const d = pathFor(a, b, lanes, 6, 7);
    // it enters each lane between (inputs, steps) 10 px before the lane and leaves 10 px after it
    expect(d).toContain(" 190 ");
    expect(d).toContain(" 380 ");
    // and every crossing sits on a gutter: a row boundary less half the gap
    const ys = [...d.matchAll(/C[^C]*? (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)(?= C|$)/g)].map((m) => Number(m[2]));
    const gutters = Array.from({ length: 7 }, (_, r) => (r === 0 ? 29 : r === 6 ? 30 + 360 - 7 : 30 + r * 60 - 3.5));
    for (const y of ys.slice(0, -1)) expect(gutters.some((g) => Math.abs(g - y) < 0.11)).toBe(true);
  });

  it("reads three tiers from the row's height", () => {
    expect(densityOf(6 * 80, 6, 7)).toBe(0);
    expect(densityOf(6 * 65, 6, 7)).toBe(1);
    expect(densityOf(6 * 50, 6, 7)).toBe(2);
  });
});
