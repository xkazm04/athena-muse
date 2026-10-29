// The Orbit view's lines, pure: the seven arcs hugging the question card (how much of each place
// she knows) and the links between pieces, routed round the card and never through it. Inputs are
// boxes measured in the view's own coordinates; outputs are SVG path data with their lengths.

import type { Slot } from "../../../lib/contract";
import type { Side } from "./place";

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

type Pt = readonly [number, number];

// ---- the ring ---------------------------------------------------------------------------------

/** The arcs in their order round the card: the need at the top-left corner, then clockwise. */
export const ARC_ORDER: readonly Slot[] = ["need", "steps", "hand", "output", "never", "inputs", "apps"];

/** A rounded rectangle walked clockwise from the top edge's start: 8 pieces, 4 edges and 4 corners. */
function roundRect(x: number, y: number, w: number, h: number, r: number) {
  const lh = w - 2 * r;
  const lv = h - 2 * r;
  const la = (Math.PI * r) / 2;
  const len = [lh, la, lv, la, lh, la, lv, la];
  const cum = [0];
  len.forEach((v, i) => cum.push(cum[i]! + v));
  const total = cum[8]!;
  const pointAt = (s0: number): Pt => {
    const s = ((s0 % total) + total) % total;
    let i = 0;
    while (i < 7 && s > cum[i + 1]!) i++;
    const t = s - cum[i]!;
    let a: number;
    switch (i) {
      case 0:
        return [x + r + t, y];
      case 1:
        a = -Math.PI / 2 + t / r;
        return [x + w - r + r * Math.cos(a), y + r + r * Math.sin(a)];
      case 2:
        return [x + w, y + r + t];
      case 3:
        a = t / r;
        return [x + w - r + r * Math.cos(a), y + h - r + r * Math.sin(a)];
      case 4:
        return [x + w - r - t, y + h];
      case 5:
        a = Math.PI / 2 + t / r;
        return [x + r + r * Math.cos(a), y + h - r + r * Math.sin(a)];
      case 6:
        return [x, y + h - r - t];
      default:
        a = Math.PI + t / r;
        return [x + r + r * Math.cos(a), y + r + r * Math.sin(a)];
    }
  };
  const at = (piece: number, f: number) => cum[piece]! + len[piece]! * f;
  const path = (s0: number, s1: number) => {
    const end = s1 < s0 ? s1 + total : s1;
    const n = Math.max(2, Math.ceil((end - s0) / 3));
    let d = "";
    for (let k = 0; k <= n; k++) {
      const p = pointAt(s0 + ((end - s0) * k) / n);
      d += `${k ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`;
    }
    return { d, mid: pointAt((s0 + end) / 2) };
  };
  return { at, path };
}

export interface Arc {
  slot: Slot;
  d: string;
  /** The arc's middle, where a phrase flies to (the need) and where its tip is anchored. */
  mid: Pt;
  /** Where the arc's tip sits, just outside the arc, and which side of the card that is. */
  tip: Pt;
  side: Side;
}

/** The seven arcs, 9 px outside the card's border, in the winner's spans along the rounded edge. */
export function ringArcs(hub: Box, offset = 9, radius = 16): Arc[] {
  if (hub.w <= 0 || hub.h <= 0) return [];
  const o = offset;
  const P = roundRect(hub.x - o, hub.y - o, hub.w + 2 * o, hub.h + 2 * o, radius + o);
  const spans: Record<Slot, [number, number]> = {
    need: [P.at(7, 0.5), P.at(0, 0.055)],
    steps: [P.at(0, 0.085), P.at(0, 0.965)],
    hand: [P.at(1, 0.18), P.at(2, 0.47)],
    output: [P.at(2, 0.55), P.at(3, 0.86)],
    never: [P.at(4, 0.07), P.at(4, 0.95)],
    inputs: [P.at(5, 0.14), P.at(6, 0.45)],
    apps: [P.at(6, 0.55), P.at(7, 0.36)],
  };
  const cx = hub.x + hub.w / 2;
  const cy = hub.y + hub.h / 2;
  return ARC_ORDER.map((slot) => {
    const [s0, s1] = spans[slot];
    const { d, mid } = P.path(s0, s1);
    const dx = mid[0] - cx;
    const dy = mid[1] - cy;
    const side: Side =
      Math.abs(dx) / (hub.w / 2) > Math.abs(dy) / (hub.h / 2) ? (dx < 0 ? "left" : "right") : dy < 0 ? "top" : "bottom";
    const off = 22;
    const tip: Pt =
      slot === "need"
        ? [mid[0] - 6, mid[1] - off]
        : [mid[0] + (side === "left" ? -off : side === "right" ? off : 0), mid[1] + (side === "top" ? -off : side === "bottom" ? off : 0)];
    return { slot, d, mid, tip, side };
  });
}

