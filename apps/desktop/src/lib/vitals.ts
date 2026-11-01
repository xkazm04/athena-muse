// A PC's vitals, as the window reads them (portable ADR 0143, ADR 0017 here): `src/athena/vitals/`.
//
// Each daemon measures its own room (CPU, RAM, GPU, power, disk) with the standard library, decides how
// many background tasks fit and names the reason work has to wait, and shares the snapshot with its
// paired computers on the hello the presence probe already sends.
//
// The shapes are the Python's, field for field, absent values `null` (never omitted): `null` is "could
// not measure", never zero. `gpus` is `[]` when the probe ran and found none. `runs` and `sleep` are
// always `null` in this daemon (it has no ledger of runs and no sleep cycle); they keep the wire shape.

/** The gate's word for a PC's room: `null` when the figures it needs are unknown. */
export type Room = "ok" | "tight" | "full";

export interface GpuVitals {
  name: string;
  util_pct: number | null;
  vram_total_mb: number | null;
  vram_used_mb: number | null;
}

export interface Vitals {
  at: string;
  cpu_pct: number | null;
  cores: number | null;
  ram_total_mb: number | null;
  ram_free_mb: number | null;
  ram_pct: number | null;
  gpus: GpuVitals[] | null;
  power: "mains" | "battery" | null;
  battery_pct: number | null;
  disk_free_mb: number | null;
  room: Room | null;
  /** How many background tasks the RAM has room for right now, 0 to 3. */
  slots: number;
  /** Why background work is waiting, as a sentence for a person; `null` when nothing waits. */
  held: string | null;
  runs: null;
  sleep: null;
}

/** `GET /vitals`. */
export interface VitalsResponse {
  ok: boolean;
  vitals: Vitals;
}
