// The main window's state: one small store over the daemon. Every action goes through `api`; the
// daemon stays the truth and the store only mirrors what it last answered.

import { create } from "zustand";
import * as api from "../lib/api";
import { CORE, type AppEvent, type Card, type EngineStatus, type LedgerPage, type SpaceCounts, type SpaceSummary } from "../lib/contract";
import { DaemonError } from "../lib/daemon";
import { parseHash, routeSpace, toHash, type Route } from "./route";

export type Load = "idle" | "reading" | "ready" | "problem";

/** Plain words for anything thrown at us; a daemon refusal is shown verbatim. */
export function reasonOf(e: unknown, fallback = "Something went wrong"): string {
  return e instanceof DaemonError ? e.reason : fallback;
}

/** How many resolved cards the Athena view keeps. */
export const DECIDED_SHOWN = 12;

interface Data {
  engine: EngineStatus | null;
  spaces: SpaceSummary[];
  spacesLoad: Load;
  spacesProblem: string;
  active: string;
  waiting: Card[];
  resolved: Card[];
  ledger: LedgerPage | null;
  ledgerProblem: string;
  coreCounts: SpaceCounts | null;
  route: Route;
  /** A short-lived problem from an action outside a form (switching project). */
  notice: string;
}

interface Actions {
  setEngine: (e: EngineStatus) => void;
  loadEngine: () => Promise<void>;
  loadSpaces: () => Promise<void>;
  loadActive: () => Promise<void>;
  loadCards: () => Promise<void>;
  loadLedger: () => Promise<void>;
  loadCoreCounts: () => Promise<void>;
  loadAll: () => Promise<void>;
  setActive: (spaceId: string) => Promise<void>;
  createSpace: (name: string) => Promise<SpaceSummary>;
  updateSpace: (id: string, patch: api.SpacePatch) => Promise<SpaceSummary>;
  eraseSpace: (id: string) => Promise<void>;
  navigate: (route: Route) => void;
  /** Called on hashchange; keeps the store in step with the address bar. */
  syncRoute: (hash: string) => void;
  handleEvent: (e: AppEvent) => void;
  clearNotice: () => void;
}

export type MainState = Data & Actions;

const initial = (): Data => ({
  engine: null,
  spaces: [],
  spacesLoad: "idle",
  spacesProblem: "",
  active: CORE,
  waiting: [],
  resolved: [],
  ledger: null,
  ledgerProblem: "",
  coreCounts: null,
  route: parseHash(typeof window === "undefined" ? "" : window.location.hash),
  notice: "",
});

const putSpace = (list: SpaceSummary[], s: SpaceSummary) =>
  list.some((x) => x.id === s.id) ? list.map((x) => (x.id === s.id ? s : x)) : [...list, s];

const newestResolved = (a: Card, b: Card) => (b.resolved ?? b.created).localeCompare(a.resolved ?? a.created);

export const useMain = create<MainState>()((set, get) => ({
  ...initial(),

  setEngine: (engine) => set({ engine }),

  loadEngine: async () => {
    set({ engine: await api.engine() });
  },

  loadSpaces: async () => {
    // Only the first read shows "reading"; a refresh keeps the field on screen.
    if (get().spacesLoad !== "ready") set({ spacesLoad: "reading", spacesProblem: "" });
    try {
      set({ spaces: await api.spaces(), spacesLoad: "ready", spacesProblem: "" });
    } catch (e) {
      set({ spacesLoad: "problem", spacesProblem: reasonOf(e, "Could not read your projects") });
    }
  },

  loadActive: async () => {
    try {
      set({ active: (await api.activeSpace()).space_id });
    } catch {
      // the pill keeps what it had; the next active_space event corrects it
    }
  },

  loadCards: async () => {
    try {
      const [waiting, resolved] = await Promise.all([api.cards("waiting"), api.cards("resolved")]);
      set({ waiting, resolved: [...resolved].sort(newestResolved).slice(0, DECIDED_SHOWN) });
    } catch {
      // cards are shown again on the next event
    }
  },

  loadLedger: async () => {
    try {
      set({ ledger: await api.ledger(), ledgerProblem: "" });
    } catch (e) {
      set({ ledgerProblem: reasonOf(e, "Could not read what it cost") });
    }
  },

  loadCoreCounts: async () => {
    try {
      const [episodes, facts] = await Promise.all([api.memory(CORE, "episode", 1), api.memory(CORE, "fact", 1)]);
      set({ coreCounts: { episodes: episodes.total, facts: facts.total } });
    } catch {
      // counts stay unknown; the core level says so
    }
  },

  loadAll: async () => {
    const s = get();
    await Promise.all([s.loadSpaces(), s.loadActive(), s.loadCards(), s.loadLedger(), s.loadCoreCounts()]);
  },

  setActive: async (spaceId) => {
    try {
      set({ active: (await api.setActiveSpace(spaceId)).space_id, notice: "" });
    } catch (e) {
      set({ notice: reasonOf(e, "Could not switch the project") });
    }
  },

  createSpace: async (name) => {
    const created = await api.createSpace({ name });
    set({ spaces: putSpace(get().spaces, created) });
    return created;
  },

  updateSpace: async (id, patch) => {
    const updated = await api.updateSpace(id, patch);
    set({ spaces: putSpace(get().spaces, updated) });
    return updated;
  },

  eraseSpace: async (id) => {
    await api.eraseSpace(id);
    set({ spaces: get().spaces.filter((s) => s.id !== id) });
    if (routeSpace(get().route) === id) get().navigate({ view: "projects" });
  },

  navigate: (route) => {
    set({ route });
    const hash = toHash(route);
    if (typeof window !== "undefined" && window.location.hash !== hash) window.location.hash = hash;
  },

  syncRoute: (hash) => set({ route: parseHash(hash) }),

  handleEvent: (e) => {
    const s = get();
    switch (e.type) {
      case "space_changed":
        void s.loadSpaces();
        void s.loadCoreCounts();
        if (e.erased && e.space_id && routeSpace(s.route) === e.space_id) s.navigate({ view: "projects" });
        break;
      case "active_space":
        set({ active: e.space_id ?? CORE });
        break;
      case "card_filed":
      case "card_resolved":
        void s.loadCards();
        break;
      case "engine":
        if (e.status) set({ engine: e.status });
        else void s.loadEngine().catch(() => undefined);
        break;
      case "turn_done":
        void s.loadSpaces();
        void s.loadLedger();
        void s.loadCoreCounts();
        break;
    }
  },

  clearNotice: () => set({ notice: "" }),
}));

/** Tests start from a clean store. */
export function resetMain(): void {
  useMain.setState(initial());
}

/** Project name for a space id, or "Core". */
export function whereName(spaces: SpaceSummary[], spaceId: string): string {
  if (spaceId === CORE) return "Core";
  return spaces.find((s) => s.id === spaceId)?.name ?? "A project that is gone";
}
