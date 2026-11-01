import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Conversation } from "./conversation";
import { VIEW, model } from "./fixtures";
import { MessageBox } from "./MessageBox";
import type { DevicesModel } from "./parts";

const laptop = VIEW.peers[0]!;

const talking = (conversation?: Conversation, send = vi.fn(async () => {})): DevicesModel => {
  const base = model();
  return {
    ...base,
    state: { ...base.state, conversations: conversation ? { [laptop.peer_id]: conversation } : {} },
    actions: { ...base.actions, send },
  };
};

afterEach(cleanup);

describe("the message box in a computer's drawer", () => {
  it("sends what was typed on Enter and clears the box", () => {
    const send = vi.fn(async () => {});
    render(<MessageBox model={talking(undefined, send)} peer={laptop} />);
    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(screen.getByRole("button", { name: "Send" })).toHaveProperty("disabled", true);
    fireEvent.change(input, { target: { value: "what is due?" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(send).toHaveBeenCalledWith(laptop.peer_id, "what is due?");
    expect(input.value).toBe("");
  });

  it("shows the log, says it is working while it waits, and holds a second send", () => {
    const send = vi.fn(async () => {});
    const conversation: Conversation = {
      requestId: "job_0000000000d1",
      phase: "waiting",
      lines: [
        { kind: "you", text: "hi" },
        { kind: "athena", text: "Hello." },
      ],
      dropped: 3,
      problem: null,
    };
    render(<MessageBox model={talking(conversation, send)} peer={laptop} />);
    expect(screen.getByText("You: hi")).toBeTruthy();
    expect(screen.getByText("Hello.")).toBeTruthy();
    expect(screen.getByText("(showing 2 of 5)")).toBeTruthy();
    expect(screen.getByText(`${laptop.name} is working...`)).toBeTruthy();
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "again" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(send).not.toHaveBeenCalled();
  });

  it("says a refusal under the log", () => {
    const conversation: Conversation = { requestId: null, phase: "error", lines: [], dropped: 0, problem: "Athena is busy" };
    render(<MessageBox model={talking(conversation)} peer={laptop} />);
    expect(screen.getByRole("alert").textContent).toBe("Athena is busy");
  });

  it("draws nothing in a model with no way to send", () => {
    const { container } = render(<MessageBox model={model()} peer={laptop} />);
    expect(container.innerHTML).toBe("");
  });
});
