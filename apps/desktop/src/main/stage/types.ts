// The stage's shapes (onboarding v2, ADR 0007): one model, two views. The store folds the daemon's
// streams into StageState; a view draws it and sends StageActions back. Neither view owns state.

import type {
  AccessAct,
  Ask,
  AuthorEvent,
  Draft,
  DraftJobKind,
  DraftNotes,
  DraftVerdict,
  ExpectedCard,
  JobEvent,
  Mark,
  RehearsalEvent,
  SayBody,
  SketchOp,
  StageView,
  TurnEvent,
} from "../../lib/contract";
import type { StageWords } from "./words";

/** Where the current reply is: sent and waiting, slow past 8 s, or failed (never shown as progress). */
export type ReplyPhase = "idle" | "sending" | "thinking" | "slow" | "failed";

/** The frame that owns the window: her line, the one question, and what the last reply changed. */
export interface StageFrame {
  /** Her line in this reply, as it streamed. */
  line: string;
  ask: Ask | null;
  /** The person's last words or picked answer, echoed back. */
  youSaid: string;
  phase: ReplyPhase;
  /** Plain words for a failed reply or a refused action; "" when there is none. */
  problem: string;
  /** The sketch ops of the last reply, in order: the view animates exactly these. */
  lastOps: SketchOp[];
}

/** What the stage is waiting on from the daemon; one at a time. */
export type StageWork =
  | "describe"
  | "say"
  | "ink"
  | "drop"
  | "write"
  | "preview"
  | "key"
  | "rehearse"
  | "verdict"
  | "access"
  | "open";

/** A piece's place in one view, kept by node id so a piece never moves, whatever arrives after it. */
export interface Place {
  /** The view's own coordinates: a lane and row (Drawing) or a zone and cell (Orbit). */
  area: string;
  index: number;
}

export interface StageState {
  draft: Draft | null;
  frame: StageFrame;
  view: StageView;
  /** Per view, the places it has given each node id. Switching views never clears either. */
  places: Record<StageView, Record<string, Place>>;
  /** Pencil the person rubbed out, held for the undo toast before it is sent. */
  dropping: string[];
  author: AuthorEvent[];
  rehearsal: RehearsalEvent[];
  /** The marks being made on the preview, before they are sent as the key. */
  marks: Record<string, { mark: Mark; note?: string }>;
  missing: string[];
  never: string[];
  /** What is in flight, or null. A second daemon act waits until it is done. */
  work: StageWork | null;
  /** The act that failed last; `retry` sends it again. */
  failed: StageAction | null;
  /** The last thing said, for the echo and for retry. */
  lastSay: SayBody | null;
  /** When the current work began and when the daemon was last heard (ms); read by hooks, never by timers. */
  startedAt: number;
  heardAt: number;
  /** Her guesses the person inked since the last reply: the views draw them turning to ink. */
  inked: string[];
  /** Whether the reply in flight asked a question; a reply with none closes the open question. */
  replyAsked: boolean;
  /** The piece whose card is open, or null. Escape closes it. */
  card: string | null;
  /** Events of the draft's job heard so far: where a follow picks up (`GET /drafts/{id}/job?after=n`). */
  cursor: number;
  /** The kind of job that ended in `stopped` and is still shown so; null once anything moves on. */
  halted: DraftJobKind | null;
  /** The person pressed Stop on this job; kept once it ended, so the stage says "You stopped her." */
  stopping: boolean;
  /** What the person said while she worked, as typed here; null until they change it (the draft's then). */
  notes: DraftNotes | null;
  /** The "meanwhile" questions answered or skipped, and the ones the person has changed. */
  meanwhile: { done: MeanwhileQuestion[]; touched: MeanwhileQuestion[] };
}

/** The two questions asked while she works. */
export type MeanwhileQuestion = "expect" | "never";

export type StageAction =
  | { type: "describe"; need: string }
  | { type: "say"; text: string }
  | { type: "pick"; choice: string }
  | { type: "retry" }
  | { type: "ink"; node_ids: string[] }
  | { type: "drop"; node_ids: string[] }
  | { type: "undo_drop" }
  | { type: "enough" }
  | { type: "preview" }
  | { type: "mark"; expected_id: string; mark: Mark; note?: string }
  | { type: "add_missing"; text: string }
  | { type: "add_never"; text: string }
  | { type: "send_key" }
  | { type: "rehearse" }
  | { type: "verdict"; verdict: DraftVerdict; note?: string }
  /** The access step (ADR 0014): sign in to one real site, look at it now, or skip it. */
  | { type: "access"; origin: string; act: AccessAct }
  | { type: "switch_view"; view: StageView }
  | { type: "unmark"; expected_id: string }
  | { type: "remove_missing"; index: number }
  | { type: "remove_never"; index: number }
  | { type: "open_card"; node_id: string }
  | { type: "close_card" }
  /** Reads the draft again from the daemon (after a failed open, or to recover). */
  | { type: "reload"; draft_id: string }
  /** Ends the running job's model process (`POST /drafts/{id}/job/stop`). */
  | { type: "stop" }
  /** Lets go of the job's stream only; the job runs on and the draft is read again on return. */
  | { type: "leave" }
  /** The whole notes, sent each time they change (`PUT /drafts/{id}/notes`). */
  | { type: "notes"; notes: DraftNotes; question: MeanwhileQuestion }
  /** A "meanwhile" question answered (its lines are kept) or skipped. */
  | { type: "meanwhile_done"; question: MeanwhileQuestion; skip?: boolean };

/** Everything a stream can hand the store, plus a fresh read of the draft (after any `error`). */
export type StageEvent =
  | TurnEvent
  | AuthorEvent
  | RehearsalEvent
  | { type: "draft"; draft: Draft }
  /** The preview's answer, as the old JSON route gave it (the harness's beats still use it). */
  | { type: "expected"; expected: ExpectedCard[] }
  /** A job stream's own lines: its snapshot, `stopped`, and the preview's events. */
  | JobEvent;

/** What every view receives. A view draws from these and calls `dispatch`; it holds no copy of the model. */
export interface StageViewProps {
  draft: Draft;
  frame: StageFrame;
  state: StageState;
  dispatch: (action: StageAction) => void;
  words: StageWords;
  /** Keeps a piece's place in this view by node id. Only views write places; the store never moves one. */
  place: (view: StageView, nodeId: string, place: Place) => void;
}
