// Every state the twins page must show (prototypes/shared/states.md), built from the generated fixture
// through the store's own reducers, so the preview, the fidelity harness and the tests draw exactly what
// the routes would answer. Invented data; the screen says so.

import type { MissionTurn, TwinRehearsalEvent } from "../../lib/contract";
import { TWIN_FIXTURE } from "./fixture/twins";
import type { TwinFixture } from "./fixture/types";
import { initialSetup, initialTwins, reduceSetup } from "./store";
import type { TwinRoute } from "./Twins";
import type { SetupState, TwinsState } from "./types";

export const TWIN_STATES = [
  "overview-loading",
  "overview-first-run",
  "overview-today",
  "overview-row-open",
  "overview-handed-back",
  "overview-needs-sign-in",
  "overview-after-golive",
  "overview-error",
  "setup-describe",
  "setup-thinking",
  "setup-slow",
  "setup-failed",
  ...Array.from({ length: 12 }, (_, i) => `setup-f${i}`),
  "gmail-waiting",
  "gmail-failed",
  "notion-checking",
  "notion-rejected",
  "rehearsal-running",
  "rehearsal-waits",
  "rehearsal-held",
  "rehearsal-editing",
  "rehearsal-edited",
  "rehearsal-sent-alone",
  "rehearsal-resolved",
  "rehearsal-handed-back",
  "golive",
  "voice",
  "mission",
  "draft",
] as const;

export type TwinStateId = (typeof TWIN_STATES)[number];

export interface Shown {
  state: TwinsState;
  route: TwinRoute;
}

const turnsOf = (events: { event: TwinRehearsalEvent }[]): MissionTurn[] =>
  events.flatMap(({ event }) => (event.type === "turn" ? [event.turn] : []));

/** The setup after reply `n` (-1: the describe step), with the connections as the path left them. */
export function setupAt(n: number, fx: TwinFixture = TWIN_FIXTURE): SetupState {
  let s: SetupState = { ...initialSetup(), twin: fx.setup.created };
  const frames = fx.setup.frames;
  for (let i = 0; i <= n; i++) {
    for (const e of frames[i]!.events) s = reduceSetup(s, e);
    s = reduceSetup(s, { type: "twin", twin: frames[i]!.twin });
  }
  for (const kind of ["gmail", "notion"] as const) {
    const at = frames.findIndex((f) => f.twin.ask?.panel === "connect" && f.twin.ask.channel === kind);
    s.connect = { ...s.connect, [kind]: at >= 0 && n > at ? "connected" : "idle" };
  }
  if (n >= 0) s.youSaid = n === 0 ? fx.setup.need : (frames[n]!.say.choice ?? frames[n]!.say.text);
  return s;
}

function rehearsalAt(step: string, fx: TwinFixture): SetupState {
  const r = fx.setup.rehearsal;
  const [leg0, leg1, leg2] = r.legs;
  const base = setupAt(fx.setup.frames.length - 1, fx);
  const reh = { goal: r.goal, turns: [] as MissionTurn[], outcome: null, editing: null, continued: [] as string[], editText: "", streaming: false };
  const t = { ...base, ask: null, line: "", rehearsal: reh };
  const usual = [...turnsOf(leg0!.events), ...turnsOf(leg1!.events)];
  switch (step) {
    case "running":
      return { ...t, rehearsal: { ...reh, streaming: true }, work: "rehearse", startedAt: Date.now() - 3400 };
    case "waits":
      return { ...t, rehearsal: { ...reh, turns: turnsOf(leg0!.events) } };
    case "held":
      return { ...t, twin: leg1!.twin!, rehearsal: { ...reh, turns: usual } };
    case "editing":
      return { ...t, twin: leg1!.twin!, rehearsal: { ...reh, turns: usual, editing: usual.at(-1)!.id, editText: usual.at(-1)!.text } };
    case "edited":
      return { ...t, twin: leg2!.twin!, rehearsal: { ...reh, turns: usual } };
    case "sent-alone": {
      const turns = [...usual, ...turnsOf(leg2!.events)];
      return { ...t, twin: leg2!.twin!, rehearsal: { ...reh, turns, continued: [usual.at(-1)!.id], streaming: true }, work: "rehearse" };
    }
    case "resolved": {
      const turns = [...usual, ...turnsOf(leg2!.events)];
      const outcome = leg2!.events.find((e) => e.event.type === "outcome")!.event;
      const filed = outcome.type === "outcome" ? outcome.filed : undefined;
      return { ...t, twin: r.rehearsed, rehearsal: { ...reh, turns, continued: [usual.at(-1)!.id], outcome: filed ? { state: "resolved", filed } : { state: "resolved" } } };
    }
    case "handed": {
      const turns = [...turnsOf(leg0!.events), ...turnsOf(r.handed.events)];
      return { ...t, twin: r.handed.after, rehearsal: { ...reh, turns, outcome: { state: "handed_back" } } };
    }
    default: {
      const done = rehearsalAt("resolved", fx);
      return { ...done, twin: fx.setup.golive, sealed: true };
    }
  }
}

