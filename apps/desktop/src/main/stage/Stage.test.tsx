import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import type { Draft } from "../../lib/contract";
import { resetMain, useMain } from "../store";
import { STAGED } from "./fixture/staged";
import { composingEnter, keyFor, type KeyContext } from "./keymap";
import { StageScreen, Stage } from "./Stage";
import { applyLocal, initialStage, reduce, useStage } from "./store";
import type { StageAction, StageState } from "./types";

vi.mock("../../lib/api");
vi.mock("../../lib/windows");

const at = (draft: Draft): StageState => ({ ...initialStage(), draft });
const asking = (): StageState => STAGED.frames[1]!.events.reduce(reduce, at(STAGED.frames[0]!.draft));
const input = document.createElement("input");
const ctx = (over: Partial<KeyContext> = {}): KeyContext => ({ step: "shape", asking: true, suggestions: 3, ...over });

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("the keymap", () => {
  it("picks 1 to 4 only while a question is open, and only as many as there are", () => {
    expect(keyFor({ key: "2", target: document.body }, ctx())).toEqual({ type: "pick", index: 1 });
    expect(keyFor({ key: "4", target: document.body }, ctx())).toBeNull();
    expect(keyFor({ key: "1", target: document.body }, ctx({ asking: false }))).toBeNull();
  });

  it("is ignored while typing, except Escape; modifiers are never the stage's", () => {
    expect(keyFor({ key: "1", target: input }, ctx())).toBeNull();
    expect(keyFor({ key: "i", target: input }, ctx())).toBeNull();
    expect(keyFor({ key: "Escape", target: input }, ctx())).toEqual({ type: "close" });
    expect(keyFor({ key: "1", ctrlKey: true, target: document.body }, ctx())).toBeNull();
  });

  it("inks and rubs out in the sketch, marks and moves in the check step", () => {
    expect(keyFor({ key: "i", target: document.body }, ctx())).toEqual({ type: "ink" });
    expect(keyFor({ key: "Delete", target: document.body }, ctx())).toEqual({ type: "drop" });
    expect(keyFor({ key: "y", target: document.body }, ctx({ step: "preview" }))).toEqual({ type: "mark", mark: "yes" });
    expect(keyFor({ key: "N", target: document.body }, ctx({ step: "preview" }))).toEqual({ type: "mark", mark: "no" });
    expect(keyFor({ key: "ArrowDown", target: document.body }, ctx({ step: "preview" }))).toEqual({ type: "move", by: 1 });
    expect(keyFor({ key: "y", target: document.body }, ctx())).toBeNull();
  });

  it("never lets Enter that ends a composition send", () => {
    expect(composingEnter({ key: "Enter", isComposing: true, target: input })).toBe(true);
    expect(composingEnter({ key: "Enter", keyCode: 229, target: input })).toBe(true);
    expect(composingEnter({ key: "Enter", target: input })).toBe(false);
  });
});

