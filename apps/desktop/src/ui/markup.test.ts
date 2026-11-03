// @vitest-environment node
import { describe, expect, it } from "vitest";
import { parseInline, parseProse, revealStarts, type Block, type Inline } from "./markup";

const blocks = (text: string) => parseProse(text).blocks;
/** The inline nodes of a one-paragraph text, without offsets. */
const inline = (text: string, open = false): unknown => {
  const b = blocks(text)[0];
  if (b?.kind !== "p") throw new Error(`not a paragraph: ${b?.kind}`);
  return strip(parseInline(b.body, open));
};
/** Nodes as plain data, adjacent text joined (an escape is its own node, keyed on its own offset). */
const strip = (nodes: Inline[]): unknown[] =>
  nodes.map((n): unknown => {
    switch (n.kind) {
      case "text":
        return n.text;
      case "br":
        return "<br>";
      case "code":
        return { code: n.text };
      case "link":
        return { link: strip(n.label), url: n.url };
      default:
        return { [n.kind]: strip(n.children) };
    }
  }).reduce<unknown[]>((out, x) => {
    const prev = out[out.length - 1];
    if (typeof x === "string" && typeof prev === "string" && prev !== "<br>" && x !== "<br>") out[out.length - 1] = prev + x;
    else out.push(x);
    return out;
  }, []);
const kinds = (text: string) => blocks(text).map((b) => b.kind);

describe("markup blocks", () => {
  it("splits paragraphs on blank lines and keeps single newlines as line breaks", () => {
    expect(kinds("one\n\ntwo")).toEqual(["p", "p"]);
    expect(inline("one\ntwo")).toEqual(["one", "<br>", "two"]);
    expect(inline("one\r\ntwo")).toEqual(["one", "<br>", "two"]);
  });

  it("reads bulleted and numbered lists, a blank line between items keeping the list", () => {
    const [ul] = blocks("- a\n* b\n+ c") as [Extract<Block, { kind: "list" }>];
    expect(ul.ordered).toBe(false);
    expect(ul.items.map((i) => i.lines.map((l) => l.text))).toEqual([["a"], ["b"], ["c"]]);
    const [ol] = blocks("3. three\n\n4. four") as [Extract<Block, { kind: "list" }>];
    expect(ol).toMatchObject({ ordered: true, first: 3 });
    expect(ol.items).toHaveLength(2);
  });

  it("lets a bulleted list or one numbered from 1 interrupt a paragraph, and nothing else", () => {
    expect(kinds("Done:\n- a")).toEqual(["p", "list"]);
    expect(kinds("Steps:\n1. a")).toEqual(["p", "list"]);
    expect(kinds("In\n2024. it rained")).toEqual(["p"]);
  });

  it("continues an item on an indented line; an unindented line ends the list", () => {
    const [list, p] = blocks("- a\n  more\n- b\nSo that is it.") as [Extract<Block, { kind: "list" }>, Block];
    expect(list.items[0]!.lines.map((l) => l.text)).toEqual(["a", "more"]);
    expect(p.kind).toBe("p");
  });

  it("reads a fenced block verbatim, with its language as a hint", () => {
    const src = 'Run:\n\n```py\n  print("a\\tb")  \n\tx = "curly “quotes” kept"\n```\nafter';
    const [, code, after] = blocks(src);
    expect(code).toMatchObject({ kind: "code", lang: "py", closed: true, text: '  print("a\\tb")  \n\tx = "curly “quotes” kept"' });
    expect(after?.kind).toBe("p");
    expect(blocks("~~~\nx\n~~~")[0]).toMatchObject({ kind: "code", text: "x", closed: true });
  });

  it("leaves what is not the subset as a paragraph of its own characters", () => {
    expect(kinds("#### Deep\n\n> quote\n\n| a | b |\n\n---\n\n* * *")).toEqual(["p", "p", "p", "p", "p"]);
    expect(inline("#### Deep")).toEqual(["#### Deep"]);
    expect(inline("#hashtag and #5")).toEqual(["#hashtag and #5"]);
    expect(inline("<script>alert(1)</script>")).toEqual(["<script>alert(1)</script>"]);
  });

  it("reads # to ### as a heading of its words, one level for every depth", () => {
    expect(kinds("# One\n## Two\n### Three")).toEqual(["h", "h", "h"]);
    const [h] = blocks("##  Where it stands ##") as [Extract<Block, { kind: "h" }>];
    expect(h.body.lines).toEqual([{ text: "Where it stands", at: 4 }]);
    // a heading ends the paragraph above it and needs words of its own
    expect(kinds("So far:\n## Next\nmore")).toEqual(["p", "h", "p"]);
    expect(kinds("##\n\n## ")).toEqual(["p", "p"]);
    expect(inline("##")).toEqual(["##"]); // settled: a bare marker is its characters
  });

  it("holds a bare # back at a live tail until the next delta decides it", () => {
    expect(inline("#", true)).toEqual([]);
    expect(inline("Done.\n##", true)).toEqual(["Done.", "<br>"]);
    expect(inline("Done.\n## ", true)).toEqual(["Done.", "<br>"]);
    expect(inline("#hash", true)).toEqual(["#hash"]); // decided: not a heading
    expect(inline("####", true)).toEqual(["####"]); // deeper than the subset: never a heading
    // the next delta decides: a space and words make it a heading, read again from that block
    const prev = parseProse("Done.\n\n##");
    const next = parseProse("Done.\n\n## Ne", prev);
    expect(next.blocks.map((b) => b.kind)).toEqual(["p", "h"]);
  });
});

