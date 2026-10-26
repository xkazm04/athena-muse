import { afterEach, describe, expect, it, vi } from "vitest";
import {
  FPS_ACTIVE,
  FPS_LONG_EXPOSURE,
  IDLE_AFTER_MS,
  LOOPS,
  drawStill,
  makeMotes,
  moteCount,
  place,
  startCurrent,
  targetFps,
  type Ctx,
} from "./current";

function seeded(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

function recorder(): Ctx & { arcs: number; fills: number } {
  const ctx = {
    arcs: 0,
    fills: 0,
    globalAlpha: 1,
    globalCompositeOperation: "source-over" as GlobalCompositeOperation,
    fillStyle: "",
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    beginPath: vi.fn(),
    setTransform: vi.fn(),
    arc: vi.fn(() => {
      ctx.arcs++;
    }),
    fill: vi.fn(() => {
      ctx.fills++;
    }),
  };
  return ctx as unknown as Ctx & { arcs: number; fills: number };
}

afterEach(() => vi.unstubAllGlobals());

describe("the loops", () => {
  it("share out all the motes", () => {
    expect(LOOPS.reduce((n, l) => n + l.w, 0)).toBeCloseTo(1, 5);
  });

  it("keeps every mote on the stage-ish and never on a closed outline of one radius", () => {
    const motes = makeMotes(400, seeded(7));
    const radii = new Set<number>();
    for (const m of motes) {
      const [x, y] = place(m, m.th, 1000, 600);
      expect(x).toBeGreaterThan(-300);
      expect(x).toBeLessThan(1300);
      expect(y).toBeGreaterThan(-100);
      expect(y).toBeLessThan(700);
      radii.add(Math.round(Math.hypot(x - 500, y - 300) / 10));
    }
    expect(radii.size).toBeGreaterThan(20);
  });

  it("scales the mote count with the stage within bounds", () => {
    expect(moteCount(100, 100)).toBe(60);
    expect(moteCount(1280, 800)).toBe(284);
    expect(moteCount(4000, 3000)).toBe(420);
  });
});

describe("frame budget", () => {
  it("runs at 30 fps and drops to 8 after 15 s without anyone near", () => {
    expect(targetFps(0)).toBe(FPS_ACTIVE);
    expect(targetFps(IDLE_AFTER_MS - 1)).toBe(30);
    expect(targetFps(IDLE_AFTER_MS)).toBe(FPS_LONG_EXPOSURE);
    expect(FPS_LONG_EXPOSURE).toBe(8);
  });
});

describe("reduced motion", () => {
  it("drawStill paints the motes and the trails once", () => {
    const ctx = recorder();
    const motes = makeMotes(10, seeded(1));
    drawStill(ctx, motes, 800, 500, { colour: "#4aa3ff", light: false });
    expect(ctx.arcs).toBe(10 * 41);
    expect(ctx.globalAlpha).toBe(1);
  });

  it("startCurrent with reduced paints one still frame and schedules no frame", () => {
    const ctx = recorder();
    const canvas = { getContext: () => ctx, width: 0, height: 0 } as unknown as HTMLCanvasElement;
    const raf = vi.fn();
    vi.stubGlobal("requestAnimationFrame", raf);
    const cur = startCurrent(canvas, {
      reduced: true,
      rng: seeded(3),
      look: () => ({ colour: "#4aa3ff", light: false }),
    });
    cur.resize(800, 500, 3);
    expect(raf).not.toHaveBeenCalled();
    expect(ctx.arcs).toBeGreaterThan(0);
    // dpr is capped at 2
    expect(canvas.width).toBe(1600);
    const painted = ctx.arcs;
    cur.setSpeed(1.8);
    cur.wake();
    expect(ctx.arcs).toBe(painted);
    cur.stop();
  });

  it("startCurrent without reduced does ask for frames", () => {
    const ctx = recorder();
    const canvas = { getContext: () => ctx, width: 0, height: 0 } as unknown as HTMLCanvasElement;
    const raf = vi.fn(() => 1);
    vi.stubGlobal("requestAnimationFrame", raf);
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    const cur = startCurrent(canvas, { reduced: false, look: () => ({ colour: "#fff", light: false }) });
    cur.resize(800, 500, 1);
    expect(raf).toHaveBeenCalledOnce();
    cur.stop();
  });
});
