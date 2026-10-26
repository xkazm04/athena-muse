import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Card, SpaceSummary } from "../lib/contract";
import { CardView } from "./CardView";
import { ProjectPill } from "./ProjectPill";

afterEach(cleanup);

const card: Card = {
  id: "card_1",
  space_id: "spc_1",
  action: "propose_brief",
  label: "Change this project's brief to: file by April",
  args: { brief: "file by April" },
  state: "waiting",
  created: "2026-10-26T12:00:00Z",
};

const space = (id: string, name: string): SpaceSummary => ({
  id, name, brief: "", apps: [], hue: 210, created: "", updated: "", counts: { episodes: 0, facts: 0 },
});

describe("CardView", () => {
  it("signs once and reports the resolved card", async () => {
    const decided = { ...card, state: "approved" as const };
    const onDecide = vi.fn().mockResolvedValue(decided);
    const onResolved = vi.fn();
    render(<CardView card={card} onDecide={onDecide} onResolved={onResolved} />);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Sign" })));
    expect(onDecide).toHaveBeenCalledWith("approve");
    expect(onResolved).toHaveBeenCalledWith(decided);
  });

  it("shows a resolved card without buttons", () => {
    render(<CardView card={{ ...card, state: "approved" }} onDecide={vi.fn()} />);
    expect(screen.getByText("Signed, ran once")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("ProjectPill", () => {
  it("names the active project and switches through the menu", () => {
    const onSelect = vi.fn();
    render(<ProjectPill spaces={[space("spc_1", "Taxes"), space("spc_2", "Garden")]} activeId="spc_1" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Taxes/ }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: /Garden/ }));
    expect(onSelect).toHaveBeenCalledWith("spc_2");
  });

  it("reads Core when no project is active and says when a switch waits", () => {
    render(<ProjectPill spaces={[space("spc_1", "Taxes")]} activeId="" pendingId="spc_1" onSelect={vi.fn()} />);
    expect(screen.getByText("Core")).toBeTruthy();
    expect(screen.getByText("switches after this reply")).toBeTruthy();
  });
});
