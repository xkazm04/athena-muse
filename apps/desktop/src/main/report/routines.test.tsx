import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import type { Routine, RoutineRun, Site, SpaceSummary } from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import { byKind, derivedRows, FIXTURE_ROUTINES, ROUTINE_STATES, ROUTINES_NOW, ROUTINES_SPACE, runsOf } from "../../preview/routineStates";
import { Shell } from "../App";
import { toHash, type Route } from "../route";
import { resetMain, ROUTINES_IDLE, useMain, type RoutinesState } from "../store";
import { Routines, RoutinesBody, STRIP_TITLE, type RoutinesBodyProps } from "./Routines";

vi.mock("../../lib/api");
vi.mock("../../lib/windows");
vi.mock("../../theme/Backdrop", () => ({ Backdrop: () => null }));
vi.mock("../../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/daemon")>()),
  subscribe: vi.fn(() => () => undefined),
}));

const space = (over: Partial<SpaceSummary> = {}): SpaceSummary => ({
  id: ROUTINES_SPACE,
  name: "Music channel (simulated)",
  brief: "",
  apps: [],
  hue: 210,
  created: "2026-10-26T10:00:00Z",
  updated: "2026-10-26T10:00:00Z",
  counts: { episodes: 0, facts: 0 },
  ...over,
});

const ready = (list: Routine[]): RoutinesState => ({ ...ROUTINES_IDLE, load: "ready", list });

function body(over: Partial<RoutinesBodyProps> = {}) {
  const props: RoutinesBodyProps = {
    state: ready(FIXTURE_ROUTINES),
    now: ROUTINES_NOW,
    onChange: vi.fn(async () => undefined),
    onRun: vi.fn(async () => undefined),
    onRuns: vi.fn(async () => []),
    onSignIn: vi.fn(),
    onRetry: vi.fn(),
    ...over,
  };
  render(<RoutinesBody {...props} />);
  return props;
}

const rows = () => [...document.querySelectorAll<HTMLElement>('[data-role="routine"]')];
const lineOf = (row: HTMLElement) => row.querySelector('[data-role="routine-line"]')!.textContent;

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => (resolve = res));
  return { promise, resolve };
}

