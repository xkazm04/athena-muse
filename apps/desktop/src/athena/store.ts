// Her window's state: the active project's conversation, the reply streaming in, the cards she filed
// and the seal that tells all of it. One store, because the turn, the project switch and the live
// events all touch the same few fields and must agree.

import { create } from "zustand";
import * as api from "../lib/api";
import { CORE, type AppEvent, type Card, type EngineStatus, type SpaceSummary, type Turn } from "../lib/contract";
import { DaemonError, getConnection, streamRun, UNREACHABLE } from "../lib/daemon";
import type { SealState } from "../theme";

export type LiveItem = { kind: "tool"; label: string } | { kind: "card"; id: string };

/** The reply being written right now (or the one that just failed). */
export interface Live {
  text: string;
  items: LiveItem[];
  done: boolean;
  cost?: number;
  error?: string;
}

export interface HerState {
  status: "reading" | "ready" | "offline";
  /** A boot failure or a refused switch, in the daemon's own words. */
  problem: string;
  engine?: EngineStatus;
  spaces: SpaceSummary[];
  activeId: string;
  turns: Turn[];
  cards: Record<string, Card>;
  streaming: boolean;
  /** What the person sent for the live turn; "" when no turn is on screen. */
  sent: string;
  live: Live | null;
  /** A switch asked for while a turn streams; applied when it ends. */
  pendingId?: string;
  /** The signed flourish is showing. */
  signed: boolean;

  boot(): Promise<void>;
  send(text: string): Promise<void>;
  retry(): Promise<void>;
  stop(): void;
  select(spaceId: string): Promise<void>;
  decided(card: Card): void;
  settle(): void;
  onEvent(e: AppEvent): void;
}

const initial = {
  status: "reading" as const,
  problem: "",
  engine: undefined,
  spaces: [],
  activeId: CORE,
  turns: [],
  cards: {},
  streaming: false,
  sent: "",
  live: null,
  pendingId: undefined,
  signed: false,
};

const reason = (e: unknown, fallback: string): string => (e instanceof DaemonError ? e.reason : fallback);

const byId = (list: Card[]): Record<string, Card> => Object.fromEntries(list.map((c) => [c.id, c]));

export const waitingCount = (s: Pick<HerState, "cards">): number =>
  Object.values(s.cards).filter((c) => c.state === "waiting").length;

/** The seal follows the turn and the cards: signed flashes, working while she writes, waiting while
 *  a card waits on the person, otherwise rest. */
export function sealOf(s: Pick<HerState, "signed" | "streaming" | "live" | "cards">): SealState {
  if (s.signed) return "signed";
  if (s.streaming && !s.live?.items.some((i) => i.kind === "card")) return "working";
  return waitingCount(s) > 0 ? "waiting" : "rest";
}

export const STATE_WORDS: Record<SealState, string> = {
  rest: "Resting",
  working: "Thinking...",
  waiting: "Waiting on you",
  signed: "Signed",
};

let controller: AbortController | null = null;
let booting: Promise<void> | null = null;
// Each conversation load takes a ticket; only the newest one may write, so a slow answer for the
// project the person just left never paints over the one they switched to.
let ticket = 0;

