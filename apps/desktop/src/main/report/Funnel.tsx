// Stages a piece of work passes through, as a funnel: one row per stage, in order, a bar in one hue
// whose length places the daemon's count against the largest stage, and the count itself beside it
// (every bar is labelled, so nothing is read from colour or length alone).

import type { StageCount } from "../../lib/contract";
import { figure } from "./format";

export function Funnel({ stages, title }: { stages: StageCount[]; title: string }) {
  const top = Math.max(0, ...stages.map((s) => s.count));
  return (
    <ol className="rp-funnel" aria-label={title}>
      {stages.map((s, i) => (
        <li key={`${i}-${s.label}`} className="rp-funnel__row" data-zero={String(s.count === 0)}>
          <span className="rp-funnel__label">{s.label}</span>
          <span className="rp-funnel__track" aria-hidden="true">
            <i style={{ width: top ? `${(s.count / top) * 100}%` : "0%" }} />
          </span>
          <b className="rp-funnel__n">{figure(s.count)}</b>
        </li>
      ))}
    </ol>
  );
}
