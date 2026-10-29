// @vitest-environment node
// The port's code rules for every stylesheet under main/stage/: a reduced-motion block per file, type
// sizes from --fs-* tokens only (12 px floor), literal colours and z-indexes only as named custom
// properties, and each view's selectors scoped under its own root so the two never collide.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return walk(p);
    return name.endsWith(".css") ? [p] : [];
  });
}

const files = walk(here).map((p) => ({ name: relative(here, p).split(sep).join("/"), css: readFileSync(p, "utf8") }));
const uncommented = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, "");

/** Every top-level and nested rule's selector list (at-rule preludes excluded). */
function selectors(css: string): string[] {
  const out: string[] = [];
  const re = /([^{};]+)\{/g;
  for (const m of uncommented(css).matchAll(re)) {
    const sel = m[1]!.trim();
    if (!sel || sel.startsWith("@")) continue;
    if (/^(from|to|\d+%)(\s*,\s*(from|to|\d+%))*$/.test(sel)) continue; // keyframe steps
    out.push(...sel.split(",").map((s) => s.trim()));
  }
  return out;
}

/** Declarations as [property, value], custom properties included. */
function declarations(css: string): [string, string][] {
  return [...uncommented(css).matchAll(/([-\w]+)\s*:\s*([^;{}]+);/g)].map((m) => [m[1]!, m[2]!.trim()]);
}

describe("the stage's stylesheets", () => {
  it("finds the shell's and the parts' stylesheets", () => {
    const names = files.map((f) => f.name);
    expect(names).toContain("stage.css");
    expect(names).toContain("parts/parts.css");
  });

  it.each(files.map((f) => [f.name, f.css] as const))("%s stills its motion under reduced motion", (_name, css) => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it.each(files.map((f) => [f.name, f.css] as const))("%s sizes type only with --fs-* tokens", (_name, css) => {
    for (const [prop, value] of declarations(css)) {
      if (prop === "font-size") expect(value).toMatch(/^var\(--fs-(xs|sm|md|lg|xl|2xl)\)$/);
      if (prop === "font" && value !== "inherit") expect(value).toMatch(/var\(--fs-/);
      if (prop === "font-size" || prop === "font") {
        const px = [...value.matchAll(/(\d+(?:\.\d+)?)px/g)].map((m) => Number(m[1]));
        expect(px.filter((n) => n < 12)).toEqual([]);
      }
    }
  });

  it.each(files.map((f) => [f.name, f.css] as const))("%s names its colours and layers", (_name, css) => {
    for (const [prop, value] of declarations(css)) {
      if (prop.startsWith("--")) continue; // a named local custom property may hold a literal
      expect(value, `${prop}: ${value}`).not.toMatch(/#[0-9a-f]{3,8}\b|\b(rgb|rgba|hsl|hsla)\(/i);
      if (prop === "z-index") expect(value).toMatch(/^var\(--/);
    }
  });

  it.each([
    ["drawing", '[data-stage-view="drawing"]'],
    ["orbit", '[data-stage-view="orbit"]'],
  ])("scopes every selector in %s/*.css under its root", (view, root) => {
    for (const f of files.filter((x) => x.name.startsWith(`${view}/`))) {
      for (const sel of selectors(f.css)) expect(sel.startsWith(root), `${f.name}: ${sel}`).toBe(true);
      for (const m of uncommented(f.css).matchAll(/@keyframes\s+([-\w]+)/g)) expect(m[1]).toMatch(new RegExp(`^${view}-`));
    }
  });
});
