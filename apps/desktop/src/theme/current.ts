// The living current behind the main window: motes circulating on three wide, lopsided loops (a
// figure-of-eight, an eddy, a swell). No closed outline is ever drawn; the loop exists only as the
// way the water moves. This file is the engine, free of React so it can be tested without a DOM.

export interface Loop {
  /** share of the motes that ride this loop */
  w: number;
  /** centre and radii, in fractions of the stage */
  cx: number;
  cy: number;
  rx: number;
  ry: number;
  /** radians */
  tilt: number;
  eight: boolean;
  /** how far motes stray off the loop's line */
  spread: number;
}

export const LOOPS: readonly Loop[] = [
  { w: 0.5, cx: 0.52, cy: 0.6, rx: 0.47, ry: 0.15, tilt: -0.08, eight: true, spread: 0.05 },
  { w: 0.26, cx: 0.24, cy: 0.33, rx: 0.2, ry: 0.13, tilt: 0.18, eight: false, spread: 0.07 },
  { w: 0.24, cx: 0.58, cy: 0.84, rx: 0.56, ry: 0.07, tilt: 0.03, eight: false, spread: 0.12 },
];

export interface Mote {
  loop: Loop;
  /** angle on the loop, radians */
  th: number;
  /** offset off the line, as a fraction */
  d: number;
  /** angular speed, radians per second at speed 1 */
  w: number;
  /** radius in css px */
  r: number;
  /** alpha 0..1 */
  a: number;
}

export const FPS_ACTIVE = 30;
export const FPS_LONG_EXPOSURE = 8;
export const IDLE_AFTER_MS = 15_000;
export const DPR_CAP = 2;
export const SPEED_REST = 1;
export const SPEED_WORKING = 1.8;

/** Frames per second the current may spend: full while someone is near, a long exposure after 15 s. */
export function targetFps(idleMs: number): number {
  return idleMs >= IDLE_AFTER_MS ? FPS_LONG_EXPOSURE : FPS_ACTIVE;
}

export function moteCount(cssW: number, cssH: number): number {
  return Math.max(60, Math.min(420, Math.round((cssW * cssH) / 3600)));
}

function pickLoop(r: number): Loop {
  let acc = 0;
  for (const l of LOOPS) {
    acc += l.w;
    if (r <= acc) return l;
  }
  return LOOPS[0]!;
}

/** Roughly normal in -1..1, cheap. */
function bell(rng: () => number): number {
  return (rng() + rng() + rng() - 1.5) / 1.5;
}

export function makeMotes(count: number, rng: () => number = Math.random): Mote[] {
  const motes: Mote[] = [];
  for (let i = 0; i < count; i++) {
    const loop = pickLoop(rng());
    motes.push({
      loop,
      th: rng() * Math.PI * 2,
      d: bell(rng) * loop.spread * 2,
      w: (0.045 + rng() * 0.05) * (loop.eight ? 1 : 1.25),
      r: 0.5 + rng() * rng() * 1.3,
      a: 0.18 + rng() * 0.62,
    });
  }
  return motes;
}

/** Where a mote sits at angle `th`, in css px on a stage `w` by `h`. */
export function place(m: Mote, th: number, w: number, h: number): [number, number] {
  const l = m.loop;
  let x = l.eight ? l.rx * Math.sin(th) : l.rx * Math.cos(th);
  let y = l.eight ? l.ry * Math.sin(2 * th) : l.ry * Math.sin(th);
  x *= 1 + m.d;
  y *= 1 + m.d * 1.6;
  const ct = Math.cos(l.tilt);
  const st = Math.sin(l.tilt);
  return [(l.cx + x * ct - y * st) * w, (l.cy + x * st + y * ct) * h];
}

/** The subset of CanvasRenderingContext2D the current uses, so tests can pass a recorder. */
export type Ctx = Pick<
  CanvasRenderingContext2D,
  "clearRect" | "fillRect" | "beginPath" | "arc" | "fill" | "setTransform"
> & {
  globalAlpha: number;
  globalCompositeOperation: GlobalCompositeOperation;
  fillStyle: string | CanvasGradient | CanvasPattern;
};

export interface Look {
  colour: string;
  /** light themes draw darker ink on paler water, so blending changes */
  light: boolean;
}

function dot(ctx: Ctx, x: number, y: number, r: number, a: number): void {
  ctx.globalAlpha = a;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}

