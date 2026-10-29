// The Passport's small marks: line icons, the twin's monogram portrait in her seal's dome language, a
// rubber stamp, how sure a draft was against the bar, and the readiness meter.

import { useId, type ReactNode } from "react";

const PATHS = {
  gmail: ["M3 6.5h18v11H3z", "M3.5 7l8.5 6.5L20.5 7"],
  notion: ["M5 4.5h11l3 3v12H5z", "M9 16V9l6 7V9"],
  calendar: ["M4 6h16v14H4z", "M4 10h16M8 3.5v4M16 3.5v4"],
  slack: ["M9 4v9M15 11v9M4 15h9M11 9h9"],
  pencil: ["M4 20l1-4.5L15.5 5a2 2 0 0 1 3 3L8 18.5z", "M13.5 7l3 3"],
  nib: ["M12 21l-6-8 3-8h6l3 8z", "M12 13v8M10.5 11a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0 -3 0"],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  x: ["M6 6l12 12M18 6L6 18"],
  risk: ["M12 4l9 16H3z", "M12 10v4.5M12 17.2v.3"],
  send: ["M4 12l16-8-6 16-2.5-6.5z"],
  hand: [
    "M8 12V6a1.5 1.5 0 0 1 3 0v5M11 11V4.5a1.5 1.5 0 0 1 3 0V11M14 11V6a1.5 1.5 0 0 1 3 0v7c0 4-2.5 7-6 7s-5-2-6.5-5L3 11.5a1.4 1.4 0 0 1 2.3-1.6L8 13",
  ],
  clock: ["M12 3.5a8.5 8.5 0 1 0 0 17a8.5 8.5 0 1 0 0-17", "M12 7.5V12l3 2"],
  book: ["M4 5.5c3-1.5 5.5-1.5 8 0v14c-2.5-1.5-5-1.5-8 0z", "M20 5.5c-3-1.5-5.5-1.5-8 0v14c2.5-1.5 5-1.5 8 0z"],
  chat: ["M4 5h16v11H9l-5 4z"],
  layers: ["M12 4l8.5 4.5L12 13 3.5 8.5z", "M3.5 12.5L12 17l8.5-4.5", "M3.5 16.5L12 21l8.5-4.5"],
  arrow: ["M5 12h14M13 6l6 6-6 6"],
  back: ["M19 12H5M11 6l-6 6 6 6"],
  close: ["M6 6l12 12M18 6L6 18"],
  retry: ["M4.5 12a7.5 7.5 0 1 0 2.2-5.3", "M4.5 4.5v4h4"],
  key: ["M8.5 15.5a4 4 0 1 1 3-3l8 8M16.5 16.5l2-2M14.5 14.5l1.5-1.5"],
  mail: ["M3 6.5h18v11H3z", "M3.5 7l8.5 6.5L20.5 7"],
  plus: ["M12 5v14M5 12h14"],
  eye: [
    "M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12z",
    "M12 9.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5",
  ],
} as const;

export type IconName = keyof typeof PATHS;

/** A line icon on the 24 grid, in the current colour. */
export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      className="ic"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

const DOME =
  "M8 50 C8 25 21 10 38 10 C55 10 68 25 68 50 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 Z";
const TENT = ["M22 54 q-3 7 0 14", "M33 55 q3 8 0 15", "M44 55 q-3 8 0 15", "M55 54 q3 7 0 14"];

export interface PortraitProps {
  letter: string;
  size?: number;
  /** Her sketch: the twin is still being issued. */
  pencil?: boolean;
  /** The printed form before anything is written. */
  blank?: boolean;
}