// ---- links ------------------------------------------------------------------------------------

export interface LinkEnd {
  box: Box;
  side: Side;
}

export interface Route {
  d: string;
  /** The path's length in px (for the line that draws itself in). */
  len: number;
}

const dist = (a: Pt, b: Pt) => Math.hypot(b[0] - a[0], b[1] - a[1]);
const f1 = (n: number) => n.toFixed(1);

function cubic(p0: Pt, c0: Pt, c1: Pt, p1: Pt): Route {
  let len = 0;
  let prev = p0;
  for (let k = 1; k <= 16; k++) {
    const t = k / 16;
    const u = 1 - t;
    const p: Pt = [
      u * u * u * p0[0] + 3 * u * u * t * c0[0] + 3 * u * t * t * c1[0] + t * t * t * p1[0],
      u * u * u * p0[1] + 3 * u * u * t * c0[1] + 3 * u * t * t * c1[1] + t * t * t * p1[1],
    ];
    len += dist(prev, p);
    prev = p;
  }
  return { d: `M${f1(p0[0])} ${f1(p0[1])}C${f1(c0[0])} ${f1(c0[1])} ${f1(c1[0])} ${f1(c1[1])} ${f1(p1[0])} ${f1(p1[1])}`, len };
}

/** A polyline with its corners rounded (radius r), as the winner drew the lanes round the card. */
export function rounded(points: readonly Pt[], r: number): Route {
  const q: Pt[] = [points[0]!];
  for (const p of points.slice(1)) {
    const last = q[q.length - 1]!;
    if (Math.abs(p[0] - last[0]) > 0.5 || Math.abs(p[1] - last[1]) > 0.5) q.push(p);
  }
  let len = 0;
  for (let i = 1; i < q.length; i++) len += dist(q[i - 1]!, q[i]!);
  if (q.length < 2) return { d: `M${f1(q[0]![0])} ${f1(q[0]![1])}`, len: 0 };
  let d = `M${f1(q[0]![0])} ${f1(q[0]![1])}`;
  for (let j = 1; j < q.length - 1; j++) {
    const p0 = q[j - 1]!;
    const p = q[j]!;
    const p1 = q[j + 1]!;
    const l0 = dist(p0, p);
    const l1 = dist(p, p1);
    const rr = Math.min(r, l0 / 2, l1 / 2);
    if (rr < 0.6) {
      d += `L${f1(p[0])} ${f1(p[1])}`;
      continue;
    }
    const s: Pt = [p[0] + ((p0[0] - p[0]) / l0) * rr, p[1] + ((p0[1] - p[1]) / l0) * rr];
    const e: Pt = [p[0] + ((p1[0] - p[0]) / l1) * rr, p[1] + ((p1[1] - p[1]) / l1) * rr];
    d += `L${f1(s[0])} ${f1(s[1])}Q${f1(p[0])} ${f1(p[1])} ${f1(e[0])} ${f1(e[1])}`;
  }
  const last = q[q.length - 1]!;
  return { d: `${d}L${f1(last[0])} ${f1(last[1])}`, len };
}

/** Two pieces in one side column: a bracket that bows into the moat between the column and the card. */
function bracket(a: Box, b: Box, bow: "left" | "right"): Route {
  const y0 = a.y + a.h / 2;
  const y1 = b.y + b.h / 2;
  const x0 = bow === "right" ? a.x + a.w : a.x;
  const x1 = bow === "right" ? b.x + b.w : b.x;
  const k = (bow === "right" ? 1 : -1) * (14 + Math.min(10, Math.abs(y0 - y1) * 0.06)) * 1.35;
  return cubic([x0, y0], [x0 + k, y0], [x1 + k, y1], [x1, y1]);
}