/** One named state of the page, in the example, with the address it lives at. */
export function stateOf(id: TwinStateId, fx: TwinFixture = TWIN_FIXTURE): Shown {
  const base = initialTwins("example");
  const ready: TwinsState = { ...base, page: fx.page, pageLoad: "ready" };
  const partners = fx.setup.twinId;
  const [desk, family] = fx.page.twins;
  const setup = (s: SetupState): Shown => ({ state: { ...ready, setup: s }, route: { view: "twin", id: partners } });
  if (id.startsWith("setup-f")) return setup(setupAt(Number(id.slice(7)), fx));
  if (id.startsWith("rehearsal-")) return setup(rehearsalAt(id.slice(10).replace("handed-back", "handed"), fx));
  const now = Date.now();
  const describe: SetupState = { ...initialSetup(), twin: fx.setup.created };
  switch (id) {
    case "overview-loading":
      return { state: { ...base, pageLoad: "reading" }, route: { view: "twins" } };
    case "overview-first-run":
      return { state: { ...base, page: { twins: [], stats: { live: 0, waiting_for_you: 0, missions_open: 0 } }, pageLoad: "ready" }, route: { view: "twins" } };
    case "overview-error":
      return { state: { ...base, pageLoad: "problem", pageProblem: "" }, route: { view: "twins" } };
    case "overview-row-open":
    case "overview-handed-back":
      return { state: ready, route: { view: "twin", id: desk!.id } };
    case "overview-needs-sign-in":
      return { state: ready, route: { view: "twin", id: family!.id } };
    case "overview-after-golive":
      return {
        state: { ...ready, page: fx.pageAfter, before: fx.page.stats, issued: partners, flash: `${fx.setup.golive.name} is live. Its document is issued and in your wallet.` },
        route: { view: "twins" },
      };
    case "setup-describe":
      return setup(describe);
    case "setup-thinking":
    case "setup-slow":
      return setup({ ...describe, youSaid: fx.setup.need, phase: "thinking", work: "say", startedAt: now - (id === "setup-slow" ? 9200 : 2400), heardAt: now - (id === "setup-slow" ? 9200 : 2400) });
    case "setup-failed":
      return setup({ ...describe, youSaid: fx.setup.need, phase: "failed", problem: "Her answer stopped before the end. Nothing was kept from it.", failed: { type: "describe", need: fx.setup.need } });
    case "gmail-waiting":
    case "gmail-failed": {
      const s = setupAt(1, fx);
      return setup({ ...s, connect: { ...s.connect, gmail: id === "gmail-waiting" ? "waiting" : "failed" }, connectSince: now - 12000, work: id === "gmail-waiting" ? "connect" : null });
    }
    case "notion-checking":
    case "notion-rejected": {
      const s = setupAt(4, fx);
      return setup({ ...s, connect: { ...s.connect, notion: id === "notion-checking" ? "checking" : "rejected" }, connectSince: now - 600, where: id === "notion-rejected", work: id === "notion-checking" ? "connect" : null });
    }
    case "golive":
      return setup(rehearsalAt("golive", fx));
    case "voice":
      return {
        state: { ...ready, page: fx.pageAfter, details: { [partners]: fx.setup.golive } },
        route: { view: "twin_voice", id: partners },
      };
    case "mission":
      return { state: ready, route: { view: "twin_mission", id: desk!.id, mission: desk!.missions[0]!.id } };
    case "draft":
      return { state: ready, route: { view: "twin_draft", id: desk!.id, draft: desk!.waiting[0]!.id } };
    default:
      return { state: ready, route: { view: "twins" } };
  }
}
