// A message to another computer, and its turn read back (ADR 0017). The daemon on the other side runs
// the message as a turn (`src/athena/peer/remote.py`) and this window reads it through its own daemon's
// relay. Pure helpers and the one procedure `converse`; the store holds the state and calls it.

import type { TurnFrame } from "../../../lib/fleet";

/** How many times a relayed turn is read again after a quiet end before the box gives up. */
export const RELAY_ATTEMPTS = 40;
/** How many lines one conversation box keeps; older ones are dropped and counted. */
export const CONVERSATION_CAP = 200;

/** One line of a conversation with another computer's Athena. */
export interface ConversationLine {
  kind: "you" | "athena" | "tool" | "card" | "problem";
  text: string;
}

export interface Conversation {
  requestId: string | null;
  phase: "sending" | "waiting" | "done" | "error";
  lines: ConversationLine[];
  /** How many lines were dropped past {@link CONVERSATION_CAP}. */
  dropped: number;
  /** The plain sentence of a refusal or a failure; `null` while all is well. */
  problem: string | null;
}

export const IDLE: Conversation = { requestId: null, phase: "done", lines: [], dropped: 0, problem: null };

/**
 * Append lines, keeping the newest {@link CONVERSATION_CAP}. Her words arrive a few at a time, so a line
 * of hers that follows one of hers continues it rather than starting a new one.
 */
export function appendLines(conversation: Conversation, lines: readonly ConversationLine[]): Conversation {
  const all = [...conversation.lines];
  for (const line of lines) {
    const last = all[all.length - 1];
    if (line.kind === "athena" && last?.kind === "athena") all[all.length - 1] = { kind: "athena", text: last.text + line.text };
    else all.push(line);
  }
  const over = Math.max(0, all.length - CONVERSATION_CAP);
  return { ...conversation, lines: over ? all.slice(over) : all, dropped: conversation.dropped + over };
}

/** What one relayed frame adds to the box: her words, a tool's line, a card waiting over there. */
export function linesOf(frame: TurnFrame, deviceName: string): ConversationLine[] {
  switch (frame.kind) {
    case "text.delta":
      return frame.text ? [{ kind: "athena", text: frame.text }] : [];
    case "tool.result":
      return [{ kind: "tool", text: frame.label || frame.name }];
    case "decision.requested":
      return [{ kind: "card", text: `Waiting for your approval on ${deviceName}: ${frame.label || frame.action}` }];
    case "turn.error":
      return [{ kind: "problem", text: `It stopped: ${frame.detail || frame.reason}` }];
    case "remote.closed":
      return frame.footer ? [{ kind: "tool", text: frame.footer }] : [];
    default:
      return [];
  }
}

/** What `converse` asks of the daemon. */
export interface TalkClient {
  sendMessage: (peerId: string, text: string) => Promise<{ request_id: string }>;
  turn: (peerId: string, requestId: string, from: number, signal?: AbortSignal) => AsyncIterable<TurnFrame>;
}

/** The ends a conversation can come to, for the store to put in the box. */
export interface Talking {
  change: (change: (c: Conversation) => Conversation) => void;
  sentence: (error: unknown) => string;
}

/**
 * Send `words` to `peerId` and read its turn to the end, coming back with `from` set to the events
 * already seen each time a quiet stream ends open. The box is changed through `talking.change`.
 */
export async function converse(
  client: TalkClient,
  peerId: string,
  name: string,
  words: string,
  talking: Talking,
): Promise<void> {
  const { change } = talking;
  change((c) => appendLines({ ...c, phase: "sending", problem: null, requestId: null }, [{ kind: "you", text: words }]));
  let requestId: string;
  try {
    requestId = (await client.sendMessage(peerId, words)).request_id;
  } catch (error) {
    change((c) => ({ ...c, phase: "error", problem: talking.sentence(error) }));
    return;
  }
  change((c) => ({ ...c, phase: "waiting", requestId }));
  let from = 0;
  for (let attempt = 0; attempt < RELAY_ATTEMPTS; attempt += 1) {
    let closed = false;
    try {
      for await (const frame of client.turn(peerId, requestId, from)) {
        if (frame.kind === "remote.closed") closed = true;
        else from += 1;
        const lines = linesOf(frame, name);
        if (lines.length) change((c) => appendLines(c, lines));
        if (closed) break;
      }
    } catch (error) {
      change((c) => ({ ...c, phase: "error", problem: talking.sentence(error) }));
      return;
    }
    if (closed) {
      change((c) => ({ ...c, phase: "done" }));
      return;
    }
  }
  change((c) => ({ ...c, phase: "error", problem: `${name} has not finished; it is still working there.` }));
}
