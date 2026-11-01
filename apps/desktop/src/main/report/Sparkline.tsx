// A reading over time as one thin line (dataviz rules: one series, one hue, no grid, the latest value
// as the headline, the first and last dates as the only axis words, a crosshair and readout on hover
// or arrow keys). Every number drawn is the daemon's; the line is only placed.

import { useState, type KeyboardEvent, type PointerEvent } from "react";
import type { SeriesPoint } from "../../lib/contract";
import { day, figure } from "./format";

const W = 100;
const H = 40;
const PAD = 4;

export function Sparkline({ series, unit, title }: { series: SeriesPoint[]; unit?: string; title: string }) {
  const [at, setAt] = useState<number | null>(null);
  const n = series.length;
  const vs = series.map((p) => p.v);
  const lo = Math.min(...vs);
  const hi = Math.max(...vs);
  const x = (i: number) => (n === 1 ? W / 2 : (i / (n - 1)) * W);
  const y = (v: number) => (hi === lo ? H / 2 : H - PAD - ((v - lo) / (hi - lo)) * (H - 2 * PAD));
  const d = series.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(2)},${y(p.v).toFixed(2)}`).join(" ");
  const last = series[n - 1]!;
  const first = series[0]!;
  const shown = at === null ? null : series[at]!;
  const pct = (i: number) => `${x(i)}%`;

  const move = (e: PointerEvent<HTMLDivElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    if (!box.width) return;
    const f = Math.min(1, Math.max(0, (e.clientX - box.left) / box.width));
    setAt(Math.round(f * (n - 1)));
  };
  const key = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      const from = at ?? n - 1;
      setAt(Math.min(n - 1, Math.max(0, from + (e.key === "ArrowRight" ? 1 : -1))));
    } else if (e.key === "Escape") setAt(null);
  };

  return (
    <div className="rp-spark">
      <p className="rp-spark__head">
        <b>{figure(last.v)}</b>
        {unit && <span>{unit}</span>}
        <span className="rp-spark__when">latest, {day(last.t)}</span>
      </p>
      <div
        className="rp-spark__plot"
        role="img"
        tabIndex={0}
        aria-label={`${title}: ${n} ${n === 1 ? "reading" : "readings"} from ${day(first.t)} to ${day(last.t)}, latest ${figure(last.v)}${unit ? ` ${unit}` : ""}`}
        onPointerMove={move}
        onPointerLeave={() => setAt(null)}
        onKeyDown={key}
        onBlur={() => setAt(null)}
      >
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
          <path className="rp-spark__line" d={d} vectorEffect="non-scaling-stroke" />
          {at !== null && <line className="rp-spark__cross" x1={x(at)} x2={x(at)} y1={0} y2={H} vectorEffect="non-scaling-stroke" />}
        </svg>
        <i className="rp-spark__dot" style={{ left: pct(n - 1), top: `${(y(last.v) / H) * 100}%` }} aria-hidden="true" />
        {shown && at !== null && (
          <>
            <i className="rp-spark__dot rp-spark__dot--at" style={{ left: pct(at), top: `${(y(shown.v) / H) * 100}%` }} aria-hidden="true" />
            <span className="rp-spark__tip" data-side={at > (n - 1) / 2 ? "left" : "right"} style={{ left: pct(at) }} role="status">
              <b>{figure(shown.v)}</b> {day(shown.t)}
            </span>
          </>
        )}
      </div>
      <p className="rp-spark__axis" aria-hidden="true">
        <span>{day(first.t)}</span>
        <span>{day(last.t)}</span>
      </p>
    </div>
  );
}
