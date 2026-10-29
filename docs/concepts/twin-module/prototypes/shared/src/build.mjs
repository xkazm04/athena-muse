// Builds ../twin-data.js and ../twin-data.json from twin.src.mjs. Run: node src/build.mjs
// Every derived field is computed here: the pieces after each frame, coverage, ready, the dials,
// each twin's readiness and the overview stats. The output is byte-identical on every run.
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as src from "./twin.src.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const clone = (v) => JSON.parse(JSON.stringify(v));

// A place's coverage: 1 = holds a confirmed piece (your words are confirmed when added),
// 0.5 = only her unconfirmed proposals, 0 = empty.
function coverageOf(pieces) {
  const out = {};
  for (const p of src.places) {
    const mine = pieces.filter((x) => x.place === p.id);
    out[p.id] = mine.some((x) => x.confirmed) ? 1 : mine.length ? 0.5 : 0;
  }
  return out;
}
const readyOf = (cov) => src.places.every((p) => cov[p.id] >= p.required);

// Readiness of a twin: the mean of the places setup requires (required > 0), as a whole percent.
const core = src.places.filter((p) => p.required > 0).map((p) => p.id);
const readiness = (filled) => Math.round((100 * core.reduce((s, id) => s + filled[id], 0)) / core.length);

let pieces = [];
let dials = clone(src.style.dials);
let firstReady = null;
const frames = src.frames.map((f, index) => {
  for (const o of f.ops) {
    if (o.op === "add") pieces.push({ ...o.piece, confirmed: o.piece.origin === "you" });
    if (o.op === "change") {
      pieces = pieces.map((p) => (p.id === o.piece.id ? { ...p, ...o.piece, confirmed: o.piece.origin === "you" ? true : p.confirmed } : p));
    }
    if (o.op === "dial") dials = dials.map((d) => (d.id === o.dial ? { ...d, value: o.value, source: o.source } : d));
  }
  for (const id of f.confirm) {
    if (!pieces.some((p) => p.id === id)) throw new Error(`frame ${index} confirms unknown piece ${id}`);
    pieces = pieces.map((p) => (p.id === id ? { ...p, confirmed: true } : p));
  }
  const coverage = coverageOf(pieces);
  const ready = readyOf(coverage);
  if (ready && firstReady === null) firstReady = index;
  return { index, ...clone(f), pieces: clone(pieces), dials: clone(dials), coverage, ready, readiness: readiness(coverage) };
});
if (firstReady === null) throw new Error("the setup never becomes ready");

// The overview. Stats are sums over the twins' rows; null weeks are skipped, and a stat whose
// every input is null stays null (renders "-").
const sumOf = (rows, f) => {
  const vals = rows.map(f).filter((v) => v !== null && v !== undefined);
  return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) * 100) / 100 : null;
};
function overviewOf(twins) {
  const rows = twins.map((t) => ({
    ...clone(t),
    readiness: readiness(t.filled),
    open_missions: t.missions.filter((m) => m.state === "open" || m.state === "handed_back").length,
    waiting_count: t.waiting.length,
  }));
  const stats = {
    live: rows.filter((t) => t.state === "live").length,
    waiting_for_you: sumOf(rows, (t) => t.waiting.length + t.missions.filter((m) => m.state === "handed_back").length),
    missions_open: sumOf(rows, (t) => t.open_missions),
    sent_week: sumOf(rows, (t) => t.week.sent),
    sent_alone_week: sumOf(rows, (t) => t.week.sent_alone),
    held_by_risk_week: sumOf(rows, (t) => t.week.held_by_risk),
    cost_usd_week: sumOf(rows, (t) => t.week.cost_usd),
  };
  return { rows, stats };
}

const last = frames[frames.length - 1];
const partnersLive = {
  ...clone(src.twins.find((t) => t.id === "tw_partners")),
  state: "live",
  since: "2026-10-29",
  channels: [
    { kind: "gmail", account: "alex@lowtide-visuals.example", status: "connected", autonomy: "auto", split: { first_message: "assist", replies: "auto" }, bar: 80, health: "active", last_at: src.now },
    { kind: "notion", account: "Low Tide studio", status: "connected", autonomy: "auto", scope: "practice page only", bar: 60, health: "active", last_at: src.now },
  ],
  filled: { ...last.coverage, mission: 1 },
  week: { sent: 0, sent_alone: 0, held_by_risk: 0, median_reply_min: null, cost_usd: 0.31 },
  missions: [{ id: "ms_5", title: "Get Lumen Vale's yes to feature 'Glass Harbor'", with: "Lumen Vale (practice)", channel: "notion", state: "resolved", turns: 5, last_at: src.now, note: "Rehearsed on the practice page. Filed to Notion: Partnerships." }],
  waiting: [],
};

const data = {
  invented: src.invented,
  owner: src.owner,
  now: src.now,
  places: src.places,
  channelKinds: src.channelKinds,
  autonomyLevels: src.autonomyLevels,
  overview: overviewOf(src.twins),
  overview_after_golive: overviewOf(src.twins.map((t) => (t.id === "tw_partners" ? partnersLive : t))),
  setup: {
    twin_id: "tw_partners",
    need: src.need,
    first_ready_frame: firstReady,
    frames,
    connect: src.connect,
    samples: src.samples,
    style: src.style,
    pages: src.pages,
    chorePresets: src.chorePresets,
    autonomy: src.autonomy,
    memory: src.memory,
    rehearsal: src.rehearsal,
    golive: src.golive,
  },
};

const json = JSON.stringify(data, null, 2) + "\n";
writeFileSync(join(here, "..", "twin-data.json"), json);
writeFileSync(join(here, "..", "twin-data.js"), "// Invented data for a design prototype. Generated by src/build.mjs; do not edit.\nwindow.TWIN_DATA = " + json.trimEnd() + ";\n");
console.log(`frames ${frames.length}, first ready at frame ${firstReady}, pieces ${last.pieces.length}, readiness ${last.readiness}%`);
console.log("stats", JSON.stringify(data.overview.stats));
console.log("after", JSON.stringify(data.overview_after_golive.stats));
