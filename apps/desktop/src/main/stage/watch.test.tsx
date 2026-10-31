// The access step keeps checking while the person signs in (owner, 2026-10-31).
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Draft, DraftSite } from "../../lib/contract";
import { STAGED } from "./fixture/staged";
import { useAccessWatch, WATCH_MS, WATCH_TRIES } from "./hooks";

const origin = "https://parents.brightside.example";
const at = (site: Partial<DraftSite>): Draft =>
  ({ ...STAGED.saved, step: "access", sites: [{ origin, label: "Parents", probe_url: `${origin}/`, state: "open", ...site }] }) as Draft;

describe("useAccessWatch", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("looks again every few seconds while the person signs in, until the site is signed in", () => {
    const dispatch = vi.fn();
    const { rerender } = renderHook(({ d, busy }) => useAccessWatch(d, busy, dispatch), { initialProps: { d: at({ tab: 3 }), busy: false } });
    vi.advanceTimersByTime(WATCH_MS);
    expect(dispatch).toHaveBeenCalledWith({ type: "access", origin, act: "check" });
    rerender({ d: at({ tab: 3 }), busy: true }); // one look at a time
    vi.advanceTimersByTime(WATCH_MS * 3);
    expect(dispatch).toHaveBeenCalledTimes(1);
    rerender({ d: at({ tab: 3, reason: "still on the sign-in page" }), busy: false });
    vi.advanceTimersByTime(WATCH_MS);
    expect(dispatch).toHaveBeenCalledTimes(2);
    rerender({ d: at({ state: "signed_in" }), busy: false });
    vi.advanceTimersByTime(WATCH_MS * 5);
    expect(dispatch).toHaveBeenCalledTimes(2);
  });

  it("does not look before the site is opened, nor while a move waits for the person", () => {
    const dispatch = vi.fn();
    const { rerender } = renderHook(({ d }) => useAccessWatch(d, false, dispatch), { initialProps: { d: at({}) } });
    vi.advanceTimersByTime(WATCH_MS * 3);
    rerender({ d: at({ tab: 3, moved_to: "https://studio.brightside.example/" }) });
    vi.advanceTimersByTime(WATCH_MS * 3);
    expect(dispatch).not.toHaveBeenCalled();
  });

  it("stops after a bounded number of looks and leaves 'I have signed in' to the person", () => {
    const dispatch = vi.fn();
    const { rerender } = renderHook(({ d }) => useAccessWatch(d, false, dispatch), { initialProps: { d: at({ tab: 3 }) } });
    for (let i = 0; i < WATCH_TRIES + 5; i++) {
      vi.advanceTimersByTime(WATCH_MS);
      rerender({ d: at({ tab: 3, reason: `look ${i}` }) });
    }
    expect(dispatch).toHaveBeenCalledTimes(WATCH_TRIES);
  });
});
