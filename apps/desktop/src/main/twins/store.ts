// The twins page's one model (Passport, ADR 0008-0010). `reduceSetup` folds the daemon's setup and
// rehearsal streams into SetupState and is pure, so the generated fixture drives it with no daemon;
// `applyLocal` does the same for what the person does on a slip before anything is sent. The store
// wires both to the daemon through `io` (lib/api live, the invented example otherwise).

import { create } from "zustand";
import {
  BAR_DEFAULT,
  BAR_MAX,
  BAR_MIN,
  CORE,
  type ChannelKind,
  type ConnectFlow,
  type DialsBody,
  type TwinDetail,
  type TwinDraft,
  type TwinSayBody,
} from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import { reasonOf } from "../store";
import { createExampleIo } from "./example";
import { liveIo, type TwinsIo } from "./io";
import { applyPieceOps, currentTurn, pencilOf, rehearsalStep } from "./select";
import type {
  Choices,
  ConnectView,
  RehearsalState,
  SetupState,
  SetupWork,
  TwinsAction,
  TwinsEvent,
  TwinsState,
} from "./types";
import { CONNECT_WORDS, TWINS_WORDS } from "./words";

export const emptyChoices = (): Choices => ({
  samples: {},
  pages: {},
  chores: {},
  memory: {},
  dials: {},
  preset: null,
  autonomy: { first: "assist", reply: "assist", split: false, bar: BAR_DEFAULT, notion: "auto", touched: false },
});

export function initialSetup(): SetupState {
  return {
    twin: null,
    line: "",
    ask: null,
    youSaid: "",
    phase: "idle",
    problem: "",
    arrived: [],
    inked: [],
    replyAsked: false,
    note: "",
    connect: { gmail: "idle", notion: "idle" },
    connectSince: 0,
    connectDetail: "",
    connectUrl: "",
    where: false,
    choices: emptyChoices(),
    rehearsal: null,
    sealed: false,
    work: null,
    startedAt: 0,
    heardAt: 0,
    failed: null,
  };
}

export function initialTwins(mode: TwinsState["mode"] = "live"): TwinsState {
  return {
    mode,
    page: null,
    pageLoad: "idle",
    pageProblem: "",
    before: null,
    issued: null,
    details: {},
    previews: {},
    done: {},
    flash: "",
    signin: null,
    setup: initialSetup(),
  };
}

// --- reduce: the daemon's events ---------------------------------------------------------------

const newRehearsal = (goal: string): RehearsalState => ({
  goal,
  turns: [],
  outcome: null,
  editing: null,
  continued: [],
  editText: "",
  streaming: true,
});

/** A fresh read of the twin: the question it still holds open shows when nothing else is asked. */
function withTwin(s: SetupState, twin: TwinDetail): SetupState {
  const ask = s.ask ?? (s.rehearsal ? null : (twin.ask ?? null));
  return { ...s, twin, ask };
}

/**
 * Folds one event into the setup. Pure. `start` begins her reply, `text` builds her line, `sketch`
 * applies ops in order (nothing already written moves), `ask` opens the question, `coverage` counts
 * the twin again, `done` ends the reply and `error` fails it. A rehearsal's `turn` adds or replaces a
 * turn by id and `outcome` ends it; `twin` is a fresh read.
 */
