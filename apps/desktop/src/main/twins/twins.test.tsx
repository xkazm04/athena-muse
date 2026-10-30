import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { parseHash, toHash, type Route } from "../route";
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
  it.each(["#twins", "#twin/new", `#twin/${desk!.id}`, `#twin/${partners!.id}/voice`, `#twin/${desk!.id}/mission/ms_1`, `#twin/${desk!.id}/draft/dr_1`])(
    "%s round-trips",
    (hash) => expect(toHash(parseHash(hash))).toBe(hash),
  );

  it("reads the nested pages and a new twin", () => {
    expect(parseHash("#twin/new")).toEqual({ view: "twin", id: null });
    expect(parseHash("#/twin/tw_1/mission/ms_3")).toEqual({ view: "twin_mission", id: "tw_1", mission: "ms_3" });
    expect(parseHash("#twin/tw_1/draft/dr_2")).toEqual({ view: "twin_draft", id: "tw_1", draft: "dr_2" });
    expect(parseHash("#twin/tw_1/voice")).toEqual({ view: "twin_voice", id: "tw_1" });
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
