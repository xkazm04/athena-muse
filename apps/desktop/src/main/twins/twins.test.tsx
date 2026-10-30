import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { parseHash, toHash, type Route } from "../route";
import { EntryPage, ruleFor } from "./Entry";
import { createExampleIo } from "./example";
import { TWIN_FIXTURE as fx } from "./fixture/twins";
import { stateOf, type TwinStateId } from "./states";
import { createTwinsStore } from "./store";
import { TwinsView, type TwinRoute } from "./Twins";

afterEach(cleanup);

const [desk, family, partners] = fx.page.twins;
// Client desk, as the daemon left it: a reply held below the bar, and a money ask handed back
const invoice = desk!.waiting.find((d) => d.subject === "Re: Invoice 2026-031")!;
const scripted = desk!.missions.filter((m) => m.beats.length);
const rush = desk!.missions.find((m) => m.state === "handed_back")!;

describe("the twins routes", () => {
  it.each(["#twins", "#twin/new", `#twin/${desk!.id}`, `#twin/${partners!.id}/voice`, `#twin/${desk!.id}/entry`, `#twin/${desk!.id}/mission/ms_1`, `#twin/${desk!.id}/draft/dr_1`])(
    "%s round-trips",
    (hash) => expect(toHash(parseHash(hash))).toBe(hash),
  );

  it("reads the nested pages and a new twin", () => {
    expect(parseHash("#twin/new")).toEqual({ view: "twin", id: null });
    expect(parseHash("#/twin/tw_1/mission/ms_3")).toEqual({ view: "twin_mission", id: "tw_1", mission: "ms_3" });
    expect(parseHash("#twin/tw_1/draft/dr_2")).toEqual({ view: "twin_draft", id: "tw_1", draft: "dr_2" });
    expect(parseHash("#twin/tw_1/voice")).toEqual({ view: "twin_voice", id: "tw_1" });
    expect(parseHash("#twin/tw_1/entry")).toEqual({ view: "twin_entry", id: "tw_1" });
    expect(parseHash("#twin")).toEqual({ view: "twins" });
    // a nested page with nothing after it falls back to the twin itself
    expect(parseHash("#twin/tw_1/mission")).toEqual({ view: "twin", id: "tw_1" });
  });
});

/** Draws one named state of the example; returns where the page asked to go. */
function show(id: TwinStateId, route?: TwinRoute) {
  const io = createExampleIo(fx, { pace: 0 });
  const store = createTwinsStore(io, { pollMs: 0 });
  store.getState().useExample(io);
  const shown = stateOf(id);
  store.setState(shown.state);
  const go = vi.fn<(r: Route) => void>();
  const view = render(<TwinsView route={route ?? shown.route} top={(extra) => <header>{extra}</header>} navigate={go} store={store.getState()} />);
  return { go, store, view };
}

