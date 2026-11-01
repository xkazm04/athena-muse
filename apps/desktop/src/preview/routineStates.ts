// What Athena does on her own, in every row state: the routines the daemon generated through its real
// host on the simulated channel (main/report/routines.fixture.json, never edited by hand), and the
// reasons that fixture cannot produce, DERIVED here from its rows (each says so in its name). Used by
// the preview and the strip's tests.

import type { Routine, RoutineList, RoutineRun, RunList, SkipReason } from "../lib/contract";
import fixture from "../main/report/routines.fixture.json";
import { ROUTINES_IDLE, type RoutinesState } from "../main/store";

interface RoutinesFixture {
  simulated: boolean;
  routines: RoutineList;
  runs: Record<string, RunList>;
}

export const ROUTINES_FIXTURE = fixture as unknown as RoutinesFixture;
export const FIXTURE_ROUTINES: Routine[] = ROUTINES_FIXTURE.routines.routines;
export const ROUTINES_SPACE = FIXTURE_ROUTINES[0]!.space_id;

/** Twelve minutes after the last run the daemon recorded. */
export const ROUTINES_NOW = new Date(
  Math.max(...FIXTURE_ROUTINES.map((r) => new Date(r.last_run?.ended ?? r.last_run?.started ?? 0).getTime())) + 12 * 60 * 1000,
);

const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x)) as T;
export const byKind = (kind: Routine["kind"]): Routine => clone(FIXTURE_ROUTINES.find((r) => r.kind === kind)!);
export const runsOf = (id: string): RoutineRun[] => clone(ROUTINES_FIXTURE.runs[id]?.runs ?? []);

/** One of the fixture's routines with another last run, named as derived. */
function derived(kind: Routine["kind"], tag: string, run: Partial<RoutineRun>, over: Partial<Routine> = {}): Routine {
  const r = byKind(kind);
  const last = r.last_run!;
  return {
    ...r,
    ...over,
    id: `${r.id}-${tag}`,
    name: `${r.name} (derived)`,
    last_run: { ...last, id: `${last.id}-${tag}`, found: 0, kept: 0, cards: 0, note: undefined, reason: undefined, of: undefined, spent_usd: undefined, ...run },
  };
}

const skipped = (kind: Routine["kind"], reason: SkipReason, over: Partial<Routine> = {}, note?: string) =>
  derived(kind, reason, { outcome: "skipped", reason, ...(note ? { note } : {}) }, over);

/** The stats routine as its earlier run left it: her browser was closed (a run the fixture kept). */
export function noBrowserRow(): Routine {
  const r = byKind("stats");
  const closed = runsOf(r.id).find((x) => x.reason === "no_browser")!;
  return { ...r, id: `${r.id}-no_browser`, name: `${r.name} (its earlier run)`, last_run: closed };
}

/** Every reason and outcome the fixture's own runs do not show. */
export function derivedRows(): Routine[] {
  return [
    noBrowserRow(),
    skipped("watch", "live_turn"),
    skipped("inbox", "signed_out", { url: "https://mail.example.test/inbox", state: "on", next_at: byKind("watch").next_at }),
    skipped("outreach", "no_twin"),
    skipped("watch", "running"),
    skipped("stats", "paused", { state: "paused", next_at: undefined }),
    skipped("stats", "no_engine"),
    derived("watch", "partial", { outcome: "partial", of: 4, found: 3, kept: 1, cards: 1, spent_usd: 0.08, note: "1 creator page could not be read." }),
    derived("outreach", "ran", { outcome: "ran", found: 3, kept: 1, cards: 1, spent_usd: 0.04, note: "Drafted 1 offer for the person to sign." }),
    derived("watch", "failed", { outcome: "failed", note: "It stopped on an unexpected error." }),
  ];
}

const ready = (list: Routine[]): RoutinesState => ({ ...ROUTINES_IDLE, load: "ready", list });

export interface NamedRoutines {
  name: string;
  state: RoutinesState;
}

export const ROUTINE_STATES: NamedRoutines[] = [
  { name: "from the daemon", state: ready(clone(FIXTURE_ROUTINES)) },
  { name: "every reason", state: ready([...clone(FIXTURE_ROUTINES), ...derivedRows()]) },
  { name: "could not read", state: { ...ROUTINES_IDLE, load: "problem", problem: "Athena's background service is not reachable (simulated)" } },
  { name: "no routines", state: ready([]) },
];
