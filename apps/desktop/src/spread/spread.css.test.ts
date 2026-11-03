// @vitest-environment node
// The book's sheets hold to the brief's floor (ADR 0024): every size from a token, none under 12 px,
// every colour through the theme, and a still form for every move.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");
const SHEETS = { "spread/spread.css": read("./spread.css"), "athena/her.css": read("../athena/her.css") };
const tokens = read("../theme/tokens.css");

/** The px a size token resolves to: its number, or for a clamp() each px in it. */
function pxOf(token: string): number[] {
  const m = new RegExp(`--${token}:\\s*([^;]+);`).exec(tokens);
  expect(m, token).toBeTruthy();
  return [...m![1]!.matchAll(/(\d+(?:\.\d+)?)px/g)].map((x) => Number(x[1]));
}

describe.each(Object.entries(SHEETS))("%s", (_name, css) => {
  it("sets every font size from an --fs-* token, and every token is 12 px or more", () => {
    const sizes = [...css.matchAll(/font-size:\s*([^;]+);/g)].map((m) => m[1]!.trim());
    expect(sizes.length).toBeGreaterThan(0);
    for (const s of sizes) {
      const t = /^var\(--(fs-[a-z0-9-]+)\)$/.exec(s);
      expect(t, s).toBeTruthy();
      for (const px of pxOf(t![1]!)) expect(px).toBeGreaterThanOrEqual(12);
    }
    for (const m of css.matchAll(/\bfont:\s*([^;]+);/g)) if (m[1]!.trim() !== "inherit") expect(m[1]).toMatch(/var\(--fs-/);
  });

  it("names no colour of its own outside the gradients' black (theme tokens repaint it)", () => {
    const hex = [...css.matchAll(/#[0-9a-f]{3,8}\b/gi)].map((m) => m[0]);
    expect(hex).toEqual([]);
  });

  it("stills its motion under reduced motion", () => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});

describe("the book's additions to Loop Tide", () => {
  it("are tokens, the gutter defined for dark and both light blocks", () => {
    expect(tokens.match(/--gutter-shade:/g)).toHaveLength(3);
    for (const t of ["--page-l", "--page-r", "--dur-turn", "--dur-page", "--fs-ask", "--fs-read", "--fs-answer"]) expect(tokens).toContain(`${t}:`);
  });

  it("scopes every rule of the book under its own root", () => {
    const css = SHEETS["spread/spread.css"].replace(/\/\*[\s\S]*?\*\//g, "");
    const selectors = [...css.replace(/@keyframes[^{]+\{(?:[^{}]*\{[^}]*\})*[^}]*\}/g, "").matchAll(/(^|\})\s*([^{}@]+)\{/g)]
      .map((m) => m[2]!.trim())
      .filter((s) => s && !/^(from|to|\d+%)/.test(s));
    expect(selectors.length).toBeGreaterThan(50);
    for (const group of selectors) for (const sel of group.split(",")) expect(sel.trim(), sel).toMatch(/^\[data-spread\]/);
  });
});
