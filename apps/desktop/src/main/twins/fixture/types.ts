// The twins page's invented example in wire shape: what the daemon would answer for the overview, each
// twin, the setup conversation and its dress rehearsal. Generated into twins.ts by
// scripts/twin_fixture.py and checked there against contracts.py, so the store's tests and the preview
// harness replay exactly what the routes answer. When the twin store lands (WP3) the generator drives
// the daemon's scripted setup instead; this shape stays. Invented data, labelled on screen.

import type {
  MarkBody,
  TwinDetail,
  TwinPage,
  TwinRehearsalEvent,
  TwinSayBody,
  TwinSetupEvent,
} from "../../../lib/contract";

/** One reply of the setup conversation: what the person said, the stream back, the twin after it. */
export interface SetupFrame {
  say: TwinSayBody;
  /** How long her reply took (illustrative, within the measured 3-8 s). */
  elapsed_s: number;
  events: TwinSetupEvent[];
  /** `GET /twins/{id}` after this reply: the panels' material (samples, pages, presets, facts) with it. */
  twin: TwinDetail;
}

/** A stream event with the second it arrived at, counted from the start of the rehearsal. */
export interface TimedRehearsal {
  at_s: number;
  event: TwinRehearsalEvent;
}

/**
 * One stretch of the rehearsal stream, up to the next draft that waits for the person. Every stretch
 * after the first follows the person's mark (`POST /twins/{id}/rehearse/mark`) and the twin it answered.
 */
export interface RehearsalLeg {
  mark?: MarkBody;
  twin?: TwinDetail;
  events: TimedRehearsal[];
}

export interface TwinFixture {
  invented: string;
  /** The example's "now": every relative time on the page is read against it. */
  now: string;
  /** `GET /twins` today: one live, one paused, one being set up. */
  page: TwinPage;
  /** `GET /twins` after the twin being set up goes live. */
  pageAfter: TwinPage;
  /** `GET /twins/{id}` for the twins made before this example began. */
  details: Record<string, TwinDetail>;
  setup: {
    twinId: string;
    need: string;
    /** The first reply after which the rehearsal may start. */
    firstReadyFrame: number;
    /** `POST /twins {space_id}`: a blank twin. */
    created: TwinDetail;
    frames: SetupFrame[];
    rehearsal: {
      goal: string;
      where: string;
      playedBy: string;
      /** The usual path: its first message, the held reply, then the reply that went on its own. */
      legs: RehearsalLeg[];
      /** "Try it another way": the other side asks for money and it hands the conversation back. */
      handed: RehearsalLeg & { after: TwinDetail };
      /** The twin once the usual path resolved. */
      rehearsed: TwinDetail;
    };
    /** `POST /twins/{id}/golive`: the twin as issued. */
    golive: TwinDetail;
  };
}
