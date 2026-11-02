import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Draft, DraftJob, JobEvent, SayBody, TurnEvent } from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import { STAGED } from "./fixture/staged";
import { useShownPhase } from "./hooks";
import {
  allMarked,
  applyOps,
  coverageOf,
  covers,
  isAgreed,
  keyOf,
  meanwhileLeft,
  missingFor,
  needMarks,
  needsInk,
  neverLinesOf,
  overlayOf,
  runOf,
  scoreOf,
  sealOf,
  shownPhase,
  SLOW_MS,
} from "./select";
import {
  DEFAULT_VIEW,
  VIEW_KEY,
  applyLocal,
  createStageStore,
  initialStage,
  readView,
  reduce,
  useStage,
  type StageApi,
} from "./store";
import type { StageAction, StageEvent, StageState } from "./types";
import { VIEWS } from "./views";

/** A draft as the daemon stores it, minus the clock. */
const stored = (draft: Draft): Omit<Draft, "updated"> => {
  const out: Partial<Draft> = { ...draft };
  delete out.updated;
  return out as Omit<Draft, "updated">;
};
const fold = (state: StageState, events: readonly StageEvent[]) => events.reduce(reduce, state);
const at = (draft: Draft): StageState => ({ ...initialStage(), draft });
/** The draft after frame i, its confirm included. */
const after = (i: number): Draft => {
  const f = STAGED.frames[i]!;
  return f.confirm?.draft ?? f.draft;
};
const AGREED = after(STAGED.frames.length - 1);

describe("the stage's contract", () => {
  afterEach(() => localStorage.clear());

  it("has both views behind the switch", () => {
    expect(Object.keys(VIEWS).sort()).toEqual(["drawing", "orbit"]);
  });

  it("keeps the view per device and falls back to the default", () => {
    expect(readView()).toBe(DEFAULT_VIEW);
    localStorage.setItem(VIEW_KEY, "orbit");
    expect(readView()).toBe("orbit");
    localStorage.setItem(VIEW_KEY, "list");
    expect(readView()).toBe(DEFAULT_VIEW);
    useStage.getState().dispatch({ type: "switch_view", view: "orbit" });
    expect(localStorage.getItem(VIEW_KEY)).toBe("orbit");
    expect(useStage.getState().view).toBe("orbit");
  });

  it("starts with an empty place memo for each view", () => {
    expect(initialStage().places).toEqual({ drawing: {}, orbit: {} });
  });

  it("stages the whole conversation in wire shape", () => {
    expect(STAGED.created.step).toBe("describe");
    expect(AGREED.agreed).toBe(true);
    expect(AGREED.sketch.nodes.length).toBeGreaterThan(20);
    expect(STAGED.rehearsal.at(-1)?.event.type).toBe("scored");
    expect(STAGED.saved.step).toBe("saved");
  });
});

