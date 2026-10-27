import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import { DaemonError } from "../../lib/daemon";
import { Shell } from "../App";
import { parseHash, toHash, type Route } from "../route";
import { resetMain, useMain } from "../store";
import { ChoreDetailView } from "./ChoreScene";
import { Catalogue, ChoreTile } from "./Chores";
import { FIXTURE_CHORES, fixtureBench, fixtureChore, fixtureDetail } from "./fixtures";
import { arrange, backendLines, passTone, STATUS, usd, VERDICT } from "./words";

vi.mock("../../lib/api");
vi.mock("../../lib/windows");
vi.mock("../../theme/Backdrop", () => ({ Backdrop: () => null }));
vi.mock("../../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/daemon")>()),
  subscribe: vi.fn(() => () => undefined),
}));

async function start(route: Route) {
  window.location.hash = toHash(route);
  useMain.setState({ route });
  await act(async () => {
    render(<Shell />);
  });
}

beforeEach(() => resetMain());
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("chore routes", () => {
  it.each(["#chores", "#chores/care-circle", "#chores/a%20b"])("%s round-trips", (hash) =>
    expect(toHash(parseHash(hash))).toBe(hash),
  );

  it("reads the slash form the brief writes", () => {
    expect(parseHash("#/chores")).toEqual({ view: "chores" });
    expect(parseHash("#/chores/care-circle")).toEqual({ view: "chore", id: "care-circle" });
    expect(parseHash("#chores/a%20b")).toEqual({ view: "chore", id: "a b" });
  });
});

describe("catalogue order and colour", () => {
  it("features chores with senses: proven, rehearsed, failing, unproven, then title; the rest apart", () => {
    const plain = fixtureChore({ id: "plain", title: "A plain chore", senses: [], featured: "unproven" });
    const second = fixtureChore({ id: "r2", title: "Zebra rehearsed" });
    const { featured, others } = arrange([...FIXTURE_CHORES, plain, second]);
    expect(featured.map((c) => c.id)).toEqual([
      "care-circle",
      "paper-flip-through",
      "r2",
      "prior-auth-denial-appeal",
      "renovation-witness",
    ]);
    expect(others.map((c) => c.id)).toEqual(["plain"]);
  });

  it("never gives a rehearsed chore the success colour, whatever its bench says", () => {
    for (const verdict of ["exceeds", "meets", "short"] as const) {
      const chore = fixtureChore({ featured: "rehearsed", bench: fixtureBench({ verdict }) });
      const { container } = render(<ChoreTile chore={chore} onOpen={() => undefined} />);
      expect(container.querySelector('[data-tone="success"]')).toBeNull();
      cleanup();
    }
    expect(STATUS.rehearsed.tone).not.toBe("success");
    expect(Object.values(VERDICT).map((v) => v.tone)).not.toContain("success");
    expect(passTone(true, "rehearsed")).not.toBe("success");
    expect(passTone(true, "proven")).toBe("success");
    expect(passTone(false, "proven")).toBe("error");
  });

  it("a proven chore says so in green", () => {
    render(<ChoreTile chore={fixtureChore({ featured: "proven" })} onOpen={() => undefined} />);
    expect(screen.getByText("Proven on Meta").getAttribute("data-tone")).toBe("success");
  });
});

describe("tile", () => {
  it("shows short title, promise with its tooltip, senses, status and the bench verdict", () => {
    const onOpen = vi.fn();
    const chore = fixtureChore({ senses: ["paper", "call"] });
    render(<ChoreTile chore={chore} onOpen={onOpen} />);
    expect(screen.getByText(chore.short_title)).toBeTruthy();
    expect(screen.getByText(chore.promise).getAttribute("title")).toBe(chore.promise);
    expect(screen.getByText("Paper")).toBeTruthy();
    expect(screen.getByText("Call")).toBeTruthy();
    expect(screen.getByText("Rehearsed on fixtures")).toBeTruthy();
    expect(screen.getByText("Exceeds the bar")).toBeTruthy();
    expect(screen.getByText("found 10 of 12, Claude Code")).toBeTruthy();
    fireEvent.click(screen.getByRole("button"));
    expect(onOpen).toHaveBeenCalledWith("paper-flip-through");
  });

  it("a tile with no bench run says it is not rehearsed", () => {
    render(<ChoreTile chore={fixtureChore({ bench: undefined, featured: "unproven" })} onOpen={() => undefined} />);
    expect(screen.getByText("Not rehearsed yet")).toBeTruthy();
    expect(screen.getByText("Not proven yet")).toBeTruthy();
  });
});

describe("catalogue states", () => {
  it("reading shows quiet placeholders; empty says so; no other-chores list without chores for it", () => {
    const { rerender, container } = render(<Catalogue chores={[]} load="reading" onOpen={() => undefined} />);
    expect(screen.getByRole("status", { name: "Reading the chores" })).toBeTruthy();
    expect(container.querySelectorAll(".m-chores__ghost").length).toBeGreaterThan(0);
    rerender(<Catalogue chores={[]} load="ready" onOpen={() => undefined} />);
    expect(screen.getByText("No chores yet.")).toBeTruthy();
    rerender(<Catalogue chores={FIXTURE_CHORES} load="ready" onOpen={() => undefined} />);
    expect(screen.queryByRole("list", { name: "Every other chore" })).toBeNull();
    expect(screen.queryByText("No chores yet.")).toBeNull();
  });

  it("an error is one sentence with a retry that reads again", async () => {
    vi.mocked(api.chores).mockRejectedValueOnce(new DaemonError(0, "bad_request", "Athena's background service is not reachable"));
    await start({ view: "chores" });
    expect(screen.getByRole("alert").textContent).toContain("Athena's background service is not reachable");
    vi.mocked(api.chores).mockResolvedValueOnce(FIXTURE_CHORES);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Try again" })));
    expect(api.chores).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("Proven on Meta")).toBeTruthy();
  });
});

