// The drawing itself (A/1): the person's sentence on top, five territories with the pieces in their
// rows and the links routed through the gutters, and the fence for "never" below. A piece is drawn at
// the place the store keeps for it; pointing at one heats its links and dims the rest.

import { memo, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import type { Coverage, DraftStep, Sketch as SketchData, SketchNode } from "../../../lib/contract";
import { KindGlyph, NeedSentence, PieceCard } from "../parts";
import { isPencil, needMarks, type Overlay } from "../select";
import type { Place, StageAction } from "../types";
import type { StageWords } from "../words";
import { FENCE, LANES, TIGHT_ROWS, boxOf, densityOf, pathFor, type LaneBox, type Layout } from "./place";
import { DRAWING_WORDS as dw } from "./words";

/** A/1's motion: pieces 170 ms apart, then the links 110 ms apart once the pieces are in. */
export const PIECE_STAGGER_MS = 170;
export const LINK_STAGGER_MS = 110;
const FIRST_MS = 40;

/** The gap between rows, px: 7, or 4 once the lanes are tight (A/1 `--pgap`). */
export const gapOf = (tight: boolean) => (tight ? 4 : 7);

interface Geometry {
  lanes: LaneBox[];
}
const NO_GEOMETRY: Geometry = { lanes: [] };
const sameGeometry = (a: Geometry, b: Geometry) =>
  a.lanes.length === b.lanes.length &&
  a.lanes.every((l, i) => {
    const m = b.lanes[i]!;
    return l.x === m.x && l.top === m.top && l.w === m.w && l.h === m.h;
  });

const vars = (v: Record<string, string | number>) => v as CSSProperties;

export interface SketchProps {
  need: string;
  /** The sketch as drawn (pieces being rubbed out are hidden). */
  sketch: SketchData;
  coverage: Coverage;
  lay: Layout;
  overlay: Overlay;
  /** Links that arrived in the last reply ("from>to"). */
  newLinks: ReadonlySet<string>;
  step: DraftStep;
  /** The lane she is asking about, while the question is open. */
  asking: string | null;
  /** One faint slot where her answer will land, while she thinks. */
  ghost: Place | null;
  card: string | null;
  busy: boolean;
  dispatch: (action: StageAction) => void;
  words: StageWords;
  /** What sits beside the person's sentence: the revisit banner, her pencil count, the project. */
  side: ReactNode;
}

export function Sketch(props: SketchProps) {
  const { need, sketch, coverage, lay, overlay, newLinks, step, asking, ghost, card, busy, dispatch, words, side } = props;
  const [focus, setFocus] = useState<string | null>(null);
  const lanesRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const bodies = useRef<(HTMLDivElement | null)[]>([]);
  const [geom, setGeom] = useState<Geometry>(NO_GEOMETRY);
  const arrow = useId().replace(/:/g, "");
  const tight = lay.rows > TIGHT_ROWS;
  const gap = gapOf(tight);
  const density = densityOf(geom.lanes[0]?.h ?? 0, lay.rows, gap);
  const shaping = step === "shape";

  // The lanes' boxes, read when the window (or what sits above and below the lanes) changes size.
  useLayoutEffect(() => {
    const el = lanesRef.current;
    if (!el) return;
    const measure = () => {
      const at = el.getBoundingClientRect();
      const lanes = bodies.current.slice(0, LANES.length).map((b) => {
        const r = b?.getBoundingClientRect();
        return r ? { x: r.left - at.left, top: r.top - at.top, w: r.width, h: r.height } : { x: 0, top: 0, w: 0, h: 0 };
      });
      const next = { lanes };
      setGeom((prev) => (sameGeometry(prev, next) ? prev : next));
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // A detail line that cannot be shown whole is hidden, never cut (it stays in the title and the card).
  useLayoutEffect(() => {
    const root = mapRef.current;
    if (!root) return;
    for (const el of root.querySelectorAll<HTMLElement>('[data-role="piece"]')) {
      const d = el.querySelector<HTMLElement>(".dr-piece__detail");
      if (!d) continue;
      delete el.dataset.cut;
      if (d.scrollWidth > d.clientWidth + 1 || d.scrollHeight > d.clientHeight + 1) el.dataset.cut = "true";
    }
  }, [sketch, geom, density, tight]);

  const byLane = useMemo(() => {
    const out = new Map<string, SketchNode[]>();
    for (const n of sketch.nodes) {
      const p = lay.places[n.id];
      if (!p) continue;
      out.set(p.area, [...(out.get(p.area) ?? []), n]);
    }
    const fence = out.get(FENCE);
    if (fence) fence.sort((a, b) => lay.places[a.id]!.index - lay.places[b.id]!.index);
    return out;
  }, [sketch, lay]);

  // Arrival order of the last reply's pieces, and the links' start once the pieces are in.
  const arrival = useMemo(() => {
    const order = new Map<string, number>();
    for (const n of sketch.nodes) if (overlay.added.has(n.id) && lay.places[n.id]) order.set(n.id, FIRST_MS + order.size * PIECE_STAGGER_MS);
    return { order, links: FIRST_MS + order.size * PIECE_STAGGER_MS + 200 };
  }, [sketch, overlay, lay]);

  const confirmed = useMemo(() => new Set(sketch.nodes.filter((n) => n.confirmed).map((n) => n.id)), [sketch]);
  const links = useMemo(() => {
    let fresh = 0;
    return sketch.edges.flatMap((e) => {
      const a = boxOf(lay.places[e.from], geom.lanes, lay.rows, gap);
      const b = boxOf(lay.places[e.to], geom.lanes, lay.rows, gap);
      if (!a || !b) return [];
      const key = `${e.from}>${e.to}`;
      const isNew = newLinks.has(key);
      return [
        {
          key,
          from: e.from,
          to: e.to,
          d: pathFor(a, b, geom.lanes, lay.rows, gap),
          ink: confirmed.has(e.from) && confirmed.has(e.to),
          delay: isNew ? arrival.links + fresh++ * LINK_STAGGER_MS : null,
        },
      ];
    });
  }, [sketch, lay, geom, gap, newLinks, confirmed, arrival]);

  const related = useMemo(() => {
    if (!focus) return null;
    const out = new Set<string>([focus]);
    for (const e of sketch.edges) {
      if (e.from === focus) out.add(e.to);
      if (e.to === focus) out.add(e.from);
    }
    return out;
  }, [focus, sketch]);

  const piece = (n: SketchNode, lane: number) => {
    const p = lay.places[n.id]!;
    return (
      <Piece
        key={n.id}
        node={n}
        row={p.area === FENCE ? null : p.index}
        delay={arrival.order.get(n.id) ?? null}
        inking={overlay.inked.has(n.id)}
        rewrite={overlay.changed.has(n.id)}
        related={related ? related.has(n.id) && n.id !== focus : false}
        open={card === n.id}
        side={p.area === FENCE ? "up" : lane >= 3 ? "left" : "right"}
        low={p.area !== FENCE && p.index >= lay.rows / 2}
        shaping={shaping}
        step={step}
        busy={busy}
        dispatch={dispatch}
        onPoint={setFocus}
        words={words}
      />
    );
  };

  const marks = useMemo(() => needMarks(need, sketch.nodes), [need, sketch]);
  const fence = byLane.get(FENCE) ?? [];
  return (
    <div
      className="dr-map"
      ref={mapRef}
      data-focus={focus ? "true" : undefined}
      data-density={density}
      data-tight={tight ? "true" : undefined}
      style={vars({ "--dr-rows": lay.rows, "--dr-pgap": `${gap}px` })}
      onPointerDown={(e) => {
        if (card && !(e.target as HTMLElement).closest('[data-role="piece"]')) dispatch({ type: "close_card" });
      }}
    >
      <div className="dr-headline">
        <div className="dr-need">
          <NeedSentence need={need} marks={marks} words={words} onPoint={setFocus} />
        </div>
        <div className="dr-side">{side}</div>
      </div>

      <div className="dr-lanes" ref={lanesRef}>
        <svg className="dr-links" aria-hidden="true" focusable="false">
          <defs>
            {(["ink", "pencil"] as const).map((k) => (
              <marker key={k} id={`${arrow}-${k}`} viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M0 1L10 5L0 9z" className={`dr-arrow dr-arrow--${k}`} />
              </marker>
            ))}
          </defs>
          {links.map((l) => (
            <path
              key={l.key}
              className={`dr-link dr-link--${l.ink ? "ink" : "pencil"}`}
              d={l.d}
              markerEnd={`url(#${arrow}-${l.ink ? "ink" : "pencil"})`}
              data-hot={focus && (l.from === focus || l.to === focus) ? "true" : undefined}
              data-arrive={l.delay !== null ? "true" : undefined}
              style={l.delay !== null ? vars({ "--dr-delay": `${l.delay}ms` }) : undefined}
            />
          ))}
        </svg>
        {LANES.map((slot, i) => {
          const nodes = byLane.get(slot) ?? [];
          return (
            <section
              key={slot}
              className="dr-lane"
              data-role="lane"
              data-slot={slot}
              data-asking={asking === slot ? "true" : undefined}
              data-open={nodes.some((n) => n.id === card) ? "true" : undefined}
              aria-label={words.slot[slot]}
            >
              <div className="dr-lane__bg" aria-hidden="true" />
              <h3 className="dr-lane__head" data-role="lane-head">
                <Coverage value={coverage[slot]} />
                <span className="dr-lane__title">{words.slot[slot]}</span>
                <span className="dr-lane__count">{nodes.length}</span>
              </h3>
              <div
                className="dr-lane__body"
                ref={(el) => {
                  bodies.current[i] = el;
                }}
              >
                {nodes.map((n) => piece(n, i))}
                {ghost && ghost.area === slot && <div className="dr-ghost-piece" aria-hidden="true" style={vars({ "--row": ghost.index })} />}
                {!nodes.length && !(ghost && ghost.area === slot) && (
                  <p className="dr-lane__empty">{slot === "hand" ? dw.handEmpty : dw.laneEmpty}</p>
                )}
              </div>
            </section>
          );
        })}
      </div>

      <section
        className="dr-fence"
        data-role="never-fence"
        data-asking={asking === FENCE ? "true" : undefined}
        data-open={fence.some((n) => n.id === card) ? "true" : undefined}
        aria-label={words.slot.never}
      >
        <h3 className="dr-fence__label">
          <KindGlyph kind="never" />
          <span>{words.slot.never}</span>
          <Coverage value={coverage.never} />
        </h3>
        <div className="dr-fence__items">
          {fence.map((n) => piece(n, -1))}
          {ghost && ghost.area === FENCE && <div className="dr-ghost-piece dr-ghost-piece--fence" aria-hidden="true" />}
          {!fence.length && !(ghost && ghost.area === FENCE) && <p className="dr-fence__empty">{dw.fenceEmpty}</p>}
        </div>
      </section>
    </div>
  );
}

/** How much she knows about a territory: an empty dashed ring, half, or inked. */
function Coverage({ value }: { value: Coverage[keyof Coverage] }) {
  return <span className="dr-cov" data-v={String(value)} title={dw.laneCovered[value]} aria-hidden="true" />;
}

interface PieceProps {
  node: SketchNode;
  /** Its row in the lane, or null in the fence. */
  row: number | null;
  /** When it arrives (ms), if it arrived in the last reply. */
  delay: number | null;
  inking: boolean;
  rewrite: boolean;
  related: boolean;
  open: boolean;
  /** Where its card opens: beside it, to the left in the last lanes, above it in the fence. */
  side: "right" | "left" | "up";
  low: boolean;
  shaping: boolean;
  step: DraftStep;
  busy: boolean;
  dispatch: (action: StageAction) => void;
  onPoint: (id: string | null) => void;
  words: StageWords;
}

/** One piece: dashed violet while it is her pencil, solid once inked, a pink edge when it is the person's. */
const Piece = memo(function Piece(p: PieceProps) {
  const { node, row, delay, inking, rewrite, related, open, side, low, shaping, step, busy, dispatch, onPoint, words } = p;
  const pencil = isPencil(node);
  const hit = useRef<HTMLButtonElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  // the card takes focus when it opens, and gives it back to its piece when it closes
  useEffect(() => {
    if (!open) return;
    cardRef.current?.querySelector("button")?.focus({ preventScroll: true });
    const back = hit.current;
    return () => {
      if (!document.activeElement || document.activeElement === document.body) back?.focus({ preventScroll: true });
    };
  }, [open]);
  const who = node.origin === "you" ? dw.you : dw.her;
  const label = dw.pieceKind(words.kind[node.kind], node.label, node.detail, who, node.confirmed ? dw.inInk : dw.inPencil);
  const style: Record<string, string | number> = {};
  if (row !== null) style["--row"] = row;
  if (delay !== null) style["--dr-delay"] = `${delay}ms`;
  return (
    <div
      className="dr-piece"
      data-role="piece"
      data-node-id={node.id}
      data-kind={node.kind}
      data-state={node.confirmed ? "ink" : "pencil"}
      data-origin={node.origin}
      data-fence={row === null ? "true" : undefined}
      data-detail={node.detail ? "true" : undefined}
      data-arrive={delay !== null ? "true" : undefined}
      data-inking={inking ? "true" : undefined}
      data-rewrite={rewrite ? "true" : undefined}
      data-related={related ? "true" : undefined}
      data-open={open ? "true" : undefined}
      style={vars(style)}
      onPointerEnter={() => onPoint(node.id)}
      onPointerLeave={() => onPoint(null)}
    >
      <button
        ref={hit}
        type="button"
        className="dr-piece__hit"
        aria-label={label}
        aria-expanded={open}
        title={node.detail ? `${node.label} (${node.detail})` : node.label}
        onClick={() => dispatch(open ? { type: "close_card" } : { type: "open_card", node_id: node.id })}
        onFocus={() => onPoint(node.id)}
        onBlur={() => onPoint(null)}
      />
      <span className="dr-piece__glyph">
        <KindGlyph kind={node.kind} />
      </span>
      <span className="dr-piece__text">
        <span className="dr-piece__label" data-role="piece-label">
          {node.label}
        </span>
        {node.detail && <span className="dr-piece__detail">{node.detail}</span>}
      </span>
      {pencil && shaping && (
        <button
          type="button"
          className="dr-piece__ink"
          data-role="piece-ink"
          tabIndex={-1}
          aria-label={dw.inkThis(node.label)}
          title={dw.inkThis(node.label)}
          disabled={busy}
          onClick={() => dispatch({ type: "ink", node_ids: [node.id] })}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        </button>
      )}
      {open && (
        <div className="dr-piece__card" ref={cardRef} data-side={side} data-low={low ? "true" : undefined}>
          <PieceCard
            node={node}
            step={step}
            busy={busy}
            onInk={(id) => dispatch({ type: "ink", node_ids: [id] })}
            onDrop={(id) => dispatch({ type: "drop", node_ids: [id] })}
            onClose={() => dispatch({ type: "close_card" })}
            words={words}
          />
        </div>
      )}
    </div>
  );
});