describe("the fixture's streams through reduce give the drafts the daemon stores", () => {
  it("describe: the first reply on the need", () => {
    const s = fold(at(STAGED.created), STAGED.frames[0]!.events);
    expect(stored(s.draft!)).toEqual(stored(STAGED.frames[0]!.draft));
    expect(s.frame.line).toBe(STAGED.frames[0]!.events.find((e) => e.type === "text")?.delta);
    expect(s.frame.ask).toEqual(STAGED.frames[0]!.events.find((e) => e.type === "ask")?.ask);
    expect(s.frame.phase).toBe("idle");
  });

  it.each(STAGED.frames.map((f, i) => [i, f] as const).slice(1))("shape frame %i", (i, f) => {
    const s = fold(at(after(i - 1)), f.events);
    expect(stored(s.draft!)).toEqual(stored(f.draft));
    expect(s.frame.lastOps).toEqual(f.events.flatMap((e) => (e.type === "sketch" ? e.ops : [])));
    // a reply with no question closes the open one
    expect(s.frame.ask).toEqual(f.events.find((e) => e.type === "ask")?.ask ?? null);
  });

  it.each(STAGED.frames.map((f, i) => [i, f] as const).filter(([, f]) => f.confirm))(
    "shape frame %i's confirm: inking recomputes coverage as the daemon does",
    (_i, f) => {
      const confirm = f.confirm!;
      const ids = new Set(confirm.node_ids);
      const ops = f.draft.sketch.nodes.filter((n) => ids.has(n.id)).map((n) => ({ op: "change" as const, node: { ...n, confirmed: true } }));
      const sketch = applyOps(f.draft.sketch, ops);
      const coverage = coverageOf(sketch);
      expect(sketch).toEqual(confirm.draft.sketch);
      expect(coverage).toEqual(confirm.draft.coverage);
      expect(isAgreed(coverage)).toBe(confirm.draft.agreed);
      const s = reduce(at(f.draft), { type: "draft", draft: confirm.draft });
      expect(stored(s.draft!)).toEqual(stored(confirm.draft));
    },
  );

  it("every stored frame's coverage is computed from its sketch alone", () => {
    for (const f of STAGED.frames) {
      expect(coverageOf(f.draft.sketch)).toEqual(f.draft.coverage);
      expect(isAgreed(f.draft.coverage)).toBe(f.draft.agreed);
    }
  });

  it("write: writing, a repair, then written", () => {
    const s = fold(at(AGREED), STAGED.author.map((t) => t.event));
    expect(stored(s.draft!)).toEqual(stored(STAGED.written));
    expect(s.author.map((e) => e.type)).toEqual(["writing", "repair", "written"]);
  });

  it("write: two repairs that do not fix it go back to the sketch", () => {
    const s = fold(at(AGREED), STAGED.authorFailed.map((t) => t.event));
    expect(stored(s.draft!)).toEqual(stored(STAGED.failedDraft));
    expect(s.author.at(-1)?.type).toBe("author_failed");
  });

  it("preview: the cards she expects land on the draft", () => {
    const s = reduce(at(STAGED.written), { type: "expected", expected: STAGED.preview.expected });
    expect(stored(s.draft!)).toEqual(stored(STAGED.previewed));
  });

  it("key: the person's marks become the body the daemon took, then its draft", () => {
    let s = at(STAGED.previewed);
    for (const m of STAGED.key.marks) s = applyLocal(s, { type: "mark", expected_id: m.expected_id, mark: m.mark, note: m.note });
    for (const t of STAGED.key.missing) s = applyLocal(s, { type: "add_missing", text: t });
    for (const t of STAGED.key.never) s = applyLocal(s, { type: "add_never", text: t });
    expect(allMarked(s)).toBe(true);
    expect(keyOf(s)).toEqual(STAGED.key);
    expect(stored(reduce(s, { type: "draft", draft: STAGED.keyed }).draft!)).toEqual(stored(STAGED.keyed));
  });

  it("rehearse: phases and filed cards, then the score", () => {
    const s = fold(at(STAGED.keyed), STAGED.rehearsal.map((t) => t.event));
    expect(stored(s.draft!)).toEqual(stored(STAGED.scored));
    const run = runOf(s.rehearsal);
    expect(run.phases.map((p) => p.index)).toEqual([1, 2, 3, 4]);
    expect(run.cards).toHaveLength(4);
    const score = scoreOf(s.draft!, run.cards)!;
    expect(score).toMatchObject({ found: 4, eligible: 5, short: true });
    expect(score.rows.map((r) => [r.id, r.mark, r.filed])).toEqual([
      ["e1", "yes", true],
      ["e2", "yes", true],
      ["e3", "yes", true],
      ["e4", "yes", true],
      ["e5", "no", false],
      ["m1", "yes", false],
    ]);
    expect(score.never).toEqual([{ text: "She must never pay the invoice." }]);
  });

  it("verdict: kept, or back to the sketch", () => {
    expect(stored(reduce(at(STAGED.scored), { type: "draft", draft: STAGED.saved }).draft!)).toEqual(stored(STAGED.saved));
    expect(stored(reduce(at(STAGED.scored), { type: "draft", draft: STAGED.revised }).draft!)).toEqual(stored(STAGED.revised));
  });
});

