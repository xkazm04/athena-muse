// The report's states, derived from the one view the daemon generated (main/report/fixture.json, the
// simulated music channel; never edited by hand). Each state changes only what it must; the figures
// stay the daemon's. Used by the preview and the report's tests.

import type { ReportView } from "../lib/contract";
import fixture from "../main/report/fixture.json";
import { REPORT_IDLE, type ReportState } from "../main/store";

export const FIXTURE = fixture as unknown as ReportView;

/** A moment just after the daemon read it, so nothing is stale. */
export const FIXTURE_NOW = new Date(new Date(FIXTURE.rendered_at).getTime() + 5 * 60 * 1000);
/** Three hours later: every part says how old it is. */
export const FIXTURE_LATER = new Date(new Date(FIXTURE.rendered_at).getTime() + 3 * 60 * 60 * 1000);

const clone = (): ReportView => JSON.parse(JSON.stringify(FIXTURE)) as ReportView;

const ready = (view: ReportView, over: Partial<ReportState> = {}): ReportState => ({ ...REPORT_IDLE, load: "ready", view, ...over });

/** Arranged by Athena: her sentence, one part pinned, and the time she arranged it. */
export function composedView(): ReportView {
  const v = clone();
  v.default = false;
  v.composed_at = new Date(new Date(v.rendered_at).getTime() - 20 * 60 * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");
  v.spec.callout = "Two creators answered this week; the oldest waiting track is from Paper Orbit (simulated).";
  v.pinned = ["d-queue"];
  return v;
}

/** One part she chose could not be shown, and why (the daemon's words). */
export function droppedView(): ReportView {
  const v = composedView();
  v.dropped = 1;
  v.reasons = ["“Followers”: this project keeps no follower readings yet."];
  return v;
}

/** Every track has an answer: the queue is empty. */
export function emptyQueueView(): ReportView {
  const v = clone();
  v.values["d-queue"] = { items: [] };
  return v;
}

/** The first waiting track on YouTube, so its player can be loaded (the address is invented). */
export function playerView(): ReportView {
  const v = clone();
  const first = v.values["d-queue"]!.items![0]!;
  first.body = { ...first.body, url: "https://www.youtube.com/watch?v=Sim0000000a" };
  return v;
}

export interface NamedState {
  name: string;
  state: ReportState;
  now: Date;
}

export const REPORT_STATES: NamedState[] = [
  { name: "default", state: ready(clone()), now: FIXTURE_NOW },
  { name: "arranged", state: ready(composedView()), now: FIXTURE_NOW },
  { name: "dropped", state: ready(droppedView()), now: FIXTURE_NOW },
  { name: "empty queue", state: ready(emptyQueueView()), now: FIXTURE_NOW },
  { name: "player", state: ready(playerView()), now: FIXTURE_NOW },
  { name: "composing", state: ready(clone(), { composing: true }), now: FIXTURE_NOW },
  {
    name: "compose refused",
    state: ready(clone(), { composeProblem: "She could not arrange the report: no engine is set up (simulated)" }),
    now: FIXTURE_NOW,
  },
  { name: "stale", state: ready(clone()), now: FIXTURE_LATER },
  { name: "loading", state: { ...REPORT_IDLE, load: "reading" }, now: FIXTURE_NOW },
  {
    name: "error",
    state: { ...REPORT_IDLE, load: "problem", problem: "Athena's background service is not reachable (simulated)" },
    now: FIXTURE_NOW,
  },
];
