// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("vitals css", () => {
  const css = readFileSync(fileURLToPath(new URL("./vitals.css", import.meta.url)), "utf8");

  it("uses font-size tokens and no colour that is not a token", () => {
    for (const m of css.matchAll(/font-size:\s*([^;]+);/g)) expect(m[1]!.trim()).toMatch(/^var\(--fs-(xs|sm|md|lg|xl|2xl)\)$/);
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(css).not.toMatch(/\b(rgb|rgba|hsl|hsla)\(/);
  });

  it("stills the meter's fill under reduced motion", () => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
