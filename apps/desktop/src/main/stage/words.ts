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

/** The rail's names for the draft's steps (the winners' seven, and signing in, ADR 0014). */
export const STEP_LABEL: Record<DraftStep, string> = {
  describe: "Describe",
  shape: "Shape",
  author: "Write",
  preview: "Check",
  rehearse: "Test",
  verdict: "Verdict",
  access: "Sign in",
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
  writingHint: "She also makes up practice apps to try it on.",
  problems: "The problems, in plain words",
  nothingLost: "Nothing you drew is lost.",
  practiceTile: "A practice app, made up for the test",
  reads: "Reads",
  does: "Does",
  onlyLooks: "nothing: she can only look here",
  showCards: "Show me what she will file",
  rows: "invented rows",

  // her background work: writing, the cards, the test run (onboarding-jobs). No promise of a time.
  jobHint: {
    write: "This can take a few minutes. You can leave; I'll tell you when it is written.",
    preview: "This can take a minute or two. You can leave; I'll tell you when the cards are ready.",
    rehearse: "This can take a few minutes. You can leave; I'll tell you when the test is done.",
  },
  soFar: "so far",
  stop: "Stop",
  stopping: "Stopping",
  leaveForNow: "Leave for now",
  youStopped: "You stopped her.",
  sheStopped: "She stopped before the end.",
  writeAgain: "Write again",
  nothingLostStop: "Nothing you drew is lost.",

  // meanwhile: two questions while she works, never in the way
  meanwhile: "While she works",
  expectQ: "What do you expect her to find when she runs it?",
  expectHint: "One thing per line. At the check, any she did not list is added for you.",
  expectAdd: "Something you expect her to find",
  neverQ: "Is there anything she must never do?",
  neverFromSketch: "From your sketch. Keep them, change them or add to them.",
  neverAdd: "Something she must never do",
  thatsAll: "That's all",
  keepThese: "Keep these",
  skip: "Skip",

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

  // a piece's real site (ADR 0014)
  site: "The real site",
  siteGuess: "her guess: ink it if it is right",

  // signing in to the real sites (ADR 0014)
  accessTitle: "Sign in to the sites she needs",
  accessHint:
    "Each one opens in her browser. You sign in on the site's own page; Athena never sees your password. Next time she gets in on her own.",
  accessList: "The sites this chore needs",
  signIn: "Sign in",
  signInAgain: "Open it again",
  signedInNow: "I have signed in",
  skipSite: "Skip for now",
  signInAfterAll: "Sign in after all",
  toDo: "to do",
  signedIn: "signed in",
  skipped: "skipped",
  skippedHint: "Until you sign in, the project shows this site as a blocker.",
  signingIn: "Sign in on the page in her browser. She keeps checking until you are in.",
  useMoved: (host: string) => `Use ${host} instead`,
  accessDone: "signed in or skipped",

  // saved
  savedTitle: "Handed off to a new Project",
  savedHint: "It lives in your own library, not the app's.",
  choreKept: "Chore kept",
  openProject: "Open the project",
} as const;

export type StageWords = typeof STAGE_WORDS;
