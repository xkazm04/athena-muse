// The staged conversation in wire shape: what the daemon would answer, step by step, for one invented
// need. Generated into staged.ts by scripts/stage_fixture.py through the daemon's own sketch rules, so
// the preview harness and the store's tests replay exactly what a live draft streams. Invented data.

import type {
  AuthorEvent,
  ChoreSummary,
  Draft,
  ExpectedList,
  KeyBody,
  RehearsalEvent,
  SayBody,
  SpaceSummary,
  TurnEvent,
  VerdictBody,
} from "../../../lib/contract";

/** One stage reply: what the person sent, the stream that came back, and the draft as stored after it. */
export interface StagedFrame {
  say: SayBody;
  /** How long she took to answer (illustrative, within the measured 3-8 s). */
  elapsed_s: number;
  events: TurnEvent[];
  draft: Draft;
  /** Her guesses the person inked after this reply (`POST /drafts/{id}/confirm`), and the draft then. */
  confirm?: { node_ids: string[]; draft: Draft };
}

/** A stream event with the second it arrived at, counted from the start of its request. */
export interface Timed<E> {
  at_s: number;
  event: E;
}

export interface Staged {
  invented: string;
  need: string;
  /** `POST /drafts {need}`: the draft at `describe`, nothing run yet. */
  created: Draft;
  frames: StagedFrame[];
  /** `POST /drafts/{id}/write`: one repair, then written. */
  author: Timed<AuthorEvent>[];
  written: Draft;
  /** The same write when two repairs do not fix it; the draft goes back to the sketch. */
  authorFailed: Timed<AuthorEvent>[];
  failedDraft: Draft;
  /** `POST /drafts/{id}/preview` after ~11 s. */
  preview: ExpectedList;
  previewed: Draft;
  /** `PUT /drafts/{id}/key`: 4 yes, 1 no, one missing line placed, one never line kept as words. */
  key: KeyBody;
  keyed: Draft;
  /** `POST /drafts/{id}/rehearse`: phases and filed cards (never signable), then the score. */
  rehearsal: Timed<RehearsalEvent>[];
  scored: Draft;
  verdict: VerdictBody;
  saved: Draft;
  /** "Not quite" instead: back to the sketch with the person's note. */
  revise: VerdictBody;
  revised: Draft;
  project: SpaceSummary;
  chore: ChoreSummary;
}
