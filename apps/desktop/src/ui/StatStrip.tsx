import type { ReactNode } from "react";

export interface StatTile {
  key: string;
  label: string;
  /** Omitted when nobody measured it: the tile says "-", never 0. */
  value?: number | string;
  /** The small line under the value ("of 3 twins", "est."). */
  unit?: ReactNode;
  /** A status or person tone the skin may colour ("human", "moved"). */
  tone?: string;
  /** A small drawing inside the tile (a split bar, a row of dots). */
  draw?: ReactNode;
}

export interface StatStripProps {
  tiles: readonly StatTile[];
  label: string;
  /** While reading: this many quiet placeholder tiles, no fake numbers. */
  busy?: number;
  className?: string;
}

/** A row of stat tiles: a label, one value and its small line. An unmeasured value reads "-". */
export function StatStrip({ tiles, label, busy = 0, className = "" }: StatStripProps) {
  const cls = `ui-stats ${className}`.trim();
  if (busy > 0) {
    return (
      <div className={cls} aria-busy="true" aria-label={label}>
        {Array.from({ length: busy }, (_, i) => (
          <div key={i} className="ui-stat ui-stat--wait" data-role="stat-tile">
            <span className="ui-stat__sk ui-stat__sk--l" />
            <span className="ui-stat__sk ui-stat__sk--v" />
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className={cls} role="group" aria-label={label}>
      {tiles.map((t) => (
        <div key={t.key} className="ui-stat" data-role="stat-tile" data-tone={t.tone || undefined}>
          <span className="ui-stat__l">{t.label}</span>
          <span className="ui-stat__v">
            <b>{t.value === undefined || t.value === "" ? "-" : t.value}</b>
            {t.unit !== undefined && t.unit !== "" && <span className="ui-stat__u">{t.unit}</span>}
          </span>
          {t.draw}
        </div>
      ))}
    </div>
  );
}
