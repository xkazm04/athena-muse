// Her window's state: the active project's conversation, the reply streaming in, the cards she filed
// and the seal that tells all of it. One store, because the turn, the project switch and the live
// events all touch the same few fields and must agree.

import { create } from "zustand";
import * as api from "../lib/api";
import {
  CORE,
  type AppEvent,
  type Card,
  type EngineStatus,
  type ShownBlocks,
  type SpaceSummary,
  type Turn,
  type TurnEvent,
  type TurnPart,
} from "../lib/contract";
import { DaemonError, getConnection, streamRun, UNREACHABLE } from "../lib/daemon";
import { setupConversation, streamSetup } from "../lib/setup";
import type { SealState } from "../theme";
import { applyLook } from "../ui/look";

/** Her window wears the look chosen in Settings (ADR 0012); unread, the default look stays. */
async function paintLook(): Promise<void> {
  try {
    applyLook((await api.settings()).look);
  } catch {
    // the defaults stay painted; the next `settings` event paints the choice
  }
}

/** One piece of the reply, in the order the stream delivered it. `marks` are where each text delta
 *  began in `text`, so the transcript can fade in only the words that just arrived. */
export type LivePart =
  | { kind: "text"; text: string; marks: number[] }
  | { kind: "tool"; label: string }
  | { kind: "card"; id: string }
  /** Report parts she showed (ADR 0022), with the figures the daemon computed then. */
  | { kind: "blocks"; shown: ShownBlocks }
  /** A stored part this window has no renderer for: shown as a plain row, never dropped. */
  | { kind: "unknown"; what: string };

/** A text delta extends the text run it follows; after a tool line or a card it starts a new run. */
export function appendText(parts: LivePart[], delta: string): LivePart[] {
  if (!delta) return parts;
  const last = parts[parts.length - 1];
  if (last?.kind === "text") {
    return [...parts.slice(0, -1), { kind: "text", text: last.text + delta, marks: [...last.marks, last.text.length] }];
  }
  return [...parts, { kind: "text", text: delta, marks: [0] }];
}

/**
 * The one reducer from a turn's parts to what the transcript draws: fed each streamed event live, and
 * fed a settled turn's stored parts after a reload, so a turn looks the same before and after
 * (inline-structured-rows: one dispatcher, or a kind that rendered live vanishes on reload).
 */
export function addPart(parts: LivePart[], p: TurnPart): LivePart[] {
  switch (p.kind) {
    case "text":
      return appendText(parts, p.text);
    case "tool":
      // A gated action shows as its card, which follows; a line too would say it twice.
      return p.class === "auto" ? [...parts, { kind: "tool", label: p.label }] : parts;
    case "card":
      return [...parts, { kind: "card", id: p.card_id }];
    case "blocks":
      return [...parts, { kind: "blocks", shown: p.shown }];
    default:
      // A part from a newer daemon: a visible row, never nothing (version skew must not edit the record).
      return [...parts, { kind: "unknown", what: String((p as { kind?: unknown }).kind ?? "") }];
  }
}

/** A settled turn's stored parts, read through the live reducer. */
export const settledParts = (parts: readonly TurnPart[]): LivePart[] => parts.reduce(addPart, []);

/** The reply being written right now (or the one that just failed). */
export interface Live {
  /** Text runs, tool lines and cards, interleaved as they streamed (inline-structured-rows: position is meaning). */
  parts: LivePart[];
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
  /** The transcript is the setup conversation (ADR 0017), not the active project's. */
  setup: boolean;

  /** Words the surface handed over while a reply was still being written; the composer takes them. */
  handed: string;

  boot(): Promise<void>;
  send(text: string, opts?: { start?: boolean }): Promise<void>;
  /** "Set up with Athena": show the setup conversation and have her speak first. */
  beginSetup(): Promise<void>;
  /** Words from the surface's ask (ADR 0016): sent as the next turn, or left in the composer when a
   *  reply is still being written. */
  hand(text: string): Promise<void>;
  /** The composer took the handed words. */
  takeHanded(): void;
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
  setup: false,
  handed: "",
};

