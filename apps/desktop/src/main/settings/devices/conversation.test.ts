import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DaemonError, resetConnection } from "../../../lib/daemon";
import type { TurnFrame } from "../../../lib/fleet";
import { peerTurn } from "../../../lib/relay";
import { VIEW } from "./fixtures";
import { appendLines, CONVERSATION_CAP, IDLE, linesOf, RELAY_ATTEMPTS, type Conversation } from "./conversation";
import { resetDevicesForTests, setDevicesDeps, useDevices, type DevicesClient } from "./store";

const PEER = "dev_0000000000a2";
const JOB = "job_0000000000d1";
const closed = (reason: "finished" | "error" | "expired" = "finished", footer = ""): TurnFrame => ({
  kind: "remote.closed",
  request_id: JOB,
  reason,
  showing: 0,
  total: 0,
  footer,
});
const text = (t: string): TurnFrame => ({ kind: "text.delta", text: t });

async function* frames(list: TurnFrame[]): AsyncGenerator<TurnFrame> {
  for (const f of list) yield f;
}

function client(over: Partial<DevicesClient> = {}): DevicesClient {
  return {
    devices: async () => VIEW,
    overlayPeers: async () => ({ state: "up", peers: [] }) as never,
    renameSelf: async () => ({}),
    setBeacon: async () => ({}),
    openPairing: async () => ({}) as never,
    answerPending: async () => ({}),
    revokeDevice: async () => ({}),
    joinDevice: async () => ({}),
    ...over,
  };
}

beforeEach(() => resetDevicesForTests());
afterEach(() => resetDevicesForTests());

describe("the lines a relayed frame adds", () => {
  it("draws her words, a tool, a waiting card, a stop and the footer", () => {
    expect(linesOf(text("hi"), "Laptop")).toEqual([{ kind: "athena", text: "hi" }]);
    expect(linesOf({ kind: "tool.result", name: "recall", label: "Looked it up", ok: true }, "Laptop")).toEqual([
      { kind: "tool", text: "Looked it up" },
    ]);
    const card = linesOf({ kind: "decision.requested", id: "card_1", action: "propose_brief", label: "Set the brief" }, "Laptop");
    expect(card[0]!.text).toBe("Waiting for your approval on Laptop: Set the brief");
    expect(linesOf({ kind: "turn.error", reason: "engine_unavailable", detail: "No key" }, "Laptop")[0]).toEqual({
      kind: "problem",
      text: "It stopped: No key",
    });
    expect(linesOf(closed("finished", "(showing 2000 of 2005)"), "Laptop")[0]!.text).toBe("(showing 2000 of 2005)");
    expect(linesOf(closed(), "Laptop")).toEqual([]);
    expect(linesOf({ kind: "turn.started", turn_id: "t", engine: "e", simulated: true }, "Laptop")).toEqual([]);
  });

  it("joins her words into one line and caps the box, counting what it dropped", () => {
    let box: Conversation = appendLines(IDLE, [{ kind: "athena", text: "Two " }]);
    box = appendLines(box, [{ kind: "athena", text: "invoices." }]);
    expect(box.lines).toEqual([{ kind: "athena", text: "Two invoices." }]);
    let many: Conversation = IDLE;
    for (let n = 0; n < CONVERSATION_CAP + 10; n += 1) many = appendLines(many, [{ kind: "tool", text: String(n) }]);
    expect(many.lines).toHaveLength(CONVERSATION_CAP);
    expect(many.dropped).toBe(10);
    expect(many.lines[0]!.text).toBe("10");
  });
});

