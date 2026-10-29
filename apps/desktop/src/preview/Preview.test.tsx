import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Preview } from "./Preview";
import { STATES_MD, stageBeats } from "./stageBeats";

vi.mock("../theme/Backdrop", () => ({ Backdrop: () => null }));

afterEach(cleanup);

describe("preview", () => {
  it("renders the chores section on fixture data, labelled as such, in each state", () => {
    render(<Preview />);
    const section = screen.getByRole("heading", { name: /Chores \(fixture data/ }).closest("section")!;
    const scene = within(section);
    expect(scene.getByText("Proven on Meta")).toBeTruthy();
    expect(scene.getByRole("heading", { name: "Proofs" })).toBeTruthy();
    fireEvent.click(scene.getByRole("button", { name: /Remodel changes/ }));
    expect(scene.getByText("python -m athena.bench renovation-witness")).toBeTruthy();
    fireEvent.click(scene.getByRole("button", { name: "empty" }));
    expect(scene.getByText("No chores yet.")).toBeTruthy();
    fireEvent.click(scene.getByRole("button", { name: "problem" }));
    expect(scene.getByRole("alert")).toBeTruthy();
    fireEvent.click(scene.getByRole("button", { name: "Try again" }));
    expect(scene.queryByRole("alert")).toBeNull();
  });

  it("drives every state the stage must show from the staged streams, with no daemon, in both views", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    render(<Preview />);
    const section = screen.getByRole("heading", { name: /Stage \(invented example/ }).closest("section")!;
    const scene = within(section);
    const pick = scene.getByRole("combobox", { name: "Go to a state" });
    const ids = new Set(stageBeats().map((b) => b.id));
    const has = (sel: string) => section.querySelectorAll(sel).length;
    const expectations: Record<string, string> = {
      "describe-empty": '[data-role="describe"]',
      "describe-sending": '[data-role="describe"][data-sending="true"]',
      "shape-thinking": '[data-role="notice"][data-phase="thinking"]',
      "shape-slow": '[data-role="notice"][data-phase="slow"]',
      "shape-failed": '[data-role="notice"][data-phase="failed"] [data-role="retry"]',
      "shape-proposal": '[data-role="piece-card"] [data-role="ink"]',
      "shape-agreed": '[data-role="exit"][data-ready="true"]',
      "author-writing": '[data-role="progress"]',
      "author-repair": '[data-role="problems"][data-tone="repair"]',
      "author-failed": '[data-role="revisit"][data-why="unwritten"]',
      "preview-ready": '[data-role="check-card"]',
      "preview-marked": '[data-role="missed"] li',
      "rehearse-running": '[data-role="filed"] li',
      "verdict-short": '[data-role="score"][data-short="true"]',
      saved: '[data-role="saved"]',
    };
    for (const row of STATES_MD) {
      expect(ids.has(row.beat), row.state).toBe(true);
      fireEvent.change(pick, { target: { value: row.beat } });
      expect(has(`[data-beat="${row.beat}"]`), row.state).toBe(1);
      const sel = expectations[row.beat];
      if (sel) expect(has(sel), `${row.state}: ${sel}`).toBeGreaterThan(0);
      expect(has('[data-role="invented"]')).toBe(1);
    }
    fireEvent.change(pick, { target: { value: "preview-ready" } });
    expect(has('[data-role="check-card"]')).toBe(5);
    fireEvent.change(pick, { target: { value: "shape-agreed" } });
    expect(has('[data-stage-view="drawing"]')).toBe(1);
    fireEvent.click(scene.getByRole("tab", { name: "Orbit" }));
    expect(has('[data-stage-view="orbit"]')).toBe(1);
    expect(has('[data-stage-view="drawing"]')).toBe(0);
    expect(fetchSpy).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
