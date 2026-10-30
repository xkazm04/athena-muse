// The wire contract between the desktop and the daemon. Mirrors src/athena/contracts.py key for key
// (tests/test_contract_parity.py holds the two equal). JSON keys are snake_case. Absent values: the
// key is omitted (never null); core is the empty string ""; `cost_usd` omitted means unpriced.
// The person's word is Project; the wire's is space (`spc_` ids).

export const VERSION = "0.1.0";

export const SPACE_PREFIX = "spc_";
export const CORE = "";
export const CORE_ITEM = "core";

export const NAME_MAX = 60;
export const BRIEF_MAX = 1600;
export const APPS_MAX = 24;
export const SPACES_MAX = 100;
export const HUE_MAX = 359;
export const TEXT_MAX = 8000;

export type ErrorWord = "bad_request" | "unknown_ref" | "space_busy" | "unauthorized" | "engine_unavailable";
export type EngineId = "muse" | "muse_code" | "claude_code" | "scripted";
export type KeySource = "env" | "file" | "absent";
export type MemoryKind = "episode" | "fact";
export type Role = "person" | "athena";
export type ActionClass = "auto" | "gated";
export type CardState = "waiting" | "approved" | "declined";
export type Verdict = "approve" | "decline";
export type Surface = "turn" | "probe" | "design" | "rehearsal" | "twin";
export type ActionName =
  | "recall"
  | "remember"
  | "propose_brief"
  | "add_app"
  | "forget"
  | "portal_read"
  | "portal_act"
  | "sketch"
  | "ask"
  | "twin_send"
  | "twin_note";
export type AppEventType = "card_filed" | "card_resolved" | "space_changed" | "active_space" | "engine" | "turn_done";

export const CATALOG: Record<ActionName, ActionClass> = {
  recall: "auto",
  remember: "auto",
  propose_brief: "gated",
  add_app: "gated",
  forget: "gated",
  portal_read: "auto",
  portal_act: "gated",
  sketch: "auto",
  ask: "auto",
  // Twins (ADR 0009): one Gmail message, one Notion append or create; a draft not let go alone waits here.
  twin_send: "gated",
  twin_note: "gated",
};

// --- chores (ADR 0005) ---------------------------------------------------------------------------

export type SenseName = "paper" | "call" | "walk" | "circle";
export type FeaturedStatus = "proven" | "rehearsed" | "failing" | "unproven";
export type BenchWord = "exceeds" | "meets" | "short";
export type ProofOp = ">=" | "<=";
/** The app's playbooks/ or the person's own library under the data folder. */
export type ChoreOrigin = "library" | "yours";

// --- drafts: a chore written in conversation (ADR 0007) ------------------------------------------

export type DraftStep = "describe" | "shape" | "author" | "preview" | "rehearse" | "verdict" | "saved";
export type Slot = "need" | "apps" | "inputs" | "steps" | "hand" | "output" | "never";
export type SketchKind = "source" | "app" | "step" | "gate" | "output" | "never";
export type NodeOrigin = "you" | "athena";
export type SketchOpName = "add" | "change" | "remove" | "link";
export type Mark = "yes" | "no";
export type DraftVerdict = "keep" | "revise";
/** The two views of the stage, switched by a tab. */
export type StageView = "drawing" | "orbit";

export const FOLLOW_UPS_MAX = 2;
export const REPAIRS_MAX = 2;
export const SKETCH_NODES_MAX = 60;
export const LABEL_MAX = 80;
export const DETAIL_MAX = 240;
export const ASK_TEXT_MAX = 240;
export const SUGGESTIONS_MIN = 2;
export const SUGGESTIONS_MAX = 4;
export const NEED_MAX = 2000;

// --- twins: a clone that speaks for you (ADR 0008-0010) -------------------------------------------
// A name the wire already uses (`Mark`, `Decision` on a card) is prefixed for twins.

