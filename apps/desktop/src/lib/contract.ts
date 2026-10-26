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
export type EngineId = "muse" | "scripted";
export type KeySource = "env" | "file" | "absent";
export type MemoryKind = "episode" | "fact";
export type Role = "person" | "athena";
export type ActionClass = "auto" | "gated";
export type CardState = "waiting" | "approved" | "declined";
export type Verdict = "approve" | "decline";
export type Surface = "turn" | "probe";
export type ActionName = "recall" | "remember" | "propose_brief" | "add_app" | "forget";
export type AppEventType = "card_filed" | "card_resolved" | "space_changed" | "active_space" | "engine" | "turn_done";

export const CATALOG: Record<ActionName, ActionClass> = {
  recall: "auto",
  remember: "auto",
  propose_brief: "gated",
  add_app: "gated",
  forget: "gated",
};

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
  | { type: "error"; error: ErrorWord; reason: string };

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
} as const;
