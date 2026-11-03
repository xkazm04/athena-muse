// The book's model (ADR 0024): a conversation read as spreads. Pure: turns and cards in, pages,
// receipts, tallies and the bookmark's target out. Both windows draw from it; nothing here computes a
// figure, it only reads and words the ones the daemon kept.

import type { Card, Turn } from "../lib/contract";
import { settledParts, type LivePart } from "../athena/store";

/** One exchange: what the person asked and the Athena turn that answered it. Either side may be
 *  missing: she can speak first (the setup conversation), and a question may have no answer kept. */
export interface Exchange {
  /** "p1", "p2", ...: the page's key, stable for a conversation as long as no turn is erased. */
  key: string;
  /** 1-based page number. */
  num: number;
  person: Turn | null;
  reply: Turn | null;
  /** The reply's parts through the window's one reducer (empty when there is no reply). */
  parts: LivePart[];
  /** The engine stopped this try: its reason. */
  stopped?: string;
  /** A question with no answer kept at all (older data, or the person pressed Stop). */
  unanswered: boolean;
  /** The same words as the try just before, which stopped. */
  secondTry: boolean;
  /** The card ids this page holds, in order. */
  cards: string[];
}

const failed = (x: Exchange): boolean => x.stopped !== undefined || x.unanswered;

/** The conversation as exchanges, oldest first. */
export function exchangesOf(turns: readonly Turn[]): Exchange[] {
  const pairs: { person: Turn | null; reply: Turn | null }[] = [];
  for (const t of turns) {
    const open = pairs[pairs.length - 1];
    if (t.role === "person") pairs.push({ person: t, reply: null });
    else if (open && open.reply === null && open.person !== null) open.reply = t;
    else pairs.push({ person: null, reply: t });
  }
  const out: Exchange[] = [];
  pairs.forEach(({ person, reply }, i) => {
    const parts = reply ? (reply.parts ? settledParts(reply.parts) : legacyParts(reply)) : [];
    const prev = out[i - 1];
    const x: Exchange = {
      key: `p${i + 1}`,
      num: i + 1,
      person,
      reply,
      parts,
      unanswered: person !== null && reply === null,
      secondTry: false,
      cards: parts.flatMap((p) => (p.kind === "card" ? [p.id] : [])),
    };
    if (reply?.stopped !== undefined) x.stopped = reply.stopped;
    x.secondTry = !!prev && failed(prev) && !!person && prev.person?.text.trim() === person.text.trim();
    out.push(x);
  });
  return out;
}

/** A turn stored before parts were kept: its words, then its card. */
function legacyParts(t: Turn): LivePart[] {
  const parts: LivePart[] = [];
  if (t.text.trim()) parts.push({ kind: "text", text: t.text, marks: [0] });
  if (t.card_id) parts.push({ kind: "card", id: t.card_id });
  return parts;
}

/** Whether the next page tried the same words again (the stopped page links to it). */
export const triedAgainNext = (xs: readonly Exchange[], i: number): boolean => xs[i + 1]?.secondTry === true;

// --- what she did ------------------------------------------------------------------------------

/** The kind of step a receipt marks, which sets its dot. */
export type ReceiptSort = "look" | "memory" | "keep" | "card" | "parts" | "write" | "error" | "unknown";

export interface Receipt {
  sort: ReceiptSort;
  /** ms from the turn's start; absent when no figure was kept. */
  at?: number;
  text: string;
  sub?: string;
}

const SORT_OF: Record<string, ReceiptSort> = { record_list: "look", recall: "memory", remember: "memory", forget: "memory", record_put: "keep" };

/** "1 part could not be shown" / "2 parts could not be shown". */
export const droppedWords = (n: number): string => `${n} ${n === 1 ? "part" : "parts"} could not be shown`;

/**
 * One receipt per step she took, in the order she took it. `actionWords` names a card's action
 * (CardView's headings); `writing` says the last text run is still being written.
 */