export type Place = "who" | "channels" | "voice" | "knowledge" | "chores" | "never" | "autonomy" | "memory" | "mission";
export type ChannelKind = "gmail" | "notion";
export type Autonomy = "review" | "assist" | "auto";
export type TwinState = "setting_up" | "live" | "paused";
export type ChannelStatus = "connected" | "needs_sign_in" | "disconnected";
/** Omitted on a channel that has never spoken. */
export type ChannelHealth = "active" | "quiet" | "stale";
export type MissionState = "open" | "resolved" | "handed_back";
export type SendDecision = "sent_alone" | "waits";
export type WaitReason = "review" | "assist" | "first_message" | "below_bar" | "risk" | "paused";
export type TwinMark = "me" | "edited" | "not_me";
export type ChoreKind = "outcome" | "inbox" | "test" | "channel";
export type DialSource = "learned" | "preset" | "you";
export type TwinTurnSide = "twin" | "other";
export type TwinMessageKind = "first_message" | "reply";
/** Given on the twins page, or taken from its task inbox. */
export type MissionSource = "page" | "notion";
export type PieceOpName = "add" | "change" | "remove" | "dial";
export type SetupPanel = "connect" | "samples" | "style" | "pages" | "chores" | "autonomy" | "memory" | "rehearsal";
export type FactSuggest = "keep" | "drop";
export type ConnectState = "idle" | "waiting" | "exchanging" | "done" | "failed";

export const TWINS_MAX = 20;
/** Sent mail the voice is learned from. */
export const SAMPLES_MAX = 12;
/** How sure a draft must be, in whole percent, to send alone on Auto. */
export const BAR_MIN = 50;
export const BAR_MAX = 99;
export const BAR_DEFAULT = 80;
/** Lines on one draft's risk list. */
export const RISKS_MAX = 5;
/** Gmail threads with an open mission are read this often while the daemon runs. */
export const POLL_SECONDS_DEFAULT = 300;
/** Recent Gmail conversations the new entry slip offers. */
export const THREADS_MAX = 20;
/** Characters of a conversation's last message the slip shows. */
export const SNIPPET_MAX = 200;
/** Goals Athena suggests for a new mission. */
export const GOALS_MAX = 3;
/** A style dial's value. */
export const DIAL_MIN = 1;
export const DIAL_MAX = 5;

/** 0, 0.5 or 1; "skipped" = left open with a stated default. Computed from the sketch, never claimed. */
export type CoverageValue = 0 | 0.5 | 1 | "skipped";

export interface SketchNode {
  id: string;
  kind: SketchKind;
  slot: Slot;
  label: string;
  /** "you": the person's own words, confirmed when added; "athena": a proposal. */
  origin: NodeOrigin;
  confirmed: boolean;
  detail?: string;
  /** On the person's nodes: their own words it was drawn from, verbatim. */
  quote?: string;
}

export interface SketchEdge {
  from: string;
  to: string;
}

export interface Sketch {
  nodes: SketchNode[];
  edges: SketchEdge[];
}

/** One change as applied: add/change carry the whole node after it; remove the node or edge; link the edge. */
export interface SketchOp {
  op: SketchOpName;
  node?: SketchNode;
  edge?: SketchEdge;
}

export interface Ask {
  slot: Slot;
  text: string;
  suggestions: string[];
  /** 0 for the first question on a slot, up to FOLLOW_UPS_MAX. */
  follow_up: number;
}

export type Coverage = Record<Slot, CoverageValue>;

/** One invented app of a written chore, as the person sees it on the stage. */
export interface PracticeApp {
  app_id: string;
  name: string;
  /** What she can look at there, in plain words. */
  reads: string[];
  /** What she can do there (each waits for a signature). */
  acts: string[];
  /** Invented rows across the tables she reads there. */
  rows: number;
}

/** A card Athena expects to file on her practice apps; the person's marks turn it into the key. */
export interface ExpectedCard {
  id: string;
  app: string;
  tool: string;
  key: string;
  label: string;
  why: string;
}

export interface ExpectedList {
  expected: ExpectedCard[];
}

export interface KeyMark {
  expected_id: string;
  /** yes = eligible, no = a trap. */
  mark: Mark;
  note?: string;
}

/** A card the person says she missed; `expected` is set when Athena could place it, else unscored. */
export interface MissingCard {
  text: string;
  expected?: ExpectedCard;
}

/** A "she must never..." line; `tool` is the act tool it forbids when Athena could name one. */
export interface NeverLine {
  text: string;
  tool?: string;
}

export interface DraftKey {
  marks: KeyMark[];
  missing: MissingCard[];
  never: NeverLine[];
}

