// The constellation, layer 1 of the Devices level (portable ADR 0140, design decision D1: a
// constellation, not device cards and not a ledger).
//
// This computer is the centre. Every paired device sits on an orbit around it, at an angle fixed by
// its place in a stable order (oldest pairing first), so a device does not wander between two
// readings of the list. The line from the centre says how the device stands *now*, from the daemon's
// presence probe: lit, with a slow breath along it, when Athena there answered; dim when the private
// network sees the device but Athena there does not answer (asleep); broken when neither (out of
// reach); a plain hairline before the first probe, and always for a phone, which runs no daemon to
// answer. A request waiting on this person is a pulsing node that "wants to join"; a computer this
// one asked to join is a dotted node until the other side answers. Two '+' nodes sit at the foot of
// the orbit, a phone and a computer, and the pairing wizard grows out of whichever was pressed.
//
// Geometry is one coordinate space, SKY: the lines are an SVG stretched over the stage
// (`preserveAspectRatio="none"`, strokes that do not scale), and every node is a real <button>
// placed at the same point in percent, so the stage can change its aspect at a narrow width and the
// nodes stay on their lines. Text is HTML, never SVG text. A visually hidden list says the same
// things in reading order.
//
// Pressing a node opens its details below the stage: an in-layer drawer with a caret under the
// node, not a route.

import { useState, type ReactNode, type Ref } from "react";
import {
  overlayWords,
  type DeviceKind,
  type DevicesView,
  type JoinView,
  type LinkState,
  type OverlayState,
  type PeerView,
  type PendingView,
  type Presence,
} from "../../../lib/fleet";
import { clockOf, whenAgo } from "../../../lib/time";
import {
  DeviceGlyph,
  Fact,
  Facts,
  Field,
  GRANT_WORDS,
  JOIN_WORDS,
  KIND_WORD,
  PendingCard,
  Refusal,
  type Answered,
  type DevicesModel,
} from "./parts";
import { HeldLine, VitalsFacts, roomSaid, useVitalsReread, withRoom } from "./vitals";
import { memoryWords } from "./memory";
import { MessageBox } from "./MessageBox";

/** The stage's coordinate space: its size, the centre, and the orbit's two radii. */
export const SKY = { w: 1000, h: 640, cx: 500, cy: 320, rx: 340, ry: 222 } as const;

export interface Spot {
  x: number;
  y: number;
}

/** Where the arc of devices starts and how far it runs, in degrees (0 = east, 90 = south). */
const ARC_FROM = 150;
const ARC_SPAN = 240;
/** Past this many, every other node moves to an inner orbit so labels do not touch. */
const ONE_RING = 9;
/** The '+' nodes, at the foot of the orbit, in the gap the arc leaves. */
const ADD_ANGLE: Readonly<Record<DeviceKind, number>> = { phone: 114, pc: 66 };

function onOrbit(degrees: number, scale = 1): Spot {
  const r = (degrees * Math.PI) / 180;
  return { x: Math.round(SKY.cx + SKY.rx * scale * Math.cos(r)), y: Math.round(SKY.cy + SKY.ry * scale * Math.sin(r)) };
}

/** The spots of `count` nodes on the arc, evenly; one alone is at the top. */
export function orbitSpots(count: number): Spot[] {
  return Array.from({ length: count }, (_, i) => {
    const angle = ARC_FROM + ((i + 0.5) * ARC_SPAN) / count;
    return onOrbit(angle, count > ONE_RING && i % 2 === 1 ? 0.66 : 1);
  });
}

export const ADD_SPOT: Readonly<Record<DeviceKind, Spot>> = { phone: onOrbit(ADD_ANGLE.phone), pc: onOrbit(ADD_ANGLE.pc) };

/** A spot in percent of the stage, for a node's `left`/`top` and the wizard's transform origin. */
export function percentOf(spot: Spot): { x: number; y: number } {
  const round = (n: number) => Math.round(n * 1000) / 1000;
  return { x: round((spot.x / SKY.w) * 100), y: round((spot.y / SKY.h) * 100) };
}

export type SkyNode =
  | { key: string; role: "peer"; peer: PeerView; at: Spot }
  | { key: string; role: "joining"; join: JoinView; at: Spot }
  | { key: string; role: "pending"; pending: PendingView; at: Spot };

