// The devices, as the main window holds them (portable ADR 0140, ADR 0017 here).
//
// A mirror of `GET /devices` and nothing more: the daemon owns the identity, the peers, the pending
// requests and the beacon, and every act here is a request after which the mirror is read again. The
// store never mints, never holds a token and never decides a grant; the one thing it keeps of its own
// is *when* each pending request was first shown (`seenAt`), because Approve is armed only ARM_MS
// after a person could have read the card: a request that appears under a moving pointer must not be
// approved by the click that was already on its way.
//
// The mirror follows `GET /devices/events` while the level is open (`startDevices`, counted): every
// `pair.requested`, `peer.changed` and `pair.opened` nudges a read. The reads go through the shared
// mirror reader (`lib/mirror.ts`). The bus is a nudge; the list is the state, with one exception:
// `pair.opened` carries the code and the phone's address, which `GET /devices` never lists, so the
// store keeps them in `opened` exactly as when the person pressed the button here.

import { create } from "zustand";
import * as api from "../../../lib/api";
import { DaemonError } from "../../../lib/daemon";
import {
  followBus,
  type BusEvent,
  type DeviceKind,
  type DevicesView,
  type Grant,
  type OverlayPeers,
  type PairOpened,
  type PairingWindow,
  type PendingView,
} from "../../../lib/fleet";
import { createMirror } from "../../../lib/mirror";
import { appendLines, converse, IDLE, type Conversation, type TalkClient } from "./conversation";

/** How long a pending request is shown before its Approve button arms. */
export const ARM_MS = 1500;
/** The least time between a read and the one a bus (re)connect asks for. */
export const REREAD_MIN_MS = 5000;

/** What the store asks of the daemon; the live one is lib/api.ts, a test passes its own. */
export interface DevicesClient {
  devices: () => Promise<DevicesView>;
  overlayPeers: () => Promise<OverlayPeers>;
  renameSelf: (name: string) => Promise<unknown>;
  setBeacon: (on: boolean) => Promise<unknown>;
  openPairing: (kind: DeviceKind) => Promise<PairingWindow>;
  answerPending: (id: string, choice: "approve" | "decline", grants: readonly Grant[] | null) => Promise<unknown>;
  revokeDevice: (peerId: string) => Promise<unknown>;
  joinDevice: (address: string, code: string, grants: readonly Grant[]) => Promise<unknown>;
  /** A message to a paired computer, and its turn read back (ADR 0017); absent in a client that has none. */
  sendMessage?: TalkClient["sendMessage"];
  turn?: TalkClient["turn"];
}

export interface DevicesDeps {
  client: DevicesClient;
  now: () => number;
  /** Follow the bus: `onChange` per frame that moves the list, `onConnected` per (re)connect. Returns its stop. */
  follow?: (onChange: () => void, onConnected: () => void) => () => void;
}

const LIVE: DevicesDeps = {
  client: {
    devices: () => api.devices(),
    overlayPeers: () => api.overlayPeers(),
    renameSelf: (name) => api.renameSelf(name),
    setBeacon: (on) => api.setBeacon(on),
    openPairing: (kind) => api.openPairing(kind),
    answerPending: (id, choice, grants) => api.answerPending(id, choice, grants),
    revokeDevice: (peerId) => api.revokeDevice(peerId),
    joinDevice: (address, code, grants) => api.joinDevice(address, code, grants),
    sendMessage: (peerId, text) => api.sendMessage(peerId, text),
    turn: (peerId, requestId, from, signal) => api.turn(peerId, requestId, from, signal),
  },
  now: () => Date.now(),
  follow: (onChange, onConnected) => followBus(devicesHandler(onChange), onConnected),
};

/** What the level does with one bus frame: a window opened elsewhere is kept as this one's own, and every frame re-reads. */
export function devicesHandler(onChange: () => void): (event: BusEvent) => void {
  return (event) => {
    if (event.kind === "pair.opened") useDevices.getState().pairOpened(event);
    onChange();
  };
}

let deps: DevicesDeps = LIVE;

export function setDevicesDeps(next: DevicesDeps): void {
  deps = next;
}