describe("sending a message to a paired computer", () => {
  it("reads the reply back, coming back with `from` after a quiet end", async () => {
    const reads: number[] = [];
    setDevicesDeps({
      client: client({
        sendMessage: async () => ({ request_id: JOB }),
        turn: (_peer, _id, from) => {
          reads.push(from);
          return reads.length === 1
            ? frames([text("Two invoices")])
            : frames([text(" are due."), { kind: "turn.finished", turn_id: "t", waiting: false, text: "Two invoices are due." }, closed()]);
        },
      }),
      now: () => 0,
    });
    await useDevices.getState().load();
    await useDevices.getState().send(PEER, "what is due?");
    expect(reads).toEqual([0, 1]);
    const box = useDevices.getState().conversations[PEER]!;
    expect(box.phase).toBe("done");
    expect(box.requestId).toBe(JOB);
    expect(box.lines.map((l) => l.text)).toEqual(["what is due?", "Two invoices are due."]);
  });

  it("says a refusal under the box, in the daemon's words, and a silent peer in ours", async () => {
    setDevicesDeps({
      client: client({
        sendMessage: async () => {
          throw new DaemonError(429, "bad_request", "Athena is still answering your earlier messages");
        },
        turn: () => frames([]),
      }),
      now: () => 0,
    });
    await useDevices.getState().send(PEER, "again");
    let box = useDevices.getState().conversations[PEER]!;
    expect(box.phase).toBe("error");
    expect(box.problem).toBe("Athena is still answering your earlier messages");

    setDevicesDeps({
      client: client({
        sendMessage: async () => {
          throw new DaemonError(502, "bad_request", "that device did not answer");
        },
        turn: () => frames([]),
      }),
      now: () => 0,
    });
    await useDevices.getState().send(PEER, "hello");
    box = useDevices.getState().conversations[PEER]!;
    expect(box.problem).toContain("did not answer");
    expect(box.problem).toContain("private network");
  });

  it("gives up after RELAY_ATTEMPTS quiet ends and says it is still working there", async () => {
    let reads = 0;
    setDevicesDeps({
      client: client({
        sendMessage: async () => ({ request_id: JOB }),
        turn: () => {
          reads += 1;
          return frames([]);
        },
      }),
      now: () => 0,
    });
    await useDevices.getState().load();
    await useDevices.getState().send(PEER, "slow one");
    expect(reads).toBe(RELAY_ATTEMPTS);
    expect(useDevices.getState().conversations[PEER]!.problem).toContain("still working there");
  });

  it("sends nothing for blank words and says so when the window has no relay", async () => {
    const sendMessage = vi.fn(async () => ({ request_id: JOB }));
    setDevicesDeps({ client: client({ sendMessage, turn: () => frames([]) }), now: () => 0 });
    await useDevices.getState().send(PEER, "   ");
    expect(sendMessage).not.toHaveBeenCalled();
    expect(useDevices.getState().conversations[PEER]).toBeUndefined();

    setDevicesDeps({ client: client(), now: () => 0 });
    await useDevices.getState().send(PEER, "hi");
    expect(useDevices.getState().conversations[PEER]!.phase).toBe("error");
  });

  it("a stream that ends in an error reads as a turn that stopped", async () => {
    setDevicesDeps({
      client: client({
        sendMessage: async () => ({ request_id: JOB }),
        turn: () => frames([{ kind: "turn.error", reason: "engine_unavailable", detail: "No key" }, closed("error")]),
      }),
      now: () => 0,
    });
    await useDevices.getState().load();
    await useDevices.getState().send(PEER, "hi");
    const box = useDevices.getState().conversations[PEER]!;
    expect(box.phase).toBe("done");
    expect(box.lines.at(-1)).toEqual({ kind: "problem", text: "It stopped: No key" });
  });
});

describe("the turn relay over fetch", () => {
  beforeEach(() => {
    resetConnection();
    sessionStorage.setItem("athena.connection", JSON.stringify({ url: "http://127.0.0.1:5555", token: "tok" }));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  const sse = (chunks: string[], status = 200) => {
    const encoder = new TextEncoder();
    return new Response(
      new ReadableStream({
        start(controller) {
          for (const c of chunks) controller.enqueue(encoder.encode(c));
          controller.close();
        },
      }),
      { status, headers: { "content-type": "text/event-stream" } },
    );
  };

  async function drain(it: AsyncGenerator<TurnFrame>): Promise<TurnFrame[]> {
    const got: TurnFrame[] = [];
    for await (const frame of it) got.push(frame);
    return got;
  }

  it("sends the token in a header, splits frames across chunks and skips what it cannot draw", async () => {
    const fetchMock = vi.fn(async () =>
      sse([
        ": athena turn\nretry: 1000\n\n",
        'id: 0\nevent: text.delta\ndata: {"kind":"text.delta","te',
        'xt":"hi"}\n\nid: 1\nevent: other\ndata: {"kind":"future.thing"}\n\n',
        `event: remote.closed\ndata: {"kind":"remote.closed","request_id":"${JOB}","reason":"finished","showing":2,"total":2,"footer":""}\n\n`,
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    const got = await drain(peerTurn(PEER, JOB, 3));
    expect(got.map((f) => f.kind)).toEqual(["text.delta", "remote.closed"]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`http://127.0.0.1:5555/devices/${PEER}/turns/${JOB}?from=3`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("turns a refusal into the daemon's words and a dead daemon into unreachable", async () => {
    const body = JSON.stringify({ ok: false, error: "peer_unreachable", reason: "that device did not answer" });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status: 502 })));
    const refused = await drain(peerTurn(PEER, JOB, 0)).catch((e: unknown) => e);
    expect(refused).toBeInstanceOf(DaemonError);
    expect((refused as DaemonError).status).toBe(502);
    expect((refused as DaemonError).error).toBe("peer_unreachable");

    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))));
    const down = await drain(peerTurn(PEER, JOB, 0)).catch((e: unknown) => e);
    expect((down as DaemonError).status).toBe(0);
  });
});
