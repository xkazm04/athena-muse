// Where a piece sits in the Drawing view, and how its links run. Pure: the view reads the store's memo
// of places, adds the new pieces' places here, and hands those back to the store, so a piece never
// moves once drawn. Ported from A/1 (app.js `placement`, `pathFor`) with one change the plan names:
// rows are appended only when a lane fills, instead of re-placing every piece when the grid grows.

import type { Sketch, SketchNode, Slot } from "../../../lib/contract";
import type { Place } from "../types";

/** The five territories, left to right; "never" is the fence below them, "need" the sentence on top. */
export const LANES = ["apps", "inputs", "steps", "hand", "output"] as const satisfies readonly Slot[];
export type Lane = (typeof LANES)[number];
export const FENCE = "never";

/** A lane holds at least this many rows (A/1's six), so the first pieces do not fill the lane's height. */
export const MIN_ROWS = 6;
/** Past this many rows the drawing tightens: smaller labels, no glyphs, a narrower gap (A/1's tier). */
export const TIGHT_ROWS = 7;

export const isLane = (slot: Slot): slot is Lane => (LANES as readonly string[]).includes(slot);

export interface Layout {
  /** Every drawn piece's place: memo places first, new ones after. */
  places: Record<string, Place>;
  /** The places this pass gave, in arrival order: what the view writes back to the store. */
  fresh: [string, Place][];
  /** Rows per lane (every lane has the same rows, so the territories line up). */
  rows: number;
}

/** The free row nearest the average row of the pieces a piece links to; the middle when it links to none. */
function nearestFree(free: readonly number[], target: number): number {
  let best = free[0]!;
  for (const r of free) if (Math.abs(r - target) < Math.abs(best - target) - 1e-9) best = r;
  return best;
}

/**
 * Places every piece of `sketch` that `memo` has not placed yet, in the sketch's order (the order the
 * pieces arrived). A memo place is kept as long as the piece is still in the same territory; a piece
 * whose territory changed is placed again there. A lane with no free row gets one more row (for every
 * lane), so nothing already drawn moves.
 */
export function layout(sketch: Sketch, memo: Readonly<Record<string, Place>>): Layout {
  const places: Record<string, Place> = {};
  const fresh: [string, Place][] = [];
  const used = new Map<string, Set<number>>();
  const take = (area: string, index: number) => {
    let set = used.get(area);
    if (!set) used.set(area, (set = new Set()));
    set.add(index);
  };
  const areaOf = (n: SketchNode): string | null => (isLane(n.slot) ? n.slot : n.slot === FENCE ? FENCE : null);

  // the memo first: those places are fixed
  const waiting: SketchNode[] = [];
  let rows = MIN_ROWS;
  for (const n of sketch.nodes) {
    const area = areaOf(n);
    if (!area) continue;
    const was = memo[n.id];
    if (was && was.area === area && !used.get(area)?.has(was.index)) {
      places[n.id] = was;
      take(area, was.index);
      if (area !== FENCE) rows = Math.max(rows, was.index + 1);
    } else waiting.push(n);
  }

  for (const n of waiting) {
    const area = areaOf(n)!;
    const taken = used.get(area) ?? new Set<number>();
    let index: number;
    if (area === FENCE) {
      index = 0;
      while (taken.has(index)) index++;
    } else {
      const linked: number[] = [];
      for (const e of sketch.edges) {
        const other = e.from === n.id ? e.to : e.to === n.id ? e.from : null;
        const at = other ? places[other] : undefined;
        if (at && at.area !== FENCE) linked.push(at.index);
      }
      let free = Array.from({ length: rows }, (_, r) => r).filter((r) => !taken.has(r));
      if (!free.length) {
        // the lane is full: append a row; every piece already drawn keeps its row
        rows++;
        free = [rows - 1];
      }
      const target = linked.length ? linked.reduce((a, b) => a + b, 0) / linked.length : (rows - 1) / 2;
      index = nearestFree(free, target);
    }
    const p: Place = { area, index };
    places[n.id] = p;
    fresh.push([n.id, p]);
    take(area, index);
  }
  return { places, fresh, rows };
}

