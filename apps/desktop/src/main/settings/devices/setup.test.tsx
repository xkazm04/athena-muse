import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DevicesLevel } from "./Devices";
import { model } from "./fixtures";
import { SetupSection } from "./SetupSection";

afterEach(cleanup);

describe("Set up with Athena", () => {
  it("is the bottom of the Devices level, whatever is paired", () => {
    expect(renderToStaticMarkup(<DevicesLevel model={model()} />)).toContain("Set up with Athena");
    expect(renderToStaticMarkup(<DevicesLevel model={model({}, null)} />)).not.toContain("Set up with Athena");
  });

  it("says it changes nothing until a card is signed", () => {
    render(<SetupSection begin={vi.fn()} />);
    expect(screen.getByText(/Nothing on this computer changes until you sign/)).toBeTruthy();
  });

  it("opens the conversation on a press, and is busy while it does", async () => {
    let done: () => void = () => undefined;
    const begin = vi.fn(() => new Promise<void>((resolve) => (done = resolve)));
    render(<SetupSection begin={begin} />);
    fireEvent.click(screen.getByRole("button", { name: "Set up with Athena" }));
    expect(begin).toHaveBeenCalledTimes(1);
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
    await act(async () => done());
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows the reason it could not open, in the daemon's words", async () => {
    render(<SetupSection begin={async () => Promise.reject(new Error("devices are switched off on this computer"))} />);
    fireEvent.click(screen.getByRole("button", { name: "Set up with Athena" }));
    expect((await screen.findByRole("alert")).textContent).toBe("devices are switched off on this computer");
  });
});
