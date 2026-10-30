import { describe, expect, it, vi } from "vitest";
import type { TwinSetupEvent } from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import { createExampleIo } from "./example";
import { TWIN_FIXTURE as fx } from "./fixture/twins";
import { coverageOf, currentTurn, readinessOf, rehearsalStep } from "./select";
import { setupAt, stateOf, TWIN_STATES } from "./states";
import { applyLocal, createTwinsStore, dialsShown, goalsKey, inboxPage, initialSetup, reduceSetup } from "./store";
import type { SetupState } from "./types";

const frames = fx.setup.frames;
const partners = fx.setup.twinId;

/** Waits until the store's setup has no act in flight. */
async function settled(store: ReturnType<typeof createTwinsStore>) {
  for (let i = 0; i < 400 && store.getState().setup.work; i++) await new Promise((r) => setTimeout(r, 0));
  await new Promise((r) => setTimeout(r, 0));
}

function exampleStore() {
  const io = createExampleIo(fx, { pace: 0 });
  const store = createTwinsStore(io, { pollMs: 0 });
  store.getState().useExample(io);
  return store;
}

describe("reduceSetup", () => {
  it("folds every setup stream into the twin the daemon stored after it", () => {
    let s: SetupState = { ...initialSetup(), twin: fx.setup.created };
    for (const f of frames) {
      if (f.before) s = reduceSetup(s, { type: "twin", twin: f.before });
      for (const e of f.events) s = reduceSetup(s, e);
      expect(s.twin!.pieces).toEqual(f.twin.pieces);
      expect(s.twin!.dials).toEqual(f.twin.dials);
      expect(s.twin!.coverage).toEqual(f.twin.coverage);
      expect(s.twin!.readiness).toBe(f.twin.readiness);
      expect(s.ask).toEqual(f.twin.ask ?? null);
      s = reduceSetup(s, { type: "twin", twin: f.twin });
    }
    expect(s.twin!.ready).toBe(true);
  });

  it("marks what a reply wrote and what it inked, so each animates once", () => {
    let s = setupAt(0);
    for (const e of frames[1]!.events) s = reduceSetup(s, e);
    expect(s.arrived).toEqual(["p_sign", "p_gmail"]);
    s = setupAt(1);
    // Gmail was signed in before this reply: the daemon inks its visa in the reply's stream
    for (const e of frames[2]!.events) s = reduceSetup(s, e);
    expect(s.inked).toEqual(["p_gmail"]);
    s = reduceSetup(s, frames[3]!.events[0]!);
    expect(s.arrived).toEqual([]);
    expect(s.phase).toBe("thinking");
  });

  it("keeps the question only when the reply asked one, and fails without losing the twin", () => {
    const s = setupAt(3);
    const start: TwinSetupEvent = { type: "start", turn_id: "t", engine: "scripted", simulated: true };
    const asked = reduceSetup(reduceSetup(s, start), { type: "done", turn_id: "t", waiting: false });
    expect(asked.ask).toBeNull();
    const failed = reduceSetup(reduceSetup(s, start), { type: "error", error: "engine_unavailable", reason: "No answer" });
    expect(failed.phase).toBe("failed");
    expect(failed.problem).toBe("No answer");
    expect(failed.twin).toBe(s.twin);
  });

  it("takes the whole rehearsal in one stream, then walks the drafts that waited before the outcome", () => {
    const r = fx.setup.rehearsal;
    let s: SetupState = { ...setupAt(11), rehearsal: null };
    for (const { event } of r.events) s = reduceSetup(s, event);
    expect(s.rehearsal!.turns.map((t) => t.id)).toEqual(["t1", "t2", "t3", "t4", "t5"]);
    expect(s.rehearsal!.outcome?.state).toBe("resolved");
    expect(rehearsalStep(s)).toBe("sent"); // still streaming: the last draft went on its own
    s = reduceSetup({ ...s, rehearsal: { ...s.rehearsal!, streaming: false } }, { type: "twin", twin: r.played });
    expect(rehearsalStep(s)).toBe("waits");
    expect(currentTurn(s)?.id).toBe("t1");
    s = reduceSetup(s, { type: "twin", twin: r.marks[0]!.twin });
    expect(rehearsalStep(s)).toBe("held");
    expect(currentTurn(s)?.id).toBe("t3");
    s = reduceSetup(s, { type: "twin", twin: r.marks[1]!.twin });
    expect(rehearsalStep(s)).toBe("edited");
    s = { ...s, rehearsal: { ...s.rehearsal!, continued: ["t3"] } };
    expect(rehearsalStep(s)).toBe("resolved");
    expect(currentTurn(s)).toBeUndefined();
  });
});