beforeEach(() => {
  resetMain();
  vi.mocked(api.setActiveSpace).mockImplementation(async (id) => ({ space_id: id }));
  vi.mocked(api.spaceSites).mockResolvedValue([]);
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("what Athena does on her own", () => {
  it("draws one row per routine the daemon generated, each last run in plain words with its note as given", () => {
    body();
    expect(screen.getByRole("heading", { name: STRIP_TITLE })).toBeTruthy();
    expect(rows().map((r) => r.dataset.kind)).toEqual(FIXTURE_ROUTINES.map((r) => r.kind));
    const [watch, inbox, stats, outreach] = rows();
    // partial at its spending limit: what it spent (0.30) is past what it may (0.25), both the daemon's
    expect(lineOf(watch!)).toBe("stopped at its spending limit 12 min ago - 4 creators to read, found 0, kept 0");
    expect(within(watch!).getByText("It stopped at its spending limit of $0.25 (est.).")).toBeTruthy();
    expect(watch!.querySelector(".rt-spent")!.textContent).toBe("$0.30 est.");
    expect(lineOf(stats!)).toBe("ran 12 min ago - found 2, kept 2");
    expect(within(stats!).getByText("Read 2 figures.")).toBeTruthy();
    expect(stats!.querySelector(".rt-spent")!.textContent).toBe("under $0.01 est.");
    expect(lineOf(inbox!)).toBe("skipped 12 min ago: nothing to do");
    expect(within(inbox!).getByText("set the mailbox address")).toBeTruthy();
    // no price given: no spend shown, never "$0.00"
    expect(inbox!.querySelector(".rt-spent")!.textContent).toBe("");
    expect(lineOf(outreach!)).toBe("skipped 12 min ago: nothing to do");
    // when it runs next, from the daemon's next_at only
    expect(watch!.querySelector('[data-role="routine-next"]')!.textContent).toBe("next in 6 h");
    expect(inbox!.querySelector('[data-role="routine-next"]')!.textContent).toBe("paused");
    expect(outreach!.querySelector('[data-role="routine-next"]')!.textContent).toBe("next any moment");
    expect(rows().map((r) => r.dataset.outcome)).toEqual(["partial", "skipped", "ran", "skipped"]);
  });

  it("says each reason and outcome its own way (the ones the fixture cannot make are derived from its rows)", () => {
    body({ state: ready(derivedRows()) });
    const by = Object.fromEntries(rows().map((r, i) => [derivedRows()[i]!.id.split("-").at(-1)!, lineOf(r)]));
    expect(by).toEqual({
      no_browser: "skipped 12 min ago: her browser is closed",
      live_turn: "skipped 12 min ago: you were talking with her",
      signed_out: "skipped 12 min ago: sign in to the mailbox again",
      no_twin: "skipped 12 min ago: no twin set up for this project",
      running: "skipped 12 min ago: it was already running",
      paused: "skipped 12 min ago: it is paused",
      no_engine: "skipped 12 min ago: Athena has no engine to think with",
      partial: "stopped part way 12 min ago - 4 creators to read, found 3, kept 1, 1 draft for you",
      ran: "ran 12 min ago - found 3, kept 1, 1 draft for you",
      failed: "did not finish 12 min ago",
    });
  });

  it("Pause and Resume send the routine's new state", async () => {
    const props = body();
    const [watch, inbox] = rows();
    await act(async () => fireEvent.click(watch!.querySelector('[data-role="routine-pause"]')!));
    expect(props.onChange).toHaveBeenLastCalledWith(byKind("watch").id, { state: "paused" });
    expect(inbox!.querySelector('[data-role="routine-pause"]')!.textContent).toBe("Resume");
    await act(async () => fireEvent.click(inbox!.querySelector('[data-role="routine-pause"]')!));
    expect(props.onChange).toHaveBeenLastCalledWith(byKind("inbox").id, { state: "on" });
  });

  it("asks an inbox without its page for the mailbox address and sends it; a stats routine with one is not asked", async () => {
    const props = body();
    const fields = document.querySelectorAll('[data-role="routine-url"]');
    expect(fields).toHaveLength(1);
    const form = fields[0] as HTMLElement;
    expect(form.closest('[data-role="routine"]')!.getAttribute("data-kind")).toBe("inbox");
    fireEvent.change(within(form).getByLabelText("Mailbox address"), { target: { value: " https://mail.example.test/inbox " } });
    await act(async () => fireEvent.submit(form));
    expect(props.onChange).toHaveBeenCalledWith(byKind("inbox").id, { url: "https://mail.example.test/inbox" });
    cleanup();
    const statsNoUrl = { ...byKind("stats"), url: undefined };
    body({ state: ready([statsNoUrl]) });
    expect(screen.getByLabelText("Analytics page")).toBeTruthy();
  });

  it("a refusal stays on its row and says why, verbatim", async () => {
    body({ onChange: vi.fn().mockRejectedValue(new DaemonError(400, "bad_request", "a routine's page is a web address starting with http:// or https://")) });
    const inbox = rows()[1]!;
    fireEvent.change(within(inbox).getByLabelText("Mailbox address"), { target: { value: "mail" } });
    await act(async () => fireEvent.submit(inbox.querySelector("form")!));
    expect(within(inbox).getByRole("alert").textContent).toMatch(/web address/);
  });

  it("a signed-out run offers the project's own sign-in", () => {
    const props = body({ state: ready(derivedRows()) });
    const links = document.querySelectorAll('[data-role="routine-sign-in"]');
    expect(links).toHaveLength(1);
    expect(links[0]!.closest('[data-role="routine"]')!.getAttribute("data-reason")).toBe("signed_out");
    fireEvent.click(links[0]!);
    expect(props.onSignIn).toHaveBeenCalled();
  });

  it("its last runs fold open as a small table read from the daemon", async () => {
    const stats = byKind("stats");
    const onRuns = vi.fn(async () => runsOf(stats.id));
    body({ onRuns });
    const fold = rows()[2]!.querySelector<HTMLDetailsElement>('[data-role="routine-runs"]')!;
    await act(async () => {
      fold.open = true;
      fireEvent(fold, new Event("toggle"));
    });
    expect(onRuns).toHaveBeenCalledWith(stats.id);
    const cells = [...fold.querySelectorAll("tbody tr")].map((tr) => tr.children[1]!.textContent);
    expect(cells).toEqual(["ran - found 2, kept 2Read 2 figures.", "skipped: her browser is closedHer browser is not open."]);
    expect([...fold.querySelectorAll("th")].map((th) => th.textContent)).toEqual(["When", "What happened", "Spent"]);
  });

  it("folds to its head, and a problem says why with a way to try again", () => {
    body({ folded: true });
    expect(rows()).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(rows()).toHaveLength(FIXTURE_ROUTINES.length);
    cleanup();
    const props = body({ state: { ...ROUTINES_IDLE, load: "problem", problem: "not reachable" } });
    expect(screen.getByRole("alert").textContent).toContain("not reachable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(props.onRetry).toHaveBeenCalled();
  });

  it("never says the words the screen does not use, in any state", () => {
    const banned = /\b(records?|cadences?|ceilings?|skip reasons?|mcp|fixtures?|models?|prompts?|nodes?|slots?|hands|bindings?|specs?|blocks?|kinds?)\b/i;
    for (const s of ROUTINE_STATES) {
      body({ state: s.state });
      for (const d of document.querySelectorAll("details")) d.open = true;
      const text = document.body.textContent ?? "";
      expect(text.match(banned)?.[0], s.name).toBeUndefined();
      cleanup();
    }
  });
});

describe("the strip through the daemon", () => {
  it("Run now is busy while it runs, then the run it recorded is the row's last run", async () => {
    vi.mocked(api.spaceRoutines).mockResolvedValue(structuredClone(FIXTURE_ROUTINES));
    const d = deferred<RoutineRun>();
    vi.mocked(api.runRoutine).mockReturnValueOnce(d.promise);
    await act(async () => render(<Routines space={space()} />));
    expect(api.spaceRoutines).toHaveBeenCalledWith(ROUTINES_SPACE);
    const outreach = () => rows()[3]!;
    const btn = () => outreach().querySelector<HTMLButtonElement>('[data-role="routine-run-now"]')!;
    await act(async () => fireEvent.click(btn()));
    expect(api.runRoutine).toHaveBeenCalledWith(byKind("outreach").id);
    expect(btn().textContent).toBe("Running...");
    expect(btn().disabled).toBe(true);
    expect(outreach().getAttribute("aria-busy")).toBe("true");
    expect(lineOf(outreach())).toBe("running now...");
    const now = new Date().toISOString();
    await act(async () =>
      d.resolve({ id: "run_new", routine_id: byKind("outreach").id, started: now, ended: now, outcome: "ran", found: 2, kept: 1, cards: 1, spent_usd: 0.04, note: "Drafted 1 offer for the person to sign." }),
    );
    expect(btn().textContent).toBe("Run now");
    expect(lineOf(outreach())).toBe("ran just now - found 2, kept 1, 1 draft for you");
    expect(within(outreach()).getByText("Drafted 1 offer for the person to sign.")).toBeTruthy();
    expect(outreach().querySelector(".rt-spent")!.textContent).toBe("$0.04 est.");
  });

  it("Pause goes to the daemon and its answer replaces the row", async () => {
    vi.mocked(api.spaceRoutines).mockResolvedValue(structuredClone(FIXTURE_ROUTINES));
    const watch = byKind("watch");
    vi.mocked(api.changeRoutine).mockResolvedValue({ ...watch, state: "paused", next_at: undefined });
    await act(async () => render(<Routines space={space()} />));
    await act(async () => fireEvent.click(rows()[0]!.querySelector('[data-role="routine-pause"]')!));
    expect(api.changeRoutine).toHaveBeenCalledWith(watch.id, { state: "paused" });
    expect(rows()[0]!.dataset.state).toBe("paused");
    expect(rows()[0]!.querySelector('[data-role="routine-pause"]')!.textContent).toBe("Resume");
  });

  it("a routine event changes that one row in place: nothing is read again, the others stay as they were", async () => {
    vi.mocked(api.spaceRoutines).mockResolvedValue(structuredClone(FIXTURE_ROUTINES));
    await act(async () => render(<Routines space={space()} />));
    const before = rows();
    const stats = byKind("stats");
    const ran: Routine = { ...stats, last_run: { ...stats.last_run!, id: "run_after", found: 5, kept: 5, note: "Read 5 figures." } };
    await act(async () => useMain.getState().handleEvent({ type: "routine", space_id: ROUTINES_SPACE, routine: ran }));
    expect(api.spaceRoutines).toHaveBeenCalledTimes(1);
    const after = rows();
    expect(after).toHaveLength(before.length);
    after.forEach((r, i) => expect(r).toBe(before[i]));
    expect(lineOf(after[2]!)).toMatch(/^ran .+ - found 5, kept 5$/);
    expect(lineOf(after[0]!)).toMatch(/^stopped at its spending limit/);
    // another project's routine changes nothing here
    await act(async () => useMain.getState().handleEvent({ type: "routine", space_id: "spc_other", routine: { ...ran, space_id: "spc_other" } }));
    expect(lineOf(rows()[2]!)).toMatch(/found 5, kept 5$/);
  });
});

describe("the strip on the project's page", () => {
  function start(spaces: SpaceSummary[], route: Route) {
    window.location.hash = toHash(route);
    useMain.setState({ spaces, spacesLoad: "ready", route });
    render(<Shell />);
  }

  it("a project without routines shows no strip", async () => {
    vi.mocked(api.spaceRoutines).mockResolvedValue([]);
    await act(async () => start([space()], { view: "project", id: ROUTINES_SPACE }));
    expect(api.spaceRoutines).toHaveBeenCalledWith(ROUTINES_SPACE);
    expect(document.querySelector('[data-role="routines"]')).toBeNull();
    expect(screen.queryByText(STRIP_TITLE)).toBeNull();
  });

  it("sits under the report; a signed-out run brings the project's own 'Sign in again' to hand", async () => {
    const signedOut = derivedRows().find((r) => r.last_run?.reason === "signed_out")!;
    vi.mocked(api.spaceRoutines).mockResolvedValue([{ ...signedOut, space_id: ROUTINES_SPACE }]);
    const site: Site = {
      origin: "https://mail.example.test",
      label: "Business mail",
      probe_url: "https://mail.example.test/inbox",
      access: "signed_out",
      blocks: ["Read the mailbox for replies"],
    };
    vi.mocked(api.spaceSites).mockResolvedValue([site]);
    await act(async () => start([space({ kinds: undefined })], { view: "project", id: ROUTINES_SPACE }));
    const strip = document.querySelector('[data-role="routines"]')!;
    expect(strip).toBeTruthy();
    fireEvent.click(strip.querySelector('[data-role="routine-sign-in"]')!);
    const again = document.querySelector('[data-role="blockers"] [data-role="sign-in-again"]');
    expect(again).toBeTruthy();
    expect(document.activeElement).toBe(again);
  });
});
