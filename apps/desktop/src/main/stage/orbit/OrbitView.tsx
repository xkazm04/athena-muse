// The Orbit view: a port of the contest's A/3 "Orbit" (WP3-3). The question card is the centre and
// the largest thing on screen; what she has understood circles it in six zones (steps on top, where
// it happens and what she reads on the left, the signature and what you get on the right, never
// below). Seven arcs hugging the card show coverage (read from the draft); links route round the
// card and stay faint until a piece is pointed at. The view holds no model: places go to the store
// through `place`, and everything it shows is read from the props.

import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { CoverageValue, SketchNode, Slot } from "../../../lib/contract";
import { needMarks, overlayOf, shownSketch } from "../select";
import type { StageViewProps } from "../types";
import { ringArcs, routeAll, type Box, type LinkIn } from "./geometry";
import { countsBySlot, Hub } from "./Hub";
import { gridFor, placesFor, SIDE_OF, splitZone, unsaved, ZONES, type ZoneBox, type ZoneGrid, type ZoneKey, type ZoneSplit } from "./place";
import { ORBIT_WORDS } from "./words";
import { Zone, type ChipLook } from "./Zone";
import "./orbit.css";

/** The reply's choreography (ms), from the winner: phrases light, fly, pieces land, links draw. */
export const MOTION = {
  highlightAt: 380,
  highlightEach: 460,
  fly: 720,
  landEach: 110,
  linksAfter: 140,
  linkEach: 90,
} as const;

interface Geo {
  w: number;
  h: number;
  hub: Box;
  chips: Record<string, Box>;
  /** The gap between lanes round the card, from the moat's width. */
  lane: number;
}

interface Flight {
  id: string;
  text: string;
  box: Box;
  dx: number;
  dy: number;
  s: number;
}

const near = (a: number, b: number) => Math.abs(a - b) < 0.5;
const sameBox = (a: Box | undefined, b: Box | undefined) =>
  !!a && !!b && near(a.x, b.x) && near(a.y, b.y) && near(a.w, b.w) && near(a.h, b.h);

function sameGeo(a: Geo | null, b: Geo): boolean {
  if (!a || !near(a.w, b.w) || !near(a.h, b.h) || !near(a.lane, b.lane) || !sameBox(a.hub, b.hub)) return false;
  const ka = Object.keys(a.chips);
  if (ka.length !== Object.keys(b.chips).length) return false;
  return ka.every((k) => sameBox(a.chips[k], b.chips[k]));
}

function sameBoxes(a: Partial<Record<ZoneKey, ZoneBox>>, b: Partial<Record<ZoneKey, ZoneBox>>): boolean {
  return ZONES.every(({ key }) => {
    const x = a[key];
    const y = b[key];
    if (!x || !y) return x === y;
    return (Object.keys(x) as (keyof ZoneBox)[]).every((k) => near(x[k], y[k]));
  });
}

/** An element's layout box inside `root`, by offsets (a chip mid-landing still reports its cell). */
function offsetBox(el: HTMLElement, root: HTMLElement): Box {
  let x = 0;
  let y = 0;
  let e: HTMLElement | null = el;
  while (e && e !== root) {
    x += e.offsetLeft;
    y += e.offsetTop;
    e = e.offsetParent as HTMLElement | null;
  }
  return { x, y, w: el.offsetWidth, h: el.offsetHeight };
}

const px = (style: CSSStyleDeclaration, name: string) => parseFloat(style.getPropertyValue(name)) || 0;

