// Talking to another computer through this one (ADR 0017): a message to send, and that computer's
// turn read back as it streams. The stream is `fetch`, not `EventSource`, because the daemon wants the
// token in a header and an `EventSource` cannot send one.

import { DaemonError, getConnection, UNREACHABLE } from "./daemon";
import type { ErrorWord } from "./contract";
import { turnFrameFromJson, type TurnFrame } from "./fleet";

/** The data of each SSE frame off a fetch body; comments and frames without data are skipped. */
export async function* sseData(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let cut = buffer.indexOf("\n\n");
      while (cut >= 0) {
        const frame = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).replace(/^ /, ""));
        if (data.length) yield data.join("\n");
        cut = buffer.indexOf("\n\n");
      }
    }
  } finally {
    reader.releaseLock();
  }
}

async function refusal(res: Response): Promise<DaemonError> {
  try {
    const body = (await res.json()) as { error?: unknown; reason?: unknown };
    if (typeof body.error === "string") {
      return new DaemonError(res.status, body.error as ErrorWord, typeof body.reason === "string" ? body.reason : res.statusText);
    }
  } catch {
    // not an error body; fall through
  }
  return new DaemonError(res.status, "bad_request", res.statusText || `Request failed (${res.status})`);
}

/**
 * Another computer's turn, relayed from `from` on: its events, then `remote.closed`. A stream also ends
 * quietly after a while with nothing new; the caller comes back with `from` set to how many events it
 * has. A frame of a kind this window does not draw is skipped.
 */
export async function* peerTurn(
  peerId: string,
  requestId: string,
  from: number,
  signal?: AbortSignal,
): AsyncGenerator<TurnFrame> {
  const conn = await getConnection();
  const path = `/devices/${encodeURIComponent(peerId)}/turns/${encodeURIComponent(requestId)}?from=${from}`;
  let res: Response;
  try {
    res = await fetch(conn.url + path, {
      headers: { Authorization: `Bearer ${conn.token}`, Accept: "text/event-stream" },
      signal,
    });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new DaemonError(0, "bad_request", UNREACHABLE);
  }
  if (!res.ok) throw await refusal(res);
  if (!res.body) return;
  try {
    for await (const data of sseData(res.body)) {
      const frame = turnFrameFromJson(data);
      if (frame) yield frame;
    }
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new DaemonError(0, "bad_request", UNREACHABLE);
  }
}
