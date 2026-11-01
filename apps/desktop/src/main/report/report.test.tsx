import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import type { ReportView, SpaceSummary } from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import {
  FIXTURE,
  FIXTURE_LATER,
  FIXTURE_NOW,
  REPORT_STATES,
  composedView,
  droppedView,
  emptyQueueView,
  playerView,
} from "../../preview/reportStates";
import { Shell } from "../App";
import { toHash, type Route } from "../route";
import { REPORT_IDLE, resetMain, useMain, type ReportState } from "../store";
import { creatorName, youtubeId } from "./format";
import { Report, ReportBody, type ReportBodyProps } from "./Report";

vi.mock("../../lib/api");
vi.mock("../../lib/windows");
vi.mock("../../theme/Backdrop", () => ({ Backdrop: () => null }));
vi.mock("../../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/daemon")>()),
  subscribe: vi.fn(() => () => undefined),
}));

const SPACE_ID = FIXTURE.values["d-queue"]!.items![0]!.space_id;

const space = (over: Partial<SpaceSummary> = {}): SpaceSummary => ({
  id: SPACE_ID,
  name: "Music channel (simulated)",
  brief: "",
  apps: [],
  hue: 210,
  created: "2026-10-26T10:00:00Z",
  updated: "2026-10-26T10:00:00Z",
  counts: { episodes: 0, facts: 0 },
  kinds: ["creator", "track", "thread", "agreement", "file", "render", "release", "stat"],
  ...over,
});

const ready = (view: ReportView, over: Partial<ReportState> = {}): ReportState => ({ ...REPORT_IDLE, load: "ready", view, ...over });

function body(over: Partial<ReportBodyProps> = {}) {
  const props: ReportBodyProps = {
    state: ready(FIXTURE),
    now: FIXTURE_NOW,
    genres: ["lo-fi"],
    onRetry: vi.fn(),
    onRecompose: vi.fn(),
    onPin: vi.fn(async () => undefined),
    onVerdict: vi.fn(async () => undefined),
    onDecide: vi.fn(),
    ...over,
  };
  render(<ReportBody {...props} />);
  return props;
}

