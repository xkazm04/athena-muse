// The Drawing view draws the props and sends actions: every named interaction is a `dispatch` with
// the action the store expects, and a piece's place goes to the store once and is never rewritten.
import { cleanup, fireEvent, render, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { STAGED } from "../fixture/staged";
import { applyLocal, initialStage, reduce, withPlace } from "../store";
import type { Place, StageAction, StageState } from "../types";
import { STAGE_WORDS } from "../words";
import { DrawingView } from "./DrawingView";
import { withStress } from "./stress";

vi.mock("../../../lib/api");
vi.mock("../../../lib/windows");

afterEach(cleanup);

const words = STAGE_WORDS;
/** The first reply, folded through the store as the daemon streams it. */
const firstFrame = (): StageState => STAGED.frames[0]!.events.reduce(reduce, { ...initialStage(), draft: STAGED.created });
const at = (state: Partial<StageState>): StageState => ({ ...initialStage(), ...state });

function draw(state: StageState) {
  const dispatch = vi.fn<(a: StageAction) => void>();
  const place = vi.fn<(view: "drawing" | "orbit", id: string, p: Place) => void>();
  const view = render(<DrawingView draft={state.draft!} frame={state.frame} state={state} dispatch={dispatch} words={words} place={place} />);
  const root = view.container.querySelector<HTMLElement>('[data-stage-view="drawing"]')!;
  return { dispatch, place, root, view };
}

const piece = (root: HTMLElement, id: string) => root.querySelector<HTMLElement>(`[data-role="piece"][data-node-id="${id}"]`)!;

describe("the Drawing view", () => {
  it("draws the first reply: five territories, the fence, the sentence, pencil and ink, the pinned question", () => {
    const { root } = draw(firstFrame());
    expect(root.querySelectorAll('[data-role="lane"]')).toHaveLength(5);
    expect(root.querySelector('[data-role="never-fence"]')).toBeTruthy();
    expect(root.querySelector('[data-role="need"]')).toBeTruthy();
    expect(piece(root, "n2").dataset.state).toBe("pencil");
    expect(piece(root, "n3").dataset.origin).toBe("you");
    expect(piece(root, "n1")).toBeNull(); // the person's sentence is on top, not a piece
    expect(root.querySelector('[data-role="note"] [data-role="ask-text"]')?.textContent).toBe(STAGED.frames[0]!.draft.ask?.text);
    expect(root.querySelector('[data-role="lane"][data-slot="apps"]')?.getAttribute("data-asking")).toBe("true");
  });

  it("gives each new piece its place once, through the store, and never again", () => {
    const state = firstFrame();
    const { place, view } = draw(state);
    const given = place.mock.calls.map(([v, id, p]) => [v, id, p.area] as const);
    expect(given).toEqual([
      ["drawing", "n2", "apps"],
      ["drawing", "n3", "apps"],
      ["drawing", "n4", "steps"],
      ["drawing", "n5", "output"],
    ]);
    // the store keeps them; drawn again with the memo, nothing is placed again
    let kept = state;
    for (const [v, id, p] of place.mock.calls) kept = withPlace(kept, v, id, p);
    place.mockClear();
    view.rerender(<DrawingView draft={kept.draft!} frame={kept.frame} state={kept} dispatch={vi.fn()} words={words} place={place} />);
    expect(place).not.toHaveBeenCalled();
    // a 36-piece sketch places only the new pieces, and the drawn ones keep their rows
    const big = { ...kept, draft: withStress(kept.draft!) };
    view.rerender(<DrawingView draft={big.draft} frame={big.frame} state={big} dispatch={vi.fn()} words={words} place={place} />);
    const ids = place.mock.calls.map(([, id]) => id);
    expect(ids).not.toContain("n2");
    expect(ids).toContain("s13");
  });

  it("picks a suggestion, says it its own way, and says that's enough", () => {
    const state = firstFrame();
    const { dispatch, root } = draw(state);
    const ask = state.frame.ask!;
    fireEvent.click(within(root).getAllByRole("button", { name: new RegExp(ask.suggestions[0]!.slice(0, 12)) })[0]!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "pick", choice: ask.suggestions[0] });
    fireEvent.change(within(root).getByRole("textbox", { name: words.ownWords }), { target: { value: "By email" } });
    fireEvent.submit(root.querySelector('[data-role="composer"]')!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "say", text: "By email" });
    fireEvent.click(root.querySelector('[data-role="exit"]')!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "enough" });
  });

  it("inks a pencil piece from its mark, opens a piece's card, and rubs one out from the card", () => {
    const state = firstFrame();
    const { dispatch, root, view } = draw(state);
    fireEvent.click(piece(root, "n2").querySelector('[data-role="piece-ink"]')!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "ink", node_ids: ["n2"] });
    expect(piece(root, "n3").querySelector('[data-role="piece-ink"]')).toBeNull(); // the person's own words
    fireEvent.click(piece(root, "n4").querySelector("button")!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "open_card", node_id: "n4" });

    const open = applyLocal(state, { type: "open_card", node_id: "n4" });
    view.rerender(<DrawingView draft={open.draft!} frame={open.frame} state={open} dispatch={dispatch} words={words} place={vi.fn()} />);
    const card = piece(root, "n4").querySelector<HTMLElement>('[data-role="piece-card"]')!;
    fireEvent.click(within(card).getByRole("button", { name: words.dropIt }));
    expect(dispatch).toHaveBeenLastCalledWith({ type: "drop", node_ids: ["n4"] });
    fireEvent.click(within(card).getByRole("button", { name: words.inkIt }));
    expect(dispatch).toHaveBeenLastCalledWith({ type: "ink", node_ids: ["n4"] });
    fireEvent.click(within(root).getByRole("button", { name: /Ink them all/ }));
    expect(dispatch).toHaveBeenLastCalledWith({ type: "ink", node_ids: ["n2", "n4"] });
  });

  it("hides a piece while it is being rubbed out, and keeps its place for the undo", () => {
    const state = { ...firstFrame(), dropping: ["n4"] };
    const { root, place } = draw(state);
    expect(piece(root, "n4")).toBeNull();
    expect(place.mock.calls.map(([, id]) => id)).toContain("n4");
  });

  it("shows the reply's notice while she thinks, and offers the question again after a failure", () => {
    const thinking = reduce({ ...firstFrame(), work: "say", frame: { ...firstFrame().frame, youSaid: "By email" } }, STAGED.frames[1]!.events[0]!);
    const { root, view, dispatch } = draw(thinking);
    expect(root.querySelector('[data-role="note"]')?.getAttribute("data-mode")).toBe("thinking");
    expect(root.querySelector('[data-role="echo"]')?.textContent).toContain("By email");
    const failed = { ...reduce(thinking, { type: "error", error: "engine_unavailable", reason: "Muse did not answer." }), startedAt: 7 };
    view.rerender(<DrawingView draft={failed.draft!} frame={failed.frame} state={failed} dispatch={dispatch} words={words} place={vi.fn()} />);
    fireEvent.click(root.querySelector('[data-role="retry"]')!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "retry" });
    fireEvent.click(within(root).getByRole("button", { name: words.sayDifferently }));
    expect((within(root).getByRole("textbox", { name: words.ownWords }) as HTMLInputElement).value).toBe("By email");
  });

  it("marks yes and no in the check drawer, adds lines, and runs the test once every card is marked", () => {
    let state = reduce(at({ draft: STAGED.written }), { type: "expected", expected: STAGED.preview.expected });
    const { dispatch, root, view } = draw(state);
    const drawer = root.querySelector<HTMLElement>('[data-role="drawer"][data-step="preview"]')!;
    const cards = drawer.querySelectorAll<HTMLElement>('[data-role="check-card"]');
    expect(cards).toHaveLength(STAGED.preview.expected.length);
    fireEvent.click(cards[0]!.querySelector('[data-role="mark-yes"]')!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "mark", expected_id: "e1", mark: "yes" });
    fireEvent.click(cards[1]!.querySelector('[data-role="mark-no"]')!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "mark", expected_id: "e2", mark: "no" });
    expect((drawer.querySelector('[data-role="run-test"]') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(drawer).getByRole("textbox", { name: words.never }), { target: { value: "Never pay" } });
    fireEvent.submit(drawer.querySelector('[data-role="never-line"] form')!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "add_never", text: "Never pay" });

    for (const m of STAGED.key.marks) state = applyLocal(state, { type: "mark", expected_id: m.expected_id, mark: m.mark, note: m.note });
    view.rerender(<DrawingView draft={state.draft!} frame={state.frame} state={state} dispatch={dispatch} words={words} place={vi.fn()} />);
    fireEvent.click(root.querySelector('[data-role="run-test"]')!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "send_key" });
    fireEvent.click(within(root).getByRole("button", { name: /Back to the sketch/ }));
    expect(dispatch).toHaveBeenLastCalledWith({ type: "verdict", verdict: "revise" });
  });

  it("asks for the cards from the written strip, and shows the test run in the strip", () => {
    const written = at({ draft: STAGED.written });
    const { dispatch, root, view } = draw(written);
    expect(root.querySelector('[data-role="strip"][data-step="written"]')).toBeTruthy();
    expect(root.querySelectorAll('[data-role="practice-tile"]')).toHaveLength(STAGED.written.practice!.length);
    fireEvent.click(within(root).getByRole("button", { name: words.showCards }));
    expect(dispatch).toHaveBeenLastCalledWith({ type: "preview" });

    let run = at({ draft: { ...STAGED.keyed, step: "rehearse" }, work: "rehearse" });
    for (const t of STAGED.rehearsal.slice(0, 5)) run = reduce(run, t.event);
    view.rerender(<DrawingView draft={run.draft!} frame={run.frame} state={run} dispatch={dispatch} words={words} place={vi.fn()} />);
    expect(root.querySelector('[data-role="strip"][data-step="rehearse"] [data-role="phases"]')).toBeTruthy();
    expect(root.querySelector('[data-role="filed"]')).toBeTruthy();
    expect(root.querySelector('[data-role="filed"] button')).toBeNull(); // shown, never signable
    expect(root.getAttribute("data-run")).toBe("true");
  });

  it("keeps the chore, or says not quite with a note, from the verdict drawer", () => {
    let state = at({ draft: { ...STAGED.keyed, step: "rehearse" } });
    for (const t of STAGED.rehearsal) state = reduce(state, t.event);
    const { dispatch, root } = draw(state);
    const drawer = root.querySelector<HTMLElement>('[data-role="drawer"][data-step="verdict"]')!;
    expect(drawer.querySelector('[data-role="score"]')).toBeTruthy();
    fireEvent.click(drawer.querySelector('[data-role="keep"]')!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "verdict", verdict: "keep" });
    fireEvent.click(drawer.querySelector('[data-role="revise"]')!);
    fireEvent.change(within(drawer).getByRole("textbox"), { target: { value: "She missed the late fee" } });
    fireEvent.submit(drawer.querySelector(".sp-verdict__note")!);
    expect(dispatch).toHaveBeenLastCalledWith({ type: "verdict", verdict: "revise", note: "She missed the late fee" });
  });

  it("brings the person back to the sketch with the gaps named after not quite, and hands off once kept", () => {
    const { root, view } = draw(at({ draft: STAGED.revised }));
    expect(root.querySelector('[data-role="revisit"][data-why="revise"]')?.textContent).toContain(STAGED.revised.note!);
    view.rerender(
      <DrawingView draft={STAGED.saved} frame={initialStage().frame} state={at({ draft: STAGED.saved })} dispatch={vi.fn()} words={words} place={vi.fn()} />,
    );
    expect(root.querySelector('[data-role="saved"]')).toBeTruthy();
  });
});
