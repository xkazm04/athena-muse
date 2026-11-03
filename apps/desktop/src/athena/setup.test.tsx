import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import type { Card, EngineStatus, TurnEvent } from "../lib/contract";
import { streamRun } from "../lib/daemon";
import { setupConversation, streamSetup } from "../lib/setup";
import { App } from "./App";
import { resetHer, useHer } from "./store";

vi.mock("../lib/api", () => ({
  engine: vi.fn(),
  activeSpace: vi.fn(),
  spaces: vi.fn(),
  conversation: vi.fn(),
  cards: vi.fn(),
  setActiveSpace: vi.fn(),
  decide: vi.fn(),
  settings: vi.fn(),
}));
vi.mock("../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/daemon")>()),
  getConnection: vi.fn().mockResolvedValue({ url: "http://127.0.0.1:1", token: "t" }),
  streamRun: vi.fn(),
  subscribe: vi.fn(() => () => undefined),
}));
vi.mock("../lib/setup", () => ({ setupConversation: vi.fn(), streamSetup: vi.fn() }));

let startSetup: () => void = () => undefined;
vi.mock("../lib/windows", () => ({
  isTauri: () => false,
  hideThisWindow: vi.fn(),
  startDrag: vi.fn(),
  onHanded: vi.fn(async () => () => undefined),
  onSetupStart: vi.fn(async (fn: () => void) => {
    startSetup = fn;
    return () => undefined;
  }),
}));

const m = vi.mocked(api);
const live: EngineStatus = { engine: "muse", model: "muse-1", key: "env", simulated: false };
const setupCard = (state: Card["state"]): Card => ({
  id: "card_s",
  space_id: "setup",
  action: "setup_act",
  label: "Install Tailscale, the private network",
  args: { tool: "install_overlay" },
  state,
  created: "2026-11-01T10:00:00Z",
});

beforeEach(() => {
  resetHer();
  vi.clearAllMocks();
  m.engine.mockResolvedValue(live);
  m.activeSpace.mockResolvedValue({ space_id: "spc_1" });
  m.spaces.mockResolvedValue([]);
  m.conversation.mockResolvedValue([]);
  m.cards.mockResolvedValue([]);
  vi.mocked(setupConversation).mockResolvedValue([]);
});
afterEach(cleanup);

/** The next setup stream plays the given events at once. */
function plays(...events: TurnEvent[]) {
  vi.mocked(streamSetup).mockImplementationOnce(async (_body, onEvent) => {
    for (const e of events) onEvent(e);
  });
}

const done = (id: string): TurnEvent => ({ type: "done", turn_id: id, waiting: false });

describe("her window in the setup conversation", () => {
  it("speaks first: the press sends start with no words, on the setup route and not /run", async () => {
    plays({ type: "start", turn_id: "t1", engine: "muse", simulated: false }, { type: "text", delta: "Hello. " }, done("t1"));
    render(<App />);
    await waitFor(() => expect((screen.getByRole("textbox", { name: "Your words to Athena" }) as HTMLTextAreaElement).disabled).toBe(false));
    await act(async () => startSetup());
    expect(streamSetup).toHaveBeenCalledWith({ start: true }, expect.any(Function), expect.any(AbortSignal));
    expect(streamRun).not.toHaveBeenCalled();
    expect(useHer.getState().setup).toBe(true);
    expect(setupConversation).toHaveBeenCalled();
  });

  it("sends the person's later words as setup turns, and a project switch leaves the conversation", async () => {
    render(<App />);
    await waitFor(() => expect(useHer.getState().status).toBe("ready"));
    plays(done("t1"));
    await act(async () => useHer.getState().beginSetup());
    plays(done("t2"));
    await act(async () => useHer.getState().send("yes please"));
    expect(streamSetup).toHaveBeenLastCalledWith({ text: "yes please" }, expect.any(Function), expect.any(AbortSignal));
    m.setActiveSpace.mockResolvedValue({ space_id: "spc_2" });
    await act(async () => useHer.getState().select("spc_2"));
    expect(useHer.getState().setup).toBe(false);
  });

  it("picks up from a signed setup card, and not from any other card", async () => {
    render(<App />);
    await waitFor(() => expect(useHer.getState().status).toBe("ready"));
    plays(done("t1"));
    await act(async () => useHer.getState().beginSetup());
    vi.mocked(streamSetup).mockClear();
    plays(done("t2"));
    await act(async () => useHer.getState().decided(setupCard("approved")));
    expect(streamSetup).toHaveBeenCalledWith({ start: true }, expect.any(Function), expect.any(AbortSignal));
    vi.mocked(streamSetup).mockClear();
    await act(async () => useHer.getState().decided(setupCard("declined")));
    await act(async () => useHer.getState().decided({ ...setupCard("approved"), action: "propose_brief" }));
    expect(streamSetup).not.toHaveBeenCalled();
  });

  it("outside the setup conversation a project turn still goes to /run", async () => {
    render(<App />);
    await waitFor(() => expect(useHer.getState().status).toBe("ready"));
    vi.mocked(streamRun).mockImplementationOnce(async (_b, onEvent) => onEvent(done("t")));
    await act(async () => useHer.getState().send("hello"));
    expect(streamRun).toHaveBeenCalledWith({ text: "hello", space_id: "spc_1" }, expect.any(Function), expect.any(AbortSignal));
    expect(streamSetup).not.toHaveBeenCalled();
  });
});