/**
 * Every node but the centre and the '+' pair, in orbit order: the paired devices, oldest first (ties
 * by id), then this computer's own asks, then the requests waiting here.
 */
export function skyNodes(view: DevicesView): SkyNode[] {
  const peers = [...view.peers].sort((a, b) => a.created.localeCompare(b.created) || a.peer_id.localeCompare(b.peer_id));
  const joining = [...view.joining].sort((a, b) => a.join_id.localeCompare(b.join_id));
  const pending = [...view.pending].sort((a, b) => a.pairing_id.localeCompare(b.pairing_id));
  const spots = orbitSpots(peers.length + joining.length + pending.length);
  let i = 0;
  return [
    ...peers.map((peer) => ({ key: peer.peer_id, role: "peer" as const, peer, at: spots[i++]! })),
    ...joining.map((join) => ({ key: join.join_id, role: "joining" as const, join, at: spots[i++]! })),
    ...pending.map((row) => ({ key: row.pairing_id, role: "pending" as const, pending: row, at: spots[i++]! })),
  ];
}

/** The key of the centre node in `selected`. */
export const SELF = "self";

type Tone = "success" | "warning" | "error" | undefined;

/**
 * How a peer stands: a presence, or what the link state says where a presence cannot: the other side
 * removed this device, no key has arrived, the last hello is too old. `none` is "not checked yet",
 * and a phone's.
 */
type Standing = Presence | "none" | "removed" | "keyless" | "stale";

const STANDING: Readonly<Record<Standing, { word: string; tone: Tone; note?: string }>> = {
  online: { word: "Online", tone: "success" },
  asleep: { word: "Asleep", tone: undefined },
  unreachable: { word: "Out of reach", tone: "warning" },
  none: { word: "Not checked yet", tone: undefined },
  removed: {
    word: "Removed there",
    tone: "error",
    note: "That computer no longer lists this one. Revoke it here, then pair it again.",
  },
  keyless: {
    word: "Waiting for its key",
    tone: "warning",
    note: "No key has arrived from it yet. If this stays, revoke it and pair it again.",
  },
  stale: { word: "Not heard lately", tone: undefined, note: "It has not answered for a few minutes; this is its last known state." },
};

const LINK_STANDING: Readonly<Partial<Record<LinkState, Standing>>> = {
  removed_there: "removed",
  awaiting_key: "keyless",
  stale: "stale",
};

const standingOf = (peer: PeerView): Standing => {
  const state = peer.link?.state;
  return (state && LINK_STANDING[state]) || peer.presence || "none";
};

const OVERLAY_TONE: Readonly<Record<OverlayState, Tone>> = { absent: "warning", logged_out: "warning", up: "success" };

/** The node's caption: how it stands, in a few words. A phone is never probed, so it says when it was seen. */
export function presenceCaption(peer: PeerView, now: number): string {
  const seen = peer.last_seen ? `seen ${whenAgo(peer.last_seen, now)}` : "not seen yet";
  switch (standingOf(peer)) {
    case "online":
      return "Online";
    case "asleep":
      return `Asleep · ${seen}`;
    case "unreachable":
      return `Out of reach · ${seen}`;
    case "removed":
      return `Removed there · ${seen}`;
    case "keyless":
      return "Waiting for its key";
    case "stale":
      return `Not heard lately · ${seen}`;
    case "none":
      return seen.charAt(0).toUpperCase() + seen.slice(1);
  }
}

/** A peer's presence as read aloud, its room after it: "online, room is tight". */
function presenceSaid(peer: PeerView, now: number): string {
  const presence = presenceCaption(peer, now).toLowerCase();
  const room = roomSaid(peer.vitals);
  return room ? `${presence}, ${room}` : presence;
}

/** This computer's room as a sentence of its own, " Room ok." or nothing. */
function selfRoom(view: DevicesView): string {
  const room = roomSaid(view.self.vitals);
  return room ? ` ${room.charAt(0).toUpperCase()}${room.slice(1)}.` : "";
}

function nodeLabel(node: SkyNode, now: number): string {
  switch (node.role) {
    case "peer":
      return `${node.peer.name}, ${KIND_WORD[node.peer.kind].toLowerCase()}, ${presenceSaid(node.peer, now)}. Show its details.`;
    case "joining":
      return `${node.join.name || node.join.address}, a computer this one asked to join: ${JOIN_WORDS[node.join.state] ?? node.join.state}. Show the request.`;
    case "pending":
      return `${node.pending.name}, a ${KIND_WORD[node.pending.kind].toLowerCase()}, wants to join. Answer it.`;
  }
}