export function reduceSetup(s: SetupState, e: TwinsEvent): SetupState {
  const t = s.twin;
  switch (e.type) {
    case "twin":
      return withTwin(s, e.twin);
    case "start":
      return { ...s, line: "", phase: "thinking", problem: "", arrived: [], inked: [], replyAsked: false };
    case "text":
      return { ...s, line: s.line + e.delta };
    case "sketch": {
      if (!t) return s;
      const was = new Map(t.pieces.map((p) => [p.id, p]));
      const { pieces, dials } = applyPieceOps(t.pieces, t.dials, e.ops);
      const arrived: string[] = [];
      const inked: string[] = [];
      for (const op of e.ops) {
        const p = op.piece;
        if (!p || op.op === "remove") continue;
        const before = was.get(p.id);
        if (before && !before.confirmed && p.confirmed && before.label === p.label) inked.push(p.id);
        else arrived.push(p.id);
      }
      return {
        ...s,
        twin: { ...t, pieces, dials, style_presets: t.style_presets },
        arrived: [...s.arrived, ...arrived],
        inked: [...s.inked, ...inked],
      };
    }
    case "ask":
      return { ...s, ask: e.ask, replyAsked: true };
    case "coverage":
      return t ? { ...s, twin: { ...t, coverage: e.coverage, ready: e.ready, readiness: e.readiness } } : s;
    case "done":
      return { ...s, phase: "idle", ask: s.replyAsked ? s.ask : null };
    case "error":
      return {
        ...s,
        phase: "failed",
        problem: e.reason,
        rehearsal: s.rehearsal ? { ...s.rehearsal, streaming: false } : null,
      };
    case "turn": {
      const r = s.rehearsal ?? newRehearsal("");
      const turns = r.turns.some((x) => x.id === e.turn.id)
        ? r.turns.map((x) => (x.id === e.turn.id ? e.turn : x))
        : [...r.turns, e.turn];
      return { ...s, rehearsal: { ...r, turns } };
    }
    case "outcome": {
      const r = s.rehearsal ?? newRehearsal("");
      return { ...s, rehearsal: { ...r, outcome: e.filed ? { state: e.state, filed: e.filed } : { state: e.state } } };
    }
    default:
      return s;
  }
}

// --- applyLocal: what the person does on a slip before it is sent --------------------------------

const clampBar = (v: number) => Math.max(BAR_MIN, Math.min(BAR_MAX, v));

/** The person's own choices that stay local until sent: pure; anything else is unchanged. */
export function applyLocal(s: SetupState, a: TwinsAction): SetupState {
  const c = s.choices;
  switch (a.type) {
    case "choose":
      return { ...s, choices: { ...c, [a.group]: { ...c[a.group], [a.id]: a.on } } };
    case "dial":
      return { ...s, choices: { ...c, dials: { ...c.dials, [a.id]: a.value } } };
    case "preset":
      return c.preset === a.name
        ? { ...s, choices: { ...c, preset: null, dials: {} } }
        : { ...s, choices: { ...c, preset: a.name, dials: {} } };
    case "level": {
      const au = { ...c.autonomy, touched: true };
      if (a.which === "notion") au.notion = a.value;
      else if (a.which === "reply") au.reply = a.value;
      else {
        au.first = a.value;
        if (!au.split) au.reply = a.value;
      }
      return { ...s, choices: { ...c, autonomy: au } };
    }
    case "bar":
      return { ...s, choices: { ...c, autonomy: { ...c.autonomy, bar: clampBar(c.autonomy.bar + a.delta), touched: true } } };
    case "split": {
      const split = !c.autonomy.split;
      const au = { ...c.autonomy, split, reply: split ? c.autonomy.reply : c.autonomy.first, touched: true };
      return { ...s, choices: { ...c, autonomy: au } };
    }
    case "where":
      return { ...s, where: !s.where };
    case "reh_text":
      return s.rehearsal ? { ...s, rehearsal: { ...s.rehearsal, editText: a.text } } : s;
    default:
      return s;
  }
}

const LOCAL: ReadonlySet<TwinsAction["type"]> = new Set(["choose", "dial", "preset", "level", "bar", "split", "where", "reh_text"]);

/** A row on a slip: what the daemon keeps of it. */
interface SlipRow {
  id: string;
  picked: boolean;
  suggest: boolean;
}

/** Whether a slip's row is on: the person's choice; else what the twin holds once anything on the
 * slip was picked; else her suggestion (the daemon lists rows unpicked, each with her suggestion). */