export const useHer = create<HerState>()((set, get) => {
  const loadConversation = async (spaceId: string): Promise<boolean> => {
    const mine = ++ticket;
    try {
      const turns = await api.conversation(spaceId);
      if (mine !== ticket || get().activeId !== spaceId) return false;
      set({ turns });
      return true;
    } catch (e) {
      if (mine === ticket) set({ problem: reason(e, UNREACHABLE) });
      return false;
    }
  };

  const loadCards = async (): Promise<void> => {
    const [waiting, resolved] = await Promise.all([api.cards("waiting"), api.cards("resolved")]);
    set({ cards: byId([...resolved, ...waiting]) });
  };

  const show = (spaceId: string): Promise<boolean> => {
    set({ activeId: spaceId, pendingId: undefined, live: null, sent: "", turns: [], problem: "" });
    return loadConversation(spaceId);
  };

  const switchTo = async (spaceId: string): Promise<void> => {
    try {
      const { space_id } = await api.setActiveSpace(spaceId);
      await show(space_id);
    } catch (e) {
      set({ pendingId: undefined, problem: reason(e, "Could not switch the project") });
    }
  };

  const learnCard = (card: Card): void => {
    const before = get().cards[card.id];
    const flourish = card.state === "approved" && before?.state === "waiting";
    set((s) => ({ cards: { ...s.cards, [card.id]: card }, signed: s.signed || flourish }));
  };

  const doBoot = async (): Promise<void> => {
    set({ status: "reading", problem: "" });
    try {
      await getConnection();
      const [engine, active, spaces] = await Promise.all([api.engine(), api.activeSpace(), api.spaces()]);
      set({ engine, spaces, activeId: active.space_id });
      await Promise.all([loadConversation(active.space_id), loadCards()]);
      set({ status: "ready" });
    } catch (e) {
      set({ status: "offline", problem: reason(e, UNREACHABLE) });
    }
  };

  return {
    ...initial,

    boot() {
      if (!booting) booting = doBoot().finally(() => (booting = null));
      return booting;
    },

    async send(raw) {
      const text = raw.trim();
      if (!text || get().streaming) return;
      const ctrl = new AbortController();
      controller = ctrl;
      const spaceId = get().activeId;
      set({ streaming: true, sent: text, live: { text: "", items: [], done: false }, problem: "" });
      const patch = (fn: (l: Live) => Live) => set((s) => (s.live ? { live: fn(s.live) } : {}));
      let ended = false;
      try {
        await streamRun(
          { text, space_id: spaceId },
          (e) => {
            switch (e.type) {
              case "start":
                set((s) => (s.engine ? { engine: { ...s.engine, engine: e.engine, simulated: e.simulated } } : {}));
                break;
              case "text":
                patch((l) => ({ ...l, text: l.text + e.delta }));
                break;
              case "tool":
                // A gated action shows as its card, which follows; a line too would say it twice.
                if (e.class === "auto") patch((l) => ({ ...l, items: [...l.items, { kind: "tool", label: e.label }] }));
                break;
              case "card":
                learnCard(e.card);
                patch((l) => ({ ...l, items: [...l.items, { kind: "card", id: e.card.id }] }));
                break;
              case "done":
                ended = true;
                patch((l) => ({ ...l, done: true, cost: e.cost_usd }));
                break;
              case "error":
                ended = true;
                patch((l) => ({ ...l, error: e.reason }));
                break;
            }
          },
          ctrl.signal,
        );
        if (!ended) patch((l) => ({ ...l, error: "The reply stopped before it finished" }));
      } catch (e) {
        if (!ctrl.signal.aborted) patch((l) => ({ ...l, error: reason(e, UNREACHABLE) }));
      } finally {
        if (controller === ctrl) controller = null;
        set({ streaming: false });
      }

      const { pendingId } = get();
      if (pendingId !== undefined && pendingId !== spaceId) {
        await switchTo(pendingId);
        return;
      }
      set({ pendingId: undefined });
      // A failed turn keeps its note and "Try again" on screen; anything else reloads so ids are true.
      if (get().live?.error) return;
      if (await loadConversation(spaceId)) set({ live: null, sent: "" });
    },

    async retry() {
      const { sent, streaming } = get();
      if (sent && !streaming) await get().send(sent);
    },

    stop() {
      controller?.abort();
    },

    async select(spaceId) {
      const s = get();
      if (s.streaming) {
        set({ pendingId: spaceId === s.activeId ? undefined : spaceId });
        return;
      }
      if (spaceId === s.activeId) return;
      await switchTo(spaceId);
    },

    decided(card) {
      learnCard(card);
    },

    settle() {
      set({ signed: false });
    },

    onEvent(e) {
      switch (e.type) {
        case "active_space": {
          const id = e.space_id ?? CORE;
          const s = get();
          if (s.streaming) {
            if (id !== s.activeId) set({ pendingId: id });
          } else if (id !== s.activeId) {
            void show(id);
          }
          break;
        }
        case "card_filed":
        case "card_resolved":
          if (e.card) learnCard(e.card);
          break;
        case "engine":
          if (e.status) set({ engine: e.status });
          break;
        case "space_changed":
          void api.spaces().then((spaces) => set({ spaces }), () => undefined);
          if (e.erased) {
            void loadCards().catch(() => undefined);
            if (e.space_id === get().activeId && !get().streaming) void show(CORE);
          }
          break;
        case "turn_done":
          if ((e.space_id ?? CORE) === get().activeId && !get().streaming) void loadConversation(get().activeId);
          break;
      }
    },
  };
});

/** Tests start from a clean window. */
export function resetHer(): void {
  controller?.abort();
  controller = null;
  booting = null;
  ticket = 0;
  useHer.setState({ ...initial });
}
