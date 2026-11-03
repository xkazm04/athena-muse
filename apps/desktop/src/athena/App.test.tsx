import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import type { AppEvent, Card, EngineStatus, ShownBlocks, SpaceSummary, Turn, TurnEvent } from "../lib/contract";
import { streamRun } from "../lib/daemon";
import { SETTLE_MS } from "../theme";
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
  setLook: vi.fn(),
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
  args: { brief: "file by April, and keep every receipt" },
  state: "waiting",
  created: "2026-10-26T12:00:00Z",
};

const sealState = () => document.querySelector(".seal")!.getAttribute("data-state");
const book = () => document.querySelector('[data-role="book"]')!;
const left = () => document.querySelector('[data-role="page-left"]')!;
const right = () => document.querySelector('[data-role="page-right"]')!;
/** Each receipt's own words (its small second line aside). */
const receipts = () => [...left().querySelectorAll(".sp-rc-x")].map((r) => r.firstChild!.textContent);
const answer = () => right().querySelector('[data-role="answer"]')!;
const composer = () => screen.getByRole("textbox", { name: "Your words to Athena" }) as HTMLTextAreaElement;
const select = () => document.querySelector("#sp-page-select") as HTMLSelectElement;

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
  document.documentElement.removeAttribute("data-motion");
  m.engine.mockResolvedValue(live);
  m.activeSpace.mockResolvedValue({ space_id: "spc_1" });
  m.spaces.mockResolvedValue([space("spc_1", "Taxes"), space("spc_2", "Garden")]);
  m.conversation.mockResolvedValue([]);
  m.cards.mockResolvedValue([]);
});

afterEach(cleanup);

/** Boots her window; with no conversation it opens on the page being written. */
async function boot() {
  render(<App />);
  await waitFor(() => expect(useHer.getState().status).toBe("ready"));
}

async function bootOnNewPage() {
  await boot();
  await waitFor(() => expect(composer().disabled).toBe(false));
}