export const chosen = (c: Choices, group: "samples" | "pages" | "chores", x: SlipRow, all: readonly SlipRow[]) =>
  c[group][x.id] ?? (all.some((y) => y.picked) ? x.picked : x.suggest);

/** The style presets' dial values, as the daemon applies them (`twins/style.py` PRESETS). */
export const PRESET_VALUES: Record<string, Record<string, number>> = {
  "Friendly pro": { formality: 3, warmth: 4, humor: 2, energy: 3, length: 3, directness: 3, expressiveness: 3, detail: 2 },
  "Brief and direct": { formality: 3, warmth: 2, humor: 1, energy: 2, length: 1, directness: 5, expressiveness: 2, detail: 1 },
  "Warm storyteller": { formality: 2, warmth: 5, humor: 3, energy: 4, length: 4, directness: 2, expressiveness: 5, detail: 4 },
};

/** The dials as the slip shows them: the twin's, with a preset or the person's own values on top. */
export function dialsShown(s: SetupState) {
  const preset = s.choices.preset ? PRESET_VALUES[s.choices.preset] : undefined;
  return (s.twin?.dials ?? []).map((d) => {
    const own = s.choices.dials[d.id];
    if (own !== undefined) return { ...d, value: own, source: "you" as const };
    if (preset?.[d.id] !== undefined) return { ...d, value: preset[d.id]!, source: "preset" as const };
    return d;
  });
}

// --- the store ---------------------------------------------------------------------------------

const CUT = "Her answer stopped before the end. Nothing was kept from it.";
/** Google's sign-in waits this long in the browser before it gives up. */
export const SIGN_IN_TIMEOUT_MS = 10 * 60 * 1000;

export interface TwinsStore extends TwinsState {
  /** Plays the invented example (labelled on screen) instead of the daemon. */
  useExample: (io?: TwinsIo) => void;
  /** Back to the daemon from the invented example. */
  useLive: () => void;
  loadPage: () => Promise<void>;
  loadDetail: (id: string) => Promise<TwinDetail | null>;
  /** The daemon changed something (a card filed or decided, a mission worked): read the page again,
   * and the twins it has open, unless an act of the person's is in flight there. */
  refresh: () => Promise<void>;
  /** How a twin sounds now; the daemon keeps it until its voice changes. */
  loadPreview: (id: string) => Promise<void>;
  /** Opens a twin's setup, or `null` for a new one (the describe step). */
  openSetup: (id: string | null) => Promise<void>;
  dispatch: (action: TwinsAction) => void;
  /** Signs a waiting draft, with the person's words when they changed it. Answers the problem the
   * daemon gave, in plain words, or "" when it went. */
  sign: (draft: TwinDraft, text?: string) => Promise<string>;
  decline: (draft: TwinDraft) => Promise<string>;
  takeOver: (missionId: string) => void;
  signInAgain: (twinId: string) => Promise<void>;
  /** A paused twin goes live again (its rehearsal stands). */
  resume: (twinId: string) => Promise<void>;
  clearFlash: () => void;
  /** "now" for relative times: the example's own, else the clock. */
  now: () => Date;
}

export interface StoreOptions {
  /** How often a sign-in in the browser is asked about (ms). */
  pollMs?: number;
  clock?: () => number;
}

/**
 * A twins store over `io`. One setup act runs at a time; a stream that ends in `error` is followed by
 * a fresh read of the twin; an answer for a setup no longer open is ignored.
 */
