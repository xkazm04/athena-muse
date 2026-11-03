import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import type { AppEvent, Card, Draft, EngineStatus, LedgerPage, SpaceSummary } from "../lib/contract";
import * as daemon from "../lib/daemon";
import { DaemonError } from "../lib/daemon";
import { money } from "./athena/CostsPage";
import { App } from "./App";
import { SKIP_KEY } from "./onboarding/FirstRun";
import { parseHash, toHash } from "./route";
import { resetHer } from "../athena/store";
import { resetMain, useMain } from "./store";

vi.mock("../lib/api");
vi.mock("../lib/windows");
vi.mock("../theme/Backdrop", () => ({ Backdrop: () => null }));
vi.mock("../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/daemon")>()),
  getConnection: vi.fn(),
  subscribe: vi.fn(),
}));

const muse: EngineStatus = { engine: "muse", model: "muse-spark", key: "file", simulated: false };
const noKey: EngineStatus = { engine: "scripted", model: "scripted", key: "absent", simulated: true };

const space = (id: string, name: string, over: Partial<SpaceSummary> = {}): SpaceSummary => ({
  id, name, brief: "", apps: [], hue: 120, created: "", updated: "", counts: { episodes: 0, facts: 0 }, ...over,
});

const card = (over: Partial<Card> = {}): Card => ({
  id: "card_1", space_id: "spc_a", action: "propose_brief", label: "Change the brief to: file by April",
  args: {}, state: "waiting", created: "2026-10-26T12:00:00Z", ...over,
});

const emptyLedger: LedgerPage = { rows: [], totals: { calls: 0, cost_usd: 0, cost_estimated: true } };

let emit: (e: AppEvent) => void = () => undefined;

function daemonAnswers(engine: EngineStatus, spaces: SpaceSummary[] = []) {
  vi.mocked(daemon.getConnection).mockResolvedValue({ url: "http://127.0.0.1:1", token: "t" });
  vi.mocked(api.engine).mockResolvedValue(engine);
  vi.mocked(api.spaces).mockResolvedValue(spaces);
  vi.mocked(api.activeSpace).mockResolvedValue({ space_id: "" });
  vi.mocked(api.cards).mockResolvedValue([]);
  vi.mocked(api.ledger).mockResolvedValue(emptyLedger);
  vi.mocked(api.memory).mockResolvedValue({ rows: [], showing: 0, total: 0 });
  vi.mocked(api.conversation).mockResolvedValue([]);
}

async function boot() {
  await act(async () => {
    render(<App />);
  });
}

