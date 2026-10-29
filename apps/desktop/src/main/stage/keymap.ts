// The stage's one keymap, scoped to the stage while it is mounted. 1-4 pick a suggestion; Escape
// closes a card; `i` inks the focused piece and Delete rubs it out; Y, N and the arrows mark in the
// check step, in both views. Keys are ignored while typing in a field, except that Enter which ends
// an input method's composition never sends.

import { useEffect, useRef } from "react";
import type { DraftStep, Mark } from "../../lib/contract";

export type StageKey =
  | { type: "pick"; index: number }
  | { type: "close" }
  | { type: "ink" }
  | { type: "drop" }
  | { type: "mark"; mark: Mark }
  | { type: "move"; by: 1 | -1 };

export interface KeyContext {
  step: DraftStep;
  /** A question with suggestions is open and nothing is in flight. */
  asking: boolean;
  /** How many suggestions there are (keys past it do nothing). */
  suggestions: number;
}

/** The part of a KeyboardEvent the map reads. */
export interface KeyLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  isComposing?: boolean;
  keyCode?: number;
  target: EventTarget | null;
}

/** Whether the key lands in a place the person types: a field, a text area, a select or editable text. */
export function typingIn(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** What a key means on the stage now, or null. Pure. */
export function keyFor(e: KeyLike, ctx: KeyContext): StageKey | null {
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  if (e.key === "Escape") return { type: "close" };
  if (typingIn(e.target)) return null;
  if (ctx.step === "shape") {
    if (/^[1-4]$/.test(e.key) && ctx.asking && Number(e.key) <= ctx.suggestions) return { type: "pick", index: Number(e.key) - 1 };
    if (e.key === "i" || e.key === "I") return { type: "ink" };
    if (e.key === "Delete") return { type: "drop" };
  }
  if (ctx.step === "preview") {
    if (e.key === "y" || e.key === "Y") return { type: "mark", mark: "yes" };
    if (e.key === "n" || e.key === "N") return { type: "mark", mark: "no" };
    if (e.key === "ArrowDown" || e.key === "ArrowRight") return { type: "move", by: 1 };
    if (e.key === "ArrowUp" || e.key === "ArrowLeft") return { type: "move", by: -1 };
  }
  return null;
}

/** Enter while an input method is composing picks the word; it must never send or submit. */
export const composingEnter = (e: KeyLike): boolean => e.key === "Enter" && (!!e.isComposing || e.keyCode === 229);

/** One window listener while the stage is mounted; `onKey` and `ctx` are read fresh on each key. */
export function useStageKeys(ctx: KeyContext, onKey: (key: StageKey, e: KeyboardEvent) => void): void {
  const latest = useRef({ ctx, onKey });
  latest.current = { ctx, onKey };
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (composingEnter(e)) {
        e.preventDefault();
        return;
      }
      const key = keyFor(e, latest.current.ctx);
      if (!key) return;
      e.preventDefault();
      latest.current.onKey(key, e);
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);
}
