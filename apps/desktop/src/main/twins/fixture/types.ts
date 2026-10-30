// The twins page's invented example in wire shape: what the daemon answered for the overview, each
// twin, the setup conversation and its dress rehearsal. Generated into twins.ts by
// scripts/twin_fixture.py, which drives the daemon itself (scripted engine, fake Gmail and Notion) and
// checks every object against contracts.py, so the store's tests and the preview harness replay exactly
// what the routes answer. Invented data, labelled on screen.

import type {
  GoalList,
  MarkBody,
  ThreadList,
  TwinDetail,
  TwinPage,
  TwinPreview,
  TwinRehearsalEvent,
  TwinSayBody,
  TwinSetupEvent,
} from "../../../lib/contract";

/** One reply of the setup conversation: what the person did on the slip first (inked her pencil,
 * picked, connected), what they said, the stream back, the twin after it. */
export interface SetupFrame {
  /** The twin as the slip's own act answered it, before the reply; absent when it answered none. */
  before?: TwinDetail;
  say: TwinSayBody;
  /** How long her reply takes in the example (the prototype's pace; the scripted engine is instant). */
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

/** One mark the person made on a waiting draft (`POST /twins/{id}/rehearse/mark`) and the twin after it. */
export interface RehearsalMark {
  mark: MarkBody;
  twin: TwinDetail;
}

export interface TwinFixture {
  invented: string;
  /** The example's "now": every relative time on the page is read against it. */
  now: string;
  /** `GET /twins` as the Partnerships setup ends: one live, one paused, one being set up. */
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
    /** `POST /twins {space_id: ""}`: a blank twin in a Project of its own. */
    created: TwinDetail;
    frames: SetupFrame[];
    rehearsal: {
      goal: string;
      /** The daemon plays the whole conversation in one stream: its first message and a held reply
       * wait for the person, a reply goes on its own, then the outcome. */
      events: TimedRehearsal[];
      /** `GET /twins/{id}` once it has played, before any mark. */
      played: TwinDetail;
      /** The person's marks on the drafts that waited, oldest first. */
      marks: RehearsalMark[];
      /** The twin once every waiting draft is marked. */
      rehearsed: TwinDetail;
      /** "Try it another way": the other side asks for money and it hands the conversation back. */
      handed: { goal: string; events: TimedRehearsal[]; after: TwinDetail };
    };
    /** `POST /twins/{id}/golive`: the twin as issued. */
    golive: TwinDetail;
  };
  /** `GET /twins/{id}/preview` per twin once Partnerships is live (its second: what changed shows). */
  previews: Record<string, TwinPreview>;
  /** `GET /twins/{id}/threads` per live twin: the new entry slip's recent conversations. */
  threads: Record<string, ThreadList>;
  /** `POST /twins/{id}/goals {thread}` for one conversation: the goals Athena suggests for it. */
  goals: Record<string, GoalList & { thread: string }>;
}