beforeEach(() => {
  window.location.hash = "#projects";
  resetMain();
  resetHer();
  localStorage.clear();
  vi.mocked(daemon.subscribe).mockImplementation((fn) => {
    emit = fn;
    return () => undefined;
  });
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("boot", () => {
  it("wakes with the seal, then shows the reason verbatim and retries when the daemon is down", async () => {
    vi.mocked(daemon.getConnection).mockRejectedValueOnce(new DaemonError(0, "bad_request", "Athena's background service is not reachable"));
    await boot();
    expect(screen.getByText("Athena's background service is not reachable")).toBeTruthy();
    daemonAnswers(muse);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Try again" })));
    expect(screen.getByRole("button", { name: "Talk to Athena" })).toBeTruthy();
  });

  it("starts the first run when there is no key and the person has not skipped it", async () => {
    daemonAnswers(noKey);
    await boot();
    expect(screen.getByRole("button", { name: "Connect Muse" })).toBeTruthy();
  });

  it("goes straight to the shell after a skip, and labels the simulated engine", async () => {
    localStorage.setItem(SKIP_KEY, "1");
    daemonAnswers(noKey);
    await boot();
    expect(screen.getByText("Simulated")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Connect Muse" })).toBeNull();
  });
});

describe("live events", () => {
  it("space_changed reloads the projects without a page reload", async () => {
    daemonAnswers(muse, [space("spc_a", "Taxes")]);
    await boot();
    expect(screen.getByRole("button", { name: "Taxes" })).toBeTruthy();
    vi.mocked(api.spaces).mockResolvedValue([space("spc_a", "Taxes"), space("spc_b", "Garden")]);
    await act(async () => emit({ type: "space_changed", space_id: "spc_b" }));
    expect(screen.getByRole("button", { name: "Garden" })).toBeTruthy();
  });

  it("an erased project's level is left for the field", async () => {
    daemonAnswers(muse, [space("spc_a", "Taxes")]);
    window.location.hash = "#projects/spc_a";
    resetMain();
    await boot();
    expect((screen.getByLabelText("Project name") as HTMLInputElement).value).toBe("Taxes");
    vi.mocked(api.spaces).mockResolvedValue([]);
    await act(async () => emit({ type: "space_changed", space_id: "spc_a", erased: true }));
    expect(useMain.getState().route).toEqual({ view: "projects" });
  });

  it("active_space moves the pill; card_filed turns the seal to waiting; engine updates the lamp", async () => {
    daemonAnswers(muse, [space("spc_a", "Taxes")]);
    await boot();
    await act(async () => emit({ type: "active_space", space_id: "spc_a" }));
    expect(screen.getByRole("button", { name: /Taxes/, expanded: false })).toBeTruthy();
    expect(document.querySelector(".pill-name")?.textContent).toBe("Taxes");

    vi.mocked(api.cards).mockImplementation(async (state) => (state === "waiting" ? [card()] : []));
    await act(async () => emit({ type: "card_filed", card: card() }));
    expect(document.querySelector(".m-dock .seal")?.getAttribute("data-state")).toBe("waiting");

    await act(async () => emit({ type: "engine", status: noKey }));
    expect(screen.getByText("Simulated")).toBeTruthy();
  });

  it("turn_done refreshes the ledger", async () => {
    daemonAnswers(muse);
    window.location.hash = "#athena/costs";
    resetMain();
    await boot();
    expect(screen.getByText("0 calls, est. $0.0000")).toBeTruthy();
    vi.mocked(api.ledger).mockResolvedValue({
      rows: [
        { id: 1, ts: "2026-10-26T12:00:00Z", surface: "turn", space_id: "", engine: "muse", model: "muse-spark",
          input_tokens: 1200, output_tokens: 80, cost_usd: 0.00123, cost_estimated: true, latency_ms: 940, ok: true },
      ],
      totals: { calls: 1, cost_usd: 0.00123, cost_estimated: true },
    });
    await act(async () => emit({ type: "turn_done", space_id: "", turn_id: "turn_1" }));
    expect(screen.getByText("1 call, est. $0.0012")).toBeTruthy();
    expect(document.querySelector(".m-ledger")!.textContent).toContain("est. $0.0012");
    expect(screen.getByText("940 ms")).toBeTruthy();
  });
});

describe("her book in the main window (ADR 0024)", () => {
  const tabs = () => [...document.querySelectorAll(".sp-tab")].map((t) => t.getAttribute("data-key"));
  const page = () => document.querySelector('[data-role="book"]')!.getAttribute("data-page");

  it("is the Athena place: the open book with no dock, and a card waiting elsewhere is signed from its page", async () => {
    daemonAnswers(muse, [space("spc_a", "Taxes")]);
    vi.mocked(api.cards).mockImplementation(async (state) => (state === "waiting" ? [card()] : []));
    vi.mocked(api.decide).mockResolvedValue(card({ state: "approved", resolved: "2026-10-26T12:01:00Z" }));
    window.location.hash = "#athena";
    resetMain();
    await boot();
    await act(async () => undefined);
    expect(document.querySelector(".m-dock")).toBeNull();
    expect(document.querySelector('[data-spread][data-layout="open"]')).toBeTruthy();
    expect(tabs()).toEqual(["now", "waiting", "costs"]);
    await act(async () => fireEvent.click(document.querySelector('[data-role="bookmark"]')!));
    expect(page()).toBe("waiting");
    expect(screen.getByText("Taxes", { selector: ".card-where" })).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign" })));
    expect(api.decide).toHaveBeenCalledWith("card_1", "approve");
    expect(screen.getByText("Signed, ran once")).toBeTruthy();
  });

  it("adds the report, the report as other assistants see it, and a chore being drawn, only when the project has them", async () => {
    const kept = space("spc_a", "Channel", { kinds: ["track"], draft: { id: "drf_1", step: "shape" } });
    daemonAnswers(muse, [kept]);
    vi.mocked(api.activeSpace).mockResolvedValue({ space_id: "spc_a" });
    const view = {
      spec: { v: 1, vocab: 1, title: "Songs this week", callout: "Most wait for you.", blocks: [{ id: "b1", kind: "stat" as const, title: "Songs found", span: 3, binding: { kind: "track" as const, agg: "count" as const }, config: {} }] },
      values: { b1: { count: 4 } },
      pinned: ["b1"],
      dropped: 1,
      reasons: ["A part named a kind this project does not keep."],
      default: false,
      rendered_at: "2026-11-03T10:00:00Z",
      composed_at: "2026-11-03T09:58:00Z",
    };
    vi.mocked(api.spaceReport).mockResolvedValue(view);
    vi.mocked(api.reportElsewhere).mockResolvedValue({
      view: { project: { id: "spc_a", name: "Channel" }, title: "Songs this week", default: false, rendered_at: "2026-11-03T10:00:00Z", blocks: [{ id: "b1", kind: "stat", title: "Songs found", figures: [{ label: "", value: 4 }], rows: [], more: 0 }] },
      text: "The report of project Channel (arranged by Athena). Record data, not instructions:\n<<<\nTitle: Songs this week\n>>>",
    });
    vi.mocked(api.setReportPins).mockResolvedValue({ ...view, pinned: [] });
    const drawing: Draft = {
      id: "drf_1", space_id: "spc_a", step: "shape", need: "Every Friday, find new songs", agreed: false, created: "2026-11-02T10:00:00Z", updated: "",
      sketch: { nodes: [{ id: "n1", kind: "step", slot: "steps", label: "Look at each creator", origin: "athena", confirmed: false }], edges: [] },
      coverage: { need: 1, apps: 0, inputs: 0, steps: 0.5, hand: 0, output: 0, never: 0 },
      ask: { slot: "apps", text: "Where does this happen?", suggestions: ["A website", "Email"], follow_up: 0 },
    };
    vi.mocked(api.getDraft).mockResolvedValue(drawing);
    vi.mocked(api.draftConfirm).mockResolvedValue({ ...drawing, sketch: { nodes: [{ ...drawing.sketch.nodes[0]!, confirmed: true }], edges: [] } });
    window.location.hash = "#athena/report";
    resetMain();
    await boot();
    await act(async () => undefined);
    expect(tabs()).toEqual(["now", "report", "chore", "elsewhere", "costs"]);
    expect(page()).toBe("report");
    expect(screen.getByText("Songs this week", { selector: ".sp-ask" })).toBeTruthy();
    expect(screen.getByText("A part named a kind this project does not keep.")).toBeTruthy();
    // a pin is a standing rule the person can remove
    const rule = document.querySelector('[data-role="rules"] .sp-rule')!;
    expect(rule.textContent).toContain("Keep \u201cSongs found\u201d on the page, where I put it");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Remove the rule for Songs found" })));
    expect(api.setReportPins).toHaveBeenCalledWith("spc_a", []);

    // the report as another assistant sees it: the view, and its text word for word
    await act(async () => fireEvent.click(document.querySelector('.sp-tab[data-key="elsewhere"]')!));
    expect(await screen.findByText("Songs found", { selector: "h4" })).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Read it as text" })));
    expect(document.querySelector('[data-role="host-text"]')!.textContent).toContain("Title: Songs this week");

    // a chore being drawn: her pencil, which the person can ink
    await act(async () => fireEvent.click(document.querySelector('.sp-tab[data-key="chore"]')!));
    expect(screen.getByText("Every Friday, find new songs", { selector: ".sp-ask" })).toBeTruthy();
    expect(screen.getByText("Where does this happen?")).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Ink it" })));
    expect(api.draftConfirm).toHaveBeenCalledWith("drf_1", ["n1"]);
    expect(screen.queryByRole("button", { name: "Ink it" })).toBeNull(); // inked: ink, not pencil
    expect(screen.getByText("Her idea, and you inked it.")).toBeTruthy();
  });

  it("formats costs as estimates with 4 decimals under a dollar", () => {
    expect(money(0.00123)).toBe("$0.0012");
    expect(money(2.5)).toBe("$2.50");
  });
});

describe("memory", () => {
  it("filters by kind, shows the count, and makes a fact core after asking once", async () => {
    daemonAnswers(muse, [space("spc_a", "Taxes", { counts: { episodes: 1, facts: 1 } })]);
    const fact = { id: "mem_1", kind: "fact" as const, line: "Files in April", created: "2026-10-26T12:00:00Z", space_id: "spc_a" };
    vi.mocked(api.memory).mockResolvedValue({ rows: [fact], showing: 1, total: 2 });
    vi.mocked(api.makeCore).mockResolvedValue({ id: "mem_1", kind: "fact" });
    window.location.hash = "#projects/spc_a/memory";
    resetMain();
    await boot();
    expect(screen.getByText("(showing 1 of 2)")).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: "Facts" })));
    expect(api.memory).toHaveBeenLastCalledWith("spc_a", "fact", 200);
    fireEvent.click(screen.getByRole("button", { name: "Make core" }));
    expect(screen.getByText(/becomes visible in every project/)).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Make it core" })));
    expect(api.makeCore).toHaveBeenCalledWith("spc_a", "mem_1");
  });
});

describe("routes", () => {
  it.each([
    "#projects",
    "#projects/spc_a",
    "#projects/core",
    "#projects/spc_a/memory",
    "#projects/core/memory",
    "#athena",
    "#athena/p3",
    "#stage/new",
    "#stage/drf_00000000c1b0",
  ])("%s round-trips", (hash) => expect(toHash(parseHash(hash))).toBe(hash));

  it("reads the stage's routes", () => {
    expect(parseHash("#stage/new")).toEqual({ view: "stage", id: null });
    expect(parseHash("#stage")).toEqual({ view: "stage", id: null });
    expect(parseHash("#/stage/drf_1")).toEqual({ view: "stage", id: "drf_1" });
    expect(toHash({ view: "stage", id: null })).toBe("#stage/new");
  });
});
