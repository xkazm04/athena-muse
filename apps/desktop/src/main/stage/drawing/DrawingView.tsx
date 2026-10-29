// The Drawing view: a port of the contest's A/1 "Pencil & Ink" (WP3-2). The sketch fills the window
// as five territories, a fence for "never" and the person's sentence on top; her guesses are dashed
// violet pencil, the person inks them; the question is a note pinned across the bottom. The later
// steps sit in A/1's strip and drawer. The view holds no copy of the model: it draws the props and
// sends actions, and a piece's place is kept in the store so it never moves.

import { useEffect, useMemo } from "react";
import type { SketchNode } from "../../../lib/contract";
import { useDraftProject } from "../hooks";
import { RevisitBanner } from "../parts";
import { authorOf, isPencil, overlayOf, shownSketch } from "../select";
import type { Place, StageViewProps } from "../types";
import { CheckDrawer, Finale, Strip, VerdictDrawer } from "./Later";
import { Note } from "./Note";
import { FENCE, isLane, layout } from "./place";
import { Sketch } from "./Sketch";
import { DRAWING_WORDS as dw } from "./words";
import "./drawing.css";

const WAITING = new Set(["sending", "thinking", "slow"]);

export function DrawingView({ draft, frame, state, dispatch, words, place }: StageViewProps) {
  const step = draft.step;
  const phase = frame.phase;
  const busy = !!state.work || phase !== "idle";
  const sketch = useMemo(() => shownSketch(draft.sketch, state.dropping), [draft.sketch, state.dropping]);

  // Places for the whole sketch (a piece being rubbed out keeps its row for the undo); the new ones
  // go back to the store, so they never move again, whatever arrives after them.
  const memo = state.places.drawing;
  const lay = useMemo(() => layout(draft.sketch, memo), [draft.sketch, memo]);
  useEffect(() => {
    for (const [id, p] of lay.fresh) place("drawing", id, p);
  }, [lay, place]);

  const overlay = useMemo(() => overlayOf(frame, state.inked), [frame, state.inked]);
  const newLinks = useMemo(
    () => new Set(frame.lastOps.flatMap((op) => (op.op === "link" && op.edge ? [`${op.edge.from}>${op.edge.to}`] : []))),
    [frame.lastOps],
  );
  const pencil = useMemo(() => sketch.nodes.filter(isPencil).map((n) => n.id), [sketch]);
  const author = authorOf(state.author);
  const revisit = step === "shape" && (draft.verdict === "revise" || author.status === "failed");

  // The lane she asks about glows while the question is open; while she thinks, one faint slot shows
  // where her answer to it will land (the ask carries its slot; nothing peeks at what comes next).
  const ask = frame.ask;
  const shaping = step === "shape" || step === "describe";
  const asking = shaping && ask && phase === "idle" ? ask.slot : null;
  const ghost = useMemo((): Place | null => {
    if (!shaping || !ask || !WAITING.has(phase) || !(isLane(ask.slot) || ask.slot === FENCE)) return null;
    const probe: SketchNode = { id: "\u0000ghost", kind: "step", slot: ask.slot, label: "", origin: "athena", confirmed: false };
    const at = layout({ nodes: [...draft.sketch.nodes, probe], edges: [] }, lay.places).places[probe.id];
    return at && (at.area === FENCE || at.index < lay.rows) ? at : null;
  }, [shaping, ask, phase, draft.sketch, lay]);

  const { project } = useDraftProject(draft);
  const side = (
    <>
      {revisit && (
        <RevisitBanner
          why={draft.verdict === "revise" ? "revise" : "unwritten"}
          note={draft.note}
          problems={author.status === "failed" ? author.problems : []}
          words={words}
        />
      )}
      {step === "shape" && !revisit && pencil.length > 0 && phase === "idle" && (
        <p className="dr-pencil">
          <b>{dw.pencilLeft(pencil.length)}</b>
          <button type="button" className="btn" data-role="ink-all" disabled={busy} onClick={() => dispatch({ type: "ink", node_ids: pencil })}>
            {dw.inkAll}
          </button>
        </p>
      )}
      {project && (
        <p className="dr-draftname">
          {dw.draftProject}: <b>{project.name}</b>
        </p>
      )}
    </>
  );

  const later = { draft, frame, state, dispatch, words };
  const strip = step === "author" || step === "rehearse" || (step === "preview" && !draft.expected && state.work !== "preview");
  const drawer = (step === "preview" && !strip) || step === "verdict";
  return (
    <section
      data-stage-view="drawing"
      aria-label={words.view.drawing}
      data-step={step}
      data-dim={(step === "preview" && drawer) || step === "saved" ? "true" : undefined}
      data-run={step === "rehearse" ? "true" : undefined}
    >
      <div className="dr">
        <Sketch
          need={draft.need}
          sketch={sketch}
          coverage={draft.coverage}
          lay={lay}
          overlay={overlay}
          newLinks={newLinks}
          step={step}
          asking={asking}
          ghost={ghost}
          card={state.card}
          busy={busy}
          dispatch={dispatch}
          words={words}
          side={side}
        />
        {shaping && <Note draft={draft} frame={frame} state={state} pencil={pencil} revisit={revisit} dispatch={dispatch} words={words} />}
        {strip && <Strip {...later} />}
        {drawer && step === "preview" && <CheckDrawer {...later} />}
        {drawer && step === "verdict" && <VerdictDrawer {...later} />}
        {step === "saved" && <Finale draft={draft} words={words} />}
      </div>
    </section>
  );
}
