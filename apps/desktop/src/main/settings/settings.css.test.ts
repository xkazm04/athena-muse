// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(fileURLToPath(new URL("./settings.css", import.meta.url)), "utf8");

describe("settings css", () => {
  it("sets every font-size from an --fs-* token", () => {
    const found = [...css.matchAll(/font-size:\s*([^;]+);/g)].map((m) => m[1]!.trim());
    expect(found.length).toBeGreaterThan(0);
    for (const s of found) expect(s).toMatch(/^var\(--fs-(xs|sm|md|lg|xl|2xl)\)$/);
  });

  it("stills its own motion under reduced motion", () => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
