import { describe, expect, it } from "vitest";
import type { Card, Turn, TurnPart } from "../lib/contract";
import { BOOK_KEYS, bookCommand, turnTo } from "./keymap";
import {
  bookmarkTarget,
  dateShort,
  exchangesOf,
  formatCost,
  isShort,
  NOW,
  plainOf,
  receiptsOf,
  secs,
  strayWaiting,
  triedAgainNext,
  WAITING,
  waitsWords,
} from "./model";
import { PHASE, SHOWS, nextPhase, phaseOf, type Phase } from "./phase";

let n = 0;
const person = (text: string): Turn => ({ id: `t${++n}`, space_id: "s", role: "person", text, created: "2026-11-03T10:00:00Z" });
const athena = (parts: TurnPart[], extra: Partial<Turn> = {}): Turn => ({
  id: `t${++n}`,
  space_id: "s",
  role: "athena",
  text: parts.flatMap((p) => (p.kind === "text" ? [p.text] : [])).join(""),
  created: "2026-11-03T10:01:00Z",
  parts,
  ...extra,
});
const card = (id: string, state: Card["state"] = "waiting", created = "2026-11-03T10:00:00Z"): Card => ({
  id,
  space_id: "s",
  action: "propose_brief",
  label: "Change this project's brief to: x",
  args: {},
  state,
  created,
});

describe("exchanges", () => {
  it("pairs each question with the reply that answers it, numbered from one", () => {
    const xs = exchangesOf([person("a"), athena([{ kind: "text", text: "A", at_ms: 900 }]), person("b"), athena([{ kind: "text", text: "B" }])]);
    expect(xs.map((x) => [x.key, x.person?.text, x.reply?.text])).toEqual([
      ["p1", "a", "A"],
      ["p2", "b", "B"],
    ]);
  });

  it("keeps a stopped try with its reason, and marks the same words asked again as a second try", () => {
    const xs = exchangesOf([
      person("Which offers wait?"),
      athena([{ kind: "tool", name: "record_list", label: "Looked through the licence offers", class: "auto", at_ms: 1200 }], { stopped: "Meta is rate limiting" }),
      person("Which offers wait?"),
      athena([{ kind: "text", text: "Two." }]),
    ]);
    expect(xs[0]!.stopped).toBe("Meta is rate limiting");
    expect(xs[1]!.secondTry).toBe(true);
    expect(triedAgainNext(xs, 0)).toBe(true);
    expect(triedAgainNext(xs, 1)).toBe(false);
  });

  it("says a question with no reply was not answered, and a reply with no question stands alone", () => {
    const xs = exchangesOf([athena([{ kind: "text", text: "Hello, I am Athena." }]), person("hi"), person("hi")]);
    expect(xs.map((x) => [x.person?.text ?? null, x.unanswered, x.secondTry])).toEqual([
      [null, false, false],
      ["hi", true, false],
      ["hi", true, true],
    ]);
  });

  it("reads a turn stored before parts were kept as its words and its card", () => {
    const old: Turn = { id: "o", space_id: "s", role: "athena", text: "Sign this.", created: "x", card_id: "c1" };
    const [x] = exchangesOf([person("q"), old]);
    expect(x!.parts.map((p) => p.kind)).toEqual(["text", "card"]);
    expect(x!.cards).toEqual(["c1"]);
  });
});

describe("receipts", () => {
  const words = (id: string) => (id === "c1" ? "Change the brief" : undefined);

  it("says each step in order with the moment the daemon kept, and folds a gated line into its card", () => {
    const [x] = exchangesOf([
      person("q"),
      athena([
        { kind: "tool", name: "record_list", label: "Looked through the creators", class: "auto", at_ms: 4000 },
        { kind: "tool", name: "recall", label: "Looked through memory", class: "auto", at_ms: 26000 },
        { kind: "tool", name: "record_put", label: "Keep: x", class: "gated", at_ms: 59000 },
        { kind: "card", card_id: "c1", at_ms: 59000 },
        { kind: "text", text: "Done.", at_ms: 111000 },
      ]),
    ]);
    expect(receiptsOf(x!.parts, words)).toEqual([
      { sort: "look", at: 4000, text: "Looked through the creators" },
      { sort: "memory", at: 26000, text: "Looked through memory" },
      { sort: "card", at: 59000, text: "Filed a card for your signature", sub: "Change the brief" },
      { sort: "write", at: 111000, text: "Wrote to you" },
    ]);
  });

  it("shows no moment where none was kept, never a guessed one", () => {
    const [x] = exchangesOf([person("q"), athena([{ kind: "text", text: "Old." }])]);
    expect(receiptsOf(x!.parts, words)).toEqual([{ sort: "write", text: "Wrote to you" }]);
  });

  it("names the report parts she showed and what could not be shown, then the stop", () => {
    const shown = { blocks: [{ id: "a", kind: "trend" as const, title: "Views", span: 12, config: {} }], values: {}, dropped: 1, reasons: ["r"] };
    const got = receiptsOf([{ kind: "blocks", shown, at: 3000 }], words, { stopped: "It broke", stoppedAt: 9000 });
    expect(got).toEqual([
      { sort: "parts", at: 3000, text: "Showed parts of the report: “Views”", sub: "1 part could not be shown" },
      { sort: "error", at: 9000, text: "Stopped: It broke" },
    ]);
  });

  it("says the run still being written is being written", () => {
    expect(receiptsOf([{ kind: "text", text: "Hel", marks: [0], at: 10 }], words, { writing: true })[0]!.text).toBe("Writing to you");
  });
});

