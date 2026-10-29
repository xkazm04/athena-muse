// The Orbit view (WP3-3): pieces never move, zones fill and grow without moving anyone, links go
// round the card, and every interaction reaches the store through `dispatch`.
import { cleanup, fireEvent, render, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Draft, SketchOp } from "../../../lib/contract";
import { stageBeats } from "../../../preview/stageBeats";
import { STAGED } from "../fixture/staged";
import { applyOps } from "../select";
import { StageScreen } from "../Stage";
import { initialStage, reduce, withPlace } from "../store";
import type { Place, StageAction, StageState } from "../types";
import { MORE_NODES, MORE_OPS } from "./fixture36";
import { crosses, ringArcs, routeLink, type Box } from "./geometry";
import { gridFor, placesFor, SIDE_OF, splitZone, unsaved, type Side, type ZoneBox } from "./place";

afterEach(cleanup);

/** Keeps places the way the view does: every new place is written, nothing else is touched. */
function keep(draft: Draft, memo: Record<string, Place>): Record<string, Place> {
  const out = { ...memo };
  for (const [id, p] of unsaved(placesFor(draft.sketch.nodes, out), out)) out[id] = p;
  // the store forgets the places of pieces no longer drawn (store.ts `prune`)
  const ids = new Set(draft.sketch.nodes.map((n) => n.id));
  for (const id of Object.keys(out)) if (!ids.has(id)) delete out[id];
  return out;
}

function expectKept(before: Record<string, Place>, after: Record<string, Place>) {
  for (const [id, p] of Object.entries(before)) if (after[id]) expect(after[id], id).toEqual(p);
}

describe("placement", () => {
  it("gives every piece the next free cell of its zone in arrival order, and never moves one as the staged sketch grows", () => {
    let memo: Record<string, Place> = {};
    let draft: Draft = STAGED.created;
    for (const f of STAGED.frames) {
      for (const e of f.events) {
        if (e.type !== "sketch") continue;
        for (const op of e.ops) {
          draft = { ...draft, sketch: applyOps(draft.sketch, [op]) };
          const next = keep(draft, memo);
          expectKept(memo, next);
          memo = next;
        }
      }
      if (f.confirm) {
        const next = keep(f.confirm.draft, memo);
        expectKept(memo, next);
        memo = next;
        draft = f.confirm.draft;
      }
    }
    expect(memo.n1).toBeUndefined(); // the need lives in the card, not in a zone
    expect(memo.n4).toEqual({ area: "steps", index: 0 });
    expect(memo.n7).toEqual({ area: "steps", index: 1 });
    expect(memo.n2).toEqual({ area: "apps", index: 0 });
    expect(memo.n3).toEqual({ area: "apps", index: 1 });
    expect(Object.keys(memo)).toHaveLength(22);
  });

  it("keeps every place when the sketch grows to 36 pieces and the zones fill past their room", () => {
    const final = STAGED.frames.at(-1)!.confirm!.draft;
    let memo = keep(final, {});
    let draft = final;
    const box: ZoneBox = { w: 252, h: 236, chipW: 180, chipH: 48, gap: 6, lineH: 29, lineGap: 3 };
    const before = gridFor(box, 3);
    for (const op of MORE_OPS) {
      draft = { ...draft, sketch: applyOps(draft.sketch, [op]) };
      const next = keep(draft, memo);
      expectKept(memo, next);
      memo = next;
    }
    expect(draft.sketch.nodes).toHaveLength(36);
    // apps grew from 4 to 7 pieces: past its room at full height, so it went to one-line chips
    const apps = Object.values(memo).filter((p) => p.area === "apps");
    const grown = gridFor(box, Math.max(...apps.map((p) => p.index)));
    expect(before.dense).toBe(false);
    expect(grown.dense).toBe(true);
    expect(grown.cols).toBe(before.cols); // a piece keeps its column; only the rows get shorter
    expect(memo.s1).toEqual({ area: "apps", index: 4 });
  });

  it("leaves a dropped piece's cell empty until the next arrival takes it", () => {
    const final = STAGED.frames.at(-1)!.confirm!.draft;
    let memo = keep(final, {});
    const n7 = memo.n7!;
    const dropped = { ...final, sketch: applyOps(final.sketch, [{ op: "remove", node: final.sketch.nodes.find((n) => n.id === "n7")! }]) };
    const after = keep(dropped, memo);
    expectKept(memo, after);
    expect(Object.values(after).some((p) => p.area === "steps" && p.index === n7.index)).toBe(false);
    memo = after;
    const step = MORE_NODES.find((n) => n.slot === "steps")!;
    const arrived = { ...dropped, sketch: applyOps(dropped.sketch, [{ op: "add", node: step }]) };
    const filled = keep(arrived, memo);
    expectKept(memo, filled);
    expect(filled[step.id]).toEqual(n7);
  });

  it("writes places through the view's `place`, and a re-render with more pieces never rewrites an old one", () => {
    const writes: [string, Place][] = [];
    let state: StageState = { ...stageBeats().find((b) => b.id === "shape-agreed")!.state, view: "orbit" };
    const place = (_v: string, id: string, p: Place) => {
      writes.push([id, p]);
      state = withPlace(state, "orbit", id, p);
    };
    const screen = render(<StageScreen state={state} dispatch={() => undefined} place={place} phase="idle" />);
    const first = Object.fromEntries(writes);
    expect(Object.keys(first).length).toBeGreaterThan(10);
    const grown: StageState = { ...state, draft: { ...state.draft!, sketch: applyOps(state.draft!.sketch, MORE_OPS) } };
    state = grown;
    screen.rerender(<StageScreen state={grown} dispatch={() => undefined} place={place} phase="idle" />);
    for (const [id, p] of writes) if (first[id]) expect(p, id).toEqual(first[id]);
    expect(writes.map(([id]) => id)).toEqual(expect.arrayContaining(MORE_NODES.map((n) => n.id).filter((id) => id !== "s14")));
  });
});

