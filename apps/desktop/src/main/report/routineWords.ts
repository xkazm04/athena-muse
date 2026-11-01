// What Athena does on her own (business Phase 2), in plain words. Nothing here computes a figure: every
// count, time and spend is the daemon's, and the screen only formats it. The daemon's note on a run is
// already in screen words and is shown as given, beside the line.

import type { Routine, RoutineKind, RoutineRun, SkipReason } from "../../lib/contract";
import { rel } from "./format";

/** Why a run did nothing, after "skipped: ". */
export const SKIP_WORD: Record<SkipReason, string> = {
  running: "it was already running",
  live_turn: "you were talking with her",
  paused: "it is paused",
  no_browser: "her browser is closed",
  signed_out: "sign in again",
  no_engine: "Athena has no engine to think with",
  no_twin: "no twin set up for this project",
  nothing_to_do: "nothing to do",
};

/** Where a signed-out run could not get in, by what it reads. */
const SIGNED_OUT: Partial<Record<RoutineKind, string>> = {
  inbox: "sign in to the mailbox again",
  stats: "sign in to the analytics page again",
};

/** What `of` counts, by what it reads (only these kinds say how many there were). */
const OF_UNIT: Partial<Record<RoutineKind, [string, string]>> = {
  watch: ["creator", "creators"],
  twin: ["mission", "missions"],
};

/** The page an inbox or stats routine reads, asked for by name when it has none. */
export const URL_LABEL: Partial<Record<RoutineKind, { label: string; placeholder: string }>> = {
  inbox: { label: "Mailbox address", placeholder: "https://mail.example.com/inbox" },
  stats: { label: "Analytics page", placeholder: "https://studio.example.com/analytics" },
};

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The counts of a run that did its work: "found 3, kept 1, 1 draft for you". */
function counts(run: RoutineRun): string {
  const parts = [`found ${run.found}`, `kept ${run.kept}`];
  if (run.cards > 0) parts.push(`${plural(run.cards, "draft", "drafts")} for you`);
  return parts.join(", ");
}

/** It reached its spending limit: what it spent is at least what it may spend (both the daemon's). */
export const atLimit = (routine: Routine, run: RoutineRun): boolean =>
  run.outcome === "partial" && run.spent_usd !== undefined && run.spent_usd >= routine.ceiling_usd;

/** The last run in one line: "ran 12 min ago - found 3, kept 1, 1 draft for you". Without `now`, the
 * same line with no time in it (the table of runs has its own column for when). */
export function runLine(routine: Routine, run: RoutineRun, now?: Date): string {
  const at = (verb: string) => (now ? `${verb} ${rel(run.ended ?? run.started, now)}` : verb);
  if (run.outcome === "ran") return `${at("ran")} - ${counts(run)}`;
  if (run.outcome === "partial") {
    const unit = OF_UNIT[routine.kind];
    const of = run.of !== undefined && unit ? `${plural(run.of, unit[0], unit[1])} to read, ` : "";
    return `${at(atLimit(routine, run) ? "stopped at its spending limit" : "stopped part way")} - ${of}${counts(run)}`;
  }
  if (run.outcome === "failed") return at("did not finish");
  const reason = run.reason ?? "nothing_to_do";
  const why = reason === "signed_out" ? (SIGNED_OUT[routine.kind] ?? SKIP_WORD.signed_out) : SKIP_WORD[reason];
  return `${at("skipped")}: ${why}`;
}

/** "next in 4 h", "next in 20 min", "paused". Read from the daemon's next_at only. */
export function nextLine(routine: Routine, now: Date): string {
  if (routine.state === "paused") return "paused";
  if (!routine.next_at) return "next: not planned";
  const at = new Date(routine.next_at);
  if (Number.isNaN(at.getTime())) return "next: not planned";
  const min = Math.round((at.getTime() - now.getTime()) / 60000);
  if (min <= 0) return "next any moment";
  if (min < 60) return `next in ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `next in ${h} h`;
  return `next in ${Math.round(h / 24)} days`;
}

/** What a run spent, as the daemon priced it: "$0.30 est."; none when it gave no price. */
export function spentLine(run: RoutineRun | undefined): string | undefined {
  if (run?.spent_usd === undefined) return undefined;
  return run.spent_usd > 0 && run.spent_usd < 0.01 ? "under $0.01 est." : `$${run.spent_usd.toFixed(2)} est.`;
}

/** The row's tone: what needs the person (a sign-in, a failure, a limit) is warning; a run is quiet. */
export function toneOf(routine: Routine): "ok" | "warn" | "quiet" {
  const run = routine.last_run;
  if (!run) return "quiet";
  if (run.outcome === "failed" || run.outcome === "partial" || run.reason === "signed_out") return "warn";
  return run.outcome === "ran" ? "ok" : "quiet";
}

/** The routine has no page of its own yet and needs one to read (an inbox, an analytics page). */
export const needsUrl = (routine: Routine): boolean => !routine.url && URL_LABEL[routine.kind] !== undefined;
