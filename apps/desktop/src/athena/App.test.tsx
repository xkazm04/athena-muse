import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import type { AppEvent, Card, EngineStatus, SpaceSummary, Turn, TurnEvent } from "../lib/contract";
import { streamRun } from "../lib/daemon";
import { SETTLE_MS } from "../theme";
import { App } from "./App";
import { resetHer } from "./store";
import { formatCost } from "./Transcript";

vi.mock("../lib/api", () => ({
  engine: vi.fn(),
  activeSpace: vi.fn(),
  spaces: vi.fn(),
  conversation: vi.fn(),
  cards: vi.fn(),
  setActiveSpace: vi.fn(),
  decide: vi.fn(),
}));

let emitApp: (e: AppEvent) => void = () => undefined;
vi.mock("../lib/daemon", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/daemon")>();
  return {
    ...real,
    getConnection: vi.fn().mockResolvedValue({ url: "http://127.0.0.1:1", token: "t" }),
    streamRun: vi.fn(),
    subscribe: vi.fn((fn: (e: AppEvent) => void) => {
      emitApp = fn;
      return () => undefined;
    }),
  };
});

vi.mock("../lib/windows", () => ({
  isTauri: () => false,
  hideThisWindow: vi.fn().mockResolvedValue(undefined),
  startDrag: vi.fn().mockResolvedValue(undefined),
}));

const m = vi.mocked(api);
const run = vi.mocked(streamRun);

const live: EngineStatus = { engine: "muse", model: "muse-1", key: "env", simulated: false };
const space = (id: string, name: string): SpaceSummary => ({
  id, name, brief: "", apps: [], hue: 210, created: "", updated: "", counts: { episodes: 0, facts: 0 },
});
const turn = (id: string, role: Turn["role"], text: string, extra: Partial<Turn> = {}): Turn => ({
  id, space_id: "spc_1", role, text, created: "2026-10-26T12:00:00Z", ...extra,
});
const card: Card = {
  id: "card_1",
  space_id: "spc_1",
  action: "propose_brief",
  label: "Change this project's brief to: file by April",
  args: { brief: "file by April" },
  state: "waiting",
  created: "2026-10-26T12:00:00Z",
};

const sealState = () => document.querySelector(".seal")!.getAttribute("data-state");
const composer = () => screen.getByRole("textbox", { name: "Message Athena" }) as HTMLTextAreaElement;

function type(text: string) {
  fireEvent.change(composer(), { target: { value: text } });
  fireEvent.keyDown(composer(), { key: "Enter" });
}

/** A turn stream the test drives by hand: `emit` events, then `end` it. */
function heldStream() {
  let emit: (e: TurnEvent) => void = () => undefined;
  let end: () => void = () => undefined;
  run.mockImplementationOnce((_body, onEvent) => {
    emit = onEvent;
    return new Promise<void>((resolve) => (end = resolve));
  });
  return {
    emit: (e: TurnEvent) => act(() => emit(e)),
    end: () => act(async () => end()),
  };
}

beforeEach(() => {
  resetHer();
  vi.clearAllMocks();
  m.engine.mockResolvedValue(live);
  m.activeSpace.mockResolvedValue({ space_id: "spc_1" });
  m.spaces.mockResolvedValue([space("spc_1", "Taxes"), space("spc_2", "Garden")]);
  m.conversation.mockResolvedValue([]);
  m.cards.mockResolvedValue([]);
});

afterEach(cleanup);

async function boot() {
  render(<App />);
  await waitFor(() => expect(composer().disabled).toBe(false));
}

