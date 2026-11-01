// Fixture devices for the tests: a fixed clock and a handful of views. Fixtures, and labelled so.

import type { DevicesView, PairingWindow, PendingView } from "../../../lib/fleet";
import { EMPTY_DEVICES } from "./store";
import type { DevicesModel } from "./parts";

export const DEVICES_NOW = Date.parse("2026-10-24T12:00:00Z");

const iso = (offsetMs: number) => new Date(DEVICES_NOW + offsetMs).toISOString();

export const PENDING: PendingView = {
  pairing_id: "pair_0000000000b1",
  name: "Kitchen phone",
  kind: "phone",
  requested_grants: ["chat", "approve"],
  expires_at: iso(240_000),
  pair_back: false,
  address: "100.64.0.21",
  replaces: null,
};

export const VIEW: DevicesView = {
  ok: true,
  self: { device_id: "dev_0000000000a1", name: "Study PC" },
  peers: [
    {
      peer_id: "dev_0000000000a2",
      name: "Laptop",
      kind: "pc",
      grants: ["chat", "approve", "memory"],
      created: "2026-10-20T09:00:00Z",
      expires: null,
      last_seen: iso(-120_000),
      presence: "online",
      presence_at: iso(-30_000),
      link: { state: "online", since: iso(-30_000), evidence: {} },
    },
    {
      peer_id: "dev_0000000000a3",
      name: "Kitchen phone",
      kind: "phone",
      grants: ["chat"],
      created: "2026-10-21T09:00:00Z",
      expires: null,
      last_seen: null,
    },
    {
      peer_id: "dev_0000000000a4",
      name: "Studio PC",
      kind: "pc",
      grants: ["chat"],
      created: "2026-10-22T09:00:00Z",
      expires: null,
      last_seen: iso(-2 * 3_600_000),
      presence: "asleep",
    },
    {
      peer_id: "dev_0000000000a5",
      name: "Attic tower",
      kind: "pc",
      grants: ["chat"],
      created: "2026-10-23T09:00:00Z",
      expires: null,
      last_seen: iso(-2 * 86_400_000),
      presence: "unreachable",
    },
    {
      peer_id: "dev_0000000000a6",
      name: "Old desk",
      kind: "pc",
      grants: ["chat"],
      created: "2026-10-24T09:00:00Z",
      expires: null,
      last_seen: iso(-3 * 3_600_000),
      presence: "online",
      link: { state: "removed_there", since: null, evidence: {} },
    },
  ],
  pending: [],
  beacon: { on: false, url: null },
  overlay: { state: "up" },
  listener: { up: true, address: "100.64.0.7", port: 17491, error: null },
  joining: [{ join_id: "pair_0000000000e1", address: "100.64.0.9", name: "Office PC", state: "pending", expires_at: iso(200_000) }],
};

export const EMPTY_VIEW: DevicesView = {
  ...VIEW,
  peers: [],
  joining: [],
  overlay: { state: "absent" },
  listener: { up: false, address: null, port: 17491, error: null },
};

export const PHONE_WINDOW: PairingWindow = {
  ok: true,
  pairing_id: "pair_0000000000c1",
  code: "7Q4K2P",
  url: "http://100.64.0.7:17491/m/#claim=pair_0000000000c1.nonce",
  expires_at: iso(240_000),
};

export const PC_WINDOW: PairingWindow = { ...PHONE_WINDOW, pairing_id: "pair_0000000000c2", code: "M7KQ2X", url: null };

const noop = async () => {};

export function model(
  state: Partial<DevicesModel["state"]> = {},
  view: DevicesView | null = VIEW,
  actions: Partial<DevicesModel["actions"]> = {},
): DevicesModel {
  return {
    now: DEVICES_NOW,
    state: {
      ...EMPTY_DEVICES,
      view,
      loaded: view !== null,
      seenAt: {},
      ...state,
    },
    actions: {
      load: noop,
      rename: noop,
      setBeacon: noop,
      openPairing: noop,
      join: noop,
      toggleGrant: () => {},
      answer: noop,
      revoke: noop,
      ...actions,
    },
  };
}

/** A pending request first shown long enough ago to be armed. */
export const armed = (view: DevicesView = { ...VIEW, pending: [PENDING] }) =>
  model({ seenAt: { [PENDING.pairing_id]: DEVICES_NOW - 5000 } }, view);
