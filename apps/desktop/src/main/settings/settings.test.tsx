import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../lib/api";
import type { AppEvent, EngineStatus, LedgerPage, SettingsView } from "../../lib/contract";
import * as daemon from "../../lib/daemon";
import { DaemonError } from "../../lib/daemon";
import { App } from "../App";
import { parseHash, toHash } from "../route";
import { resetMain, useMain } from "../store";

vi.mock("../../lib/api");
vi.mock("../../lib/windows");
vi.mock("../../theme/Backdrop", () => ({ Backdrop: () => null }));
vi.mock("../../lib/daemon", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/daemon")>()),
  getConnection: vi.fn(),
  subscribe: vi.fn(),
}));

const muse: EngineStatus = { engine: "muse", model: "muse-spark", key: "file", simulated: false };
const emptyLedger: LedgerPage = { rows: [], totals: { calls: 0, cost_usd: 0, cost_estimated: true } };

const settings = (over: Partial<SettingsView> = {}): SettingsView => ({
  look: { theme: "auto", type_scale: "standard", motion: "system" },
  engine: "muse",
  source: "default",
  engines: [
    { id: "muse", readiness: "ready" },
    { id: "muse_code", readiness: "not_installed", reason: "Muse Code is not installed: put `muse` on PATH" },
    { id: "claude_code", readiness: "ready" },
    { id: "scripted", readiness: "simulated" },
  ],
  data_dir: "athena-data",
  ...over,
});

let emit: (e: AppEvent) => void = () => undefined;

async function open(hash: string, view = settings()) {
  window.location.hash = hash;
  resetMain();
  vi.mocked(daemon.getConnection).mockResolvedValue({ url: "http://127.0.0.1:1", token: "t" });
  vi.mocked(api.engine).mockResolvedValue(muse);
  vi.mocked(api.spaces).mockResolvedValue([]);
  vi.mocked(api.activeSpace).mockResolvedValue({ space_id: "" });
  vi.mocked(api.cards).mockResolvedValue([]);
  vi.mocked(api.ledger).mockResolvedValue(emptyLedger);
  vi.mocked(api.memory).mockResolvedValue({ rows: [], showing: 0, total: 0 });
  vi.mocked(api.settings).mockResolvedValue(view);
  vi.mocked(api.connections).mockResolvedValue([
    { kind: "gmail", status: "connected", writes: false, account: "me@example.test" },
    { kind: "notion", status: "disconnected", writes: false },
  ]);
  await act(async () => {
    render(<App />);
  });
}

const root = () => document.documentElement;

beforeEach(() => {
  localStorage.clear();
  vi.mocked(daemon.subscribe).mockImplementation((fn) => {
    emit = fn;
    return () => undefined;
  });
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  for (const a of ["data-theme", "data-type-scale", "data-motion"]) root().removeAttribute(a);
});

describe("settings routes", () => {
  it.each(["#settings", "#settings/look", "#settings/engine"])("%s round-trips", (hash) =>
    expect(toHash(parseHash(hash))).toBe(hash),
  );

  it("reads the overview and a level", () => {
    expect(parseHash("#/settings")).toEqual({ view: "settings", item: null });
    expect(parseHash("#settings/data")).toEqual({ view: "settings", item: "data" });
  });
});