/** The still: each mote's recent path as a long exposure. Reduced motion shows only this. */
export function drawStill(ctx: Ctx, motes: readonly Mote[], w: number, h: number, look: Look): void {
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = look.colour;
  ctx.globalCompositeOperation = look.light ? "source-over" : "lighter";
  const k = look.light ? 0.5 : 1;
  const steps = 40;
  for (const m of motes) {
    const span = 0.9 + m.w * 6;
    for (let i = 0; i < steps; i++) {
      const [x, y] = place(m, m.th - (span * i) / steps, w, h);
      dot(ctx, x, y, m.r * 0.7, m.a * 0.05 * k * (1 - i / steps));
    }
    const [x, y] = place(m, m.th, w, h);
    dot(ctx, x, y, m.r, m.a * 0.7 * k);
  }
  ctx.globalAlpha = 1;
}

export interface CurrentOptions {
  /** prefers-reduced-motion: paint one still frame and never schedule a frame */
  reduced: boolean;
  speed?: number;
  /** reads the live colours; defaults to the canvas's --lt-current and --lt-light */
  look?: () => Look;
  rng?: () => number;
  now?: () => number;
}

export interface Current {
  setSpeed(speed: number): void;
  /** Someone is near: leave the long exposure. Call on pointer movement. */
  wake(): void;
  resize(cssW: number, cssH: number, dpr: number): void;
  /** Colours changed (theme switch). */
  relook(): void;
  stop(): void;
}

function readLook(canvas: HTMLCanvasElement): Look {
  const cs = getComputedStyle(canvas);
  return {
    colour: cs.getPropertyValue("--lt-current").trim() || "#4aa3ff",
    light: cs.getPropertyValue("--lt-light").trim() === "1",
  };
}

export function startCurrent(canvas: HTMLCanvasElement, opts: CurrentOptions): Current {
  const ctx = canvas.getContext("2d") as Ctx | null;
  const now = opts.now ?? (() => performance.now());
  const rng = opts.rng ?? Math.random;
  const getLook = opts.look ?? (() => readLook(canvas));
  let look = getLook();
  let cssW = 0;
  let cssH = 0;
  let dpr = 1;
  let motes: Mote[] = [];
  let speed = opts.speed ?? SPEED_REST;
  let target = speed;
  let lastFrame = 0;
  let lastActive = now();
  let raf = 0;
  let stopped = false;

  const still = () => {
    if (!ctx || !cssW) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawStill(ctx, motes, cssW, cssH, look);
  };

  const frame = () => {
    raf = 0;
    if (stopped || opts.reduced || document.hidden || !ctx) return;
    const t = now();
    const gap = 1000 / targetFps(t - lastActive);
    if (lastFrame && t - lastFrame < gap - 1) {
      raf = requestAnimationFrame(frame);
      return;
    }
    const dt = Math.min(0.25, lastFrame ? (t - lastFrame) / 1000 : 1 / FPS_ACTIVE);
    lastFrame = t;
    speed += (target - speed) * Math.min(1, dt * 1.5);
    // Fade the old frame instead of clearing it: that is the motes' short tail.
    ctx.globalCompositeOperation = "destination-out";
    ctx.globalAlpha = 1;
    ctx.fillStyle = `rgba(0,0,0,${Math.min(0.5, 0.12 * dt * 60)})`;
    ctx.fillRect(0, 0, cssW, cssH);
    ctx.globalCompositeOperation = look.light ? "source-over" : "lighter";
    ctx.fillStyle = look.colour;
    const k = look.light ? 0.85 : 1;
    for (const m of motes) {
      m.th += m.w * speed * dt;
      const [x, y] = place(m, m.th, cssW, cssH);
      dot(ctx, x, y, m.r, m.a * k);
    }
    ctx.globalAlpha = 1;
    raf = requestAnimationFrame(frame);
  };

  const run = () => {
    if (!raf && !stopped && !opts.reduced && !document.hidden) {
      lastFrame = 0;
      raf = requestAnimationFrame(frame);
    }
  };
  const onVisibility = () => {
    if (document.hidden) {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    } else {
      lastActive = now();
      run();
    }
  };
  document.addEventListener("visibilitychange", onVisibility);

  return {
    setSpeed(s) {
      target = s;
      lastActive = now();
    },
    wake() {
      lastActive = now();
    },
    resize(w, h, ratio) {
      cssW = Math.max(1, Math.round(w));
      cssH = Math.max(1, Math.round(h));
      dpr = Math.min(ratio || 1, DPR_CAP);
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
      motes = makeMotes(moteCount(cssW, cssH), rng);
      if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (opts.reduced) still();
      else run();
    },
    relook() {
      look = getLook();
      if (opts.reduced) still();
    },
    stop() {
      stopped = true;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      document.removeEventListener("visibilitychange", onVisibility);
    },
  };
}