export interface DevicesState {
  view: DevicesView | null;
  /** True once `/devices` has answered once: not the same fact as "nothing is paired". */
  loaded: boolean;
  /** Why the list could not be read; `null` when it was. */
  problem: string | null;
  /** What is in flight: `rename`, `beacon`, `pairing.<kind>`, `join`, `<pairing_id>`, `<peer_id>`. */
  busy: Readonly<Record<string, true>>;
  /** The last refusal per act, in the daemon's words. */
  errors: Readonly<Record<string, string>>;
  /** The window this device opened, per kind: a phone's QR url, or the code another PC types. */
  opened: Readonly<Partial<Record<DeviceKind, PairingWindow>>>;
  /** When each pending request was first shown, by pairing id (ms). */
  seenAt: Readonly<Record<string, number>>;
  /** The grants a person unticked on a pending card, by pairing id. */
  unticked: Readonly<Record<string, readonly Grant[]>>;
  /** The private network's other devices, for the join form's pick list; `null` until read. */
  overlay: OverlayPeers | null;
  /** Each paired computer's message box, by peer id. */
  conversations: Readonly<Record<string, Conversation>>;

  load: () => Promise<void>;
  rename: (name: string) => Promise<void>;
  setBeacon: (on: boolean) => Promise<void>;
  openPairing: (kind: DeviceKind) => Promise<void>;
  join: (address: string, code: string) => Promise<void>;
  /** Tick or untick a grant on a pending card. Only what was asked can be unticked; nothing added. */
  toggleGrant: (pairingId: string, grant: Grant) => void;
  answer: (pairingId: string, choice: "approve" | "decline") => Promise<void>;
  revoke: (peerId: string) => Promise<void>;
  /** Read the private network's other devices. A failure leaves no pick list: the address is typed. */
  findPeers: () => Promise<void>;
  /** A pairing window was opened elsewhere (`pair.opened`): show it as one opened here. */
  pairOpened: (event: PairOpened) => void;
  /** Send a message to a paired computer's Athena and read what she does with it. */
  send: (peerId: string, text: string) => Promise<void>;
}

export const EMPTY_DEVICES = {
  view: null as DevicesView | null,
  loaded: false,
  problem: null as string | null,
  busy: {} as Record<string, true>,
  errors: {} as Record<string, string>,
  opened: {} as Partial<Record<DeviceKind, PairingWindow>>,
  seenAt: {} as Record<string, number>,
  unticked: {} as Record<string, readonly Grant[]>,
  overlay: null as OverlayPeers | null,
  conversations: {} as Record<string, Conversation>,
};

/** Whether a pending card first shown at `seenAt` may be approved at `now`. */
export function isArmed(seenAt: number | undefined, now: number): boolean {
  return seenAt !== undefined && now - seenAt >= ARM_MS;
}

/** The grants an approval sends: what was asked, less what the person unticked. */
export function grantsOf(pending: PendingView, unticked: readonly Grant[] = []): Grant[] {
  return pending.requested_grants.filter((grant) => !unticked.includes(grant));
}

/** `seenAt` kept for the pending rows still listed, stamped `now` for the new ones. */
export function stampSeen(
  seenAt: Readonly<Record<string, number>>,
  pending: readonly PendingView[],
  now: number,
): Record<string, number> {
  const next: Record<string, number> = {};
  for (const row of pending) next[row.pairing_id] = seenAt[row.pairing_id] ?? now;
  return next;
}

/** A refusal in a person's words. The daemon's reason is already plain; a peer that did not answer is named. */
export function sentenceOf(error: unknown): string {
  if (error instanceof DaemonError) {
    if ((error.error as string) === "peer_unreachable" || error.status === 502) {
      return "That computer did not answer. It may be off, or off the private network.";
    }
    return error.reason || error.message;
  }
  return error instanceof Error ? error.message : String(error);
}

/** The one reader of `GET /devices`; `load`, every act and the bus all go through it. */
const reader = createMirror<DevicesView>({
  read: () => deps.client.devices(),
  apply: (view) =>
    useDevices.setState((s) => ({
      view,
      loaded: true,
      problem: null,
      seenAt: stampSeen(s.seenAt, view.pending, deps.now()),
    })),
  onFail: (error) => useDevices.setState({ problem: sentenceOf(error) }),
  now: () => deps.now(),
  rereadMinMs: REREAD_MIN_MS,
  follow: () => deps.follow,
});