/** A lane body's box inside the lanes' box (px), as the view measures it. */
export interface LaneBox {
  x: number;
  top: number;
  w: number;
  h: number;
}

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
  col: number;
}

/** A piece's box from its place: its lane's column and its row's slice of the lane's height. */
export function boxOf(place: Place | undefined, lanes: readonly LaneBox[], rows: number, gap: number): Box | null {
  if (!place) return null;
  const col = (LANES as readonly string[]).indexOf(place.area);
  const lane = lanes[col];
  if (col < 0 || !lane) return null;
  const rowH = lane.h / rows;
  return { x: lane.x, y: lane.top + place.index * rowH, w: lane.w, h: rowH - gap, col };
}

const r1 = (n: number) => Math.round(n * 10) / 10;

/**
 * A link's path (A/1 `pathFor`): within a lane it bows out to the right; forward it crosses each lane
 * between at the gutter between rows nearest its line, so it never runs behind a piece; backward it
 * curves straight across.
 */
export function pathFor(a: Box, b: Box, lanes: readonly LaneBox[], rows: number, gap: number): string {
  const ay = a.y + a.h / 2;
  const by = b.y + b.h / 2;
  if (a.col === b.col) {
    const bulge = 24 + Math.min(26, Math.abs(by - ay) * 0.1);
    const sx = a.x + a.w;
    const ex = b.x + b.w - 2;
    return `M${r1(sx)} ${r1(ay)} C${r1(sx + bulge)} ${r1(ay)} ${r1(ex + bulge)} ${r1(by)} ${r1(ex)} ${r1(by)}`;
  }
  if (a.col < b.col) {
    const pts: [number, number][] = [[a.x + a.w, ay]];
    for (let k = a.col + 1; k < b.col; k++) {
      const lane = lanes[k];
      if (!lane) continue;
      const x0 = lane.x;
      const x1 = lane.x + lane.w;
      const mid = (x0 + x1) / 2;
      const span = b.x - (a.x + a.w);
      const yLine = ay + (by - ay) * (span ? (mid - (a.x + a.w)) / span : 0);
      const rowH = lane.h / rows;
      let best = lane.top;
      let bd = Infinity;
      for (let r = 0; r <= rows; r++) {
        let g = lane.top + r * rowH - gap / 2;
        if (r === 0) g = lane.top - 1;
        if (r === rows) g = lane.top + rows * rowH - gap;
        const dd = Math.abs(g - yLine);
        if (dd < bd) {
          bd = dd;
          best = g;
        }
      }
      pts.push([x0 - 10, best], [x1 + 10, best]);
    }
    pts.push([b.x - 2, by]);
    let d = `M${r1(pts[0]![0])} ${r1(pts[0]![1])}`;
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1]!;
      const [x1, y1] = pts[i]!;
      const dx = (x1 - x0) * 0.5;
      d += ` C${r1(x0 + dx)} ${r1(y0)} ${r1(x1 - dx)} ${r1(y1)} ${r1(x1)} ${r1(y1)}`;
    }
    return d;
  }
  const sx = a.x;
  const ex = b.x + b.w + 2;
  const dx = (sx - ex) * 0.5;
  return `M${r1(sx)} ${r1(ay)} C${r1(sx - dx)} ${r1(ay)} ${r1(ex + dx)} ${r1(by)} ${r1(ex)} ${r1(by)}`;
}

/** How much room a piece has, by the row's height (A/1 `fit`): 0 roomy, 1 compact, 2 no details. */
export function densityOf(laneHeight: number, rows: number, gap: number): 0 | 1 | 2 {
  if (!laneHeight) return 1;
  const h = laneHeight / rows - gap;
  return h >= 70 ? 0 : h >= 55 ? 1 : 2;
}
