// The twins page's shapes (Passport, ADR 0008-0010): one model for the overview, the setup with its
// dress rehearsal, and the nested pages. The store folds the daemon's streams into it; the views draw
// it and send TwinsActions back.

import type {
  Autonomy,
  ChannelKind,
  MissionState,
  MissionTurn,
  TwinAsk,
  TwinDetail,
  TwinFiled,
  TwinMark,
  TwinPage,
  TwinRehearsalEvent,
  TwinSetupEvent,
  TwinStats,
} from "../../lib/contract";
import type { ReplyPhase } from "../stage/types";

export type { ReplyPhase };

export type Load = "idle" | "reading" | "ready" | "problem";

/** A connection as the slip shows it: Google's sign-in waits in the browser, a Notion key is checked. */
export type ConnectView = "idle" | "waiting" | "checking" | "connected" | "failed" | "rejected";

/** What the person chose on the slips, before it is sent; each overrides her suggestion. */
export interface Choices {
  samples: Record<string, boolean>;
  pages: Record<string, boolean>;
  chores: Record<string, boolean>;
  memory: Record<string, boolean>;
  dials: Record<string, number>;
  preset: string | null;
  autonomy: { first: Autonomy; reply: Autonomy; split: boolean; bar: number; notion: Autonomy; touched: boolean };
}

export interface RehearsalState {
  goal: string;
  /** Every turn as streamed, in order. */
  turns: MissionTurn[];
  outcome: { state: MissionState; filed?: TwinFiled } | null;
  /** The draft the person is editing. */
  editing: string | null;
  /** Edited drafts the person sent on with "Send it". */
  continued: string[];
  /** The person's version while they edit. */
  editText: string;
  streaming: boolean;
}

export type SetupWork = "open" | "create" | "say" | "ink" | "panel" | "connect" | "rehearse" | "mark" | "golive";

export interface SetupState {
  twin: TwinDetail | null;
  /** Her line in this reply, as it streamed. */
  line: string;
  ask: TwinAsk | null;
  /** The person's last words or picked answer. */
  youSaid: string;
  phase: ReplyPhase;
  /** Plain words for a failed reply; "" when there is none. */
  problem: string;
  /** Pieces the last reply wrote, and pieces just inked: each animates once. */
  arrived: string[];
  inked: string[];
  replyAsked: boolean;
  /** A quiet note under the question (the example follows one path). */
  note: string;
  connect: Record<ChannelKind, ConnectView>;
  /** When the current connect began to wait (ms). */
  connectSince: number;
  /** The Notion steps are open. */
  where: boolean;
  choices: Choices;
  rehearsal: RehearsalState | null;
  /** Gone live: the seal is pressed. */
  sealed: boolean;
  work: SetupWork | null;
  startedAt: number;
  heardAt: number;
  /** The act to repeat on "Try again". */
  failed: TwinsAction | null;
}

/** What the person did on the overview that the next read has not caught up with. */
export type Done = "signed" | "declined" | "taken";

export interface TwinsState {
  /** "example" plays the invented example, labelled on screen; "live" talks to the daemon. */
  mode: "live" | "example";
  page: TwinPage | null;
  pageLoad: Load;
  pageProblem: string;
  /** The stats before the last go-live, for "was 1". */
  before: TwinStats | null;
  /** The twin that just went live, for its fresh stamp. */
  issued: string | null;
  details: Record<string, TwinDetail>;
  done: Record<string, Done>;
  flash: string;
  /** Signing in to Google again for a paused twin, from the overview. */
  signin: { twin: string; state: ConnectView; since: number } | null;
  setup: SetupState;
}

export type ChoiceGroup = "samples" | "pages" | "chores" | "memory";

export type TwinsAction =
  | { type: "describe"; need: string }
  | { type: "say"; text: string }
  | { type: "pick"; index: number }
  | { type: "ink"; pieces: string[] }
  | { type: "ink_all" }
  | { type: "choose"; group: ChoiceGroup; id: string; on: boolean }
  | { type: "dial"; id: string; value: number }
  | { type: "preset"; name: string }
  | { type: "level"; which: "first" | "reply" | "notion"; value: Autonomy }
  | { type: "bar"; delta: number }
  | { type: "split" }
  | { type: "panel_go" }
  | { type: "gmail"; client_id?: string; client_secret?: string }
  | { type: "gmail_cancel" }
  | { type: "notion"; key: string }
  | { type: "where" }
  | { type: "enough" }
  | { type: "rehearse" }
  | { type: "reh_mark"; mark: TwinMark }
  | { type: "reh_edit" }
  | { type: "reh_text"; text: string }
  | { type: "reh_save" }
  | { type: "reh_send" }
  | { type: "reh_alt" }
  | { type: "golive" }
  | { type: "retry" };

/** Everything the store folds: the setup stream, the rehearsal stream, or a fresh read of the twin. */
export type TwinsEvent = TwinSetupEvent | TwinRehearsalEvent | { type: "twin"; twin: TwinDetail };
