// Every state the twins page must show (docs/features/twins/reference/shared/states.md), built from the generated fixture
// through the store's own reducers, so the preview, the fidelity harness and the tests draw exactly what
// the routes would answer. Invented data; the screen says so.

import { BAR_DEFAULT, type MissionTurn, type Piece, type Sample, type TwinChannel, type TwinDetail, type TwinRehearsalEvent } from "../../lib/contract";
import { TWIN_FIXTURE } from "./fixture/twins";
import type { TwinFixture } from "./fixture/types";
import { initialSetup, initialTwins, reduceSetup } from "./store";
import type { TwinRoute } from "./Twins";
import type { RehearsalState, SetupState, TwinsState } from "./types";
import { WEB_SCOPE } from "./words";
import type { TwinsIo } from "./io";
import { DaemonError } from "../../lib/daemon";

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
  // derived, not generated: no fixture twin speaks on a web channel yet (see onWeb)
  "setup-web-paste",
  "setup-web-clearance",
  "overview-web",
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
    const before = frames[i]!.before;
    if (before) s = reduceSetup(s, { type: "twin", twin: before });
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

/** The rehearsal at one step: the daemon played the whole conversation, then the person marks each
 * draft that waited (the twin after each mark is the daemon's answer). */
function rehearsalAt(step: string, fx: TwinFixture): SetupState {
  const r = fx.setup.rehearsal;
  const [first, held] = r.marks;
  const base = setupAt(fx.setup.frames.length - 1, fx);
  const reh = { goal: r.goal, turns: [] as MissionTurn[], outcome: null, editing: null, continued: [] as string[], editText: "", streaming: false };
  const t = { ...base, ask: null, line: "", rehearsal: reh };
  const turns = turnsOf(r.events);
  const heldTurn = turns.find((x) => x.id === held!.mark.turn)!;
  const ended = outcomeOf(r.events);
  const played = { ...reh, turns, outcome: ended };
  switch (step) {
    case "running":
      return { ...t, rehearsal: { ...reh, streaming: true }, work: "rehearse", startedAt: Date.now() - 3400 };
    case "waits":
      return { ...t, twin: r.played, rehearsal: played };
    case "held":
      return { ...t, twin: first!.twin, rehearsal: played };
    case "editing":
      return { ...t, twin: first!.twin, rehearsal: { ...played, editing: heldTurn.id, editText: heldTurn.text } };
    case "edited":
      return { ...t, twin: held!.twin, rehearsal: played };
    case "sent-alone":
      return { ...t, twin: r.played, rehearsal: { ...reh, turns, streaming: true }, work: "rehearse" };
    case "resolved":
      return { ...t, twin: r.rehearsed, rehearsal: { ...played, continued: [heldTurn.id] } };
    case "handed":
      return { ...t, twin: r.handed.after, rehearsal: { ...reh, goal: r.handed.goal, turns: turnsOf(r.handed.events), outcome: outcomeOf(r.handed.events) } };
    default: {
      const done = rehearsalAt("resolved", fx);
      return { ...done, twin: fx.setup.golive, sealed: true };
    }
  }
}

function outcomeOf(events: { event: TwinRehearsalEvent }[]): RehearsalState["outcome"] {
  for (const { event } of events) {
    if (event.type === "outcome") return event.filed ? { state: event.state, filed: event.filed } : { state: event.state };
  }
  return null;
}

// --- web channels: DERIVED in preview and test code, not generated --------------------------------
// The generated twins fixture has no twin on a web channel (business Phase 2). These states take a
// generated twin and put web channels on it in the shapes the daemon answers (twins/view.py channels,
// web.status, web.pasted_sample): a bio link and a comment are "Her browser", business mail names its
// mailbox's host. The pasted messages are invented, like everything in the example.

const WEB_LABEL: Record<"mail_web" | "bio" | "comment", string> = { mail_web: "Business mail", bio: "Bio links", comment: "Comments" };

/** A web channel as the daemon opens it: at Assist, where it stays. */
export function webChannel(kind: "mail_web" | "bio" | "comment", status: TwinChannel["status"] = "connected"): TwinChannel {
  const account = kind === "mail_web" ? (status === "disconnected" ? "" : "mail.example.test") : "Her browser";
  return { kind, account, status, autonomy: "assist", bar: BAR_DEFAULT, scope: WEB_SCOPE[kind] };
}