describe("the stage's frame", () => {
  const screenOn = (state: StageState) => {
    const dispatch = vi.fn<(a: StageAction) => void>();
    render(<StageScreen state={state} dispatch={dispatch} place={() => undefined} phase={state.frame.phase} />);
    return dispatch;
  };

  it("mounts only the chosen view, with the rail on the draft's step", () => {
    screenOn({ ...asking(), view: "orbit" });
    expect(document.querySelectorAll("[data-stage-view]")).toHaveLength(1);
    expect(document.querySelector('[data-stage-view="orbit"]')).toBeTruthy();
    expect(document.querySelector('[data-role="rail"] [aria-current="step"]')?.getAttribute("data-step")).toBe("shape");
    expect(screen.getByRole("tab", { name: "Orbit" }).getAttribute("aria-selected")).toBe("true");
  });

  it("switches the view from the tab", () => {
    const dispatch = screenOn(asking());
    fireEvent.click(screen.getByRole("tab", { name: "Orbit" }));
    expect(dispatch).toHaveBeenCalledWith({ type: "switch_view", view: "orbit" });
  });

  it("picks a suggestion with its number, inks the focused guess with i, closes the card with Escape", () => {
    const state = { ...asking(), card: "n4" };
    const dispatch = screenOn(state);
    fireEvent.keyDown(window, { key: "2" });
    expect(dispatch).toHaveBeenLastCalledWith({ type: "pick", choice: state.frame.ask!.suggestions[1] });
    const piece = document.createElement("button");
    piece.dataset.nodeId = "n7";
    document.body.append(piece);
    piece.focus();
    fireEvent.keyDown(piece, { key: "i" });
    expect(dispatch).toHaveBeenLastCalledWith({ type: "ink", node_ids: ["n7"] });
    fireEvent.keyDown(piece, { key: "Delete" });
    expect(dispatch).toHaveBeenLastCalledWith({ type: "drop", node_ids: ["n7"] });
    piece.dataset.nodeId = "n1"; // the person's own words: nothing to ink or rub out
    dispatch.mockClear();
    fireEvent.keyDown(piece, { key: "i" });
    expect(dispatch).not.toHaveBeenCalled();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(dispatch).toHaveBeenLastCalledWith({ type: "close_card" });
    piece.remove();
  });

  it("marks the first unmarked card with Y and N in the check step", () => {
    let state = reduce(at(STAGED.written), { type: "expected", expected: STAGED.preview.expected });
    state = applyLocal(state, { type: "mark", expected_id: "e1", mark: "yes" });
    const dispatch = screenOn(state);
    fireEvent.keyDown(window, { key: "n" });
    expect(dispatch).toHaveBeenLastCalledWith({ type: "mark", expected_id: "e2", mark: "no" });
  });

  it("shows the undo toast while a guess is being rubbed out", () => {
    const dispatch = screenOn({ ...asking(), dropping: ["n4"] });
    expect(screen.getByRole("status").textContent).toContain("Compare billed days with attended days");
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(dispatch).toHaveBeenCalledWith({ type: "undo_drop" });
  });

  it("asks for the need before there is a draft", () => {
    const dispatch = screenOn(initialStage());
    fireEvent.change(screen.getByRole("textbox", { name: /Describe the chore/ }), { target: { value: "My need" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(dispatch).toHaveBeenCalledWith({ type: "describe", need: "My need" });
  });
});

describe("the stage on the app's store", () => {
  beforeEach(() => {
    resetMain();
    useStage.setState(initialStage());
  });

  it("describes from #stage/new, then follows the new draft to its own address", async () => {
    vi.mocked(api.createDraft).mockResolvedValue(STAGED.created);
    vi.mocked(api.draftSay).mockImplementation(async (_id, _body, on) => {
      for (const e of STAGED.frames[0]!.events) on(e);
    });
    await act(async () => {
      render(<Stage id={null} />);
    });
    fireEvent.change(screen.getByRole("textbox", { name: /Describe the chore/ }), { target: { value: STAGED.need } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Send" }));
    });
    expect(api.createDraft).toHaveBeenCalledWith(STAGED.need);
    expect(vi.mocked(api.draftSay).mock.calls[0]![1]).toEqual({ text: "", view: useStage.getState().view });
    expect(useMain.getState().route).toEqual({ view: "stage", id: STAGED.created.id });
    expect(useStage.getState().draft?.step).toBe("shape");
  });

  it("opens a draft by its address and offers a retry when it cannot be read", async () => {
    vi.mocked(api.getDraft).mockRejectedValueOnce(new Error("down")).mockResolvedValueOnce(STAGED.frames[2]!.draft);
    await act(async () => {
      render(<Stage id="drf_00000000c1b0" />);
    });
    expect(useStage.getState().frame.phase).toBe("failed");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    });
    expect(api.getDraft).toHaveBeenCalledTimes(2);
    expect(useStage.getState().draft?.id).toBe("drf_00000000c1b0");
  });
});