/** The line from the centre to one node, in the node's state. A broken line has a gap at its middle. */
function Link({ to, state }: { to: Spot; state: string }) {
  const { cx, cy } = SKY;
  if (state === "unreachable" || state === "removed") {
    const at = (t: number) => ({ x: Math.round(cx + (to.x - cx) * t), y: Math.round(cy + (to.y - cy) * t) });
    const a = at(0.44);
    const b = at(0.56);
    return (
      <g className="m-sky__link" data-state={state}>
        <line x1={cx} y1={cy} x2={a.x} y2={a.y} vectorEffect="non-scaling-stroke" />
        <line x1={b.x} y1={b.y} x2={to.x} y2={to.y} vectorEffect="non-scaling-stroke" />
      </g>
    );
  }
  return (
    <g className="m-sky__link" data-state={state}>
      <line x1={cx} y1={cy} x2={to.x} y2={to.y} vectorEffect="non-scaling-stroke" />
      {state === "online" ? (
        <line className="m-sky__flow" x1={cx} y1={cy} x2={to.x} y2={to.y} vectorEffect="non-scaling-stroke" />
      ) : null}
    </g>
  );
}

/** The key to the sky's lines, in the order they are met: only the styles drawn on this sky are shown. */
const LEGEND: readonly { state: string; word: string }[] = [
  { state: "online", word: "online" },
  { state: "asleep", word: "asleep" },
  { state: "unreachable", word: "out of reach" },
  { state: "stale", word: "not heard lately" },
  { state: "keyless", word: "waiting for its key" },
  { state: "removed", word: "removed there" },
  { state: "none", word: "phone, or not checked yet" },
  { state: "pending", word: "wants to join" },
  { state: "joining", word: "asked to join" },
];

function linkState(node: SkyNode): string {
  return node.role === "peer" ? standingOf(node.peer) : node.role;
}

/** One node: a disc with the glyph, the name and a caption, placed on its spot. */
function Node({
  at,
  className,
  label,
  selected,
  attrs,
  onClick,
  disc,
  name,
  caption,
}: {
  at: Spot;
  className: string;
  label: string;
  selected: boolean;
  attrs?: Record<string, string | undefined>;
  onClick: () => void;
  disc: ReactNode;
  name: string;
  caption: string | null;
}) {
  const { x, y } = percentOf(at);
  return (
    <button
      type="button"
      className={`m-cnode ${className}`}
      style={{ left: `${x}%`, top: `${y}%` }}
      aria-label={label}
      aria-expanded={selected}
      data-selected={selected ? "1" : undefined}
      onClick={onClick}
      {...attrs}
    >
      <span className="m-cnode__disc">{disc}</span>
      <span className="m-cnode__name">{name}</span>
      {caption ? <span className="m-cnode__caption">{caption}</span> : null}
    </button>
  );
}

export interface ConstellationProps {
  model: DevicesModel;
  selected: string | null;
  onSelect: (key: string | null) => void;
  onAdd: (kind: DeviceKind) => void;
  /** The wizard is open: the sky dims, and nothing in it takes the focus or a click. */
  dim: boolean;
  /** The '+' nodes, so the wizard can hand the focus back to the one it grew from. */
  addRef: (kind: DeviceKind) => Ref<HTMLButtonElement>;
}