/** Two pieces in one row (the steps, or the never line): an arc on the card's side of the row. */
function rowArc(a: Box, b: Box, below: boolean): Route {
  if (Math.abs(a.y - b.y) > 6) {
    const down = b.y > a.y;
    const p0: Pt = [a.x + a.w / 2, down ? a.y + a.h : a.y];
    const p1: Pt = [b.x + b.w / 2, down ? b.y : b.y + b.h];
    const k = Math.abs(p1[1] - p0[1]) * 0.5;
    return cubic(p0, [p0[0], p0[1] + (down ? k : -k)], [p1[0], p1[1] + (down ? -k : k)], p1);
  }
  const x0 = a.x + a.w / 2;
  const x1 = b.x + b.w / 2;
  const y = below ? a.y + a.h : a.y;
  const cols = Math.max(1, Math.round(Math.abs(x1 - x0) / (a.w + 6)));
  const depth = Math.min(20, 7 + 4 * (cols - 1)) * 1.33 * (below ? 1 : -1);
  return cubic([x0, y], [x0, y + depth], [x1, y + depth], [x1, y]);
}

/** Where a piece leaves its zone for the lanes round the card: the edge facing the card. */
function port(end: LinkEnd): Pt {
  const { box: b, side } = end;
  if (side === "left") return [b.x + b.w, b.y + b.h / 2];
  if (side === "right") return [b.x, b.y + b.h / 2];
  if (side === "top") return [b.x + b.w / 2, b.y + b.h];
  return [b.x + b.w / 2, b.y];
}

/**
 * A link between pieces in different zones, on a ring road round the card: each end steps straight
 * out to the lane on its side, then the link follows the lane the nearer way round. The winner had
 * lanes only for left-top, top-right and left-right and drew everything else as a straight line
 * through the card; here every pair goes round it. `k` picks a lane, so bundles nest.
 */
function ringRoute(from: LinkEnd, to: LinkEnd, hub: Box, k: number, lane: number): Route {
  const xL = hub.x - 13 - k * lane;
  const xR = hub.x + hub.w + 13 + k * lane;
  const yT = hub.y - 13 - k * lane;
  const yB = hub.y + hub.h + 13 + k * lane;
  const W = xR - xL;
  const H = yB - yT;
  const P = 2 * (W + H);
  const clampX = (x: number) => Math.min(xR, Math.max(xL, x));
  const clampY = (y: number) => Math.min(yB, Math.max(yT, y));

  /** The point on the lane an end steps out to, and its distance along the ring (clockwise from top-left). */
  const enter = (end: LinkEnd): { out: Pt; on: Pt; t: number } => {
    const p = port(end);
    if (end.side === "left") {
      const on: Pt = [xL, clampY(p[1])];
      return { out: [xL, p[1]], on, t: 2 * W + H + (yB - on[1]) };
    }
    if (end.side === "right") {
      const on: Pt = [xR, clampY(p[1])];
      return { out: [xR, p[1]], on, t: W + (on[1] - yT) };
    }
    if (end.side === "top") {
      const on: Pt = [clampX(p[0]), yT];
      return { out: [p[0], yT], on, t: on[0] - xL };
    }
    const on: Pt = [clampX(p[0]), yB];
    return { out: [p[0], yB], on, t: W + H + (xR - on[0]) };
  };

  const a = enter(from);
  const b = enter(to);
  const cw = (((b.t - a.t) % P) + P) % P;
  const clockwise = cw <= P - cw;
  const corners: [number, Pt][] = [
    [0, [xL, yT]],
    [W, [xR, yT]],
    [W + H, [xR, yB]],
    [2 * W + H, [xL, yB]],
  ];
  const along: Pt[] = [];
  const span = clockwise ? cw : P - cw;
  const passed = corners
    .map(([t, pt]) => {
      const d = clockwise ? (((t - a.t) % P) + P) % P : (((a.t - t) % P) + P) % P;
      return [d, pt] as const;
    })
    .filter(([d]) => d > 0 && d < span)
    .sort((x, y) => x[0] - y[0]);
  for (const [, pt] of passed) along.push(pt);
  return rounded([port(from), a.out, a.on, ...along, b.on, b.out, port(to)], 9);
}

