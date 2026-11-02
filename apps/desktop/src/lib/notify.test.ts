import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as plugin from "@tauri-apps/plugin-notification";
import type { AppEvent, DraftJob } from "./contract";
import { jobEndLine, notifyDraftJob, resetNotifyForTests } from "./notify";
import { isTauri } from "./windows";

vi.mock("./windows");
vi.mock("@tauri-apps/plugin-notification", () => ({
  isPermissionGranted: vi.fn(),
  requestPermission: vi.fn(),
  sendNotification: vi.fn(),
}));

const job = (over: Partial<DraftJob> = {}): DraftJob => ({
  kind: "write",
  state: "done",
  started: "2026-11-02T10:00:00Z",
  events: 3,
  ...over,
});
const ended = (over: Partial<DraftJob> = {}): AppEvent => ({ type: "draft_job", draft_id: "drf_1", job: job(over) });

let focus = false;
beforeEach(() => {
  resetNotifyForTests();
  focus = false;
  vi.spyOn(document, "hasFocus").mockImplementation(() => focus);
  vi.mocked(isTauri).mockReturnValue(true);
  vi.mocked(plugin.isPermissionGranted).mockResolvedValue(false);
  vi.mocked(plugin.requestPermission).mockResolvedValue("granted");
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

describe("the draft job notifier", () => {
  it("words each ending plainly", () => {
    expect(jobEndLine(job())).toBe("Your chore is written - come back to check it.");
    expect(jobEndLine(job({ kind: "preview" }))).toBe("Her cards are ready to mark.");
    expect(jobEndLine(job({ kind: "rehearse" }))).toBe("The test run is done.");
    expect(jobEndLine(job({ state: "failed", reason: "the practice inbox did not open" }))).toBe(
      "She stopped: the practice inbox did not open",
    );
    expect(jobEndLine(job({ state: "stopped" }))).toBe("She stopped.");
    expect(jobEndLine(job({ state: "running" }))).toBeNull();
  });

  it("shows one toast for a job that ended while the window is away, asking permission once", async () => {
    await notifyDraftJob(ended());
    await notifyDraftJob(ended({ kind: "preview" }));
    expect(plugin.requestPermission).toHaveBeenCalledTimes(1);
    expect(plugin.sendNotification).toHaveBeenNthCalledWith(1, {
      title: "Athena",
      body: "Your chore is written - come back to check it.",
    });
    expect(plugin.sendNotification).toHaveBeenNthCalledWith(2, { title: "Athena", body: "Her cards are ready to mark." });
  });

  it("stays quiet while the window has focus, and never asks then", async () => {
    focus = true;
    await notifyDraftJob(ended());
    expect(plugin.requestPermission).not.toHaveBeenCalled();
    expect(plugin.sendNotification).not.toHaveBeenCalled();
  });

  it("stays quiet for a job that has only begun, and for other events", async () => {
    await notifyDraftJob(ended({ state: "running" }));
    await notifyDraftJob({ type: "space_changed", space_id: "spc_a1" });
    expect(plugin.requestPermission).not.toHaveBeenCalled();
    expect(plugin.sendNotification).not.toHaveBeenCalled();
  });

  it("does nothing outside the app", async () => {
    vi.mocked(isTauri).mockReturnValue(false);
    await notifyDraftJob(ended({ state: "failed", reason: "no answer" }));
    expect(plugin.isPermissionGranted).not.toHaveBeenCalled();
    expect(plugin.sendNotification).not.toHaveBeenCalled();
  });

  it("does nothing once the person said no, and does not ask again", async () => {
    vi.mocked(plugin.requestPermission).mockResolvedValue("denied");
    await notifyDraftJob(ended());
    await notifyDraftJob(ended());
    expect(plugin.requestPermission).toHaveBeenCalledTimes(1);
    expect(plugin.sendNotification).not.toHaveBeenCalled();
  });

  it("does not ask when permission was already given", async () => {
    vi.mocked(plugin.isPermissionGranted).mockResolvedValue(true);
    await notifyDraftJob(ended({ kind: "rehearse" }));
    expect(plugin.requestPermission).not.toHaveBeenCalled();
    expect(plugin.sendNotification).toHaveBeenCalledWith({ title: "Athena", body: "The test run is done." });
  });
});