describe("her window", () => {
  it("sends, streams the reply in place, and the reloaded conversation persists across reopen", async () => {
    const saved = [turn("t1", "person", "When are taxes due?"), turn("t2", "athena", "By April 15.", { cost_usd: 0.0004 })];
    await boot();
    expect(sealState()).toBe("rest");

    const stream = heldStream();
    m.conversation.mockResolvedValue(saved);
    type("When are taxes due?");
    expect(run).toHaveBeenCalledWith({ text: "When are taxes due?", space_id: "spc_1" }, expect.any(Function), expect.any(AbortSignal));
    expect(screen.getByText("When are taxes due?")).toBeTruthy(); // optimistic
    expect(composer().disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Stop" })).toBeTruthy();

    await stream.emit({ type: "start", turn_id: "turn_1", engine: "muse", simulated: false });
    expect(sealState()).toBe("working");
    expect(screen.getByText("Thinking...", { selector: ".her-state" })).toBeTruthy();
    await stream.emit({ type: "tool", name: "recall", label: "Looked through memory", class: "auto" });
    await stream.emit({ type: "text", delta: "By April" });
    expect(screen.getByText("By April")).toBeTruthy();
    await stream.emit({ type: "text", delta: " 15." });
    expect(screen.getByText("By April 15.")).toBeTruthy();
    expect(screen.getByText("Looked through memory")).toBeTruthy();
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: false, cost_usd: 0.0004 });
    await stream.end();

    await waitFor(() => expect(m.conversation).toHaveBeenCalledTimes(2));
    expect(m.conversation).toHaveBeenLastCalledWith("spc_1");
    await waitFor(() => expect(screen.getByText("est. $0.0004")).toBeTruthy());
    expect(screen.getAllByText("When are taxes due?")).toHaveLength(1);
    expect(screen.getAllByText("By April 15.")).toHaveLength(1);
    expect(sealState()).toBe("rest");

    // Reopen: a fresh window boots from the daemon and shows the same two lines.
    cleanup();
    resetHer();
    await boot();
    expect(await screen.findByText("When are taxes due?")).toBeTruthy();
    expect(screen.getByText("By April 15.")).toBeTruthy();
    expect(screen.getByText("est. $0.0004")).toBeTruthy();
  });

  it("files a card inline; it signs once and the seal goes waiting -> signed -> rest", async () => {
    await boot();
    const stream = heldStream();
    m.conversation.mockResolvedValue([
      turn("t1", "person", "Set the brief"),
      turn("t2", "athena", `I filed a card for you to sign: ${card.label}`, { card_id: card.id }),
    ]);
    type("Set the brief");
    await stream.emit({ type: "start", turn_id: "turn_1", engine: "scripted", simulated: false });
    await stream.emit({ type: "tool", name: "propose_brief", label: card.label, class: "gated" });
    await stream.emit({ type: "card", card });
    expect(sealState()).toBe("waiting");
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: true });
    await stream.end();
    await waitFor(() => expect(m.conversation).toHaveBeenCalledTimes(2));
    expect(sealState()).toBe("waiting");
    expect(document.querySelector(".seal__count")!.textContent).toBe("1");
    expect(screen.getByText("Waiting on you")).toBeTruthy();

    const approved: Card = { ...card, state: "approved", resolved: "2026-10-26T12:01:00Z" };
    m.decide.mockResolvedValue(approved);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign" })));
    expect(m.decide).toHaveBeenCalledTimes(1);
    expect(m.decide).toHaveBeenCalledWith(card.id, "approve");
    expect(sealState()).toBe("signed");
    expect(screen.getByText("Signed, ran once")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Sign" })).toBeNull();

    // The daemon's own echo of the same resolution changes nothing and asks nothing again.
    act(() => emitApp({ type: "card_resolved", card: approved }));
    expect(m.decide).toHaveBeenCalledTimes(1);

    await act(() => new Promise((r) => setTimeout(r, SETTLE_MS + 100)));
    expect(sealState()).toBe("rest");
    expect(document.querySelector(".seal__count")).toBeNull();
  });

  it("follows a card signed in the main window, seal included", async () => {
    m.cards.mockImplementation(async (state) => (state === "waiting" ? [card] : []));
    await boot();
    await waitFor(() => expect(sealState()).toBe("waiting"));
    act(() => emitApp({ type: "card_resolved", card: { ...card, state: "approved" } }));
    expect(sealState()).toBe("signed");
  });

  it("switching project switches the conversation, and a switch mid-reply waits for the reply", async () => {
    m.conversation.mockImplementation(async (id) =>
      id === "spc_1"
        ? [turn("a1", "person", "Taxes question")]
        : [{ ...turn("b1", "person", "Garden question"), space_id: "spc_2" }],
    );
    m.setActiveSpace.mockImplementation(async (id) => ({ space_id: id }));
    await boot();
    expect(await screen.findByText("Taxes question")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Taxes/ }));
    await act(async () => fireEvent.click(screen.getByRole("menuitemradio", { name: /Garden/ })));
    expect(m.setActiveSpace).toHaveBeenCalledWith("spc_2");
    expect(await screen.findByText("Garden question")).toBeTruthy();
    expect(screen.queryByText("Taxes question")).toBeNull();

    // Held: asked for during a turn, applied when it is done.
    const stream = heldStream();
    type("Plant tomatoes?");
    await stream.emit({ type: "start", turn_id: "turn_2", engine: "muse", simulated: false });
    fireEvent.click(screen.getByRole("button", { name: /Garden/ }));
    await act(async () => fireEvent.click(screen.getByRole("menuitemradio", { name: /Taxes/ })));
    expect(screen.getByText("switches after this reply")).toBeTruthy();
    expect(m.setActiveSpace).toHaveBeenCalledTimes(1);
    await stream.emit({ type: "done", turn_id: "turn_2", waiting: false });
    await stream.end();
    await waitFor(() => expect(m.setActiveSpace).toHaveBeenLastCalledWith("spc_1"));
    expect(await screen.findByText("Taxes question")).toBeTruthy();
    expect(screen.queryByText("switches after this reply")).toBeNull();
  });

  it("reloads when the other window switches the project", async () => {
    m.conversation.mockImplementation(async (id) => (id === "spc_2" ? [turn("b1", "person", "Garden question")] : []));
    await boot();
    act(() => emitApp({ type: "active_space", space_id: "spc_2" }));
    expect(await screen.findByText("Garden question")).toBeTruthy();
    expect(m.conversation).toHaveBeenLastCalledWith("spc_2");
  });

  it("labels the simulated engine, and only then", async () => {
    m.engine.mockResolvedValue({ ...live, engine: "scripted", key: "absent", simulated: true });
    await boot();
    const band = await screen.findByRole("note");
    expect(band.textContent).toBe("Simulated - connect Muse in the main window for real answers");
    act(() => emitApp({ type: "engine", status: live }));
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("shows a stream error verbatim and Try again re-sends the same text", async () => {
    await boot();
    const stream = heldStream();
    type("Hello?");
    await stream.emit({ type: "start", turn_id: "turn_1", engine: "muse", simulated: false });
    await stream.emit({ type: "error", error: "engine_unavailable", reason: "Muse did not answer in time" });
    await stream.end();
    expect(screen.getByRole("alert").textContent).toContain("Muse did not answer in time");
    expect(sealState()).toBe("rest");

    const again = heldStream();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Try again" })));
    expect(run).toHaveBeenCalledTimes(2);
    expect(run.mock.calls[1]![0]).toEqual({ text: "Hello?", space_id: "spc_1" });
    expect(screen.getAllByText("Hello?")).toHaveLength(1);
    await again.end();
  });

  it("Stop aborts the reply", async () => {
    await boot();
    let signal: AbortSignal | undefined;
    run.mockImplementationOnce((_b, _on, s) => {
      signal = s;
      return new Promise<void>((_, reject) => s!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))));
    });
    type("Long story please");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Stop" })));
    expect(signal!.aborted).toBe(true);
    await waitFor(() => expect(composer().disabled).toBe(false));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("Shift+Enter is a new line, not a send", async () => {
    await boot();
    fireEvent.change(composer(), { target: { value: "line one" } });
    fireEvent.keyDown(composer(), { key: "Enter", shiftKey: true });
    expect(run).not.toHaveBeenCalled();
  });
});

describe("formatCost", () => {
  it("always says est.", () => {
    expect(formatCost(0.0004)).toBe("est. $0.0004");
    expect(formatCost(0.00001)).toBe("est. under $0.0001");
    expect(formatCost(1.5)).toBe("est. $1.50");
  });
});
