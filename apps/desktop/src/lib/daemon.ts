// The one way a window talks to the daemon: connection, JSON requests, the turn stream, the event
// stream. Typed by the wire contract (contract.ts); no route knowledge lives here (that is api.ts).

import type { AppEvent, ErrorBody, ErrorWord, TurnEvent } from "./contract";
import { isTauri } from "./windows";

export interface Connection {
  url: string;
  token: string;
}

/** A daemon refusal or a daemon that cannot be reached. `status` 0 means no answer at all. */
export class DaemonError extends Error {
  readonly status: number;
  readonly error: ErrorWord;
  readonly reason: string;

  constructor(status: number, error: ErrorWord, reason: string) {
    super(reason);
    this.name = "DaemonError";
    this.status = status;
    this.error = error;
    this.reason = reason;
  }
}

export const UNREACHABLE = "Athena's background service is not reachable";

const STORE_KEY = "athena.connection";
let pending: Promise<Connection> | null = null;

function fromLocation(): Connection | null {
  try {
    const q = new URLSearchParams(window.location.search);
    const url = q.get("daemon");
    const token = q.get("token");
    if (url && token) {
      const found = { url: url.replace(/\/+$/, ""), token };
      // Kept so in-app navigation (which drops the query) keeps the connection.
      sessionStorage.setItem(STORE_KEY, JSON.stringify(found));
      return found;
    }
    const kept = sessionStorage.getItem(STORE_KEY);
    return kept ? (JSON.parse(kept) as Connection) : null;
  } catch {
    return null;
  }
}

/** Inside Tauri the shell hands over `{url, token}`; in a browser it comes from `?daemon=&token=`. */
export function getConnection(): Promise<Connection> {
  if (!pending) {
    pending = resolveConnection().catch((e: unknown) => {
      pending = null; // let the next call try again (the daemon may have been slow)
      throw e;
    });
  }
  return pending;
}

async function resolveConnection(): Promise<Connection> {
  if (isTauri()) {
    const { invoke } = await import("@tauri-apps/api/core");
    try {
      return await invoke<Connection>("daemon_info");
    } catch (e) {
      throw new DaemonError(0, "engine_unavailable", typeof e === "string" ? e : UNREACHABLE);
    }
  }
  const found = fromLocation();
  if (!found) throw new DaemonError(0, "bad_request", UNREACHABLE);
  return found;
}

/** Tests and the preview page use this to forget a cached connection. */
export function resetConnection(): void {
  pending = null;
}

async function toError(res: Response): Promise<DaemonError> {
  try {
    const body = (await res.json()) as Partial<ErrorBody>;
    if (body && typeof body.error === "string") {
      return new DaemonError(res.status, body.error, body.reason ?? res.statusText);
    }
  } catch {
    // not a contract body; fall through
  }
  return new DaemonError(res.status, "bad_request", res.statusText || `Request failed (${res.status})`);
}

async function send(method: string, path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  const conn = await getConnection();
  const headers: Record<string, string> = { Authorization: `Bearer ${conn.token}` };
  const init: RequestInit = { method, headers, signal };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(conn.url + path, init);
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new DaemonError(0, "bad_request", UNREACHABLE);
  }
  if (!res.ok) throw await toError(res);
  return res;
}

/** JSON in, JSON out. An empty body (204) comes back as `undefined`. */
export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await send(method, path, body);
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/**
 * Splits a byte stream into NDJSON events. Chunk boundaries fall anywhere, so the unfinished tail
 * of one chunk is held until the next one completes the line.
 */
export function createNdjsonParser<E = TurnEvent>(onEvent: (e: E) => void): {
  push: (chunk: string) => void;
  flush: () => void;
} {
  let tail = "";
  const emit = (line: string) => {
    const text = line.trim();
    if (!text) return;
    try {
      onEvent(JSON.parse(text) as E);
    } catch {
      // A garbled line is dropped; the stream's own done or error event still ends the turn.
    }
  };
  return {
    push(chunk) {
      tail += chunk;
      let nl = tail.indexOf("\n");
      while (nl >= 0) {
        emit(tail.slice(0, nl));
        tail = tail.slice(nl + 1);
        nl = tail.indexOf("\n");
      }
    },
    flush() {
      emit(tail);
      tail = "";
    },
  };
}

/**
 * Any NDJSON route: send the request and hand each event to `onEvent` as it arrives. Resolves when
 * the stream ends; a refusal before the stream starts throws a DaemonError like `request` does.
 */
export async function streamNdjson<E>(
  method: string,
  path: string,
  body: unknown,
  onEvent: (e: E) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await send(method, path, body, signal);
  if (!res.body) throw new DaemonError(0, "bad_request", UNREACHABLE);
  const parser = createNdjsonParser<E>(onEvent);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
    parser.push(decoder.decode());
    parser.flush();
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new DaemonError(0, "bad_request", UNREACHABLE);
  }
}

/** POST /run and hand each turn event to `onEvent` as it arrives. Resolves when the stream ends. */
export function streamRun(body: unknown, onEvent: (e: TurnEvent) => void, signal?: AbortSignal): Promise<void> {
  return streamNdjson<TurnEvent>("POST", "/run", body, onEvent, signal);
}

export const RECONNECT_MIN_MS = 1000;
export const RECONNECT_MAX_MS = 10000;

/** Next wait after a failed connect: doubles from 1 s up to 10 s. */
export function nextBackoff(ms: number): number {
  return Math.min(RECONNECT_MAX_MS, ms * 2);
}

/** Listen to /events. Reconnects with backoff; returns the function that stops it. */
export function subscribe(onEvent: (e: AppEvent) => void): () => void {
  let stopped = false;
  let source: EventSource | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let wait = RECONNECT_MIN_MS;

  const retry = () => {
    if (stopped) return;
    timer = setTimeout(connect, wait);
    wait = nextBackoff(wait);
  };

  const connect = () => {
    timer = null;
    getConnection().then(
      (conn) => {
        if (stopped) return;
        const es = new EventSource(`${conn.url}/events?token=${encodeURIComponent(conn.token)}`);
        source = es;
        es.onopen = () => {
          wait = RECONNECT_MIN_MS;
        };
        es.onmessage = (m: MessageEvent<string>) => {
          try {
            onEvent(JSON.parse(m.data) as AppEvent);
          } catch {
            // ignore a frame that is not an event
          }
        };
        es.onerror = () => {
          // EventSource retries on its own but never backs off; take over so the wait is ours.
          es.close();
          if (source === es) source = null;
          retry();
        };
      },
      () => retry(),
    );
  };

  connect();
  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    source?.close();
    source = null;
  };
}
