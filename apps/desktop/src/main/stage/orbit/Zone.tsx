// A zone of the orbit and its chips. A chip is one piece in a cell that never changes: pink dot for
// the person's words, dashed violet for her pencil, a drawn border once inked. Pointing at a chip
// heats its links and opens its card (the shared PieceCard): ink it, or rub it out with undo.

import { memo, useState, type CSSProperties } from "react";
import type { DraftStep, SketchKind, SketchNode } from "../../../lib/contract";
import { PieceCard } from "../parts";
import { isPencil } from "../select";
import type { StageAction } from "../types";
import type { StageWords } from "../words";
import { cellAt, type Side, type ZoneGrid, type ZoneKey, type ZoneSplit } from "./place";
import { ORBIT_WORDS } from "./words";

// The winner's 16-unit glyphs (A/3), as paths drawn with the current colour.
const ICON: Record<SketchKind, string[]> = {
  source: ["M4 1.8h5.2L12.2 4.8v9.4H4z", "M9 1.8v3.2h3.2", "M6 8.2h4M6 10.8h4"],
  app: ["M4.2 3h7.6a2.2 2.2 0 0 1 2.2 2.2v5.6a2.2 2.2 0 0 1-2.2 2.2H4.2A2.2 2.2 0 0 1 2 10.8V5.2A2.2 2.2 0 0 1 4.2 3z", "M2 6.3h12"],
  step: ["M4.6 3.4L9.2 8l-4.6 4.6", "M9 3.4L13.6 8 9 12.6"],
  gate: ["M3.2 12.4l.7-2.8 6.4-6.4a1.5 1.5 0 012.1 2.1l-6.4 6.4z", "M2.6 14.4h7.2"],
  output: ["M2.6 9.6v3.2h10.8V9.6", "M8 2.6v7M5.2 6.9L8 9.7l2.8-2.8"],
  never: ["M8 2.1a5.9 5.9 0 1 1 0 11.8a5.9 5.9 0 1 1 0-11.8z", "M3.9 12.1l8.2-8.2"],
};
const TICK = "M3.4 8.6l3 3L12.6 4.8";

function Icon({ kind }: { kind: SketchKind }) {
  return (
    <svg className="ob-chip__ic" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      {ICON[kind].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

function Tick() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path className="ob-tick" pathLength={100} d={TICK} />
    </svg>
  );
}

export interface Cell {
  col: number;
  row: number;
  end: boolean;
}

/** How a chip is drawn this frame: arriving (and when), new, inked, reworded, pointed at. */
export interface ChipLook {
  /** Lands after this many ms (the reply's choreography); undefined when it did not just arrive. */
  landAt?: number;
  fresh?: boolean;
  inked?: boolean;
  changed?: boolean;
  /** "hot": pointed at; "near": linked to the one pointed at; "dim": something else is. */
  heat?: "hot" | "near" | "dim";
}

export interface ChipProps {
  node: SketchNode;
  side: Side;
  /** The cell, or null in a zone's "+n more" list. `end`: its card opens towards the zone's start. */
  cell: Cell | null;
  look: ChipLook;
  open: boolean;
  step: DraftStep;
  busy: boolean;
  dispatch: (a: StageAction) => void;
  onPoint: (id: string | null) => void;
  setRef?: (id: string, el: HTMLElement | null) => void;
  words: StageWords;
}

const sameCell = (a: Cell | null, b: Cell | null) => a === b || (!!a && !!b && a.col === b.col && a.row === b.row && a.end === b.end);
const sameChip = (a: ChipProps, b: ChipProps) =>
  (Object.keys(a) as (keyof ChipProps)[]).every((k) => (k === "cell" ? sameCell(a.cell, b.cell) : a[k] === b[k]));

/** One piece in its cell. Re-renders only when its node, its cell, its look or its card changes. */
export const Chip = memo(function Chip({ node, side, cell, look, open, step, busy, dispatch, onPoint, setRef, words }: ChipProps) {
  const pencil = isPencil(node);
  const shaping = step === "shape";
  const shown = open || look.heat === "hot";
  const style: CSSProperties & Record<string, string | number> = {};
  if (cell) {
    style.gridColumn = cell.col + 1;
    style.gridRow = cell.row + 1;
  }
  if (look.landAt !== undefined) style["--ob-delay"] = `${look.landAt}ms`;
  const who = node.origin === "you" ? words.yours : pencil ? words.hers : words.inked;
  return (
    <div
      ref={setRef ? (el) => setRef(node.id, el) : undefined}
      className="ob-chip"
      data-role="chip"
      data-node-id={node.id}
      data-kind={node.kind}
      data-state={node.confirmed ? "ink" : "pencil"}
      data-origin={node.origin}
      data-arriving={look.landAt !== undefined ? "true" : undefined}
      data-fresh={look.fresh ? "true" : undefined}
      data-inked={look.inked ? "true" : undefined}
      data-changed={look.changed ? "true" : undefined}
      data-heat={look.heat}
      data-end={cell?.end ? "true" : undefined}
      data-open={shown ? "true" : undefined}
      style={style}
      onPointerEnter={() => onPoint(node.id)}
      onPointerLeave={(e) => {
        if (!e.currentTarget.contains(document.activeElement)) onPoint(null);
      }}
      onFocus={() => onPoint(node.id)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) onPoint(null);
      }}
    >
      <svg className="ob-chip__draw" aria-hidden="true" focusable="false">
        <rect pathLength={100} />
      </svg>
      <span className="ob-chip__dot" aria-hidden="true" />
      <button
        type="button"
        className="ob-chip__body"
        aria-label={`${who}: ${node.label}`}
        aria-expanded={shown}
        title={node.detail ? `${node.label}. ${node.detail}` : node.label}
        onClick={() => dispatch(open ? { type: "close_card" } : { type: "open_card", node_id: node.id })}
      >
        <Icon kind={node.kind} />
        <span className="ob-chip__label" data-role="chip-label">
          {node.label}
        </span>
      </button>
      {pencil && shaping && (
        <button
          type="button"
          className="ob-chip__ink"
          aria-label={`${words.inkIt}: ${node.label}`}
          title={ORBIT_WORDS.keepInk}
          disabled={busy}
          onClick={() => dispatch({ type: "ink", node_ids: [node.id] })}
        >
          <Tick />
        </button>
      )}
      <span className="ob-chip__done" aria-hidden="true">
        <Tick />
      </span>
      {shown && (
        <div className="ob-chip__card" data-side={side}>
          <PieceCard
            node={node}
            step={step}
            busy={busy}
            onInk={(id) => dispatch({ type: "ink", node_ids: [id] })}
            onDrop={(id) => dispatch({ type: "drop", node_ids: [id] })}
            onClose={() => {
              dispatch({ type: "close_card" });
              onPoint(null);
            }}
            words={words}
          />
        </div>
      )}
    </div>
  );
}, sameChip);

