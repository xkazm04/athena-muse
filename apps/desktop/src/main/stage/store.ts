// The stage's one model (onboarding v2). `reduce` folds the daemon's streams into StageState and is
// pure, so the generated fixture can drive it with no daemon; `applyLocal` does the same for what
// the person does before anything is sent (marks, lines, a rubbed-out guess, the open card). The
// store wires both to the daemon through lib/api. The view preference is per device.

import { create } from "zustand";
import * as api from "../../lib/api";
import type {
  AuthorEvent,
  Coverage,
  Draft,
  DraftJob,
  DraftJobState,
  DraftNotes,
  JobEvent,
  PracticeApp,
  RehearsalEvent,
  SayBody,
  StageView,
} from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import { reasonOf } from "../store";
import {
  DROP_MS,
  LINE_MAX,
  LINES_MAX,
  applyOps,
  allMarked,
  checkLinesOf,
  isAgreed,
  isJobWork,
  isPencil,
  keyOf,
  needsInk,
  neverLinesOf,
  notesOf,
  openSlots,
  runningJob,
} from "./select";
import type { Place, StageAction, StageEvent, StageFrame, StageState, StageWork } from "./types";

export const VIEW_KEY = "athena.stage.view";
export const DEFAULT_VIEW: StageView = "drawing";

/** The view this device used last; storage may be blocked, so it falls back to the default. */
export function readView(): StageView {
  try {
    const v = localStorage.getItem(VIEW_KEY);
    return v === "drawing" || v === "orbit" ? v : DEFAULT_VIEW;
  } catch {
    return DEFAULT_VIEW;
  }
}

export function writeView(view: StageView): void {
  try {
    localStorage.setItem(VIEW_KEY, view);
  } catch {
    // a per-device convenience: when storage is blocked the stage still works on the default
  }
}

export const EMPTY_FRAME: StageFrame = { line: "", ask: null, youSaid: "", phase: "idle", problem: "", lastOps: [] };

export function initialStage(view: StageView = DEFAULT_VIEW): StageState {
  return {
    draft: null,
    frame: EMPTY_FRAME,
    view,
    places: { drawing: {}, orbit: {} },
    dropping: [],
    author: [],
    rehearsal: [],
    marks: {},
    missing: [],
    never: [],
    work: null,
    failed: null,
    lastSay: null,
    startedAt: 0,
    heardAt: 0,
    inked: [],
    replyAsked: false,
    card: null,
    cursor: 0,
    halted: null,
    stopping: false,
    notes: null,
    meanwhile: { done: [], touched: [] },
  };
}

// --- reduce: the daemon's events ---------------------------------------------------------------

/** Forgets the places (in both views) and the open card of pieces that are no longer drawn. */
function prune(state: StageState, draft: Draft): Pick<StageState, "places" | "dropping" | "card" | "inked"> {
  const ids = new Set(draft.sketch.nodes.map((n) => n.id));
  const keep = (memo: Record<string, Place>) => {
    const gone = Object.keys(memo).filter((id) => !ids.has(id));
    if (!gone.length) return memo;
    const out = { ...memo };
    for (const id of gone) delete out[id];
    return out;
  };
  const drawing = keep(state.places.drawing);
  const orbit = keep(state.places.orbit);
  const places = drawing === state.places.drawing && orbit === state.places.orbit ? state.places : { drawing, orbit };
  const dropping = state.dropping.filter((id) => ids.has(id));
  return {
    places,
    dropping: dropping.length === state.dropping.length ? state.dropping : dropping,
    card: state.card && ids.has(state.card) ? state.card : null,
    inked: state.inked.filter((id) => ids.has(id)),
  };
}

const withDraft = (state: StageState, draft: Draft): StageState => ({ ...state, draft, ...prune(state, draft) });

/** "That's enough, write it": every open slot reads skipped (drafts/store.py `skip_open`). */
function skipOpen(cov: Coverage): Coverage {
  const out = { ...cov };
  for (const slot of openSlots(cov)) out[slot] = "skipped";
  return out;
}