describe("applyLocal", () => {
  it("keeps the person's slip choices until they are sent", () => {
    let s = setupAt(2);
    s = applyLocal(s, { type: "choose", group: "samples", id: "s5", on: true });
    expect(s.choices.samples).toEqual({ s5: true });
    s = applyLocal(setupAt(3), { type: "preset", name: "Brief and direct" });
    expect(dialsShown(s).find((d) => d.id === "directness")).toMatchObject({ value: 5, source: "preset" });
    s = applyLocal(s, { type: "dial", id: "directness", value: 2 });
    expect(dialsShown(s).find((d) => d.id === "directness")).toMatchObject({ value: 2, source: "you" });
  });

  it("holds the bar between its limits and splits replies from first messages", () => {
    let s = setupAt(8);
    for (let i = 0; i < 20; i++) s = applyLocal(s, { type: "bar", delta: 5 });
    expect(s.choices.autonomy.bar).toBe(99);
    s = applyLocal(s, { type: "split" });
    s = applyLocal(s, { type: "level", which: "reply", value: "auto" });
    expect(s.choices.autonomy).toMatchObject({ split: true, first: "assist", reply: "auto", touched: true });
  });
});

describe("the twin rubric's count", () => {
  it("matches the daemon's coverage and readiness on every frame", () => {
    for (const f of frames) {
      expect(coverageOf(f.twin.pieces)).toEqual(f.twin.coverage);
      expect(readinessOf(f.twin.coverage)).toBe(f.twin.readiness);
    }
  });
});

describe("the store over the example", () => {
  it("plays the setup from the need to a ready twin", async () => {
    const store = exampleStore();
    await store.getState().openSetup(null);
    store.getState().dispatch({ type: "describe", need: fx.setup.need });
    await settled(store);
    expect(store.getState().setup.twin!.id).toBe(partners);
    expect(store.getState().setup.ask?.place).toBe("who");
    for (let i = 1; i < frames.length; i++) {
      const s = store.getState().setup;
      if (s.ask?.panel === "connect") store.getState().dispatch(s.ask.channel === "notion" ? { type: "notion", key: "secret_example_key" } : { type: "gmail" });
      else if (s.ask?.panel) store.getState().dispatch({ type: "panel_go" });
      else store.getState().dispatch({ type: "pick", index: 0 });
      await settled(store);
    }
    const done = store.getState().setup;
    expect(done.twin!.ready).toBe(true);
    expect(done.connect).toEqual({ gmail: "connected", notion: "connected" });
    expect(done.ask).toBeNull(); // the mission is set; she asks nothing more, the rehearsal is the person's call
  });

  it("inks her pencil, and the coverage counts it", async () => {
    const store = exampleStore();
    await store.getState().openSetup(null);
    store.getState().dispatch({ type: "describe", need: fx.setup.need });
    await settled(store);
    expect(store.getState().setup.twin!.coverage.mission).toBe(0.5);
    store.getState().dispatch({ type: "ink_all" });
    await settled(store);
    const s = store.getState().setup;
    expect(s.twin!.pieces.every((p) => p.confirmed)).toBe(true);
    expect(s.twin!.coverage.mission).toBe(1);
    expect(s.inked).toContain("p_mtype");
  });

  it("says when an answer leaves the example's one path", async () => {
    const store = exampleStore();
    await store.getState().openSetup(null);
    store.getState().dispatch({ type: "pick", index: 2 });
    await settled(store);
    expect(store.getState().setup.note).toMatch(/one path/);
  });

  it("rehearses, marks, edits and goes live; the page then counts it", async () => {
    const store = exampleStore();
    const marks: string[] = [];
    const io = createExampleIo(fx, { pace: 0 });
    store.getState().useExample({ ...io, twinMark: (id, body) => (marks.push(`${body.turn}:${body.mark}`), io.twinMark(id, body)) });
    store.setState({ setup: setupAt(11) });
    store.getState().dispatch({ type: "rehearse" });
    await settled(store);
    expect(rehearsalStep(store.getState().setup)).toBe("waits");
    store.getState().dispatch({ type: "reh_mark", mark: "me" });
    await settled(store);
    expect(rehearsalStep(store.getState().setup)).toBe("held");
    expect(currentTurn(store.getState().setup)?.risks?.length).toBe(1);
    store.getState().dispatch({ type: "reh_edit" });
    store.getState().dispatch({ type: "reh_text", text: "My own words, plainly." });
    store.getState().dispatch({ type: "reh_save" });
    await settled(store);
    const edited = store.getState().setup;
    expect(rehearsalStep(edited)).toBe("edited");
    expect(currentTurn(edited)).toMatchObject({ mark: "edited", edited_text: "My own words, plainly." });
    store.getState().dispatch({ type: "reh_send" });
    await settled(store);
    expect(rehearsalStep(store.getState().setup)).toBe("resolved");
    expect(store.getState().setup.twin!.rehearsal!.state).toBe("resolved");
    // a mark never plays the conversation again: one stream, two marks
    expect(marks).toEqual(["t1:me", "t3:edited"]);
    store.getState().dispatch({ type: "golive" });
    await settled(store);
    expect(store.getState().setup.sealed).toBe(true);
    expect(store.getState().issued).toBe(partners);
    await store.getState().loadPage();
    expect(store.getState().page!.stats.live).toBe(2);
  });

  it("plays the hand-back when tried another way", async () => {
    // the example plays its usual path first; a second run plays the money question
    const s2 = exampleStore();
    s2.setState({ setup: setupAt(11) });
    s2.getState().dispatch({ type: "rehearse" });
    await settled(s2);
    for (const a of [{ type: "reh_mark", mark: "me" }, { type: "reh_mark", mark: "me" }] as const) {
      s2.getState().dispatch(a);
      await settled(s2);
    }
    expect(rehearsalStep(s2.getState().setup)).toBe("resolved");
    s2.getState().dispatch({ type: "reh_alt" });
    await settled(s2);
    // its first message and the draft it could not send wait for marks, then the hand-back shows
    for (const step of ["waits", "held"]) {
      expect(rehearsalStep(s2.getState().setup)).toBe(step);
      s2.getState().dispatch({ type: "reh_mark", mark: "me" });
      await settled(s2);
    }
    expect(rehearsalStep(s2.getState().setup)).toBe("handed");
    expect(s2.getState().setup.twin!.rehearsal!.state).toBe("handed_back");
  });

  it("signs a waiting draft with the person's words and takes it off the page", async () => {
    const store = exampleStore();
    await store.getState().loadPage();
    const draft = store.getState().page!.twins[0]!.waiting[0]!;
    await store.getState().sign(draft, "Thanks, Friday works.");
    const st = store.getState();
    expect(st.done[draft.id]).toBe("signed");
    expect(st.flash).toMatch(/Your version/);
    expect(st.page!.twins[0]!.waiting.some((d) => d.id === draft.id)).toBe(false);
    expect(st.page!.stats.waiting_for_you).toBe(fx.page.stats.waiting_for_you - 1);
  });

  it("says plainly when the twins could not be loaded, never as no twins", async () => {
    const io = { ...createExampleIo(fx, { pace: 0 }), twins: () => Promise.reject(new Error("down")) };
    const store = createTwinsStore(io);
    await store.getState().loadPage();
    expect(store.getState().pageLoad).toBe("problem");
    expect(store.getState().page).toBeNull();
  });
});

