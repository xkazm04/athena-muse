import { describe, expect, it } from "vitest";
import type { Connection, SettingsView } from "../../lib/contract";
import type { DevicesView } from "../../lib/fleet";
import { ITEMS, accountsFact, dataFact, devicesFact, engineBlocked, engineFact, isItem, lookFact } from "./model";

const view = (over: Partial<SettingsView> = {}): SettingsView => ({
  look: { theme: "auto", type_scale: "standard", motion: "system" },
  engine: "scripted",
  source: "default",
  engines: [
    { id: "muse", readiness: "no_key", reason: "There is no Meta key: add one in Settings or set META_API_KEY" },
    { id: "muse_code", readiness: "not_installed", reason: "Muse Code is not installed: put `muse` on PATH" },
    { id: "claude_code", readiness: "ready" },
    { id: "scripted", readiness: "simulated" },
  ],
  ...over,
});

describe("the engine fact", () => {
  it("is unknown before the daemon answers, never a guess", () => {
    expect(engineFact(null)).toMatchObject({ standing: "unknown", word: "checking" });
  });

  it("says simulated plainly, and names a Muse choice that has no key", () => {
    expect(engineFact(view()).standing).toBe("todo");
    expect(engineFact(view()).line).toMatch(/simulated until you add a Meta key/);
    expect(engineFact(view({ choice: "muse" }))).toMatchObject({ standing: "missing" });
    expect(engineFact(view({ source: "setting", choice: "scripted" })).line).toMatch(/Simulated is chosen/);
  });

  it("is done when the chosen engine is found, and needs you when it is not", () => {
    expect(engineFact(view({ engine: "claude_code", source: "setting", choice: "claude_code" }))).toMatchObject({
      standing: "done",
      line: "Claude Code runs her turns.",
    });
    const gone = engineFact(view({ engine: "muse_code", source: "setting", choice: "muse_code" }));
    expect(gone.standing).toBe("missing");
    expect(gone.line).toBe("Muse Code is chosen. Muse Code is not installed: put `muse` on PATH.");
  });

  it("names ATHENA_ENGINE when nothing is chosen, and still lets Settings choose", () => {
    const pinned = view({ engine: "claude_code", source: "env" });
    expect(engineFact(pinned).line).toMatch(/set by ATHENA_ENGINE until you choose here/);
    expect(engineBlocked(pinned, "scripted")).toBeUndefined();
  });

  it("says when the chosen engine cannot run and which one runs instead", () => {
    const fell = view({ engine: "claude_code", source: "default", choice: "muse" });
    expect(engineFact(fell).standing).toBe("missing");
    expect(engineFact(fell).line).toMatch(/^Muse is chosen but cannot run here\..*Claude Code runs her turns until it can\.$/);
  });

  it("blocks an engine with its own reason, and leaves the simulated one open", () => {
    expect(engineBlocked(view(), "muse")).toMatch(/no Meta key/);
    expect(engineBlocked(view(), "scripted")).toBeUndefined();
    expect(engineBlocked(view(), "claude_code")).toBeUndefined();
  });
});

describe("the other facts", () => {
  const acct = (kind: Connection["kind"], status: Connection["status"]): Connection => ({ kind, status, writes: false });

  it("reads the accounts: a lapsed sign-in needs you, none connected is not yet", () => {
    expect(accountsFact(null).standing).toBe("unknown");
    expect(accountsFact(null, "offline").line).toMatch(/could not be read: offline/);
    expect(accountsFact([acct("gmail", "disconnected"), acct("notion", "disconnected")]).standing).toBe("todo");
    expect(accountsFact([acct("gmail", "needs_sign_in"), acct("notion", "connected")]).line).toBe(
      "Gmail needs you to sign in again.",
    );
    expect(accountsFact([acct("gmail", "connected"), acct("notion", "disconnected")]).line).toBe("1 of 2 connected.");
  });

  it("words the look and the data without a standing", () => {
    expect(lookFact(view().look)).toMatchObject({ standing: null, word: "auto theme" });
    expect(dataFact(view({ data_dir: "data" })).word).toBe("local");
    expect(dataFact(view()).word).toBe("in memory");
  });

  it("knows its items", () => {
    expect(isItem("look")).toBe(true);
    expect(isItem("voice")).toBe(false);
  });
});

describe("the devices fact", () => {
  const devices = (over: Partial<DevicesView> = {}): DevicesView => ({
    ok: true,
    self: { device_id: "dev_0000000000a1", name: "Study PC" },
    peers: [],
    pending: [],
    beacon: { on: false, url: null },
    overlay: { state: "up" },
    listener: { up: true, address: null, port: 1, error: null },
    joining: [],
    ...over,
  });
  const peer = { peer_id: "p", name: "Laptop", kind: "pc" as const, grants: [], created: "", expires: null, last_seen: null };
  const row = { pairing_id: "q", name: "Phone", kind: "phone" as const, requested_grants: [], expires_at: "", pair_back: false, address: null, replaces: null };

  it("is a setting of its own", () => {
    expect(ITEMS).toContain("devices");
    expect(isItem("devices")).toBe(true);
  });

  it("is unknown when the daemon did not answer, never 'nothing paired'", () => {
    expect(devicesFact(null)).toMatchObject({ standing: "unknown", word: "checking" });
  });

  it("is not yet with nothing paired, done with some, and needs you when a request waits", () => {
    expect(devicesFact(devices())).toMatchObject({ standing: "todo", word: "No other device paired" });
    expect(devicesFact(devices({ peers: [peer] }))).toMatchObject({ standing: "done", word: "1 paired" });
    expect(devicesFact(devices({ peers: [peer, { ...peer, peer_id: "r" }] })).word).toBe("2 paired");
    expect(devicesFact(devices({ peers: [peer], pending: [row] }))).toMatchObject({ standing: "missing", word: "1 waiting for you" });
  });
});
