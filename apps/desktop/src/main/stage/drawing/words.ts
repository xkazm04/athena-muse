// The Drawing view's own plain words: what only this view says (its empty territories, the note's
// last line, the strip's and the drawer's headings). Everything both views say is in ../words.ts.

export const DRAWING_WORDS = {
  laneEmpty: "Not known yet",
  handEmpty: "Nothing waits for your signature yet",
  fenceEmpty: "Nothing yet. She will ask what she must never do.",
  laneCovered: { 0: "Not known yet", 0.5: "Only her pencil so far", 1: "Inked: she knows this", skipped: "Left for her default" },
  note: "What Athena needs from you now",
  pencilLeft: (n: number) => `${n} ${n === 1 ? "idea" : "ideas"} of hers still in pencil`,
  inkAll: "Ink them all",
  draftProject: "Draft project",
  inkThis: (label: string) => `Ink it: ${label}`,
  wholePicture: "That's the whole picture. Shall I write it?",
  lookAgain: "Look it over again if you like, then write it.",
  writeIt: "Write it",
  inkFirst: (n: number) => `Ink her ${n} pencil ${n === 1 ? "idea" : "ideas"} first`,
  pointAtAny: "Or look it over: point at any piece.",
  nextApp: "Her practice apps appear here once the chore is written",
  writtenHint: "With her practice apps, made up for the test.",
  writeAgain: "Write it again",
  nothingNeeded: "Nothing needed from you while it runs.",
  compared: "Compared with what you said.",
  backToSketch: "Back to the sketch",
  previewHint: "One careful pass over the sketch. Nothing is filed anywhere.",
  allMarked: "Everything is marked.",
  pieceKind: (kind: string, label: string, detail: string | undefined, who: string, state: string) =>
    `${kind}: ${label}${detail ? `, ${detail}` : ""}. ${who}. ${state}.`,
  you: "You said it",
  her: "Her idea",
  inInk: "In ink",
  inPencil: "In pencil. Press Enter to ink it or rub it out",
} as const;
