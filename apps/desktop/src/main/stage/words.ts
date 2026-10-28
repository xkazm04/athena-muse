// The stage's plain words, shared by both views. The screen never says token, OP, world.json, truth,
// bench, slot or node.

import type { Slot, StageView } from "../../lib/contract";

export const SLOT_TITLE: Record<Slot, string> = {
  need: "Your chore, in your words",
  apps: "Where it happens",
  inputs: "What she reads",
  steps: "The steps",
  hand: "Waits for your signature",
  output: "What you get",
  never: "What she must never do",
};

export const VIEW_LABEL: Record<StageView, string> = {
  drawing: "Drawing",
  orbit: "Orbit",
};

export const STAGE_WORDS = {
  slot: SLOT_TITLE,
  view: VIEW_LABEL,
  enough: "That's enough, write it",
  ownWords: "Or say it your own way",
  invented: "Invented example",
  yours: "your words",
  hers: "her guess, waiting for your yes",
  inked: "agreed",
  thinking: "Athena is thinking",
  slow: "Still thinking. She can take a little longer on a hard one.",
  failed: "She did not answer. Nothing changed; try again.",
  practiceApps: "her practice apps",
  testRun: "test run",
  expect: "what you expect",
  neverSigned: "From the test run. Nothing here can be signed.",
} as const;

export type StageWords = typeof STAGE_WORDS;
