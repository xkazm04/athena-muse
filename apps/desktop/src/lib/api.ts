// One typed function per daemon route. Paths come from ROUTES; nothing here knows about fetch.
// Request bodies and query names are not in the wire contract yet, so the shapes below are the ones
// the daemon routes are expected to accept (see the WP2 report); they live in one place to change.

import {
  CORE,
  CORE_ITEM,
  ROUTES,
  type ActiveSpace,
  type AuthorEvent,
  type AutonomyBody,
  type Card,
  type CardList,
  type ChannelKind,
  type ChoreDetail,
  type ChoreList,
  type ChoresBody,
  type ConfirmBody,
  type ConnectBody,
  type ConnectFlow,
  type Connection,
  type ConnectionList,
  type DecisionEdit,
  type DialsBody,
  type Draft,
  type DraftAbandoned,
  type DropBody,
  type EngineStatus,
  type ExpectedList,
  type GoalList,
  type GoalsBody,
  type Health,
  type KeyBody,
  type LedgerPage,
  type MarkBody,
  type MemoryBody,
  type MemoryKind,
  type MemoryPage,
  type MemoryRow,
  type Mission,
  type NewDraftBody,
  type NewMissionBody,
  type NewTwinBody,
  type PagesBody,
  type PiecesBody,
  type Probe,
  type RehearsalEvent,
  type RehearseBody,
  type SamplesBody,
  type SayBody,
  type SpaceErased,
  type SpaceList,
  type SpaceSummary,
  type ThreadList,
  type TurnEvent,
  type TurnList,
  type TwinDetail,
  type TwinPage,
  type TwinPreview,
  type TwinRehearsalEvent,
  type TwinSayBody,
  type TwinSetupEvent,
  type Verdict,
  type VerdictBody,
} from "./contract";
import { request, streamNdjson } from "./daemon";

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
/** `edited` is the person's words for a twin's draft, sent only when they changed it (ADR 0009). */
export const decide = (cardId: string, verdict: Verdict, edited?: DecisionEdit) =>
  request<Card>("POST", path(ROUTES.decision, { card_id: cardId }), edited ? { verdict, edited } : { verdict });
export const ledger = (limit?: number) => request<LedgerPage>("GET", ROUTES.ledger + query({ limit }));

// Chores (ADR 0005): the library is read-only on the wire.
export const chores = async () => (await request<ChoreList>("GET", ROUTES.chores)).chores;
export const chore = (id: string) => request<ChoreDetail>("GET", path(ROUTES.chore, { id }));

// Drafts (ADR 0007): a chore written in conversation. `say`, `write` and `rehearse` stream NDJSON.
export const createDraft = (need: string) => request<Draft>("POST", ROUTES.drafts, { need } satisfies NewDraftBody);
export const getDraft = (id: string) => request<Draft>("GET", path(ROUTES.draft, { id }));
export const abandonDraft = (id: string) => request<DraftAbandoned>("DELETE", path(ROUTES.draft, { id }));
export const draftSay = (id: string, body: SayBody, onEvent: (e: TurnEvent) => void, signal?: AbortSignal) =>
  streamNdjson<TurnEvent>("POST", path(ROUTES.draft_say, { id }), body, onEvent, signal);
export const draftConfirm = (id: string, nodeIds: string[]) =>
  request<Draft>("POST", path(ROUTES.draft_confirm, { id }), { node_ids: nodeIds } satisfies ConfirmBody);
export const draftDrop = (id: string, nodeIds: string[]) =>
  request<Draft>("POST", path(ROUTES.draft_drop, { id }), { node_ids: nodeIds } satisfies DropBody);
export const draftWrite = (id: string, onEvent: (e: AuthorEvent) => void, signal?: AbortSignal) =>
  streamNdjson<AuthorEvent>("POST", path(ROUTES.draft_write, { id }), undefined, onEvent, signal);
export const draftPreview = (id: string) => request<ExpectedList>("POST", path(ROUTES.draft_preview, { id }));
export const draftKey = (id: string, body: KeyBody) => request<Draft>("PUT", path(ROUTES.draft_key, { id }), body);
export const draftRehearse = (id: string, onEvent: (e: RehearsalEvent) => void, signal?: AbortSignal) =>
  streamNdjson<RehearsalEvent>("POST", path(ROUTES.draft_rehearse, { id }), undefined, onEvent, signal);
export const draftVerdict = (id: string, body: VerdictBody) =>
  request<Draft>("POST", path(ROUTES.draft_verdict, { id }), body);

