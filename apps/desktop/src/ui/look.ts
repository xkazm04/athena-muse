// The look both windows paint (ADR 0012): the theme, the text size and calm motion. The daemon holds
// the rows; each window reads them at boot and repaints on the `settings` event, so a choice made in
// one window lands in the other at once. This file is the one writer of `data-type-scale` and
// `data-motion`; the theme goes through the theme's own `applyTheme`.

import type { Look, MotionChoice, ThemeChoice, TypeScale } from "../lib/contract";
import { applyTheme } from "../theme";
import "./look.css";

export const DEFAULT_LOOK: Look = { theme: "auto", type_scale: "standard", motion: "system" };

export const THEME_CHOICES: readonly ThemeChoice[] = ["auto", "dark", "light"];
export const TYPE_SCALES: readonly TypeScale[] = ["standard", "large"];
export const MOTION_CHOICES: readonly MotionChoice[] = ["system", "calm"];

/** Paint a look on this window. A missing look paints the defaults. */
export function applyLook(look: Look | null | undefined): void {
  const chosen = look ?? DEFAULT_LOOK;
  applyTheme(chosen.theme);
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.setAttribute("data-type-scale", chosen.type_scale);
  root.setAttribute("data-motion", chosen.motion);
}

/** Calm is chosen here, or the system asks for reduced motion: either stills what moves. */
export function motionStilled(): boolean {
  if (typeof document !== "undefined" && document.documentElement.getAttribute("data-motion") === "calm") return true;
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}
