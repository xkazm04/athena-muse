import { afterEach, describe, expect, it } from "vitest";
import { STAGED } from "./fixture/staged";
import { DEFAULT_VIEW, VIEW_KEY, initialStage, readView, useStage } from "./store";
import { VIEWS } from "./views";

describe("the stage's contract stubs", () => {
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
    const last = STAGED.frames.at(-1);
    if (!last) throw new Error("the fixture has no frames");
    const agreed = last.confirm?.draft ?? last.draft;
    expect(agreed.agreed).toBe(true);
    expect(agreed.sketch.nodes.length).toBeGreaterThan(20);
    expect(STAGED.rehearsal.at(-1)?.event.type).toBe("scored");
    expect(STAGED.saved.step).toBe("saved");
  });
});
