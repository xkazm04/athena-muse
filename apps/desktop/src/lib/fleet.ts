// The fleet's wire, as the window reads it (portable ADR 0140, ADR 0017 here): `/devices*` on the
// daemon. Shapes are the Python's (`src/athena/peer/devices.py`) field for field, absent values `null`.
//
// The event stream is `/devices/events`, not `/events`: a nudge that a pairing or a peer moved. The
// list is the state; a frame only says "read it again", so an unknown kind is skipped, never thrown.

import { getConnection } from "./daemon";
import type { Room, Vitals } from "./vitals";

export type Grant = "chat" | "approve" | "memory";
export const GRANTS: readonly Grant[] = ["chat", "approve", "memory"];
export type DeviceKind = "pc" | "phone";

/** The presence probe's verdict. Online: Athena there answered. Asleep: the network sees it, Athena does not. */
export type Presence = "online" | "asleep" | "unreachable";

/** The states `peer/link.py` derives; `state` is `null` until there is anything to say. */
export type LinkState = "phone" | "awaiting_key" | "online" | "stale" | "asleep" | "unreachable" | "removed_there";

export interface PeerLink {
  state: LinkState | null;
  since: string | null;
  evidence: Record<string, unknown>;
}

/** How the last pull of a peer's memory went: `peer/replicate.py`'s `memory_view`. */
export type MemoryState = "ok" | "not_shared" | "removed_there" | "unreachable";

export interface PeerMemory {
  last_pull_at: string | null;
  pulled: number;
  /** Rows both devices hold under one id with different words; the local one stays, theirs is kept aside. */
  conflicts: number;
  deferred: number;
  state: MemoryState;
}

export interface PeerView {
  peer_id: string;
  name: string;
  kind: DeviceKind;
  grants: Grant[];
  created: string;
  expires: string | null;
  last_seen: string | null;
  presence?: Presence | null;
  presence_at?: string | null;
  link?: PeerLink | null;
  /** The replication toward this peer (ADR 0017); `null` until the first pull, and for a phone. */
  memory?: PeerMemory | null;
  /** The peer's last vitals off its hello (ADR 0017): `null` for a phone, before the first hello, and once stale. */
  vitals?: Vitals | null;
}

/** A request waiting on this person. `pair_back` is a PC this one joined, asking to be let in here. */
export interface PendingView {
  pairing_id: string;
  name: string;
  kind: DeviceKind;
  requested_grants: Grant[];
  expires_at: string;
  pair_back: boolean;
  /** Where the request came from, as the daemon's socket said; `null` when unknown. */
  address: string | null;
  /** The paired device approving this would overwrite (its token dies), else `null`. */
  replaces: { peer_id: string; name: string } | null;
}

/** This PC asking another to let it in. */
export interface JoinView {
  join_id: string;
  address: string;
  name: string;
  state: string;
  expires_at: string;
}

export type OverlayState = "absent" | "logged_out" | "up";

export interface DevicesView {
  ok: boolean;
  /** `vitals` is this PC's own snapshot, `null` before its first reading. */
  self: { device_id: string; name: string; vitals?: Vitals | null };
  peers: PeerView[];
  pending: PendingView[];
  beacon: { on: boolean; url: string | null };
  overlay: { state: OverlayState };
  listener: { up: boolean; address: string | null; port: number; error: string | null };
  joining: JoinView[];
}

/** `GET /devices/overlay`: the other devices on the private network, to pick the join form's address from. */
export interface OverlayPeers {
  ok: boolean;
  state: "no_overlay" | "logged_out" | "up";
  self_ip: string | null;
  peers: Array<{ name: string; ip: string; os: string; online: boolean }>;
  showing: number;
  total: number;
  footer: string;
}

/** `POST /devices/pairing`. `url` is the phone's QR target; `null` while the listener cannot bind. */
export interface PairingWindow {
  ok: boolean;
  pairing_id: string;
  code: string;
  url: string | null;
  expires_at: string;
}

/** A pairing window opened elsewhere (the code and the phone's address come here, never in `GET /devices`). */
export interface PairOpened {
  kind: "pair.opened";
  pairing_id: string;
  device_kind: DeviceKind;
  code: string;
  url: string | null;
  expires_at: string;
}

export type BusEvent =
  | PairOpened
  | { kind: "peer.changed"; peer_id: string | null }
  | { kind: "pair.requested"; pending: PendingView }
  | { kind: "vitals.changed"; room: Room | null; held: string | null; slots: number };

export const BUS_KINDS = ["pair.requested", "peer.changed", "pair.opened", "vitals.changed"] as const;