export function createTwinsStore(io0: TwinsIo = liveIo, { pollMs = 1000, clock = Date.now }: StoreOptions = {}) {
  let io = io0;
  return create<TwinsStore>()((set, get) => {
    let session = 0;
    let cancelled = false;

    const setS = (patch: Partial<SetupState> | ((s: SetupState) => Partial<SetupState>)) =>
      set((st) => ({ setup: { ...st.setup, ...(typeof patch === "function" ? patch(st.setup) : patch) } }));

    const feed = (e: TwinsEvent, from = session) => {
      if (from !== session) return;
      set((st) => ({ setup: { ...reduceSetup(st.setup, e), heardAt: clock() } }));
    };

    const begin = (work: SetupWork, action: TwinsAction | null) => {
      const t = clock();
      setS((s) => ({ work, failed: null, startedAt: t, heardAt: t, phase: work === "say" ? "sending" : s.phase, problem: "" }));
      return { from: session, action };
    };
    const finish = () => setS((s) => ({ work: null, phase: s.phase === "failed" ? s.phase : "idle" }));

    const reread = async (from = session) => {
      const id = get().setup.twin?.id;
      if (!id) return;
      try {
        feed({ type: "twin", twin: await io.twin(id) }, from);
      } catch {
        // the failure is already on screen; the next act reads the twin again
      }
    };

    const fail = async (action: TwinsAction | null, from: number, e: unknown) => {
      if (from !== session) return;
      const error = e instanceof DaemonError ? e.error : "bad_request";
      feed({ type: "error", error, reason: reasonOf(e, CUT) }, from);
      setS({ work: null, failed: action });
      await reread(from);
    };

    /** One request that answers the twin. */
    const call = async (work: SetupWork, action: TwinsAction | null, run: () => Promise<TwinDetail>) => {
      const { from } = begin(work, action);
      try {
        feed({ type: "twin", twin: await run() }, from);
        finish();
        return true;
      } catch (e) {
        await fail(action, from, e);
        return false;
      }
    };

    const say = async (body: TwinSayBody, action: TwinsAction | null, words: string) => {
      const id = get().setup.twin?.id;
      if (!id) return;
      setS({ youSaid: words, note: io.noteFor?.(body) ?? "" });
      const { from } = begin("say", action);
      try {
        await io.twinSay(id, body, (e) => feed(e, from));
        if (from !== session) return;
        if (get().setup.phase === "thinking") throw new Error(CUT);
        if (get().setup.phase === "failed") {
          setS({ work: null, failed: action });
          await reread(from);
          return;
        }
        await reread(from);
        finish();
      } catch (e) {
        await fail(action, from, e);
      }
    };

    /** Follows a connect until Google or Notion answers, or the wait runs out. A Notion key is checked
     * inside its connect, so its first answer is already the end; Google's sign-in waits in the browser. */
    const connectFlow = async (
      kind: ChannelKind,
      first: ConnectFlow,
      from: number,
      onWait?: (f: ConnectFlow) => void,
    ): Promise<ConnectFlow> => {
      const started = clock();
      let f = first;
      for (;;) {
        if (f.state === "done" || f.state === "failed") return f;
        if (from !== session || cancelled) return { state: "failed" };
        if (clock() - started > SIGN_IN_TIMEOUT_MS) return { state: "failed", detail: CONNECT_WORDS.gmail.failed };
        onWait?.(f);
        await new Promise((r) => setTimeout(r, pollMs));
        f = await io.connectFlow(kind);
      }
    };

    const connect = async (kind: ChannelKind, body: { client_id?: string; client_secret?: string; key?: string }) => {
      const s = get().setup;
      const waiting: ConnectView = kind === "gmail" ? "waiting" : "checking";
      cancelled = false;
      setS({ connect: { ...s.connect, [kind]: waiting }, connectSince: clock(), connectDetail: "", connectUrl: "", note: "" });
      const { from } = begin("connect", null);
      try {
        const first = await io.connect(kind, body);
        const end = await connectFlow(kind, first, from, (f) => {
          if (from === session && f.url) setS({ connectUrl: f.url });
        });
        if (from !== session) return;
        const done = end.state === "done";
        const shown: ConnectView = done ? "connected" : kind === "gmail" ? "failed" : "rejected";
        setS((x) => ({
          connect: { ...x.connect, [kind]: shown },
          connectDetail: done ? "" : (end.detail ?? ""),
          connectUrl: "",
          where: kind === "notion" && !done ? true : x.where,
        }));
        finish();
        if (done) {
          const ask = get().setup.ask;
          await say({ text: "", choice: ask?.suggestions[0] ?? "Connected" }, null, ask?.suggestions[0] ?? "");
        }
      } catch (e) {
        setS((x) => ({
          connect: { ...x.connect, [kind]: kind === "gmail" ? "failed" : "rejected" },
          connectDetail: reasonOf(e, ""),
          connectUrl: "",
        }));
        await fail(null, from, e);
      }
    };

    /** Sends a slip's choices, then answers her question with the slip's own words. */
    const panelGo = async (action: TwinsAction) => {
      const s = get().setup;
      const t = s.twin;
      const panel = s.ask?.panel;
      if (!t || !panel) return;
      const c = s.choices;
      const id = t.id;
      let words = "";
      const runs: (() => Promise<TwinDetail>)[] = [];
      if (panel === "samples") {
        const ids = t.samples.filter((x) => chosen(c, "samples", x, t.samples)).map((x) => x.id);
        runs.push(() => io.twinSamples(id, ids));
        words = `Learn from these ${ids.length}`;
      } else if (panel === "style") {
        const dials = Object.fromEntries(dialsShown(s).filter((d) => d.source !== "learned").map((d) => [d.id, d.value]));
        const body: DialsBody = c.preset ? { dials, preset: c.preset } : { dials };
        if (Object.keys(dials).length) runs.push(() => io.twinDials(id, body));
        words = "Keep this style";
      } else if (panel === "pages") {
        const ids = t.pages.filter((x) => chosen(c, "pages", x, t.pages)).map((x) => x.id);
        runs.push(() => io.twinPages(id, ids));
        words = `Read from these ${ids.length}`;
      } else if (panel === "chores") {
        const ids = t.chores.filter((x) => !x.coming && chosen(c, "chores", x, t.chores)).map((x) => x.id);
        runs.push(() => io.twinChores(id, ids));
        words = `Issue ${ids.length} permit${ids.length === 1 ? "" : "s"}`;
      } else if (panel === "autonomy") {
        const a = c.autonomy;
        if (t.channels.some((x) => x.kind === "gmail")) {
          const split = a.split ? { first_message: a.first, reply: a.reply } : undefined;
          const level = a.split && a.reply === "auto" ? "auto" : a.first;
          runs.push(() => io.twinAutonomy(id, split ? { channel: "gmail", autonomy: level, bar: a.bar, split } : { channel: "gmail", autonomy: level, bar: a.bar }));
        }
        if (t.channels.some((x) => x.kind === "notion")) {
          runs.push(() => io.twinAutonomy(id, { channel: "notion", autonomy: a.notion, bar: 60 }));
        }
        words = "Set clearance";
      } else if (panel === "memory") {
        let kept = 0;
        for (const f of t.memory) {
          const keep = c.memory[f.id] ?? f.keep ?? f.suggest === "keep";
          if (keep) kept++;
          runs.push(() => io.twinMemory(id, { id: f.id, keep }));
        }
        words = `Keep ${kept}, drop ${t.memory.length - kept}`;
      }
      for (const run of runs) if (!(await call("panel", action, run))) return;
      setS({ choices: emptyChoices() });
      await say({ text: words }, action, words);
    };

    const stream = async (action: TwinsAction | null, fresh: boolean, goal: string) => {
      const id = get().setup.twin?.id;
      if (!id) return;
      setS((s) => ({ rehearsal: fresh || !s.rehearsal ? newRehearsal(goal) : { ...s.rehearsal, streaming: true } }));
      const { from } = begin("rehearse", action);
      try {
        await io.twinRehearse(id, goal, (e) => feed(e, from));
        if (from !== session) return;
        setS((s) => ({ rehearsal: s.rehearsal ? { ...s.rehearsal, streaming: false } : null }));
        await reread(from);
        finish();
      } catch (e) {
        await fail(action, from, e);
      }
    };

    /** The mission it rehearses: the person's, else her suggested one (said on screen). */
    const goalOf = (s: SetupState): { goal: string; note: string } => {
      const missions = (s.twin?.pieces ?? []).filter((p) => p.place === "mission");
      const yours = missions.filter((p) => p.origin === "you").at(-1);
      if (yours) return { goal: yours.label, note: "" };
      const suggested = s.ask?.place === "mission" && s.ask.panel !== "rehearsal" ? s.ask.suggestions[0] : missions.at(-1)?.label;
      const goal = suggested ?? "";
      return { goal, note: goal ? TWINS_WORDS.tookMission(goal) : "" };
    };

    /** The person's mark on one draft. The daemon played the whole conversation already, so a mark
     * never plays it again: the next draft that waited, or the outcome, comes up. */
    const mark = async (action: TwinsAction, body: Parameters<TwinsIo["twinMark"]>[1]) => {
      const id = get().setup.twin?.id;
      if (!id) return;
      if (!(await call("mark", action, () => io.twinMark(id, body)))) return;
      setS((s) => (s.rehearsal ? { rehearsal: { ...s.rehearsal, editing: null } } : {}));
    };

    const rehPick = async (i: number, action: TwinsAction) => {
      const s = get().setup;
      const step = rehearsalStep(s);
      const turn = currentTurn(s);
      if (step === "intro") return act({ type: "rehearse" });
      if (step === "waits" && turn) {
        if (i === 2) return act({ type: "reh_edit" });
        return mark(action, { turn: turn.id, mark: i === 0 ? "me" : "not_me" });
      }
      if (step === "held" && turn) {
        if (i === 0) return act({ type: "reh_edit" });
        return mark(action, { turn: turn.id, mark: i === 1 ? "me" : "not_me" });
      }
      if (step === "editing" && turn) {
        if (i === 0) return act({ type: "reh_save" });
        if (i === 1) return mark(action, { turn: turn.id, mark: "me" });
        return setS((x) => (x.rehearsal ? { rehearsal: { ...x.rehearsal, editText: turn.text } } : {}));
      }
      if (step === "edited" && turn) {
        if (i === 2) return mark(action, { turn: turn.id, mark: "me" });
        return act(i === 0 ? { type: "reh_send" } : { type: "reh_edit" });
      }
      if (step === "resolved") return i === 0 ? act({ type: "golive" }) : i === 1 ? act({ type: "reh_alt" }) : undefined;
      if (step === "handed") return i === 0 ? act({ type: "golive" }) : i === 1 ? act({ type: "reh_alt" }) : undefined;
      return undefined;
    };

    const act = async (a: TwinsAction): Promise<void> => {
      const s = get().setup;
      if (s.work && a.type !== "gmail_cancel") return; // one act at a time; the buttons say so
      const t = s.twin;
      switch (a.type) {
        case "describe": {
          const need = a.need.trim();
          if (!need) return;
          if (!t) {
            if (!(await call("create", a, () => io.createTwin(CORE)))) return;
          }
          await say({ text: need }, a, need);
          return;
        }
        case "say": {
          const text = a.text.trim();
          if (!text) return;
          if (!t || !t.pieces.length) return act({ type: "describe", need: text });
          if (s.rehearsal || s.sealed) return rehPick(0, a);
          if (s.ask?.panel === "rehearsal") return act({ type: "rehearse" });
          await say({ text }, a, text);
          return;
        }
        case "pick": {
          if (!t || (!t.pieces.length && !s.ask)) return act({ type: "describe", need: TWINS_WORDS.describeSuggestions[a.index] ?? "" });
          if (s.rehearsal || s.sealed) return rehPick(a.index, a);
          const ask = s.ask;
          if (!ask) return;
          const choice = ask.suggestions[a.index];
          if (choice === undefined) return;
          if (ask.panel === "connect" && ask.channel === "gmail" && a.index < 2) return act({ type: "gmail" });
          if (ask.panel === "connect" && ask.channel === "notion" && a.index === 1) return act({ type: "where" });
          if (ask.panel === "rehearsal") {
            setS({ note: a.index === 0 ? "" : (io.noteFor ? TWINS_WORDS.staged : "") });
            return act({ type: "rehearse" });
          }
          await say({ text: "", choice }, a, choice);
          return;
        }
        case "ink":
        case "ink_all": {
          if (!t) return;
          const pencil = new Set(pencilOf(t).map((p) => p.id));
          const ids = a.type === "ink_all" ? [...pencil] : a.pieces.filter((id) => pencil.has(id));
          if (!ids.length) return;
          if (await call("ink", a, () => io.twinConfirm(t.id, ids))) setS({ inked: ids, arrived: [] });
          return;
        }
        case "panel_go":
          return panelGo(a);
        case "gmail":
          return connect("gmail", a.client_id ? { client_id: a.client_id, client_secret: a.client_secret ?? "" } : {});
        case "gmail_cancel":
          cancelled = true;
          setS((x) => ({ connect: { ...x.connect, gmail: "failed" }, work: null }));
          return;
        case "notion":
          return connect("notion", { key: a.key.trim() });
        case "enough": {
          if (!t) return;
          const { goal, note } = goalOf(s);
          setS({ note, ask: null });
          return stream(a, true, goal);
        }
        case "rehearse": {
          if (!t) return;
          const { goal, note } = goalOf(s);
          setS((x) => ({ note: x.note || note, ask: null }));
          return stream(a, true, goal);
        }
        case "reh_mark": {
          const turn = currentTurn(s);
          if (turn) await mark(a, { turn: turn.id, mark: a.mark });
          return;
        }
        case "reh_edit": {
          const turn = currentTurn(s);
          if (!turn || !s.rehearsal) return;
          setS({ rehearsal: { ...s.rehearsal, editing: turn.id, editText: turn.edited_text ?? turn.text } });
          return;
        }
        case "reh_save": {
          const turn = currentTurn(s);
          const r = s.rehearsal;
          if (!turn || !r) return;
          const text = r.editText.trim();
          if (!text || text === turn.text.trim()) {
            await mark(a, { turn: turn.id, mark: "me" });
            return;
          }
          await mark(a, { turn: turn.id, mark: "edited", edited_text: text });
          return;
        }
        case "reh_send": {
          const turn = currentTurn(s);
          const r = s.rehearsal;
          if (!turn || !r) return;
          setS({ rehearsal: { ...r, continued: [...r.continued, turn.id] } });
          return;
        }
        case "reh_alt":
          return stream(a, true, s.rehearsal?.goal ?? goalOf(s).goal);
        case "golive": {
          if (!t) return;
          const before = get().page?.stats ?? null;
          if (await call("golive", a, () => io.twinGoLive(t.id))) {
            setS({ sealed: true, ask: null, note: "" });
            set({ before, issued: t.id, flash: TWINS_WORDS.liveFlash(t.name), page: null, pageLoad: "idle" });
          }
          return;
        }
        case "retry": {
          const f = s.failed;
          setS({ phase: "idle", problem: "" });
          if (f && f.type !== "retry") await act(f);
          return;
        }
        default:
          return;
      }
    };

    return {
      ...initialTwins(),

      now: () => io.now?.() ?? new Date(clock()),

      useExample: (example) => {
        io = example ?? createExampleIo();
        session++;
        set({ ...initialTwins("example") });
      },

      useLive: () => {
        io = io0;
        session++;
        set({ ...initialTwins("live") });
      },

      loadPage: async () => {
        if (get().pageLoad !== "ready") set({ pageLoad: "reading", pageProblem: "" });
        try {
          set({ page: await io.twins(), pageLoad: "ready", pageProblem: "" });
        } catch (e) {
          set({ pageLoad: "problem", pageProblem: reasonOf(e, TWINS_WORDS.loadProblemLine) });
        }
      },

      loadDetail: async (id) => {
        try {
          const d = await io.twin(id);
          set((st) => ({ details: { ...st.details, [id]: d } }));
          return d;
        } catch {
          return null;
        }
      },

      refresh: async () => {
        const st = get();
        const from = session;
        if (st.pageLoad === "ready") await get().loadPage();
        for (const id of Object.keys(get().details)) await get().loadDetail(id);
        const open = get().setup;
        if (open.twin && !open.work && open.phase !== "failed" && from === session) await reread(from);
      },

      loadPreview: async (id) => {
        const was = get().previews[id];
        if (was?.load === "reading") return;
        set((st) => ({ previews: { ...st.previews, [id]: { ...was, load: "reading", problem: "" } } }));
        try {
          const value = await io.twinPreview(id);
          set((st) => ({ previews: { ...st.previews, [id]: { load: "ready", value } } }));
        } catch (e) {
          const problem = reasonOf(e, "It could not write how it sounds just now. Nothing was changed.");
          set((st) => ({ previews: { ...st.previews, [id]: { ...st.previews[id], load: "problem", problem } } }));
        }
      },

      openSetup: async (id) => {
        if (id !== null && get().setup.twin?.id === id) return;
        session++;
        set({ setup: initialSetup() });
        if (id === null) return;
        const { from } = begin("open", null);
        try {
          feed({ type: "twin", twin: await io.twin(id) }, from);
          finish();
        } catch (e) {
          if (from !== session) return;
          setS({ work: null, phase: "failed", problem: reasonOf(e, "Could not open the twin") });
        }
      },

      dispatch: (action) => {
        if (LOCAL.has(action.type)) {
          setS((s) => applyLocal(s, action));
          return;
        }
        void act(action);
      },

      sign: async (draft, text) => {
        if (!draft.card_id) return "This draft has nothing to sign.";
        const edited = text !== undefined && text.trim() && text.trim() !== draft.text.trim() ? { text: text.trim() } : undefined;
        try {
          await io.decide(draft.card_id, "approve", edited);
        } catch (e) {
          return reasonOf(e, "It could not be sent. Nothing went out.");
        }
        set((st) => ({
          done: { ...st.done, [draft.id]: "signed" },
          flash: edited ? "Your version was sent. It learns from what you changed." : "Signed and sent as you.",
        }));
        await get().loadPage();
        return "";
      },

      decline: async (draft) => {
        if (!draft.card_id) return "This draft has nothing to decline.";
        try {
          await io.decide(draft.card_id, "decline");
        } catch (e) {
          return reasonOf(e, "Could not decline it. Nothing changed.");
        }
        set((st) => ({ done: { ...st.done, [draft.id]: "declined" }, flash: "Declined. It will not send that draft." }));
        await get().loadPage();
        return "";
      },

      takeOver: (missionId) =>
        set((st) => ({
          done: { ...st.done, [missionId]: "taken" },
          flash: "It's yours now. The twin stays out of that conversation until you hand it back.",
        })),

      signInAgain: async (twinId) => {
        const from = session;
        set({ signin: { twin: twinId, state: "waiting", since: clock() } });
        try {
          const end = await connectFlow("gmail", await io.connect("gmail", {}), from);
          set({ signin: { twin: twinId, state: end.state === "done" ? "connected" : "failed", since: clock() } });
          if (end.state === "done") await get().loadPage();
        } catch {
          set({ signin: { twin: twinId, state: "failed", since: clock() } });
        }
      },

      resume: async (twinId) => {
        try {
          const t = await io.twinGoLive(twinId);
          set({ flash: TWINS_WORDS.resumed(t.name) });
          await get().loadPage();
        } catch (e) {
          set({ flash: reasonOf(e, "It could not go live again. Nothing changed.") });
        }
      },

      clearFlash: () => set({ flash: "" }),
    };
  });
}

export const useTwins = createTwinsStore();
