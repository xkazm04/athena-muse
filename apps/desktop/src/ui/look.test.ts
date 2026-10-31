import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { applyLook, motionStilled } from "./look";

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");
const sizes = (css: string) =>
  Object.fromEntries([...css.matchAll(/--fs-(\w+): (\d+)px/g)].map((m) => [m[1]!, Number(m[2])]));

afterEach(() => {
  for (const a of ["data-theme", "data-type-scale", "data-motion"]) document.documentElement.removeAttribute(a);
});

describe("the look", () => {
  it("paints the three attributes; auto leaves the theme to the system", () => {
    applyLook({ theme: "light", type_scale: "large", motion: "calm" });
    const root = document.documentElement;
    expect(root.getAttribute("data-theme")).toBe("light");
    expect(root.getAttribute("data-type-scale")).toBe("large");
    expect(root.getAttribute("data-motion")).toBe("calm");
    expect(motionStilled()).toBe(true);
    applyLook(null);
    expect(root.hasAttribute("data-theme")).toBe(false);
    expect(root.getAttribute("data-motion")).toBe("system");
  });

  it("large text is the theme's sizes under the headings, each 2px up, and never below 12", () => {
    const base = sizes(read("../theme/tokens.css"));
    const large = sizes(read("./look.css"));
    expect(Object.keys(large).sort()).toEqual(["md", "sm", "xs"]);
    for (const [step, px] of Object.entries(large)) expect(px).toBe(base[step]! + 2);
    expect(Math.min(...Object.values(large))).toBeGreaterThanOrEqual(12);
  });

  it("calm stills every animation and transition, as reduced motion does", () => {
    const css = read("./look.css");
    expect(css).toContain(':root[data-motion="calm"] *');
    expect(css).toContain("animation: none !important");
    expect(css).toContain("transition: none !important");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