describe("words for figures", () => {
  it("says every cost is an estimate", () => {
    expect(formatCost(0.033)).toBe("est. $0.0330");
    expect(formatCost(0.00001)).toBe("est. under $0.0001");
    expect(formatCost(1.5)).toBe("est. $1.50");
  });

  it("says a length in seconds, then minutes", () => {
    expect(secs(4000)).toBe("4 s");
    expect(secs(87000)).toBe("1 min 27 s");
    expect(secs(65000)).toBe("1 min 05 s");
  });

  it("says a date short", () => {
    expect(dateShort("2026-11-03T12:00:00")).toBe("3 Nov");
    expect(dateShort("not a date")).toBe("");
  });

  it("sets a short one-paragraph answer large, and nothing else", () => {
    expect(isShort([{ kind: "text", text: "Yes, **two** are waiting.", marks: [0] }])).toBe(true);
    expect(isShort([{ kind: "text", text: "x".repeat(300), marks: [0] }])).toBe(false);
    expect(isShort([{ kind: "text", text: "a", marks: [0] }, { kind: "card", id: "c" }])).toBe(false);
    expect(plainOf("### Head\n- **bold** `code` [a](https://x)")).toBe("Head - bold code a");
  });
});

describe("the bookmark", () => {
  const xs = exchangesOf([person("q"), athena([{ kind: "card", card_id: "c1" }]), person("r"), athena([{ kind: "card", card_id: "c2" }])]);

  it("opens the first page that holds a card waiting for a signature", () => {
    expect(bookmarkTarget(xs, { c1: card("c1", "approved"), c2: card("c2") })).toBe("p2");
    expect(waitsWords(1)).toBe("1 waits for your signature");
    expect(waitsWords(3)).toBe("3 wait for your signature");
  });

  it("opens the page being written when it holds the card, else the page of cards waiting elsewhere", () => {
    expect(bookmarkTarget(xs, { c9: card("c9") }, [{ kind: "card", id: "c9" }])).toBe(NOW);
    const stray = { c1: card("c1", "declined"), c7: card("c7") };
    expect(bookmarkTarget(xs, stray)).toBe(WAITING);
    expect(strayWaiting(xs, stray).map((c) => c.id)).toEqual(["c7"]);
    expect(bookmarkTarget(xs, { c1: card("c1", "approved") })).toBeNull();
  });
});

describe("the keymap", () => {
  const key = (k: string, extra: object = {}) => ({ key: k, target: null, ...extra });

  it("turns pages with the arrows and Page Up/Down, Home to the first page, End to the page being written", () => {
    expect(Object.keys(BOOK_KEYS).sort()).toEqual(["ArrowLeft", "ArrowRight", "End", "Home", "PageDown", "PageUp"]);
    expect(bookCommand(key("ArrowRight"))).toBe("next");
    expect(bookCommand(key("PageUp"))).toBe("prev");
    expect(turnTo("next", 6, 10, 7)).toBe(7);
    expect(turnTo("prev", 0, 10, 7)).toBe(0);
    expect(turnTo("now", 2, 10, 7)).toBe(7);
    expect(turnTo("first", 5, 10, 7)).toBe(0);
  });

  it("leaves keys held with a modifier, or typed into a field, alone", () => {
    expect(bookCommand(key("ArrowRight", { ctrlKey: true }))).toBeNull();
    expect(bookCommand(key("ArrowRight", { target: document.createElement("textarea") }))).toBeNull();
    expect(bookCommand(key("x"))).toBeNull();
  });
});

describe("the page being written", () => {
  it("asks, writes, then settles into the book; a page that cannot be read back fails and can try again", () => {
    expect(nextPhase("ask", "send")).toBe("writing");
    expect(nextPhase("writing", "settle")).toBe("ask");
    expect(nextPhase("writing", "fail")).toBe("failed");
    expect(nextPhase("failed", "retry")).toBe("writing");
    expect(nextPhase("failed", "again")).toBe("ask");
    expect(nextPhase("ask", "settle")).toBe("ask");
  });

  it("reads the store, and every phase shows one way out", () => {
    expect(phaseOf({ streaming: true, live: null })).toBe("writing");
    expect(phaseOf({ streaming: false, live: { parts: [], done: false, started: 0, error: "x" } })).toBe("failed");
    expect(phaseOf({ streaming: false, live: null })).toBe("ask");
    for (const p of Object.keys(PHASE) as Phase[]) {
      const s = SHOWS[p];
      expect([s.composer, s.stop, s.retry].filter(Boolean)).toHaveLength(1);
    }
  });
});
