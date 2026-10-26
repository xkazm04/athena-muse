import { useEffect, useId, useState, type ReactNode } from "react";

export type SealState = "rest" | "working" | "waiting" | "signed";

export interface SealProps {
  state: SealState;
  /** pixel size of the square seal (default 76) */
  size?: number;
  /** cards waiting for the person; shown as a small badge when above zero */
  count?: number;
  onClick?: () => void;
  /** accessible name */
  label: string;
  /** fires once when "signed" has finished and the seal has settled back to rest */
  onSettled?: () => void;
}

/** How long the signed flourish holds before the seal settles back to rest. */
export const SETTLE_MS = 1600;

// Geometry given by the owner; the viewBox is 0 0 76 76.
const TENTACLES = ["M22 54 q-3 7 0 14", "M33 55 q3 8 0 15", "M44 55 q-3 8 0 15", "M55 54 q3 7 0 14"];
const DOME =
  "M8 50 C8 25 21 10 38 10 C55 10 68 25 68 50 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 q-5 6 -10 0 Z";
const GLEAM = "M17 36 C19 25 27 17 37 15.5";
const MARK = "M31.5 41 L38 24 L44.5 41 M34 35.5 L42 35.5";
const CHECK = "M29 33 L35.5 39.5 L48 25";

/** Her seal: a small jellyfish dome with an orb and the A. State is told by the ring around it. */
export function Seal({ state, size = 76, count = 0, onClick, label, onSettled }: SealProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    setSettled(false);
    if (state !== "signed") return;
    const t = setTimeout(() => {
      setSettled(true);
      onSettled?.();
    }, SETTLE_MS);
    return () => clearTimeout(t);
    // onSettled is read when the timer fires; a new callback identity must not restart the flourish.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  const shown: SealState = state === "signed" && settled ? "rest" : state;
  const className = `seal seal--${shown}`;
  const body: ReactNode = (
    <>
      <svg className="seal__svg" viewBox="0 0 76 76" width={size} height={size} aria-hidden="true" focusable="false">
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
        {/* the orbit: blue arc normally, the person's pink ring when something waits */}
        <circle className="seal__orbit seal__orbit--arc" cx="38" cy="38" r="42" pathLength="100" />
        <circle className="seal__orbit seal__orbit--human" cx="38" cy="38" r="42" pathLength="100" />
        <g className="seal__tentacles">
          {TENTACLES.map((d, i) => (
            <path key={d} className="seal__tentacle" d={d} style={{ ["--i" as string]: i }} />
          ))}
        </g>
        <path className="seal__dome" d={DOME} fill={`url(#${uid}d)`} />
        <path className="seal__gleam" d={GLEAM} />
        <circle className="seal__orb" cx="38" cy="33" r="16" fill={`url(#${uid}o)`} />
        <circle className="seal__ring" cx="38" cy="33" r="18.5" />
        <path className="seal__mark" d={MARK} />
        <path className="seal__check" d={CHECK} pathLength="100" />
        <circle className="seal__sign" cx="38" cy="38" r="42" pathLength="100" />
      </svg>
      {count > 0 && (
        <span className="seal__count" aria-hidden="true">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </>
  );

  if (onClick) {
    return (
      <button type="button" className={className} data-state={shown} onClick={onClick} aria-label={label}>
        {body}
      </button>
    );
  }
  return (
    <span className={className} data-state={shown} role="img" aria-label={label}>
      {body}
    </span>
  );
}
