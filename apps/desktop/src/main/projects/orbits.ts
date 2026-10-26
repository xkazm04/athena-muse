// Geometry of the projects field: each project an elliptical orbit around the core, at its own
// radius and tilt. Pure functions so the layout is testable without a browser.

import type { SpaceSummary } from "../../lib/contract";

export interface Orbit {
  id: string;
  rx: number;
  ry: number;
  /** tilt in degrees */
  tilt: number;
  /** the closed ellipse as an SVG path, for the ring and for moons to travel on */
  path: string;
  /** where the project's label sits, in stage pixels */
  label: { x: number; y: number };
  /** where each app's moon sits when still */
  moons: { x: number; y: number; letter: string; origin: string; phase: number }[];
  /** 0..1, from how much the project remembers */
  halo: number;
  /** seconds per turn of its moons; outer orbits are slower */
  period: number;
}

const GOLDEN = Math.PI * (3 - Math.sqrt(5));

/** First letter of an origin's host ("https://www.github.com" -> "G"). */
export function hostInitial(origin: string): string {
  let host = origin;
  try {
    host = new URL(origin).hostname;
  } catch {
    // not a URL; use the text as it is
  }
  host = host.replace(/^www\./, "");
  return (host.match(/[a-z0-9]/i)?.[0] ?? "?").toUpperCase();
}

function point(cx: number, cy: number, rx: number, ry: number, tiltDeg: number, t: number) {
  const a = (tiltDeg * Math.PI) / 180;
  const x = rx * Math.cos(t);
  const y = ry * Math.sin(t);
  return { x: cx + x * Math.cos(a) - y * Math.sin(a), y: cy + x * Math.sin(a) + y * Math.cos(a) };
}

const r1 = (n: number) => Math.round(n * 10) / 10;

export function layoutOrbits(spaces: SpaceSummary[], width: number, height: number): Orbit[] {
  const cx = width / 2;
  const cy = height / 2;
  const flat = 0.42;
  const inner = Math.max(80, Math.min(width, height) * 0.2);
  const outer = Math.max(inner + 20, Math.min(width / 2 - 40, (height / 2 - 28) / flat));
  const n = spaces.length;
  const step = n > 1 ? Math.min(64, (outer - inner) / (n - 1)) : 0;

  return spaces.map((s, i) => {
    const rx = inner + step * i;
    const ry = rx * flat;
    // Tilt from the hue so a project keeps its angle across reloads.
    const tilt = ((s.hue % 30) - 15) * 0.8;
    const p0 = point(cx, cy, rx, ry, tilt, 0);
    const p1 = point(cx, cy, rx, ry, tilt, Math.PI);
    const path =
      `M${r1(p0.x)} ${r1(p0.y)} A${r1(rx)} ${r1(ry)} ${r1(tilt)} 1 1 ${r1(p1.x)} ${r1(p1.y)} ` +
      `A${r1(rx)} ${r1(ry)} ${r1(tilt)} 1 1 ${r1(p0.x)} ${r1(p0.y)} Z`;
    const labelT = -Math.PI / 2 + i * GOLDEN;
    const label = point(cx, cy, rx, ry, tilt, labelT);
    const moons = s.apps.map((origin, k) => {
      const phase = s.apps.length ? k / s.apps.length : 0;
      const at = point(cx, cy, rx, ry, tilt, labelT + Math.PI + phase * 2 * Math.PI);
      return { x: at.x, y: at.y, letter: hostInitial(origin), origin, phase };
    });
    const total = s.counts.episodes + s.counts.facts;
    return {
      id: s.id,
      rx,
      ry,
      tilt,
      path,
      label,
      moons,
      halo: Math.min(1, Math.log1p(total) / Math.log1p(200)),
      period: 40 + i * 6,
    };
  });
}
