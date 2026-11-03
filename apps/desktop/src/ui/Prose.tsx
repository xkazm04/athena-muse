// Model-authored prose on screen: the one door (see markup.ts for what is read and why). Every string
// below reaches the page as a React text node; there is no innerHTML anywhere on this path, so text
// that looks like markup - a <script>, an <img onerror>, a style - is shown as the characters it is.

import { memo, useMemo, useRef, useState, type ReactNode } from "react";
import { parseInline, parseProse, revealStarts, type Block, type Inline, type Parsed } from "./markup";
import "./prose.css";

export interface ProseProps {
  text: string;
  /** Still streaming: the last block is read provisionally and newly arrived words fade in. */
  live?: boolean;
  /** Where each streamed delta began in `text`, ascending; read only while `live`. */
  marks?: readonly number[];
  className?: string;
}

const NONE: readonly number[] = [];

/** Rich text from a model or a playbook author, read as a safe markdown subset. */
export function Prose({ text, live = false, marks = NONE, className }: ProseProps) {
  // The previous reading is the checkpoint: a longer text re-reads only from its last block.
  const last = useRef<Parsed | null>(null);
  const parsed = useMemo(() => (last.current = parseProse(text, last.current)), [text]);
  const starts = useMemo(() => (live ? revealStarts(text, marks) : NONE), [live, text, marks]);
  const tail = parsed.blocks.length - 1;
  return (
    <div className={className ? `prose ${className}` : "prose"}>
      {parsed.blocks.map((block, n) => {
        const isTail = live && n === tail;
        return (
          <BlockView
            key={block.start}
            block={block}
            open={isTail}
            starts={isTail ? starts.filter((s) => s >= block.start) : NONE}
          />
        );
      })}
    </div>
  );
}

// A settled block keeps its object across deltas (markup.ts keeps every block before the last), so
// memo skips it: only the live tail re-renders as words arrive.
const BlockView = memo(function BlockView({ block, open, starts }: { block: Block; open: boolean; starts: readonly number[] }) {
  switch (block.kind) {
    case "code":
      return <CodeBlock text={block.text} lang={block.lang} />;
    case "p":
      return <p>{render(parseInline(block.body, open), starts)}</p>;
    case "h":
      // One emphasis level for every depth, and no size scale: a chat column is not a document.
      return (
        <p className="prose-h">
          <strong>{render(parseInline(block.body, open), starts)}</strong>
        </p>
      );
    case "list": {
      const items = block.items.map((item, n) => (
        <li key={n}>{render(parseInline(item, open && n === block.items.length - 1), starts)}</li>
      ));
      return block.ordered ? <ol start={block.first === 1 ? undefined : block.first}>{items}</ol> : <ul>{items}</ul>;
    }
  }
});

/** Inline nodes to elements. With reveal starts, each delta's words are their own span, keyed by
 *  where they begin, so a span mounts (and fades in) once and is never animated again. */
function render(nodes: Inline[], starts: readonly number[]): ReactNode[] {
  return nodes.map((node, n): ReactNode => {
    switch (node.kind) {
      case "text":
        return starts.length ? <Words key={`t${node.at}`} text={node.text} at={node.at} starts={starts} /> : node.text;
      case "br":
        return <br key={`b${n}`} />;
      case "code":
        return (
          <code key={`c${n}`} className="prose-ic">
            {node.text}
          </code>
        );
      case "strong":
        return <strong key={`s${n}`}>{render(node.children, starts)}</strong>;
      case "em":
        return <em key={`e${n}`}>{render(node.children, starts)}</em>;
      case "link":
        return <Link key={`l${n}`} label={render(node.label, NONE)} labelText={plain(node.label)} url={node.url} />;
    }
  });
}

function Words({ text, at, starts }: { text: string; at: number; starts: readonly number[] }) {
  const end = at + text.length;
  const cuts = [at, ...starts.filter((s) => s > at && s < end), end];
  const parts: ReactNode[] = [];
  for (let k = 0; k + 1 < cuts.length; k++) {
    const a = cuts[k]!;
    parts.push(
      <span key={a} className="prose-new">
        {text.slice(a - at, cuts[k + 1]! - at)}
      </span>,
    );
  }
  return <>{parts}</>;
}

const plain = (nodes: Inline[]): string =>
  nodes.map((n) => (n.kind === "text" || n.kind === "code" ? n.text : n.kind === "br" ? " " : n.kind === "link" ? plain(n.label) : plain(n.children))).join("");

/**
 * A link is shown, not followed. The words and the address are both model-authored, and a label that
 * names one place while the address goes to another is the phishing shape; so the label is text and
 * the true address stands beside it in full, for the person to copy if they choose. Nothing a model
 * writes becomes something to click.
 */
function Link({ label, labelText, url }: { label: ReactNode[]; labelText: string; url: string }) {
  if (!url || labelText.trim() === url) {
    return <span className="prose-link">{url ? <span className="prose-url">{url}</span> : label}</span>;
  }
  return (
    <span className="prose-link">
      {label}
      <span className="prose-url"> ({url})</span>
    </span>
  );
}

function CodeBlock({ text, lang }: { text: string; lang: string }) {
  const [copied, setCopied] = useState<boolean | null>(null);
  const copy = () => {
    // The source text exactly; no clipboard (an insecure origin) or a refusal is said, never silent.
    const write = navigator.clipboard?.writeText(text) ?? Promise.reject(new Error("no clipboard"));
    void write.then(
      () => setCopied(true),
      () => setCopied(false),
    );
  };
  return (
    <div className="prose-code">
      <div className="prose-code__bar">
        {/* the label is model-authored too: a hint, shown as text, never trusted */}
        <span className="prose-code__lang">{lang}</span>
        <button type="button" className="btn btn-quiet prose-code__copy" onClick={copy}>
          {copied === true ? "Copied" : copied === false ? "Could not copy" : "Copy"}
        </button>
      </div>
      <pre>
        <code>{text}</code>
      </pre>
    </div>
  );
}
