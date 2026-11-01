// The setup conversation's wire (ADR 0017, portable ADR 0140 WP4): what "Set up with Athena" on the
// Devices page calls. `POST /devices/setup` opens the conversation on this device's daemon; her window
// then runs its turns on `POST /devices/setup/run` (`{start: true}` makes her speak first, `{text}` is
// the person's line) and reads it back from `GET /devices/setup/conversation`. It is a conversation of
// its own, not a project's: no page or browser context, and its tools exist nowhere else. Nothing
// here decides what is gated; the daemon files a card for every step that changes this computer.

import { DaemonError, request, streamNdjson } from "./daemon";
import type { Turn, TurnEvent } from "./contract";
import { startSetupInAthena } from "./windows";

/** The conversation's own space id, as `athena.peer.setup.SETUP_SPACE` spells it. */
export const SETUP_SPACE = "setup";

/** What the daemon answered: the conversation, and what this device is waiting for (`null` before any). */
export interface SetupOpened {
  ok: boolean;
  space_id: string;
  phase: string | null;
  opened_at: string | null;
}

/** The person chose "Set up with Athena": open the conversation on this device's daemon. */
export async function openSetup(): Promise<SetupOpened> {
  const opened = await request<SetupOpened>("POST", "/devices/setup");
  if (opened?.space_id !== SETUP_SPACE) throw new Error("The daemon answered something that is not the setup conversation.");
  return opened;
}

/** The setup conversation so far, oldest first. */
export async function setupConversation(): Promise<Turn[]> {
  return (await request<{ turns: Turn[] }>("GET", "/devices/setup/conversation")).turns;
}

/** One setup turn, streamed as `/run` is: `start` with no text makes her speak first. */
export function streamSetup(
  body: { text?: string; start?: boolean },
  onEvent: (e: TurnEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamNdjson<TurnEvent>("POST", "/devices/setup/run", body, onEvent, signal);
}

export interface BeginSetupDeps {
  open?: () => Promise<SetupOpened>;
  /** Show her window and have it send the opening turn; `false` when there is no window to show. */
  hand?: () => Promise<boolean>;
}

/**
 * "Set up with Athena", end to end: open the conversation, then hand it to her window, where she
 * speaks first. Rejects with a sentence a person can read.
 */
export async function beginSetup({ open = openSetup, hand = startSetupInAthena }: BeginSetupDeps = {}): Promise<SetupOpened> {
  let opened: SetupOpened;
  try {
    opened = await open();
  } catch (e) {
    throw new Error(e instanceof DaemonError ? e.reason : "Athena could not open the setup conversation.");
  }
  if (!(await hand())) throw new Error("Her window opens in the Athena app; this page is not running in it.");
  return opened;
}
