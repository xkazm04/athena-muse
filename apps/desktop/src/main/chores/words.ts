// Plain words, tones and order for the Chores scene. Pure: the tiles, the detail and the preview
// all read from here, so the rules ("a rehearsed chore is never green") live in one place.

import type { BenchWord, ChoreSummary, EngineId, FeaturedStatus, ProofOp, SenseName } from "../../lib/contract";

/** A `.badge` data-tone. `undefined` is the plain, muted badge. */
export type Tone = "success" | "info" | "warning" | "error" | undefined;

export const SENSE_WORD: Record<SenseName, string> = {
  paper: "Paper",
  call: "Call",
  walk: "Walk",
  circle: "Circle",
};

/** Featured status in plain words. Green (success) means proven on Meta and nothing else. */
export const STATUS: Record<FeaturedStatus, { word: string; tone: Tone }> = {
  proven: { word: "Proven on Meta", tone: "success" },
  rehearsed: { word: "Rehearsed on fixtures", tone: "info" },
  failing: { word: "A proof is failing", tone: "error" },
  unproven: { word: "Not proven yet", tone: undefined },
};

/**
 * The bench verdict. It never takes the success colour: a tile's green is reserved for "proven on
 * Meta", and a verdict reached on fixtures or a development engine must not read as that.
 */
export const VERDICT: Record<BenchWord, { word: string; tone: Tone }> = {
  exceeds: { word: "Exceeds the bar", tone: "info" },
  meets: { word: "Meets the bar", tone: "info" },
  short: { word: "Short of the bar", tone: "warning" },
};

export const ENGINE_WORD: Record<EngineId, string> = {
  muse: "Muse",
  muse_code: "Muse Code",
  claude_code: "Claude Code",
  scripted: "Scripted",
};

export const OP_WORD: Record<ProofOp, string> = { ">=": "≥", "<=": "≤" };

/** A proof's pass badge: green only when the chore is proven on Meta, so fixtures never look proven. */
export function passTone(passed: boolean, featured: FeaturedStatus): Tone {
  if (!passed) return "error";
  return featured === "proven" ? "success" : "info";
}

const RANK: Record<FeaturedStatus, number> = { proven: 0, rehearsed: 1, failing: 2, unproven: 3 };

const byTitle = (a: ChoreSummary, b: ChoreSummary) => a.title.localeCompare(b.title);

/** Featured chores (non-empty `senses`) ordered proven, rehearsed, failing, unproven, then title; the rest by title. */
export function arrange(chores: ChoreSummary[]): { featured: ChoreSummary[]; others: ChoreSummary[] } {
  const featured = chores
    .filter((c) => c.senses.length > 0)
    .sort((a, b) => RANK[a.featured] - RANK[b.featured] || byTitle(a, b));
  const others = chores.filter((c) => c.senses.length === 0).sort(byTitle);
  return { featured, others };
}

/** Dollars with thousands separators: "$10,400", "$1,234.50"; under a dollar, four decimals. */
export function usd(n: number): string {
  if (n !== 0 && Math.abs(n) < 1) return `$${n.toFixed(4)}`;
  const cents = Number.isInteger(n) ? 0 : 2;
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: cents, maximumFractionDigits: cents })}`;
}

/** A measured figure: whole numbers as they are, fractions to at most three places. */
export function figure(n: number): string {
  return n.toLocaleString("en-US", { maximumFractionDigits: 3 });
}

export const count = (n: number, one: string, many: string) => `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;

export function minutes(n: number): string {
  return `${n.toLocaleString("en-US", { maximumFractionDigits: 1 })} min`;
}

export function when(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

/** What read the senses, grouped: {reader: "fixture", segmenter: "fixture"} -> ["Read with fixtures (reader, segmenter)"]. */
export function backendLines(backends: Record<string, string>): string[] {
  const roles = new Map<string, string[]>();
  for (const [role, backend] of Object.entries(backends)) roles.set(backend, [...(roles.get(backend) ?? []), role]);
  return [...roles.entries()].map(([backend, rs]) => `${backendWord(backend)} (${rs.sort().join(", ")})`);
}

export function backendWord(backend: string): string {
  switch (backend) {
    case "fixture":
    case "fixtures":
      return "Read with fixtures";
    case "muse_code":
      return "Read with Muse Code";
    case "meta":
    case "muse":
      return "Read with Muse";
    default:
      return `Read with ${backend}`;
  }
}

export const benchCommand = (id: string) => `python -m athena.bench ${id}`;
