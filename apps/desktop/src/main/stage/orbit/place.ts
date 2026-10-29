// Where each piece sits in the Orbit view, pure. Six zones frame the question card (steps on top,
// where it happens and what she reads on the left, the signature and what you get on the right,
// never below). A piece takes its zone's next free cell in arrival order and keeps it: the place is
// memoised in the store by node id, a dropped piece leaves a hole until the next arrival, and how
// many cells a zone shows is read from its measured size, never from the example's counts.

import type { SketchNode, Slot } from "../../../lib/contract";
import type { Place } from "../types";

export type ZoneKey = Exclude<Slot, "need">;
export type Side = "top" | "left" | "right" | "bottom";

/** The six zones in reading (and tab) order, with the side of the card each one frames. */
export const ZONES: readonly { key: ZoneKey; side: Side }[] = [
  { key: "steps", side: "top" },
  { key: "apps", side: "left" },
  { key: "inputs", side: "left" },
  { key: "hand", side: "right" },
  { key: "output", side: "right" },
  { key: "never", side: "bottom" },
];

export const SIDE_OF: Record<ZoneKey, Side> = {
  steps: "top",
  apps: "left",
  inputs: "left",
  hand: "right",
  output: "right",
  never: "bottom",
};

export const isZone = (slot: Slot): slot is ZoneKey => slot !== "need";

/**
 * Every zone piece's place. Places already given are kept as they are; a piece without one (in the
 * order the pieces arrived) takes the lowest cell of its zone that no drawn piece holds, so a hole
 * left by a dropped piece is filled by the next arrival and nothing else ever moves. A piece whose
 * zone changed (her own rewording moved it) is placed again in the new zone.
 */
export function placesFor(nodes: readonly SketchNode[], memo: Readonly<Record<string, Place>>): Record<string, Place> {
  const out: Record<string, Place> = {};
  const taken = new Map<string, Set<number>>();
  const used = (area: string) => {
    let s = taken.get(area);
    if (!s) taken.set(area, (s = new Set()));
    return s;
  };
  for (const n of nodes) {
    if (!isZone(n.slot)) continue;
    const p = memo[n.id];
    if (p && p.area === n.slot && !used(p.area).has(p.index)) {
      out[n.id] = p;
      used(p.area).add(p.index);
    }
  }
  for (const n of nodes) {
    if (!isZone(n.slot) || out[n.id]) continue;
    const cells = used(n.slot);
    let i = 0;
    while (cells.has(i)) i++;
    cells.add(i);
    out[n.id] = { area: n.slot, index: i };
  }
  return out;
}

/** The places in `next` the memo does not hold yet (or holds differently): what the view writes. */
export function unsaved(next: Readonly<Record<string, Place>>, memo: Readonly<Record<string, Place>>): [string, Place][] {
  return Object.entries(next).filter(([id, p]) => {
    const was = memo[id];
    return !was || was.area !== p.area || was.index !== p.index;
  });
}

/** A zone's cell area as measured, with the chip sizes its stylesheet asks for (px). */
export interface ZoneBox {
  w: number;
  h: number;
  /** The narrowest a chip may be; decides the columns. */
  chipW: number;
  /** A chip's height, and a one-line chip's, with the gap between cells in each case. */
  chipH: number;
  gap: number;
  lineH: number;
  lineGap: number;
}

export interface ZoneGrid {
  cols: number;
  rows: number;
  /** One-line chips: the zone's pieces passed what fits at full height. */
  dense: boolean;
  /** Cells shown. Past it, the last cell is a "+n more" chip that opens the zone's list. */
  capacity: number;
}

const fit = (room: number, size: number, gap: number) => Math.max(1, Math.floor((room + gap) / (size + gap)));

/**
 * The zone's grid for the highest cell its pieces hold (`last`, -1 when empty). Columns depend on the
 * width only, so a piece's column never changes; past what fits at full height the zone switches
 * to one-line chips (more rows in the same room). Unmeasured (no layout yet), nothing is held back.
 */
export function gridFor(box: ZoneBox | undefined, last: number): ZoneGrid {
  if (!box || box.w <= 0 || box.h <= 0) return { cols: 1, rows: Math.max(1, last + 1), dense: false, capacity: Infinity };
  const cols = fit(box.w, box.chipW, box.gap);
  const rows = fit(box.h, box.chipH, box.gap);
  if (last < cols * rows) return { cols, rows, dense: false, capacity: cols * rows };
  const lines = Math.max(rows, fit(box.h, box.lineH, box.lineGap));
  return { cols, rows: lines, dense: true, capacity: cols * lines };
}

export interface ZoneSplit {
  /** [node id, cell] drawn in the zone. */
  shown: [string, number][];
  /** In the zone's list behind the "+n more" chip, in cell order. */
  more: string[];
  /** The cell the "+n more" chip takes, or -1. */
  moreAt: number;
}

/** Which of a zone's pieces are drawn in their cells and which wait behind "+n more". */
export function splitZone(cells: readonly [string, number][], grid: ZoneGrid): ZoneSplit {
  const sorted = [...cells].sort((a, b) => a[1] - b[1]);
  if (!sorted.length || sorted[sorted.length - 1]![1] < grid.capacity) return { shown: sorted, more: [], moreAt: -1 };
  const moreAt = grid.capacity - 1;
  return {
    shown: sorted.filter(([, i]) => i < moreAt),
    more: sorted.filter(([, i]) => i >= moreAt).map(([id]) => id),
    moreAt,
  };
}

/** A cell's column and row (from 0) in a grid of `cols` columns. */
export const cellAt = (index: number, cols: number) => ({ col: index % cols, row: Math.floor(index / cols) });