describe("the overview", () => {
  it("shows the stat strip, a document per twin, what waits and the ledger, labelled as invented", () => {
    show("overview-today");
    expect(screen.getAllByText("Invented example").length).toBeGreaterThan(0);
    expect(document.querySelectorAll('[data-role="stat-tile"]')).toHaveLength(6);
    expect(document.querySelectorAll('[data-role="wallet-doc"]')).toHaveLength(3);
    expect(document.querySelectorAll('[data-role="ledger-row"]')).toHaveLength(3);
    expect(document.querySelectorAll('[data-role="waiting-card"]')).toHaveLength(4);
  });

  it("opens a waiting card's draft on its own page, and a handed-back card's mission", () => {
    const { go } = show("overview-today");
    fireEvent.click(screen.getByRole("button", { name: /Re: Invoice 2026-031/ }));
    expect(go).toHaveBeenLastCalledWith({ view: "twin_draft", id: desk!.id, draft: invoice.id });
    fireEvent.click(screen.getByRole("button", { name: /handed back to you/ }));
    expect(go).toHaveBeenLastCalledWith({ view: "twin_mission", id: desk!.id, mission: rush.id });
  });

  it("opens a twin in place from its ledger row, and its beat dots open the mission's script", () => {
    const { go } = show("overview-today");
    fireEvent.click(document.querySelectorAll('[data-role="ledger-row"]')[0]!);
    expect(go).toHaveBeenLastCalledWith({ view: "twin", id: desk!.id });
    cleanup();
    const opened = show("overview-row-open");
    // its rehearsal has no script; each mission on Gmail has its beats, counted by the daemon
    const dots = document.querySelectorAll('[data-role="beat-dots"]');
    expect(dots).toHaveLength(scripted.length);
    expect(dots[0]!.textContent).toContain("3 of 4");
    fireEvent.click(dots[0]!);
    expect(opened.go).toHaveBeenLastCalledWith({ view: "twin_mission", id: desk!.id, mission: scripted[0]!.id });
  });

  it("says why a twin is paused, and takes it live again with one press", () => {
    const { store } = show("overview-needs-sign-in");
    expect(screen.getByText(family!.paused_because!)).toBeTruthy();
    // the person paused it, and Gmail is still signed in: no sign-in is asked for
    expect(screen.queryByRole("button", { name: /Sign in with Google/ })).toBeNull();
    const resume = vi.fn();
    cleanup();
    render(
      <TwinsView route={{ view: "twin", id: family!.id }} top={() => null} navigate={vi.fn()} store={{ ...store.getState(), resume }} />,
    );
    fireEvent.click(document.querySelector('[data-role="resume"]')!);
    expect(resume).toHaveBeenCalledWith(family!.id);
  });

  it("shows a failed load as a problem with a retry, never as no twins", () => {
    show("overview-error");
    expect(screen.getByRole("alert").textContent).toMatch(/could not be loaded/);
    expect(screen.queryByText(/No twins yet/)).toBeNull();
  });

  it("marks the stats that moved after a go-live and stamps the new document", () => {
    show("overview-after-golive");
    expect(screen.getByText(/was 1/)).toBeTruthy();
    expect(screen.getAllByText("Issued today").length).toBe(1);
  });
});

describe("the setup", () => {
  it("lights the section her question is about, with her pencil and an ink button", () => {
    show("setup-f3");
    const lit = document.querySelector('[data-role="section-lit"]')!;
    expect(lit.className).toContain("sec--voice");
    expect(document.querySelectorAll('.doc [data-role="piece-pencil"]').length).toBe(5);
    expect(screen.getByRole("heading", { name: "Is that a bit too casual for a first message to a stranger?" })).toBeTruthy();
    expect(document.querySelectorAll('[data-role="suggestion"]')).toHaveLength(3);
  });

  it("offers 'That's enough, rehearse it' once the twin is ready", () => {
    show("setup-f9");
    expect(screen.getByRole("button", { name: "That's enough, rehearse it" }).getAttribute("data-role")).toBe("exit");
  });

  it("opens the voice page from the voice section's 'sounds like' line", () => {
    const { go } = show("setup-f3");
    fireEvent.click(document.querySelector('[data-role="sounds-like"]')!);
    expect(go).toHaveBeenLastCalledWith({ view: "twin_voice", id: partners!.id });
  });

  it("stamps the held reply with how sure it was against the bar and its risk list", () => {
    show("rehearsal-held");
    const held = document.querySelector('[data-turn="t3"]')!;
    expect(within(held as HTMLElement).getByText("Held")).toBeTruthy();
    expect(held.textContent).toMatch(/How sure it was: 77 · your bar 80/);
    expect(held.textContent).toMatch(/exclusive rights/);
    expect(document.querySelector(".is-hit")!.textContent).toMatch(/exclusive rights/);
  });

  it("presses the seal when it goes live", () => {
    show("golive");
    expect(document.querySelector('[data-role="seal"]')!.getAttribute("aria-label")).toBe("Issued 29 Oct 2026");
  });

  it("opens an issued twin as its document once the person left its setup", () => {
    const { store } = show("golive");
    const closeSetup = vi.fn();
    const live = { ...store.getState(), page: fx.pageAfter, closeSetup };
    cleanup();
    render(<TwinsView route={{ view: "twins" }} top={() => null} navigate={vi.fn()} store={live} />);
    expect(closeSetup).toHaveBeenCalledTimes(1);
    cleanup();
    const left = { ...live, setup: { ...live.setup, sealed: false } };
    render(<TwinsView route={{ view: "twin", id: fx.setup.twinId }} top={() => null} navigate={vi.fn()} store={left} />);
    expect(document.querySelector(".tw-frame--setup")).toBeNull();
    expect(document.querySelector('[data-role="give-mission"]')).toBeTruthy();
  });
});

