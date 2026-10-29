// "She still needs" and the "enough" exit work on any rubric's coverage (ADR 0010): a twin's places
// here, the chore's by default, with the same DOM hooks.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Coverage, Place, PlaceCoverage } from "../../../lib/contract";
import type { Rubric } from "../select";
import { STAGE_WORDS } from "../words";
import { EnoughButton, StillNeeds } from "./Ask";

afterEach(cleanup);

/** A stand-in for the twin rubric (ADR 0010's requirements); the real one is the daemon's. */
const TWIN: Rubric<Place> = {
  places: ["who", "channels", "voice", "knowledge", "chores", "never", "autonomy", "memory", "mission"],
  required: { who: 1, channels: 1, voice: 1, knowledge: 0.5, chores: 0.5, never: 1, autonomy: 1, memory: 0, mission: 0 },
};
const TITLE: Record<Place, string> = {
  who: "Who it is",
  channels: "Where it speaks",
  voice: "How it sounds",
  knowledge: "What it knows",
  chores: "What it does",
  never: "What it must never do",
  autonomy: "How much it does alone",
  memory: "What it remembers",
  mission: "Its first mission",
};
const PHRASE: Record<Place, string> = {
  who: "who it is",
  channels: "where it speaks",
  voice: "how it sounds",
  knowledge: "what it knows",
  chores: "what it does",
  never: "what it must never do",
  autonomy: "how much it does alone",
  memory: "what it remembers",
  mission: "its first mission",
};
const WORDS = {
  stillNeeds: "She still needs",
  ready: "Ready to rehearse.",
  needPhrase: PHRASE,
  enough: "That's enough, rehearse it",
  leftOpen: "Rehearse now and she leaves open",
  slot: TITLE,
};
const COVERED: PlaceCoverage = {
  who: 1,
  channels: 1,
  voice: 0.5,
  knowledge: "skipped",
  chores: 0,
  never: 1,
  autonomy: 1,
  memory: 0,
  mission: 0,
};

describe("the coverage parts on a twin's places", () => {
  it("names what she still needs by the twin's requirements, in its order", () => {
    render(<StillNeeds coverage={COVERED} rubric={TWIN} words={WORDS} />);
    const still = screen.getByText(/She still needs/).closest("[data-role='still-needs']")!;
    expect(still.textContent).toBe("She still needs: how it sounds and what it does");
    expect(still.getAttribute("data-ready")).toBeNull();
  });

  it("reads ready once every place meets what it requires; places that need nothing stay empty", () => {
    const done: PlaceCoverage = { ...COVERED, voice: 1, chores: 0.5 };
    const { container } = render(<StillNeeds coverage={done} rubric={TWIN} words={WORDS} />);
    const still = container.querySelector("[data-role='still-needs']")!;
    expect(still.textContent).toBe("Ready to rehearse.");
    expect(still.getAttribute("data-ready")).toBe("true");
  });

  it("names the places the exit leaves open, and calls back", () => {
    const onEnough = vi.fn();
    const { container } = render(
      <EnoughButton coverage={COVERED} rubric={TWIN} agreed={false} onEnough={onEnough} words={WORDS} />,
    );
    const exit = container.querySelector("[data-role='exit']")!;
    expect(exit.textContent).toBe("That's enough, rehearse it");
    expect(exit.getAttribute("data-ready")).toBeNull();
    expect(container.querySelector(".sp-enough__open")!.textContent).toBe(
      "Rehearse now and she leaves open: how it sounds, what it does, what it remembers and its first mission",
    );
    fireEvent.click(exit);
    expect(onEnough).toHaveBeenCalledOnce();
  });

  it("needs the rubric for any places but the chore's (a type check)", () => {
    // @ts-expect-error a twin's coverage has no default rubric
    const element = <StillNeeds coverage={COVERED} words={WORDS} />;
    expect(element).toBeTruthy();
  });
});

describe("the coverage parts on the chore's slots", () => {
  it("default to the chore's rubric, as before", () => {
    const cov: Coverage = { need: 1, apps: 0.5, inputs: 0, steps: "skipped", hand: 1, output: 1, never: 0.5 };
    const { container } = render(
      <>
        <StillNeeds coverage={cov} words={STAGE_WORDS} />
        <EnoughButton coverage={cov} agreed={false} onEnough={() => {}} words={STAGE_WORDS} />
      </>,
    );
    expect(container.querySelector("[data-role='still-needs']")!.textContent).toBe(
      "She still needs: where it happens and what she reads",
    );
    expect(container.querySelector(".sp-enough__open")!.textContent).toBe(
      `${STAGE_WORDS.leftOpen}: where it happens, what she reads and what she must never do`,
    );
  });
});