const blocks = () => [...document.querySelectorAll<HTMLElement>('[data-role="report-block"]')];
const blockOf = (id: string) => {
  const b = FIXTURE.spec.blocks.find((x) => x.id === id)!;
  return blocks().find((el) => el.getAttribute("aria-labelledby") === `rp-h-${b.id}`)!;
};

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  resetMain();
  vi.mocked(api.setActiveSpace).mockImplementation(async (id) => ({ space_id: id }));
  vi.mocked(api.spaceSites).mockResolvedValue([]);
  vi.mocked(api.spaceRecords).mockResolvedValue(FIXTURE.values["d-tracks"]!.items!);
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("the report", () => {
  it("renders every part the daemon's view holds, in its order, each as its own sort", () => {
    body();
    expect(blocks().map((b) => b.dataset.kind)).toEqual(FIXTURE.spec.blocks.map((b) => b.kind));
    expect(screen.getByRole("heading", { name: FIXTURE.spec.title })).toBeTruthy();
    expect(screen.getByText("Athena has not arranged this yet")).toBeTruthy();
    for (const b of FIXTURE.spec.blocks) expect(blockOf(b.id).style.gridColumn).toBe(`span ${b.span}`);
  });

  it("shows exactly the daemon's figures: no number is worked out on screen", () => {
    body();
    const v = FIXTURE.values;
    const tile = (id: string) => within(blockOf(id)).getByText((_, el) => el?.tagName === "B" && !!el.closest('[data-role="stat-tile"]')).textContent;
    expect(tile("d-creators")).toBe(String(v["d-creators"]!.count));
    expect(tile("d-file")).toBe(String(v["d-file"]!.count));
    const stages = [...blockOf("d-pipeline").querySelectorAll(".rp-funnel__row")].map((r) => [
      r.querySelector(".rp-funnel__label")!.textContent,
      r.querySelector(".rp-funnel__n")!.textContent,
    ]);
    expect(stages).toEqual(v["d-pipeline"]!.stages!.map((s) => [s.label, String(s.count)]));
    const series = v["d-views"]!.series!;
    expect(blockOf("d-views").querySelector(".rp-spark__head b")!.textContent).toBe(String(series[series.length - 1]!.v));
    expect(blockOf("d-queue").querySelectorAll('[data-role="queue-item"]').length).toBe(v["d-queue"]!.items!.length);
    expect(blockOf("d-tracks").querySelectorAll("tbody tr").length).toBe(v["d-tracks"]!.items!.length);
    expect(blockOf("d-threads").querySelectorAll(".rp-thread").length).toBe(v["d-threads"]!.items!.length);
    expect(within(blockOf("d-cards")).getByText("Nothing waits for your signature.")).toBeTruthy();
    // the list's heads and cells are plain words
    expect([...blockOf("d-tracks").querySelectorAll("th")].map((th) => th.textContent)).toEqual(["Title", "Genre", "Verdict"]);
    expect(within(blockOf("d-tracks")).getAllByText("Kept").length).toBeGreaterThan(0);
  });

  it("a verdict sends the track's answer with its genre and note, and takes it out in place", async () => {
    const props = body();
    const items = FIXTURE.values["d-queue"]!.items!;
    const first = items[0]!;
    const row = blockOf("d-queue").querySelector<HTMLElement>(`[data-id="${first.id}"]`)!;
    fireEvent.change(within(row).getByLabelText(/^Genre for/), { target: { value: " lo-fi " } });
    fireEvent.change(within(row).getByLabelText(/^Note on/), { target: { value: "Ask about the stems" } });
    await act(async () => fireEvent.click(row.querySelector('[data-role="verdict"][data-verdict="keep"]')!));
    expect(props.onVerdict).toHaveBeenCalledWith(first.id, { verdict: "keep", genre: "lo-fi", note: "Ask about the stems" });
    expect(document.querySelector(`[data-id="${first.id}"]`)).toBeNull();
    expect(blockOf("d-queue").querySelectorAll('[data-role="queue-item"]').length).toBe(items.length - 1);
    // the other parts are untouched
    expect(blocks().length).toBe(FIXTURE.spec.blocks.length);
  });

  it("a verdict with no genre or note sends the verdict alone; a refusal stays on the track and says why", async () => {
    const onVerdict = vi.fn().mockRejectedValueOnce(new DaemonError(400, "bad_request", "the verdict must be keep, pass or later"));
    body({ onVerdict });
    const first = FIXTURE.values["d-queue"]!.items![0]!;
    const row = () => document.querySelector<HTMLElement>(`[data-id="${first.id}"]`)!;
    await act(async () => fireEvent.click(row().querySelector('[data-verdict="later"]')!));
    expect(onVerdict).toHaveBeenCalledWith(first.id, { verdict: "later" });
    expect(within(row()).getByRole("alert").textContent).toBe("the verdict must be keep, pass or later");
    expect(row()).toBeTruthy();
  });

  it("the dropped line appears only when something was dropped, its reasons behind a disclosure", () => {
    body();
    expect(document.querySelector('[data-role="dropped"]')).toBeNull();
    cleanup();
    const v = droppedView();
    body({ state: ready(v) });
    const dropped = document.querySelector<HTMLElement>('[data-role="dropped"]')!;
    expect(dropped.tagName).toBe("DETAILS");
    expect(dropped.querySelector("summary")!.textContent).toBe("1 part could not be shown");
    expect(within(dropped).getByText(v.reasons[0]!)).toBeTruthy();
  });

  it("arranged by Athena: when, her sentence, and the pinned part", () => {
    body({ state: ready(composedView()) });
    expect(screen.getByText("arranged 25 min ago")).toBeTruthy();
    expect(screen.getByText(/Two creators answered this week/)).toBeTruthy();
    expect(blockOf("d-queue").querySelector('[data-role="pin"]')!.getAttribute("aria-pressed")).toBe("true");
    expect(blockOf("d-views").querySelector('[data-role="pin"]')!.getAttribute("aria-pressed")).toBe("false");
  });

  it("every part says how old it is when the report is old", () => {
    body({ now: FIXTURE_LATER });
    for (const b of blocks()) expect(within(b).getByText("as of 3 h ago")).toBeTruthy();
  });

  it("reading shows quiet placeholders, a problem says why and tries again, an empty queue says so", () => {
    body({ state: { ...REPORT_IDLE, load: "reading" } });
    expect(document.querySelector('[data-role="report"]')!.getAttribute("aria-busy")).toBe("true");
    expect(blocks().length).toBe(0);
    cleanup();
    const props = body({ state: { ...REPORT_IDLE, load: "problem", problem: "not reachable" } });
    expect(screen.getByRole("alert").textContent).toContain("not reachable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(props.onRetry).toHaveBeenCalled();
    cleanup();
    body({ state: ready(emptyQueueView()) });
    expect(within(blockOf("d-queue")).getByText("No tracks waiting for you.")).toBeTruthy();
  });

  it("a YouTube track loads its player on a click, one at a time; any other address is a link out", () => {
    body({ state: ready(playerView()) });
    const queue = blockOf("d-queue");
    expect(queue.querySelectorAll("iframe").length).toBe(0);
    expect(within(queue).getAllByRole("link", { name: "Open the track" }).length).toBe(FIXTURE.values["d-queue"]!.items!.length - 1);
    fireEvent.click(within(queue).getAllByRole("button", { name: /^Play / })[0]!);
    const frames = queue.querySelectorAll("iframe");
    expect(frames.length).toBe(1);
    expect(frames[0]!.getAttribute("src")).toBe("https://www.youtube-nocookie.com/embed/Sim0000000a?autoplay=1");
  });

  it("never says the words the screen does not use, in any state", () => {
    const banned = /\b(records?|bindings?|specs?|blocks?|kinds?|mcp|fixtures?|models?|prompts?|nodes?|slots?)\b/i;
    for (const s of REPORT_STATES) {
      body({ state: s.state, now: s.now });
      const text = document.body.textContent ?? "";
      expect(text.match(banned)?.[0], s.name).toBeUndefined();
      cleanup();
    }
  });

  it("parses YouTube addresses and names creators by their handle", () => {
    expect(youtubeId("https://www.youtube.com/watch?v=abcdefghijk&t=3")).toBe("abcdefghijk");
    expect(youtubeId("https://youtu.be/abcdefghijk")).toBe("abcdefghijk");
    expect(youtubeId("https://www.youtube.com/shorts/abcdefghijk")).toBe("abcdefghijk");
    expect(youtubeId("https://youtube.example/watch?v=sim0008")).toBeNull();
    expect(youtubeId("https://www.youtube.com/watch?v=short")).toBeNull();
    expect(youtubeId("not a url")).toBeNull();
    expect(creatorName("https://youtube.example/@paper-orbit-sim")).toBe("@paper-orbit-sim");
  });
});

describe("the report through the daemon", () => {
  it("reads the report, sends a verdict through the API, and suggests the project's genres", async () => {
    vi.mocked(api.spaceReport).mockResolvedValue(FIXTURE);
    vi.mocked(api.trackVerdict).mockImplementation(async (id) => ({ ...FIXTURE.values["d-queue"]!.items![0]!, id: `${id}-2` }));
    await act(async () => render(<Report space={space()} />));
    expect(api.spaceReport).toHaveBeenCalledWith(SPACE_ID);
    expect(api.spaceRecords).toHaveBeenCalledWith(SPACE_ID, "track");
    expect([...document.querySelectorAll("datalist option")].map((o) => o.getAttribute("value"))).toContain("lo-fi");
    const first = FIXTURE.values["d-queue"]!.items![0]!;
    await act(async () => fireEvent.click(document.querySelector(`[data-id="${first.id}"] [data-verdict="pass"]`)!));
    expect(api.trackVerdict).toHaveBeenCalledWith(first.id, { verdict: "pass" });
    expect(document.querySelector(`[data-id="${first.id}"]`)).toBeNull();
  });

  it("Recompose shows composing, then the new view; a refusal keeps the report and says why", async () => {
    vi.mocked(api.spaceReport).mockResolvedValue(FIXTURE);
    const d = deferred<ReportView>();
    vi.mocked(api.composeReport).mockReturnValueOnce(d.promise);
    await act(async () => render(<Report space={space()} />));
    const btn = () => document.querySelector<HTMLButtonElement>('[data-role="recompose"]')!;
    await act(async () => fireEvent.click(btn()));
    expect(btn().textContent).toBe("Arranging...");
    expect(btn().disabled).toBe(true);
    await act(async () => d.resolve(composedView()));
    expect(btn().textContent).toBe("Arrange again");
    expect(screen.getByText(/^arranged /)).toBeTruthy();
    expect(screen.getByText(/Two creators answered this week/)).toBeTruthy();

    vi.mocked(api.composeReport).mockRejectedValueOnce(new DaemonError(503, "engine_unavailable", "She could not arrange the report: no engine"));
    await act(async () => fireEvent.click(btn()));
    expect(screen.getByRole("alert").textContent).toBe("She could not arrange the report: no engine");
    expect(screen.getByText(/Two creators answered this week/)).toBeTruthy();
  });

  it("a pin goes to the daemon as the whole pinned list", async () => {
    vi.mocked(api.spaceReport).mockResolvedValue(composedView());
    vi.mocked(api.setReportPins).mockResolvedValue({ ...composedView(), pinned: ["d-queue", "d-views"] });
    await act(async () => render(<Report space={space()} />));
    await act(async () => fireEvent.click(blockOf("d-views").querySelector('[data-role="pin"]')!));
    expect(api.setReportPins).toHaveBeenCalledWith(SPACE_ID, ["d-queue", "d-views"]);
    expect(blockOf("d-views").querySelector('[data-role="pin"]')!.getAttribute("aria-pressed")).toBe("true");
  });
});

describe("the report on the project's page", () => {
  function start(spaces: SpaceSummary[], route: Route) {
    window.location.hash = toHash(route);
    useMain.setState({ spaces, spacesLoad: "ready", route });
    render(<Shell />);
  }

  it("a project that keeps nothing looks exactly as before: no report, nothing read", async () => {
    await act(async () => start([space({ kinds: undefined, name: "Taxes" })], { view: "project", id: SPACE_ID }));
    expect(document.querySelector('[data-role="report"]')).toBeNull();
    expect(document.querySelector(".m-level")!.className).toBe("m-level");
    expect(api.spaceReport).not.toHaveBeenCalled();
    expect((screen.getByLabelText("Project name") as HTMLInputElement).value).toBe("Taxes");
  });

  it("a project that keeps records shows its report under the crumb, above the name and brief", async () => {
    vi.mocked(api.spaceReport).mockResolvedValue(FIXTURE);
    await act(async () => start([space()], { view: "project", id: SPACE_ID }));
    const report = document.querySelector('[data-role="report"]')!;
    const name = screen.getByLabelText("Project name");
    expect(report.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("button", { name: "All projects" }).compareDocumentPosition(report) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("follows the daemon: a report event, a card, and a change of kinds read the open project's report again", async () => {
    vi.mocked(api.spaceReport).mockResolvedValue(FIXTURE);
    vi.mocked(api.cards).mockResolvedValue([]);
    await act(async () => start([space()], { view: "project", id: SPACE_ID }));
    expect(api.spaceReport).toHaveBeenCalledTimes(1);
    await act(async () => useMain.getState().handleEvent({ type: "report", space_id: "spc_other" }));
    expect(api.spaceReport).toHaveBeenCalledTimes(1);
    await act(async () => useMain.getState().handleEvent({ type: "report", space_id: SPACE_ID }));
    expect(api.spaceReport).toHaveBeenCalledTimes(2);
    await act(async () => useMain.getState().handleEvent({ type: "card_filed" }));
    expect(api.spaceReport).toHaveBeenCalledTimes(3);
    vi.mocked(api.spaces).mockResolvedValueOnce([space()]);
    await act(async () => useMain.getState().handleEvent({ type: "space_changed", space_id: SPACE_ID }));
    expect(api.spaceReport).toHaveBeenCalledTimes(3);
    vi.mocked(api.spaces).mockResolvedValueOnce([space({ kinds: ["track", "creator"] })]);
    await act(async () => useMain.getState().handleEvent({ type: "space_changed", space_id: SPACE_ID }));
    expect(api.spaceReport).toHaveBeenCalledTimes(4);
  });
});