/** The step a draft leaves when the written chore changes: the later steps' results are stale. */
function written(draft: Draft, chore_id: string, practice: PracticeApp[]): Draft {
  const out: Draft = { ...draft, step: "preview", chore_id, practice };
  delete out.ask;
  delete out.expected;
  delete out.key;
  delete out.bench;
  delete out.verdict;
  delete out.note;
  return out;
}

/** The draft's job as its terminal event leaves it (the stream carries no second snapshot). */
function ended(draft: Draft | null, state: DraftJobState, reason?: string): Draft | null {
  if (!draft?.job || draft.job.state !== "running") return draft;
  const job: DraftJob = { ...draft.job, state };
  if (reason) job.reason = reason;
  return { ...draft, job };
}

/** The check's lines, pre-filled from what the person said while she worked (nothing is sent yet). */
function checkLines(state: StageState, draft: Draft): Pick<StageState, "marks" | "missing" | "never"> {
  const notes = state.notes ?? draft.notes;
  return { marks: {}, ...checkLinesOf(notes, draft.expected ?? []) };
}

/**
 * Folds one daemon event into the state. Pure. A turn's `start` begins a reply, `text` builds her
 * line, `sketch` applies ops in order, `ask` opens the question, `coverage` settles the frame (step
 * `shape`), `done` ends it and `error` fails it (the caller then reads the draft again, and that
 * `{type: "draft"}` replaces it). Writing and the test run append to their lists and move the step
 * as the daemon does. `error` belongs to whatever work is in flight.
 */
