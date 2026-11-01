import { beforeEach, describe, expect, it, vi } from "vitest";
import { DaemonError, request } from "./daemon";
import { beginSetup, openSetup, setupConversation, SETUP_SPACE, type SetupOpened } from "./setup";

vi.mock("./daemon", async (importOriginal) => ({ ...(await importOriginal<typeof import("./daemon")>()), request: vi.fn() }));

const asked = vi.mocked(request);
const opened: SetupOpened = { ok: true, space_id: SETUP_SPACE, phase: "installing", opened_at: "2026-11-01T10:00:00+00:00" };

beforeEach(() => asked.mockReset());

describe("openSetup", () => {
  it("posts to /devices/setup and takes the conversation it names", async () => {
    asked.mockResolvedValueOnce(opened);
    await expect(openSetup()).resolves.toEqual(opened);
    expect(asked).toHaveBeenCalledWith("POST", "/devices/setup");
  });

  it("refuses an answer that is not the setup conversation", async () => {
    asked.mockResolvedValueOnce({ ...opened, space_id: "spc_1" });
    await expect(openSetup()).rejects.toThrow("not the setup conversation");
  });

  it("reads the conversation back from its own route", async () => {
    asked.mockResolvedValueOnce({ turns: [] });
    await expect(setupConversation()).resolves.toEqual([]);
    expect(asked).toHaveBeenCalledWith("GET", "/devices/setup/conversation");
  });
});

describe("beginSetup", () => {
  it("opens the conversation, then shows her window", async () => {
    const order: string[] = [];
    const result = await beginSetup({
      open: async () => (order.push("open"), opened),
      hand: async () => (order.push("hand"), true),
    });
    expect(order).toEqual(["open", "hand"]);
    expect(result).toBe(opened);
  });

  it("says in plain words when the daemon refuses, and does not show her window", async () => {
    const hand = vi.fn(async () => true);
    const open = async () => {
      throw new DaemonError(409, "bad_request", "devices are switched off on this computer");
    };
    await expect(beginSetup({ open, hand })).rejects.toThrow("devices are switched off on this computer");
    expect(hand).not.toHaveBeenCalled();
  });

  it("says so when there is no window to show", async () => {
    await expect(beginSetup({ open: async () => opened, hand: async () => false })).rejects.toThrow("Athena app");
  });
});
