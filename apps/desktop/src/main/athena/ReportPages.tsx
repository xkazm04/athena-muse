// The project's report as a spread of the book (ADR 0024): the left page says what it is, when she
// arranged it, her one sentence, the person's pins as standing rules they can remove, and what could
// not be shown; the right page is the report's own grid of parts. Every figure is the daemon's.

import * as api from "../../lib/api";
import type { ReportView } from "../../lib/contract";
import { useMain } from "../store";
import { Block, type BlockContext } from "../report/Block";
import { droppedLine, isStale, rel } from "../report/format";
import "../report/report.css";

export function ReportLeft({ spaceId, view }: { spaceId: string; view: ReportView }) {
  const composing = useMain((s) => s.reports[spaceId]?.composing ?? false);
  const composeProblem = useMain((s) => s.reports[spaceId]?.composeProblem ?? "");
  const composeReport = useMain((s) => s.composeReport);
  const pinBlock = useMain((s) => s.pinBlock);
  const titleOf = (id: string) => view.spec.blocks.find((b) => b.id === id)?.title ?? "A part";
  const arranged = !view.default && view.composed_at;
  return (
    <div>
      <p className="sp-kicker">
        <span className="eyebrow">The project&apos;s report</span>
      </p>
      <h2 className="sp-ask">{view.spec.title}</h2>
      <p className="sp-when">
        {arranged ? `Arranged by her ${rel(view.composed_at, new Date())}` : "Athena has not arranged this yet"} · every figure is counted from what
        the project keeps; she never types one
      </p>
      {view.spec.callout && <p className="sp-callout">{view.spec.callout}</p>}
      <h3 className="sp-h">Your standing rules</h3>
      <ul className="sp-rules" data-role="rules">
        {view.pinned.length === 0 && <li className="sp-rule-empty">No rules: she may rearrange every part.</li>}
        {view.pinned.map((id) => (
          <li key={id} className="sp-rule">
            <span>Keep &ldquo;{titleOf(id)}&rdquo; on the page, where I put it</span>
            <button type="button" className="btn btn-quiet btn-sm" aria-label={`Remove the rule for ${titleOf(id)}`} onClick={() => void pinBlock(spaceId, id, false).catch(() => undefined)}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      <p className="sp-foot">You set these by pinning a part. She keeps to them every time she rearranges the page, and a pinned part stays where you put it.</p>
      {view.dropped > 0 && (
        <>
          <h3 className="sp-h">What she could not show</h3>
          <p className="sp-note">{droppedLine(view.dropped)}:</p>
          <ul className="sp-list">
            {view.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </>
      )}
      <div className="sp-controls">
        <button type="button" className="btn btn-sm" data-role="recompose" disabled={composing} aria-busy={composing} onClick={() => void composeReport(spaceId)}>
          {composing ? "Arranging..." : "Arrange again"}
        </button>
      </div>
      {composeProblem && (
        <p className="sp-note" role="alert">
          {composeProblem}
        </p>
      )}
    </div>
  );
}

export function ReportRight({ spaceId, view }: { spaceId: string; view: ReportView }) {
  const pinBlock = useMain((s) => s.pinBlock);
  const verdict = useMain((s) => s.verdict);
  const loadCards = useMain((s) => s.loadCards);
  const loadReport = useMain((s) => s.loadReport);
  const failed = useMain((s) => s.reports[spaceId]?.load === "problem");
  const now = new Date();
  const stale = isStale(view, now, failed) ? `as of ${rel(view.rendered_at, now)}` : undefined;
  const ctx: BlockContext = {
    now,
    genres: [],
    ...(view.spec.callout ? { callout: view.spec.callout } : {}),
    onVerdict: verdict,
    onPin: (id, on) => pinBlock(spaceId, id, on),
    onDecide: (cardId, v, edited) => api.decide(cardId, v, edited),
    onResolved: () => {
      void loadCards();
      void loadReport(spaceId);
    },
  };
  return (
    <div>
      <p className="sp-her">
        <span className="eyebrow">The page</span>
      </p>
      <p className="sp-note">Her parts on a twelve-column grid. The pin keeps a part where it is.</p>
      <div className="rp-grid sp-rgrid" data-role="report-grid">
        {view.spec.blocks.map((b) => (
          <Block key={b.id} block={b} value={view.values[b.id]} pinned={view.pinned.includes(b.id)} stale={stale} ctx={ctx} />
        ))}
      </div>
    </div>
  );
}