export function reduce(state: StageState, event: StageEvent): StageState {
  const d = state.draft;
  const frame = state.frame;
  switch (event.type) {
    case "draft": {
      const fresh = event.draft;
      let next = withDraft(state, fresh);
      // A draft opened with a stopped job says so until anything moves on.
      if (d?.id !== fresh.id && fresh.job?.state === "stopped") next = { ...next, halted: fresh.job.kind };
      // The check's cards arrived while the person was away: its lines start from their notes.
      if (fresh.step === "preview" && fresh.expected?.length && !d?.expected?.length && !state.missing.length && !state.never.length) {
        next = { ...next, ...checkLines(next, fresh) };
      }
      // A reopened stage shows the question the draft still holds open.
      if (frame.ask || !fresh.ask || fresh.step !== "shape") return next;
      return { ...next, frame: { ...next.frame, ask: fresh.ask } };
    }
    case "start":
      return {
        ...state,
        frame: { ...frame, line: "", lastOps: [], phase: "thinking", problem: "" },
        inked: [],
        replyAsked: false,
        halted: null,
      };
    case "job": {
      // The snapshot that opens every job stream: the clock runs from when the job really began.
      const started = Date.parse(event.job.started);
      const running = event.job.state === "running";
      return {
        ...state,
        draft: d ? { ...d, job: event.job } : d,
        startedAt: running && Number.isFinite(started) ? started : state.startedAt,
        halted: running ? null : state.halted,
      };
    }
    case "stopped": {
      const kind = d?.job?.kind ?? (isJobWork(state.work) ? state.work : null);
      return {
        ...state,
        draft: ended(d, "stopped", event.reason),
        work: null,
        halted: kind,
        frame: { ...frame, phase: "idle", problem: "" },
      };
    }
    case "previewing":
      return { ...state, halted: null, frame: { ...frame, phase: "thinking", problem: "" } };
    case "previewed": {
      const next = d ? { ...ended(d, "done")!, expected: event.expected } : d;
      return {
        ...state,
        draft: next,
        work: null,
        stopping: false,
        frame: { ...frame, phase: "idle" },
        ...(next ? checkLines(state, next) : { marks: {}, missing: [], never: [] }),
      };
    }
    case "text":
      return { ...state, frame: { ...frame, line: frame.line + event.delta } };
    case "sketch": {
      if (!d) return state;
      const next = withDraft(state, { ...d, sketch: applyOps(d.sketch, event.ops) });
      return { ...next, frame: { ...frame, lastOps: [...frame.lastOps, ...event.ops] } };
    }
    case "ask":
      return { ...state, frame: { ...frame, ask: event.ask }, replyAsked: true };
    case "coverage": {
      // The reply counted (drafts/shape.py `settle`): the draft keeps this reply's question, or none.
      if (!d) return state;
      const settled: Draft = { ...d, coverage: event.coverage, agreed: event.agreed, step: "shape" };
      if (state.replyAsked && frame.ask) settled.ask = frame.ask;
      else delete settled.ask;
      return { ...state, draft: settled };
    }
    case "done":
      return {
        ...state,
        work: null,
        frame: { ...frame, phase: "idle", ask: state.replyAsked ? frame.ask : null },
      };
    case "tool":
      return state;
    case "repair":
      return { ...state, author: [...state.author, event] };
    case "card":
      // A turn's card cannot happen on a design turn; on the stage, cards come from the test run.
      return d?.step === "rehearse" ? { ...state, rehearsal: [...state.rehearsal, event] } : state;
    case "writing": {
      const next: StageState = { ...state, author: [event], halted: null, frame: { ...frame, phase: "thinking", problem: "" } };
      if (!d) return next;
      const coverage = skipOpen(d.coverage);
      return { ...next, draft: { ...d, step: "author", coverage, agreed: isAgreed(coverage) } };
    }
    case "written":
      return {
        ...state,
        author: [...state.author, event],
        draft: d ? written(ended(d, "done")!, event.chore_id, event.practice) : d,
        work: null,
        stopping: false,
        frame: { ...frame, phase: "idle" },
        marks: {},
        missing: [],
        never: [],
      };
    case "author_failed":
      return {
        ...state,
        author: [...state.author, event],
        draft: d ? { ...ended(d, "failed")!, step: "shape" } : d,
        work: null,
        stopping: false,
        frame: { ...frame, phase: "idle" },
      };
    case "phase":
      return {
        ...state,
        rehearsal: event.index === 1 ? [event] : [...state.rehearsal, event],
        halted: event.index === 1 ? null : state.halted,
      };
    case "scored": {
      const next = d ? { ...ended(d, "done")!, step: "verdict" as const, bench: event.bench } : d;
      if (next) delete next.verdict;
      return {
        ...state,
        rehearsal: [...state.rehearsal, event],
        draft: next,
        work: null,
        stopping: false,
        frame: { ...frame, phase: "idle" },
      };
    }
    case "expected": {
      const next = d ? { ...d, expected: event.expected } : d;
      return { ...state, draft: next, ...(next ? checkLines(state, next) : { marks: {}, missing: [], never: [] }) };
    }
    case "error": {
      const failed: StageState = {
        ...state,
        draft: ended(d, "failed", event.reason),
        work: null,
        stopping: false,
        frame: { ...frame, phase: "failed", problem: event.reason },
      };
      if (state.work === "write") return { ...failed, author: [...state.author, event as AuthorEvent] };
      if (state.work === "rehearse") return { ...failed, rehearsal: [...state.rehearsal, event as RehearsalEvent] };
      return failed;
    }
  }
}

// --- applyLocal: what the person does before anything is sent -----------------------------------

const clean = (text: string) => text.split(/\s+/).filter(Boolean).join(" ");

/** Notes as sent: each line cleaned, empty and repeated lines dropped, within the daemon's caps. */
function cleanNotes(notes: DraftNotes): DraftNotes {
  const lines = (xs: readonly string[]) => {
    const out: string[] = [];
    for (const x of xs) {
      const t = clean(x).slice(0, LINE_MAX);
      if (t && !out.some((y) => y.toLowerCase() === t.toLowerCase()) && out.length < LINES_MAX) out.push(t);
    }
    return out;
  };
  return { expect: lines(notes.expect), never: lines(notes.never) };
}

