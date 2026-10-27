import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { resetConnection } from "./daemon";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  resetConnection();
  sessionStorage.setItem("athena.connection", JSON.stringify({ url: "http://127.0.0.1:1", token: "t" }));
  fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response("{}", { status: 200 })));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

async function called(run: () => Promise<unknown>): Promise<{ method: string; url: string; body?: unknown }> {
  await run();
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
  return {
    method: init.method ?? "GET",
    url: url.replace("http://127.0.0.1:1", ""),
    body: init.body ? JSON.parse(init.body as string) : undefined,
  };
}

describe("api paths", () => {
  it("builds the simple routes", async () => {
    expect(await called(api.health)).toMatchObject({ method: "GET", url: "/health" });
    expect(await called(api.engine)).toMatchObject({ method: "GET", url: "/engine" });
    expect(await called(() => api.saveKey("k"))).toMatchObject({ method: "POST", url: "/engine/key", body: { key: "k" } });
    expect(await called(api.deleteKey)).toMatchObject({ method: "DELETE", url: "/engine/key" });
    expect(await called(api.probe)).toMatchObject({ method: "POST", url: "/engine/probe" });
    expect(await called(api.spaces)).toMatchObject({ url: "/spaces" });
  });

  it("puts the space id in the path", async () => {
    expect(await called(() => api.space("spc_1"))).toMatchObject({ method: "GET", url: "/spaces/spc_1" });
    expect(await called(() => api.updateSpace("spc_1", { name: "N" }))).toMatchObject({
      method: "POST",
      url: "/spaces/spc_1",
      body: { name: "N" },
    });
    expect(await called(() => api.eraseSpace("spc_1"))).toMatchObject({ method: "DELETE", url: "/spaces/spc_1" });
  });

  it("addresses core as 'core' and adds query only when given", async () => {
    expect((await called(() => api.memory(""))).url).toBe("/spaces/core/memory");
    expect((await called(() => api.memory("spc_1", "fact", 20))).url).toBe("/spaces/spc_1/memory?kind=fact&limit=20");
    expect((await called(() => api.makeCore("spc_1", "mem_9"))).url).toBe("/spaces/spc_1/memory/mem_9/core");
  });

  it("builds settings, conversation, cards, decision and ledger", async () => {
    expect(await called(api.activeSpace)).toMatchObject({ url: "/settings/active-space" });
    expect(await called(() => api.setActiveSpace("spc_2"))).toMatchObject({ method: "POST", body: { space_id: "spc_2" } });
    expect((await called(() => api.conversation("spc_1"))).url).toBe("/conversation?space_id=spc_1");
    expect((await called(() => api.cards("waiting"))).url).toBe("/cards?state=waiting");
    expect((await called(() => api.cards())).url).toBe("/cards");
    expect(await called(() => api.decide("crd_1", "approve"))).toMatchObject({
      method: "POST",
      url: "/decisions/crd_1",
      body: { verdict: "approve" },
    });
    expect((await called(() => api.ledger(50))).url).toBe("/ledger?limit=50");
  });

  it("builds the chore routes, escaping the id", async () => {
    expect(await called(() => api.chore("care-circle"))).toMatchObject({ method: "GET", url: "/chores/care-circle" });
    expect((await called(() => api.chore("a b"))).url).toBe("/chores/a%20b");
  });
});

describe("api list routes", () => {
  it("unwraps the daemon's {spaces}, {turns} and {cards} answers", async () => {
    const answer = (body: unknown) =>
      fetchMock.mockImplementationOnce(() => Promise.resolve(new Response(JSON.stringify(body), { status: 200 })));
    answer({ spaces: [{ id: "spc_1" }] });
    expect(await api.spaces()).toEqual([{ id: "spc_1" }]);
    answer({ turns: [{ id: "turn_1" }] });
    expect(await api.conversation("")).toEqual([{ id: "turn_1" }]);
    answer({ cards: [{ id: "card_1" }] });
    expect(await api.cards("resolved")).toEqual([{ id: "card_1" }]);
    answer({ chores: [{ id: "care-circle" }] });
    expect(await api.chores()).toEqual([{ id: "care-circle" }]);
  });
});
