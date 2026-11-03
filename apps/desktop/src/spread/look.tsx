// The book's two look switches (the prototype's "Calm motion" and "Dark"). They write the same setting
// as Settings > Look (ADR 0012), so the choice lands in both windows; where the daemon cannot be
// reached (the preview), the look is painted on this window alone.

import { useEffect, useState } from "react";
import * as api from "../lib/api";
import type { LookBody } from "../lib/contract";
import { applyLook, DEFAULT_LOOK, MOTION_CHOICES, THEME_CHOICES, TYPE_SCALES } from "../ui/look";

interface Painted {
  calm: boolean;
  dark: boolean;
}

const darkQuery = (): MediaQueryList | null =>
  typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: light)") : null;

/** What the window wears now, read from the attributes the look writes. */
export function painted(): Painted {
  const root = document.documentElement;
  const theme = root.getAttribute("data-theme");
  return {
    calm: root.getAttribute("data-motion") === "calm",
    dark: theme ? theme === "dark" : !(darkQuery()?.matches ?? false),
  };
}

function usePainted(): Painted {
  const [now, setNow] = useState(painted);
  useEffect(() => {
    const read = () => setNow(painted());
    const watch = new MutationObserver(read);
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-motion"] });
    const q = darkQuery();
    q?.addEventListener?.("change", read);
    return () => {
      watch.disconnect();
      q?.removeEventListener?.("change", read);
    };
  }, []);
  return now;
}

/** One of `ok`, read from an attribute without a cast; else the default. */
const pick = <T extends string>(v: string | null, ok: readonly T[], d: T): T => ok.find((x) => x === v) ?? d;

async function choose(body: LookBody): Promise<void> {
  try {
    applyLook((await api.setLook(body)).look);
  } catch {
    const root = document.documentElement;
    applyLook({
      theme: body.theme ?? pick(root.getAttribute("data-theme"), THEME_CHOICES, DEFAULT_LOOK.theme),
      type_scale: pick(root.getAttribute("data-type-scale"), TYPE_SCALES, DEFAULT_LOOK.type_scale),
      motion: body.motion ?? pick(root.getAttribute("data-motion"), MOTION_CHOICES, DEFAULT_LOOK.motion),
    });
  }
}

export function LookSwitches() {
  const { calm, dark } = usePainted();
  return (
    <>
      <button type="button" className="btn btn-quiet btn-sm" aria-pressed={calm} onClick={() => void choose({ motion: calm ? "system" : "calm" })}>
        Calm motion
      </button>
      <button
        type="button"
        className="btn btn-quiet btn-sm"
        aria-label={`Switch to the ${dark ? "light" : "dark"} look`}
        onClick={() => void choose({ theme: dark ? "light" : "dark" })}
      >
        {dark ? "Light" : "Dark"}
      </button>
    </>
  );
}
