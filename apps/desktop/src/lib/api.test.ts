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

describe("draft routes", () => {
  it("builds every draft route, with its body", async () => {
    expect(await called(() => api.createDraft("a need"))).toEqual({ method: "POST", url: "/drafts", body: { need: "a need" } });
    expect(await called(() => api.getDraft("drf_1"))).toMatchObject({ method: "GET", url: "/drafts/drf_1" });
    expect(await called(() => api.abandonDraft("drf_1"))).toMatchObject({ method: "DELETE", url: "/drafts/drf_1" });
    expect(await called(() => api.draftConfirm("drf_1", ["n2"]))).toEqual({
      method: "POST",
      url: "/drafts/drf_1/confirm",
      body: { node_ids: ["n2"] },
    });
    expect(await called(() => api.draftDrop("drf_1", ["n4"]))).toEqual({
      method: "POST",
      url: "/drafts/drf_1/drop",
      body: { node_ids: ["n4"] },
    });
    expect(await called(() => api.draftPreview("drf_1"))).toEqual({ method: "POST", url: "/drafts/drf_1/preview" });
    const key = { marks: [{ expected_id: "e1", mark: "yes" as const }], missing: [], never: ["pay"] };
    expect(await called(() => api.draftKey("drf_1", key))).toEqual({ method: "PUT", url: "/drafts/drf_1/key", body: key });
    expect(await called(() => api.draftVerdict("drf_1", { verdict: "revise", note: "n" }))).toEqual({
      method: "POST",
      url: "/drafts/drf_1/verdict",
      body: { verdict: "revise", note: "n" },
    });
  });

  it("streams say, write and rehearse as NDJSON events", async () => {
    const lines = (...events: unknown[]) =>
      fetchMock.mockImplementationOnce(() =>
        Promise.resolve(new Response(events.map((e) => JSON.stringify(e)).join("\n"), { status: 200 })),
      );
    const seen: string[] = [];
    lines({ type: "start", turn_id: "t", engine: "scripted", simulated: true }, { type: "done", turn_id: "t", waiting: false });
    expect(
      await called(() => api.draftSay("drf_1", { text: "", choice: "Yes", view: "orbit" }, (e) => seen.push(e.type))),
    ).toEqual({ method: "POST", url: "/drafts/drf_1/say", body: { text: "", choice: "Yes", view: "orbit" } });
    lines({ type: "writing" }, { type: "written", chore_id: "c" });
    expect(await called(() => api.draftWrite("drf_1", (e) => seen.push(e.type)))).toEqual({
      method: "POST",
      url: "/drafts/drf_1/write",
    });
    lines({ type: "phase", index: 1, app: "mail", message: "m" });
    expect((await called(() => api.draftRehearse("drf_1", (e) => seen.push(e.type)))).url).toBe("/drafts/drf_1/rehearse");
    expect(seen).toEqual(["start", "done", "writing", "written", "phase"]);
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
