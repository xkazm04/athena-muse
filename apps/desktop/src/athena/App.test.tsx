import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import type { AppEvent, Card, EngineStatus, ShownBlocks, SpaceSummary, Turn, TurnEvent } from "../lib/contract";
import { streamRun } from "../lib/daemon";
import { SETTLE_MS } from "../theme";
import { App } from "./App";
import { resetHer, useHer } from "./store";
import { formatCost } from "./Transcript";

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

let handOver: (text: string) => void = () => undefined;
vi.mock("../lib/windows", () => ({
  isTauri: () => false,
  hideThisWindow: vi.fn().mockResolvedValue(undefined),
  startDrag: vi.fn().mockResolvedValue(undefined),
  onHanded: vi.fn(async (fn: (text: string) => void) => {
    handOver = fn;
    return () => undefined;
  }),
  onSetupStart: vi.fn(async () => () => undefined),
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
/** Her paragraph whose whole text is `text`, however many spans the word reveal split it into. */
const said = (text: string) => screen.getByText((_, el) => el?.tagName === "P" && el.closest(".her-say") !== null && el.textContent === text);
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
  it("takes the surface's handed words as a turn, and keeps them in the composer while she writes", async () => {
    await boot();
    const stream = heldStream();
    await act(async () => handOver("  Appeal my mother's plan denial  "));
    expect(run).toHaveBeenCalledWith({ text: "Appeal my mother's plan denial", space_id: "spc_1" }, expect.any(Function), expect.any(AbortSignal));
    await act(async () => handOver("And the pharmacy bill"));
    expect(run).toHaveBeenCalledTimes(1);
    expect(composer().value).toBe("And the pharmacy bill");
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: false });
    await stream.end();
  });

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
    expect(said("By April")).toBeTruthy();
    await stream.emit({ type: "text", delta: " 15." });
    // live words arrive in their own reveal spans; the paragraph reads whole
    expect(said("By April 15.")).toBeTruthy();
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

  it("wears the look chosen in Settings, at boot and when the main window changes it", async () => {
    m.settings.mockResolvedValue({
      look: { theme: "light", type_scale: "large", motion: "system" },
      engine: "muse",
      source: "default",
      engines: [],
    });
    await boot();
    await waitFor(() => expect(document.documentElement.getAttribute("data-theme")).toBe("light"));
    expect(document.documentElement.getAttribute("data-type-scale")).toBe("large");
    act(() => emitApp({ type: "settings", look: { theme: "auto", type_scale: "standard", motion: "calm" } }));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(document.documentElement.getAttribute("data-motion")).toBe("calm");
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

  it("keeps the live parts in the order they streamed: text, tool, text, card, text", async () => {
    await boot();
    const stream = heldStream();
    type("Look into it");
    await stream.emit({ type: "start", turn_id: "turn_1", engine: "muse", simulated: false });
    await stream.emit({ type: "text", delta: "Let me look." });
    await stream.emit({ type: "tool", name: "recall", label: "Looked through memory", class: "auto" });
    await stream.emit({ type: "text", delta: "Found **two** notes." });
    await stream.emit({ type: "tool", name: "propose_brief", label: card.label, class: "gated" });
    await stream.emit({ type: "card", card });
    await stream.emit({ type: "text", delta: "Sign it" });
    await stream.emit({ type: "text", delta: " when ready." });

    const parts = useHer.getState().live!.parts;
    expect(parts.map((p) => p.kind)).toEqual(["text", "tool", "text", "card", "text"]);
    expect(parts[4]).toEqual({ kind: "text", text: "Sign it when ready.", marks: [0, 7] });

    // The screen says them in that order, and her name only once.
    const rows = [...document.querySelectorAll(".her-transcript > *")].slice(1);
    expect(rows.map((r) => r.className.split(" ")[0])).toEqual(["her-line", "her-tool", "her-line", "her-card", "her-line"]);
    expect(rows.map((r) => r.textContent)).toEqual([
      "Let me look.",
      "Looked through memory",
      "Found two notes.",
      expect.stringContaining(card.label),
      "Sign it when ready.",
    ]);
    expect(document.querySelectorAll(".her-say:not(.her-say--more)")).toHaveLength(1);
    expect(document.querySelector(".her-transcript strong")!.textContent).toBe("two");

    // While she writes, the newest words are their own reveal span; once done, none is left.
    // A run a tool line or card followed is finished: only the last run is still revealing.
    expect(rows[4]!.querySelectorAll(".prose-new").length).toBeGreaterThan(0);
    expect(rows[0]!.querySelector(".prose-new")).toBeNull();
    expect(rows[2]!.querySelector(".prose-new")).toBeNull();
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: true, cost_usd: 0.0004 });
    expect(document.querySelectorAll(".prose-new")).toHaveLength(0);
    expect(rows[4]!.textContent).toBe("Sign it when ready.est. $0.0004");
    await stream.end();
  });

  it("draws a settled turn from its stored parts exactly as it drew it live", async () => {
    m.cards.mockResolvedValue([card]);
    await boot();
    const stream = heldStream();
    type("Look into it");
    await stream.emit({ type: "start", turn_id: "turn_1", engine: "muse", simulated: false });
    await stream.emit({ type: "text", delta: "Let me look." });
    await stream.emit({ type: "tool", name: "recall", label: "Looked through memory", class: "auto" });
    await stream.emit({ type: "text", delta: "Found **two** notes." });
    await stream.emit({ type: "tool", name: "propose_brief", label: card.label, class: "gated" });
    await stream.emit({ type: "card", card });
    await stream.emit({ type: "text", delta: "Sign it" });
    await stream.emit({ type: "text", delta: " when ready." });
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: true, cost_usd: 0.0004 });
    const rowsOf = () =>
      [...document.querySelectorAll(".her-transcript > *")].slice(1).map((r) => [r.className.split(" ")[0], r.textContent]);
    const before = rowsOf();
    const liveKinds = useHer.getState().live!.parts.map((p) => p.kind);

    // The daemon's reload: the turn as it was stored, its parts in the order they streamed (a fixture
    // of what `turn._Parts` keeps; tests/test_turn_parts.py holds the daemon to the same order).
    m.conversation.mockResolvedValue([
      turn("t1", "person", "Look into it"),
      turn("t2", "athena", "Let me look.Found **two** notes.Sign it when ready.", {
        cost_usd: 0.0004,
        card_id: card.id,
        parts: [
          { kind: "text", text: "Let me look." },
          { kind: "tool", name: "recall", label: "Looked through memory", class: "auto" },
          { kind: "text", text: "Found **two** notes." },
          { kind: "tool", name: "propose_brief", label: card.label, class: "gated" },
          { kind: "card", card_id: card.id },
          { kind: "text", text: "Sign it when ready." },
        ],
      }),
    ]);
    await stream.end();
    await waitFor(() => expect(useHer.getState().live).toBeNull());

    const after = [...document.querySelectorAll(".her-transcript > *")].map((r) => [r.className.split(" ")[0], r.textContent]);
    expect(after[0]).toEqual(["her-line", "Look into it"]);
    expect(after.slice(1)).toEqual(before);
    expect(liveKinds).toEqual(["text", "tool", "text", "card", "text"]);
    expect(document.querySelector(".her-transcript strong")!.textContent).toBe("two");
  });

  it("shows report parts in place among her words, with drops said, and the same after a reload", async () => {
    const shown: ShownBlocks = {
      blocks: [
        {
          id: "part-1",
          kind: "pipeline",
          title: "Where the tracks stand",
          span: 12,
          config: { stages: [{ label: "Found", binding: { kind: "track", agg: "count" } }, { label: "Kept", binding: { kind: "track", agg: "count" } }] },
        },
      ],
      values: { "part-1": { stages: [{ label: "Found", count: 3 }, { label: "Kept", count: 1 }] } },
      dropped: 1,
      reasons: ["A queue part: a queue asks for a verdict on each track, which the project's report does."],
    };
    await boot();
    const stream = heldStream();
    type("How are the tracks doing?");
    await stream.emit({ type: "start", turn_id: "turn_1", engine: "muse", simulated: false });
    await stream.emit({ type: "text", delta: "Here is where they stand." });
    await stream.emit({ type: "blocks", shown });
    await stream.emit({ type: "text", delta: "Most still wait for you." });
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: false });
    const rowsOf = () => [...document.querySelectorAll(".her-transcript > *")].map((r) => r.className.split(" ")[0]);
    expect(rowsOf().slice(1)).toEqual(["her-line", "her-blocks", "her-line"]);
    const part = document.querySelector('.her-blocks [data-role="report-block"]')!;
    expect(part.getAttribute("data-kind")).toBe("pipeline");
    expect(part.textContent).toContain("Where the tracks stand");
    expect(document.querySelector('.her-blocks [data-role="pin"]')).toBeNull(); // a reply's part is not pinned
    expect(document.querySelector('.her-blocks [data-role="dropped"] summary')!.textContent).toBe("1 part could not be shown");
    const before = document.querySelector(".her-blocks")!.innerHTML;

    m.conversation.mockResolvedValue([
      turn("t1", "person", "How are the tracks doing?"),
      turn("t2", "athena", "Here is where they stand.Most still wait for you.", {
        parts: [
          { kind: "text", text: "Here is where they stand." },
          { kind: "blocks", shown },
          { kind: "text", text: "Most still wait for you." },
        ],
      }),
    ]);
    await stream.end();
    await waitFor(() => expect(useHer.getState().live).toBeNull());
    expect(rowsOf()).toEqual(["her-line", "her-line", "her-blocks", "her-line"]);
    expect(document.querySelector(".her-blocks")!.innerHTML).toBe(before);
  });

  it("draws a turn stored before parts were kept as its words and its card, as before", async () => {
    m.cards.mockResolvedValue([card]);
    m.conversation.mockResolvedValue([turn("t1", "person", "Brief?"), turn("t2", "athena", "Filed it.", { card_id: card.id })]);
    await boot();
    const rows = [...document.querySelectorAll(".her-transcript > *")].map((r) => r.className.split(" ")[0]);
    expect(rows).toEqual(["her-line", "her-line", "her-card"]);
  });

  it("shows a stored part this window does not know as a plain row, never nothing", async () => {
    const odd = { kind: "hologram", what: "x" } as unknown as NonNullable<Turn["parts"]>[number];
    m.conversation.mockResolvedValue([turn("t1", "athena", "Here.", { parts: [{ kind: "text", text: "Here." }, odd] })]);
    await boot();
    expect(document.querySelector(".her-tool--unknown")!.getAttribute("data-part")).toBe("hologram");
  });

  it("shows a tool line after the words before it, with the dots while more is coming", async () => {
    await boot();
    const stream = heldStream();
    type("Check");
    await stream.emit({ type: "text", delta: "One moment." });
    expect(document.querySelector(".her-say--pending")).toBeNull();
    await stream.emit({ type: "tool", name: "recall", label: "Looked through memory", class: "auto" });
    const after = document.querySelector(".her-tool")!.nextElementSibling!;
    expect(after.querySelector(".her-say--pending")).toBeTruthy();
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: false });
    await stream.end();
  });

  it("renders her words as rich text, settled and live, and any HTML in them as inert text", async () => {
    m.conversation.mockResolvedValue([
      turn("t1", "person", "Steps?"),
      turn("t2", "athena", "**First:**\n- open `settings`\n- sign\n\n<img src=x onerror=alert(1)><script>alert(2)</script>"),
    ]);
    await boot();
    expect((await screen.findByText("First:")).tagName).toBe("STRONG");
    expect(screen.getByText("sign").tagName).toBe("LI");
    expect(screen.getByText("settings").tagName).toBe("CODE");
    expect(said("<img src=x onerror=alert(1)><script>alert(2)</script>")).toBeTruthy();
    expect(document.querySelector(".her-transcript img, .her-transcript script")).toBeNull();

    const stream = heldStream();
    type("And now?");
    await stream.emit({ type: "text", delta: "Now *wait" });
    // an unclosed marker mid-stream is styled as if closed at the tail; its star never shows
    expect(document.querySelector(".her-transcript em")!.textContent).toBe("wait");
    await stream.emit({ type: "text", delta: "* <b>here</b>" });
    expect(said("Now wait <b>here</b>")).toBeTruthy();
    expect(document.querySelector(".her-transcript b")).toBeNull();
    await stream.emit({ type: "done", turn_id: "turn_2", waiting: false });
    await stream.end();
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
