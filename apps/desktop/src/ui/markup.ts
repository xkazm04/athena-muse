// The one door model-authored prose comes through (the chat-transcript technique "one sanitizing
// door"): a small, dependency-free reader of a markdown SUBSET - paragraphs, line breaks, **bold**,
// *italic*, `inline code`, fenced code blocks, bulleted and numbered lists, links, and `#` to `###`
// headings (read as one bold line: a chat column is not a document, so there is no size scale). It
// returns a plain tree; `Prose.tsx` turns the tree into React elements, so every string reaches the
// page as a React text node and nothing is ever parsed as HTML. Whatever is not the subset (deeper
// headings, tables, quotes, raw HTML, images) stays literal text.
//
// The text may be a streaming prefix. Blocks are read line by line from the top, and every block but
// the last is final once the next one starts, so a later delta re-reads only the last block (the
// checkpoint). The last block of a live turn is read with provisional closure: an open fence is a code
// block growing line by line, an unclosed ** or * or ` is styled as if closed at the tail, and a
// marker run still undecided at the very end is held back until the next delta decides it. Settled
// text is read without provisional closure, so an unmatched marker there is literal.

export type Inline =
  /** `at` is the absolute offset of `text` in the source, which the word reveal keys on. */
  | { kind: "text"; text: string; at: number }
  | { kind: "strong" | "em"; children: Inline[] }
  | { kind: "code"; text: string }
  | { kind: "link"; label: Inline[]; url: string }
  | { kind: "br" };

/** A run of source lines read as one unit: a paragraph or a list item's text. */
export interface Span {
  /** Each line's text with its indentation trimmed, and the absolute offset of its first character. */
  lines: { text: string; at: number }[];
}

export type Block =
  | { kind: "p"; start: number; end: number; body: Span }
  /** A `#`, `##` or `###` line: one emphasis level whatever its depth. */
  | { kind: "h"; start: number; end: number; body: Span }
  | { kind: "list"; start: number; end: number; ordered: boolean; first: number; items: Span[] }
  | { kind: "code"; start: number; end: number; lang: string; text: string; closed: boolean };

export interface Parsed {
  text: string;
  blocks: Block[];
}

interface Line {
  text: string;
  at: number;
}

