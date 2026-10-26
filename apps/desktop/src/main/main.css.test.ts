// @vitest-environment node
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const css = readFileSync(join(here, "main.css"), "utf8");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sources(p);
    return /\.tsx$/.test(name) && !name.includes(".test.") ? [p] : [];
  });
}

describe("main window type sizes", () => {
  it("sets every font-size from an --fs-* token (12 px is the smallest)", () => {
    const sizes = [...css.matchAll(/font-size:\s*([^;]+);/g)].map((m) => m[1]!.trim());
    expect(sizes.length).toBeGreaterThan(0);
    for (const s of sizes) expect(s).toMatch(/^var\(--fs-(xs|sm|md|lg|xl|2xl)\)$/);
  });

  it("uses a token in every font shorthand and no pixel size below 12", () => {
    for (const m of css.matchAll(/\bfont:\s*([^;]+);/g)) {
      if (m[1]!.trim() === "inherit") continue;
      expect(m[1]).toMatch(/var\(--fs-/);
    }
    const px = [...css.matchAll(/font(?:-size)?:[^;]*?(\d+(?:\.\d+)?)px/g)].map((m) => Number(m[1]));
    expect(px.filter((n) => n < 12)).toEqual([]);
  });

  it("sets no inline font sizes in the components", () => {
    for (const file of sources(here)) expect(readFileSync(file, "utf8")).not.toMatch(/fontSize|font-size=/);
  });

  it("stills its own motion under reduced motion", () => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
