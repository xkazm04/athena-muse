// Plain words for what the report shows. Nothing here computes a number: every figure is the daemon's,
// and the screen only formats it.

import type { RecordItem, ReportView, ThreadChannel, TrackVerdict } from "../../lib/contract";
import { day, rel } from "../twins/format";

export { day, rel };

/** How old a report may be before each part says "as of ...". */
export const STALE_MS = 30 * 60 * 1000;

export function isStale(view: ReportView, now: Date, failed = false): boolean {
  if (failed) return true;
  const t = new Date(view.rendered_at).getTime();
  return Number.isFinite(t) && now.getTime() - t > STALE_MS;
}

/** "1,204"; the daemon's figure, formatted only. */
export const figure = (n: number | undefined): string | undefined =>
  n === undefined ? undefined : n.toLocaleString("en-US", { maximumFractionDigits: 2 });

const YT_HOSTS = new Set(["youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"]);
const YT_ID = /^[A-Za-z0-9_-]{11}$/;

/** The video id of a YouTube address, or null for anything else (another site, or an address that does not parse). */
export function youtubeId(url: string): string | null {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    return null;
  }
  if (u.protocol !== "https:" && u.protocol !== "http:") return null;
  let id: string | null = null;
  if (u.hostname === "youtu.be") id = u.pathname.slice(1).split("/")[0] ?? null;
  else if (YT_HOSTS.has(u.hostname)) {
    if (u.pathname === "/watch") id = u.searchParams.get("v");
    else {
      const m = /^\/(?:shorts|embed|live)\/([^/]+)/.exec(u.pathname);
      id = m ? m[1]! : null;
    }
  }
  return id && YT_ID.test(id) ? id : null;
}

export const embedUrl = (id: string) => `https://www.youtube-nocookie.com/embed/${id}?autoplay=1`;

/** A creator's channel address as a name: its handle ("@lumen-tide"), else its host and path. */
export function creatorName(key: string | undefined): string {
  if (!key) return "-";
  try {
    const u = new URL(key);
    const handle = u.pathname.split("/").find((p) => p.startsWith("@"));
    if (handle) return handle;
    const rest = u.pathname.replace(/\/+$/, "");
    return `${u.hostname.replace(/^www\./, "")}${rest}`;
  } catch {
    return key;
  }
}

export const VERDICT_WORD: Record<TrackVerdict, string> = { keep: "Kept", pass: "Passed", later: "Later" };
export const VERDICT_ACT: Record<TrackVerdict, string> = { keep: "Keep", pass: "Pass", later: "Later" };

export const CHANNEL_WORD: Record<ThreadChannel, string> = { mail_web: "Mail", bio: "Bio message", comment: "Comment" };

const FIELD_WORD: Record<string, string> = {
  title: "Title",
  genre: "Genre",
  verdict: "Verdict",
  creator_key: "Creator",
  found_at: "Found",
  note: "Note",
  url: "Address",
  name: "Name",
  channel_url: "Channel",
  followed: "Followed",
  state: "State",
  plan: "Plan",
  metric: "Reading",
  value: "Value",
  measured_at: "Read",
  last_at: "Last",
  subject: "Subject",
  channel: "Where",
  track_key: "Track",
  credits: "Credits",
};

/** A column head for a body field, in plain words. */
export const fieldWord = (field: string): string =>
  FIELD_WORD[field] ?? `${field.charAt(0).toUpperCase()}${field.slice(1).replace(/_/g, " ")}`;

/** One field of an item as a cell: absent reads "-", times read relative, creators by name. */
export function cellText(item: RecordItem, field: string, now: Date): string {
  const v = item.body[field];
  if (v === undefined || v === null || v === "") return "-";
  if (field === "verdict" && typeof v === "string" && v in VERDICT_WORD) return VERDICT_WORD[v as TrackVerdict];
  if (field === "channel" && typeof v === "string" && v in CHANNEL_WORD) return CHANNEL_WORD[v as ThreadChannel];
  if (field.endsWith("_key") && field !== "track_key") return creatorName(String(v));
  if (field.endsWith("_at") && typeof v === "string") return rel(v, now);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return figure(v) ?? "-";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

/** A body field as a string, or undefined. */
export const str = (item: RecordItem, field: string): string | undefined => {
  const v = item.body[field];
  return typeof v === "string" && v ? v : undefined;
};

/** The genres already used on a project's tracks, most used first, for the queue's suggestions. */
export function genresOf(tracks: RecordItem[]): string[] {
  const n = new Map<string, number>();
  for (const t of tracks) {
    const g = str(t, "genre")?.trim();
    if (g) n.set(g, (n.get(g) ?? 0) + 1);
  }
  return [...n.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([g]) => g);
}

/** "1 part could not be shown" (the screen never says "block"; see the WP1.3 report). */
export const droppedLine = (n: number): string => `${n} ${n === 1 ? "part" : "parts"} could not be shown`;