describe("her window: the book folded to one page", () => {
  it("takes the surface's handed words as a page, and keeps later ones for the next page", async () => {
    await bootOnNewPage();
    const stream = heldStream();
    await act(async () => handOver("  Appeal my mother's plan denial  "));
    expect(run).toHaveBeenCalledWith({ text: "Appeal my mother's plan denial", space_id: "spc_1" }, expect.any(Function), expect.any(AbortSignal));
    await act(async () => handOver("And the pharmacy bill"));
    expect(run).toHaveBeenCalledTimes(1);
    m.conversation.mockResolvedValue([turn("t1", "person", "Appeal my mother's plan denial"), turn("t2", "athena", "Done.")]);
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: false });
    await stream.end();
    await waitFor(() => expect(composer().value).toBe("And the pharmacy bill"));
    expect(book().getAttribute("data-page")).toBe("now");
  });

  it("writes a page while you watch, then the page settles into the book and persists across reopen", async () => {
    const saved = [
      turn("t1", "person", "When are taxes due?"),
      turn("t2", "athena", "By April 15.", {
        cost_usd: 0.0004,
        duration_ms: 6200,
        parts: [
          { kind: "tool", name: "recall", label: "Looked through memory", class: "auto", at_ms: 4000 },
          { kind: "text", text: "By April 15.", at_ms: 5100 },
        ],
      }),
    ];
    await bootOnNewPage();
    expect(sealState()).toBe("rest");
    expect(screen.getByText("Ask Athena anything. In a project, she remembers it there.")).toBeTruthy();

    const stream = heldStream();
    m.conversation.mockResolvedValue(saved);
    type("When are taxes due?");
    expect(run).toHaveBeenCalledWith({ text: "When are taxes due?", space_id: "spc_1" }, expect.any(Function), expect.any(AbortSignal));
    expect(screen.getByText("Writing now")).toBeTruthy();
    expect(left().querySelector('[data-role="ask"], .sp-ask')!.textContent).toBe("When are taxes due?");
    expect(screen.getByRole("button", { name: "Stop" })).toBeTruthy();
    expect(screen.getByText("Her answer will be written here.")).toBeTruthy();

    await stream.emit({ type: "start", turn_id: "turn_1", engine: "muse", simulated: false });
    expect(sealState()).toBe("working");
    expect(screen.getByText("Thinking...", { selector: ".sp-state" })).toBeTruthy();
    await stream.emit({ type: "tool", name: "recall", label: "Looked through memory", class: "auto" });
    await stream.emit({ type: "text", delta: "By April" });
    await stream.emit({ type: "text", delta: " 15." });
    expect(receipts()).toEqual(["Looked through memory", "Writing to you"]);
    // live moments are this window's own count, said in words
    expect(left().querySelector(".sp-rc-t")!.textContent).toMatch(/^after \d+ s$/);
    expect(answer().textContent).toBe("By April 15.");
    expect(answer().textContent).not.toContain("Looked through memory"); // a step is a receipt, not her answer
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: false, cost_usd: 0.0004 });
    await stream.end();

    // settled: the window turns to the page it became, with the daemon's moments and the tally
    await waitFor(() => expect(book().getAttribute("data-page")).toBe("p1"));
    expect([...left().querySelectorAll(".sp-rc-t")].map((t) => t.textContent)).toEqual(["after 4 s", "after 5 s"]);
    expect(left().querySelector('[data-role="tally"]')!.textContent).toBe("Took 6 sest. $0.0004");
    expect(right().querySelector(".sp-cost")!.textContent).toBe("est. $0.0004");
    expect(answer().classList.contains("is-short")).toBe(true);
    expect(sealState()).toBe("rest");

    // Reopen: a fresh window boots from the daemon on the newest page.
    cleanup();
    resetHer();
    await boot();
    await waitFor(() => expect(book().getAttribute("data-page")).toBe("p1"));
    expect(answer().textContent).toBe("By April 15.");
  });

  it("files a card inline; it signs once, the seal goes waiting -> signed -> rest, and the bookmark finds it", async () => {
    m.conversation.mockResolvedValue([turn("t0", "person", "Hello"), turn("t00", "athena", "Hi.")]);
    await boot();
    fireEvent.change(select(), { target: { value: "now" } });
    const stream = heldStream();
    m.conversation.mockResolvedValue([
      turn("t0", "person", "Hello"),
      turn("t00", "athena", "Hi."),
      turn("t1", "person", "Set the brief"),
      turn("t2", "athena", "Here it is.", {
        card_id: card.id,
        parts: [
          { kind: "text", text: "Here it is.", at_ms: 900 },
          { kind: "tool", name: "propose_brief", label: card.label, class: "gated", at_ms: 1000 },
          { kind: "card", card_id: card.id, at_ms: 1000 },
        ],
      }),
    ]);
    type("Set the brief");
    await stream.emit({ type: "start", turn_id: "turn_1", engine: "scripted", simulated: false });
    await stream.emit({ type: "text", delta: "Here it is." });
    await stream.emit({ type: "tool", name: "propose_brief", label: card.label, class: "gated" });
    await stream.emit({ type: "card", card });
    expect(sealState()).toBe("waiting");
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: true });
    await stream.end();
    await waitFor(() => expect(book().getAttribute("data-page")).toBe("p2"));
    expect(receipts()).toEqual(["Wrote to you", "Filed a card for your signature"]);
    expect(screen.getByText("Waits for your signature")).toBeTruthy();
    expect(document.querySelector('[data-role="card-brief"]')!.textContent).toContain("file by April, and keep every receipt");

    // the bookmark: from another page, it opens the page that holds the card
    fireEvent.change(select(), { target: { value: "p1" } });
    const mark = document.querySelector('[data-role="bookmark"]')!;
    expect(mark.textContent).toBe("1 waits for your signatureOpen its page");
    await act(async () => fireEvent.click(mark));
    expect(book().getAttribute("data-page")).toBe("p2");

    const approved: Card = { ...card, state: "approved", resolved: "2026-10-26T12:01:00Z", outcome: "The brief now reads: file by April." };
    m.decide.mockResolvedValue(approved);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign" })));
    expect(m.decide).toHaveBeenCalledTimes(1);
    expect(m.decide).toHaveBeenCalledWith(card.id, "approve");
    expect(sealState()).toBe("signed");
    expect(screen.getByText("Signed, ran once")).toBeTruthy();
    expect(document.querySelector('[data-role="card-outcome"]')!.textContent).toBe("The brief now reads: file by April.");
    expect(document.querySelector('[data-role="bookmark"]')).toBeNull();

    act(() => emitApp({ type: "card_resolved", card: approved }));
    expect(m.decide).toHaveBeenCalledTimes(1);
    await act(() => new Promise((r) => setTimeout(r, SETTLE_MS + 100)));
    expect(sealState()).toBe("rest");
  });

  it("puts a card waiting on no page of this book on its own page, which the bookmark opens", async () => {
    m.cards.mockImplementation(async (state) => (state === "waiting" ? [{ ...card, space_id: "spc_2" }] : []));
    m.conversation.mockResolvedValue([turn("t1", "person", "Hi"), turn("t2", "athena", "Hello.")]);
    await boot();
    await waitFor(() => expect(document.querySelector('[data-role="bookmark"]')).toBeTruthy());
    await act(async () => fireEvent.click(document.querySelector('[data-role="bookmark"]')!));
    expect(book().getAttribute("data-page")).toBe("waiting");
    expect(right().querySelector(".card-where")!.textContent).toBe("Garden");
  });

  it("follows a card signed in the main window, seal included", async () => {
    m.cards.mockImplementation(async (state) => (state === "waiting" ? [card] : []));
    await boot();
    await waitFor(() => expect(sealState()).toBe("waiting"));
    act(() => emitApp({ type: "card_resolved", card: { ...card, state: "approved" } }));
    expect(sealState()).toBe("signed");
  });

  it("switching project switches the book, and a switch mid-reply waits for the reply", async () => {
    m.conversation.mockImplementation(async (id) =>
      id === "spc_1" ? [turn("a1", "person", "Taxes question")] : [{ ...turn("b1", "person", "Garden question"), space_id: "spc_2" }],
    );
    m.setActiveSpace.mockImplementation(async (id) => ({ space_id: id }));
    await boot();
    expect(await screen.findByText("Taxes question", { selector: ".sp-ask" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Taxes/ }));
    await act(async () => fireEvent.click(screen.getByRole("menuitemradio", { name: /Garden/ })));
    expect(m.setActiveSpace).toHaveBeenCalledWith("spc_2");
    expect(await screen.findByText("Garden question", { selector: ".sp-ask" })).toBeTruthy();

    fireEvent.change(select(), { target: { value: "now" } });
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
    expect(await screen.findByText("Taxes question", { selector: ".sp-ask" })).toBeTruthy();
  });

  it("reloads when the other window switches the project, or ends a turn there", async () => {
    m.conversation.mockImplementation(async (id) => (id === "spc_2" ? [turn("b1", "person", "Garden question")] : []));
    await boot();
    act(() => emitApp({ type: "active_space", space_id: "spc_2" }));
    expect(await screen.findByText("Garden question", { selector: ".sp-ask" })).toBeTruthy();
    expect(m.conversation).toHaveBeenLastCalledWith("spc_2");
  });

  it("wears the look chosen in Settings, and its own two switches write that same setting", async () => {
    m.settings.mockResolvedValue({ look: { theme: "light", type_scale: "large", motion: "system" }, engine: "muse", source: "default", engines: [] });
    await boot();
    await waitFor(() => expect(document.documentElement.getAttribute("data-theme")).toBe("light"));
    act(() => emitApp({ type: "settings", look: { theme: "auto", type_scale: "standard", motion: "calm" } }));
    expect(document.documentElement.getAttribute("data-motion")).toBe("calm");
    await waitFor(() => expect(screen.getByRole("button", { name: "Calm motion" }).getAttribute("aria-pressed")).toBe("true"));

    // "auto" with no system answer reads dark here, so the switch offers light
    m.setLook.mockResolvedValue({ look: { theme: "light", type_scale: "standard", motion: "calm" }, engine: "muse", source: "default", engines: [] });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /Switch to the light look/ })));
    expect(m.setLook).toHaveBeenCalledWith({ theme: "light" });
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("labels the simulated engine, and only then", async () => {
    m.engine.mockResolvedValue({ ...live, engine: "scripted", key: "absent", simulated: true });
    await bootOnNewPage();
    expect(screen.getByText("Simulated", { selector: ".badge" })).toBeTruthy();
    expect(screen.getByText("Simulated - connect Muse in the main window for real answers")).toBeTruthy();
    act(() => emitApp({ type: "engine", status: live }));
    expect(screen.queryByText("Simulated", { selector: ".badge" })).toBeNull();
  });

  it("keeps a stopped try as its own page with its reason, and Try again asks the same words", async () => {
    await bootOnNewPage();
    const stream = heldStream();
    type("Hello?");
    await stream.emit({ type: "start", turn_id: "turn_1", engine: "muse", simulated: false });
    await stream.emit({ type: "tool", name: "recall", label: "Looked through memory", class: "auto" });
    await stream.emit({ type: "error", error: "engine_unavailable", reason: "Muse did not answer in time" });
    // the daemon kept the try (ADR 0024)
    m.conversation.mockResolvedValue([
      turn("t1", "person", "Hello?"),
      turn("t2", "athena", "", {
        stopped: "Muse did not answer in time",
        duration_ms: 9000,
        parts: [{ kind: "tool", name: "recall", label: "Looked through memory", class: "auto", at_ms: 1000 }],
      }),
    ]);
    await stream.end();
    await waitFor(() => expect(book().getAttribute("data-page")).toBe("p1"));
    expect(screen.getByText("This try stopped", { selector: ".badge" })).toBeTruthy();
    expect(receipts()).toEqual(["Looked through memory", "Stopped: Muse did not answer in time"]);
    expect(right().querySelector('[role="alert"]')!.textContent).toContain("Muse did not answer in time");
    expect(left().querySelector('[data-role="tally"]')!.textContent).toBe("Took 9 sno cost figure: this try stopped");
    expect(sealState()).toBe("rest");

    const again = heldStream();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Try again" })));
    expect(run).toHaveBeenCalledTimes(2);
    expect(run.mock.calls[1]![0]).toEqual({ text: "Hello?", space_id: "spc_1" });
    expect(book().getAttribute("data-page")).toBe("now");
    await again.end();
  });

  it("marks the same words asked after a stopped try as its second try, each page linking the other", async () => {
    m.conversation.mockResolvedValue([
      turn("t1", "person", "Which offers wait?"),
      turn("t2", "athena", "", { stopped: "Meta is rate limiting", parts: [] }),
      turn("t3", "person", "Which offers wait?"),
      turn("t4", "athena", "Two."),
    ]);
    await boot();
    expect(screen.getByText("Second try")).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /The try that stopped/ })));
    expect(book().getAttribute("data-page")).toBe("p1");
    expect(screen.getByRole("button", { name: "See her second try" })).toBeTruthy();
  });

  it("keeps a failed page on screen with Try again when the conversation cannot be read back", async () => {
    await bootOnNewPage();
    const stream = heldStream();
    type("Hello?");
    await stream.emit({ type: "error", error: "engine_unavailable", reason: "Muse did not answer in time" });
    m.conversation.mockRejectedValue(new Error("down"));
    await stream.end();
    expect(book().getAttribute("data-page")).toBe("now");
    expect(receipts()).toEqual(["Stopped: Muse did not answer in time"]);
    expect(screen.getByRole("button", { name: "Write another page" })).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Write another page" })));
    expect(composer()).toBeTruthy();
  });

  it("Stop aborts the reply, and its page says you stopped her", async () => {
    await bootOnNewPage();
    let signal: AbortSignal | undefined;
    run.mockImplementationOnce((_b, _on, s) => {
      signal = s;
      return new Promise<void>((_, reject) => s!.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))));
    });
    m.conversation.mockResolvedValue([turn("t1", "person", "Long story please")]);
    type("Long story please");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Stop" })));
    expect(signal!.aborted).toBe(true);
    await waitFor(() => expect(book().getAttribute("data-page")).toBe("p1"));
    expect(screen.getByText("You stopped her before she wrote anything.")).toBeTruthy();
  });

  it("draws a settled page from its stored parts exactly as it drew it live", async () => {
    m.cards.mockResolvedValue([card]);
    await bootOnNewPage();
    const stream = heldStream();
    type("Look into it");
    await stream.emit({ type: "text", delta: "Let me look." });
    await stream.emit({ type: "tool", name: "recall", label: "Looked through memory", class: "auto" });
    await stream.emit({ type: "text", delta: "Found **two** notes." });
    await stream.emit({ type: "tool", name: "propose_brief", label: card.label, class: "gated" });
    await stream.emit({ type: "card", card });
    await stream.emit({ type: "text", delta: "Sign it" });
    await stream.emit({ type: "text", delta: " when ready." });
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: true, cost_usd: 0.0004 });
    const kinds = () => [...answer().children].map((c) => c.className.split(" ")[0]);
    const liveKinds = kinds();
    const liveText = answer().textContent;
    const liveReceipts = receipts();
    expect(liveKinds).toEqual(["prose", "prose", "card", "prose"]);
    m.conversation.mockResolvedValue([
      turn("t1", "person", "Look into it"),
      turn("t2", "athena", "Let me look.Found **two** notes.Sign it when ready.", {
        cost_usd: 0.0004,
        card_id: card.id,
        parts: [
          { kind: "text", text: "Let me look.", at_ms: 100 },
          { kind: "tool", name: "recall", label: "Looked through memory", class: "auto", at_ms: 200 },
          { kind: "text", text: "Found **two** notes.", at_ms: 300 },
          { kind: "tool", name: "propose_brief", label: card.label, class: "gated", at_ms: 400 },
          { kind: "card", card_id: card.id, at_ms: 400 },
          { kind: "text", text: "Sign it when ready.", at_ms: 500 },
        ],
      }),
    ]);
    await stream.end();
    await waitFor(() => expect(book().getAttribute("data-page")).toBe("p1"));
    expect(kinds()).toEqual(liveKinds);
    expect(answer().textContent).toBe(liveText);
    expect(receipts()).toEqual(liveReceipts.map((r) => (r === "Writing to you" ? "Wrote to you" : r)));
    expect(answer().querySelector("strong")!.textContent).toBe("two");
  });

  it("shows report parts in her answer with the drops said, and the same after a reload", async () => {
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
    await bootOnNewPage();
    const stream = heldStream();
    type("How are the tracks doing?");
    await stream.emit({ type: "text", delta: "Here is where they stand." });
    await stream.emit({ type: "blocks", shown });
    await stream.emit({ type: "text", delta: "Most still wait for you." });
    await stream.emit({ type: "done", turn_id: "turn_1", waiting: false });
    expect(receipts()).toContain("Showed parts of the report: “Where the tracks stand”");
    const part = answer().querySelector('[data-role="report-block"]')!;
    expect(part.getAttribute("data-kind")).toBe("pipeline");
    expect(answer().querySelector('[data-role="pin"]')).toBeNull();
    expect(answer().querySelector('[data-role="dropped"] summary')!.textContent).toBe("1 part could not be shown");
    const before = answer().querySelector(".her-blocks")!.innerHTML;
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
    await waitFor(() => expect(book().getAttribute("data-page")).toBe("p1"));
    expect(answer().querySelector(".her-blocks")!.innerHTML).toBe(before);
  });

  it("draws a turn stored before parts were kept as its words and its card, with no moments", async () => {
    m.cards.mockResolvedValue([card]);
    m.conversation.mockResolvedValue([turn("t1", "person", "Brief?"), turn("t2", "athena", "Filed it.", { card_id: card.id })]);
    await boot();
    await waitFor(() => expect(answer().querySelector(".card")).toBeTruthy());
    expect([...left().querySelectorAll(".sp-rc-t")].map((t) => t.textContent)).toEqual(["", ""]);
    expect(left().querySelector('[data-role="tally"]')!.textContent).toBe("no cost figure");
  });

  it("shows a stored part this window does not know as a plain row, never nothing", async () => {
    const odd = { kind: "hologram", what: "x" } as unknown as NonNullable<Turn["parts"]>[number];
    m.conversation.mockResolvedValue([turn("t1", "athena", "Here.", { parts: [{ kind: "text", text: "Here." }, odd] })]);
    await boot();
    await waitFor(() => expect(document.querySelector(".sp-unknown")!.getAttribute("data-part")).toBe("hologram"));
    expect(screen.getByText("She spoke first")).toBeTruthy();
  });

  it("renders her words as rich text, and any HTML in them as inert text", async () => {
    m.conversation.mockResolvedValue([
      turn("t1", "person", "Steps?"),
      turn("t2", "athena", "**First:**\n- open `settings`\n- sign\n\n<img src=x onerror=alert(1)><script>alert(2)</script>"),
    ]);
    await boot();
    expect((await screen.findByText("First:")).tagName).toBe("STRONG");
    expect(screen.getByText("sign").tagName).toBe("LI");
    expect(screen.getByText("settings").tagName).toBe("CODE");
    expect(answer().textContent).toContain("<img src=x onerror=alert(1)><script>alert(2)</script>");
    expect(answer().querySelector("img, script")).toBeNull();
  });

  it("turns pages with the keys and the compact bar; the leaf turns only when motion is allowed", async () => {
    m.conversation.mockResolvedValue([turn("t1", "person", "One"), turn("t2", "athena", "A."), turn("t3", "person", "Two"), turn("t4", "athena", "B.")]);
    await boot();
    await waitFor(() => expect(book().getAttribute("data-page")).toBe("p2"));
    fireEvent.keyDown(document.body, { key: "ArrowLeft" });
    expect(book().getAttribute("data-page")).toBe("p1");
    expect(book().classList.contains("turn-back")).toBe(true);
    fireEvent.keyDown(document.body, { key: "End" });
    expect(book().getAttribute("data-page")).toBe("now");
    fireEvent.keyDown(document.body, { key: "Home" });
    expect(book().getAttribute("data-page")).toBe("p1");
    // a key typed into the field is the field's
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    fireEvent.keyDown(composer(), { key: "ArrowLeft" });
    expect(book().getAttribute("data-page")).toBe("now");

    document.documentElement.setAttribute("data-motion", "calm");
    fireEvent.keyDown(document.body, { key: "Home" });
    expect(book().getAttribute("data-page")).toBe("p1");
    expect(book().classList.contains("turn-back")).toBe(false);
    expect(left().querySelector(".sp-ask")!.textContent).toBe("One"); // the still form carries the same page
  });

  it("Shift+Enter is a new line, not a send", async () => {
    await bootOnNewPage();
    fireEvent.change(composer(), { target: { value: "line one" } });
    fireEvent.keyDown(composer(), { key: "Enter", shiftKey: true });
    expect(run).not.toHaveBeenCalled();
  });
});