describe("selectors", () => {
  it("says what she still needs, counting a skipped slot as settled", () => {
    // her guesses alone settle an optional slot (steps at 0.5), never a required one
    expect(missingFor(STAGED.frames[0]!.draft.coverage)).toEqual(["inputs", "hand", "never"]);
    const skipped = coverageOf(STAGED.frames[4]!.draft.sketch, new Set(["never"]));
    expect(skipped.never).toBe("skipped");
    expect(missingFor(skipped)).toEqual([]);
    expect(isAgreed(skipped)).toBe(true);
  });

  it("marks the person's phrases in their sentence, never overlapping", () => {
    const marks = needMarks(STAGED.need, after(0).sketch.nodes);
    const text = marks.map((m) => STAGED.need.slice(m.start, m.end).toLowerCase());
    // the quotes the person's pieces were drawn from, verbatim (the winners' three marks)
    expect(text).toEqual([
      "check the after-school club's invoice against the days my kids actually went",
      "the school portal has attendance",
      "dispute the extra days",
    ]);
    for (let i = 1; i < marks.length; i++) expect(marks[i]!.start).toBeGreaterThanOrEqual(marks[i - 1]!.end);
  });

  it("overlays what the last reply added and changed", () => {
    const s = fold(at(after(0)), STAGED.frames[1]!.events);
    const o = overlayOf(s.frame, ["n9"]);
    expect([...o.changed]).toEqual(["n2"]);
    expect(o.added.size).toBe(2);
    expect(o.inked.has("n9")).toBe(true);
  });

  it("derives one seal from the step and the reply", () => {
    expect(sealOf(at(STAGED.saved), "idle")).toEqual({ state: "signed", count: 0 });
    expect(sealOf(at(after(2)), "thinking").state).toBe("working");
    expect(sealOf(at(after(2)), "failed").state).toBe("rest");
    expect(sealOf(at(STAGED.previewed), "idle")).toEqual({ state: "waiting", count: 5 });
    expect(sealOf(at(after(2)), "idle")).toEqual({ state: "waiting", count: 1 });
  });

  it("reads slow only for a reply silent past 8 s", () => {
    const frame = { ...initialStage().frame, phase: "thinking" as const };
    expect(shownPhase(frame, "say", 0, SLOW_MS - 1)).toBe("thinking");
    expect(shownPhase(frame, "say", 0, SLOW_MS)).toBe("slow");
    expect(shownPhase(frame, "write", 0, SLOW_MS * 10)).toBe("thinking");
  });
});

// --- the store over a fake daemon --------------------------------------------------------------

function fakeApi(over: Partial<StageApi> = {}): StageApi & { calls: { name: string; args: unknown[] }[] } {
  const calls: { name: string; args: unknown[] }[] = [];
  const rec =
    <A extends unknown[], R>(name: string, fn: (...a: A) => R) =>
    (...a: A): R => {
      calls.push({ name, args: a });
      return fn(...a);
    };
  const never = () => Promise.reject(new Error("not staged"));
  const base: StageApi = {
    createDraft: rec("createDraft", () => Promise.resolve(STAGED.created)),
    getDraft: rec("getDraft", never),
    draftSay: rec("draftSay", never),
    draftConfirm: rec("draftConfirm", never),
    draftDrop: rec("draftDrop", never),
    draftWrite: rec("draftWrite", never),
    draftPreviewJob: rec("draftPreviewJob", never),
    draftFollow: rec("draftFollow", never),
    draftStopJob: rec("draftStopJob", never),
    draftNotes: rec("draftNotes", never),
    draftKey: rec("draftKey", never),
    draftRehearse: rec("draftRehearse", never),
    draftVerdict: rec("draftVerdict", never),
    draftAccess: rec("draftAccess", never),
  };
  const wrapped = Object.fromEntries(
    Object.entries(over).map(([k, fn]) => [k, rec(k, fn as (...a: unknown[]) => unknown)]),
  ) as Partial<StageApi>;
  return Object.assign(base, wrapped, { calls });
}

/** A say that replays one staged frame's stream. */
const replay = (i: number) => (_id: string, _body: SayBody, on: (e: TurnEvent) => void) => {
  for (const e of STAGED.frames[i]!.events) on(e);
  return Promise.resolve();
};

const flush = () => act(async () => {
  for (let i = 0; i < 10; i++) await Promise.resolve();
});

