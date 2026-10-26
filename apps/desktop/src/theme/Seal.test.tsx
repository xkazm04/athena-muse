import { act, cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Seal, SETTLE_MS, type SealState } from "./Seal";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("Seal states", () => {
  const states: SealState[] = ["rest", "working", "waiting", "signed"];

  it.each(states)("renders %s with its class and data-state", (state) => {
    const { container } = render(<Seal state={state} label="Athena" />);
    const root = container.firstElementChild!;
    expect(root.classList.contains("seal")).toBe(true);
    expect(root.classList.contains(`seal--${state}`)).toBe(true);
    expect(root.getAttribute("data-state")).toBe(state);
    expect(root.getAttribute("aria-label")).toBe("Athena");
  });

  it("draws the full geometry: four tentacles, dome, orb, mark, check, sign ring", () => {
    const { container } = render(<Seal state="rest" label="Athena" />);
    expect(container.querySelectorAll(".seal__tentacle")).toHaveLength(4);
    for (const part of [".seal__dome", ".seal__gleam", ".seal__orb", ".seal__mark", ".seal__check", ".seal__sign"]) {
      expect(container.querySelector(part), part).not.toBeNull();
    }
    expect(container.querySelector("svg")!.getAttribute("viewBox")).toBe("0 0 76 76");
  });

  it("uses a different gradient id per instance", () => {
    const { container } = render(
      <>
        <Seal state="rest" label="a" />
        <Seal state="rest" label="b" />
      </>,
    );
    const ids = [...container.querySelectorAll("radialGradient")].map((g) => g.id);
    expect(new Set(ids).size).toBe(4);
  });

  it("shows the waiting count, capped at 99+, and nothing at zero", () => {
    const { container, rerender } = render(<Seal state="waiting" count={3} label="Athena" />);
    expect(container.querySelector(".seal__count")!.textContent).toBe("3");
    rerender(<Seal state="waiting" count={120} label="Athena" />);
    expect(container.querySelector(".seal__count")!.textContent).toBe("99+");
    rerender(<Seal state="waiting" count={0} label="Athena" />);
    expect(container.querySelector(".seal__count")).toBeNull();
  });

  it("is a button only when it has a click handler", () => {
    const onClick = vi.fn();
    const { container, rerender } = render(<Seal state="rest" label="Athena" onClick={onClick} />);
    const btn = container.querySelector("button")!;
    btn.click();
    expect(onClick).toHaveBeenCalledOnce();
    rerender(<Seal state="rest" label="Athena" />);
    expect(container.querySelector("button")).toBeNull();
    expect(container.firstElementChild!.getAttribute("role")).toBe("img");
  });

  it("settles from signed back to rest and says so once", () => {
    vi.useFakeTimers();
    const onSettled = vi.fn();
    const { container } = render(<Seal state="signed" label="Athena" onSettled={onSettled} />);
    const root = () => container.firstElementChild!;
    expect(root().classList.contains("seal--signed")).toBe(true);
    act(() => {
      vi.advanceTimersByTime(SETTLE_MS - 10);
    });
    expect(root().classList.contains("seal--signed")).toBe(true);
    expect(onSettled).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(20);
    });
    expect(root().classList.contains("seal--rest")).toBe(true);
    expect(onSettled).toHaveBeenCalledOnce();
  });
});