export interface Draft {
  id: string;
  space_id: string;
  step: DraftStep;
  need: string;
  sketch: Sketch;
  coverage: Coverage;
  agreed: boolean;
  created: string;
  updated: string;
  chore_id?: string;
  /** Once written: her practice apps. */
  practice?: PracticeApp[];
  /** While shaping: the question still open, so a reopened stage shows it. */
  ask?: Ask;
  expected?: ExpectedCard[];
  key?: DraftKey;
  bench?: BenchSummary;
  verdict?: DraftVerdict;
  note?: string;
  /** Stage turns that counted, per view the person answered in. */
  views?: Partial<Record<StageView, number>>;
}

/** DELETE /drafts/{id}: the draft is gone, its Project stays. */
export interface DraftAbandoned {
  id: string;
}

export interface NewDraftBody {
  need: string;
}

export interface SayBody {
  /** "" when the person picked a suggestion. */
  text: string;
  choice?: string;
  /** The view the person answered in; counted on the draft. */
  view?: StageView;
}

export interface ConfirmBody {
  node_ids: string[];
}

/** Athena's unconfirmed guesses the person rubs out, with their links. */
export interface DropBody {
  node_ids: string[];
}

export interface KeyBody {
  marks: KeyMark[];
  missing: string[];
  never: string[];
}

export interface VerdictBody {
  verdict: DraftVerdict;
  note?: string;
}

export type AuthorEvent =
  | { type: "writing" }
  | { type: "repair"; problems: string[] }
  | { type: "written"; chore_id: string; practice: PracticeApp[] }
  | { type: "author_failed"; problems: string[] }
  | { type: "error"; error: ErrorWord; reason: string };

export type RehearsalEvent =
  | { type: "phase"; /** from 1 */ index: number; app: string; message: string }
  | { type: "card"; card: Card }
  | { type: "scored"; bench: BenchSummary }
  | { type: "error"; error: ErrorWord; reason: string };

export interface ChoreApp {
  app_id: string;
  name: string;
}

/** The latest bench run of a chore (`playbooks/<id>/bench.json`). */
export interface BenchSummary {
  verdict: BenchWord;
  reasons: string[];
  found: number;
  eligible: number;
  value_found_usd: number;
  value_total_usd: number;
  false_claims: number;
  duplicates: number;
  traps_filed: number;
  turns: number;
  minutes: number;
  engine: EngineId;
  model: string;
  run_at: string;
  /** Omitted = unpriced (a plan-billed CLI engine). */
  cost_usd?: number;
}

/** One row of `senses/proofs.json`: a spike proof measured on one build. */
export interface ProofRow {
  sense: SenseName;
  id: string;
  question: string;
  bar: number;
  op: ProofOp;
  passed: boolean;
  n: number;
  measured?: number;
  note?: string;
}

export interface ChoreSummary {
  id: string;
  title: string;
  short_title: string;
  promise: string;
  category: string;
  job: string;
  /** Empty for a chore that is not featured. */
  senses: SenseName[];
  /** Computed from proofs.json, never authored. */
  featured: FeaturedStatus;
  origin: ChoreOrigin;
  bench?: BenchSummary;
}

export interface ChoreList {
  chores: ChoreSummary[];
}

export interface ChoreDetail {
  chore: ChoreSummary;
  brief: string;
  persona: string;
  apps: ChoreApp[];
  proofs: ProofRow[];
  /** The sense roles the proofs ran on: segmenter / transcriber / reader. */
  backends: Record<string, string>;
}

export interface ErrorBody {
  error: ErrorWord;
  reason: string;
}

export interface Health {
  ok: boolean;
  version: string;
}

export interface EngineStatus {
  engine: EngineId;
  model: string;
  key: KeySource;
  simulated: boolean;
}

export interface Probe {
  ok: boolean;
  model?: string;
  latency_ms?: number;
  error?: string;
}

export interface SpaceCounts {
  episodes: number;
  facts: number;
}

export interface SpaceSummary {
  id: string;
  name: string;
  brief: string;
  apps: string[];
  hue: number;
  created: string;
  updated: string;
  counts: SpaceCounts;
}

// List routes answer wrapped, never as a bare array.
export interface SpaceList {
  spaces: SpaceSummary[];
}

export interface SpaceErased {
  id: string;
  episodes: number;
  facts: number;
  turns: number;
}

export interface MemoryRow {
  id: string;
  kind: MemoryKind;
  line: string;
  created: string;
  space_id: string;
}

export interface MemoryPage {
  rows: MemoryRow[];
  showing: number;
  total: number;
}

export interface ActiveSpace {
  space_id: string;
}

