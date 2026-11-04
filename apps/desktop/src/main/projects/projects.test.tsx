import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import type { Site, SpaceSummary } from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import { Shell } from "../App";
import { toHash, type Route } from "../route";
import { resetMain, useMain } from "../store";
import { hostInitial, layoutOrbits } from "./orbits";

vi.mock("../../lib/api");
vi.mock("../../lib/windows");
vi.mock("../../theme/Backdrop", () => ({ Backdrop: () => null }));
vi.mock("../../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/daemon")>()),
  subscribe: vi.fn(() => () => undefined),
}));

const space = (over: Partial<SpaceSummary> = {}): SpaceSummary => ({
  id: "spc_a1",
  name: "Taxes",
  brief: "File by April\nKeep receipts",
  apps: [],
  hue: 210,
  created: "2026-10-26T10:00:00Z",
  updated: "2026-10-26T10:00:00Z",
  counts: { episodes: 3, facts: 2 },
  ...over,
});

function start(spaces: SpaceSummary[], route: Route = { view: "projects" }) {
  // The hash leads: Shell follows hashchange, so a stale hash from the last test must not win.
  window.location.hash = toHash(route);
  useMain.setState({ spaces, spacesLoad: "ready", route });
  render(<Shell />);
}

beforeEach(() => {
  resetMain();
  vi.mocked(api.setActiveSpace).mockImplementation(async (id) => ({ space_id: id }));
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("projects field", () => {
  it("empty: the core alone, one line, and New project", () => {
    start([]);
    expect(screen.getByRole("button", { name: /what Athena knows everywhere/ })).toBeTruthy();
    expect(screen.getByText(/Projects keep Athena's memory for one piece of your work apart/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "New project" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Describe a need" }).getAttribute("href")).toBe("#stage/new");
  });

  it("lists the core and every project in the table with their counts, and totals them beside the title", async () => {
    useMain.setState({ coreCounts: { episodes: 4, facts: 7 } });
    start([space(), space({ id: "spc_b2", name: "Garden", apps: ["https://www.github.com"] })]);
    expect(screen.getByText("2 projects · 7 facts and 4 episodes in core")).toBeTruthy();
    const rows = screen.getAllByRole("row").slice(1).map((r) => r.textContent);
    expect(rows).toEqual(["Core-47", "Taxes032", "Garden132"]);
    expect(screen.getByRole("link", { name: "Core" }).getAttribute("href")).toBe("#projects/core");
    await act(async () => fireEvent.click(screen.getByRole("link", { name: "Garden" })));
    expect(useMain.getState().route).toEqual({ view: "project", id: "spc_b2" });
    expect(api.setActiveSpace).toHaveBeenCalledWith("spc_b2");
  });

  it("every project is a button; focus fills the marquee, click enters and makes it active", async () => {
    start([space(), space({ id: "spc_b2", name: "Garden", brief: "", apps: ["https://www.github.com"] })]);
    const garden = screen.getByRole("button", { name: "Garden" });
    fireEvent.focus(garden);
    expect(screen.getByRole("heading", { name: "Garden" })).toBeTruthy();
    expect(screen.getByText("No brief yet.")).toBeTruthy();
    await act(async () => fireEvent.click(garden));
    expect(useMain.getState().route).toEqual({ view: "project", id: "spc_b2" });
    expect(api.setActiveSpace).toHaveBeenCalledWith("spc_b2");
    expect((screen.getByLabelText("Project name") as HTMLInputElement).value).toBe("Garden");
  });

  it("creating a project round-trips through the daemon and lands on its level", async () => {
    vi.mocked(api.createSpace).mockResolvedValue(space({ id: "spc_new", name: "Moving house", brief: "", counts: { episodes: 0, facts: 0 } }));
    start([]);
    fireEvent.click(screen.getByRole("button", { name: "New project" }));
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "  Moving house " } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Create" })));
    expect(api.createSpace).toHaveBeenCalledWith({ name: "Moving house" });
    expect(useMain.getState().route).toEqual({ view: "project", id: "spc_new" });
    expect(api.setActiveSpace).toHaveBeenCalledWith("spc_new");
    expect((screen.getByLabelText("Project name") as HTMLInputElement).value).toBe("Moving house");
  });

  it("a refused create shows the daemon's reason verbatim", async () => {
    vi.mocked(api.createSpace).mockRejectedValue(new DaemonError(400, "bad_request", "you have 100 projects, the most"));
    start([]);
    fireEvent.click(screen.getByRole("button", { name: "New project" }));
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "One more" } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Create" })));
    expect(screen.getByText("you have 100 projects, the most")).toBeTruthy();
  });
});

describe("project level", () => {
  const level = () => start([space()], { view: "project", id: "spc_a1" });

  it("edits the name on blur and the brief with its counter", async () => {
    vi.mocked(api.updateSpace).mockImplementation(async (_id, patch) => space(patch));
    level();
    const name = screen.getByLabelText("Project name") as HTMLInputElement;
    fireEvent.focus(name);
    fireEvent.change(name, { target: { value: "Taxes 2026" } });
    await act(async () => fireEvent.blur(name));
    expect(api.updateSpace).toHaveBeenCalledWith("spc_a1", { name: "Taxes 2026" });
    expect(useMain.getState().spaces[0]?.name).toBe("Taxes 2026");
    expect(name.value).toBe("Taxes 2026");

    const brief = screen.getByLabelText("Brief") as HTMLTextAreaElement;
    expect(screen.getByText(`${space().brief.length}/1600`)).toBeTruthy();
    fireEvent.focus(brief);
    fireEvent.change(brief, { target: { value: "File by May" } });
    expect(screen.getByText("11/1600")).toBeTruthy();
    await act(async () => fireEvent.blur(brief));
    expect(api.updateSpace).toHaveBeenLastCalledWith("spc_a1", { brief: "File by May" });
    expect(screen.getByText("Brief saved")).toBeTruthy();
    expect(screen.getByText("Athena reads this every time she works in this project.")).toBeTruthy();
  });

  it("lists the project's apps by kind from the daemon, and adds one kind first", async () => {
    vi.mocked(api.spaceApps).mockResolvedValue([
      { app_id: "web_aaaaaaaaaa", kind: "website", label: "example.com", slug: "example_com", address: "https://example.com", status: "unchecked", tools: [], remotes: [], sealed: false },
    ]);
    level();
    await act(async () => undefined);
    expect(api.spaceApps).toHaveBeenCalledWith("spc_a1");
    const apps = document.querySelector('[data-role="apps"]')!;
    expect(apps.textContent).toContain("A website");
    expect(apps.textContent).toContain("https://example.com");
    fireEvent.click(screen.getByRole("button", { name: "Add app" }));
    expect(screen.getByRole("group", { name: "What kind of app is it?" })).toBeTruthy();
  });

  it("erases after a second confirm that states the counts, then goes back to the field", async () => {
    vi.mocked(api.eraseSpace).mockResolvedValue({ id: "spc_a1", episodes: 3, facts: 2, turns: 4 });
    level();
    fireEvent.click(screen.getByRole("button", { name: "Erase this project" }));
    expect(screen.getByText("This erases 5 memories and the conversation. Chores are not affected.")).toBeTruthy();
    expect(api.eraseSpace).not.toHaveBeenCalled();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Erase Taxes" })));
    expect(api.eraseSpace).toHaveBeenCalledWith("spc_a1");
    expect(useMain.getState().route).toEqual({ view: "projects" });
    expect(useMain.getState().spaces).toEqual([]);
  });

  it("a busy project is not erased and says why", async () => {
    vi.mocked(api.eraseSpace).mockRejectedValue(new DaemonError(409, "space_busy", "busy"));
    level();
    fireEvent.click(screen.getByRole("button", { name: "Erase this project" }));
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Erase Taxes" })));
    expect(screen.getByText("Athena is working in this project; try again when she is done")).toBeTruthy();
    expect(useMain.getState().route).toEqual({ view: "project", id: "spc_a1" });
  });

  it("offers Work here when the project is not active", async () => {
    level();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Work here" })));
    expect(api.setActiveSpace).toHaveBeenCalledWith("spc_a1");
    expect(screen.getByText("Athena is working in this project")).toBeTruthy();
  });
});

describe("orbits", () => {
  it("gives every project its own radius inside the stage and moons for its apps", () => {
    const spaces = Array.from({ length: 100 }, (_, i) =>
      space({ id: `spc_${i}`, hue: (i * 37) % 360, apps: i === 0 ? ["https://a.com", "https://b.org"] : [] }),
    );
    const orbits = layoutOrbits(spaces, 960, 520);
    const radii = orbits.map((o) => o.rx);
    expect(new Set(radii).size).toBe(100);
    expect(Math.max(...radii)).toBeLessThanOrEqual(960 / 2);
    expect(orbits[0]?.moons.map((m) => m.letter)).toEqual(["A", "B"]);
  });

  it("names a moon by its host's first letter", () => {
    expect(hostInitial("https://www.github.com")).toBe("G");
    expect(hostInitial("http://localhost:3000")).toBe("L");
  });
});

// --- a project's sites on its overview (ADR 0014) ------------------------------------------------

const CLUB = "https://billing.sunbeam-club.example";
const SCHOOL = "https://portal.maple-school.example";
const site = (over: Partial<Site> = {}): Site => ({
  origin: CLUB,
  label: "The club's billing page",
  probe_url: `${CLUB}/account`,
  access: "signed_in",
  blocks: ["Club invoice check"],
  checked_at: "2026-10-31T10:00:00Z",
  ...over,
});

describe("the overview's blocker", () => {
  const level = (sites: Site[]) => {
    vi.mocked(api.spaceSites).mockResolvedValue(sites);
    start([space()], { view: "project", id: "spc_a1" });
  };
  const band = () => document.querySelector<HTMLElement>('[data-role="blockers"]');

  it("is clean when every site is signed in, and a site not looked at yet reads checking, never fine", async () => {
    level([site(), site({ origin: SCHOOL, label: "The school portal", access: "unknown", checked_at: undefined })]);
    await act(async () => undefined);
    expect(api.spaceSites).toHaveBeenCalledWith("spc_a1");
    expect(band()).toBeNull();
    const rows = [...document.querySelectorAll<HTMLElement>('[data-role="site"]')];
    expect(rows.map((r) => r.dataset.access)).toEqual(["signed_in", "unknown"]);
    expect(rows[1]!.textContent).toContain("checking");
    expect(rows[1]!.textContent).not.toContain("signed in");
  });

  it("names a site the person is signed out of, what it blocks, and signs in again through her browser", async () => {
    level([site({ access: "signed_out", reason: "billing.sunbeam-club.example showed its sign-in page." })]);
    await act(async () => undefined);
    const row = band()!.querySelector<HTMLElement>('[data-role="blocker"]')!;
    expect(row.textContent).toContain("not signed in to The club's billing page");
    expect(row.textContent).toContain("This blocks: Club invoice check.");
    vi.mocked(api.siteSignIn).mockResolvedValue({ origin: CLUB, tab: 4 });
    vi.mocked(api.siteCheck).mockResolvedValue(site());
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign in again" })));
    expect(api.siteSignIn).toHaveBeenCalledWith("spc_a1", CLUB);
    expect(screen.getByText(/Athena never sees your password/)).toBeTruthy();
    // Another tab moving on is not this sign-in; this tab's page moving on is.
    await act(async () => useMain.getState().handleEvent({ type: "wheel", wheel: { tab: 9, state: "back" } }));
    expect(api.siteCheck).not.toHaveBeenCalled();
    await act(async () => useMain.getState().handleEvent({ type: "wheel", wheel: { tab: 4, state: "back" } }));
    expect(api.siteCheck).toHaveBeenCalledWith("spc_a1", CLUB);
    expect(band()).toBeNull();
  });

  it("follows a look live: a lapse shows the band, and nowhere says the words the screen never uses", async () => {
    level([site()]);
    await act(async () => undefined);
    expect(band()).toBeNull();
    const lapsed = site({ access: "signed_out", reason: "billing.sunbeam-club.example asked for a password." });
    await act(async () => useMain.getState().handleEvent({ type: "site", space_id: "spc_a1", site: lapsed }));
    expect(band()).toBeTruthy();
    const text = document.body.textContent!.toLowerCase();
    for (const word of ["token", "cookie", "session", "oauth", "origin"]) expect(text, word).not.toContain(word);
  });

  it("says why a site could not be read, and Check again looks now", async () => {
    level([site({ access: "unknown", reason: "Athena could not reach billing.sunbeam-club.example: no answer" })]);
    await act(async () => undefined);
    expect(document.querySelector('[data-role="site"]')!.textContent).toContain("could not check");
    vi.mocked(api.siteCheck).mockRejectedValue(new DaemonError(400, "bad_request", "Her browser is not open; the desktop app runs it."));
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Check again" })));
    expect(screen.getByRole("alert").textContent).toBe("Her browser is not open; the desktop app runs it.");
  });
});