describe("markup inline", () => {
  it("reads bold, italic, inline code and links", () => {
    expect(inline("a **b** *c* `d` [e](https://x.test/f)")).toEqual([
      "a ",
      { strong: ["b"] },
      " ",
      { em: ["c"] },
      " ",
      { code: "d" },
      " ",
      { link: ["e"], url: "https://x.test/f" },
    ]);
    expect(inline("***both***")).toEqual([{ strong: [{ em: ["both"] }] }]);
    expect(inline("**a *b* c**")).toEqual([{ strong: ["a ", { em: ["b"] }, " c"] }]);
    expect(inline("``a ` b``")).toEqual([{ code: "a ` b" }]);
  });

  it("keeps lone and spaced stars, escapes and unmatched markers literal in settled text", () => {
    expect(inline("5 * 3 = 15")).toEqual(["5 * 3 = 15"]);
    expect(inline("\\*not\\* emphasis")).toEqual(["*not* emphasis"]);
    expect(inline("**never closed")).toEqual(["**never closed"]);
    expect(inline("a `tick")).toEqual(["a `tick"]);
    expect(inline("[label](no-close")).toEqual(["[label](no-close"]);
    expect(inline("snake_case_name")).toEqual(["snake_case_name"]);
  });

  it("reads code spans literally: no emphasis or links inside", () => {
    expect(inline("`**x** [a](b)`")).toEqual([{ code: "**x** [a](b)" }]);
  });
});

describe("a streaming prefix", () => {
  it("closes an open ** or * or ` at the tail, without showing the marker", () => {
    expect(inline("Note: **impor", true)).toEqual(["Note: ", { strong: ["impor"] }]);
    expect(inline("so *wai", true)).toEqual(["so ", { em: ["wai"] }]);
    expect(inline("run `npm in", true)).toEqual(["run ", { code: "npm in" }]);
    expect(inline("[docs](https://ex", true)).toEqual([{ link: ["docs"], url: "https://ex" }]);
  });

  it("holds back a marker run the next delta has yet to decide", () => {
    expect(inline("wait **", true)).toEqual(["wait "]);
    expect(inline("wait *", true)).toEqual(["wait "]);
    expect(inline("**done*", true)).toEqual([{ strong: ["done"] }]);
    expect(inline("a ``", true)).toEqual(["a "]);
    expect(inline("end\\", true)).toEqual(["end"]);
  });

  it("does not style a star inside a word before its closer arrives", () => {
    expect(inline("2*3", true)).toEqual(["2*3"]);
  });

  it("renders an open fence as a code block growing line by line", () => {
    expect(blocks("Here:\n\n```js\nconst a")).toMatchObject([{ kind: "p" }, { kind: "code", lang: "js", text: "const a", closed: false }]);
    expect(blocks("```")).toMatchObject([{ kind: "code", text: "", closed: false }]);
  });

  it("keeps a bare marker on the last line a paragraph until a space decides it", () => {
    expect(kinds("-")).toEqual(["p"]);
    expect(kinds("- ")).toEqual(["list"]);
    expect(kinds("1.")).toEqual(["p"]);
  });

  it("never reclassifies a block once its fence or item has begun", () => {
    const doc = "Here:\n\n```js\nconst a = 1;\n```\n\n- one\n- two **bold**\n\nDone.";
    const codeFrom = doc.indexOf("```js\n") + 6;
    const listFrom = doc.indexOf("- one") + 2;
    for (let n = 1; n <= doc.length; n++) {
      const got = kinds(doc.slice(0, n));
      if (n >= codeFrom) expect(got[1], `prefix ${n}`).toBe("code");
      if (n >= listFrom) expect(got[2], `prefix ${n}`).toBe("list");
    }
  });

  it("re-reads only from the last block, with the same result as reading it all", () => {
    const docs = [
      "Here:\n\n```js\nconst a = 1;\n```\n\n- one\n- two **bold**\n\nDone.",
      "1. a\n\n2. b\n\n3. c\nand then\n\n- x\n\n-\n- y",
      "para\n-\n- a\n\n\n- b\n\n```\nopen fence\n\n- not a list",
    ];
    for (const doc of docs) {
      let prev = parseProse("");
      for (let n = 1; n <= doc.length; n++) {
        prev = parseProse(doc.slice(0, n), prev);
        expect(prev.blocks, `prefix ${n} of ${JSON.stringify(doc)}`).toEqual(parseProse(doc.slice(0, n)).blocks);
      }
    }
  });

  it("keeps a block that was followed by another the same object, so it is not rendered again", () => {
    const a = parseProse("one\n\ntwo");
    const b = parseProse("one\n\ntwo more", a);
    expect(b.blocks[0]).toBe(a.blocks[0]);
    expect(b.blocks[1]).not.toBe(a.blocks[1]);
  });
});

describe("revealStarts", () => {
  it("starts a reveal at each delta, snapped forward to the next word", () => {
    expect(revealStarts("By April 15.", [0, 8])).toEqual([0, 9]);
    // a delta that begins inside a word joins the span the word began in
    expect(revealStarts("By April 15.", [0, 6])).toEqual([0, 9]);
    expect(revealStarts("By April", [0, 6])).toEqual([0]);
    expect(revealStarts("one two", [0, 3, 7])).toEqual([0, 4]);
  });
});
