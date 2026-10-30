// The invented example as a daemon: every route the twins page uses, answered from the generated
// fixture (fixture/twins.ts: what the daemon answered on the scripted engine) at the example's own
// pace. The screen labels it "Invented example"; nothing here reaches a real account. Only what the
// person does off the example's one path (ink, the slips' choices, a mark it did not record, signing
// a draft) is computed here, with the twin rubric's own count (select.ts).

import { DaemonError } from "../../lib/daemon";
import type {
  Card,
  ChannelKind,
  ConnectFlow,
  Mission,
  MissionTurn,
  Piece,
  PieceOp,
  TwinDetail,
  TwinPage,
  TwinRehearsalEvent,
  TwinSayBody,
  TwinSetupEvent,
} from "../../lib/contract";
import { TWIN_FIXTURE } from "./fixture/twins";
import type { TimedRehearsal, TwinFixture } from "./fixture/types";
import type { TwinsIo } from "./io";
import { coverageOf, isReady, readinessOf } from "./select";
import { TWINS_WORDS } from "./words";

export interface ExampleOptions {
  /** Milliseconds per second of the example: 0 answers at once (tests), 1000 at the real pace. */
  pace?: number;
}

const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

/** How long Google's sign-in waits in the example, and how long Notion takes to check a key (s). */
const GMAIL_S = 18;
const NOTION_S = 2;