/** The twin's portrait: her seal's dome with the twin's own letter on the orb. */
export function Portrait({ letter, size = 72, pencil = false, blank = false }: PortraitProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  if (blank) {
    return (
      <svg className="portrait portrait--blank" viewBox="0 0 76 76" width={size} height={size} aria-hidden="true" focusable="false">
        <path d={DOME} fill="none" stroke="var(--border-emphasis)" strokeWidth="1.6" strokeDasharray="4 4" />
        <circle cx="38" cy="33" r="14" fill="none" stroke="var(--border-default)" strokeWidth="1.6" strokeDasharray="3 4" />
      </svg>
    );
  }
  if (pencil) {
    return (
      <svg className="portrait portrait--pencil" viewBox="0 0 76 76" width={size} height={size} aria-hidden="true" focusable="false">
        <g fill="none" stroke="var(--role-agent)" strokeWidth="1.6" strokeDasharray="4 3" strokeLinecap="round">
          {TENT.map((d) => (
            <path key={d} d={d} />
          ))}
          <path d={DOME} />
          <circle cx="38" cy="33" r="16" />
        </g>
        <text x="38" y="39.5" textAnchor="middle" className="portrait__l" fill="var(--role-agent)">
          {letter}
        </text>
      </svg>
    );
  }
  return (
    <svg className="portrait" viewBox="0 0 76 76" width={size} height={size} aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id={`${uid}d`} cx="35%" cy="25%" r="85%">
          <stop offset="0" stopColor="var(--seal-dome-a)" />
          <stop offset="1" stopColor="var(--seal-dome-b)" />
        </radialGradient>
        <radialGradient id={`${uid}o`} cx="40%" cy="35%" r="70%">
          <stop offset="0" stopColor="var(--seal-orb-core)" />
          <stop offset="1" stopColor="var(--seal-orb-edge)" />
        </radialGradient>
      </defs>
      <g fill="none" stroke="var(--seal-dome-a)" strokeWidth="2.4" strokeLinecap="round" opacity=".75">
        {TENT.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
      <path d={DOME} fill={`url(#${uid}d)`} />
      <path d="M17 36 C19 25 27 17 37 15.5" fill="none" stroke="var(--seal-gleam)" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="38" cy="33" r="16" fill={`url(#${uid}o)`} />
      <text x="38" y="39.5" textAnchor="middle" className="portrait__l" fill="var(--seal-mark)">
        {letter}
      </text>
    </svg>
  );
}

export type StampTone = "human" | "warning" | "success" | "error" | "info";

export interface StampProps {
  text: string;
  tone: StampTone;
  sub?: string;
  /** It lands now: the one-time press. */
  fresh?: boolean;
  className?: string;
  role?: string;
}

/** A rubber stamp: waits for you (pink), held (amber), went or connected (green). */
export function Stamp({ text, tone, sub, fresh = false, className = "", role }: StampProps) {
  return (
    <span className={`stamp ${fresh ? "stamp--fresh" : ""} ${className}`.trim()} data-tone={tone} data-role={role}>
      <span className="stamp__t">{text}</span>
      {sub && <span className="stamp__s">{sub}</span>}
    </span>
  );
}

/** How sure it was against the channel's bar; with no bar (not on Auto), only how sure. */
export function Sure({ value, bar, compact = false }: { value: number; bar?: number; compact?: boolean }) {
  const ok = bar === undefined || value >= bar;
  return (
    <div className={`sure ${compact ? "sure--compact" : ""}`} data-ok={String(ok)}>
      <div className="sure__track" role="img" aria-label={`How sure it was: ${value}. Your bar: ${bar ?? "none"}.`}>
        <span className="sure__fill" style={{ width: `${value}%` }} />
        {bar !== undefined && <span className="sure__bar" style={{ left: `${bar}%` }} />}
      </div>
      <span className="sure__words">
        How sure it was: <b>{value}</b>
        {bar !== undefined && ` · your bar ${bar}`}
      </span>
    </div>
  );
}

export function Meter({ value }: { value: number }) {
  return (
    <span className="meter" aria-hidden="true">
      <i style={{ width: `${value}%` }} />
    </span>
  );
}

/** The quiet "Invented example" label every simulated screen carries. */
export function InventedBadge({ title, children }: { title: string; children: ReactNode }) {
  return (
    <span className="badge invented" data-tone="warning" title={title} data-role="invented">
      {children}
    </span>
  );
}
