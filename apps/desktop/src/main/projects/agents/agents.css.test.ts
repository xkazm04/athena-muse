// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// --- the sheet ---

describe("agents css", () => {
  const css = readFileSync(fileURLToPath(new URL("./agents.css", import.meta.url)), "utf8");

  it("sets every font-size from an --fs-* token (12 px is the smallest)", () => {
    const found = [...css.matchAll(/font-size:\s*([^;]+);/g)].map((m) => m[1]!.trim());
    expect(found.length).toBeGreaterThan(0);
    for (const s of found) expect(s).toMatch(/^var\(--fs-(xs|sm|md|lg|xl|2xl)\)$/);
  });

  it("uses no colour that is not a token", () => {
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(css).not.toMatch(/\b(rgb|rgba|hsl|hsla)\(/);
  });

  it("keeps long text inside its plane: the config scrolls in its block, notes and names wrap", () => {
    expect(css).toMatch(/\.m-agent-config__text \{[^}]*overflow: auto;[^}]*max-width: 100%|\.m-agent-config__text \{[^}]*max-width: 100%;[^}]*overflow: auto;/);
    expect(css).toMatch(/\.m-agent-note__text \{[^}]*overflow-wrap: anywhere;/);
    expect(css).toMatch(/\.m-agent-wrap \{[^}]*overflow-wrap: anywhere;/);
    // No fixed width anywhere a narrow window could be pushed past.
    expect(css).not.toMatch(/(?:^|[\s;{])(?:min-)?width:\s*\d+px/);
  });

  it("stills its own motion under reduced motion", () => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
