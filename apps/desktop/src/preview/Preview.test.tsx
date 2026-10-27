import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Preview } from "./Preview";

vi.mock("../theme/Backdrop", () => ({ Backdrop: () => null }));

afterEach(cleanup);

describe("preview", () => {
  it("renders the chores section on fixture data, labelled as such, in each state", () => {
    render(<Preview />);
    const section = screen.getByRole("heading", { name: /Chores \(fixture data/ }).closest("section")!;
    const scene = within(section);
    expect(scene.getByText("Proven on Meta")).toBeTruthy();
    expect(scene.getByRole("heading", { name: "Proofs" })).toBeTruthy();
    fireEvent.click(scene.getByRole("button", { name: /Remodel changes/ }));
    expect(scene.getByText("python -m athena.bench renovation-witness")).toBeTruthy();
    fireEvent.click(scene.getByRole("button", { name: "empty" }));
    expect(scene.getByText("No chores yet.")).toBeTruthy();
    fireEvent.click(scene.getByRole("button", { name: "problem" }));
    expect(scene.getByRole("alert")).toBeTruthy();
    fireEvent.click(scene.getByRole("button", { name: "Try again" }));
    expect(scene.queryByRole("alert")).toBeNull();
  });
});