export interface Card {
  id: string;
  space_id: string;
  action: ActionName;
  label: string;
  args: Record<string, unknown>;
  state: CardState;
  created: string;
  resolved?: string;
}

export interface Turn {
  id: string;
  space_id: string;
  role: Role;
  text: string;
  created: string;
  cost_usd?: number;
  card_id?: string;
}

export interface TurnList {
  turns: Turn[];
}

export interface CardList {
  cards: Card[];
}

export interface LedgerRow {
  id: number;
  ts: string;
  surface: Surface;
  space_id: string;
  engine: EngineId;
  model: string;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
  cost_estimated: boolean;
  latency_ms: number;
  ok: boolean;
  error?: string;
}

export interface LedgerTotals {
  calls: number;
  cost_usd: number;
  cost_estimated: boolean;
}

export interface LedgerPage {
  rows: LedgerRow[];
  totals: LedgerTotals;
}

export type TurnEvent =
  | { type: "start"; turn_id: string; engine: EngineId; simulated: boolean }
  | { type: "text"; delta: string }
  | { type: "tool"; name: ActionName; label: string; class: ActionClass }
  | { type: "card"; card: Card }
  | { type: "done"; turn_id: string; waiting: boolean; cost_usd?: number }
  | { type: "error"; error: ErrorWord; reason: string }
  // stage turns only (ADR 0007)
  | { type: "sketch"; ops: SketchOp[] }
  | { type: "ask"; ask: Ask }
  | { type: "coverage"; coverage: Coverage; agreed: boolean };

export interface AppEvent {
  type: AppEventType;
  card?: Card;
  space_id?: string;
  erased?: boolean;
  status?: EngineStatus;
  turn_id?: string;
}

// --- twins (ADR 0008-0010) ------------------------------------------------------------------------
// Field names follow docs/concepts/twin-module/prototypes/shared/SCHEMA.md. The daemon computes every
// derived number; an unmeasured figure is an omitted key and reads "-", never 0. Percents are 0-100.

/** One part of a twin, on its place in the document. Origin is computed as a sketch node's is. */
export interface Piece {
  id: string;
  place: Place;
  label: string;
  /** "you": the person's words, confirmed when added; "athena": her proposal. */
  origin: NodeOrigin;
  confirmed: boolean;
  detail?: string;
  /** On the person's pieces: their own words it was drawn from, verbatim. */
  quote?: string;
  /** The sample ids it was learned from. */
  evidence?: string[];
}

export type PlaceCoverage = Record<Place, CoverageValue>;

export interface StyleDial {
  id: string;
  label: string;
  /** The word at DIAL_MIN. */
  low: string;
  /** The word at DIAL_MAX. */
  high: string;
  value: number;
  source: DialSource;
}

/** A sent mail of the person's that the voice may be learned from. */
export interface Sample {
  id: string;
  to: string;
  subject: string;
  /** ISO 8601 date. */
  date: string;
  words: number;
  excerpt: string;
  /** Athena suggests learning from it. */
  suggest: boolean;
  /** The person's choice. */
  picked: boolean;
  why_not?: string;
}

export interface NotionPage {
  id: string;
  title: string;
  /** Notion's word: "page" or "database". */
  kind: string;
  suggest: boolean;
  picked: boolean;
  why_not?: string;
}

/** A ready-made chore the twin may run (ADR 0005); the catalogue grows with the tools. */
export interface ChorePreset {
  id: string;
  /** The tool it runs on: "notion" today, others listed as `coming`. */
  tool: string;
  name: string;
  does: string;
  kind: ChoreKind;
  suggest: boolean;
  picked: boolean;
  /** Can be picked once the twin is live. */
  later?: boolean;
  /** A tool this app cannot reach yet: shown, never picked. */
  coming?: boolean;
  /** The task inbox: the Notion page it reads, one the twin may read. */
  page?: string;
}

export interface MemoryFact {
  id: string;
  fact: string;
  /** Where she noticed it, in plain words. */
  from: string;
  suggest: FactSuggest;
  /** Why she suggests it. */
  reason?: string;
  /** The person's call; omitted until they make it. */
  keep?: boolean;
}

/** A channel with two levels: one for first messages, one for replies. */
export interface AutonomySplit {
  first_message: Autonomy;
  reply: Autonomy;
}