export function OrbitView({ draft, frame, state, dispatch, words, place }: StageViewProps) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const step = draft.step;
  const shaping = step === "describe" || step === "shape";
  const busy = !!state.work || frame.phase === "sending" || frame.phase === "thinking" || frame.phase === "slow";

  // ---- the model, as drawn -------------------------------------------------------------------
  const sketch = useMemo(() => shownSketch(draft.sketch, state.dropping), [draft.sketch, state.dropping]);
  const memo = state.places.orbit;
  const places = useMemo(() => placesFor(draft.sketch.nodes, memo), [draft.sketch.nodes, memo]);
  useLayoutEffect(() => {
    for (const [id, p] of unsaved(places, memo)) place("orbit", id, p);
  }, [places, memo, place]);

  const nodes = useMemo(() => new Map<string, SketchNode>(sketch.nodes.map((n) => [n.id, n])), [sketch.nodes]);
  const overlay = useMemo(() => overlayOf(frame, state.inked), [frame, state.inked]);
  const marks = useMemo(() => needMarks(draft.need, sketch.nodes), [draft.need, sketch.nodes]);
  const counts = useMemo(() => countsBySlot(sketch.nodes), [sketch.nodes]);

  // ---- measuring ----------------------------------------------------------------------------
  const stageRef = useRef<HTMLDivElement>(null);
  const chipEls = useRef(new Map<string, HTMLElement>());
  const cellsEls = useRef(new Map<ZoneKey, HTMLElement>());
  const setChipRef = useCallback((id: string, el: HTMLElement | null) => {
    if (el) chipEls.current.set(id, el);
    else chipEls.current.delete(id);
  }, []);
  const setCellsRef = useCallback((zone: ZoneKey, el: HTMLElement | null) => {
    if (el) cellsEls.current.set(zone, el);
    else cellsEls.current.delete(zone);
  }, []);
  const [boxes, setBoxes] = useState<Partial<Record<ZoneKey, ZoneBox>>>({});
  const [geo, setGeo] = useState<Geo | null>(null);

  const measure = useCallback(() => {
    const root = stageRef.current;
    if (!root || !root.clientWidth) return;
    const nextBoxes: Partial<Record<ZoneKey, ZoneBox>> = {};
    for (const [zone, el] of cellsEls.current) {
      const cs = getComputedStyle(el);
      nextBoxes[zone] = {
        w: el.clientWidth,
        h: el.clientHeight,
        chipW: px(cs, "--ob-chip-min"),
        chipH: px(cs, "--ob-cell-h"),
        gap: px(cs, "--ob-gap"),
        lineH: px(cs, "--ob-line-h"),
        lineGap: px(cs, "--ob-line-gap"),
      };
    }
    setBoxes((prev) => (sameBoxes(prev, nextBoxes) ? prev : nextBoxes));
    const hubEl = root.querySelector<HTMLElement>('[data-role="hub"]');
    const chips: Record<string, Box> = {};
    for (const [id, el] of chipEls.current) chips[id] = offsetBox(el, root);
    const moat = parseFloat(getComputedStyle(root).columnGap) || 28;
    const next: Geo = {
      w: root.clientWidth,
      h: root.clientHeight,
      hub: hubEl ? offsetBox(hubEl, root) : { x: 0, y: 0, w: 0, h: 0 },
      chips,
      lane: Math.max(1.5, Math.min(3.4, (moat - 17) / 4)),
    };
    setGeo((prev) => (sameGeo(prev, next) ? prev : next));
  }, []);

  // Read the layout after every render (a setState only when something moved), on resize, and
  // once the type has loaded.
  useLayoutEffect(measure);
  useEffect(() => {
    const root = stageRef.current;
    if (!root || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => measure());
    ro.observe(root);
    void document.fonts?.ready.then(() => measure());
    return () => ro.disconnect();
  }, [measure]);

  // ---- zones ---------------------------------------------------------------------------------
  const zones = useMemo(() => {
    const out = {} as Record<ZoneKey, { grid: ZoneGrid; split: ZoneSplit }>;
    for (const { key } of ZONES) {
      const cells: [string, number][] = [];
      for (const n of sketch.nodes) {
        const p = places[n.id];
        if (n.slot === key && p) cells.push([n.id, p.index]);
      }
      const last = cells.reduce((m, [, i]) => Math.max(m, i), -1);
      const grid = gridFor(boxes[key], last);
      out[key] = { grid, split: splitZone(cells, grid) };
    }
    return out;
  }, [sketch.nodes, places, boxes]);

  // ---- the reply's choreography: phrases light and fly, pieces land, links draw --------------
  const [hot, setHot] = useState<string | null>(null);
  const flyIds = useMemo(() => marks.filter((m) => overlay.added.has(m.node_id)).map((m) => m.node_id), [marks, overlay]);
  const landFrom = flyIds.length ? MOTION.highlightAt + MOTION.highlightEach * flyIds.length + MOTION.fly : 0;
  const arrivals = useMemo(() => {
    const added = sketch.nodes.filter((n) => overlay.added.has(n.id) && n.slot !== "need");
    added.sort((a, b) => Number(b.origin === "you") - Number(a.origin === "you"));
    return new Map(added.map((n, i) => [n.id, landFrom + i * MOTION.landEach]));
  }, [sketch.nodes, overlay, landFrom]);
  const newLinks = useMemo(() => {
    const keys = frame.lastOps.filter((o) => o.op === "link" && o.edge).map((o) => `${o.edge!.from}>${o.edge!.to}`);
    const at = landFrom + arrivals.size * MOTION.landEach + MOTION.linksAfter;
    return new Map(keys.map((k, i) => [k, at + i * MOTION.linkEach]));
  }, [frame.lastOps, landFrom, arrivals]);

  const neighbours = useMemo(() => {
    const out = new Set<string>();
    if (!hot) return out;
    for (const e of sketch.edges) {
      if (e.from === hot) out.add(e.to);
      if (e.to === hot) out.add(e.from);
    }
    return out;
  }, [hot, sketch.edges]);

  // One shared look object per distinct look, so a chip re-renders only when its own look changes.
  const lookCache = useRef(new Map<string, ChipLook>());
  const looks = useMemo(() => {
    const out = new Map<string, ChipLook>();
    for (const n of sketch.nodes) {
      const look: ChipLook = {
        landAt: arrivals.get(n.id),
        fresh: overlay.added.has(n.id) || undefined,
        inked: overlay.inked.has(n.id) || undefined,
        changed: overlay.changed.has(n.id) || undefined,
        heat: hot ? (n.id === hot ? "hot" : neighbours.has(n.id) ? "near" : "dim") : undefined,
      };
      const key = `${look.landAt}|${look.fresh}|${look.inked}|${look.changed}|${look.heat}`;
      let shared = lookCache.current.get(key);
      if (!shared) lookCache.current.set(key, (shared = look));
      out.set(n.id, shared);
    }
    return out;
  }, [sketch.nodes, arrivals, overlay, hot, neighbours]);

  // ---- links and the ring ---------------------------------------------------------------------
  const routes = useMemo(() => {
    if (!geo) return new Map<string, { d: string; len: number }>();
    const list: LinkIn[] = [];
    for (const e of sketch.edges) {
      const a = nodes.get(e.from);
      const b = nodes.get(e.to);
      const ba = geo.chips[e.from];
      const bb = geo.chips[e.to];
      if (!a || !b || !ba || !bb || a.slot === "need" || b.slot === "need") continue;
      list.push({ key: `${e.from}>${e.to}`, from: { box: ba, side: SIDE_OF[a.slot] }, to: { box: bb, side: SIDE_OF[b.slot] } });
    }
    return routeAll(list, geo.hub, geo.lane);
  }, [geo, sketch.edges, nodes]);
  const arcs = useMemo(() => (geo ? ringArcs(geo.hub) : []), [geo]);
  const [lit, setLit] = useState<Slot | null>(null);
  const litArc = arcs.find((a) => a.slot === lit);

  // ---- flights: the person's phrases travel to the pieces they became -------------------------
  const [flights, setFlights] = useState<Flight[]>([]);
  const flownFor = useRef<unknown>(null);
  useLayoutEffect(() => {
    const root = stageRef.current;
    if (!root || !geo || flownFor.current === frame.lastOps) return;
    flownFor.current = frame.lastOps;
    const origin = root.getBoundingClientRect();
    const needArc = arcs.find((a) => a.slot === "need");
    const next: Flight[] = [];
    for (const id of flyIds) {
      const mark = root.querySelector<HTMLElement>(`[data-role="need-phrase"][data-node-id="${CSS.escape(id)}"]`);
      // a phrase that wraps flies from its first line
      const r = mark ? (mark.getClientRects()[0] ?? mark.getBoundingClientRect()) : undefined;
      const to = geo.chips[id] ?? (nodes.get(id)?.slot === "need" && needArc ? { x: needArc.mid[0] - 7, y: needArc.mid[1] - 7, w: 14, h: 14 } : undefined);
      if (!mark || !r || !r.width || !to) continue;
      const a: Box = { x: r.left - origin.left, y: r.top - origin.top, w: r.width, h: r.height };
      const sw = Math.min(1, to.w / a.w);
      const sh = Math.min(1, to.h / a.h);
      next.push({
        id,
        text: mark.textContent ?? "",
        box: a,
        dx: to.x + (to.w - a.w * sw) / 2 - a.x,
        dy: to.y + (to.h - a.h * sh) / 2 - a.y,
        s: Math.min(sw, sh),
      });
    }
    setFlights(next);
  }, [geo, frame.lastOps, flyIds, arcs, nodes]);

  const asked = shaping && frame.ask ? frame.ask.slot : null;
  const flyAt = MOTION.highlightAt + MOTION.highlightEach * flyIds.length;
  const rootStyle = { "--ob-fly-at": `${flyAt}ms`, "--ob-fly": `${MOTION.fly}ms` } as CSSProperties;

  return (
    <section
      data-stage-view="orbit"
      aria-label={words.view.orbit}
      className="ob"
      data-step={step}
      data-context={shaping ? undefined : "true"}
      data-working={busy ? "true" : undefined}
      data-hot={hot ? "true" : undefined}
      style={rootStyle}
    >
      <div className="ob-stage" ref={stageRef}>
        <Hub
          draft={draft}
          frame={frame}
          state={state}
          dispatch={dispatch}
          words={words}
          marks={marks}
          arriving={flyIds.length > 0 && flyIds.length === marks.length}
          onPoint={setHot}
          counts={{ all: sketch.nodes.filter((n) => n.slot !== "need").length, pencil: sketch.nodes.filter((n) => n.slot !== "need" && !n.confirmed && n.origin === "athena").length }}
        />
        {zoneEl("steps")}
        <div className="ob-col ob-col--left">
          {zoneEl("apps")}
          {zoneEl("inputs")}
        </div>
        <div className="ob-col ob-col--right">
          {zoneEl("hand")}
          {zoneEl("output")}
        </div>
        {zoneEl("never")}

        {geo && (
          <svg className="ob-links" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`} aria-hidden="true" focusable="false">
            <defs>
              <marker id={`${uid}ink`} viewBox="0 0 8 8" refX="6.5" refY="4" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M1 1L6.5 4L1 7" className="ob-ah ob-ah--ink" />
              </marker>
              <marker id={`${uid}pen`} viewBox="0 0 8 8" refX="6.5" refY="4" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M1 1L6.5 4L1 7" className="ob-ah ob-ah--pen" />
              </marker>
            </defs>
            {sketch.edges.map((e) => {
              const key = `${e.from}>${e.to}`;
              const r = routes.get(key);
              if (!r) return null;
              const ink = !!nodes.get(e.from)?.confirmed && !!nodes.get(e.to)?.confirmed;
              const drawAt = newLinks.get(key);
              const style = { "--ob-len": `${Math.ceil(r.len)}px`, "--ob-delay": `${drawAt ?? 0}ms` } as CSSProperties;
              return (
                <g
                  key={key}
                  className="ob-link"
                  data-ink={ink ? "true" : undefined}
                  data-heat={hot ? (e.from === hot || e.to === hot ? "hot" : "dim") : undefined}
                  data-drawing={drawAt !== undefined ? "true" : undefined}
                  style={style}
                >
                  <path className="ob-link__base" d={r.d} markerEnd={`url(#${uid}${ink ? "ink" : "pen"})`} />
                  <path className="ob-link__flow" d={r.d} />
                </g>
              );
            })}
          </svg>
        )}

        {geo && (
          <svg className="ob-ring" width={geo.w} height={geo.h} viewBox={`0 0 ${geo.w} ${geo.h}`} focusable="false">
            {arcs.map((a) => {
              const cov: CoverageValue = draft.coverage[a.slot];
              const c = counts[a.slot];
              const label = ORBIT_WORDS.arc(a.slot, words.slot[a.slot], c.all, c.pencil);
              return (
                <g
                  key={a.slot}
                  className="ob-arc"
                  data-slot={a.slot}
                  data-cov={String(cov)}
                  data-asked={asked === a.slot ? "true" : undefined}
                  data-lit={lit === a.slot ? "true" : undefined}
                  role="img"
                  tabIndex={0}
                  aria-label={label}
                  onPointerEnter={() => setLit(a.slot)}
                  onPointerLeave={() => setLit(null)}
                  onFocus={() => setLit(a.slot)}
                  onBlur={() => setLit(null)}
                >
                  <path className="ob-arc__line" d={a.d} />
                  <path className="ob-arc__hit" d={a.d} />
                </g>
              );
            })}
          </svg>
        )}
        {litArc && (
          <div className="ob-tip" data-side={litArc.side} style={{ left: litArc.tip[0], top: litArc.tip[1] }} aria-hidden="true">
            {ORBIT_WORDS.arc(litArc.slot, words.slot[litArc.slot], counts[litArc.slot].all, counts[litArc.slot].pencil)}
          </div>
        )}

        {flights.length > 0 && (
          <div className="ob-flights" aria-hidden="true">
            {flights.map((f) => (
              <span
                key={f.id}
                className="ob-flight"
                style={
                  {
                    left: f.box.x,
                    top: f.box.y,
                    width: f.box.w,
                    height: f.box.h,
                    "--ob-dx": `${f.dx}px`,
                    "--ob-dy": `${f.dy}px`,
                    "--ob-s": f.s,
                  } as CSSProperties
                }
              >
                {f.text}
              </span>
            ))}
          </div>
        )}
      </div>
    </section>
  );

  function zoneEl(key: ZoneKey) {
    const z = zones[key];
    return (
      <Zone
        key={key}
        zone={key}
        side={SIDE_OF[key]}
        name={words.slot[key]}
        grid={z.grid}
        split={z.split}
        nodes={nodes}
        looks={looks}
        card={state.card}
        asked={asked === key}
        lit={lit === key}
        step={step}
        busy={busy}
        dispatch={dispatch}
        onPoint={setHot}
        setChipRef={setChipRef}
        setCellsRef={setCellsRef}
        words={words}
      />
    );
  }
}