describe("zones", () => {
  const box: ZoneBox = { w: 252, h: 236, chipW: 180, chipH: 48, gap: 6, lineH: 29, lineGap: 3 };

  it("reads room from the measured size, not from the example's counts", () => {
    expect(gridFor(box, 3)).toEqual({ cols: 1, rows: 4, dense: false, capacity: 4 });
    expect(gridFor({ ...box, h: 400 }, 3).capacity).toBe(7);
    expect(gridFor({ ...box, w: 1248, h: 48 }, 0).cols).toBe(6);
    expect(gridFor(undefined, 30).capacity).toBe(Infinity);
  });

  it("switches to one-line chips past its room, then puts the rest behind +n more", () => {
    expect(gridFor(box, 4)).toMatchObject({ dense: true, rows: 7, capacity: 7 });
    const cells: [string, number][] = Array.from({ length: 9 }, (_, i) => [`p${i}`, i]);
    const split = splitZone(cells, gridFor(box, 8));
    expect(split.moreAt).toBe(6);
    expect(split.shown.map(([id]) => id)).toEqual(["p0", "p1", "p2", "p3", "p4", "p5"]);
    expect(split.more).toEqual(["p6", "p7", "p8"]);
    expect(splitZone(cells.slice(0, 7), gridFor(box, 6)).more).toEqual([]);
  });
});

