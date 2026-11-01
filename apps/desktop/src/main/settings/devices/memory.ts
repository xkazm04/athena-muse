// What the Devices page says about memory replication toward one computer (ADR 0017). Words only:
// the numbers come from `GET /devices` `peers[].memory`, `null` until the first pull.

import type { MemoryState, PeerView } from "../../../lib/fleet";
import { whenAgo } from "../../../lib/time";

const PROBLEM: Readonly<Record<Exclude<MemoryState, "ok">, string>> = {
  not_shared: "not shared by that computer",
  removed_there: "removed there",
  unreachable: "could not reach it",
};

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** The short line under a computer: when it last pulled, or the replication's own word when it did not. */
export function memoryCaption(peer: PeerView, now: number): string | null {
  const memory = peer.memory ?? null;
  if (peer.kind !== "pc" || memory === null) return null;
  if (memory.state !== "ok") return `Memory: ${PROBLEM[memory.state]}`;
  return memory.last_pull_at ? `Memory synced ${whenAgo(memory.last_pull_at, now)}` : "Memory not synced yet";
}

/** The fact in full: how it stands, how many came across, when, and any conflicts kept aside. */
export function memoryWords(peer: PeerView, now: number): string | null {
  const memory = peer.memory ?? null;
  if (peer.kind !== "pc" || memory === null) return null;
  const when = memory.last_pull_at ? whenAgo(memory.last_pull_at, now) : "never";
  const parts = [
    memory.state === "ok" ? "in step" : PROBLEM[memory.state],
    `${plural(memory.pulled, "memory", "memories")} pulled`,
    `last ${when}`,
  ];
  if (memory.deferred > 0) parts.push(`${memory.deferred} waiting`);
  if (memory.conflicts > 0) {
    parts.push(`${plural(memory.conflicts, "conflict", "conflicts")} kept for a look (the local memory stays)`);
  }
  return parts.join(", ");
}