export interface TwinChannel {
  kind: ChannelKind;
  account: string;
  status: ChannelStatus;
  autonomy: Autonomy;
  /** BAR_MIN..BAR_MAX; kept on every level, it only matters where a level is Auto. */
  bar: number;
  /** When set, it decides the level per kind of message. */
  split?: AutonomySplit;
  /** What it may touch there, in plain words ("practice page only"). */
  scope?: string;
  /** Computed from last_at. */
  health?: ChannelHealth;
  last_at?: string;
}

export interface MissionBeat {
  label: string;
  done: boolean;
}

/** One message of a mission or the dress rehearsal. The twin's turns carry its draft facts. */
export interface MissionTurn {
  id: string;
  side: TwinTurnSide;
  /** What was sent, or the draft as it waits. */
  text: string;
  at: string;
  kind?: TwinMessageKind;
  /** How sure it was, whole percent. */
  confidence?: number;
  /** Its risk list, plain words, at most RISKS_MAX. */
  risks?: string[];
  decision?: SendDecision;
  /** When it waits. */
  reason?: WaitReason;
  /** The bar it was held against, when its level was Auto. */
  bar?: number;
  /** How long it took to write. */
  elapsed_s?: number;
  /** The waiting draft's id. */
  draft?: string;
  /** The person's mark (rehearsal). */
  mark?: TwinMark;
  /** With mark "edited": the person's words. */
  edited_text?: string;
  /** What an edit taught it, in plain words. */
  learned?: string;
}

/** What a preset chore wrote when a mission ended. */
export interface TwinFiled {
  /** The ChorePreset id. */
  chore: string;
  /** Plain words: "Notion: Partnerships". */
  where: string;
  row: Record<string, string>;
}

export interface Mission {
  id: string;
  twin_id: string;
  title: string;
  /** Who the conversation is with. */
  with: string;
  channel: ChannelKind;
  goal: string;
  state: MissionState;
  beats: MissionBeat[];
  turns: MissionTurn[];
  created: string;
  last_at?: string;
  /** The latest, in plain words. */
  note?: string;
  /** The Gmail thread it lives on. */
  thread?: string;
  /** The dress rehearsal on a Notion practice page. */
  practice?: boolean;
  filed?: TwinFiled;
  /** Where the person gave it (a real mission only). */
  source?: MissionSource;
}

/** A message the twin wrote. A waiting one is a signature card the person may edit. */
export interface TwinDraft {
  id: string;
  twin_id: string;
  channel: ChannelKind;
  to: string;
  subject: string;
  text: string;
  confidence: number;
  risks: string[];
  decision: SendDecision;
  created: string;
  mission?: string;
  /** When it waits. */
  reason?: WaitReason;
  /** The bar it was held against, when its level was Auto. */
  bar?: number;
  /** When it waits. */
  card_id?: string;
  /** The message it replies to; omitted on a first message. */
  answers?: string;
}

/** The last seven days; each figure is omitted until measured. */
export interface TwinWeek {
  sent?: number;
  sent_alone?: number;
  held_by_risk?: number;
  median_reply_min?: number;
  /** An estimate; the screen says "est.". */
  cost_usd?: number;
}

/** One twin: a document in the wallet and a row of the ledger. */
/** The task inbox at work (the `task-inbox` preset): the Notion page it reads for new missions, one
 * line each ("<who or thread>: <goal>"), and what it made of the page when it last read it. */
export interface TaskInbox {
  /** The Notion page id. */
  page: string;
  title: string;
  /** Lines it started a mission for, ever. */
  taken: number;
  /** Lines it could not place at its last read, each with why; it left them alone. */
  unplaced: string[];
  /** Its last read of the page. */
  checked_at?: string;
  /** The page could not be read, plain words. */
  problem?: string;
}
export interface TwinSummary {
  id: string;
  space_id: string;
  name: string;
  purpose: string;
  state: TwinState;
  channels: TwinChannel[];
  week: TwinWeek;
  /** Whole percent: the mean coverage over the places setup requires. */
  readiness: number;
  /** Open or handed back. */
  open_missions: number;
  /** Drafts waiting for a signature. */
  waiting_count: number;
  missions: Mission[];
  /** Drafts waiting for a signature, oldest first. */
  waiting: TwinDraft[];
  created: string;
  updated: string;
  /** When it first went live. */
  since?: string;
  paused_because?: string;
  /** When the task inbox is picked and reads a page. */
  inbox?: TaskInbox;
}

