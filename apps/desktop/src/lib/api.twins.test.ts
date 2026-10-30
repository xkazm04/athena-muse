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

const lines = (...events: unknown[]) =>
  fetchMock.mockImplementationOnce(() =>
    Promise.resolve(new Response(events.map((e) => JSON.stringify(e)).join("\n"), { status: 200 })),
  );

describe("twin routes", () => {
  it("builds the overview, create and one twin", async () => {
    expect(await called(api.twins)).toEqual({ method: "GET", url: "/twins" });
    expect(await called(() => api.createTwin("spc_1"))).toEqual({ method: "POST", url: "/twins", body: { space_id: "spc_1" } });
    expect(await called(() => api.twin("tw_1"))).toEqual({ method: "GET", url: "/twins/tw_1" });
  });

  it("builds every setup route, with its body", async () => {
    const t = "/twins/tw_1";
    expect(await called(() => api.twinConfirm("tw_1", ["p1"]))).toEqual({ method: "POST", url: `${t}/confirm`, body: { pieces: ["p1"] } });
    expect(await called(() => api.twinDrop("tw_1", ["p2"]))).toEqual({ method: "POST", url: `${t}/drop`, body: { pieces: ["p2"] } });
    expect(await called(() => api.twinSamples("tw_1", ["s1"]))).toEqual({ method: "POST", url: `${t}/samples`, body: { ids: ["s1"] } });
    const dials = { dials: { formality: 3 }, preset: "Friendly pro" };
    expect(await called(() => api.twinDials("tw_1", dials))).toEqual({ method: "POST", url: `${t}/dials`, body: dials });
    expect(await called(() => api.twinPages("tw_1", ["pg1"]))).toEqual({ method: "POST", url: `${t}/pages`, body: { ids: ["pg1"] } });
    expect(await called(() => api.twinChores("tw_1", ["c1"]))).toEqual({ method: "POST", url: `${t}/chores`, body: { ids: ["c1"] } });
    const level = {
      channel: "gmail" as const,
      autonomy: "assist" as const,
      bar: 80,
      split: { first_message: "assist" as const, reply: "auto" as const },
    };
    expect(await called(() => api.twinAutonomy("tw_1", level))).toEqual({ method: "POST", url: `${t}/autonomy`, body: level });
    const fact = { id: "f1", keep: false, reason: "it changes" };
    expect(await called(() => api.twinMemory("tw_1", fact))).toEqual({ method: "POST", url: `${t}/memory`, body: fact });
    const mark = { turn: "t3", mark: "edited" as const, edited_text: "mine" };
    expect(await called(() => api.twinMark("tw_1", mark))).toEqual({ method: "POST", url: `${t}/rehearse/mark`, body: mark });
    expect(await called(() => api.twinGoLive("tw_1"))).toEqual({ method: "POST", url: `${t}/golive` });
    expect(await called(() => api.twinPause("tw_1"))).toEqual({ method: "POST", url: `${t}/pause` });
  });

  it("builds the mission routes", async () => {
    const body = { thread: "th_1", goal: "a yes" };
    expect(await called(() => api.startMission("tw_1", body))).toEqual({ method: "POST", url: "/twins/tw_1/missions", body });
    expect(await called(() => api.mission("tw_1", "ms_1"))).toEqual({ method: "GET", url: "/twins/tw_1/missions/ms_1" });
    expect(await called(() => api.twinPreview("tw_1"))).toEqual({ method: "GET", url: "/twins/tw_1/preview" });
  });

  it("streams say and rehearse as NDJSON events", async () => {
    const seen: string[] = [];
    lines({ type: "start", turn_id: "t", engine: "scripted", simulated: true }, { type: "ask", ask: {} });
    expect(await called(() => api.twinSay("tw_1", { text: "", choice: "As me" }, (e) => seen.push(e.type)))).toEqual({
      method: "POST",
      url: "/twins/tw_1/say",
      body: { text: "", choice: "As me" },
    });
    lines({ type: "turn", turn: {} }, { type: "outcome", state: "resolved" });
    expect(await called(() => api.twinRehearse("tw_1", "a yes", (e) => seen.push(e.type)))).toEqual({
      method: "POST",
      url: "/twins/tw_1/rehearse",
      body: { goal: "a yes" },
    });
    expect(seen).toEqual(["start", "ask", "turn", "outcome"]);
  });
});

describe("connector routes", () => {
  it("builds every connector route and unwraps the list", async () => {
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve(new Response(JSON.stringify({ connections: [{ kind: "gmail" }] }), { status: 200 })),
    );
    expect(await api.connections()).toEqual([{ kind: "gmail" }]);
    expect(await called(() => api.connect("notion", { key: "k" }))).toEqual({
      method: "POST",
      url: "/connectors/notion/connect",
      body: { key: "k" },
    });
    expect(await called(() => api.connectFlow("gmail"))).toEqual({ method: "GET", url: "/connectors/gmail/flow" });
    expect(await called(() => api.disconnect("gmail"))).toEqual({ method: "POST", url: "/connectors/gmail/disconnect" });
    expect(await called(() => api.probeConnection("notion"))).toEqual({ method: "POST", url: "/connectors/notion/probe" });
  });
});
