// The stage's plain words, shared by both views. The screen never says token, OP, world.json, truth,
// bench, slot or node.

import type { DraftStep, SketchKind, Slot, StageView } from "../../lib/contract";

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

/** The rail's names for the draft's steps (the winners' seven). */
export const STEP_LABEL: Record<DraftStep, string> = {
  describe: "Describe",
  shape: "Shape",
  author: "Write",
  preview: "Check",
  rehearse: "Test",
  verdict: "Verdict",
  saved: "Keep",
};

/** What a piece is, in the person's words. */
export const KIND_LABEL: Record<SketchKind, string> = {
  app: "Where it happens",
  source: "What she reads",
  step: "A step",
  gate: "Waits for your signature",
  output: "What you get",
  never: "What she must never do",
};

/** "She still needs ..." per slot. */
export const NEED_PHRASE: Record<Slot, string> = {
  need: "your chore in a sentence",
  apps: "where it happens",
  inputs: "what she reads",
  steps: "the steps",
  hand: "what waits for your signature",
  output: "what you get",
  never: "what she must never do",
};

export const STAGE_WORDS = {
  slot: SLOT_TITLE,
  view: VIEW_LABEL,
  step: STEP_LABEL,
  kind: KIND_LABEL,
  needPhrase: NEED_PHRASE,
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

  // the frame
  rail: "Where you are in making this chore",
  views: "How the sketch is drawn",
  history: "History in her window",
  historyHint: "The whole conversation so far is in her window",
  leave: "Projects",
  youSaid: "You said",
  about: "About",
  send: "Send",
  sending: "She is reading what you wrote",
  suggestions: "Suggested answers",
  stillNeeds: "She still needs",
  ready: "Ready when you are.",
  leftOpen: "Write it now and she fills in a sensible default for",
  retry: "Try again",
  sayDifferently: "Say it differently",

  // a piece
  inkIt: "Ink it",
  dropIt: "Not this",
  close: "Close",
  youWrote: "You said this.",
  herGuess: "Her idea, still in pencil. Is it right?",
  herInked: "Her idea, and you inked it.",
  rubbedOut: "Rubbed out",
  undo: "Undo",

  // after "Not quite" or a chore that could not be written
  backToSketch: "Back to the sketch.",
  couldNotWrite: "She could not write it.",

  // writing
  writing: "Writing your chore",
  repairing: "Fixing what her own check found",
  written: "Written",
  unwritten: "She could not write it",
  writingHint: "She also makes up practice apps to try it on. About a minute.",
  problems: "The problems, in plain words",
  nothingLost: "Nothing you drew is lost.",
  practiceTile: "A practice app, made up for the test",
  reads: "Reads",
  does: "Does",
  onlyLooks: "nothing: she can only look here",
  showCards: "Show me what she will file",
  rows: "invented rows",

  // the check step
  checkTitle: "What she expects to file",
  checkHint: "Mark each card. Yes means she should file it.",
  checkLoading: "Working out what she will file",
  shouldFile: "Should she file this one?",
  yes: "Yes",
  no: "No",
  whyNot: "Why not? (optional)",
  missed: "She missed one",
  missedHint: "A card she should have listed",
  never: "She must never...",
  neverHint: "Something she must never do",
  add: "Add",
  remove: "Remove",
  marked: "marked",
  toMark: "still to mark",
  runTest: "Run the test",

  // the test run
  running: "Testing on her practice apps",
  runningHint: "Nothing real is touched. Cards she files wait for a signature that never comes in a test.",
  startTest: "Start the test run",
  phases: "Her practice apps, in order",
  starting: "Opening her practice apps",
  now: "Now",
  done: "Done",
  ranAll: "She ran every step on her practice apps.",
  filed: "Cards she filed",
  noneYet: "None yet. She is still reading.",
  of: "of",
  aboutTime: "of about",
  stopped: "The test run stopped",

  // the verdict
  verdictTitle: "Her cards beside your marks",
  short: "She found fewer than you expected.",
  allFound: "She found everything you expected.",
  filedIt: "She filed it",
  missedIt: "She missed it",
  leftAlone: "Left alone",
  filedNo: "Filed one you said no to",
  unscored: "Kept, not scored",
  youExpected: "You expected it",
  youSaidNo: "You said no",
  yourLine: "Your missed line",
  neverLine: "Your never line",
  forbids: "Forbids",
  keptAsWords: "Kept as words: no practice app can do it",
  keep: "This is it",
  revise: "Not quite",
  reviseNote: "What is not right? (optional)",

  // saved
  savedTitle: "Handed off to a new Project",
  savedHint: "It lives in your own library, not the app's.",
  choreKept: "Chore kept",
  openProject: "Open the project",
} as const;

export type StageWords = typeof STAGE_WORDS;