describe("the new entry", () => {
  const threads = fx.threads[desk!.id]!.threads;
  const goals = fx.goals[desk!.id]!;
  const key = `${desk!.id}|${goals.thread}`;

  function entry(over: Partial<Parameters<typeof EntryPage>[0]> = {}) {
    const go = vi.fn<(r: Route) => void>();
    const onGoals = vi.fn();
    const onStart = vi.fn(async () => ({ mission: { ...desk!.missions[0]!, id: "ms_new" }, problem: "" }));
    render(
      <div data-twins-view="passport">
        <EntryPage
          twin={desk!}
          entry={{ load: "ready", threads }}
          goals={{ [key]: { load: "ready", goals: goals.goals } }}
          simulated
          now={new Date(fx.now)}
          go={go}
          onGoals={onGoals}
          onStart={onStart}
          {...over}
        />
      </div>,
    );
    return { go, onGoals, onStart };
  }

  it("is given from the opened document's entries", () => {
    const { go } = show("overview-row-open");
    fireEvent.click(document.querySelector('[data-role="give-mission"]')!);
    expect(go).toHaveBeenLastCalledWith({ view: "twin_entry", id: desk!.id });
  });

  it("lists the conversations where they wrote last first; one with an open mission cannot be picked", () => {
    entry();
    const rows = [...document.querySelectorAll<HTMLButtonElement>('[data-role="entry-thread"]')];
    const theirs = threads.filter((t) => t.theirs_last).map((t) => t.id);
    expect(rows.slice(0, theirs.length).map((r) => r.dataset.id)).toEqual(theirs);
    const busy = new Set(desk!.missions.filter((m) => m.state === "open").map((m) => m.thread));
    for (const r of rows) expect(r.disabled).toBe(busy.has(r.dataset.id!));
    expect(screen.getByText(/Choose who it is with, on the left/)).toBeTruthy();
    expect((screen.getByRole("button", { name: /Start the mission/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("starts the mission on the conversation in the person's words, with her pencil to take from, and opens it", async () => {
    const { go, onGoals, onStart } = entry();
    fireEvent.click(document.querySelector(`[data-role="entry-thread"][data-id="${goals.thread}"]`)!);
    expect(onGoals).toHaveBeenCalledWith({ thread: goals.thread });
    const pencil = document.querySelectorAll('[data-role="entry-suggestion"]');
    expect([...pencil].map((b) => b.textContent)).toEqual(goals.goals);
    expect(screen.getByText("simulated")).toBeTruthy();
    // the rule its first message meets: it wrote last there, so its next message is a reply
    expect(document.querySelector('[data-role="entry-rule"]')!.textContent).toMatch(/a reply: on Auto it sends on its own when it is at least 80 sure/);
    fireEvent.click(pencil[1]!);
    expect((screen.getByLabelText("The goal, in your words") as HTMLTextAreaElement).value).toBe(goals.goals[1]);
    fireEvent.change(screen.getByLabelText("The goal, in your words"), { target: { value: "Get Oren's sign-off by Friday" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /Start the mission/ })));
    expect(onStart).toHaveBeenCalledWith({ thread: goals.thread, goal: "Get Oren's sign-off by Friday" });
    expect(go).toHaveBeenLastCalledWith({ view: "twin_mission", id: desk!.id, mission: "ms_new" });
  });

  it("writes to someone new as a first message, and keeps the daemon's refusal on the slip", async () => {
    const onStart = vi.fn(async () => ({ problem: "Gmail is not connected; sign in with Google again first." }));
    const { go, onGoals } = entry({ onStart });
    fireEvent.change(screen.getByLabelText("Their address"), { target: { value: "kai@moss" } });
    fireEvent.click(screen.getByRole("button", { name: "Write to them" }));
    expect(screen.getByRole("alert").textContent).toMatch(/one address/);
    fireEvent.change(screen.getByLabelText("Their address"), { target: { value: "kai@moss.example" } });
    fireEvent.click(screen.getByRole("button", { name: "Write to them" }));
    expect(onGoals).toHaveBeenCalledWith({ to: "kai@moss.example" });
    expect(document.querySelector('[data-role="entry-rule"]')!.textContent).toMatch(/a first message: on Assist it waits for your signature/);
    fireEvent.change(screen.getByLabelText("The goal, in your words"), { target: { value: "Ask Kai for a call" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /Start the mission/ })));
    expect(onStart).toHaveBeenCalledWith({ thread: "kai@moss.example", goal: "Ask Kai for a call" });
    expect(screen.getByRole("alert").textContent).toMatch(/Gmail is not connected/);
    expect(go).not.toHaveBeenCalled();
  });

  it("shows the task inbox at work on the document: what it took, and the lines it left alone", () => {
    const { store } = show("overview-row-open");
    const page = store.getState().page!;
    const unplaced = "'Morgan: Ask about the invoice': no recent conversation with 'Morgan'; write their address instead";
    const withInbox = {
      ...desk!,
      missions: desk!.missions.map((m, i) => (i === 0 ? { ...m, source: "notion" as const } : m)),
      inbox: { page: "9".repeat(32), title: "Twin inbox", taken: 2, unplaced: [unplaced], checked_at: fx.now },
    };
    cleanup();
    render(
      <TwinsView
        route={{ view: "twin", id: desk!.id }}
        top={() => null}
        navigate={vi.fn()}
        store={{ ...store.getState(), page: { ...page, twins: page.twins.map((t) => (t.id === desk!.id ? withInbox : t)) } }}
      />,
    );
    const line = document.querySelector('[data-role="inbox"]')!;
    expect(line.textContent).toMatch(/Task inbox reads .Twin inbox. · 2 taken · read just now/);
    expect(line.textContent).toMatch(/1 line it could not place/);
    expect(line.textContent).toContain(unplaced);
    expect(screen.getAllByText("from your inbox")).toHaveLength(1);
  });

  it("says the rule plainly for a paused twin and for each level", () => {
    const paused = fx.page.twins.find((t) => t.state === "paused")!;
    expect(ruleFor(paused, { to: "a@b.example" })).toMatch(/paused, so nothing goes out/);
    expect(ruleFor(desk!, null)).toMatch(/depends on who it is with/);
    expect(ruleFor({ ...desk!, channels: [] }, null)).toMatch(/no Gmail/);
  });
});

describe("the nested pages", () => {
  it("lays a draft beside the message it answers, and signs it in the person's words", async () => {
    const { store, go } = show("draft");
    expect(screen.getByText(desk!.waiting[0]!.answers!)).toBeTruthy();
    expect(document.querySelector('[data-role="draft-page"]')!.textContent).toMatch(/74 is below your bar of 80/);
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Your version"), { target: { value: "Thanks, Friday is fine." } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign and send yours" })));
    expect(store.getState().done[desk!.waiting[0]!.id]).toBe("signed");
    expect(go).toHaveBeenLastCalledWith({ view: "twins" });
  });

  it("stays on the draft and says the daemon's problem when the send fails", async () => {
    const { store, go } = show("draft");
    const sign = vi.fn(async () => "Gmail did not send it: refused");
    cleanup();
    render(
      <TwinsView route={stateOf("draft").route} top={() => null} navigate={go} store={{ ...store.getState(), sign }} />,
    );
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign and send" })));
    expect(sign).toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toMatch(/Gmail did not send it: refused/);
    expect(go).not.toHaveBeenCalledWith({ view: "twins" });
  });

  it("draws a mission as its script of beats beside its turns", () => {
    show("mission");
    const beats = document.querySelectorAll(".beat");
    expect(beats).toHaveLength(4);
    expect(beats[2]!.getAttribute("data-now")).toBe("true");
    expect(screen.getByText("waits for your signature")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Open the draft that waits/ })).toBeTruthy();
  });

  it("shows its voice: their message, its reply now, and what changed since", () => {
    show("voice");
    const page = document.querySelector('[data-role="voice-page"]')!;
    const sounds = fx.previews[partners!.id]!;
    expect(page.querySelector('[data-role="preview-inbound"]')!.textContent).toBe(sounds.inbound);
    expect(page.querySelector('[data-role="preview-text"]')!.textContent).toBe(sounds.text);
    expect(page.querySelector('[data-role="preview-changed"]')!.textContent).toMatch(/rewrote in your own words/);
    expect(page.textContent).toMatch(/from 4 of your mails/);
  });

  it("says plainly when a draft no longer waits", () => {
    show("overview-today", { view: "twin_draft", id: desk!.id, draft: "dr_404" });
    expect(screen.getByRole("alert").textContent).toMatch(/no longer waits/);
  });
});