const reason = (e: unknown, fallback: string): string => (e instanceof DaemonError ? e.reason : fallback);

const byId = (list: Card[]): Record<string, Card> => Object.fromEntries(list.map((c) => [c.id, c]));

export const waitingCount = (s: Pick<HerState, "cards">): number =>
  Object.values(s.cards).filter((c) => c.state === "waiting").length;

/** The seal follows the turn and the cards: signed flashes, working while she writes, waiting while
 *  a card waits on the person, otherwise rest. */
export function sealOf(s: Pick<HerState, "signed" | "streaming" | "live" | "cards">): SealState {
  if (s.signed) return "signed";
  if (s.streaming && !s.live?.parts.some((p) => p.kind === "card")) return "working";
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
      const turns = get().setup ? await setupConversation() : await api.conversation(spaceId);
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
    set({ activeId: spaceId, pendingId: undefined, live: null, sent: "", turns: [], problem: "", setup: false });
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
      void paintLook();
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

    async send(raw, opts) {
      const text = raw.trim();
      // A setup conversation can open with no words of the person's: `start` makes her speak first.
      const start = opts?.start === true && get().setup;
      if ((!text && !start) || get().streaming) return;
      const ctrl = new AbortController();
      controller = ctrl;
      const spaceId = get().activeId;
      set({ streaming: true, sent: text, live: { parts: [], done: false }, problem: "" });
      const patch = (fn: (l: Live) => Live) => set((s) => (s.live ? { live: fn(s.live) } : {}));
      let ended = false;
      try {
        const run = get().setup
          ? (on: (e: TurnEvent) => void, signal: AbortSignal) => streamSetup(text ? { text } : { start: true }, on, signal)
          : (on: (e: TurnEvent) => void, signal: AbortSignal) => streamRun({ text, space_id: spaceId }, on, signal);
        await run(
          (e) => {
            switch (e.type) {
              case "start":
                set((s) => (s.engine ? { engine: { ...s.engine, engine: e.engine, simulated: e.simulated } } : {}));
                break;
              case "text":
                patch((l) => ({ ...l, parts: addPart(l.parts, { kind: "text", text: e.delta }) }));
                break;
              case "tool":
                patch((l) => ({ ...l, parts: addPart(l.parts, { kind: "tool", name: e.name, label: e.label, class: e.class }) }));
                break;
              case "card":
                learnCard(e.card);
                patch((l) => ({ ...l, parts: addPart(l.parts, { kind: "card", card_id: e.card.id }) }));
                break;
              case "blocks":
                patch((l) => ({ ...l, parts: addPart(l.parts, { kind: "blocks", shown: e.shown }) }));
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

    async hand(raw) {
      const text = raw.trim();
      if (!text) return;
      if (get().streaming || get().status !== "ready") set({ handed: text });
      else await get().send(text);
    },

    takeHanded() {
      set({ handed: "" });
    },

    async retry() {
      const { sent, streaming, setup } = get();
      if (streaming) return;
      if (sent) await get().send(sent);
      else if (setup) await get().send("", { start: true });
    },

    async beginSetup() {
      if (get().status !== "ready") await get().boot();
      if (get().status !== "ready") return;
      set({ setup: true, live: null, sent: "", problem: "", pendingId: undefined });
      if (get().streaming) return;
      await loadConversation(get().activeId);
      await get().send("", { start: true });
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
      // A signed step of the setup conversation: she picks up from what came of it.
      const s = get();
      if (s.setup && card.action === "setup_act" && card.state === "approved" && !s.streaming) {
        void s.send("", { start: true });
      }
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
        case "settings":
          if (e.look) applyLook(e.look);
          else void paintLook();
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
