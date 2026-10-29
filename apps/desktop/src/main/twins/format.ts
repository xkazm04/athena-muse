// What the twins page reads from the wire, computed and never stored: time words against a "now",
// money and counts ("-" when unmeasured, never 0), each channel's clearance in plain words, and the
// twin rubric the bottom panel's coverage parts read.

import type { Mission, Place, TwinChannel, TwinDraft, TwinSummary } from "../../lib/contract";
import type { Rubric } from "../stage/select";
import { CHANNEL_LABEL, LEVEL, PLACE_LABEL } from "./words";

/** The places a twin is made of, in setup order, and what setup needs of each (SCHEMA.md `places`). */
export const TWIN_RUBRIC: Rubric<Place> = {
  places: ["who", "channels", "voice", "knowledge", "chores", "never", "autonomy", "memory", "mission"],
  required: { who: 1, channels: 1, voice: 1, knowledge: 0.5, chores: 0.5, never: 1, autonomy: 1, memory: 0, mission: 0 },
};

/** "She still needs ..." per place: the place's label, lower case. */
export const NEED_PHRASE = Object.fromEntries(
  TWIN_RUBRIC.places.map((p) => [p, PLACE_LABEL[p].toLowerCase()]),
) as Record<Place, string>;

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function day(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

/** Relative words against `now`: "just now", "28 min ago", "2 h ago", "yesterday", "26 Sep"; "-" when absent. */
export function rel(iso: string | undefined, now: Date): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  const min = Math.round((now.getTime() - d.getTime()) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  if (d.toDateString() === now.toDateString()) return `${Math.round(min / 60)} h ago`;
  const y = new Date(now);
  y.setDate(y.getDate() - 1);
  if (d.toDateString() === y.toDateString()) return "yesterday";
  return day(iso);
}

/** "$1.90"; "-" when unmeasured. Callers add "est.". */
export const money = (v: number | undefined) => (v === undefined ? "-" : `$${v.toFixed(2)}`);
/** A count; "-" when unmeasured, never 0. */
export const num = (v: number | undefined) => (v === undefined ? "-" : String(v));
export const secs = (s: number) => `${s.toFixed(1)} s`;
export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const levelOf = (c: TwinChannel) => LEVEL[c.autonomy].label;

/** One channel's clearance, in full: "first message Assist, replies Auto at 80". */
export function clearance(c: TwinChannel): string {
  if (c.split) return `first message ${LEVEL[c.split.first_message].label}, replies ${LEVEL[c.split.reply].label} at ${c.bar}`;
  return `${levelOf(c)}${c.autonomy === "auto" ? ` at ${c.bar}` : ""}${c.scope ? `, ${c.scope}` : ""}`;
}

/** One channel's clearance, short: "Assist first, then Auto at 80". */
export function clearanceShort(c: TwinChannel): string {
  if (c.split) return `${LEVEL[c.split.first_message].label} first, then ${LEVEL[c.split.reply].label} at ${c.bar}`;
  return `${levelOf(c)}${c.autonomy === "auto" ? ` at ${c.bar}` : ""}`;
}

export const channelLabel = (c: TwinChannel) => CHANNEL_LABEL[c.kind];

/** The newest thing a twin did: a channel heard from or a mission moved. */
export function lastOf(t: TwinSummary): string | undefined {
  const all = [...t.channels.map((c) => c.last_at), ...t.missions.map((m) => m.last_at)].filter(
    (x): x is string => !!x,
  );
  return all.sort().at(-1);
}

/** Drafts and hand-backs: what waits for the person on one twin. */
export const handedBack = (t: TwinSummary) => t.missions.filter((m) => m.state === "handed_back");
export const waitsOn = (t: TwinSummary) => t.waiting.length + handedBack(t).length;

/** The bar a waiting draft was held against: its own, else its channel's when that is on Auto. */
export function barOf(d: TwinDraft, t: TwinSummary): number | undefined {
  if (d.bar !== undefined) return d.bar;
  const ch = t.channels.find((c) => c.kind === d.channel);
  return ch && ch.autonomy === "auto" ? ch.bar : undefined;
}

/** The beat a mission is on (1-based), or one past the end when every beat is done. */
export function beatAt(m: Mission): number {
  const i = m.beats.findIndex((b) => !b.done);
  return i < 0 ? m.beats.length + 1 : i + 1;
}

/** The first sentence of a text, for a one-line quote. */
export function firstSentence(text: string): string {
  const m = text.match(/^.*?[.!?](\s|$)/);
  return (m ? m[0] : text).trim();
}
