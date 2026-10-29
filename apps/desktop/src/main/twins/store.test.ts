import { describe, expect, it } from "vitest";
import type { TwinSetupEvent } from "../../lib/contract";
import { createExampleIo } from "./example";
import { TWIN_FIXTURE as fx } from "./fixture/twins";
import { coverageOf, currentTurn, readinessOf, rehearsalStep } from "./select";
import { setupAt, stateOf, TWIN_STATES } from "./states";
import { applyLocal, createTwinsStore, dialsShown, initialSetup, reduceSetup } from "./store";
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
    const s0 = setupAt(0);
    let s = s0;
    for (const e of frames[1]!.events) s = reduceSetup(s, e);
    expect(s.inked).toEqual(["p_name"]);
    expect(s.arrived).toEqual(["p_sign", "p_gmail"]);
    s = reduceSetup(s, frames[2]!.events[0]!);
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

  it("adds rehearsal turns by id and ends on the outcome", () => {
    let s: SetupState = { ...setupAt(11), rehearsal: null };
    for (const { event } of fx.setup.rehearsal.legs[0]!.events) s = reduceSetup(s, event);
    expect(s.rehearsal!.turns.map((t) => t.id)).toEqual(["t1"]);
    s = { ...s, rehearsal: { ...s.rehearsal!, streaming: false } };
    expect(rehearsalStep(s)).toBe("waits");
    s = reduceSetup(s, { type: "outcome", state: "handed_back" });
    expect(rehearsalStep(s)).toBe("handed");
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
    expect(done.ask?.panel).toBe("rehearsal");
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
    expect(currentTurn(edited)?.learned).toBeTruthy();
    store.getState().dispatch({ type: "reh_send" });
    await settled(store);
    expect(rehearsalStep(store.getState().setup)).toBe("resolved");
    expect(store.getState().setup.rehearsal!.outcome!.filed?.where).toBe("Notion: Partnerships");
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
    for (const a of [{ type: "reh_mark", mark: "me" }, { type: "reh_mark", mark: "me" }, { type: "reh_send" }] as const) {
      s2.getState().dispatch(a);
      await settled(s2);
    }
    expect(rehearsalStep(s2.getState().setup)).toBe("resolved");
    s2.getState().dispatch({ type: "reh_alt" });
    await settled(s2);
    s2.getState().dispatch({ type: "reh_mark", mark: "me" });
    await settled(s2);
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
