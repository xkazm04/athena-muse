import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TurnEvent } from "./contract";
import {
  DaemonError,
  UNREACHABLE,
  createNdjsonParser,
  nextBackoff,
  request,
  resetConnection,
  streamRun,
} from "./daemon";

const conn = { url: "http://127.0.0.1:5555", token: "tok" };

beforeEach(() => {
  resetConnection();
  sessionStorage.setItem("athena.connection", JSON.stringify(conn));
});
afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ndjson parser", () => {
  it("joins a line split across chunks and keeps order", () => {
    const seen: TurnEvent[] = [];
    const p = createNdjsonParser((e) => seen.push(e));
    p.push('{"type":"text","del');
    expect(seen).toHaveLength(0);
    p.push('ta":"hi"}\n{"type":"text","delta":"there"}\n{"type":"te');
    expect(seen).toEqual([
      { type: "text", delta: "hi" },
      { type: "text", delta: "there" },
    ]);
    p.push('xt","delta":"!"}');
    p.flush();
    expect(seen.at(-1)).toEqual({ type: "text", delta: "!" });
  });

  it("skips blank and garbled lines", () => {
    const seen: TurnEvent[] = [];
    const p = createNdjsonParser((e) => seen.push(e));
    p.push('\nnot json\n{"type":"text","delta":"ok"}\n');
    expect(seen).toEqual([{ type: "text", delta: "ok" }]);
  });
});

describe("request", () => {
  it("sends the bearer header and parses JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"ok":true,"version":"0.1.0"}', { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const out = await request<{ ok: boolean }>("GET", "/health");
    expect(out.ok).toBe(true);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:5555/health");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("maps a contract error body to DaemonError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response('{"error":"space_busy","reason":"Athena is mid-turn"}', { status: 409 })),
    );
    const err = await request("POST", "/x", {}).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(DaemonError);
    expect(err).toMatchObject({ status: 409, error: "space_busy", reason: "Athena is mid-turn" });
  });

  it("maps a network failure to status 0 with the plain-words reason", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = await request("GET", "/health").catch((e: unknown) => e);
    expect(err).toMatchObject({ status: 0, reason: UNREACHABLE });
  });
});

describe("streamRun", () => {
  it("delivers events as chunks arrive, including a split line", async () => {
    const enc = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(enc.encode('{"type":"start","turn_id":"t1","engine":"scripted","simulated":true}\n{"type":"te'));
        c.enqueue(enc.encode('xt","delta":"a"}\n'));
        c.enqueue(enc.encode('{"type":"done","turn_id":"t1","waiting":false}'));
        c.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status: 200 })));
    const types: string[] = [];
    await streamRun({ text: "hi" }, (e) => types.push(e.type));
    expect(types).toEqual(["start", "text", "done"]);
  });

  it("throws DaemonError for a refused run", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response('{"error":"unauthorized","reason":"no"}', { status: 401 })),
    );
    await expect(streamRun({}, () => {})).rejects.toMatchObject({ status: 401, error: "unauthorized" });
  });
});

describe("backoff", () => {
  it("doubles from 1 s and stops at 10 s", () => {
    expect([1000, 2000, 4000, 8000].map(nextBackoff)).toEqual([2000, 4000, 8000, 10000]);
    expect(nextBackoff(10000)).toBe(10000);
  });
});