/** The person's own acts that stay local until sent: guarded, pure; anything else is unchanged. */
export function applyLocal(state: StageState, action: StageAction): StageState {
  const d = state.draft;
  const checking = d?.step === "preview" && !!d.expected?.length && !state.work;
  switch (action.type) {
    case "switch_view":
      return action.view === state.view ? state : { ...state, view: action.view };
    case "mark": {
      if (!checking || !d?.expected?.some((c) => c.id === action.expected_id)) return state;
      const note = action.mark === "no" ? clean(action.note ?? state.marks[action.expected_id]?.note ?? "").slice(0, LINE_MAX) : "";
      const mark = note ? { mark: action.mark, note } : { mark: action.mark };
      return { ...state, marks: { ...state.marks, [action.expected_id]: mark } };
    }
    case "unmark": {
      if (!checking || !state.marks[action.expected_id]) return state;
      const marks = { ...state.marks };
      delete marks[action.expected_id];
      return { ...state, marks };
    }
    case "add_missing":
    case "add_never": {
      const text = clean(action.text);
      const list = action.type === "add_missing" ? state.missing : state.never;
      const dup = list.some((x) => x.toLowerCase() === text.toLowerCase());
      if (!checking || !text || text.length > LINE_MAX || dup || list.length >= LINES_MAX) return state;
      return action.type === "add_missing" ? { ...state, missing: [...list, text] } : { ...state, never: [...list, text] };
    }
    case "remove_missing":
      return checking ? { ...state, missing: state.missing.filter((_, i) => i !== action.index) } : state;
    case "remove_never":
      return checking ? { ...state, never: state.never.filter((_, i) => i !== action.index) } : state;
    case "drop": {
      if (!d || d.step !== "shape" || state.work) return state;
      const pencil = new Set(d.sketch.nodes.filter(isPencil).map((n) => n.id));
      const ids = action.node_ids.filter((id) => pencil.has(id) && !state.dropping.includes(id));
      if (!ids.length) return state;
      return { ...state, dropping: [...state.dropping, ...ids], card: ids.includes(state.card ?? "") ? null : state.card };
    }
    case "undo_drop":
      return state.dropping.length ? { ...state, dropping: [] } : state;
    case "open_card":
      return d?.sketch.nodes.some((n) => n.id === action.node_id) ? { ...state, card: action.node_id } : state;
    case "close_card":
      return state.card ? { ...state, card: null } : state;
    case "notes": {
      const touched = state.meanwhile.touched.includes(action.question)
        ? state.meanwhile.touched
        : [...state.meanwhile.touched, action.question];
      return { ...state, notes: cleanNotes(action.notes), meanwhile: { ...state.meanwhile, touched } };
    }
    case "meanwhile_done":
      return state.meanwhile.done.includes(action.question)
        ? state
        : { ...state, meanwhile: { ...state.meanwhile, done: [...state.meanwhile.done, action.question] } };
    default:
      return state;
  }
}

/** Writes a place a view gave a piece. Pure; only views call it, through the store's `place`. */
export function withPlace(state: StageState, view: StageView, nodeId: string, place: Place): StageState {
  const memo = state.places[view];
  const was = memo[nodeId];
  if (was && was.area === place.area && was.index === place.index) return state;
  return { ...state, places: { ...state.places, [view]: { ...memo, [nodeId]: place } } };
}

// --- the store ---------------------------------------------------------------------------------

/** The daemon routes the stage uses; tests hand in a fake. */
export type StageApi = Pick<
  typeof api,
  | "createDraft"
  | "getDraft"
  | "draftSay"
  | "draftConfirm"
  | "draftDrop"
  | "draftWrite"
  | "draftPreviewJob"
  | "draftFollow"
  | "draftStopJob"
  | "draftNotes"
  | "draftKey"
  | "draftRehearse"
  | "draftVerdict"
  | "draftAccess"