export function receiptsOf(
  parts: readonly LivePart[],
  actionWords: (cardId: string) => string | undefined,
  opts: { stopped?: string; stoppedAt?: number; writing?: boolean } = {},
): Receipt[] {
  const out: Receipt[] = [];
  const at = (p: { at?: number }): { at?: number } => (p.at === undefined ? {} : { at: p.at });
  parts.forEach((p, n) => {
    switch (p.kind) {
      case "text":
        if (p.text.trim()) out.push({ sort: "write", ...at(p), text: opts.writing && n === parts.length - 1 ? "Writing to you" : "Wrote to you" });
        return;
      case "tool":
        out.push({ sort: SORT_OF[p.name] ?? "look", ...at(p), text: p.label });
        return;
      case "card": {
        const sub = actionWords(p.id);
        out.push({ sort: "card", ...at(p), text: "Filed a card for your signature", ...(sub ? { sub } : {}) });
        return;
      }
      case "blocks": {
        const titles = p.shown.blocks.map((b) => `“${b.title}”`).join(" and ");
        const text = titles ? `Showed parts of the report: ${titles}` : "Tried to show parts of the report";
        out.push({ sort: "parts", ...at(p), text, ...(p.shown.dropped ? { sub: droppedWords(p.shown.dropped) } : {}) });
        return;
      }
      case "unknown":
        out.push({ sort: "unknown", text: "A step this version of the app cannot show" });
        return;
    }
  });
  if (opts.stopped !== undefined) out.push({ sort: "error", ...(opts.stoppedAt === undefined ? {} : { at: opts.stoppedAt }), text: `Stopped: ${opts.stopped}` });
  return out;
}

// --- words for figures (format, never compute) ---------------------------------------------------

/** Muse costs are estimates; every one on screen says so. */
export function formatCost(usd: number): string {
  if (usd > 0 && usd < 0.0001) return "est. under $0.0001";
  return `est. $${usd < 1 ? usd.toFixed(4) : usd.toFixed(2)}`;
}

/** "4 s", "1 min 05 s". */
export function secs(ms: number): string {
  const t = Math.round(ms / 1000);
  if (t < 60) return `${t} s`;
  return `${Math.floor(t / 60)} min ${String(t % 60).padStart(2, "0")} s`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "3 Nov", in the person's own time zone. */
export function dateShort(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

/** A reply's words without their markdown, for a page's one-line name and the short-answer test. */
export function plainOf(src: string): string {
  return src
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/^#{1,3}\s+/gm, "")
    .replace(/\*\*|`|\*/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

/** Under this many plain characters, a one-paragraph answer is set large. */
export const SHORT_MAX = 240;

/** One run of words and nothing else (a tool line aside), short: the page sets it large. */
export function isShort(parts: readonly LivePart[]): boolean {
  const shown = parts.filter((p) => p.kind !== "tool");
  const only = shown[0];
  return shown.length === 1 && only?.kind === "text" && plainOf(only.text).length < SHORT_MAX;
}

// --- the bookmark ------------------------------------------------------------------------------

/** The page keys of the book the bookmark can open. */
export const NOW = "now";
export const WAITING = "waiting";

/** Waiting cards, in the order they were filed. */
export const waitingCards = (cards: Record<string, Card>): Card[] =>
  Object.values(cards)
    .filter((c) => c.state === "waiting")
    .sort((a, b) => a.created.localeCompare(b.created));

/** The waiting cards that sit on no page of this book (another project's, a routine's). */
export function strayWaiting(xs: readonly Exchange[], cards: Record<string, Card>, live: readonly LivePart[] = []): Card[] {
  const onPage = new Set([...xs.flatMap((x) => x.cards), ...live.flatMap((p) => (p.kind === "card" ? [p.id] : []))]);
  return waitingCards(cards).filter((c) => !onPage.has(c.id));
}

/** Where the bookmark opens: the first page holding a waiting card, else the page being written when
 *  it holds one, else the page of cards waiting elsewhere; null when nothing waits. */
export function bookmarkTarget(xs: readonly Exchange[], cards: Record<string, Card>, live: readonly LivePart[] = []): string | null {
  const waiting = new Set(waitingCards(cards).map((c) => c.id));
  if (waiting.size === 0) return null;
  const page = xs.find((x) => x.cards.some((id) => waiting.has(id)));
  if (page) return page.key;
  if (live.some((p) => p.kind === "card" && waiting.has(p.id))) return NOW;
  return WAITING;
}

/** "1 waits for your signature" / "3 wait for your signature". */
export const waitsWords = (n: number): string => `${n} ${n === 1 ? "waits" : "wait"} for your signature`;
