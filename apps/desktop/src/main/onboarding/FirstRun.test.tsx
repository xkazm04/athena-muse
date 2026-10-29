import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import type { EngineStatus } from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import * as windows from "../../lib/windows";
import { resetMain, useMain } from "../store";
import { FirstRun, META_DEV_URL, SKIP_KEY, readSkipped } from "./FirstRun";
import { classify } from "./probe";

vi.mock("../../lib/api");
vi.mock("../../lib/windows");
vi.mock("../../theme/Backdrop", () => ({ Backdrop: () => null }));

const saved: EngineStatus = { engine: "muse", model: "muse-spark", key: "file", simulated: false };
const absent: EngineStatus = { engine: "scripted", model: "scripted", key: "absent", simulated: true };

beforeEach(() => {
  resetMain();
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

async function toConnect() {
  const onDone = vi.fn();
  render(<FirstRun onDone={onDone} />);
  fireEvent.click(screen.getByRole("button", { name: "Connect Muse" }));
  return onDone;
}

async function paste(key: string) {
  fireEvent.change(screen.getByLabelText("Muse key"), { target: { value: key } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Check the key" })));
}

describe("first run", () => {
  it("welcomes in plain words and leads to the connect step", async () => {
    render(<FirstRun onDone={vi.fn()} />);
    expect(screen.getByText(/Nothing she does to your work happens without your signature/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Connect Muse" }));
    expect(screen.getByText(META_DEV_URL)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Open the page" }));
    expect(windows.openExternal).toHaveBeenCalledWith(META_DEV_URL);
  });

  it("empty: the check button is disabled until a key is pasted", async () => {
    await toConnect();
    const button = screen.getByRole("button", { name: "Check the key" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Muse key"), { target: { value: "   " } });
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Muse key"), { target: { value: "mk-123" } });
    expect(button.disabled).toBe(false);
    expect((screen.getByLabelText("Muse key") as HTMLInputElement).type).toBe("password");
  });

  it("probing: says it is asking Muse while the probe runs", async () => {
    vi.mocked(api.saveKey).mockResolvedValue(saved);
    vi.mocked(api.probe).mockReturnValue(new Promise(() => {}));
    await toConnect();
    await paste("mk-123");
    expect(api.saveKey).toHaveBeenCalledWith("mk-123");
    expect(screen.getByText("Asking Muse to answer...")).toBeTruthy();
    expect(document.querySelector(".seal")?.getAttribute("data-state")).toBe("working");
  });

  it("ok: shows the latency and the model, flashes signed, then reaches Ready", async () => {
    vi.mocked(api.saveKey).mockResolvedValue(saved);
    vi.mocked(api.probe).mockResolvedValue({ ok: true, model: "muse-spark", latency_ms: 812 });
    const onDone = await toConnect();
    await paste("mk-123");
    expect(screen.getByText(/Muse answered in 0.8 s/)).toBeTruthy();
    expect(screen.getByText(/muse-spark/)).toBeTruthy();
    expect(document.querySelector(".seal")?.getAttribute("data-state")).toBe("signed");
    expect(useMain.getState().engine).toEqual(saved);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByText("Athena is connected")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Open her window" }));
    expect(windows.toggleAthena).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Go to your projects" }));
    expect(onDone).toHaveBeenCalledWith(true);
    // the stage's door: describe a need, from right here
    fireEvent.click(screen.getByRole("button", { name: "Describe a need" }));
    expect(useMain.getState().route).toEqual({ view: "stage", id: null });
    expect(onDone).toHaveBeenLastCalledWith(false);
  });

  it("invalid: Meta refused the key, with a remedy, try again and remove", async () => {
    vi.mocked(api.saveKey).mockResolvedValue(saved);
    vi.mocked(api.probe).mockResolvedValue({ ok: false, error: "Meta refused the key" });
    vi.mocked(api.deleteKey).mockResolvedValue(absent);
    await toConnect();
    await paste("mk-bad");
    expect(screen.getByText("Meta refused the key.")).toBeTruthy();
    expect(screen.getByText(/create a new one on Meta's developer page/)).toBeTruthy();
    // the key stays saved: "Try again" re-asks Muse without saving again
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Try again" })));
    expect(api.saveKey).toHaveBeenCalledTimes(1);
    expect(api.probe).toHaveBeenCalledTimes(2);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Remove the key" })));
    expect(api.deleteKey).toHaveBeenCalled();
    expect(useMain.getState().engine).toEqual(absent);
    expect(screen.queryByText("Meta refused the key.")).toBeNull();
  });

  it("network down: could not reach Meta - try again", async () => {
    vi.mocked(api.saveKey).mockResolvedValue(saved);
    vi.mocked(api.probe).mockResolvedValue({ ok: false, error: "Could not reach Meta" });
    await toConnect();
    await paste("mk-123");
    expect(screen.getByText("Could not reach Meta.")).toBeTruthy();
    expect(screen.getByText(/Check your internet connection and try again/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("a daemon refusal while saving is shown verbatim", async () => {
    vi.mocked(api.saveKey).mockRejectedValue(new DaemonError(400, "bad_request", "send the key as text"));
    await toConnect();
    await paste("mk-123");
    expect(screen.getByText("send the key as text")).toBeTruthy();
    expect(api.probe).not.toHaveBeenCalled();
  });

  it("continue without a key sets the per-device skip flag", async () => {
    const onDone = await toConnect();
    fireEvent.click(screen.getByRole("button", { name: "Continue without a key" }));
    expect(localStorage.getItem(SKIP_KEY)).toBe("1");
    expect(readSkipped()).toBe(true);
    expect(onDone).toHaveBeenCalledWith(true);
  });

  it("classifies the daemon's probe words", () => {
    expect(classify({ ok: true })).toBe("ok");
    expect(classify({ ok: false, error: "Meta refused the key" })).toBe("invalid");
    expect(classify({ ok: false, error: "Could not reach Meta" })).toBe("network");
    expect(classify({ ok: false, error: "Meta answered with an error (500)" })).toBe("failed");
  });
});
