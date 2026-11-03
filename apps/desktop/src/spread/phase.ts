// The page being written (ADR 0024), as a table. It asks (the composer), then she writes (receipts,
// the clock, Stop), then the page settles into the book and the window turns to it. Only when the
// conversation cannot be read back does the page stay, failed, with "Try again".

import type { Live } from "../athena/store";

export type Phase = "ask" | "writing" | "failed";
export type PhaseEvent = "send" | "settle" | "fail" | "retry" | "again";

/** Every legal move. An event a phase does not list leaves it where it is. */
export const PHASE: Readonly<Record<Phase, Partial<Record<PhaseEvent, Phase>>>> = {
  ask: { send: "writing" },
  writing: { settle: "ask", fail: "failed" },
  failed: { retry: "writing", again: "ask" },
};

export function nextPhase(p: Phase, e: PhaseEvent): Phase {
  return PHASE[p][e] ?? p;
}

/** What each phase shows on the page. */
export const SHOWS: Readonly<Record<Phase, { composer: boolean; stop: boolean; clock: boolean; retry: boolean }>> = {
  ask: { composer: true, stop: false, clock: false, retry: false },
  writing: { composer: false, stop: true, clock: true, retry: false },
  failed: { composer: false, stop: false, clock: false, retry: true },
};

/** The phase the conversation store is in. A page that has ended but not yet settled (the reload is on
 *  its way) still reads as written, so the composer does not flash between the two. */
export function phaseOf(s: { streaming: boolean; live: Live | null }): Phase {
  if (s.live?.error !== undefined && !s.streaming) return "failed";
  if (s.streaming || s.live !== null) return "writing";
  return "ask";
}