describe("links and arcs", () => {
  const hub: Box = { x: 298, y: 165, w: 684, h: 528 };
  const ends: Record<Side, Box[]> = {
    top: [
      { x: 16, y: 86, w: 203, h: 48 },
      { x: 643, y: 86, w: 203, h: 48 },
      { x: 1061, y: 86, w: 203, h: 48 },
    ],
    left: [
      { x: 16, y: 210, w: 252, h: 48 },
      { x: 16, y: 620, w: 252, h: 48 },
    ],
    right: [
      { x: 1012, y: 210, w: 252, h: 48 },
      { x: 1012, y: 620, w: 252, h: 48 },
    ],
    bottom: [
      { x: 298, y: 744, w: 224, h: 40 },
      { x: 758, y: 744, w: 224, h: 40 },
    ],
  };

  it("routes every pair of zones round the card, never through it (the winner drew some straight across)", () => {
    const sides = Object.keys(ends) as Side[];
    for (const a of sides)
      for (const b of sides)
        for (const ba of ends[a])
          for (const bb of ends[b]) {
            if (ba === bb) continue;
            for (const k of [0, 3]) {
              const r = routeLink({ box: ba, side: a }, { box: bb, side: b }, hub, k, 3.4);
              expect(crosses(r.d, hub), `${a}->${b} ${r.d}`).toBe(false);
              expect(r.len).toBeGreaterThan(0);
            }
          }
  });

  it("goes round the nearer side", () => {
    const viaLeft = routeLink({ box: ends.top[0]!, side: "top" }, { box: ends.bottom[0]!, side: "bottom" }, hub, 0, 3.4);
    const viaRight = routeLink({ box: ends.top[2]!, side: "top" }, { box: ends.bottom[1]!, side: "bottom" }, hub, 0, 3.4);
    const xs = (d: string) => [...d.matchAll(/[MLQC](-?\d+(?:\.\d+)?)/g)].map((m) => Number(m[1]));
    expect(Math.min(...xs(viaLeft.d))).toBeLessThan(hub.x);
    expect(Math.max(...xs(viaRight.d))).toBeGreaterThan(hub.x + hub.w);
  });

  it("draws seven arcs round the card, one per place, and none for an unmeasured card", () => {
    const arcs = ringArcs(hub);
    expect(arcs.map((a) => a.slot)).toEqual(["need", "steps", "hand", "output", "never", "inputs", "apps"]);
    expect(arcs.find((a) => a.slot === "apps")!.side).toBe("left");
    expect(arcs.find((a) => a.slot === "hand")!.side).toBe("right");
    expect(ringArcs({ x: 0, y: 0, w: 0, h: 0 })).toEqual([]);
  });

  it("puts every zone on the side the brief names", () => {
    expect(SIDE_OF).toEqual({ steps: "top", apps: "left", inputs: "left", hand: "right", output: "right", never: "bottom" });
  });
});