describe("the overview", () => {
  it("shows every setting with its standing, and paints the stored look at boot", async () => {
    await open("#settings", settings({ look: { theme: "light", type_scale: "large", motion: "calm" } }));
    expect(root().getAttribute("data-theme")).toBe("light");
    expect(root().getAttribute("data-type-scale")).toBe("large");
    expect(root().getAttribute("data-motion")).toBe("calm");
    const tiles = screen.getByRole("list", { name: "Settings" });
    expect(tiles.textContent).toContain("Muse runs her turns.");
    expect(tiles.textContent).toContain("1 of 2 connected.");
    expect(tiles.textContent).toContain("light theme");
    expect(screen.getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBe("page");
  });

  it("says why it could not read, and reads again", async () => {
    window.location.hash = "#settings";
    await open("#settings");
    vi.mocked(api.settings).mockRejectedValueOnce(new DaemonError(503, "engine_unavailable", "ATHENA_ENGINE must be one of muse"));
    await act(async () => useMain.getState().loadSettings());
    expect(screen.getByRole("alert").textContent).toContain("ATHENA_ENGINE must be one of muse");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Read again" })));
    expect(screen.queryByText(/Settings could not be read/)).toBeNull();
  });

  it("shows the welcome again without changing a row", async () => {
    await open("#settings");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Show the welcome again" })));
    expect(screen.getByRole("button", { name: "Connect Muse" })).toBeTruthy();
    expect(api.setLook).not.toHaveBeenCalled();
    expect(api.chooseEngine).not.toHaveBeenCalled();
  });

  it("names a setting it does not have", async () => {
    await open("#settings/voice");
    expect(screen.getByText("Athena has no setting called voice.")).toBeTruthy();
  });
});

describe("the look", () => {
  it("paints a choice before it is written, and keeps the daemon's answer", async () => {
    await open("#settings/look");
    let answer: (v: SettingsView) => void = () => undefined;
    vi.mocked(api.setLook).mockReturnValue(new Promise((r) => (answer = r)));
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /^dark/ })));
    expect(root().getAttribute("data-theme")).toBe("dark"); // before the daemon answered
    expect(api.setLook).toHaveBeenCalledWith({ theme: "dark" });
    await act(async () => answer(settings({ look: { theme: "dark", type_scale: "standard", motion: "system" } })));
    expect(screen.getByRole("radio", { name: /^dark/ }).getAttribute("aria-checked")).toBe("true");
  });

  it("shows a refusal beside its control and settles back to the stored look", async () => {
    await open("#settings/look");
    vi.mocked(api.setLook).mockRejectedValue(new DaemonError(400, "bad_request", "motion must be one of system, calm"));
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /^calm/ })));
    expect(screen.getByText("The motion setting was not stored. The stored choice is shown again.")).toBeTruthy();
    expect(screen.getByText("motion must be one of system, calm")).toBeTruthy();
    expect(root().getAttribute("data-motion")).toBe("system");
  });

  it("wears a look chosen in the other window", async () => {
    await open("#settings/look");
    await act(async () => emit({ type: "settings", look: { theme: "dark", type_scale: "large", motion: "system" } }));
    expect(root().getAttribute("data-type-scale")).toBe("large");
    expect(screen.getByRole("radio", { name: /^large/ }).getAttribute("aria-checked")).toBe("true");
  });
});

describe("the engine", () => {
  it("offers every engine, with the reason on one that cannot run", async () => {
    await open("#settings/engine");
    const muse = screen.getByRole("radio", { name: /^Muse Code/ }) as HTMLButtonElement;
    expect(muse.disabled).toBe(true);
    expect(muse.textContent).toContain("Muse Code is not installed");
    expect(screen.getByRole("radio", { name: /^Muse Meta/ }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText(/nothing restarts/)).toBeTruthy();
  });

  it("writes a choice and shows the stored answer", async () => {
    await open("#settings/engine");
    vi.mocked(api.chooseEngine).mockResolvedValue(settings({ engine: "claude_code", source: "setting", choice: "claude_code" }));
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /^Claude Code/ })));
    expect(api.chooseEngine).toHaveBeenCalledWith("claude_code");
    expect(screen.getByRole("radio", { name: /^Claude Code/ }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("Claude Code runs her turns.")).toBeTruthy();
  });

  it("shows the daemon's refusal beside the choice", async () => {
    await open("#settings/engine");
    vi.mocked(api.chooseEngine).mockRejectedValue(new DaemonError(503, "engine_unavailable", "Claude Code is not installed"));
    await act(async () => fireEvent.click(screen.getByRole("radio", { name: /^Claude Code/ })));
    expect(screen.getByText("The engine was not stored. The stored choice is shown again.")).toBeTruthy();
    expect(screen.getByText("Claude Code is not installed")).toBeTruthy();
  });

  it("blocks every choice while ATHENA_ENGINE decides", async () => {
    await open("#settings/engine", settings({ engine: "claude_code", source: "env" }));
    for (const r of screen.getAllByRole("radio")) expect((r as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/unset it to choose here/)).toBeTruthy();
  });
});

describe("accounts and data", () => {
  it("lists the accounts and sends their changes to Twins", async () => {
    await open("#settings/accounts");
    expect(screen.getByText("me@example.test", { exact: false })).toBeTruthy();
    expect(screen.getByText("not connected")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to Twins" }).getAttribute("href")).toBe("#twins");
  });

  it("says where it lives", async () => {
    await open("#settings/data");
    expect(screen.getByText("athena-data")).toBeTruthy();
  });
});
