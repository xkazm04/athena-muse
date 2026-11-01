import { beforeEach, describe, expect, it, vi } from "vitest";
import { DaemonError } from "../../../lib/daemon";
import type { DevicesView, PendingView } from "../../../lib/fleet";
import { PENDING, VIEW } from "./fixtures";
import {
  ARM_MS,
  devicesHandler,
  grantsOf,
  isArmed,
  resetDevicesForTests,
  sentenceOf,
  setDevicesDeps,
  stampSeen,
  useDevices,
  type DevicesClient,
} from "./store";

const view = (over: Partial<DevicesView> = {}): DevicesView => ({ ...VIEW, peers: [VIEW.peers[0]!], joining: [], pending: [PENDING], ...over });

let clock = 0;
const calls: string[] = [];

/** A fake daemon: every call is noted in order, the list is whatever `list` says now. */
function wire(list: () => DevicesView = () => view(), over: Partial<DevicesClient> = {}) {
  calls.length = 0;
  const note = <T>(name: string, value: T) => async (...args: unknown[]) => {
    calls.push(`${name} ${JSON.stringify(args)}`);
    return value;
  };
  const client: DevicesClient = {
    devices: async () => {
      calls.push("devices");
      return list();
    },
    overlayPeers: note("overlay", { ok: true, state: "up", self_ip: null, peers: [], showing: 0, total: 0, footer: "" }),
    renameSelf: note("rename", {}),
    setBeacon: note("beacon", {}),
    openPairing: note("pairing", { ok: true, pairing_id: "pair_0000000000c1", code: "7Q4K2P", url: "http://x/m/#claim=y", expires_at: "" }),
    answerPending: note("answer", {}),
    revokeDevice: note("revoke", {}),
    joinDevice: note("join", {}),
    ...over,
  };
  setDevicesDeps({ client, now: () => clock });
}

beforeEach(() => {
  resetDevicesForTests();
  clock = 100_000;
});

describe("the reducers", () => {
  it("arms a pending request only after the delay", () => {
    expect(isArmed(undefined, 10_000)).toBe(false);
    expect(isArmed(1000, 1000 + ARM_MS - 1)).toBe(false);
    expect(isArmed(1000, 1000 + ARM_MS)).toBe(true);
  });

  it("keeps the first sight of a request across reads, and forgets one no longer listed", () => {
    const first = stampSeen({}, [PENDING], 5);
    expect(first).toEqual({ pair_0000000000b1: 5 });
    expect(stampSeen({ ...first, gone: 1 }, [PENDING], 99)).toEqual({ pair_0000000000b1: 5 });
  });

  it("sends what was asked, less what was unticked", () => {
    expect(grantsOf(PENDING)).toEqual(["chat", "approve"]);
    expect(grantsOf(PENDING, ["approve"])).toEqual(["chat"]);
  });

  it("says a refusal in the daemon's plain words, and a silent peer in ours", () => {
    expect(sentenceOf(new DaemonError(400, "bad_request", "A name is at most 40 characters."))).toBe("A name is at most 40 characters.");
    const silent = new DaemonError(502, "bad_request", "peer said nothing");
    expect(sentenceOf(silent)).toBe("That computer did not answer. It may be off, or off the private network.");
    const named = new DaemonError(409, "peer_unreachable" as never, "x");
    expect(sentenceOf(named)).toContain("did not answer");
    expect(sentenceOf(new Error("boom"))).toBe("boom");
  });
});