/**
 * The route of one link. Same column: a bracket in the moat. Same row: an arc on the card's side.
 * A side piece level with the steps row: the winner's short curve up to the step. Otherwise round
 * the card, the nearer way.
 */
export function routeLink(from: LinkEnd, to: LinkEnd, hub: Box, k: number, lane: number): Route {
  if (from.side === to.side) {
    if (from.side === "left") return bracket(from.box, to.box, "right");
    if (from.side === "right") return bracket(from.box, to.box, "left");
    return rowArc(from.box, to.box, from.side === "top");
  }
  const yT = hub.y - 13 - k * lane;
  const sideToTop = (s: LinkEnd, t: LinkEnd) => (s.side === "left" || s.side === "right") && t.side === "top" && port(s)[1] <= yT + 6;
  if (sideToTop(from, to) || sideToTop(to, from)) {
    const a = port(from);
    const b = port(to);
    const pull = (p: Pt, end: LinkEnd): Pt =>
      end.side === "top" ? [p[0], p[1] + 40] : [p[0] + (end.side === "left" ? 40 : -40), p[1]];
    return cubic(a, pull(a, from), pull(b, to), b);
  }
  return ringRoute(from, to, hub, k, lane);
}

/** One drawn link and the lane it took. */
export interface LinkIn {
  key: string;
  from: LinkEnd;
  to: LinkEnd;
}

/**
 * Lanes for a set of links: links of one kind (side to side) are sorted by where they start, and the
 * lower ones take the inner lanes, so bundles nest instead of crossing (the winner's rule).
 */
export function routeAll(links: readonly LinkIn[], hub: Box, lane: number): Map<string, Route> {
  const groups = new Map<string, LinkIn[]>();
  for (const l of links) {
    const g = `${l.from.side}>${l.to.side}`;
    groups.set(g, [...(groups.get(g) ?? []), l]);
  }
  const out = new Map<string, Route>();
  for (const g of groups.values()) {
    const sorted = [...g].sort((p, q) => p.from.box.y - q.from.box.y || p.to.box.x - q.to.box.x);
    sorted.forEach((l, i) => out.set(l.key, routeLink(l.from, l.to, hub, (sorted.length - 1 - i) % 5, lane)));
  }
  return out;
}

/** Whether a route enters the card: its M/L/Q/C segments sampled along their length. For tests. */
export function crosses(d: string, hub: Box): boolean {
  const inside = ([x, y]: Pt) => x > hub.x + 1 && x < hub.x + hub.w - 1 && y > hub.y + 1 && y < hub.y + hub.h - 1;
  let at: Pt = [0, 0];
  for (const m of d.matchAll(/([MLQC])([^MLQC]*)/g)) {
    const n = [...m[2]!.matchAll(/-?\d+(?:\.\d+)?/g)].map((x) => Number(x[0]));
    const pts: Pt[] = [];
    for (let i = 0; i + 1 < n.length; i += 2) pts.push([n[i]!, n[i + 1]!]);
    const end = pts[pts.length - 1]!;
    for (let k = 0; k <= 24; k++) {
      const t = k / 24;
      const u = 1 - t;
      let p: Pt = end;
      if (m[1] === "L") p = [at[0] + (end[0] - at[0]) * t, at[1] + (end[1] - at[1]) * t];
      else if (m[1] === "Q") {
        const c = pts[0]!;
        p = [u * u * at[0] + 2 * u * t * c[0] + t * t * end[0], u * u * at[1] + 2 * u * t * c[1] + t * t * end[1]];
      } else if (m[1] === "C") {
        const [c0, c1] = [pts[0]!, pts[1]!];
        p = [
          u * u * u * at[0] + 3 * u * u * t * c0[0] + 3 * u * t * t * c1[0] + t * t * t * end[0],
          u * u * u * at[1] + 3 * u * u * t * c0[1] + 3 * u * t * t * c1[1] + t * t * t * end[1],
        ];
      }
      if (inside(p)) return true;
    }
    at = end;
  }
  return false;
}