describe("the scene in the shell", () => {
  it("the nav reaches the chores, a tile opens one, and back returns to the catalogue", async () => {
    vi.mocked(api.chores).mockResolvedValue(FIXTURE_CHORES);
    vi.mocked(api.chore).mockResolvedValue(fixtureDetail());
    await start({ view: "chores" });
    expect(screen.getByRole("link", { name: "Chores" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Projects" }).getAttribute("aria-current")).toBeNull();
    const tiles = screen.getAllByRole("button").filter((b) => b.classList.contains("m-chores__tile"));
    expect(tiles.map((t) => t.getAttribute("data-status"))).toEqual(["proven", "rehearsed", "failing", "unproven"]);
    await act(async () => fireEvent.click(tiles[1]!));
    expect(useMain.getState().route).toEqual({ view: "chore", id: "paper-flip-through" });
    expect(api.chore).toHaveBeenCalledWith("paper-flip-through");
    expect(screen.getByRole("heading", { name: "A parent's mail, filmed once" })).toBeTruthy();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "All chores" })));
    expect(useMain.getState().route).toEqual({ view: "chores" });
    expect(window.location.hash).toBe("#chores");
  });

  it("a chore that cannot be read says why and retries", async () => {
    vi.mocked(api.chore).mockRejectedValueOnce(new DaemonError(404, "unknown_ref", "No chore is called nope"));
    await start({ view: "chore", id: "nope" });
    expect(screen.getByText("No chore is called nope")).toBeTruthy();
    vi.mocked(api.chore).mockResolvedValueOnce(fixtureDetail());
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Try again" })));
    expect(screen.getByRole("heading", { name: "Proofs" })).toBeTruthy();
  });
});

describe("one chore", () => {
  it("shows persona, apps, brief and the proofs table with the backends line", () => {
    render(<ChoreDetailView detail={fixtureDetail()} />);
    expect(screen.getByText(/An adult child handling a retired parent's/)).toBeTruthy();
    expect(screen.getByText("Phone camera")).toBeTruthy();
    expect(screen.getByText("a parent's pile of medical and benefits mail").tagName).toBe("STRONG");
    expect(screen.getByText("Every sheet found and read twice").tagName).toBe("LI");
    expect(screen.getByText("Read with fixtures (reader, segmenter)")).toBeTruthy();
    const row = screen.getByText("field-agreement").closest("tr")!;
    const cells = within(row).getAllByRole("cell").map((c) => c.textContent);
    expect(cells).toEqual([
      "Paper",
      "field-agreement",
      "Do the two reads agree on dates and dollars?",
      "0.934",
      "≥ 0.9",
      "212",
      "passed",
      "NoteSix fields were asked instead of read; none was guessed.",
    ]);
    expect(row.getAttribute("title")).toBe("Six fields were asked instead of read; none was guessed.");
    expect(within(row).getByText("passed").getAttribute("data-tone")).toBe("info");
  });

  it("shows the bench panel: verdict, reasons, counts, money and the engine", () => {
    const chore = fixtureChore({ bench: fixtureBench({ value_found_usd: 10400, value_total_usd: 12500.5, cost_usd: 1234.5 }) });
    render(<ChoreDetailView detail={fixtureDetail({ chore })} />);
    const bench = screen.getByRole("heading", { name: /Bench/ }).closest("section")!;
    expect(within(bench).getByText("Exceeds the bar")).toBeTruthy();
    expect(within(bench).getByText("No false claims").tagName).toBe("LI");
    expect(within(bench).getByText("10 of 12")).toBeTruthy();
    expect(within(bench).getByText("$10,400 of $12,500.50")).toBeTruthy();
    expect(within(bench).getByText("14 turns")).toBeTruthy();
    expect(within(bench).getByText("38.4 min")).toBeTruthy();
    expect(within(bench).getByText("est. $1,234.50")).toBeTruthy();
    expect(bench.textContent).toContain("Ran on Claude Code (claude-dev)");
  });

  it("an unpriced run says unpriced", () => {
    render(<ChoreDetailView detail={fixtureDetail()} />);
    expect(screen.getByText("unpriced")).toBeTruthy();
  });

  it("a chore with no bench run says so and shows the command", () => {
    render(<ChoreDetailView detail={fixtureDetail({ chore: fixtureChore({ id: "care-circle", bench: undefined }) })} />);
    expect(screen.getByText("Not rehearsed yet.")).toBeTruthy();
    expect(screen.getByText("python -m athena.bench care-circle")).toBeTruthy();
  });
});

describe("words", () => {
  it("formats dollars with separators and groups backends", () => {
    expect(usd(3107)).toBe("$3,107");
    expect(usd(0)).toBe("$0");
    expect(usd(0.4213)).toBe("$0.4213");
    expect(usd(1234.5)).toBe("$1,234.50");
    expect(backendLines({ reader: "meta", transcriber: "muse_code" })).toEqual([
      "Read with Muse (reader)",
      "Read with Muse Code (transcriber)",
    ]);
  });
});
