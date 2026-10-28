// The stage's shapes (onboarding v2, ADR 0007): one model, two views. The store folds the daemon's
// streams into StageState; a view draws it and sends StageActions back. Neither view owns state.

import type {
  Ask,
  AuthorEvent,
  Draft,
  DraftVerdict,
  Mark,
  RehearsalEvent,
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
}

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
  | { type: "switch_view"; view: StageView };

/** Everything a stream can hand the store, plus a fresh read of the draft (after any `error`). */
export type StageEvent = TurnEvent | AuthorEvent | RehearsalEvent | { type: "draft"; draft: Draft };

/** What every view receives. A view draws from these and calls `dispatch`; it holds no copy of the model. */
export interface StageViewProps {
  draft: Draft;
  frame: StageFrame;
  state: StageState;
  dispatch: (action: StageAction) => void;
  words: StageWords;
}