describe("the Orbit view on the stage", () => {
  const beats = stageBeats();
  const at = (id: string, over: Partial<StageState> = {}): StageState => ({ ...beats.find((b) => b.id === id)!.state, view: "orbit", ...over });
  const show = (state: StageState) => {
    const dispatch = vi.fn<(a: StageAction) => void>();
    const r = render(<StageScreen state={state} dispatch={dispatch} place={() => undefined} phase={state.frame.phase} />);
    const view = r.container.querySelector<HTMLElement>('[data-stage-view="orbit"]')!;
    return { dispatch, view, r };
  };
  const q = (view: HTMLElement, sel: string) => view.querySelector<HTMLElement>(sel)!;

  it("frames the question card with six zones, colours each piece by whose idea it is, and draws the arcs from the draft's coverage", () => {
    const { view } = show(at("shape-1"));
    expect(view.querySelectorAll('[data-role="hub"]')).toHaveLength(1);
    expect([...view.querySelectorAll<HTMLElement>('[data-role="zone"]')].map((z) => z.dataset.zone)).toEqual([
      "steps",
      "apps",
      "inputs",
      "hand",
      "output",
      "never",
    ]);
    expect(q(view, '[data-role="chip"][data-node-id="n3"]').dataset).toMatchObject({ origin: "you", state: "ink" });
    expect(q(view, '[data-role="chip"][data-node-id="n2"]').dataset).toMatchObject({ origin: "athena", state: "pencil" });
    expect(q(view, '[data-role="hub"] [data-role="ask-text"]').textContent).toBe(STAGED.frames[0]!.draft.ask!.text);
    expect(within(view).getAllByText("Not known yet").length).toBeGreaterThan(0);
  });

  it("picks a suggestion", () => {
    const { view, dispatch } = show(at("shape-1"));
    fireEvent.click(view.querySelectorAll<HTMLElement>('[data-role="suggestion"]')[1]!);
    expect(dispatch).toHaveBeenCalledWith({ type: "pick", choice: STAGED.frames[0]!.draft.ask!.suggestions[1] });
  });

  it("says it in the person's own words", () => {
    const { view, dispatch } = show(at("shape-1"));
    const field = within(view).getByRole("textbox", { name: "Or say it your own way" });
    fireEvent.change(field, { target: { value: "Email in, I dispute on the portal" } });
    fireEvent.submit(field.closest("form")!);
    expect(dispatch).toHaveBeenCalledWith({ type: "say", text: "Email in, I dispute on the portal" });
  });

  it("inks a pencil piece from its chip, and every pencil piece at once", () => {
    const { view, dispatch } = show(at("shape-1"));
    fireEvent.click(q(view, '[data-node-id="n2"] .ob-chip__ink'));
    expect(dispatch).toHaveBeenCalledWith({ type: "ink", node_ids: ["n2"] });
    fireEvent.click(within(view).getByRole("button", { name: /Ink all her pencil marks \(2\)/ }));
    expect(dispatch).toHaveBeenCalledWith({ type: "ink", node_ids: ["n2", "n4"] });
    expect(q(view, '[data-node-id="n3"]').querySelector(".ob-chip__ink")).toBeNull(); // the person's own words are ink already
  });

  it("opens a piece's card and rubs a guess out from it", () => {
    const { view, dispatch } = show(at("shape-1", { card: "n4" }));
    fireEvent.click(q(view, '[data-node-id="n4"] .ob-chip__body'));
    expect(dispatch).toHaveBeenCalledWith({ type: "close_card" });
    fireEvent.click(q(view, '[data-role="piece-card"] [data-role="drop"]'));
    expect(dispatch).toHaveBeenCalledWith({ type: "drop", node_ids: ["n4"] });
    fireEvent.click(q(view, '[data-role="piece-card"] [data-role="ink"]'));
    expect(dispatch).toHaveBeenCalledWith({ type: "ink", node_ids: ["n4"] });
  });

  it("hides a piece being rubbed out and keeps its cell empty", () => {
    const { view } = show(at("shape-1", { dropping: ["n4"] }));
    expect(view.querySelector('[data-node-id="n4"]')).toBeNull();
    expect(view.querySelectorAll('[data-zone="steps"] [data-role="chip"]')).toHaveLength(0);
  });

  it("writes it: \"That's enough, write it\" from the first frame", () => {
    const { view, dispatch } = show(at("shape-1"));
    fireEvent.click(q(view, '[data-role="exit"]'));
    expect(dispatch).toHaveBeenCalledWith({ type: "enough" });
  });

  it("deals the check step one card at a time with yes and no, then the missed and never lines", () => {
    const ready = at("preview-ready");
    const { view, dispatch, r } = show(ready);
    const cards = view.querySelectorAll('[data-role="check-card"]');
    expect(cards).toHaveLength(5);
    expect(view.querySelectorAll(".ob-deck__slot[data-front]")).toHaveLength(1);
    const front = q(view, ".ob-deck__slot[data-front]");
    fireEvent.click(q(front, '[data-role="mark-yes"]'));
    expect(dispatch).toHaveBeenCalledWith({ type: "mark", expected_id: "e1", mark: "yes" });
    fireEvent.click(q(front, '[data-role="mark-no"]'));
    expect(dispatch).toHaveBeenCalledWith({ type: "mark", expected_id: "e1", mark: "no" });
    // a yes deals the next card
    r.rerender(<StageScreen state={{ ...ready, marks: { e1: { mark: "yes" } } }} dispatch={dispatch} place={() => undefined} phase="idle" />);
    expect(q(view, ".ob-deck__slot[data-front] [data-role='check-card']").dataset.expectedId).toBe("e2");
    expect(view.querySelector('[data-role="missed"]')).toBeNull();

    const marked = at("preview-marked");
    const done = show(marked);
    expect(done.view.querySelector('[data-role="missed"]')).toBeTruthy();
    expect(done.view.querySelector('[data-role="never-line"]')).toBeTruthy();
    fireEvent.click(q(done.view, '[data-role="run-test"]'));
    expect(done.dispatch).toHaveBeenCalledWith({ type: "send_key" });
  });

  it("marks with Y and N from the stage's keymap on the card in front", () => {
    const { dispatch } = show(at("preview-ready"));
    fireEvent.keyDown(document.activeElement ?? window, { key: "y" });
    expect(dispatch).toHaveBeenCalledWith({ type: "mark", expected_id: "e1", mark: "yes" });
  });

  it("shows the test run's phases and filed cards in the card, never signable", () => {
    const { view } = show(at("rehearse-running"));
    expect(view.querySelector('[data-role="phases"]')).toBeTruthy();
    expect(view.querySelectorAll('[data-role="filed"] li')).toHaveLength(1);
    expect(view.dataset.context).toBe("true");
  });

  it("says \"Not quite\" with a note, or keeps it", () => {
    const { view, dispatch } = show(at("verdict-short"));
    expect(q(view, '[data-role="score"]').dataset.short).toBe("true");
    fireEvent.click(q(view, '[data-role="keep"]'));
    expect(dispatch).toHaveBeenCalledWith({ type: "verdict", verdict: "keep" });
    fireEvent.click(q(view, '[data-role="revise"]'));
    fireEvent.change(within(view).getByRole("textbox", { name: "What is not right? (optional)" }), { target: { value: "She missed the late fee" } });
    fireEvent.click(q(view, '[data-role="revise"]'));
    expect(dispatch).toHaveBeenCalledWith({ type: "verdict", verdict: "revise", note: "She missed the late fee" });
  });

  it("hands off to the Project when kept", () => {
    const { view } = show(at("saved"));
    expect(view.querySelector('[data-role="saved"]')).toBeTruthy();
  });

  it("brings the person back to the sketch after \"Not quite\" and after a chore that could not be written", () => {
    expect(q(show(at("shape-revisit")).view, '[data-role="revisit"]').dataset.why).toBe("revise");
    cleanup();
    expect(q(show(at("author-failed")).view, '[data-role="revisit"]').dataset.why).toBe("unwritten");
  });

  it("retries a failed reply", () => {
    const { view, dispatch } = show(at("shape-failed"));
    fireEvent.click(q(view, '[data-role="retry"]'));
    expect(dispatch).toHaveBeenCalledWith({ type: "retry" });
  });

  it("choreographs a reply: phrases light, then pieces land in turn, the person's first", () => {
    const { view } = show(at("shape-1"));
    expect(q(view, ".ob-quote").dataset.arriving).toBe("true");
    const landing = [...view.querySelectorAll<HTMLElement>('[data-role="chip"][data-arriving]')].map((c) => [
      c.dataset.nodeId,
      c.style.getPropertyValue("--ob-delay"),
    ]);
    // three phrases light at 380 ms + 460 ms each, fly for 720 ms, then the pieces land 110 ms apart
    expect(landing).toEqual(
      expect.arrayContaining([
        ["n3", "2480ms"],
        ["n5", "2590ms"],
        ["n2", "2700ms"],
        ["n4", "2810ms"],
      ]),
    );
  });

  it("does not replay an arrival once the next reply starts", () => {
    const base = at("shape-1");
    const started = reduce(base, { type: "start", turn_id: "t", engine: "scripted", simulated: true });
    const { view } = show(started);
    expect(view.querySelectorAll("[data-arriving]")).toHaveLength(0);
  });
});

describe("the 36-piece fixture", () => {
  it("is the staged 23 plus 13 more", () => {
    const final = STAGED.frames.at(-1)!.confirm!.draft;
    const ops: SketchOp[] = [...MORE_OPS];
    const grown = applyOps(final.sketch, ops);
    expect(final.sketch.nodes).toHaveLength(23);
    expect(grown.nodes).toHaveLength(36);
    expect(initialStage().places.orbit).toEqual({});
  });
});