/** A message the person pasted, as the samples list carries it. Invented. */
export function pastedSample(n: number, kind: "mail_web" | "bio" | "comment", text: string, date = "2026-10-28"): Sample {
  const first = text.split("\n").find((l) => l.trim()) ?? "";
  return { id: `ps_${String(n).padStart(12, "0")}`, to: `Pasted for ${WEB_LABEL[kind].toLowerCase()}`, subject: first.slice(0, 80), date, words: text.split(/\s+/).length, excerpt: text.slice(0, 200), suggest: true, picked: true };
}

export const PASTED: Sample[] = [
  pastedSample(1, "mail_web", "Hi Mara, I run a small lo-fi channel and your track Tidepool stopped me mid-scroll. Would you be open to a feature? Happy to share the numbers first."),
  pastedSample(2, "comment", "This one is lovely. The tape hiss under the keys is exactly right."),
];

/** A generated twin on web channels: alone (`only`), or beside the accounts it already has. */
export function onWeb(t: TwinDetail, kinds: ("mail_web" | "bio" | "comment")[], only = false, pasted: Sample[] = PASTED): TwinDetail {
  const web = kinds.map((k) => webChannel(k));
  const pieces: Piece[] = only
    ? [
        ...t.pieces.filter((p) => p.place !== "channels"),
        ...kinds.map((k, i): Piece => ({ id: `p_web_${i}`, place: "channels", label: WEB_LABEL[k], origin: "you", confirmed: true, detail: WEB_SCOPE[k] })),
      ]
    : [...t.pieces, ...kinds.map((k, i): Piece => ({ id: `p_web_${i}`, place: "channels", label: WEB_LABEL[k], origin: "you", confirmed: true, detail: WEB_SCOPE[k] }))];
  return {
    ...t,
    channels: only ? web : [...t.channels, ...web],
    pieces,
    samples: only ? pasted : [...t.samples, ...pasted],
  };
}

/** The example's routes with a paste that keeps onto the derived twin, as the daemon would answer it. */
export function webIo(io: TwinsIo, start: TwinDetail): TwinsIo {
  let twin = start;
  return {
    ...io,
    twinPaste: async (_id, body) => {
      const kind = body.channel as "mail_web" | "bio" | "comment";
      if (!(kind in WEB_LABEL) || !body.text.trim()) throw new DaemonError(400, "bad_request", "paste a message for business mail, a bio link or a comment");
      twin = { ...twin, samples: [...twin.samples, pastedSample(twin.samples.length + 1, kind, body.text.trim(), "2026-10-29")] };
      return twin;
    },
  };
}

const frameWith = (fx: TwinFixture, panel: string) => fx.setup.frames.findIndex((f) => f.twin.ask?.panel === panel);

function webSetup(fx: TwinFixture, which: "paste" | "clearance"): SetupState {
  const at = setupAt(frameWith(fx, which === "paste" ? "samples" : "autonomy"), fx);
  const twin = which === "paste" ? onWeb(at.twin!, ["mail_web", "comment"], true) : onWeb(at.twin!, ["mail_web", "bio"]);
  return { ...at, twin };
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
    case "setup-web-paste":
      return setup(webSetup(fx, "paste"));
    case "setup-web-clearance":
      return setup(webSetup(fx, "clearance"));
    case "overview-web": {
      const twins = fx.page.twins.map((t, i) =>
        i === 0 ? { ...t, channels: [...t.channels, webChannel("mail_web", "needs_sign_in"), webChannel("comment")] } : t,
      );
      return { state: { ...ready, page: { ...fx.page, twins } }, route: { view: "twins" } };
    }
    case "voice":
      return {
        state: {
          ...ready,
          page: fx.pageAfter,
          details: { [partners]: fx.setup.golive },
          previews: { [partners]: { load: "ready", value: fx.previews[partners] } },
        },
        route: { view: "twin_voice", id: partners },
      };
    case "mission":
      return { state: ready, route: { view: "twin_mission", id: desk!.id, mission: desk!.missions.find((m) => !m.practice && m.state === "open")!.id } };
    case "draft":
      return { state: ready, route: { view: "twin_draft", id: desk!.id, draft: desk!.waiting[0]!.id } };
    default:
      return { state: ready, route: { view: "twins" } };
  }
}