export const useDevices = create<DevicesState>((set, get) => {
  /**
   * One act: mark it busy, run it, read the list again, and put a refusal where it belongs. The read
   * after it supersedes any read that is out, which was issued before the act's change.
   */
  async function act(key: string, run: (client: DevicesClient) => Promise<unknown>): Promise<boolean> {
    set((s) => ({ busy: { ...s.busy, [key]: true }, errors: without(s.errors, key) }));
    let ok = true;
    try {
      await run(deps.client);
    } catch (error) {
      ok = false;
      set((s) => ({ errors: { ...s.errors, [key]: sentenceOf(error) } }));
    } finally {
      set((s) => ({ busy: without(s.busy, key) }));
    }
    await reader.refresh();
    return ok;
  }

  return {
    ...EMPTY_DEVICES,

    load: () => reader.load(),

    async rename(name) {
      await act("rename", (client) => client.renameSelf(name));
    },

    async setBeacon(on) {
      await act("beacon", async (client) => {
        await client.setBeacon(on);
        // The phone's QR is a pairing window of its own: open one when the beacon goes on.
        if (on) {
          const opened = await client.openPairing("phone");
          set((s) => ({ opened: { ...s.opened, phone: opened } }));
        } else {
          set((s) => ({ opened: { ...s.opened, phone: undefined } }));
        }
      });
    },

    async openPairing(kind) {
      await act(`pairing.${kind}`, async (client) => {
        const opened = await client.openPairing(kind);
        set((s) => ({ opened: { ...s.opened, [kind]: opened } }));
      });
    },

    async join(address, code) {
      await act("join", (client) => client.joinDevice(address.trim(), code.trim(), ["chat", "approve", "memory"]));
    },

    toggleGrant(pairingId, grant) {
      const pending = get().view?.pending.find((p) => p.pairing_id === pairingId);
      if (!pending || !pending.requested_grants.includes(grant)) return;
      set((s) => {
        const off = s.unticked[pairingId] ?? [];
        const next = off.includes(grant) ? off.filter((g) => g !== grant) : [...off, grant];
        return { unticked: { ...s.unticked, [pairingId]: next } };
      });
    },

    async answer(pairingId, choice) {
      const state = get();
      const pending = state.view?.pending.find((p) => p.pairing_id === pairingId);
      if (!pending) return;
      // The arm delay is the store's rule as well as the button's: an early approve is not sent.
      if (choice === "approve" && !isArmed(state.seenAt[pairingId], deps.now())) return;
      const grants = choice === "approve" ? grantsOf(pending, state.unticked[pairingId]) : null;
      if (choice === "approve" && grants?.length === 0) {
        set((s) => ({ errors: { ...s.errors, [pairingId]: "Leave at least one thing ticked, or decline." } }));
        return;
      }
      const ok = await act(pairingId, (client) => client.answerPending(pairingId, choice, grants));
      if (ok) set((s) => ({ unticked: without(s.unticked, pairingId) }));
    },

    async findPeers() {
      // An older daemon, no overlay, no answer: no pick list, and the address is typed.
      const overlay = await Promise.resolve()
        .then(() => deps.client.overlayPeers())
        .catch(() => null);
      set({ overlay: overlay ?? null });
    },

    pairOpened({ device_kind: kind, pairing_id, code, url, expires_at }) {
      // Only a kind this level draws; the daemon's own frame, so its fields are taken as given.
      if (kind === "pc" || kind === "phone") {
        set((s) => ({ opened: { ...s.opened, [kind]: { ok: true, pairing_id, code, url: url ?? null, expires_at } } }));
      }
    },

    async revoke(peerId) {
      await act(peerId, (client) => client.revokeDevice(peerId));
    },

    async send(peerId, text) {
      const words = text.trim();
      if (!words) return;
      const name = get().view?.peers.find((p) => p.peer_id === peerId)?.name ?? "that computer";
      const { sendMessage, turn } = deps.client;
      const talking = {
        change: (change: (c: Conversation) => Conversation) =>
          set((s) => ({ conversations: { ...s.conversations, [peerId]: change(s.conversations[peerId] ?? IDLE) } })),
        sentence: sentenceOf,
      };
      if (!sendMessage || !turn) {
        talking.change((c) => ({ ...appendLines(c, [{ kind: "you", text: words }]), phase: "error", problem: "This window cannot reach that computer yet." }));
        return;
      }
      await converse({ sendMessage, turn }, peerId, name, words, talking);
    },
  };
});

/**
 * Read the list now and follow the bus until the returned stop is called. Counted: the bus is
 * followed once for any number of holders and let go with the last.
 */
export function startDevices(): () => void {
  // Once per opening, not per nudge: it asks the overlay, and the list of addresses rarely moves.
  if (reader.holders() === 0) void useDevices.getState().findPeers();
  return reader.hold();
}

export function resetDevicesForTests(): void {
  reader.reset();
  deps = LIVE;
  useDevices.setState({ ...EMPTY_DEVICES });
}

function without<T>(map: Readonly<Record<string, T>>, key: string): Record<string, T> {
  const next = { ...map };
  delete next[key];
  return next;
}

