// @vitest-environment node
// The stage's code rules, applied to the twins page's stylesheets: a reduced-motion block per file, type
// sizes from --fs-* tokens only (12 px floor), literal colours and z-indexes only as named custom
// properties, and every selector scoped under [data-twins-view="passport"] so nothing leaks out.
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const ROOT = '[data-twins-view="passport"]';

const files = readdirSync(here)
  .filter((n) => n.endsWith(".css"))
  .map((name) => ({ name, css: readFileSync(join(here, name), "utf8") }));
const uncommented = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, "");

function selectors(css: string): string[] {
  const out: string[] = [];
  for (const m of uncommented(css).matchAll(/([^{};]+)\{/g)) {
    const sel = m[1]!.trim();
    if (!sel || sel.startsWith("@")) continue;
    if (/^(from|to|\d+%)(\s*,\s*(from|to|\d+%))*$/.test(sel)) continue; // keyframe steps
    out.push(...sel.split(",").map((s) => s.trim()));
  }
  return out;
}

function declarations(css: string): [string, string][] {
  return [...uncommented(css).matchAll(/([-\w]+)\s*:\s*([^;{}]+);/g)].map((m) => [m[1]!, m[2]!.trim()]);
}

describe("the twins page's stylesheets", () => {
  it("finds the Passport's stylesheets", () => {
    expect(files.map((f) => f.name).sort()).toEqual(["document.css", "frame.css", "overview.css", "shell.css", "work.css"]);
  });

  it.each(files.map((f) => [f.name, f.css] as const))("%s stills its motion under reduced motion", (_n, css) => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it.each(files.map((f) => [f.name, f.css] as const))("%s sizes type only with --fs-* tokens", (_n, css) => {
    for (const [prop, value] of declarations(css)) {
      if (prop === "font-size") expect(value).toMatch(/^var\(--fs-(xs|sm|md|lg|xl|2xl)\)$/);
      if (prop === "font" && value !== "inherit") expect(value).toMatch(/var\(--fs-/);
      if (prop === "font-size" || prop === "font") {
        const px = [...value.matchAll(/(\d+(?:\.\d+)?)px/g)].map((m) => Number(m[1]));
        expect(px.filter((n) => n < 12)).toEqual([]);
      }
    }
  });

  it.each(files.map((f) => [f.name, f.css] as const))("%s names its colours and layers", (_n, css) => {
    for (const [prop, value] of declarations(css)) {
      if (prop.startsWith("--")) continue;
      expect(value, `${prop}: ${value}`).not.toMatch(/#[0-9a-f]{3,8}\b|\b(rgb|rgba|hsl|hsla)\(/i);
      if (prop === "z-index") expect(value).toMatch(/^var\(--/);
    }
  });

  it.each(files.map((f) => [f.name, f.css] as const))("%s scopes every selector and keyframe", (name, css) => {
    for (const sel of selectors(css)) expect(sel.startsWith(ROOT), `${name}: ${sel}`).toBe(true);
    for (const m of uncommented(css).matchAll(/@keyframes\s+([-\w]+)/g)) expect(m[1]).toMatch(/^twins-/);
    for (const [prop, value] of declarations(css)) {
      if (prop === "animation" || prop === "animation-name") {
        const name0 = value.split(/\s+/).find((w) => /^[a-z][-\w]*$/i.test(w) && !/^(ease|linear|both|infinite|forwards|none|ease-in-out|ease-out|ease-in)$/.test(w));
        if (name0) expect(name0, `${prop}: ${value}`).toMatch(/^twins-/);
      }
    }
  });
});