export function createExampleIo(fx: TwinFixture = TWIN_FIXTURE, { pace = 500 }: ExampleOptions = {}) {
  const S = fx.setup;
  const sleep = (s: number) => new Promise<void>((done) => setTimeout(done, Math.max(0, s * pace)));

  let frame = -1;
  let twin: TwinDetail = clone(S.created);
  const inked = new Set<string>();
  let live = false;
  let relive = false;
  const decided = new Set<string>();
  let run: { kind: "usual" | "handed"; ended: boolean } | null = null;
  let resolvedOnce = false;
  const flows: Partial<Record<ChannelKind, { at: number; ok: boolean; again: boolean }>> = {};

  /** The twin with the person's own inks on it, counted again. */
  const withInks = (t: TwinDetail): TwinDetail => {
    const out = clone(t);
    if (!inked.size || out.state !== "setting_up") return out;
    out.pieces = out.pieces.map((p) => (inked.has(p.id) ? { ...p, confirmed: true } : p));
    out.coverage = coverageOf(out.pieces);
    out.readiness = readinessOf(out.coverage);
    out.ready = isReady(out.coverage);
    return out;
  };
  const inkOp = (op: PieceOp): PieceOp =>
    op.piece && inked.has(op.piece.id) ? { ...op, piece: { ...op.piece, confirmed: true } as Piece } : op;

  const refuse = (what: string): never => {
    throw new DaemonError(404, "unknown_ref", `No ${what} in this example.`);
  };

  const streamOf = (kind: "usual" | "handed"): TimedRehearsal[] =>
    kind === "usual" ? S.rehearsal.events : S.rehearsal.handed.events;

  function pageNow(): TwinPage {
    const page = clone(live ? fx.pageAfter : fx.page);
    for (const t of page.twins) {
      const gone = t.waiting.filter((w) => decided.has(w.id)).length;
      t.waiting = t.waiting.filter((w) => !decided.has(w.id));
      t.waiting_count = t.waiting.length;
      page.stats.waiting_for_you -= gone;
      if (relive && t.state === "paused") {
        t.state = "live";
        delete t.paused_because;
        t.channels = t.channels.map((c) => ({ ...c, status: "connected", health: "active", last_at: fx.now }));
        page.stats.live += 1;
      }
    }
    return page;
  }

  const io: TwinsIo & { reset: () => void } = {
    now: () => new Date(fx.now),

    noteFor: (body: TwinSayBody) => {
      const next = S.frames[frame + 1];
      if (!next) return "";
      if (frame < 0) {
        // the describe step: the example's own need, or its first suggestion, plays as it is
        const t = body.text;
        if (t === S.need || t === TWINS_WORDS.describeSuggestions[0]) return "";
        return (TWINS_WORDS.describeSuggestions as readonly string[]).includes(t) ? TWINS_WORDS.staged : TWINS_WORDS.typed;
      }
      if (body.text) return body.text === next.say.text ? "" : TWINS_WORDS.typed;
      return body.choice && body.choice !== next.say.choice ? TWINS_WORDS.staged : "";
    },

    reset: () => {
      frame = -1;
      twin = clone(S.created);
      inked.clear();
      run = null;
      resolvedOnce = false;
    },

    twins: async () => pageNow(),

    twin: async (id: string) => {
      if (id === S.twinId) return withInks(twin);
      const d = fx.details[id];
      if (d) return clone(d);
      return refuse("such twin");
    },

    createTwin: async () => {
      io.reset();
      return clone(twin);
    },

    twinSay: async (_id, _body, onEvent) => {
      const next = S.frames[frame + 1];
      if (!next) return refuse("further reply");
      const [start, ...rest] = next.events;
      onEvent(start!);
      await sleep(next.elapsed_s);
      for (const e of rest) {
        if (e.type === "sketch") onEvent({ ...e, ops: e.ops.map(inkOp) });
        else if (e.type === "coverage") {
          const t = withInks(next.twin);
          onEvent({ type: "coverage", coverage: t.coverage, ready: t.ready, readiness: t.readiness } satisfies TwinSetupEvent);
        } else onEvent(e);
      }
      frame += 1;
      twin = clone(next.twin);
    },

    twinConfirm: async (_id, pieces) => {
      for (const p of pieces) inked.add(p);
      return withInks(twin);
    },

    twinSamples: async (_id, ids) => {
      twin.samples = twin.samples.map((s) => ({ ...s, picked: ids.includes(s.id) }));
      return withInks(twin);
    },

    twinDials: async (_id, body) => {
      twin.dials = twin.dials.map((d) =>
        body.dials[d.id] !== undefined ? { ...d, value: body.dials[d.id]!, source: body.preset ? "preset" : "you" } : d,
      );
      return withInks(twin);
    },

    twinPages: async (_id, ids) => {
      twin.pages = twin.pages.map((p) => ({ ...p, picked: ids.includes(p.id) }));
      return withInks(twin);
    },

    twinChores: async (_id, ids) => {
      twin.chores = twin.chores.map((c) => ({ ...c, picked: !c.coming && ids.includes(c.id) }));
      return withInks(twin);
    },

    twinAutonomy: async (_id, body) => {
      twin.channels = twin.channels.map((c) => {
        if (c.kind !== body.channel) return c;
        const out = { ...c, autonomy: body.autonomy, bar: body.bar };
        if (body.split) out.split = body.split;
        else delete out.split;
        return out;
      });
      return withInks(twin);
    },

    twinMemory: async (_id, body) => {
      twin.memory = twin.memory.map((f) => (f.id === body.id ? { ...f, keep: body.keep } : f));
      return withInks(twin);
    },

    twinRehearse: async (_id, _goal, onEvent) => {
      // the setup is complete (the daemon takes her suggested mission when it was not set) and the twin
      // holds no rehearsal until this one plays; the daemon plays the whole conversation in one stream.
      // The usual path plays first; tried again, the other side asks for money.
      run = { kind: resolvedOnce ? "handed" : "usual", ended: false };
      frame = S.frames.length - 1;
      twin = clone(S.frames[frame]!.twin);
      delete twin.ask;
      let prev = -1;
      for (const { at_s, event } of streamOf(run.kind)) {
        await sleep(waitBefore(event, at_s, prev));
        prev = at_s;
        onEvent(event);
        if (event.type === "outcome") {
          run.ended = true;
          resolvedOnce = event.state === "resolved";
          twin = clone(run.kind === "usual" ? S.rehearsal.played : S.rehearsal.handed.after);
        }
      }
    },

    twinMark: async (_id, body) => {
      const recorded = run?.kind === "usual" ? S.rehearsal.marks.find((m) => m.mark.turn === body.turn && m.mark.mark === body.mark) : undefined;
      // the daemon's answer when the person marks as the example did; otherwise their own mark, kept
      // on the turn as the daemon keeps it
      if (recorded) twin = clone(recorded.twin);
      const r = twin.rehearsal;
      if (r) {
        r.turns = r.turns.map((t: MissionTurn) => {
          if (t.id !== body.turn) return t;
          const out: MissionTurn = { ...t, mark: body.mark };
          if (body.mark === "edited" && body.edited_text) out.edited_text = body.edited_text;
          else delete out.edited_text;
          return out;
        });
      }
      return withInks(twin);
    },

    twinGoLive: async () => {
      live = true;
      twin = clone(S.golive);
      return clone(twin);
    },

    twinPreview: async (id: string) => {
      const found = fx.previews[id];
      if (!found) return refuse("preview for that twin");
      await sleep(2);
      return clone(found);
    },

    mission: async (id: string, mid: string) => {
      const all: Mission[] = [...pageNow().twins.flatMap((t) => t.missions), ...(twin.rehearsal ? [twin.rehearsal] : [])];
      return clone(all.find((m) => m.twin_id === id && m.id === mid) ?? refuse("such mission"));
    },

    connect: async (kind, body) => {
      flows[kind] = { at: Date.now(), ok: kind === "gmail" || (body.key ?? "").trim().length >= 8, again: kind === "gmail" && !body.client_id };
      return { state: kind === "gmail" ? "waiting" : "exchanging" } satisfies ConnectFlow;
    },

    connectFlow: async (kind) => {
      const f = flows[kind];
      if (!f) return { state: "idle" } satisfies ConnectFlow;
      const due = (kind === "gmail" ? GMAIL_S : NOTION_S) * pace;
      if (Date.now() - f.at < due) return { state: kind === "gmail" ? "waiting" : "exchanging" };
      if (!f.ok) return { state: "failed", detail: "Notion did not accept that key." };
      if (f.again && frame < 0) relive = true;
      return { state: "done" };
    },

    decide: async (cardId, verdict, edited) => {
      const all = pageNow().twins.flatMap((t) => t.waiting);
      const d = all.find((w) => w.card_id === cardId) ?? refuse("such draft");
      decided.add(d.id);
      return {
        id: cardId,
        space_id: "",
        action: d.channel === "gmail" ? "twin_send" : "twin_note",
        label: d.subject,
        args: edited ? { text: edited.text } : { text: d.text },
        state: verdict === "approve" ? "approved" : "declined",
        created: d.created,
        resolved: fx.now,
      } satisfies Card;
    },
  };
  return io;
}

/** Seconds before a rehearsal event shows: a twin's turn takes its writing time, the other side
 * answers within a few seconds, and the outcome follows its last message. */
function waitBefore(e: TwinRehearsalEvent, at: number, prev: number): number {
  if (e.type === "turn") return e.turn.side === "twin" ? (e.turn.elapsed_s ?? 4) : Math.min(3, Math.max(1, at - prev));
  return e.type === "outcome" ? 2.4 : 0;
}

export type ExampleIo = ReturnType<typeof createExampleIo>;