>;

export interface StageStore extends StageState {
  /** Opens a draft by id, or starts `#stage/new` when null. A running job is followed again. */
  open: (draftId: string | null) => Promise<void>;
  dispatch: (action: StageAction) => void;
  place: (view: StageView, nodeId: string, place: Place) => void;
  /** A draft's job started or ended elsewhere (the `draft_job` app event): read it again unless followed. */
  refresh: (draftId: string) => Promise<void>;
}

const LOCAL: ReadonlySet<StageAction["type"]> = new Set([
  "switch_view",
  "mark",
  "unmark",
  "add_missing",
  "add_never",
  "remove_missing",
  "remove_never",
  "open_card",
  "close_card",
]);

const CUT = "Her answer stopped before the end. Nothing was kept from it.";
/** A job's stream was lost while the job runs on in the background: following it again is the retry. */
const LOST = "Lost sight of her work. She is still at it; look again.";

/**
 * A stage store over `io`. `now` is the clock the slow notice reads. Every daemon act waits for any
 * rubbed-out guess to be sent first (or never, if undone), one act runs at a time, and any stream that
 * ends in `error` is followed by a fresh read of the draft. Writing, the preview and the test run are
 * the draft's background jobs: the store follows their streams, never times them out, re-attaches to a
 * running one when a draft is opened, and lets go of one (the job runs on) when the person leaves.
 */
