// A project's report on its front page (business Phase 1): Athena arranges it from a closed kit and the
// daemon computes every figure from what the project keeps. The title row says when she arranged it
// (or that she has not yet) with "Arrange again"; then her one sentence, what could not be shown and why,
// and the parts on a 12-column grid that scrolls inside its own region, so the page never does.

import { useEffect, useState } from "react";
import * as api from "../../lib/api";
import type { Card, DecisionEdit, SpaceSummary, TrackVerdictBody, Verdict } from "../../lib/contract";
import { REPORT_IDLE, useMain, type ReportState } from "../store";
import { Block, BlockSkeleton, type BlockContext } from "./Block";
import { droppedLine, genresOf, isStale, rel } from "./format";
import "./report.css";

export interface ReportBodyProps {
  state: ReportState;
  now: Date;
  genres: string[];
  onRetry: () => void;
  onRecompose: () => void;
  onPin: (blockId: string, on: boolean) => Promise<void>;
  onVerdict: (recordId: string, body: TrackVerdictBody) => Promise<unknown>;
  onDecide: (cardId: string, verdict: Verdict, edited?: DecisionEdit) => Promise<Card>;
  onResolved?: () => void;
}

const SKELETON = [8, 4, 12, 6, 6];

/** The report as the person sees it, from its state alone (the preview drives it with no daemon). */
export function ReportBody({ state, now, genres, onRetry, onRecompose, onPin, onVerdict, onDecide, onResolved }: ReportBodyProps) {
  const view = state.view;

  if (!view) {
    if (state.load === "problem") {
      return (
        <section className="rp" data-role="report" data-state="problem" aria-label="Report">
          <div className="rp-problem" role="alert">
            <p>
              <b>The report could not be read.</b> {state.problem}
            </p>
            <button type="button" className="btn" onClick={onRetry}>
              Try again
            </button>
          </div>
        </section>
      );
    }
    return (
      <section className="rp" data-role="report" data-state="reading" aria-label="Report" aria-busy="true">
        <div className="rp-head">
          <span className="rp-sk rp-sk--title" />
        </div>
        <div className="rp-grid">
          {SKELETON.map((span, i) => (
            <BlockSkeleton key={i} span={span} />
          ))}
        </div>
      </section>
    );
  }

  const failed = state.load === "problem";
  const stale = isStale(view, now, failed) ? `as of ${rel(view.rendered_at, now)}` : undefined;
  const arranged = !view.default && view.composed_at;
  const calloutPart = view.spec.blocks.some((b) => b.kind === "callout");
  const ctx: BlockContext = { now, genres, callout: view.spec.callout, onVerdict, onPin, onDecide, onResolved };

  return (
    <section className="rp" data-role="report" data-state="ready" data-default={String(view.default)} aria-labelledby="rp-title">
      <header className="rp-head">
        <h1 id="rp-title" className="rp-title">
          {view.spec.title}
        </h1>
        <p className="rp-when">{arranged ? `arranged ${rel(view.composed_at, now)}` : "Athena has not arranged this yet"}</p>
        <div className="rp-head__act">
          <button type="button" className="btn" data-role="recompose" disabled={state.composing} aria-busy={state.composing} onClick={onRecompose}>
            {state.composing ? "Arranging..." : "Arrange again"}
          </button>
        </div>
      </header>
      {state.composeProblem && (
        <p className="m-error rp-line" role="alert">
          {state.composeProblem}
        </p>
      )}
      {failed && (
        <p className="m-error rp-line" role="alert">
          Could not read it again: {state.problem}
        </p>
      )}
      {view.spec.callout && !calloutPart && <p className="rp-callout rp-callout--top">{view.spec.callout}</p>}
      {view.dropped > 0 && (
        <details className="rp-dropped" data-role="dropped">
          <summary>{droppedLine(view.dropped)}</summary>
          {view.reasons.length > 0 && (
            <ul>
              {view.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </details>
      )}
      <div className="rp-grid">
        {view.spec.blocks.map((b) => (
          <Block key={b.id} block={b} value={view.values[b.id]} pinned={view.pinned.includes(b.id)} stale={stale} ctx={ctx} />
        ))}
      </div>
    </section>
  );
}

/** The report of one project, read from the daemon when the page opens and kept live by its events. */
export function Report({ space }: { space: SpaceSummary }) {
  const state = useMain((s) => s.reports[space.id]) ?? REPORT_IDLE;
  const loadReport = useMain((s) => s.loadReport);
  const composeReport = useMain((s) => s.composeReport);
  const pinBlock = useMain((s) => s.pinBlock);
  const verdict = useMain((s) => s.verdict);
  const loadCards = useMain((s) => s.loadCards);
  const [genres, setGenres] = useState<string[]>([]);
  const queued = state.view?.spec.blocks.some((b) => b.kind === "queue") ?? false;
  const readAt = state.view?.rendered_at;

  useEffect(() => {
    void loadReport(space.id);
  }, [space.id, loadReport]);

  // The genres already used on this project's tracks, read again with each reading of the report.
  useEffect(() => {
    if (!queued) return;
    let live = true;
    api.spaceRecords(space.id, "track").then(
      (tracks) => live && setGenres(genresOf(tracks ?? [])),
      () => undefined, // suggestions only; the field still takes any genre
    );
    return () => {
      live = false;
    };
  }, [space.id, queued, readAt]);

  return (
    <ReportBody
      state={state}
      now={new Date()}
      genres={genres}
      onRetry={() => void loadReport(space.id)}
      onRecompose={() => void composeReport(space.id)}
      onPin={(blockId, on) => pinBlock(space.id, blockId, on)}
      onVerdict={verdict}
      onDecide={(cardId, v, edited) => api.decide(cardId, v, edited)}
      onResolved={() => {
        void loadCards();
        void loadReport(space.id);
      }}
    />
  );
}