describe("the stage store", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.useRealTimers());

  it("describes the need: creates the draft, then runs the first reply in the current view", async () => {
    const io = fakeApi({ draftSay: replay(0) });
    const store = createStageStore(io);
    store.getState().dispatch({ type: "switch_view", view: "orbit" });
    store.getState().dispatch({ type: "describe", need: STAGED.need });
    await flush();
    expect(io.calls.map((c) => c.name)).toEqual(["createDraft", "draftSay"]);
    expect(io.calls[1]!.args[1]).toEqual({ text: "", view: "orbit" });
    expect(stored(store.getState().draft!)).toEqual(stored(STAGED.frames[0]!.draft));
    expect(store.getState().frame.youSaid).toBe(STAGED.need);
  });

  it("sends the view the person answered in, picked or typed", async () => {
    const io = fakeApi({ draftSay: replay(1) });
    const store = createStageStore(io);
    store.setState({ draft: after(0) });
    store.getState().dispatch({ type: "pick", choice: "Email in, dispute on the portal" });
    await flush();
    expect(io.calls.at(-1)!.args[1]).toEqual({ text: "", choice: "Email in, dispute on the portal", view: "drawing" });
    store.getState().dispatch({ type: "switch_view", view: "orbit" });
    store.getState().dispatch({ type: "say", text: "  my own   words " });
    await flush();
    expect(io.calls.at(-1)!.args[1]).toEqual({ text: "my own words", view: "orbit" });
  });

  it("reads the draft again after a stream ends in error, and retries the same act", async () => {
    const before = after(2);
    let failing = true;
    const io = fakeApi({
      getDraft: () => Promise.resolve(before),
      draftSay: (_id, _body, on) => {
        if (!failing) return replay(3)(_id, _body, on);
        on({ type: "start", turn_id: "t", engine: "claude_code", simulated: false });
        on(STAGED.frames[3]!.events.find((e) => e.type === "sketch")!);
        on({ type: "error", error: "engine_unavailable", reason: "Muse did not answer" });
        return Promise.resolve();
      },
    });
    const store = createStageStore(io);
    store.setState({ draft: before });
    store.getState().dispatch({ type: "pick", choice: "Yes, closed means not billed" });
    await flush();
    const s = store.getState();
    expect(io.calls.map((c) => c.name)).toEqual(["draftSay", "getDraft"]);
    expect(s.draft).toEqual(before); // the streamed op is gone with the failed reply
    expect(s.frame).toMatchObject({ phase: "failed", problem: "Muse did not answer" });
    expect(s.failed).toEqual({ type: "pick", choice: "Yes, closed means not billed" });
    failing = false;
    store.getState().dispatch({ type: "retry" });
    await flush();
    expect(io.calls.at(-1)!.args[1]).toEqual({ text: "", choice: "Yes, closed means not billed", view: "drawing" });
    expect(stored(store.getState().draft!)).toEqual(stored(STAGED.frames[3]!.draft));
    expect(store.getState().frame.phase).toBe("idle");
  });

  it("reads the draft again when a stream is refused before it starts", async () => {
    const io = fakeApi({
      getDraft: () => Promise.resolve(AGREED),
      draftWrite: () => Promise.reject(new DaemonError(409, "space_busy", "Athena is still answering")),
    });
    const store = createStageStore(io);
    store.setState({ draft: AGREED });
    store.getState().dispatch({ type: "enough" });
    await flush();
    expect(io.calls.map((c) => c.name)).toEqual(["draftWrite", "getDraft"]);
    expect(store.getState().frame.problem).toBe("Athena is still answering");
    expect(store.getState().work).toBeNull();
  });

  it("sends a rubbed-out guess after 5 s, and never one the person undid", async () => {
    vi.useFakeTimers();
    const shaped = after(1);
    const dropped: Draft = { ...shaped, sketch: { ...shaped.sketch, nodes: shaped.sketch.nodes.filter((n) => n.id !== "n4") } };
    const io = fakeApi({ draftDrop: () => Promise.resolve(dropped) });
    const store = createStageStore(io);
    store.setState({ draft: shaped });
    store.getState().dispatch({ type: "drop", node_ids: ["n4"] });
    expect(store.getState().dropping).toEqual(["n4"]);
    store.getState().dispatch({ type: "undo_drop" });
    await act(async () => void vi.advanceTimersByTime(6000));
    expect(io.calls).toEqual([]);
    expect(store.getState().dropping).toEqual([]);

    store.getState().dispatch({ type: "drop", node_ids: ["n4", "n1"] }); // n1 is the person's: not a guess
    expect(store.getState().dropping).toEqual(["n4"]);
    await act(async () => void vi.advanceTimersByTime(4999));
    expect(io.calls).toEqual([]);
    await act(async () => void vi.advanceTimersByTime(1));
    await flush();
    expect(io.calls).toEqual([{ name: "draftDrop", args: [shaped.id, ["n4"]] }]);
    expect(store.getState().dropping).toEqual([]);
    expect(store.getState().draft).toEqual(dropped);
  });

  it("sends a waiting drop first when the person does anything else that talks to the daemon", async () => {
    vi.useFakeTimers();
    const shaped = after(1);
    const io = fakeApi({ draftDrop: () => Promise.resolve(shaped), draftSay: replay(2) });
    const store = createStageStore(io);
    store.setState({ draft: shaped });
    store.getState().dispatch({ type: "drop", node_ids: ["n4"] });
    store.getState().dispatch({ type: "pick", choice: "Mila and Teo, $18 a day each" });
    await flush();
    expect(io.calls.map((c) => c.name)).toEqual(["draftDrop", "draftSay"]);
  });

  it("shows slow after 8 s with nothing heard, and not before", () => {
    vi.useFakeTimers();
    const frame = { ...initialStage().frame, phase: "thinking" as const };
    const t0 = Date.now();
    const { result } = renderHook(() => useShownPhase(frame, "say", t0));
    expect(result.current).toBe("thinking");
    act(() => void vi.advanceTimersByTime(SLOW_MS - 10));
    expect(result.current).toBe("thinking");
    act(() => void vi.advanceTimersByTime(20));
    expect(result.current).toBe("slow");
  });

  it("turns the marks into the key with one press, then starts the test run", async () => {
    const io = fakeApi({
      draftKey: () => Promise.resolve(STAGED.keyed),
      draftRehearse: (_id, on) => {
        for (const t of STAGED.rehearsal) on(t.event);
        return Promise.resolve();
      },
    });
    const store = createStageStore(io);
    store.setState({ draft: STAGED.previewed });
    const marks: StageAction[] = STAGED.key.marks.map((m) => ({ type: "mark", expected_id: m.expected_id, mark: m.mark, note: m.note }));
    for (const a of marks) store.getState().dispatch(a);
    store.getState().dispatch({ type: "add_missing", text: STAGED.key.missing[0]! });
    store.getState().dispatch({ type: "add_never", text: STAGED.key.never[0]! });
    store.getState().dispatch({ type: "send_key" });
    await flush();
    expect(io.calls.map((c) => c.name)).toEqual(["draftKey", "draftRehearse"]);
    expect(io.calls[0]!.args[1]).toEqual(STAGED.key);
    expect(stored(store.getState().draft!)).toEqual(stored(STAGED.scored));
  });

  it("takes the preview job's list onto the draft", async () => {
    const io = fakeApi({
      draftPreviewJob: (_id, on) => {
        on({ type: "job", job: { kind: "preview", state: "running", started: "2026-11-02T10:00:00Z", events: 0 } });
        on({ type: "previewing" });
        on({ type: "previewed", expected: STAGED.preview.expected });
        return Promise.resolve();
      },
    });
    const store = createStageStore(io);
    store.setState({ draft: STAGED.written });
    store.getState().dispatch({ type: "preview" });
    await flush();
    const { job, ...rest } = store.getState().draft!;
    expect(stored(rest as Draft)).toEqual(stored(STAGED.previewed));
    expect(job).toMatchObject({ kind: "preview", state: "done" });
    expect(store.getState()).toMatchObject({ work: null, cursor: 2 });
  });

  it("keeps the draft, the frame, the open question and both place memos when the view switches", async () => {
    const io = fakeApi({ draftSay: replay(2) });
    const store = createStageStore(io);
    store.setState({ draft: after(1) });
    store.getState().dispatch({ type: "pick", choice: "Mila and Teo, $18 a day each" });
    await flush();
    const s = store.getState();
    expect(s.frame.ask).not.toBeNull();
    s.place("drawing", "n1", { area: "need", index: 0 });
    s.place("orbit", "n1", { area: "top", index: 3 });
    const before = store.getState();
    store.getState().dispatch({ type: "switch_view", view: "orbit" });
    const mid = store.getState();
    expect(mid.view).toBe("orbit");
    expect(mid.draft).toBe(before.draft);
    expect(mid.frame).toBe(before.frame);
    expect(mid.places).toBe(before.places);
    store.getState().dispatch({ type: "switch_view", view: "drawing" });
    expect(store.getState().places).toEqual({ drawing: { n1: { area: "need", index: 0 } }, orbit: { n1: { area: "top", index: 3 } } });
  });

  it("forgets the place of a piece that is removed, with its links, and only then", () => {
    const draft = after(3);
    const n4 = draft.sketch.nodes.find((n) => n.id === "n4")!;
    const s: StageState = {
      ...at(draft),
      places: { drawing: { n4: { area: "steps", index: 1 }, n1: { area: "need", index: 0 } }, orbit: { n4: { area: "top", index: 0 } } },
    };
    const kept = fold(s, STAGED.frames[4]!.events); // removes a link only
    expect(kept.places).toBe(s.places);
    const next = reduce(s, { type: "sketch", ops: [{ op: "remove", node: n4 }] });
    expect(next.places).toEqual({ drawing: { n1: { area: "need", index: 0 } }, orbit: {} });
    expect(next.draft!.sketch.edges.some((e) => e.from === "n4" || e.to === "n4")).toBe(false);
  });

  it("guards the check step's marks and lines", () => {
    let s = at(STAGED.previewed);
    s = applyLocal(s, { type: "mark", expected_id: "nope", mark: "yes" });
    expect(s.marks).toEqual({});
    s = applyLocal(s, { type: "mark", expected_id: "e5", mark: "no", note: "  grandma  " });
    expect(s.marks.e5).toEqual({ mark: "no", note: "grandma" });
    s = applyLocal(s, { type: "mark", expected_id: "e5", mark: "yes" });
    expect(s.marks.e5).toEqual({ mark: "yes" });
    s = applyLocal(s, { type: "add_never", text: "pay" });
    expect(applyLocal(s, { type: "add_never", text: " PAY " })).toBe(s);
    expect(applyLocal(s, { type: "add_missing", text: "   " })).toBe(s);
    expect(applyLocal(at(after(2)), { type: "mark", expected_id: "e1", mark: "yes" }).marks).toEqual({});
  });
});