export function createStageStore(io: StageApi = api, now: () => number = Date.now) {
  return create<StageStore>()((set, get) => {
    let dropTimer: ReturnType<typeof setTimeout> | null = null;
    let session = 0; // bumped by open() and leave: an answer for a draft no longer on stage is ignored
    let ctl: AbortController | null = null; // the open stream, so leaving can let go of it
    let notesChain: Promise<void> = Promise.resolve(); // notes go out one at a time, in order

    const feed = (event: StageEvent, from = session) => {
      if (from !== session) return;
      set((s) => ({ ...reduce(s, event), heardAt: now() }));
    };

    /** A job stream's line: also moves the follow cursor past it (the snapshot is not one of its events). */
    const feedJob = (event: JobEvent, from: number) => {
      if (from !== session) return;
      set((s) => ({ ...reduce(s, event), heardAt: now(), cursor: event.type === "job" ? s.cursor : s.cursor + 1 }));
    };

    const begin = (work: StageWork, action: StageAction, extra: Partial<StageState> = {}) => {
      const t = now();
      set((s) => ({
        work,
        failed: null,
        startedAt: t,
        heardAt: t,
        frame: { ...s.frame, phase: "sending", problem: "" },
        card: null,
        ...extra,
      }));
      return { action, from: session };
    };

    const finish = () => set((s) => ({ work: null, frame: s.frame.phase === "failed" ? s.frame : { ...s.frame, phase: "idle" } }));

    /** A refusal or a lost stream becomes an `error` event, then the draft is read again. */
    const fail = async (action: StageAction, from: number, e: unknown) => {
      if (from !== session) return;
      const error = e instanceof DaemonError ? e.error : "bad_request";
      feed({ type: "error", error, reason: reasonOf(e, CUT) }, from);
      set({ failed: action });
      await reread(from);
    };

    const reread = async (from = session) => {
      const id = get().draft?.id;
      if (!id) return;
      try {
        feed({ type: "draft", draft: await io.getDraft(id) }, from);
      } catch {
        // the failure is already on screen; the next act reads the draft again
      }
    };

    /** Sends the drop the person did not undo. */
    const flushDrop = async () => {
      if (dropTimer) clearTimeout(dropTimer);
      dropTimer = null;
      const ids = get().dropping;
      const id = get().draft?.id;
      if (!ids.length || !id) return;
      const { action, from } = begin("drop", { type: "drop", node_ids: ids });
      try {
        feed({ type: "draft", draft: await io.draftDrop(id, ids) }, from);
        set({ dropping: [] });
        finish();
      } catch (e) {
        set({ dropping: [] });
        await fail(action, from, e);
      }
    };

    /**
     * Streams one route; a stream that closes while its work is still open was cut short. A job's
     * stream that closes early leaves the job running in the daemon: the draft is read again, and if
     * the job still runs the retry follows it (a second start would be refused as busy).
     */
    const stream = async (
      work: StageWork,
      action: StageAction,
      run: (from: number, signal: AbortSignal) => Promise<void>,
      fresh = true,
    ) => {
      const lists = !fresh ? {} : work === "write" ? { author: [] } : work === "rehearse" ? { rehearsal: [] } : {};
      const job = isJobWork(work) ? { stopping: false, ...(fresh ? { cursor: 0 } : {}) } : {};
      const { from } = begin(work, action, { ...lists, ...job });
      const mine = new AbortController();
      ctl = mine;
      try {
        await run(from, mine.signal);
        if (from !== session) return;
        if (get().work === work) {
          if (isJobWork(work)) return await lost(action, from);
          await fail(action, from, new Error(CUT));
        } else if (get().frame.phase === "failed") {
          set({ failed: action });
          await reread(from);
        } else if (get().halted) {
          await reread(from); // the daemon's own step after a stop
        }
      } catch (e) {
        if (mine.signal.aborted) return; // the person left; the job runs on
        if (isJobWork(work) && !(e instanceof DaemonError) && from === session) return await lost(action, from);
        await fail(action, from, e);
      } finally {
        if (ctl === mine) ctl = null;
      }
    };

    /** A job's stream closed with no end: read the draft; a finished job shows its result, a running one waits for a look. */
    const lost = async (action: StageAction, from: number) => {
      const id = get().draft?.id;
      let draft: Draft | null = null;
      try {
        if (id) draft = await io.getDraft(id);
      } catch {
        // the notice below says it; the retry reads again
      }
      if (from !== session) return;
      if (draft) feed({ type: "draft", draft }, from);
      if (draft?.job && draft.job.state !== "running") {
        set({ work: null, stopping: false, frame: { ...get().frame, phase: "idle", problem: "" } });
        return;
      }
      const retry: StageAction = draft?.job?.state === "running" && id ? { type: "reload", draft_id: id } : action;
      set((s) => ({ work: null, failed: retry, frame: { ...s.frame, phase: "failed", problem: draft ? LOST : CUT } }));
    };

    /** Follows the draft's running job from the cursor (all of it on a fresh stage). */
    const follow = async (draft: Draft) => {
      const job = draft.job;
      if (!job || job.state !== "running") return;
      const fresh = get().cursor === 0;
      await stream(
        job.kind,
        { type: "reload", draft_id: draft.id },
        (from, signal) => io.draftFollow(draft.id, get().cursor, (e) => feedJob(e, from), signal),
        fresh,
      );
    };

    const say = async (body: SayBody, action: StageAction) => {
      const id = get().draft?.id;
      if (!id) return;
      const words = body.text || body.choice || (get().draft?.need ?? "");
      set((s) => ({ lastSay: body, frame: { ...s.frame, youSaid: words } }));
      await stream("say", action, (from, signal) => io.draftSay(id, body, (e) => feed(e, from), signal));
    };

    /** One request that answers the draft. */
    const call = async (work: StageWork, action: StageAction, run: () => Promise<Draft>) => {
      const { from } = begin(work, action);
      try {
        feed({ type: "draft", draft: await run() }, from);
        finish();
        return true;
      } catch (e) {
        await fail(action, from, e);
        return false;
      }
    };

    const act = async (action: StageAction): Promise<void> => {
      const s = get();
      if (s.work) return; // one act at a time; the buttons say so
      await flushDrop();
      const d = get().draft;
      const view = get().view;
      switch (action.type) {
        case "describe": {
          const need = clean(action.need);
          if (!need || d) return;
          const { from } = begin("describe", action, { frame: { ...EMPTY_FRAME, youSaid: need, phase: "sending" } });
          try {
            feed({ type: "draft", draft: await io.createDraft(need) }, from);
            set({ work: null });
          } catch (e) {
            await fail(action, from, e);
            return;
          }
          await say({ text: "", view }, { type: "say", text: "" });
          return;
        }
        case "say":
        case "pick": {
          if (!d || (d.step !== "shape" && d.step !== "describe")) return;
          const body: SayBody =
            action.type === "pick" ? { text: "", choice: clean(action.choice), view } : { text: clean(action.text), view };
          if (!body.text && !body.choice && d.step !== "describe") return;
          await say(body, action);
          return;
        }
        case "ink": {
          if (!d || d.step !== "shape") return;
          const pencil = new Set(d.sketch.nodes.filter(needsInk).map((n) => n.id));
          const ids = action.node_ids.filter((id) => pencil.has(id));
          if (!ids.length) return;
          if (await call("ink", action, () => io.draftConfirm(d.id, ids))) {
            set((x) => ({ inked: [...x.inked, ...ids], card: null }));
          }
          return;
        }
        case "enough":
          if (!d || (d.step !== "shape" && d.step !== "author")) return;
          await stream("write", action, (from, signal) => io.draftWrite(d.id, (e) => feedJob(e, from), signal));
          return;
        case "preview":
          if (!d || d.step !== "preview") return;
          await stream("preview", action, (from, signal) => io.draftPreviewJob(d.id, (e) => feedJob(e, from), signal));
          return;
        case "send_key": {
          if (!d || (d.step !== "preview" && d.step !== "rehearse") || !allMarked(get())) return;
          const key = keyOf(get());
          // "Run the test" is one press: the marks become the key, then the test run starts.
          if (await call("key", action, () => io.draftKey(d.id, key))) await act({ type: "rehearse" });
          return;
        }
        case "rehearse":
          if (!d || d.step !== "rehearse") return;
          await stream("rehearse", action, (from, signal) => io.draftRehearse(d.id, (e) => feedJob(e, from), signal));
          return;
        case "verdict": {
          if (!d) return;
          const note = clean(action.note ?? "");
          const body = note ? { verdict: action.verdict, note } : { verdict: action.verdict };
          if (await call("verdict", action, () => io.draftVerdict(d.id, body)) && action.verdict === "revise") {
            set((x) => ({ frame: { ...x.frame, line: "", ask: null, lastOps: [] } }));
          }
          return;
        }
        case "access": {
          if (!d || d.step !== "access" || !d.sites?.some((x) => x.origin === action.origin)) return;
          await call("access", action, () => io.draftAccess(d.id, { origin: action.origin, act: action.act }));
          return;
        }
        case "retry": {
          const failed = s.failed;
          if (failed && failed.type !== "retry") await act(failed);
          return;
        }
        case "reload":
          await load(action.draft_id);
          return;
        default:
          return;
      }
    };

    const load = async (draftId: string) => {
      const action: StageAction = { type: "reload", draft_id: draftId };
      const { from } = begin("open", action);
      let draft: Draft;
      try {
        draft = await io.getDraft(draftId);
        feed({ type: "draft", draft }, from);
        finish();
      } catch (e) {
        if (from !== session) return;
        set((s) => ({ work: null, failed: action, frame: { ...s.frame, phase: "failed", problem: reasonOf(e, "Could not open the draft") } }));
        return;
      }
      if (from === session) await follow(draft);
    };

    /** Ends the running job's model process; the job's own stream then says `stopped`. */
    const stop = async () => {
      const kind = runningJob(get());
      const id = get().draft?.id;
      if (!kind || !id || get().stopping) return;
      const from = session;
      set({ stopping: true });
      try {
        const answer = await io.draftStopJob(id);
        if (from !== session) return;
        // only the job: the rest of the draft follows the stream, which is still open
        set((s) => (s.draft && answer.job ? { draft: { ...s.draft, job: answer.job } } : {}));
      } catch {
        if (from === session) set({ stopping: false }); // the job runs on; Stop stays offered
      }
    };

    /** Sends the whole notes, one save at a time; only the notes are taken from the daemon's answer. */
    const saveNotes = (notes: DraftNotes) => {
      const id = get().draft?.id;
      if (!id) return;
      const from = session;
      notesChain = notesChain.then(async () => {
        try {
          const answer = await io.draftNotes(id, notes);
          if (from !== session) return;
          set((s) => (s.draft ? { draft: { ...s.draft, notes: answer.notes ?? notes } } : {}));
        } catch {
          // kept here; the next change sends the whole notes again
        }
      });
    };

    /** Lets go of the stream (no stop: the job runs on) and clears the stage; opening the draft again re-attaches. */
    const leave = () => {
      if (get().dropping.length) void flushDrop(); // a rub-out still waiting is sent, not lost
      if (dropTimer) clearTimeout(dropTimer);
      dropTimer = null;
      session++;
      ctl?.abort();
      ctl = null;
      set({ ...initialStage(get().view) });
    };

    return {
      ...initialStage(readView()),

      open: async (draftId) => {
        if (draftId !== null && get().draft?.id === draftId) return;
        if (dropTimer) clearTimeout(dropTimer);
        dropTimer = null;
        session++;
        ctl?.abort();
        ctl = null;
        set({ ...initialStage(get().view) });
        if (draftId !== null) await load(draftId);
      },

      refresh: async (draftId) => {
        const s = get();
        if (s.draft?.id !== draftId || s.work) return;
        const from = session;
        try {
          const draft = await io.getDraft(draftId);
          if (from !== session || get().work) return;
          feed({ type: "draft", draft }, from);
          await follow(draft);
        } catch {
          // the next act reads the draft again
        }
      },

      dispatch: (action) => {
        if (action.type === "switch_view") writeView(action.view);
        if (action.type === "stop") {
          void stop();
          return;
        }
        if (action.type === "leave") {
          leave();
          return;
        }
        if (action.type === "notes") {
          const before = get();
          set((s) => applyLocal(s, action));
          if (get() !== before) saveNotes(notesOf(get()));
          return;
        }
        if (action.type === "meanwhile_done") {
          // "Keep these" on the never question keeps the sketch's lines the person did not change.
          const s = get();
          if (action.question === "never" && !action.skip && !s.meanwhile.touched.includes("never")) {
            const never = neverLinesOf(s);
            if (never.length && never.join("\n") !== notesOf(s).never.join("\n")) {
              set((x) => applyLocal(x, { type: "notes", question: "never", notes: { ...notesOf(x), never } }));
              saveNotes(notesOf(get()));
            }
          }
          set((x) => applyLocal(x, action));
          return;
        }
        if (action.type === "drop") {
          const before = get().dropping;
          const next = applyLocal(get(), action);
          if (next === get()) return;
          // a second rub-out sends the first one now; the new one gets its own five seconds
          if (before.length) {
            const fresh = next.dropping.filter((id) => !before.includes(id));
            void flushDrop().then(() => {
              set({ dropping: fresh, card: null });
              dropTimer = setTimeout(() => void flushDrop(), DROP_MS);
            });
            return;
          }
          set({ dropping: next.dropping, card: next.card });
          dropTimer = setTimeout(() => void flushDrop(), DROP_MS);
          return;
        }
        if (action.type === "undo_drop") {
          if (dropTimer) clearTimeout(dropTimer);
          dropTimer = null;
          set((s) => applyLocal(s, action));
          return;
        }
        if (LOCAL.has(action.type)) {
          set((s) => applyLocal(s, action));
          return;
        }
        void act(action);
      },

      place: (view, nodeId, place) => set((s) => withPlace(s, view, nodeId, place)),
    };
  });
}

export const useStage = createStageStore();
