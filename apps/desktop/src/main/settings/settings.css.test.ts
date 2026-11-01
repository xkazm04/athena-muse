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

  it("fits the five tiles in one row", () => {
    expect(css).toMatch(/\.m-settings__tiles \{[^}]*repeat\(5, minmax\(0, 1fr\)\)/);
  });
});

describe("devices css", () => {
  const devices = readFileSync(fileURLToPath(new URL("./devices/devices.css", import.meta.url)), "utf8");

  it("sets every font-size from an --fs-* token", () => {
    const found = [...devices.matchAll(/font-size:\s*([^;]+);/g)].map((m) => m[1]!.trim());
    expect(found.length).toBeGreaterThan(0);
    for (const s of found) expect(s).toMatch(/^var\(--fs-(xs|sm|md|lg|xl|2xl)\)$/);
  });

  it("uses no colour that is not a token", () => {
    expect(devices).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(devices).not.toMatch(/\b(rgb|rgba|hsl|hsla)\(/);
  });

  it("stills its own motion under reduced motion", () => {
    expect(devices).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