// --- the access step (ADR 0014) -----------------------------------------------------------------

const SCHOOL = "https://portal.maple-school.example";
const CLUB = "https://billing.sunbeam-club.example";
const ACCESS: Draft = {
  ...STAGED.saved,
  step: "access",
  sites: [
    { origin: SCHOOL, label: "The school portal", probe_url: `${SCHOOL}/attendance`, state: "open" },
    { origin: CLUB, label: "The club's billing page", probe_url: `${CLUB}/`, state: "open" },
  ],
};
const withSites = (...states: ("open" | "signed_in" | "skipped")[]): Draft => ({
  ...ACCESS,
  sites: ACCESS.sites!.map((s, i) => ({ ...s, state: states[i] ?? s.state })),
});

describe("the access step", () => {
  it("waits on the person for each site still open, and inks a guessed site on an agreed piece", () => {
    expect(sealOf(at(ACCESS), "idle")).toEqual({ state: "waiting", count: 2 });
    expect(sealOf(at(withSites("signed_in", "open")), "idle")).toEqual({ state: "waiting", count: 1 });
    const node = { ...AGREED.sketch.nodes[0]!, origin: "you" as const, confirmed: true };
    expect(needsInk(node)).toBe(false);
    expect(needsInk({ ...node, site: { origin: CLUB, url: CLUB, label: "Club", confirmed: false } })).toBe(true);
    expect(needsInk({ ...node, site: { origin: CLUB, url: CLUB, label: "Club", confirmed: true } })).toBe(false);
  });

  it("sends sign in, check and skip and takes the daemon's draft; the last one saves", async () => {
    let answer: Draft = withSites("open", "open");
    const io = fakeApi({ draftAccess: () => Promise.resolve(answer) });
    const store = createStageStore(io);
    store.setState({ draft: ACCESS });
    answer = { ...withSites("open", "open"), sites: [{ ...ACCESS.sites![0]!, tab: 3 }, ACCESS.sites![1]!] };
    store.getState().dispatch({ type: "access", origin: SCHOOL, act: "sign_in" });
    await flush();
    expect(io.calls.map((c) => c.args[1])).toEqual([{ origin: SCHOOL, act: "sign_in" }]);
    expect(store.getState().draft!.sites![0]!.tab).toBe(3);
    answer = withSites("signed_in", "open");
    store.getState().dispatch({ type: "access", origin: SCHOOL, act: "check" });
    await flush();
    answer = { ...withSites("signed_in", "skipped"), step: "saved" };
    store.getState().dispatch({ type: "access", origin: CLUB, act: "skip" });
    await flush();
    expect(io.calls.map((c) => (c.args[1] as { act: string }).act)).toEqual(["sign_in", "check", "skip"]);
    expect(store.getState().draft!.step).toBe("saved");
    store.getState().dispatch({ type: "access", origin: CLUB, act: "check" }); // the step is over
    store.getState().dispatch({ type: "access", origin: "https://nowhere.example", act: "check" });
    await flush();
    expect(io.calls).toHaveLength(3);
  });

  it("shows a refused act in plain words and reads the draft again", async () => {
    const io = fakeApi({
      draftAccess: () => Promise.reject(new DaemonError(400, "bad_request", "Her browser is not open; the desktop app runs it.")),
      getDraft: () => Promise.resolve(ACCESS),
    });
    const store = createStageStore(io);
    store.setState({ draft: ACCESS });
    store.getState().dispatch({ type: "access", origin: SCHOOL, act: "check" });
    await flush();
    expect(store.getState().frame.problem).toContain("not open");
    expect(io.calls.map((c) => c.name)).toEqual(["draftAccess", "getDraft"]);
  });
});

