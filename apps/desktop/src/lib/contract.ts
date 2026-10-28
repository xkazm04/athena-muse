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
export type Surface = "turn" | "probe" | "design" | "rehearsal";
export type ActionName =
  | "recall"
  | "remember"
  | "propose_brief"
  | "add_app"
  | "forget"
  | "portal_read"
  | "portal_act"
  | "sketch"
  | "ask";
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

export const FOLLOW_UPS_MAX = 2;
export const REPAIRS_MAX = 2;
export const SKETCH_NODES_MAX = 60;
export const LABEL_MAX = 80;
export const NEED_MAX = 2000;

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

export interface DraftKey {
  marks: KeyMark[];
  missing: MissingCard[];
  /** "She must never..." lines, which become forbidden. */
  never: string[];
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
  expected?: ExpectedCard[];
  key?: DraftKey;
  bench?: BenchSummary;
  verdict?: DraftVerdict;
  note?: string;
}

export interface NewDraftBody {
  need: string;
}

export interface SayBody {
  /** "" when the person picked a suggestion. */
  text: string;
  choice?: string;
}

export interface ConfirmBody {
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
  | { type: "written"; chore_id: string }
  | { type: "author_failed"; problems: string[] }
  | { type: "error"; error: ErrorWord; reason: string };

export type RehearsalEvent =
  | { type: "phase"; index: number; app: string; message: string }
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
  draft_write: "/drafts/{id}/write",
  draft_preview: "/drafts/{id}/preview",
  draft_key: "/drafts/{id}/key",
  draft_rehearse: "/drafts/{id}/rehearse",
  draft_verdict: "/drafts/{id}/verdict",
} as const;
