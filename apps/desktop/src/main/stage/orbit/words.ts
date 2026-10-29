// The Orbit view's own plain words: the few lines only this view says (the shared words are in
// ../words.ts). The screen never says token, node, slot or op.

import type { Slot } from "../../../lib/contract";
import type { StageWords } from "../words";

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

export const ORBIT_WORDS = {
  you: "You",
  notKnown: "Not known yet",
  keepInk: "Keep it in ink",
  inkAll: (n: number) => `Ink all her pencil marks (${n})`,
  more: (n: number) => `+${n} more`,
  moreTitle: (zone: string) => `${zone}: every piece`,
  whole: "That is the whole picture.",
  wholeCount: (all: number, pencil: number) =>
    `${plural(all, "piece")} around this card: ${all - pencil} in ink${
      pencil ? `, ${pencil} still in pencil. Point at one to keep it or drop it.` : "."
    }`,
  reading: "She is reading what you wrote.",
  writtenHint: "Her practice apps are ready, with invented rows to try it on. Nothing real was touched.",
  cardsTitle: "Would you want her to file this?",
  cardOf: (i: number, n: number) => `Card ${i} of ${n}`,
  cardDot: (i: number, n: number, mark: string) => `Card ${i} of ${n}: ${mark}`,
  waiting: "waiting for you",
  earlier: "Earlier card",
  next: "Next card",
  toLines: "Next: missed and never",
  backToCards: "Back to the cards",
  keysHint: "Y yes, N no, arrows move",
  linesTitle: "Two last questions",
  linesHint: "Then she tries it on her practice apps.",
  runFiled: "Cards she files",
  scoreTitle: "The test is done",
  /** What an arc says when pointed at: how much of that place she knows. */
  arc: (slot: Slot, name: string, all: number, pencil: number) => {
    if (slot === "need") return `${name}: in your own words`;
    if (!all) return `${name}: not known yet`;
    return `${name}: ${plural(all, "piece")}${pencil ? `, ${pencil} in pencil` : ", all in ink"}`;
  },
  /** A chip's accessible name: whose idea it is and what it says. */
  chip: (label: string, pencil: boolean, words: StageWords) => `${pencil ? words.hers : words.inked}: ${label}`,
} as const;