// --- the background job, "meanwhile" and the check's pre-fill (onboarding-jobs) -----------------

const STARTED = "2026-11-02T10:00:00Z";
const writeJob = (over: Partial<DraftJob> = {}): DraftJob => ({ kind: "write", state: "running", started: STARTED, events: 1, ...over });
const WRITING: Draft = { ...AGREED, step: "author", job: writeJob() };
const authorLines = (): JobEvent[] => STAGED.author.map((t) => t.event);
/** draftWrite and draftRehearse are typed by their kind's events; their streams carry the job's lines too. */
type Push = (e: JobEvent) => void;

describe("the background job", () => {
  beforeEach(() => localStorage.clear());

  it("folds a job stream: the snapshot, its events, and stopped", () => {
    let s = at(AGREED);
    s = { ...s, work: "write" };
    s = reduce(s, { type: "job", job: writeJob({ events: 0 }) });
    expect(s.draft!.job).toMatchObject({ kind: "write", state: "running" });
    expect(s.startedAt).toBe(Date.parse(STARTED));
    s = reduce(s, authorLines()[0]!);
    expect(s.draft!.step).toBe("author");
    s = reduce(s, { type: "stopped", reason: "Stopped at your request." });
    expect(s.work).toBeNull();
    expect(s.halted).toBe("write");
    expect(s.draft!.job).toMatchObject({ state: "stopped", reason: "Stopped at your request." });
    // anything that moves on clears it: a new write
    expect(reduce(s, authorLines()[0]!).halted).toBeNull();
    // a draft opened with a stopped job says so
    expect(reduce(initialStage(), { type: "draft", draft: { ...WRITING, job: writeJob({ state: "stopped" }) } }).halted).toBe("write");
  });

  it("re-attaches to a running job when the draft is opened, from the start of its events", async () => {
    const io = fakeApi({
      getDraft: () => Promise.resolve(WRITING),
      draftFollow: (_id, _after, on) => {
        on({ type: "job", job: writeJob({ events: 1 }) });
        for (const e of authorLines()) on(e);
        return Promise.resolve();
      },
    });
    const store = createStageStore(io);
    await act(() => store.getState().open(WRITING.id));
    await flush();
    expect(io.calls.map((c) => c.name)).toEqual(["getDraft", "draftFollow"]);
    expect(io.calls[1]!.args.slice(0, 2)).toEqual([WRITING.id, 0]);
    const s = store.getState();
    expect(s.draft!.step).toBe("preview");
    expect(s.draft!.job!.state).toBe("done");
    expect(s.cursor).toBe(authorLines().length);
    expect(s.work).toBeNull();
  });

  it("shows a job that ended while away as it ended, without following it", async () => {
    const io = fakeApi({ getDraft: () => Promise.resolve({ ...STAGED.written, job: writeJob({ state: "done" }) }) });
    const store = createStageStore(io);
    await act(() => store.getState().open(STAGED.written.id));
    await flush();
    expect(io.calls.map((c) => c.name)).toEqual(["getDraft"]);
    expect(store.getState().draft!.step).toBe("preview");
  });

  it("follows the job again on a draft_job event when nothing follows it", async () => {
    const io = fakeApi({
      getDraft: () => Promise.resolve(WRITING),
      draftFollow: (_id, _after, on) => {
        on({ type: "job", job: writeJob() });
        on({ type: "stopped", reason: "Stopped." });
        return Promise.resolve();
      },
    });
    const store = createStageStore(io);
    store.setState({ draft: AGREED });
    await act(() => store.getState().refresh("drf_other"));
    expect(io.calls).toEqual([]);
    await act(() => store.getState().refresh(AGREED.id));
    await flush();
    expect(io.calls.map((c) => c.name)).toContain("draftFollow");
    expect(store.getState().halted).toBe("write");
  });

  it("lets go of the stream when the person leaves mid-job, and never stops the job", async () => {
    let signal: AbortSignal | undefined;
    const io = fakeApi({
      draftWrite: (_id, on, sig) => {
        signal = sig;
        const push = on as Push;
        push({ type: "job", job: writeJob({ events: 0 }) });
        push(authorLines()[0]!);
        return new Promise<void>((_ok, no) => sig?.addEventListener("abort", () => no(new DOMException("aborted", "AbortError"))));
      },
    });
    const store = createStageStore(io);
    store.setState({ draft: AGREED });
    store.getState().dispatch({ type: "enough" });
    await flush();
    expect(store.getState().work).toBe("write");
    store.getState().dispatch({ type: "leave" });
    await flush();
    expect(signal?.aborted).toBe(true);
    expect(io.calls.map((c) => c.name)).toEqual(["draftWrite"]);
    expect(store.getState().draft).toBeNull();
    expect(store.getState().frame.phase).toBe("idle");
  });

  it("Stop ends the job through the daemon; the stream then says stopped and the draft is read again", async () => {
    let finish: () => void = () => undefined;
    let push: Push = () => undefined;
    const io = fakeApi({
      draftWrite: (_id, on) => {
        push = on as Push;
        push({ type: "job", job: writeJob({ events: 0 }) });
        push(authorLines()[0]!);
        return new Promise<void>((ok) => (finish = ok));
      },
      draftStopJob: () => Promise.resolve({ ...WRITING, job: writeJob({ state: "stopped" }) }),
      getDraft: () => Promise.resolve({ ...AGREED, job: writeJob({ state: "stopped", reason: "Stopped." }) }),
    });
    const store = createStageStore(io);
    store.setState({ draft: AGREED });
    store.getState().dispatch({ type: "enough" });
    await flush();
    store.getState().dispatch({ type: "stop" });
    expect(store.getState().stopping).toBe(true);
    await flush();
    expect(io.calls.map((c) => c.name)).toEqual(["draftWrite", "draftStopJob"]);
    push({ type: "stopped", reason: "Stopped." });
    finish();
    await flush();
    expect(io.calls.map((c) => c.name)).toEqual(["draftWrite", "draftStopJob", "getDraft"]);
    expect(store.getState()).toMatchObject({ work: null, halted: "write", stopping: true }); // "You stopped her."
    expect(store.getState().frame.phase).toBe("idle");
  });

  it("a lost job stream with the job still running offers a look again, not a second start", async () => {
    const io = fakeApi({
      draftRehearse: (_id, on) => {
        (on as Push)({ type: "job", job: { kind: "rehearse", state: "running", started: STARTED, events: 0 } });
        return Promise.resolve();
      },
      getDraft: () => Promise.resolve({ ...STAGED.keyed, job: { kind: "rehearse", state: "running", started: STARTED, events: 3 } }),
    });
    const store = createStageStore(io);
    store.setState({ draft: STAGED.keyed });
    store.getState().dispatch({ type: "rehearse" });
    await flush();
    expect(store.getState().failed).toEqual({ type: "reload", draft_id: STAGED.keyed.id });
    expect(store.getState().frame.phase).toBe("failed");
  });
});

