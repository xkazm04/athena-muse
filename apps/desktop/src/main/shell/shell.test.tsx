import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import type { SpaceSummary } from "../../lib/contract";
import * as windows from "../../lib/windows";
import { Shell } from "../App";
import { parseHash, toHash, type Route } from "../route";
import { resetMain, useMain } from "../store";
import { depthOf, trailOf } from "./Depth";
import { ASK_AWAY } from "./Surface";

vi.mock("../../lib/api");
vi.mock("../../lib/windows");
vi.mock("../../theme/Backdrop", () => ({ Backdrop: () => null }));
vi.mock("../../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/daemon")>()),
  subscribe: vi.fn(() => () => undefined),
}));

const space = (id: string, name: string): SpaceSummary => ({
  id, name, brief: "", apps: [], hue: 120, created: "", updated: "", counts: { episodes: 0, facts: 0 },
});

async function start(route: Route) {
  window.location.hash = toHash(route);
  useMain.setState({ route });
  await act(async () => {
    render(<Shell />);
  });
}

beforeEach(() => {
  resetMain();
  vi.mocked(api.chores).mockResolvedValue([]);
  vi.mocked(api.twins).mockResolvedValue({ twins: [], week: { sent: 0, held: 0, cost_usd: 0 } } as never);
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("routes and depth", () => {
  it("lands on the surface when the address is empty, and #home round-trips", () => {
    expect(parseHash("")).toEqual({ view: "home" });
    expect(parseHash("#")).toEqual({ view: "home" });
    expect(toHash(parseHash("#home"))).toBe("#home");
  });

  it("measures depth: surface 0, a place 1, one thing in it 2, a page under that 3", () => {
    expect(depthOf({ view: "home" })).toBe(0);
    expect(depthOf({ view: "chores" })).toBe(1);
    expect(depthOf({ view: "settings", item: null })).toBe(1);
    expect(depthOf({ view: "chore", id: "c" })).toBe(2);
    expect(depthOf({ view: "stage", id: null })).toBe(2);
    expect(depthOf({ view: "memory", id: "spc_a" })).toBe(3);
    expect(depthOf({ view: "twin_draft", id: "t", draft: "d" })).toBe(3);
  });

  it("names the trail down to where you are", () => {
    const names = { space: () => "Taxes", chore: () => "A parent's care", twin: () => "Office twin" };
    expect(trailOf({ view: "home" }, names)).toEqual([]);
    expect(trailOf({ view: "memory", id: "spc_a" }, names).map((c) => c.label)).toEqual(["Projects", "Taxes", "Memory"]);
    expect(trailOf({ view: "chore", id: "care-circle" }, names).map((c) => c.label)).toEqual(["Chores", "A parent's care"]);
    expect(trailOf({ view: "twin_voice", id: "t" }, names).map((c) => c.label)).toEqual(["Twins", "Office twin", "Its voice"]);
  });
});

describe("the frame", () => {
  it("a place has the bar, the rail and the dock; the dock marks it and rises to the surface", async () => {
    await start({ view: "chores" });
    const bar = screen.getByRole("banner");
    expect(within(bar).getByText("Chores").getAttribute("aria-current")).toBe("location");
    const dock = screen.getByRole("navigation", { name: "Main" });
    expect(within(dock).getByRole("link", { name: "Chores" }).getAttribute("aria-current")).toBe("page");
    expect(document.querySelector(".m-rail")?.getAttribute("data-depth")).toBe("1");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Rise to Athena" })));
    expect(useMain.getState().route).toEqual({ view: "home" });
  });

  it("one level down rises to its place, and her pill opens her window", async () => {
    useMain.setState({ spaces: [space("spc_a", "Taxes")] });
    vi.mocked(api.memory).mockResolvedValue({ rows: [], showing: 0, total: 0 });
    vi.mocked(api.spaceSites).mockResolvedValue([]);
    await start({ view: "project", id: "spc_a" });
    expect(document.querySelector(".m-rail")?.getAttribute("data-depth")).toBe("2");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Rise to Projects" })));
    expect(useMain.getState().route).toEqual({ view: "projects" });
    fireEvent.click(screen.getByRole("button", { name: "Talk to Athena" }));
    expect(windows.toggleAthena).toHaveBeenCalled();
  });
});

describe("the surface", () => {
  it("shows her state, a tile per place with its live line, and no dock", async () => {
    useMain.setState({ spaces: [space("spc_a", "Taxes")], spacesLoad: "ready" });
    await start({ view: "home" });
    expect(screen.getByRole("heading", { name: "Athena is resting" })).toBeTruthy();
    const tiles = screen.getByRole("list", { name: "Depths" });
    expect(within(tiles).getAllByRole("link").map((a) => a.getAttribute("aria-label"))).toEqual([
      "Projects, 1 project",
      "Chores, none yet",
      "Twins, none yet",
      "Athena, nothing waits on you",
      "Settings, checking the engine",
    ]);
    expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull();
    await act(async () => fireEvent.click(within(tiles).getByRole("link", { name: /^Chores/ })));
    expect(useMain.getState().route).toEqual({ view: "chores" });
  });

  it("something waiting turns her to the person's colour and marks the Athena tile", async () => {
    useMain.setState({
      waiting: [{ id: "card_1", space_id: "", action: "propose_brief", label: "x", args: {}, state: "waiting", created: "" }],
    });
    await start({ view: "home" });
    expect(screen.getByRole("heading", { name: "1 thing waits on you" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Athena, 1 waiting on you" }).getAttribute("data-attention")).toBe("true");
    expect(document.querySelector(".m-surface__seal .seal")?.getAttribute("data-state")).toBe("waiting");
  });

  it("hands the ask to her window, and says so when there is no window to hand it to", async () => {
    vi.mocked(windows.handToAthena).mockResolvedValueOnce(true);
    await start({ view: "home" });
    const input = screen.getByLabelText("Ask her");
    fireEvent.change(input, { target: { value: "  Appeal the denial  " } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Hand it to her" })));
    expect(windows.handToAthena).toHaveBeenCalledWith("Appeal the denial");
    expect((input as HTMLInputElement).value).toBe("");

    vi.mocked(windows.handToAthena).mockResolvedValueOnce(false);
    fireEvent.change(input, { target: { value: "Again" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Hand it to her" })));
    expect(screen.getByText(ASK_AWAY)).toBeTruthy();
    expect((input as HTMLInputElement).value).toBe("Again");
  });
});
