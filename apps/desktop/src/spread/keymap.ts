// The book's one keymap (ADR 0024): the arrows and Page Up/Down turn a page, Home opens the first
// page and End the page being written. Read while the book is mounted; a key typed into a field, or
// held with a modifier, is the field's or the system's.

import { typingIn, type KeyLike } from "../ui/keys";

export type BookCommand = "next" | "prev" | "first" | "now";

/** Every binding of the book, in one place. */
export const BOOK_KEYS: Readonly<Record<string, BookCommand>> = {
  ArrowRight: "next",
  PageDown: "next",
  ArrowLeft: "prev",
  PageUp: "prev",
  Home: "first",
  End: "now",
};

/** What a key means to the book, or null. Pure. */
export function bookCommand(e: KeyLike): BookCommand | null {
  if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return null;
  if (typingIn(e.target)) return null;
  return BOOK_KEYS[e.key] ?? null;
}

/** The page a command turns to, from `at` in a book of `count` pages whose page being written is `now`. */
export function turnTo(cmd: BookCommand, at: number, count: number, now: number): number {
  const to = cmd === "next" ? at + 1 : cmd === "prev" ? at - 1 : cmd === "first" ? 0 : now;
  return Math.max(0, Math.min(count - 1, to));
}
