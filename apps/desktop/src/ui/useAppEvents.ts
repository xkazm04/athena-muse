import { useEffect, useRef } from "react";
import type { AppEvent } from "../lib/contract";
import { subscribe } from "../lib/daemon";

/** Live daemon events for as long as the component is mounted. The latest handler is always called,
 *  so callers may pass an inline function without resubscribing. */
export function useAppEvents(onEvent: (e: AppEvent) => void, enabled = true): void {
  const handler = useRef(onEvent);
  handler.current = onEvent;
  useEffect(() => {
    if (!enabled) return;
    return subscribe((e) => handler.current(e));
  }, [enabled]);
}