describe("the acts", () => {
  it("reads the list and stamps when each request was first shown", async () => {
    wire();
    await useDevices.getState().load();
    const state = useDevices.getState();
    expect(state.loaded).toBe(true);
    expect(state.seenAt).toEqual({ pair_0000000000b1: 100_000 });
  });

  it("says the list could not be read rather than showing an empty one", async () => {
    wire(() => {
      throw new DaemonError(500, "bad_request", "The daemon is unwell.");
    });
    await useDevices.getState().load();
    expect(useDevices.getState().loaded).toBe(false);
    expect(useDevices.getState().problem).toBe("The daemon is unwell.");
  });

  it("does not send an approve before the card has armed, and sends it after", async () => {
    wire();
    await useDevices.getState().load();
    await useDevices.getState().answer(PENDING.pairing_id, "approve");
    expect(calls.filter((c) => c.startsWith("answer"))).toHaveLength(0);
    clock += ARM_MS;
    await useDevices.getState().answer(PENDING.pairing_id, "approve");
    expect(calls.filter((c) => c.startsWith("answer"))).toEqual([`answer ["pair_0000000000b1","approve",["chat","approve"]]`]);
  });

  it("declines at once, armed or not", async () => {
    wire();
    await useDevices.getState().load();
    await useDevices.getState().answer(PENDING.pairing_id, "decline");
    expect(calls.filter((c) => c.startsWith("answer"))).toEqual([`answer ["pair_0000000000b1","decline",null]`]);
  });

  it("narrows only: a grant that was not asked cannot be ticked, an asked one can be unticked", async () => {
    wire();
    await useDevices.getState().load();
    useDevices.getState().toggleGrant(PENDING.pairing_id, "memory");
    expect(useDevices.getState().unticked[PENDING.pairing_id]).toBeUndefined();
    useDevices.getState().toggleGrant(PENDING.pairing_id, "approve");
    clock += ARM_MS;
    await useDevices.getState().answer(PENDING.pairing_id, "approve");
    expect(calls.filter((c) => c.startsWith("answer"))).toEqual([`answer ["pair_0000000000b1","approve",["chat"]]`]);
  });

  it("will not approve with nothing ticked", async () => {
    wire();
    await useDevices.getState().load();
    useDevices.getState().toggleGrant(PENDING.pairing_id, "chat");
    useDevices.getState().toggleGrant(PENDING.pairing_id, "approve");
    clock += ARM_MS;
    await useDevices.getState().answer(PENDING.pairing_id, "approve");
    expect(calls.filter((c) => c.startsWith("answer"))).toHaveLength(0);
    expect(useDevices.getState().errors[PENDING.pairing_id]).toContain("at least one thing ticked");
  });

  it("revokes with no confirmation and reads the list again, in that order", async () => {
    wire();
    await useDevices.getState().revoke("dev_0000000000a2");
    expect(calls).toEqual([`revoke ["dev_0000000000a2"]`, "devices"]);
  });

  it("puts a refusal where it was made, reads again anyway, and clears busy", async () => {
    wire(undefined, {
      renameSelf: async () => {
        throw new DaemonError(400, "bad_request", "A name is at most 40 characters.");
      },
    });
    await useDevices.getState().rename("x".repeat(50));
    const s = useDevices.getState();
    expect(s.errors.rename).toBe("A name is at most 40 characters.");
    expect(s.busy.rename).toBeUndefined();
    expect(s.loaded).toBe(true);
  });

  it("opens the phone's pairing window when the beacon goes on, and drops it when it goes off", async () => {
    wire();
    await useDevices.getState().setBeacon(true);
    expect(calls.slice(0, 2)).toEqual(['beacon [true]', 'pairing ["phone"]']);
    expect(useDevices.getState().opened.phone?.url).toBe("http://x/m/#claim=y");
    await useDevices.getState().setBeacon(false);
    expect(useDevices.getState().opened.phone).toBeUndefined();
  });

  it("trims what is typed into a join", async () => {
    wire();
    await useDevices.getState().join(" 100.64.0.9 ", " 123456 ");
    expect(calls[0]).toBe('join ["100.64.0.9","123456",["chat","approve","memory"]]');
  });

  it("an answer older than a read issued after it is not applied", async () => {
    let first: (v: DevicesView) => void = () => undefined;
    let n = 0;
    wire(() => view(), {
      devices: () => {
        n += 1;
        if (n === 1) return new Promise<DevicesView>((r) => (first = r));
        return Promise.resolve(view({ pending: [] }));
      },
    });
    const slow = useDevices.getState().load();
    const revoking = useDevices.getState().revoke("dev_0000000000a2"); // its read supersedes the one out
    await vi.waitFor(() => expect(n).toBe(2));
    first(view()); // the stale one lands last
    await Promise.all([slow, revoking]);
    expect(useDevices.getState().view?.pending).toEqual([]);
  });
});

describe("a pairing window opened elsewhere (pair.opened)", () => {
  const opened = (device_kind: "pc" | "phone", url: string | null = null) =>
    ({ kind: "pair.opened", pairing_id: "pair_0000000000f1", device_kind, code: "7Q4K2P", url, expires_at: "2026-10-24T12:05:00Z" }) as const;

  it("is kept as this device's own window, and the list is read again", () => {
    const changed = vi.fn();
    const on = devicesHandler(changed);
    on(opened("pc"));
    on(opened("phone", "http://100.64.0.7:17491/m/#claim=pair_0000000000f1.n"));
    const state = useDevices.getState().opened;
    expect(state.pc).toMatchObject({ pairing_id: "pair_0000000000f1", code: "7Q4K2P", url: null });
    expect(state.phone?.url).toBe("http://100.64.0.7:17491/m/#claim=pair_0000000000f1.n");
    expect(changed).toHaveBeenCalledTimes(2);
  });

  it("ignores a window of a kind it does not draw", () => {
    devicesHandler(() => {})({ ...opened("pc"), device_kind: "toaster" as "pc" });
    expect(useDevices.getState().opened).toEqual({});
  });

  it("re-reads on a peer change and on a new request", () => {
    const changed = vi.fn();
    const on = devicesHandler(changed);
    on({ kind: "peer.changed", peer_id: null });
    on({ kind: "pair.requested", pending: PENDING as PendingView });
    expect(changed).toHaveBeenCalledTimes(2);
  });
});
