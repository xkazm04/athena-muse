// The page half of her browser (src-tauri/src/hands.js, ADR 0013) in jsdom: the deep walk through
// open shadow roots and same-origin frames, refs bound to their document, the nonce on every
// answer, and the one rule no signature lifts. WebView2 itself is measured by scripts/browser_seam.py.
import { readFileSync } from "node:fs";
import { beforeEach, describe, expect, it } from "vitest";

// Vitest runs from apps/desktop.
const SOURCE = readFileSync("src-tauri/src/hands.js", "utf-8");

interface Answer {
  ok: boolean;
  output: string;
  reason?: string;
}
type Hands = { run(id: string, name: string, input: unknown): void };
type Invoke = (cmd: string, args: { nonce: string; id: string; payload: Answer }) => Promise<void>;

const answers = new Map<string, { nonce: string; payload: Answer }>();
const invoke: Invoke = async (_cmd, args) => {
  answers.set(args.id, { nonce: args.nonce, payload: args.payload });
};

/** The script installs itself once per window (a second load is a no-op), as in a real tab. */
function load(): Hands {
  const w = window as unknown as { __TAURI_INTERNALS__: { invoke: Invoke }; __athenaHands?: Hands };
  w.__TAURI_INTERNALS__ = { invoke };
  if (!w.__athenaHands) new Function(SOURCE.replace("__ATHENA_NONCE__", "nonce-1"))();
  return w.__athenaHands as Hands;
}

async function ask(hands: Hands, name: string, input: unknown = {}): Promise<Answer> {
  const id = `call_${Math.random()}`;
  hands.run(id, name, input);
  for (let i = 0; i < 50 && !answers.has(id); i += 1) await new Promise((r) => setTimeout(r, 0));
  const got = answers.get(id);
  expect(got?.nonce).toBe("nonce-1");
  return got!.payload;
}

const refOf = (found: string, contains: string) =>
  found.split("\n").find((l) => l.startsWith("ref_") && l.includes(contains))?.split(/\s+/)[0] ?? "";

beforeEach(() => {
  document.body.innerHTML = "";
  // jsdom lays nothing out; every element has a box here so `shown` can be asked.
  Element.prototype.getBoundingClientRect = () => ({ width: 10, height: 10 }) as DOMRect;
});

describe("hands.js", () => {
  it("reads and finds through an open shadow root inside a same-origin frame", async () => {
    document.body.innerHTML = '<h1>Studio</h1><iframe id="f"></iframe>';
    const frame = document.getElementById("f") as HTMLIFrameElement;
    const frameWindow = frame.contentWindow as unknown as { Element: typeof Element };
    frameWindow.Element.prototype.getBoundingClientRect = () => ({ width: 10, height: 10 }) as DOMRect;
    const inner = frame.contentDocument!;
    inner.body.innerHTML = "<upload-dialog></upload-dialog>";
    const host = inner.querySelector("upload-dialog")!;
    const root = host.attachShadow({ mode: "open" });
    root.innerHTML =
      '<p>Select files to upload</p><input id="file" type="file" style="display:none">' +
      '<label><input type="radio" name="v" value="public"> Public</label><button>Save draft</button>';
    const hands = load();
    const read = await ask(hands, "page_read");
    expect(read.output).toContain("Studio");
    expect(read.output).toContain("Select files to upload");
    const found = await ask(hands, "page_find", { role: "file" });
    expect(found.output).toMatch(/^ref_\w+_\d+ {2}file {2}file/);
    const all = await ask(hands, "page_find", { query: "save" });
    expect(all.output).toContain("Save draft");
  });

  it("lists the page's links with their addresses, once each, and never a script link", async () => {
    document.body.innerHTML =
      '<a href="/watch?v=lt1">Night Ferry</a><a href="/watch?v=lt1">Night Ferry again</a>' +
      '<a href="javascript:void(0)">Menu</a><a href="mailto:a@b.example">Mail</a><a href="/videos">Videos</a>';
    const hands = load();
    const links = await ask(hands, "page_links");
    const rows = links.output.split("\n");
    expect(rows[0]).toMatch(/^Night Ferry {2}http.*\/watch\?v=lt1$/);
    expect(rows.filter((r: string) => r.includes("watch?v=lt1"))).toHaveLength(1);
    expect(links.output).not.toContain("javascript:");
    expect(links.output).not.toContain("mailto:");
    expect(links.output).toContain("(showing 2 of 2)");
  });

  it("refuses a Public control even when asked, and checks the label it was shown", async () => {
    document.body.innerHTML =
      '<label><input type="radio" name="v" value="public"> Public</label><button id="b">Comment</button>';
    const hands = load();
    const found = await ask(hands, "page_find");
    const pub = await ask(hands, "page_click", { ref: refOf(found.output, "Public") });
    expect(pub).toMatchObject({ ok: false, reason: "refused" });
    expect(pub.output).toContain("never makes anything public");
    const moved = await ask(hands, "page_click", { ref: refOf(found.output, "Comment"), expect: "Delete" });
    expect(moved).toMatchObject({ ok: false, reason: "moved" });
    let clicked = 0;
    document.getElementById("b")!.addEventListener("click", () => (clicked += 1));
    const ok = await ask(hands, "page_click", { ref: refOf(found.output, "Comment"), expect: "comment" });
    expect(ok.ok).toBe(true);
    expect(clicked).toBe(1);
  });

  it("fills through the prototype setter and refuses a ref from another document", async () => {
    document.body.innerHTML = '<textarea aria-label="Add a comment"></textarea>';
    const hands = load();
    const found = await ask(hands, "page_find", { query: "comment" });
    const ref = refOf(found.output, "Add a comment");
    let heard = "";
    document.querySelector("textarea")!.addEventListener("input", (e) => (heard = (e.target as HTMLTextAreaElement).value));
    expect((await ask(hands, "page_fill", { ref, expect: "Add a comment", value: "Lovely" })).ok).toBe(true);
    expect(heard).toBe("Lovely");
    const stale = await ask(hands, "page_click", { ref: "ref_ffffff_1" });
    expect(stale).toMatchObject({ ok: false, reason: "unknown_ref" });
    expect((await ask(hands, "no_such_hand")).reason).toBe("refused");
  });

  it("refuses an upload whose parts did not all arrive", async () => {
    document.body.innerHTML = '<input type="file" aria-label="Video file">';
    const hands = load() as Hands & { stage(id: string, i: number, b64: string, n: number): void };
    const found = await ask(hands, "page_find", { role: "file" });
    hands.stage("s1", 0, "AAAA", 2);
    const out = await ask(hands, "page_upload", { ref: refOf(found.output, "Video"), stage: "s1", name: "a.mp4", size: 3 });
    expect(out).toMatchObject({ ok: false, reason: "refused" });
    expect(out.output).toContain("did not arrive whole");
  });
});