/** One frame's data, or `null` for anything that is not an event of a kind this window acts on. */
export function busEventFromJson(raw: string): BusEvent | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof parsed !== "object" || parsed === null) return null;
  const kind = (parsed as { kind?: unknown }).kind;
  return typeof kind === "string" && (BUS_KINDS as readonly string[]).includes(kind) ? (parsed as BusEvent) : null;
}

/** The plain words for the overlay's state. */
export function overlayWords(state: OverlayState): string {
  switch (state) {
    case "absent":
      return "Not set up";
    case "logged_out":
      return "Signed out";
    case "up":
      return "Ready";
  }
}

export const BUS_RETRY_MIN_MS = 1000;
export const BUS_RETRY_MAX_MS = 10000;

type Follower = [on: (event: BusEvent) => void, connected: (() => void) | undefined];

/** The window's one `/devices/events` stream: who listens, and what closes it. */
const followers = new Set<Follower>();
let close: (() => void) | null = null;

function openBus(): () => void {
  // A runtime with no EventSource (a test) has no bus; the list is still read on every act.
  if (typeof EventSource === "undefined") return () => undefined;
  let stopped = false;
  let source: EventSource | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let wait = BUS_RETRY_MIN_MS;

  const retry = () => {
    if (stopped) return;
    timer = setTimeout(connect, wait);
    wait = Math.min(BUS_RETRY_MAX_MS, wait * 2);
  };

  const connect = () => {
    timer = null;
    getConnection().then(
      (conn) => {
        if (stopped) return;
        const es = new EventSource(`${conn.url}/devices/events?token=${encodeURIComponent(conn.token)}`);
        source = es;
        es.onopen = () => {
          wait = BUS_RETRY_MIN_MS;
          // A frame published between two streams is missed: a (re)connect is when a reader reads again.
          for (const f of followers) f[1]?.();
        };
        const onFrame = (m: MessageEvent<string>) => {
          const event = busEventFromJson(m.data);
          if (!event) return;
          // A reader's own bug costs that reader that frame only, never the stream for the rest.
          for (const f of followers) {
            try {
              f[0](event);
            } catch (error) {
              console.error("[athena] devices bus:", error);
            }
          }
        };
        for (const kind of BUS_KINDS) es.addEventListener(kind, onFrame as EventListener);
        es.onerror = () => {
          // The daemon ends a quiet stream every 15 s with `retry: 1000` and the browser reconnects
          // itself; only a stream that is closed for good (refused, 401) is taken over with a backoff.
          if (es.readyState !== EventSource.CLOSED) return;
          es.close();
          if (source === es) source = null;
          retry();
        };
      },
      () => retry(),
    );
  };

  connect();
  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    source?.close();
    source = null;
  };
}

/**
 * Follow `GET /devices/events` until the returned function is called. Every caller shares one stream,
 * opened with the first and closed with the last. `connected` runs on each (re)connect.
 */
export function followBus(on: (event: BusEvent) => void, connected?: () => void): () => void {
  const me: Follower = [on, connected];
  followers.add(me);
  if (!close) close = openBus();
  return () => {
    if (followers.delete(me) && followers.size === 0) {
      close?.();
      close = null;
    }
  };
}

// -- A message to another computer, and its turn as that computer streams it (ADR 0017) ----------------

/** One event of a turn the other computer ran for a message from this one (`src/athena/peer/remote.py`). */
export type TurnEvent =
  | { kind: "turn.started"; turn_id: string; engine: string; simulated: boolean }
  | { kind: "text.delta"; text: string }
  | { kind: "tool.result"; name: string; label: string; ok: boolean }
  | { kind: "decision.requested"; id: string; action: string; label: string }
  | { kind: "turn.finished"; turn_id: string; waiting: boolean; text: string }
  | { kind: "turn.error"; reason: string; detail: string };

/** The last frame of a turn: why it closed, and what the buffer kept. */
export interface TurnClosed {
  kind: "remote.closed";
  request_id: string;
  reason: "finished" | "error" | "expired";
  showing: number;
  total: number;
  footer: string;
}

export type TurnFrame = TurnEvent | TurnClosed;

const TURN_KINDS: readonly string[] = [
  "turn.started",
  "text.delta",
  "tool.result",
  "decision.requested",
  "turn.finished",
  "turn.error",
  "remote.closed",
];

/** One frame's data, or `null` for a kind this window does not draw (a newer daemon's, say). */
export function turnFrameFromJson(raw: string): TurnFrame | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof parsed !== "object" || parsed === null) return null;
  const kind = (parsed as { kind?: unknown }).kind;
  return typeof kind === "string" && TURN_KINDS.includes(kind) ? (parsed as TurnFrame) : null;
}
