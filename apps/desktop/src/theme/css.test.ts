// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { fileURLToPath } from "node:url";
const css = (name: string) => readFileSync(fileURLToPath(new URL(`./${name}`, import.meta.url)), "utf8");

describe("theme css", () => {
  it.each(["base.css", "coat.css", "seal.css"])("%s stills its motion under prefers-reduced-motion", (name) => {
    expect(css(name)).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it("parks the arcs at the upper left", () => {
    expect(css("coat.css")).toContain("rotate(225deg)");
    expect(css("seal.css")).toContain("rotate(225deg)");
  });

  it("follows the system unless a theme is pinned, and defines both light blocks equally", () => {
    const t = css("tokens.css");
    expect(t).toContain(':root:not([data-theme="dark"])');
    const accent = t.match(/--accent-text: #0055c4;/g) ?? [];
    expect(accent).toHaveLength(2);
  });

  it("has no type size below 12px", () => {
    const sizes = [...css("tokens.css").matchAll(/--fs-\w+: (\d+)px/g)].map((m) => Number(m[1]));
    expect(Math.min(...sizes)).toBe(12);
  });
});
