// Her report as another assistant shows it (ADR 0021, ADR 0024): one page torn out of the book. The
// view and its text are what `show_report` answers a host, read from the daemon; the look is stylised.

import { useEffect, useState } from "react";
import * as api from "../../lib/api";
import type { HostReport } from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";

const nf = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });
const shown = (v: number | null, unit?: string) => (v === null ? "no reading yet" : nf.format(v) + (unit ? ` ${unit}` : ""));

function when(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function ElsewherePage({ spaceId }: { spaceId: string }) {
  const [got, setGot] = useState<HostReport | null>(null);
  const [problem, setProblem] = useState("");
  const [asText, setAsText] = useState(false);
  useEffect(() => {
    let live = true;
    setGot(null);
    setProblem("");
    api.reportElsewhere(spaceId).then(
      (r) => live && setGot(r),
      (e: unknown) => live && setProblem(e instanceof DaemonError ? e.reason : "The report cannot be read."),
    );
    return () => {
      live = false;
    };
  }, [spaceId]);

  const view = got?.view;
  return (
    <div className="sp-torn" data-role="elsewhere">
      <p className="sp-kicker">
        <span className="eyebrow">Seen in another assistant</span>
        <span className="badge" data-tone="warning">
          Stylised
        </span>
      </p>
      <p className="sp-torn-label">
        Stylised: how another assistant might show her report, as one page torn out of this book. It only reads: verdicts, pins and signatures stay in Athena.
      </p>
      <div className="sp-host" role="region" aria-label="Her report as another assistant shows it">
        {problem && <p className="card-problem">The report cannot be read: {problem}</p>}
        {!view && !problem && <p className="sp-hv-proj">Reading the report…</p>}
        {view && (
          <>
            <p className="sp-hv-proj">{view.project.name}</p>
            <h3 className="sp-hv-title">{view.title}</h3>
            {asText ? (
              <pre className="sp-hv-text" data-role="host-text">
                {got.text}
              </pre>
            ) : (
              <>
                {view.callout && <p className="sp-hv-callout">{view.callout}</p>}
                <div className="sp-hv-grid">
                  {view.blocks
                    .filter((b) => b.kind !== "callout")
                    .map((b) => (
                      <div key={b.id} className="sp-hv-b" data-kind={b.kind}>
                        <h4>{b.title}</h4>
                        {b.kind === "stat" && b.figures[0] ? (
                          <div className="sp-hv-big">
                            {shown(b.figures[0].value)}
                            {b.figures[0].unit && b.figures[0].value !== null && <small>{b.figures[0].unit}</small>}
                          </div>
                        ) : (
                          b.figures.map((f) => (
                            <div key={f.label} className="sp-hv-fig">
                              <span>{f.label}</span>
                              <b>{shown(f.value, f.unit)}</b>
                            </div>
                          ))
                        )}
                        {b.rows.length > 0 && (
                          <ul className="sp-hv-rows">
                            {b.rows.map((r, i) => (
                              <li key={i}>{r}</li>
                            ))}
                          </ul>
                        )}
                        {b.more > 0 && <p className="sp-hv-more">and {b.more} more in the app</p>}
                        {b.figures.length === 0 && b.rows.length === 0 && <p className="sp-hv-more">Nothing here yet.</p>}
                      </div>
                    ))}
                </div>
              </>
            )}
            <p className="sp-hv-foot">Every figure is counted from what the project keeps ({when(view.rendered_at)}).</p>
            <div className="sp-hv-actions">
              <button type="button" className="btn btn-sm" aria-pressed={asText} onClick={() => setAsText(!asText)}>
                {asText ? "Show the view" : "Read it as text"}
              </button>
            </div>
            {asText && <p className="sp-hv-more">This is the plain text an assistant that shows no views reads, word for word.</p>}
          </>
        )}
      </div>
    </div>
  );
}
