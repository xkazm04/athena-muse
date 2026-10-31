// Line-art glyphs for the depth tiles (ADR 0016), drawn in the variant's manner: a 120 x 90 box, the
// interface blue for what matters, muted strokes for the rest, one floating group. Decorative only.

import type { ReactNode } from "react";
import type { PlaceKey } from "./Depth";

const tint = (pct: number, color = "var(--accent)") => `color-mix(in srgb, ${color} ${pct}%, transparent)`;

const DRAWINGS: Record<PlaceKey, ReactNode> = {
  // a core with two walled orbits and their moons
  projects: (
    <>
      <ellipse cx="60" cy="46" rx="48" ry="20" fill="none" stroke="var(--muted)" strokeWidth="1.5" />
      <ellipse cx="60" cy="46" rx="30" ry="12" fill="none" stroke="var(--accent)" strokeOpacity=".6" strokeWidth="1.5" />
      <circle cx="60" cy="46" r="11" fill={tint(22)} stroke="var(--focus)" strokeWidth="2" />
      <circle cx="60" cy="46" r="4" fill="var(--foreground)" />
      <circle cx="90" cy="42" r="5" fill="var(--card-bg)" stroke="var(--accent)" strokeWidth="1.5" />
      <circle cx="18" cy="52" r="6" fill={tint(25, "var(--role-agent)")} stroke="var(--role-agent)" strokeWidth="1.5" />
      <circle cx="96" cy="62" r="4" fill={tint(30, "var(--status-success)")} stroke="var(--status-success)" />
    </>
  ),
  // the variant's chores: steps climbing to the one that is done
  chores: (
    <>
      <path d="M16 68 L40 46 L62 54 L90 22" fill="none" stroke="var(--accent)" strokeOpacity=".45" strokeDasharray="2 4" />
      <circle cx="16" cy="68" r="5" fill="var(--btn-primary)" stroke="var(--accent)" />
      <circle cx="40" cy="46" r="8" fill={tint(25, "var(--role-agent)")} stroke="var(--role-agent)" strokeWidth="1.5" />
      <circle cx="62" cy="54" r="6" fill={tint(20, "var(--role-external)")} stroke="var(--role-external)" strokeWidth="1.5" />
      <circle cx="90" cy="22" r="15" fill={tint(18)} stroke="var(--focus)" strokeWidth="2" />
      <circle cx="90" cy="22" r="6" fill="var(--foreground)" />
      <circle cx="102" cy="60" r="4" fill={tint(30, "var(--status-success)")} stroke="var(--status-success)" />
    </>
  ),
  // a twin's document: a passport with her stamp, and the one it speaks for behind it
  twins: (
    <>
      <rect x="26" y="12" width="44" height="60" rx="5" fill={tint(6)} stroke="var(--muted)" strokeWidth="1.5" />
      <rect x="46" y="20" width="48" height="62" rx="5" fill="var(--card-bg)" stroke="var(--accent)" strokeWidth="2" />
      <path d="M58 40 C58 33 64 29 70 29 C76 29 82 33 82 40 L58 40 Z" fill={tint(18)} stroke="var(--focus)" strokeWidth="1.6" />
      <path d="M56 52h28M56 60h22M56 68h26" stroke="var(--foreground)" strokeWidth="2" strokeLinecap="round" strokeOpacity=".7" />
      <circle cx="90" cy="74" r="9" fill="none" stroke="var(--role-human)" strokeWidth="1.8" strokeDasharray="3 2" />
    </>
  ),
  // what waits on you: a card with the person's pink mark and the check that signs it
  athena: (
    <>
      <rect x="20" y="18" width="70" height="46" rx="7" fill={tint(8)} stroke="var(--muted-foreground)" strokeWidth="1.5" />
      <rect x="32" y="28" width="70" height="46" rx="7" fill="var(--card-bg)" stroke="var(--accent)" strokeWidth="2" />
      <path d="M42 44h34M42 52h24" stroke="var(--foreground)" strokeWidth="2" strokeLinecap="round" strokeOpacity=".75" />
      <circle cx="90" cy="40" r="5" fill="var(--role-human)" />
      <path d="M78 62 l5 5 l10 -11" fill="none" stroke="var(--focus)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  // the variant's mind: a cut stone with the light at its heart
  settings: (
    <>
      <path d="M60 8 L86 26 L80 62 L60 78 L40 62 L34 26 Z" fill={tint(10)} stroke="var(--focus)" strokeWidth="2" />
      <path
        d="M60 8 L60 78 M34 26 L86 26 M40 62 L80 62 M34 26 L60 46 L86 26 M40 62 L60 46 L80 62"
        stroke="var(--accent)"
        strokeOpacity=".45"
        fill="none"
      />
      <circle cx="60" cy="46" r="6" fill="var(--foreground)" />
    </>
  ),
};

export function Glyph({ place, size = 108 }: { place: PlaceKey; size?: number }) {
  return (
    <svg className="m-glyph" viewBox="0 0 120 90" width={size} height={(size * 3) / 4} aria-hidden="true" focusable="false">
      <g className="m-glyph__float">{DRAWINGS[place]}</g>
    </svg>
  );
}
