import { describe, expect, it } from "vitest";
import { CATALOG, ROUTES } from "./contract";

describe("contract", () => {
  it("gates every action that changes a brief, an app or a memory she did not just write", () => {
    expect(CATALOG.propose_brief).toBe("gated");
    expect(CATALOG.add_app).toBe("gated");
    expect(CATALOG.forget).toBe("gated");
  });
  it("names /run", () => {
    expect(ROUTES.run).toBe("/run");
  });
});