export function Constellation({ model, selected, onSelect, onAdd, dim, addRef }: ConstellationProps) {
  const view = model.state.view!;
  const nodes = skyNodes(view);
  const lonely = nodes.length === 0;
  const toggle = (key: string) => onSelect(selected === key ? null : key);
  const centre = { x: SKY.cx, y: SKY.cy };
  // React 18 has no `inert` prop; the attribute is set by hand.
  const inert = dim ? ({ inert: "" } as Record<string, string>) : {};
  return (
    <div className="m-sky" data-dim={dim ? "1" : undefined} data-lonely={lonely ? "1" : undefined} {...inert}>
      <svg
        className="m-sky__lines"
        viewBox={`0 0 ${SKY.w} ${SKY.h}`}
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        <ellipse className="m-sky__orbit" cx={SKY.cx} cy={SKY.cy} rx={SKY.rx} ry={SKY.ry} vectorEffect="non-scaling-stroke" />
        <ellipse
          className="m-sky__orbit m-sky__orbit--inner"
          cx={SKY.cx}
          cy={SKY.cy}
          rx={SKY.rx * 0.5}
          ry={SKY.ry * 0.5}
          vectorEffect="non-scaling-stroke"
        />
        {nodes.map((node) => (
          <Link key={node.key} to={node.at} state={linkState(node)} />
        ))}
      </svg>
      {lonely ? (
        <p className="m-sky__invite">
          Only this computer so far. Add your phone or another computer, and they share one Athena: one memory, one set
          of approvals.
        </p>
      ) : null}
      <div className="m-sky__nodes" role="group" aria-label="Your devices, around this computer">
        <Node
          at={centre}
          className="m-cnode--self"
          label={`${view.self.name}, this computer. Private network: ${overlayWords(view.overlay.state).toLowerCase()}.${selfRoom(view)} Show its details.`}
          selected={selected === SELF}
          attrs={{ "data-overlay": view.overlay.state }}
          onClick={() => toggle(SELF)}
          disc={<DeviceGlyph kind="pc" />}
          name={view.self.name}
          caption={withRoom(`This computer · network ${overlayWords(view.overlay.state).toLowerCase()}`, view.self.vitals)}
        />
        {nodes.map((node) => {
          const common = {
            at: node.at,
            label: nodeLabel(node, model.now),
            selected: selected === node.key,
            onClick: () => toggle(node.key),
          };
          if (node.role === "peer") {
            return (
              <Node
                key={node.key}
                {...common}
                className="m-cnode--peer"
                attrs={{ "data-presence": standingOf(node.peer), "data-kind": node.peer.kind }}
                disc={<DeviceGlyph kind={node.peer.kind} />}
                name={node.peer.name}
                caption={withRoom(presenceCaption(node.peer, model.now), node.peer.vitals)}
              />
            );
          }
          if (node.role === "joining") {
            return (
              <Node
                key={node.key}
                {...common}
                className="m-cnode--joining"
                attrs={{ "data-state": node.join.state }}
                disc={<DeviceGlyph kind="pc" />}
                name={node.join.name || node.join.address}
                caption={node.join.state === "pending" ? "asked to join it" : (JOIN_WORDS[node.join.state] ?? node.join.state)}
              />
            );
          }
          return (
            <Node
              key={node.key}
              {...common}
              className="m-cnode--pending"
              attrs={{ "data-kind": node.pending.kind }}
              disc={<DeviceGlyph kind={node.pending.kind} />}
              name={node.pending.name}
              caption="wants to join"
            />
          );
        })}
        {(["phone", "pc"] as const).map((kind) => {
          const { x, y } = percentOf(ADD_SPOT[kind]);
          return (
            <button
              key={kind}
              ref={addRef(kind)}
              type="button"
              className="m-cnode m-cnode--add"
              data-kind={kind}
              style={{ left: `${x}%`, top: `${y}%` }}
              aria-label={kind === "phone" ? "Add a phone: show a code to scan" : "Add a computer: show or type a code"}
              aria-haspopup="dialog"
              onClick={() => onAdd(kind)}
            >
              <span className="m-cnode__disc">
                <svg className="m-cnode__plus" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
                  <path d="M16 9v14M9 16h14" />
                </svg>
              </span>
              <span className="m-cnode__name">{kind === "phone" ? "+ phone" : "+ PC"}</span>
            </button>
          );
        })}
      </div>
      {lonely ? null : (
        <ul className="m-sky__legend" aria-hidden="true">
          {LEGEND.filter((entry) => nodes.some((n) => linkState(n) === entry.state)).map((entry) => (
            <li key={entry.state} data-state={entry.state}>
              {entry.word}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const memoryLine = (peer: PeerView, now: number) => {
  const words = memoryWords(peer, now);
  return words ? ` Memory: ${words}.` : "";
};

/** The same devices as a list, in reading order, for a screen reader; drawn nowhere. */
export function DevicesList({ model }: { model: DevicesModel }) {
  const view = model.state.view!;
  const nodes = skyNodes(view);
  return (
    <ul className="m-sr" aria-label="Your devices as a list">
      <li>{`${view.self.name}: this computer. Private network: ${overlayWords(view.overlay.state)}.${selfRoom(view)}`}</li>
      {nodes.map((node) => (
        <li key={node.key}>
          {node.role === "peer"
            ? `${node.peer.name}: ${KIND_WORD[node.peer.kind].toLowerCase()}, ${presenceSaid(node.peer, model.now)}. May ${
                node.peer.grants.map((g) => GRANT_WORDS[g]).join(", ") || "do nothing"
              }.${memoryLine(node.peer, model.now)}`
            : node.role === "joining"
              ? `${node.join.name || node.join.address}: asked to join it, ${JOIN_WORDS[node.join.state] ?? node.join.state}.`
              : `${node.pending.name}: a ${KIND_WORD[node.pending.kind].toLowerCase()} that wants to join, waiting for you.`}
        </li>
      ))}
    </ul>
  );
}

/** Where the drawer's caret points: the selected node's centre, in percent of the stage's width. */
export function caretOf(view: DevicesView, selected: string): number {
  if (selected === SELF) return 50;
  const node = skyNodes(view).find((n) => n.key === selected);
  return node ? percentOf(node.at).x : 50;
}

/**
 * The details of the selected node, under the stage. Nothing when the selection is gone (a peer
 * revoked, a request answered elsewhere): the drawer simply is not there.
 */
export function Drawer({
  model,
  selected,
  onClose,
  onAnswered,
}: {
  model: DevicesModel;
  selected: string;
  onClose: () => void;
  onAnswered?: (answer: Answered) => void;
}) {
  const view = model.state.view!;
  const node = selected === SELF ? null : skyNodes(view).find((n) => n.key === selected);
  useVitalsReread(selected === SELF || (node?.role === "peer" && node.peer.kind === "pc"), model.actions.load);
  if (selected !== SELF && !node) return null;
  const caret = caretOf(view, selected);
  const head =
    selected === SELF
      ? { name: view.self.name, kind: "pc" as DeviceKind, note: "This computer" }
      : node!.role === "peer"
        ? { name: node!.peer.name, kind: node!.peer.kind, note: KIND_WORD[node!.peer.kind] }
        : node!.role === "pending"
          ? { name: node!.pending.name, kind: node!.pending.kind, note: "Wants to join" }
          : { name: node!.join.name || node!.join.address, kind: "pc" as DeviceKind, note: "Asked to join it" };
  return (
    <section className="m-cdrawer" aria-labelledby="cdrawer-name" style={{ ["--caret" as string]: `${caret}%` }}>
      <header className="m-cdrawer__head">
        <span className="m-cdrawer__disc" aria-hidden="true">
          <DeviceGlyph kind={head.kind} />
        </span>
        <div className="m-cdrawer__titles">
          <p className="eyebrow">{head.note}</p>
          <h3 id="cdrawer-name" className="m-cdrawer__name">
            {head.name}
          </h3>
        </div>
        <button type="button" className="btn btn-quiet" onClick={onClose}>
          Close
        </button>
      </header>
      {selected === SELF ? (
        <ThisComputer model={model} />
      ) : node!.role === "peer" ? (
        <PeerDetails model={model} peer={node!.peer} />
      ) : node!.role === "pending" ? (
        <PendingCard model={model} row={node!.pending} onAnswered={onAnswered} />
      ) : (
        <Facts>
          <Fact label="Its address" mono>
            {node!.join.address}
          </Fact>
          <Fact label="Where it stands">{JOIN_WORDS[node!.join.state] ?? node!.join.state}</Fact>
          <Fact label="The ask lapses at">{clockOf(node!.join.expires_at)}</Fact>
        </Facts>
      )}
    </section>
  );
}

function ThisComputer({ model }: { model: DevicesModel }) {
  const view = model.state.view!;
  const [draft, setDraft] = useState<string | null>(null);
  const value = draft ?? view.self.name;
  const typed = draft?.trim() ?? "";
  const dirty = draft !== null && typed !== "" && typed !== view.self.name;
  const renaming = Boolean(model.state.busy.rename);
  // The draft is kept until the list reads the name it asked for: a refused rename leaves the words
  // in the box, under the daemon's sentence, rather than putting the old name back.
  const name = view.self.name;
  const [named, setNamed] = useState(name);
  if (named !== name) {
    setNamed(name);
    if (draft !== null && draft.trim() === name) setDraft(null);
  }
  const commit = () => {
    if (!dirty || renaming) return;
    void model.actions.rename(typed);
  };
  const on = view.beacon.on;
  return (
    <div className="m-cdrawer__body">
      <Facts>
        <VitalsFacts vitals={view.self.vitals} presence="online" />
      </Facts>
      <HeldLine vitals={view.self.vitals} />
      <div className="m-row">
        <span className="badge" data-tone={OVERLAY_TONE[view.overlay.state]} title="The private network this computer talks to the others over">
          {`Private network: ${overlayWords(view.overlay.state)}`}
        </span>
        {view.listener.up && view.listener.address ? (
          <span className="m-muted">{`Listening at ${view.listener.address}:${view.listener.port}`}</span>
        ) : null}
        {view.listener.error ? <span className="m-muted">Athena could not listen: {view.listener.error}</span> : null}
      </div>
      <Field
        label="Its name"
        hint="What your other devices call this one."
        error={model.state.errors.rename ?? null}
        action={
          <button
            type="button"
            className={dirty ? "btn btn-primary" : "btn"}
            disabled={renaming || !dirty}
            title={renaming ? "Renaming..." : dirty ? undefined : "Type a new name first."}
            onClick={commit}
          >
            Rename
          </button>
        }
      >
        {(input) => (
          <input
            {...input}
            className="field"
            value={value}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit();
              if (e.key === "Escape") setDraft(null);
            }}
          />
        )}
      </Field>
      <div className="m-cdrawer__beacon">
        <div>
          <p>Let your phone reach Athena here</p>
          <p className="m-muted">
            While this window is open, a paired phone can chat with Athena on this computer and answer her approvals,
            from any network, over the private network.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-label="Let your phone reach Athena here"
          className="btn btn-pill"
          disabled={Boolean(model.state.busy.beacon)}
          onClick={() => void model.actions.setBeacon(!on)}
        >
          {on ? "On" : "Off"}
        </button>
      </div>
      {on && view.overlay.state !== "up" ? (
        <p className="m-muted">On, but the private network is {overlayWords(view.overlay.state).toLowerCase()}.</p>
      ) : null}
      <Refusal text={model.state.errors.beacon} />
    </div>
  );
}

function PeerDetails({ model, peer }: { model: DevicesModel; peer: PeerView }) {
  const presence = STANDING[standingOf(peer)];
  return (
    <div className="m-cdrawer__body">
      <Facts>
        <Fact label="Kind">{KIND_WORD[peer.kind]}</Fact>
        <Fact label="Now">
          <span className="badge" data-tone={presence.tone}>
            {peer.kind === "phone" && !peer.presence ? "Not probed (a phone)" : presence.word}
          </span>
          {peer.presence_at ? <span className="m-muted">{` changed ${whenAgo(peer.presence_at, model.now)}`}</span> : null}
          {presence.note ? <span className="m-muted">{presence.note}</span> : null}
        </Fact>
        <Fact label="Last seen">{peer.last_seen ? whenAgo(peer.last_seen, model.now) : "never"}</Fact>
        <Fact label="May">{peer.grants.length ? peer.grants.map((g) => GRANT_WORDS[g]).join(", ") : "-"}</Fact>
        {memoryWords(peer, model.now) ? <Fact label="Memory">{memoryWords(peer, model.now)}</Fact> : null}
        {peer.kind === "pc" ? <VitalsFacts vitals={peer.vitals} presence={peer.presence ?? null} /> : null}
      </Facts>
      {peer.kind === "pc" ? <HeldLine vitals={peer.vitals} /> : null}
      {peer.kind === "pc" ? <MessageBox model={model} peer={peer} /> : null}
      <div className="m-row">
        <button
          type="button"
          className="btn"
          disabled={Boolean(model.state.busy[peer.peer_id])}
          title={model.state.busy[peer.peer_id] ? "Revoking..." : undefined}
          onClick={() => void model.actions.revoke(peer.peer_id)}
        >
          Revoke
        </button>
        <span className="m-muted">It is let in no more, at once; pair it again to undo.</span>
      </div>
      <Refusal text={model.state.errors[peer.peer_id]} />
    </div>
  );
}
