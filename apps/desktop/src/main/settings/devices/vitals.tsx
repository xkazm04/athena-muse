// A computer's room, as the Devices level says it (portable ADR 0143, ADR 0017 here).
//
// Every computer's daemon measures its own CPU, RAM, GPU, power and disk, decides from them how many
// background tasks fit, and names the reason work has to wait. The constellation says the gate's one
// word under each computer ("room ok", "tight", "full"); a node's drawer says the figures behind it as
// facts, beside the presence it already states.
//
// Unknown is never zero: a figure the daemon could not measure is `null` on the wire, and here it
// reads "unknown" or is left out, never as an empty bar. A GPU list is left out when the probe could
// not run (`null`) and says "none" when it ran and found none (`[]`). A phone is not measured (it runs
// no daemon), so it has no rows; a computer with no vitals says why in one row: none yet, or none
// lately when it has not answered.

import { useEffect, type CSSProperties } from "react";
import type { Presence } from "../../../lib/fleet";
import type { GpuVitals, Room, Vitals } from "../../../lib/vitals";
import { Fact } from "./parts";
import "./vitals.css";

/** The gate's word for a computer's room, as a node's caption says it. */
export const ROOM_WORD: Readonly<Record<Room, string>> = { ok: "room ok", tight: "tight", full: "full" };

/**
 * The lines at which the gate holds background work (`athena/vitals/__init__.py`): a bar at one is
 * drawn in the warning hue. Not the 85% slot line: between the two the room is "tight" (no further
 * task fits) but nothing is held. CPU holds only after three samples in a row, so one reading at its
 * line means "about to hold", never "held"; the held sentence says when it is.
 */
export const RAM_HOLD_PCT = 92;
export const CPU_HOLD_PCT = 90;

/** How often an open computer's figures are read again: the presence probe's hello beat. */
export const VITALS_REREAD_MS = 30_000;

/** The room word for a caption, or `null` when the room is unknown or nothing was measured. */
export function roomWord(vitals: Vitals | null | undefined): string | null {
  return vitals?.room ? ROOM_WORD[vitals.room] : null;
}

/** A caption with the room word after it, when there is one: "Online · room ok". */
export function withRoom(caption: string, vitals: Vitals | null | undefined): string {
  const room = roomWord(vitals);
  return room ? `${caption} · ${room}` : caption;
}

/** The room as a screen reader says it, where a lone "tight" after a dot would be read as noise. */
const ROOM_SAID: Readonly<Record<Room, string>> = { ok: "room ok", tight: "room is tight", full: "no room" };

/** The same, for an accessible name or a sentence: "online, room is tight"; nothing when unknown. */
export function roomSaid(vitals: Vitals | null | undefined): string | null {
  return vitals?.room ? ROOM_SAID[vitals.room] : null;
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const pct = (n: number) => `${Math.round(n)}%`;

/** Megabytes as gigabytes a person reads: whole above 10, one decimal below. */
export function gbFigure(mb: number): string {
  const gb = mb / 1024;
  return gb >= 10 ? String(Math.round(gb)) : String(Math.round(gb * 10) / 10);
}

export const gb = (mb: number) => `${gbFigure(mb)} GB`;

/**
 * A small bar with its figure beside it. `value` is 0 to 1 (clamped); `null` draws no bar at all, only
 * the words, because an empty bar would say zero.
 */
export function Meter({
  label,
  value,
  text,
  high = false,
}: {
  /** What the bar measures, for a screen reader: "CPU", "RAM". */
  label: string;
  value: number | null;
  /** The figure in words, shown beside the bar and read as its value. */
  text: string;
  /** At the line where the gate holds work: the bar takes the warning hue. */
  high?: boolean;
}) {
  if (value === null) return <span className="m-vmeter__text">{text}</span>;
  const fill = Math.min(1, Math.max(0, value));
  return (
    <span className="m-vmeter" data-high={high ? "1" : undefined}>
      <span
        className="m-vmeter__bar"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(fill * 100)}
        aria-valuetext={text}
      >
        <span className="m-vmeter__fill" style={{ "--fill": fill } as CSSProperties} />
      </span>
      <span className="m-vmeter__text" aria-hidden="true">
        {text}
      </span>
    </span>
  );
}

