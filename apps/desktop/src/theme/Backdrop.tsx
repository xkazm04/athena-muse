import { useEffect, useRef } from "react";
import { SPEED_REST, startCurrent, type Current } from "./current";

export interface BackdropProps {
  /** 1 at rest, about 1.8 while Athena works; eases between values */
  speed?: number;
  className?: string;
}

const REDUCED = "(prefers-reduced-motion: reduce)";

/**
 * One full-bleed canvas behind a window. The bloom, shafts and vignette are CSS (backdrop.css), so
 * the theme still stands if the canvas never paints. Put it first in a positioned parent.
 */
export function Backdrop({ speed = SPEED_REST, className }: BackdropProps) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const current = useRef<Current | null>(null);
  const speedRef = useRef(speed);
  speedRef.current = speed;

  useEffect(() => {
    const el = host.current;
    const cv = canvas.current;
    if (!el || !cv) return;
    const mq = window.matchMedia(REDUCED);
    let cur: Current | null = null;

    const mount = () => {
      cur?.stop();
      cur = startCurrent(cv, { reduced: mq.matches, speed: speedRef.current });
      current.current = cur;
      const r = el.getBoundingClientRect();
      cur.resize(r.width, r.height, window.devicePixelRatio || 1);
    };
    mount();

    const ro = new ResizeObserver(([entry]) => {
      const box = entry?.contentRect;
      if (box && cur) cur.resize(box.width, box.height, window.devicePixelRatio || 1);
    });
    ro.observe(el);
    const relook = () => cur?.relook();
    const themeWatch = new MutationObserver(relook);
    themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const scheme = window.matchMedia("(prefers-color-scheme: light)");
    mq.addEventListener("change", mount);
    scheme.addEventListener("change", relook);
    const wake = () => cur?.wake();
    window.addEventListener("pointermove", wake, { passive: true });

    return () => {
      cur?.stop();
      current.current = null;
      ro.disconnect();
      themeWatch.disconnect();
      mq.removeEventListener("change", mount);
      scheme.removeEventListener("change", relook);
      window.removeEventListener("pointermove", wake);
    };
  }, []);

  useEffect(() => {
    current.current?.setSpeed(speed);
  }, [speed]);

  return (
    <div ref={host} className={className ? `backdrop ${className}` : "backdrop"} aria-hidden="true">
      <div className="backdrop__shafts" />
      <canvas ref={canvas} className="backdrop__current" />
      <div className="backdrop__vignette" />
    </div>
  );
}
