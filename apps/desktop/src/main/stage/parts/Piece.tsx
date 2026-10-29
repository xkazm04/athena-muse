// The sketch's shared parts: the person's sentence with their phrases marked, kind labels, a piece's
// card (detail, ink, drop) and the undo toast. Neutral markup; each view skins it under its root.

import type { ReactNode } from "react";
import type { DraftStep, SketchKind, SketchNode } from "../../../lib/contract";
import { isPencil, type NeedMark } from "../select";
import type { StageWords } from "../words";

// The winners' glyphs (A/1), as paths on a 24-unit grid, drawn with the current colour.
const GLYPH: Record<SketchKind, string[]> = {
  app: ["M3 5h18v14H3z", "M3 9.5h18"],
  source: ["M7 3h7l4 4v14H7z", "M14 3v4h4", "M10 12h5M10 16h5"],
  step: ["M5 6l6 6-6 6", "M13 6l6 6-6 6"],
  gate: ["M4 20l3.6-1L19 7.6a2.1 2.1 0 00-3-3L4.6 16z", "M13.6 6.8l3 3"],
  output: ["M4 13l2-8h12l2 8", "M4 13h5l1 2.2h4L15 13h5v6H4z"],
  never: ["M12 3.5a8.5 8.5 0 1 1 0 17a8.5 8.5 0 1 1 0-17z", "M6 18L18 6"],
};

export function KindGlyph({ kind }: { kind: SketchKind }) {
  return (
    <svg className="sp-glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {GLYPH[kind].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

/** What a piece is, in plain words, with its glyph. */
export function KindLabel({ kind, words }: { kind: SketchKind; words: StageWords }) {
  return (
    <span className="sp-kind" data-role="kind" data-kind={kind}>
      <KindGlyph kind={kind} />
      {words.kind[kind]}
    </span>
  );
}

export interface NeedSentenceProps {
  need: string;
  marks: readonly NeedMark[];
  words: StageWords;
  /** Pointing at a phrase points at its piece (the views heat its links). */
  onPoint?: (nodeId: string | null) => void;
}

/** The person's sentence on top, the phrases she drew as their pieces marked in their colour. */
export function NeedSentence({ need, marks, words, onPoint }: NeedSentenceProps) {
  const parts: ReactNode[] = [];
  let at = 0;
  for (const m of marks) {
    if (m.start > at) parts.push(need.slice(at, m.start));
    parts.push(
      <mark
        key={m.node_id}
        className="sp-need__mark"
        data-role="need-phrase"
        data-node-id={m.node_id}
        tabIndex={onPoint ? 0 : undefined}
        onPointerEnter={onPoint && (() => onPoint(m.node_id))}
        onPointerLeave={onPoint && (() => onPoint(null))}
        onFocus={onPoint && (() => onPoint(m.node_id))}
        onBlur={onPoint && (() => onPoint(null))}
      >
        {need.slice(m.start, m.end)}
      </mark>,
    );
    at = m.end;
  }
  if (at < need.length) parts.push(need.slice(at));
  return (
    <figure className="sp-need" data-role="need">
      <figcaption className="sp-need__label">{words.slot.need}</figcaption>
      <blockquote className="sp-need__text" title={need}>
        {parts}
      </blockquote>
    </figure>
  );
}

export interface PieceCardProps {
  node: SketchNode;
  step: DraftStep;
  /** Busy: a reply or another act is in flight, so ink and drop wait. */
  busy?: boolean;
  onInk: (id: string) => void;
  onDrop: (id: string) => void;
  onClose: () => void;
  words: StageWords;
}

/** A piece's card: what it is, whose idea, and (for her pencil) ink it or rub it out. */
export function PieceCard({ node, step, busy = false, onInk, onDrop, onClose, words }: PieceCardProps) {
  const pencil = isPencil(node);
  const shaping = step === "shape";
  const who = node.origin === "you" ? words.youWrote : node.confirmed ? words.herInked : words.herGuess;
  return (
    <div
      className="sp-card"
      role="dialog"
      aria-label={node.label}
      data-role="piece-card"
      data-node-id={node.id}
      data-state={node.confirmed ? "ink" : "pencil"}
      data-origin={node.origin}
    >
      <KindLabel kind={node.kind} words={words} />
      <p className="sp-card__label">{node.label}</p>
      {node.detail && <p className="sp-card__detail">{node.detail}</p>}
      <p className="sp-card__who" data-origin={node.origin}>
        <i aria-hidden="true" />
        {who}
      </p>
      <div className="sp-card__actions">
        {pencil && shaping && (
          <button type="button" className="btn btn-primary" data-role="ink" disabled={busy} onClick={() => onInk(node.id)}>
            {words.inkIt}
          </button>
        )}
        {pencil && shaping && (
          <button type="button" className="btn" data-role="drop" disabled={busy} onClick={() => onDrop(node.id)}>
            {words.dropIt}
          </button>
        )}
        <button type="button" className="btn btn-quiet" onClick={onClose}>
          {words.close}
        </button>
      </div>
    </div>
  );
}

export interface UndoToastProps {
  /** The labels of the pieces being rubbed out; the toast shows while there are any. */
  labels: readonly string[];
  onUndo: () => void;
  words: StageWords;
}

/** "Rubbed out ..." with Undo, while the drop waits its five seconds. */
export function UndoToast({ labels, onUndo, words }: UndoToastProps) {
  if (!labels.length) return null;
  return (
    <div className="sp-toast" role="status" data-role="toast">
      <span>
        {words.rubbedOut} {labels.map((l) => `"${l}"`).join(", ")}.
      </span>
      <button type="button" className="btn" data-role="undo" onClick={onUndo}>
        {words.undo}
      </button>
    </div>
  );
}