export interface ZoneProps {
  zone: ZoneKey;
  side: Side;
  name: string;
  grid: ZoneGrid;
  split: ZoneSplit;
  nodes: ReadonlyMap<string, SketchNode>;
  looks: ReadonlyMap<string, ChipLook>;
  card: string | null;
  asked: boolean;
  lit: boolean;
  step: DraftStep;
  busy: boolean;
  dispatch: (a: StageAction) => void;
  onPoint: (id: string | null) => void;
  setChipRef: (id: string, el: HTMLElement | null) => void;
  setCellsRef: (zone: ZoneKey, el: HTMLElement | null) => void;
  words: StageWords;
}

const NO_LOOK: ChipLook = {};

/** One zone: its name, its cells, a "Not known yet" ghost while empty, and "+n more" past its room. */
export function Zone(p: ZoneProps) {
  const [listing, setListing] = useState(false);
  const { zone, side, name, grid, split } = p;
  const empty = !split.shown.length && !split.more.length;
  const cols = Number.isFinite(grid.capacity) ? grid.cols : 1;
  const style = { "--ob-cols": cols, "--ob-rows": grid.rows } as CSSProperties;
  const lower = zone === "inputs" || zone === "output";
  const at = (index: number): Cell => {
    const c = cellAt(index, cols);
    const end = side === "top" || side === "bottom" ? cols > 1 && c.col >= cols / 2 : lower && c.row >= grid.rows / 2;
    return { ...c, end };
  };
  const chip = (id: string, cell: Cell | null) => {
    const node = p.nodes.get(id);
    if (!node) return null;
    return (
      <Chip
        key={id}
        node={node}
        side={side}
        cell={cell}
        look={p.looks.get(id) ?? NO_LOOK}
        open={p.card === id}
        step={p.step}
        busy={p.busy}
        dispatch={p.dispatch}
        onPoint={p.onPoint}
        setRef={cell ? p.setChipRef : undefined}
        words={p.words}
      />
    );
  };
  return (
    <section
      className="ob-zone"
      data-role="zone"
      data-zone={zone}
      data-side={side}
      data-dense={grid.dense ? "true" : undefined}
      data-asked={p.asked ? "true" : undefined}
      data-lit={p.lit ? "true" : undefined}
      aria-label={name}
    >
      <h2 className="ob-zone__cap">
        <span className="ob-zone__name" data-role="zone-name">
          {name}
        </span>
      </h2>
      <div className="ob-zone__cells" ref={(el) => p.setCellsRef(zone, el)} style={style}>
        {empty && (
          <div className="ob-ghost" aria-hidden="true">
            <span>{ORBIT_WORDS.notKnown}</span>
          </div>
        )}
        {split.shown.map(([id, index]) => chip(id, at(index)))}
        {split.more.length > 0 && (
          <div
            className="ob-more"
            style={{ gridColumn: cellAt(split.moreAt, cols).col + 1, gridRow: cellAt(split.moreAt, cols).row + 1 }}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setListing(false);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape" && listing) {
                e.stopPropagation();
                setListing(false);
              }
            }}
          >
            <button type="button" className="ob-more__btn" aria-expanded={listing} onClick={() => setListing((x) => !x)}>
              {ORBIT_WORDS.more(split.more.length)}
            </button>
            {listing && (
              <div className="ob-more__list" role="group" aria-label={ORBIT_WORDS.moreTitle(name)} data-side={side}>
                {split.more.map((id) => chip(id, null))}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
