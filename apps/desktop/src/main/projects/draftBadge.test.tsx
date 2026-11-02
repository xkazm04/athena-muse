import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import type { DraftBadge as DraftBadgeWire, SpaceSummary } from "../../lib/contract";
import { Shell } from "../App";
import { toHash, type Route } from "../route";
import { resetMain, useMain } from "../store";
import { DraftBadge, draftBadgeLook } from "./DraftBadge";

vi.mock("../../lib/api");
vi.mock("../../lib/windows");
vi.mock("../../lib/notify");
vi.mock("../../theme/Backdrop", () => ({ Backdrop: () => null }));
vi.mock("../../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/daemon")>()),
  subscribe: vi.fn(() => () => undefined),
}));

const space = (over: Partial<SpaceSummary> = {}): SpaceSummary => ({
  id: "spc_a1",
  name: "Taxes",
  brief: "File by April",
  apps: [],
  hue: 210,
  created: "2026-10-26T10:00:00Z",
  updated: "2026-10-26T10:00:00Z",
  counts: { episodes: 3, facts: 2 },
  ...over,
});

const draft = (over: Partial<DraftBadgeWire> = {}): DraftBadgeWire => ({ id: "drf_1", step: "author", ...over });

function start(spaces: SpaceSummary[], route: Route = { view: "projects" }) {
  window.location.hash = toHash(route);
  useMain.setState({ spaces, spacesLoad: "ready", route });
  render(<Shell />);
}

beforeEach(() => resetMain());
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("a Project's draft badge", () => {
  it("names a running job by its step, with a live dot", () => {
    expect(draftBadgeLook(draft({ job: "running" }))).toEqual({ label: "Writing", tone: "info", live: true });
    expect(draftBadgeLook(draft({ step: "preview", job: "running" })).label).toBe("Preparing cards");
    expect(draftBadgeLook(draft({ step: "rehearse", job: "running" })).label).toBe("Testing");
  });

  it("says Ready to check once a job is done, and Needs you when it failed or was stopped", () => {
    expect(draftBadgeLook(draft({ step: "preview", job: "done" }))).toEqual({
      label: "Ready to check",
      tone: "human",
      live: false,
    });
    expect(draftBadgeLook(draft({ step: "verdict", job: "failed" })).label).toBe("Needs you");
    expect(draftBadgeLook(draft({ job: "stopped" })).label).toBe("Needs you");
    expect(draftBadgeLook(draft({ step: "shape" })).label).toBe("Draft");
  });

  it("shows in the projects table only on the Project with a draft, and opens the stage on it", () => {
    start([
      space({ draft: draft({ id: "drf_9", job: "running" }) }),
      space({ id: "spc_b2", name: "Garden" }),
    ]);
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[1]!).getByText("Writing")).toBeTruthy();
    expect(rows[1]!.querySelector(".m-draft-badge__dot")).toBeTruthy();
    expect(rows[2]!.querySelector(".m-draft-badge")).toBeNull();
    fireEvent.click(within(rows[1]!).getByRole("button", { name: "Writing: open the draft" }));
    expect(useMain.getState().route).toEqual({ view: "stage", id: "drf_9" });
    expect(window.location.hash).toBe("#stage/drf_9");
  });

  it("shows on the Project's own page", () => {
    vi.mocked(api.spaceRoutines).mockResolvedValue([]);
    vi.mocked(api.spaceSites).mockResolvedValue([]);
    start([space({ draft: draft({ step: "verdict", job: "done" }) })], { view: "project", id: "spc_a1" });
    expect(screen.getByRole("button", { name: "Ready to check: open the draft" })).toBeTruthy();
  });

  it("renders nothing without a draft", () => {
    const { container } = render(<DraftBadge draft={undefined} />);
    expect(container.innerHTML).toBe("");
  });
});

describe("draft_job events", () => {
  it("refresh the projects list, so the badge follows the job", async () => {
    vi.mocked(api.spaces).mockResolvedValue([space({ draft: draft({ job: "done", step: "preview" }) })]);
    start([space({ draft: draft({ job: "running" }) })]);
    expect(screen.getByText("Writing")).toBeTruthy();
    await act(async () =>
      useMain.getState().handleEvent({
        type: "draft_job",
        draft_id: "drf_1",
        space_id: "spc_a1",
        job: { kind: "write", state: "done", started: "2026-11-02T10:00:00Z", events: 4 },
      }),
    );
    expect(api.spaces).toHaveBeenCalled();
    expect(screen.getByText("Ready to check")).toBeTruthy();
  });
});
