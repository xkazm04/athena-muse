// One typed function per daemon route. Paths come from ROUTES; nothing here knows about fetch.
// Request bodies and query names are not in the wire contract yet, so the shapes below are the ones
// the daemon routes are expected to accept (see the WP2 report); they live in one place to change.

import {
  CORE,
  CORE_ITEM,
  ROUTES,
  type ActiveSpace,
  type Card,
  type CardList,
  type EngineStatus,
  type Health,
  type LedgerPage,
  type MemoryKind,
  type MemoryPage,
  type MemoryRow,
  type Probe,
  type SpaceErased,
  type SpaceList,
  type SpaceSummary,
  type TurnList,
  type Verdict,
} from "./contract";
import { request } from "./daemon";

export interface SpaceDraft {
  name: string;
  brief?: string;
  apps?: string[];
  hue?: number;
}

export type SpacePatch = Partial<SpaceDraft>;

/** Fills `{name}` slots in a ROUTES template. A core space is addressed as "core", never "". */
function path(template: string, params: Record<string, string> = {}): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => encodeURIComponent(params[k] ?? ""));
}

const spaceRef = (id: string): string => (id === CORE ? CORE_ITEM : id);

function query(params: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, String(v));
  const text = q.toString();
  return text ? `?${text}` : "";
}

export const health = () => request<Health>("GET", ROUTES.health);
export const engine = () => request<EngineStatus>("GET", ROUTES.engine);
export const saveKey = (key: string) => request<EngineStatus>("POST", ROUTES.engine_key, { key });
export const deleteKey = () => request<EngineStatus>("DELETE", ROUTES.engine_key);
export const probe = () => request<Probe>("POST", ROUTES.engine_probe);

export const spaces = async () => (await request<SpaceList>("GET", ROUTES.spaces)).spaces;
export const createSpace = (draft: SpaceDraft) => request<SpaceSummary>("POST", ROUTES.spaces, draft);
export const space = (id: string) => request<SpaceSummary>("GET", path(ROUTES.space, { id }));
export const updateSpace = (id: string, patch: SpacePatch) =>
  request<SpaceSummary>("POST", path(ROUTES.space, { id }), patch);
export const eraseSpace = (id: string) => request<SpaceErased>("DELETE", path(ROUTES.space, { id }));

export const memory = (spaceIdOrCore: string, kind?: MemoryKind, limit?: number) =>
  request<MemoryPage>("GET", path(ROUTES.space_memory, { id: spaceRef(spaceIdOrCore) }) + query({ kind, limit }));
export const makeCore = (spaceId: string, memId: string) =>
  request<Pick<MemoryRow, "id" | "kind">>("POST", path(ROUTES.memory_core, { id: spaceRef(spaceId), mem_id: memId }));

export const activeSpace = () => request<ActiveSpace>("GET", ROUTES.active_space);
export const setActiveSpace = (spaceId: string) =>
  request<ActiveSpace>("POST", ROUTES.active_space, { space_id: spaceId });

// List routes answer wrapped (`{spaces}`, `{turns}`, `{cards}`); these unwrap them.
export const conversation = async (spaceId: string) =>
  (await request<TurnList>("GET", ROUTES.conversation + query({ space_id: spaceId }))).turns;
/** `resolved` = approved or declined; omitted = every card. */
export type CardFilter = "waiting" | "resolved";
export const cards = async (state?: CardFilter) =>
  (await request<CardList>("GET", ROUTES.cards + query({ state }))).cards;
export const decide = (cardId: string, verdict: Verdict) =>
  request<Card>("POST", path(ROUTES.decision, { card_id: cardId }), { verdict });
export const ledger = (limit?: number) => request<LedgerPage>("GET", ROUTES.ledger + query({ limit }));