const FENCE_OPEN = /^ {0,3}(`{3,}|~{3,})(.*)$/;
const ITEM = /^( {0,3})([-*+]|\d{1,9}[.)])(?:[ \t]+(.*))?$/;
const BLANK = /^\s*$/;
/** `#` to `###`, a space, then words; deeper levels and `#word` are not headings. */
const HEADING = /^( {0,3}#{1,3}[ \t]+)(.*)$/;

/** The heading on `line`, as the span of its words (a closing `##` run dropped), or null. A heading
 *  needs words: a bare `##` is a paragraph's characters (and, at a live tail, undecided). */
function headingOf(line: Line): Span | null {
  const m = HEADING.exec(line.text);
  if (!m) return null;
  const words = m[2]!.replace(/(^|[ \t]+)#+[ \t]*$/, "").trimEnd();
  if (!words.trim()) return null;
  const lead = m[2]!.length - m[2]!.trimStart().length;
  return { lines: [{ text: words.trim(), at: line.at + m[1]!.length + lead }] };
}

function linesOf(text: string, from: number): Line[] {
  const out: Line[] = [];
  let at = from;
  while (at <= text.length) {
    const nl = text.indexOf("\n", at);
    const end = nl === -1 ? text.length : nl;
    const raw = text.slice(at, end);
    out.push({ text: raw.endsWith("\r") ? raw.slice(0, -1) : raw, at });
    if (nl === -1) break;
    at = nl + 1;
  }
  return out;
}

interface Item {
  ordered: boolean;
  num: number;
  /** Absolute offset of the item's text (after the marker). */
  at: number;
  text: string;
}

function itemOf(line: Line, last: boolean): Item | null {
  const m = ITEM.exec(line.text);
  if (!m) return null;
  // A bare marker on the text's last line is undecided ("1." may yet be "1.5", "*" may yet be
  // "**bold**"): until a space or a newline follows it, it is a paragraph's words.
  if (m[3] === undefined && last) return null;
  const marker = m[2]!;
  const body = m[3] ?? "";
  const ordered = /\d/.test(marker);
  // "* * *" or "- - -" is a rule in markdown; not in the subset, so it stays a paragraph.
  if (!ordered && /^[-*+](\s*[-*+]){2,}\s*$/.test(line.text.trim())) return null;
  const offset = line.text.length - body.length;
  return { ordered, num: ordered ? Number.parseInt(marker, 10) : 0, at: line.at + offset, text: body };
}

/** A list item may start inside a paragraph when it is bulleted with words, or numbered from 1. */
const interrupts = (item: Item): boolean => item.text.trim() !== "" && (!item.ordered || item.num === 1);

const trimmed = (line: Line): Line => {
  const lead = line.text.length - line.text.trimStart().length;
  return { text: line.text.slice(lead).trimEnd(), at: line.at + lead };
};

/** Read the blocks of `text` starting at offset `from`, which must be the start of a line. */
function readBlocks(text: string, from: number): Block[] {
  const lines = linesOf(text, from);
  const blocks: Block[] = [];
  const endOf = (line: Line) => line.at + line.text.length;
  let i = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    if (BLANK.test(line.text)) {
      i++;
      continue;
    }

    const fence = FENCE_OPEN.exec(line.text);
    if (fence && !(fence[1]!.startsWith("`") && fence[2]!.includes("`"))) {
      const mark = fence[1]!;
      const close = new RegExp(`^ {0,3}${mark[0] === "`" ? "`" : "~"}{${mark.length},}\\s*$`);
      const body: string[] = [];
      let j = i + 1;
      let closed = false;
      while (j < lines.length) {
        if (close.test(lines[j]!.text)) {
          closed = true;
          break;
        }
        body.push(lines[j]!.text);
        j++;
      }
      const last = closed ? lines[j]! : lines[j - 1]!;
      blocks.push({
        kind: "code",
        start: line.at,
        end: endOf(last),
        lang: fence[2]!.trim().split(/\s+/)[0] ?? "",
        text: body.join("\n"),
        closed,
      });
      i = closed ? j + 1 : j;
      continue;
    }

    const heading = headingOf(line);
    if (heading) {
      blocks.push({ kind: "h", start: line.at, end: endOf(line), body: heading });
      i++;
      continue;
    }

    const first = itemOf(line, i === lines.length - 1);
    if (first) {
      const items: Span[] = [{ lines: [{ text: first.text.trim(), at: first.at + (first.text.length - first.text.trimStart().length) }] }];
      let end = endOf(line);
      let j = i + 1;
      while (j < lines.length) {
        const next = lines[j]!;
        if (BLANK.test(next.text)) {
          // A blank line keeps the list open only when the next words are another item of its kind.
          let k = j + 1;
          while (k < lines.length && BLANK.test(lines[k]!.text)) k++;
          const after = k < lines.length ? itemOf(lines[k]!, k === lines.length - 1) : null;
          if (after && after.ordered === first.ordered) {
            j = k;
            continue;
          }
          break;
        }
        const item = itemOf(next, j === lines.length - 1);
        if (item) {
          if (item.ordered !== first.ordered) break;
          const lead = item.text.length - item.text.trimStart().length;
          items.push({ lines: [{ text: item.text.trim(), at: item.at + lead }] });
        } else if (/^(\t| {2,})/.test(next.text) && !FENCE_OPEN.test(next.text)) {
          // An indented line continues the item above it, after a line break.
          items[items.length - 1]!.lines.push(trimmed(next));
        } else {
          break;
        }
        end = endOf(next);
        j++;
      }
      blocks.push({ kind: "list", start: line.at, end, ordered: first.ordered, first: first.ordered ? first.num : 1, items });
      i = j;
      continue;
    }

    const body: Span = { lines: [trimmed(line)] };
    let end = endOf(line);
    let j = i + 1;
    while (j < lines.length) {
      const next = lines[j]!;
      if (BLANK.test(next.text) || FENCE_OPEN.test(next.text) || headingOf(next)) break;
      const item = itemOf(next, j === lines.length - 1);
      if (item && interrupts(item)) break;
      body.lines.push(trimmed(next));
      end = endOf(next);
      j++;
    }
    blocks.push({ kind: "p", start: line.at, end, body });
    i = j;
  }
  return blocks;
}

/**
 * Read `text` into blocks. Given the previous reading of a prefix of `text`, only the last block of
 * that reading is read again (every block before it was already followed by another, so it is final).
 */
export function parseProse(text: string, prev?: Parsed | null): Parsed {
  if (prev && prev.blocks.length > 1 && text === prev.text) return prev;
  if (prev && prev.blocks.length > 1 && text.startsWith(prev.text)) {
    // A list is the one block a later line can still extend (a blank line, then another item of
    // its kind), so a list just before the last block is read again with it.
    let back = 1;
    if (prev.blocks[prev.blocks.length - 2]!.kind === "list") back = 2;
    const keep = prev.blocks.slice(0, -back);
    const from = prev.blocks[prev.blocks.length - back]!.start;
    return { text, blocks: [...keep, ...readBlocks(text, from)] };
  }
  return { text, blocks: readBlocks(text, 0) };
}

// ---- inline ----

const PUNCT = /[!-/:-@[-`{-~]/;
const isSpace = (c: string | undefined) => c === undefined || /\s/.test(c);

type Closer = "strong" | "em";

interface Reader {
  s: string;
  /** Absolute offset of each character of `s`; a "\n" maps to -1. */
  pos: number[];
  /** Read as a live tail: unclosed constructs close at the end, an undecided trailing marker waits. */
  open: boolean;
}

function readerOf(span: Span, open: boolean): Reader {
  let s = "";
  const pos: number[] = [];
  span.lines.forEach((line, n) => {
    if (n > 0) {
      s += "\n";
      pos.push(-1);
    }
    s += line.text;
    for (let k = 0; k < line.text.length; k++) pos.push(line.at + k);
  });
  return { s, pos, open };
}

function pushText(out: Inline[], r: Reader, from: number, to: number): void {
  // Text never crosses a line break: each line's characters are contiguous in the source.
  let a = from;
  for (let k = from; k <= to; k++) {
    if (k === to || r.s[k] === "\n") {
      if (k > a) {
        const prev = out[out.length - 1];
        const at = r.pos[a]!;
        if (prev?.kind === "text" && prev.at + prev.text.length === at) prev.text += r.s.slice(a, k);
        else out.push({ kind: "text", text: r.s.slice(a, k), at });
      }
      if (k < to) out.push({ kind: "br" });
      a = k + 1;
    }
  }
}

const runAt = (s: string, i: number, ch: string): number => {
  let k = i;
  while (s[k] === ch) k++;
  return k - i;
};

/** Read inline nodes from `i` to `end`. Returns the nodes, where it stopped, and whether `closer` closed. */
function readInline(r: Reader, i: number, end: number, stack: Closer[]): { nodes: Inline[]; at: number; closed: boolean } {
  const out: Inline[] = [];
  const s = r.s;
  let text = i;
  const flush = (to: number) => {
    if (to > text) pushText(out, r, text, to);
  };
  const inner = stack[stack.length - 1];
  while (i < end) {
    const c = s[i]!;

    if (c === "\\" && i + 1 < end && PUNCT.test(s[i + 1]!)) {
      flush(i);
      pushText(out, r, i + 1, i + 2);
      i += 2;
      text = i;
      continue;
    }
    if (c === "\\" && i + 1 === end && r.open) {
      // A trailing backslash may yet escape the next character.
      flush(i);
      return { nodes: out, at: end, closed: false };
    }

    if (c === "#" && r.open && (i === 0 || s[i - 1] === "\n")) {
      // A bare `#` to `###` opening the last line may yet be a heading: it waits off screen until
      // the next delta decides (a space and words make a heading; anything else, its characters).
      const n = runAt(s, i, "#");
      if (n <= 3 && i + n === end) {
        flush(i);
        return { nodes: out, at: end, closed: false };
      }
    }

    if (c === "`") {
      const n = runAt(s, i, "`");
      let k = i + n;
      let close = -1;
      while (k < end) {
        const m = runAt(s, k, "`");
        if (m === n) {
          close = k;
          break;
        }
        k += Math.max(m, 1);
      }
      if (close === -1 && !r.open) {
        i += n; // unmatched: the backticks are literal
        continue;
      }
      flush(i);
      let body = s.slice(i + n, close === -1 ? end : close).replace(/\n/g, " ");
      if (body.length > 2 && body.startsWith(" ") && body.endsWith(" ") && body.trim()) body = body.slice(1, -1);
      if (body || close !== -1) out.push({ kind: "code", text: body });
      i = close === -1 ? end : close + n;
      text = i;
      continue;
    }

    if (c === "*") {
      const n = runAt(s, i, "*");
      const before = s[i - 1];
      const after = s[i + n];
      const right = !isSpace(before);
      const left = i + n < end && !isSpace(after);
      // Closers first: the innermost open construct decides.
      if (right && inner === "em" && !(n === 2 && stack.includes("strong"))) {
        flush(i);
        return { nodes: out, at: i + 1, closed: true };
      }
      if (right && inner === "strong" && n >= 2) {
        flush(i);
        return { nodes: out, at: i + 2, closed: true };
      }
      if (right && inner === "em" && n === 2) {
        // "**" inside *...* while **...** is open: the outer strong closes here; the em never did.
        flush(i);
        return { nodes: out, at: i, closed: false };
      }
      if (left) {
        const kind: Closer = n >= 2 ? "strong" : "em";
        const width = kind === "strong" ? 2 : 1;
        flush(i);
        const got = readInline(r, i + width, end, [...stack, kind]);
        // In a live tail an opener closes provisionally at the end, unless it sits inside a word
        // ("2*3"): that reading is too unsure to style, so it waits for its closer like settled text.
        const provisional = r.open && !/[\p{L}\p{N}]/u.test(before ?? "");
        if (got.closed || provisional) {
          out.push({ kind, children: got.nodes });
        } else {
          // Never closed: the marker is literal and its words are ordinary.
          pushText(out, r, i, i + width);
          out.push(...got.nodes);
        }
        i = got.at;
        text = i;
        continue;
      }
      if (r.open && i + n === end) {
        // A marker run at the very tail is undecided until the next delta; it waits off screen.
        flush(i);
        return { nodes: out, at: end, closed: false };
      }
      i += n;
      continue;
    }

    if (c === "[") {
      const link = linkAt(r, i, end);
      if (link) {
        flush(i);
        const label = readInline({ ...r, open: false }, i + 1, link.labelEnd, []).nodes;
        out.push({ kind: "link", label, url: link.url });
        i = link.next;
        text = i;
        continue;
      }
    }

    i++;
  }
  flush(end);
  return { nodes: out, at: end, closed: false };
}

/** `[label](url)` at `i`; in a live tail, `[label](partial` reads as a link whose address is still arriving. */
function linkAt(r: Reader, i: number, end: number): { labelEnd: number; url: string; next: number } | null {
  const s = r.s;
  let k = i + 1;
  while (k < end && s[k] !== "]" && s[k] !== "[" && s[k] !== "\n") k += s[k] === "\\" ? 2 : 1;
  if (k >= end || s[k] !== "]" || s[k + 1] !== "(") return null;
  const labelEnd = k;
  let u = k + 2;
  // An address may hold balanced parentheses (a wiki page, "alert(1)"); the first unbalanced ")" ends it.
  let depth = 0;
  while (u < end && !isSpace(s[u]) && (s[u] !== ")" || depth > 0)) {
    if (s[u] === "(") depth++;
    else if (s[u] === ")") depth--;
    u++;
  }
  if (u < end && s[u] === ")") return { labelEnd, url: s.slice(k + 2, u), next: u + 1 };
  if (u === end && r.open) return { labelEnd, url: s.slice(k + 2, u), next: end };
  return null;
}

/** The inline nodes of a paragraph or a list item. `open` reads it as the live tail of a stream. */
export function parseInline(span: Span, open = false): Inline[] {
  const r = readerOf(span, open);
  return readInline(r, 0, r.s.length, []).nodes;
}

/**
 * Where each delta's words begin, snapped forward to a word start: a delta that begins inside a word
 * joins the span the word began in, so a word is never split between two reveals and nothing already
 * on screen is revealed twice. `marks` are the offsets at which each delta began, ascending.
 */
export function revealStarts(text: string, marks: readonly number[]): number[] {
  const out: number[] = [];
  marks.forEach((m, n) => {
    const limit = Math.min(marks[n + 1] ?? text.length, text.length);
    for (let j = m; j < limit; j++) {
      if (j === 0 || (isSpace(text[j - 1]) && !isSpace(text[j]))) {
        if (out[out.length - 1] !== j) out.push(j);
        return;
      }
    }
  });
  return out;
}