describe("the named states", () => {
  it.each(TWIN_STATES.map((id) => [id]))("builds %s from the fixture", (id) => {
    const shown = stateOf(id);
    expect(shown.state.mode).toBe("example");
    expect(shown.route.view.startsWith("twin")).toBe(true);
  });
});

describe("the store over the daemon's own answers", () => {
  it("takes a Notion key's answer as the end, without asking about a sign-in flow", async () => {
    const io = createExampleIo(fx, { pace: 0 });
    const connectFlow = vi.fn(io.connectFlow);
    const store = createTwinsStore({ ...io, connect: async () => ({ state: "done" }), connectFlow }, { pollMs: 0 });
    store.setState({ setup: setupAt(4) });
    store.getState().dispatch({ type: "notion", key: "a key" });
    await settled(store);
    expect(connectFlow).not.toHaveBeenCalled();
    expect(store.getState().setup.connect.notion).toBe("connected");
  });

  it("keeps the daemon's words when Google's sign-in does not finish", async () => {
    const io = createExampleIo(fx, { pace: 0 });
    const detail = "Google said no. Nothing was saved.";
    const store = createTwinsStore(
      { ...io, connect: async () => ({ state: "waiting", url: "https://accounts.example/sign-in" }), connectFlow: async () => ({ state: "failed", detail }) },
      { pollMs: 0 },
    );
    store.setState({ setup: setupAt(1) });
    store.getState().dispatch({ type: "gmail" });
    await settled(store);
    expect(store.getState().setup.connect.gmail).toBe("failed");
    expect(store.getState().setup.connectDetail).toBe(detail);
  });

  it("signs through the one decision call, with the person's words, and answers a failed send's problem", async () => {
    const io = createExampleIo(fx, { pace: 0 });
    const decide = vi.fn(io.decide);
    const store = createTwinsStore({ ...io, decide }, { pollMs: 0 });
    store.getState().useExample({ ...io, decide });
    await store.getState().loadPage();
    const draft = store.getState().page!.twins[0]!.waiting[0]!;
    expect(await store.getState().sign(draft, "My words.")).toBe("");
    expect(decide).toHaveBeenCalledWith(draft.card_id, "approve", { text: "My words." });
    const failing = createTwinsStore({ ...io, decide: () => Promise.reject(new DaemonError(400, "bad_request", "Gmail did not send it: refused")) });
    expect(await failing.getState().sign(draft)).toBe("Gmail did not send it: refused");
    expect(failing.getState().done[draft.id]).toBeUndefined();
  });

  it("reads the page and the open twins again when the daemon says something changed", async () => {
    const io = createExampleIo(fx, { pace: 0 });
    const twins = vi.fn(io.twins);
    const twin = vi.fn(io.twin);
    const store = createTwinsStore({ ...io, twins, twin }, { pollMs: 0 });
    await store.getState().loadPage();
    await store.getState().loadDetail(fx.page.twins[0]!.id);
    await store.getState().refresh();
    expect(twins).toHaveBeenCalledTimes(2);
    expect(twin).toHaveBeenCalledTimes(2);
  });

  it("reads the new entry slip's conversations, and her goals once per conversation", async () => {
    const io = createExampleIo(fx, { pace: 0 });
    const twinGoals = vi.fn(io.twinGoals);
    const store = createTwinsStore({ ...io, twinGoals }, { pollMs: 0 });
    const desk = fx.page.twins[0]!.id;
    await store.getState().loadThreads(desk);
    expect(store.getState().entries[desk]).toEqual({ load: "ready", threads: fx.threads[desk]!.threads });
    const pick = { thread: fx.goals[desk]!.thread };
    await store.getState().suggestGoals(desk, pick);
    await store.getState().suggestGoals(desk, pick);
    expect(twinGoals).toHaveBeenCalledTimes(1);
    expect(store.getState().goals[goalsKey(desk, pick)]).toEqual({ load: "ready", goals: fx.goals[desk]!.goals });
    // her suggestions are optional: a failure leaves none, quietly, and may be asked again
    const failing = createTwinsStore({ ...io, twinGoals: () => Promise.reject(new Error("no")) }, { pollMs: 0 });
    await failing.getState().suggestGoals(desk, { to: "kai@moss.example" });
    expect(failing.getState().goals[goalsKey(desk, { to: "Kai@Moss.example " })]).toEqual({ load: "problem", goals: [] });
  });

  it("starts a mission from the slip, then reads the page again; a refusal comes back in plain words", async () => {
    const io = createExampleIo(fx, { pace: 0 });
    const desk = fx.page.twins[0]!;
    const made = { ...desk.missions[0]!, id: "ms_new", source: "page" as const };
    const twins = vi.fn(io.twins);
    const startMission = vi.fn(async () => made);
    const store = createTwinsStore({ ...io, twins, startMission }, { pollMs: 0 });
    const body = { thread: "thquote", goal: "Get Oren's sign-off" };
    expect(await store.getState().startMission(desk.id, body)).toEqual({ mission: made, problem: "" });
    expect(startMission).toHaveBeenCalledWith(desk.id, body);
    expect(twins).toHaveBeenCalledTimes(1);
    expect(store.getState().flash).toMatch(/It took the mission with/);
    // the invented example starts nothing, and says so
    const example = createTwinsStore(io, { pollMs: 0 });
    const refused = await example.getState().startMission(desk.id, body);
    expect(refused.mission).toBeUndefined();
    expect(refused.problem).toMatch(/invented example starts no missions/);
  });

  it("sends the page the task inbox reads with the permits, one it may read", () => {
    const s = setupAt(7);
    const t = s.twin!;
    const readable = t.pages.filter((p) => p.picked && p.kind === "page");
    expect(readable.length).toBeGreaterThan(1);
    expect(inboxPage(s)).toBe(readable[0]!.id);
    const chosen = applyLocal(s, { type: "inbox", page: readable[1]!.id });
    expect(inboxPage(chosen)).toBe(readable[1]!.id);
    // a page it may not read is never sent: it falls back to one it may
    const database = t.pages.find((p) => p.kind === "database")!;
    expect(inboxPage(applyLocal(s, { type: "inbox", page: database.id }))).toBe(readable[0]!.id);
  });

  it("asks how a twin sounds once, and keeps the daemon's answer", async () => {
    const io = createExampleIo(fx, { pace: 0 });
    const store = createTwinsStore(io, { pollMs: 0 });
    await store.getState().loadPreview(partners);
    expect(store.getState().previews[partners]).toEqual({ load: "ready", value: fx.previews[partners] });
  });
});