/** One GPU in a line: its name, then whatever of its memory and load was measured. */
export function gpuWords(gpu: GpuVitals): string {
  const parts = [gpu.name];
  if (gpu.vram_total_mb !== null) {
    parts.push(
      gpu.vram_used_mb !== null ? `${gbFigure(gpu.vram_used_mb)} of ${gb(gpu.vram_total_mb)} VRAM` : `${gb(gpu.vram_total_mb)} VRAM`,
    );
  }
  if (gpu.util_pct !== null) parts.push(`${pct(gpu.util_pct)} busy`);
  return parts.join(" · ");
}

export function powerWords(vitals: Pick<Vitals, "power" | "battery_pct">): string {
  if (vitals.power === "mains") return "On mains";
  if (vitals.power === "battery") return vitals.battery_pct !== null ? `On battery, ${vitals.battery_pct}%` : "On battery";
  return "unknown";
}

/**
 * The facts of a computer's room, to sit inside the drawer's `Facts`. `presence` is the peer's, to
 * tell "not heard lately" (asleep, out of reach) from "none yet" (online, or not checked); this
 * computer passes `"online"`, since it is the one measuring.
 */
export function VitalsFacts({ vitals, presence }: { vitals: Vitals | null | undefined; presence: Presence | null }) {
  if (!vitals) {
    const quiet = presence === "asleep" || presence === "unreachable";
    return <Fact label="Vitals">{quiet ? "Not heard lately" : "No vitals yet"}</Fact>;
  }
  const room = vitals.room ? ROOM_WORD[vitals.room] : "room unknown";
  const ramText =
    vitals.ram_pct === null
      ? "RAM unknown"
      : `RAM ${pct(vitals.ram_pct)}${vitals.ram_total_mb !== null ? ` of ${gb(vitals.ram_total_mb)}` : ""}`;
  return (
    <>
      <Fact label="Room">
        {room}
        <span className="m-vitals__sub">{plural(vitals.slots, "task slot")}</span>
      </Fact>
      <Fact label="Load">
        <span className="m-vitals__load">
          <Meter
            label="CPU"
            value={vitals.cpu_pct === null ? null : vitals.cpu_pct / 100}
            text={vitals.cpu_pct === null ? "CPU unknown" : `CPU ${pct(vitals.cpu_pct)}`}
            high={vitals.cpu_pct !== null && vitals.cpu_pct >= CPU_HOLD_PCT}
          />
          <Meter
            label="RAM"
            value={vitals.ram_pct === null ? null : vitals.ram_pct / 100}
            text={ramText}
            high={vitals.ram_pct !== null && vitals.ram_pct >= RAM_HOLD_PCT}
          />
        </span>
      </Fact>
      {vitals.gpus === null ? null : (
        <Fact label={vitals.gpus.length > 1 ? "GPUs" : "GPU"}>
          {vitals.gpus.length === 0
            ? "none"
            : vitals.gpus.map((gpu, i) => (
                <span key={i} className="m-vitals__line">
                  {gpuWords(gpu)}
                </span>
              ))}
        </Fact>
      )}
      <Fact label="Power">{powerWords(vitals)}</Fact>
      <Fact label="Disk">{vitals.disk_free_mb === null ? "unknown" : `${gb(vitals.disk_free_mb)} free`}</Fact>
    </>
  );
}

/** The gate's reason background work waits on that computer, in its own words; nothing when none. */
export function HeldLine({ vitals }: { vitals: Vitals | null | undefined }) {
  if (!vitals?.held) return null;
  return <p className="m-vitals__held">{vitals.held}</p>;
}

/**
 * The bus says a room's word when it changes, not its figures: while a computer's figures are open,
 * the list is read again on the beat of the hello that carries a peer's.
 */
export function useVitalsReread(active: boolean, load: () => Promise<unknown> | void): void {
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => void load(), VITALS_REREAD_MS);
    return () => clearInterval(timer);
  }, [active, load]);
}