export interface TwinAsk {
  place: Place;
  text: string;
  suggestions: string[];
  follow_up: number;
  /** The working slip this question needs. */
  panel?: SetupPanel;
  /** With panel "connect". */
  channel?: ChannelKind;
}

/**
 * How it sounds now (the Mirror's live preview, nested on the voice section): one message from the
 * other side and the twin's reply in its current voice. The daemon writes it with one engine call and
 * keeps it until the compiled voice changes.
 */
export interface TwinPreview {
  /** A short message from the other side: the latest one it answered, or an invented one. */
  inbound: string;
  /** Its reply in its voice now. */
  text: string;
  /** What changed in its voice since the last preview, plain words; [] the first time. */
  changed: string[];
}

export interface TwinDetail extends TwinSummary {
  pieces: Piece[];
  coverage: PlaceCoverage;
  /** Computed: the dress rehearsal may start. */
  ready: boolean;
  dials: StyleDial[];
  style_presets: string[];
  samples: Sample[];
  pages: NotionPage[];
  chores: ChorePreset[];
  memory: MemoryFact[];
  /** While setting up: the question still open. */
  ask?: TwinAsk;
  /** The latest dress rehearsal. */
  rehearsal?: Mission;
  /** How it sounds, when one is kept for its voice as it is now. */
  preview?: TwinPreview;
}

/** The stat strip. The counts are always known; a weekly sum is omitted until a twin measured it. */
export interface TwinStats {
  live: number;
  waiting_for_you: number;
  missions_open: number;
  sent_week?: number;
  sent_alone_week?: number;
  held_by_risk_week?: number;
  /** est. */
  cost_usd_week?: number;
}

export interface TwinPage {
  twins: TwinSummary[];
  stats: TwinStats;
}
/** A recent Gmail conversation the new entry slip offers. */
export interface ThreadSummary {
  /** The Gmail thread id: what a new mission's `thread` names. */
  id: string;
  /** The other side: a name, else an address. */
  with: string;
  subject: string;
  /** An excerpt of its last message (<= SNIPPET_MAX): their words, untrusted. */
  snippet: string;
  /** Its last message, ISO 8601 UTC. */
  last_at: string;
  /** The other side spoke last: answering it is a reply. */
  theirs_last: boolean;
}
/** GET /twins/{id}/threads: recent Gmail conversations, newest first, at most THREADS_MAX. */
export interface ThreadList {
  threads: ThreadSummary[];
}
/** POST /twins/{id}/goals: Athena's suggested goals for a new mission (her pencil), at most GOALS_MAX,
 * each <= LABEL_MAX; [] when she has none. The person's own goal always works. */
export interface GoalList {
  goals: string[];
}

/** A connected account (ADR 0008). The credential itself never crosses the wire. */
export interface Connection {
  kind: ChannelKind;
  status: ChannelStatus;
  /** Whether it may send or write; off until a twin needs it. */
  writes: boolean;
  account?: string;
  last_checked?: string;
  /** Plain words. */
  problem?: string;
  /** Until connected: how to connect, in plain words (Gmail: your own Google client). */
  guide?: string;
}

export interface ConnectionList {
  connections: Connection[];
}

/** A connect in progress: Google's sign-in in the browser, or a Notion key being checked. */
export interface ConnectFlow {
  state: ConnectState;
  /** Plain words. */
  detail?: string;
  /** While waiting: Google's sign-in page, for when the browser did not open. */
  url?: string;
}

export interface NewTwinBody {
  space_id: string;
}

export interface TwinSayBody {
  /** "" when the person picked a suggestion; the first say carries the need. */
  text: string;
  choice?: string;
}

/** Piece ids: inked on confirm, rubbed out (her unconfirmed ones only) on drop. */
export interface PiecesBody {
  pieces: string[];
}

export interface SamplesBody {
  ids: string[];
}

export interface DialsBody {
  /** Dial id -> DIAL_MIN..DIAL_MAX; the person's values (source "you"). */
  dials: Record<string, number>;
  /** A style preset applied first. */
  preset?: string;
}

export interface PagesBody {
  ids: string[];
}

export interface ChoresBody {
  ids: string[];
  /** With `task-inbox`: the picked Notion page it reads. */
  inbox?: string;
}

export interface AutonomyBody {
  channel: ChannelKind;
  autonomy: Autonomy;
  bar: number;
  split?: AutonomySplit;
}

export interface MemoryBody {
  id: string;
  keep: boolean;
  reason?: string;
}

export interface RehearseBody {
  goal: string;
}