describe("meanwhile", () => {
  beforeEach(() => localStorage.clear());

  it("sends the whole notes each time they change", async () => {
    const io = fakeApi({ draftNotes: (_id, body) => Promise.resolve({ ...WRITING, notes: body }) });
    const store = createStageStore(io);
    store.setState({ draft: WRITING, work: "write" });
    store.getState().dispatch({ type: "notes", question: "expect", notes: { expect: ["  a query for 7 Oct "], never: [] } });
    await flush();
    store.getState().dispatch({
      type: "notes",
      question: "expect",
      notes: { expect: ["a query for 7 Oct", "A QUERY FOR 7 OCT", "teo on the 21st"], never: [] },
    });
    await flush();
    expect(io.calls.map((c) => c.args)).toEqual([
      [WRITING.id, { expect: ["a query for 7 Oct"], never: [] }],
      [WRITING.id, { expect: ["a query for 7 Oct", "teo on the 21st"], never: [] }],
    ]);
    expect(store.getState().draft!.notes).toEqual({ expect: ["a query for 7 Oct", "teo on the 21st"], never: [] });
  });

  it("keeps the sketch's never pieces when the person keeps them, and asks only what is left", async () => {
    const io = fakeApi({ draftNotes: (_id, body) => Promise.resolve({ ...WRITING, notes: body }) });
    const store = createStageStore(io);
    store.setState({ draft: WRITING, work: "write" });
    const sketchNever = WRITING.sketch.nodes.filter((n) => n.slot === "never").map((n) => n.label);
    expect(sketchNever.length).toBeGreaterThan(0);
    expect(neverLinesOf(store.getState())).toEqual(sketchNever);
    expect(meanwhileLeft(store.getState())).toEqual(["expect", "never"]);
    store.getState().dispatch({ type: "meanwhile_done", question: "expect" }); // skipped
    store.getState().dispatch({ type: "meanwhile_done", question: "never" });
    await flush();
    expect(io.calls.map((c) => c.args[1])).toEqual([{ expect: [], never: sketchNever }]);
    expect(meanwhileLeft(store.getState())).toEqual([]);
  });

  it("pre-fills the check from the notes: lines no card covers become missed lines, never lines carry over", () => {
    const notes = { expect: ["mila billed on tue 7 oct", "A query for the swimming fee"], never: ["Pay the club"] };
    let s = at({ ...STAGED.written, notes });
    s = reduce(s, { type: "previewed", expected: STAGED.preview.expected });
    expect(s.missing).toEqual(["A query for the swimming fee"]);
    expect(s.never).toEqual(["Pay the club"]);
    expect(covers(STAGED.preview.expected[0]!, "Mila billed on Tue 7 Oct")).toBe(true);
    // the person can still change them before the test
    s = applyLocal(s, { type: "remove_missing", index: 0 });
    expect(keyOf(s).missing).toEqual([]);
    // opening a draft whose check is already listed fills them the same way
    const opened = reduce(initialStage(), { type: "draft", draft: { ...STAGED.previewed, notes } });
    expect(opened.missing).toEqual(["A query for the swimming fee"]);
  });
});
