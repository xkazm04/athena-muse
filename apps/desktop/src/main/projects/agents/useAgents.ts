import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "../../../lib/api";
import type { AgentLease } from "../../../lib/contract";
import { createMirror } from "../../../lib/mirror";
import { useAppEvents } from "../../../ui";
import { reasonOf } from "../../store";

/** How often the list is read with nothing else happening: a call without asking moves its count. */
export const POLL_MS = 15_000;
const REREAD_MIN_MS = 5_000;

/** Never "none" before an answer: `checking` until the first read lands, `failed` if it never did. */
export type ReadState = "checking" | "ok" | "failed";

/**
 * A project's connected agents, read through one mirror (lib/mirror.ts): on mount, on a card filed
 * or answered in this project (an agent's ask, its signature card), now and again, and at once after
 * an act. An answer older than one shown is never applied.
 */
export function useAgents(spaceId: string) {
  const [agents, setAgents] = useState<AgentLease[]>([]);
  const [read, setRead] = useState<ReadState>("checking");
  const [problem, setProblem] = useState("");

  const mirror = useMemo(
    () =>
      createMirror<AgentLease[]>({
        read: () => api.listAgents(spaceId),
        apply: (list) => {
          setAgents(Array.isArray(list) ? list : []);
          setRead("ok");
          setProblem("");
        },
        onFail: (e) => {
          setProblem(reasonOf(e, "Could not read the agents"));
          setRead((r) => (r === "ok" ? "ok" : "failed"));
        },
        now: () => Date.now(),
        rereadMinMs: REREAD_MIN_MS,
      }),
    [spaceId],
  );

  useEffect(() => {
    setAgents([]);
    setRead("checking");
    setProblem("");
    const stop = mirror.hold();
    const timer = setInterval(() => mirror.nudge(), POLL_MS);
    return () => {
      clearInterval(timer);
      stop();
      mirror.reset();
    };
  }, [mirror]);

  useAppEvents((e) => {
    if (e.type !== "card_filed" && e.type !== "card_resolved" && e.type !== "space_changed") return;
    const space = e.space_id ?? e.card?.space_id;
    if (space !== undefined && space !== spaceId) return;
    mirror.nudge();
  });

  /** A lease just made here: shown now, then the list is read again. */
  const put = useCallback(
    (lease: AgentLease) => {
      setAgents((list) => (list.some((a) => a.id === lease.id) ? list.map((a) => (a.id === lease.id ? lease : a)) : [...list, lease]));
      setRead("ok");
      void mirror.refresh();
    },
    [mirror],
  );

  /** Revoke at once: shown ended as soon as the daemon agrees, then the list is read again. A refusal throws. */
  const revoke = useCallback(
    async (leaseId: string) => {
      await api.revokeAgent(spaceId, leaseId);
      setAgents((list) => list.map((a) => (a.id === leaseId ? { ...a, state: "ended" } : a)));
      await mirror.refresh();
    },
    [mirror, spaceId],
  );

  const retry = useCallback(() => void mirror.refresh(), [mirror]);

  return { agents, read, problem, put, revoke, retry };
}