export interface MarkBody {
  turn: string;
  mark: TwinMark;
  edited_text?: string;
}

export interface NewMissionBody {
  /** A Gmail thread id, or the one address of someone new. */
  thread: string;
  goal: string;
}
/** One of the two: the conversation chosen, or the one address of someone new. */
export interface GoalsBody {
  thread?: string;
  to?: string;
}

/** Gmail: the person's own Google client. Notion: the key. */
export interface ConnectBody {
  client_id?: string;
  client_secret?: string;
  key?: string;
}

export interface DecisionEdit {
  text: string;
}

/** POST /decisions/{card_id}. `edited` is taken on a twin draft's card only. */
export interface DecisionBody {
  verdict: Verdict;
  edited?: DecisionEdit;
}

/** One change as applied: add/change carry the whole piece after it, remove the piece, dial the whole dial. */
export interface PieceOp {
  op: PieceOpName;
  piece?: Piece;
  dial?: StyleDial;
}

/** POST /twins/{id}/say: a turn stream, with the twin's own sketch, ask and coverage lines. */
export type TwinSetupEvent =
  | { type: "start"; turn_id: string; engine: EngineId; simulated: boolean }
  | { type: "text"; delta: string }
  | { type: "tool"; name: ActionName; label: string; class: ActionClass }
  | { type: "card"; card: Card }
  | { type: "done"; turn_id: string; waiting: boolean; cost_usd?: number }
  | { type: "error"; error: ErrorWord; reason: string }
  | { type: "sketch"; ops: PieceOp[] }
  | { type: "ask"; ask: TwinAsk }
  | { type: "coverage"; coverage: PlaceCoverage; ready: boolean; readiness: number };

/** POST /twins/{id}/rehearse: each turn as it is played, then the outcome. */
export type TwinRehearsalEvent =
  | { type: "turn"; turn: MissionTurn }
  | { type: "outcome"; state: MissionState; filed?: TwinFiled }
  | { type: "error"; error: ErrorWord; reason: string };

export const ROUTES = {
  health: "/health",
  engine: "/engine",
  engine_key: "/engine/key",
  engine_probe: "/engine/probe",
  spaces: "/spaces",
  space: "/spaces/{id}",
  space_memory: "/spaces/{id}/memory",
  memory_core: "/spaces/{id}/memory/{mem_id}/core",
  active_space: "/settings/active-space",
  conversation: "/conversation",
  run: "/run",
  cards: "/cards",
  decision: "/decisions/{card_id}",
  ledger: "/ledger",
  events: "/events",
  chores: "/chores",
  chore: "/chores/{id}",
  drafts: "/drafts",
  draft: "/drafts/{id}",
  draft_say: "/drafts/{id}/say",
  draft_confirm: "/drafts/{id}/confirm",
  draft_drop: "/drafts/{id}/drop",
  draft_write: "/drafts/{id}/write",
  draft_preview: "/drafts/{id}/preview",
  draft_key: "/drafts/{id}/key",
  draft_rehearse: "/drafts/{id}/rehearse",
  draft_verdict: "/drafts/{id}/verdict",
  twins: "/twins",
  twin: "/twins/{id}",
  twin_say: "/twins/{id}/say",
  twin_confirm: "/twins/{id}/confirm",
  twin_drop: "/twins/{id}/drop",
  twin_samples: "/twins/{id}/samples",
  twin_dials: "/twins/{id}/dials",
  twin_pages: "/twins/{id}/pages",
  twin_chores: "/twins/{id}/chores",
  twin_autonomy: "/twins/{id}/autonomy",
  twin_memory: "/twins/{id}/memory",
  twin_rehearse: "/twins/{id}/rehearse",
  twin_mark: "/twins/{id}/rehearse/mark",
  twin_golive: "/twins/{id}/golive",
  twin_pause: "/twins/{id}/pause",
  twin_missions: "/twins/{id}/missions",
  twin_mission: "/twins/{id}/missions/{mid}",
  twin_preview: "/twins/{id}/preview",
  twin_threads: "/twins/{id}/threads",
  twin_goals: "/twins/{id}/goals",
  connectors: "/connectors",
  connector_connect: "/connectors/{kind}/connect",
  connector_flow: "/connectors/{kind}/flow",
  connector_disconnect: "/connectors/{kind}/disconnect",
  connector_probe: "/connectors/{kind}/probe",
} as const;
