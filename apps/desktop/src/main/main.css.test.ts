// @vitest-environment node
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const css = readFileSync(join(here, "main.css"), "utf8");
/** The main window's other sheets (ADR 0016) hold to the same rules as main.css. */
const SHEETS = ["shell/depth.css", "shell/surface.css", "shell/idiom.css"];

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

  it.each(SHEETS)("%s: sizes from --fs-* tokens only, none under 12 px, and a reduced-motion block", (name) => {
    const sheet = readFileSync(join(here, name), "utf8");
    const sizes = [...sheet.matchAll(/font-size:\s*([^;]+);/g)].map((m) => m[1]!.trim());
    expect(sizes.length).toBeGreaterThan(0);
    for (const s of sizes) expect(s).toMatch(/^var\(--fs-(xs|sm|md|lg|xl|2xl)\)$/);
    for (const m of sheet.matchAll(/\bfont:\s*([^;]+);/g)) {
      if (m[1]!.trim() !== "inherit") expect(m[1]).toMatch(/var\(--fs-/);
    }
    expect(sheet).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
