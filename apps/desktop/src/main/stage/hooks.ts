// Time on the stage is read, never written: the store keeps when the daemon was last heard and when
// the work began, and these hooks re-render at the moment that changes what is shown. No timer here
// changes the model.

import { useEffect, useRef, useState } from "react";
import type { Draft, SpaceSummary } from "../../lib/contract";
import { useMain } from "../store";
import { SLOW_MS, shownPhase } from "./select";
import type { ReplyPhase, StageAction, StageFrame, StageWork } from "./types";

/** The reply's phase as shown: "slow" once a reply has been silent for 8 s. */
export function useShownPhase(frame: StageFrame, work: StageWork | null, heardAt: number): ReplyPhase {
  const [now, setNow] = useState(() => Date.now());
  const phase = shownPhase(frame, work, heardAt, now);
  const waiting = phase === "sending" || phase === "thinking";
  useEffect(() => {
    if (!waiting) return;
    const left = Math.max(0, heardAt + SLOW_MS - Date.now());
    const t = setTimeout(() => setNow(Date.now()), left + 1);
    return () => clearTimeout(t);
  }, [waiting, heardAt]);
  return phase;
}

/** Whole seconds since `startedAt`, ticking once a second while `running`. */
export function useClock(startedAt: number, running: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running, startedAt]);
  return startedAt ? Math.max(0, Math.floor((now - startedAt) / 1000)) : 0;
}

/**
 * The access step (ADR 0014): when her browser says the page of a site's tab moved on (the `wheel`
 * event), she looks at that site again. Nothing is looked at on its own otherwise.
 */
export function useAccessWheel(draft: Draft | null, dispatch: (action: StageAction) => void): void {
  const wheel = useMain((s) => s.wheel);
  const seen = useRef(wheel?.n ?? 0);
  useEffect(() => {
    if (!wheel || wheel.n === seen.current) return;
    seen.current = wheel.n;
    if (draft?.step !== "access") return;
    const site = draft.sites?.find((s) => s.tab === wheel.tab && s.state !== "signed_in");
    if (site) dispatch({ type: "access", origin: site.origin, act: "check" });
  }, [wheel, draft, dispatch]);
}

/** The draft's Project as the main window knows it, and the way to open it (the hand-off). */
export function useDraftProject(draft: Draft | null): { project: SpaceSummary | undefined; openProject: () => void } {
  const project = useMain((s) => s.spaces.find((x) => x.id === draft?.space_id));
  const navigate = useMain((s) => s.navigate);
  return { project, openProject: () => draft && navigate({ view: "project", id: draft.space_id }) };
}