// Twins (ADR 0008-0010): every setup change answers the whole twin. `say` and `rehearse` stream NDJSON.
export const twins = () => request<TwinPage>("GET", ROUTES.twins);
export const createTwin = (spaceId: string) =>
  request<TwinDetail>("POST", ROUTES.twins, { space_id: spaceId } satisfies NewTwinBody);
export const twin = (id: string) => request<TwinDetail>("GET", path(ROUTES.twin, { id }));
export const twinSay = (id: string, body: TwinSayBody, onEvent: (e: TwinSetupEvent) => void, signal?: AbortSignal) =>
  streamNdjson<TwinSetupEvent>("POST", path(ROUTES.twin_say, { id }), body, onEvent, signal);
export const twinConfirm = (id: string, pieces: string[]) =>
  request<TwinDetail>("POST", path(ROUTES.twin_confirm, { id }), { pieces } satisfies PiecesBody);
export const twinDrop = (id: string, pieces: string[]) =>
  request<TwinDetail>("POST", path(ROUTES.twin_drop, { id }), { pieces } satisfies PiecesBody);
export const twinSamples = (id: string, ids: string[]) =>
  request<TwinDetail>("POST", path(ROUTES.twin_samples, { id }), { ids } satisfies SamplesBody);
export const twinDials = (id: string, body: DialsBody) =>
  request<TwinDetail>("POST", path(ROUTES.twin_dials, { id }), body);
export const twinPages = (id: string, ids: string[]) =>
  request<TwinDetail>("POST", path(ROUTES.twin_pages, { id }), { ids } satisfies PagesBody);
/** `inbox`: with the task inbox picked, the Notion page it reads. */
export const twinChores = (id: string, ids: string[], inbox?: string) =>
  request<TwinDetail>("POST", path(ROUTES.twin_chores, { id }), (inbox ? { ids, inbox } : { ids }) satisfies ChoresBody);
export const twinAutonomy = (id: string, body: AutonomyBody) =>
  request<TwinDetail>("POST", path(ROUTES.twin_autonomy, { id }), body);
export const twinMemory = (id: string, body: MemoryBody) =>
  request<TwinDetail>("POST", path(ROUTES.twin_memory, { id }), body);
export const twinRehearse = (id: string, goal: string, onEvent: (e: TwinRehearsalEvent) => void, signal?: AbortSignal) =>
  streamNdjson<TwinRehearsalEvent>(
    "POST",
    path(ROUTES.twin_rehearse, { id }),
    { goal } satisfies RehearseBody,
    onEvent,
    signal,
  );
export const twinMark = (id: string, body: MarkBody) =>
  request<TwinDetail>("POST", path(ROUTES.twin_mark, { id }), body);
export const twinGoLive = (id: string) => request<TwinDetail>("POST", path(ROUTES.twin_golive, { id }));
export const twinPause = (id: string) => request<TwinDetail>("POST", path(ROUTES.twin_pause, { id }));
export const startMission = (id: string, body: NewMissionBody) =>
  request<Mission>("POST", path(ROUTES.twin_missions, { id }), body);
export const mission = (id: string, mid: string) => request<Mission>("GET", path(ROUTES.twin_mission, { id, mid }));
/** The new entry slip: recent Gmail conversations, newest first, and Athena's suggested goals for one. */
export const twinThreads = async (id: string) =>
  (await request<ThreadList>("GET", path(ROUTES.twin_threads, { id }))).threads;
export const twinGoals = async (id: string, body: GoalsBody) =>
  (await request<GoalList>("POST", path(ROUTES.twin_goals, { id }), body)).goals;
/** How it sounds now: one engine call, kept by the daemon until its voice changes. */
export const twinPreview = (id: string) => request<TwinPreview>("GET", path(ROUTES.twin_preview, { id }));

// Connected accounts (ADR 0008): Google sign-in runs in the browser, so `connect` starts a flow to watch.
export const connections = async () => (await request<ConnectionList>("GET", ROUTES.connectors)).connections;
export const connect = (kind: ChannelKind, body: ConnectBody) =>
  request<ConnectFlow>("POST", path(ROUTES.connector_connect, { kind }), body);
export const connectFlow = (kind: ChannelKind) => request<ConnectFlow>("GET", path(ROUTES.connector_flow, { kind }));
export const disconnect = (kind: ChannelKind) =>
  request<Connection>("POST", path(ROUTES.connector_disconnect, { kind }));
export const probeConnection = (kind: ChannelKind) =>
  request<Connection>("POST", path(ROUTES.connector_probe, { kind }));
