import { useCallback, useEffect, useState, type ReactNode } from "react";
import * as api from "../../lib/api";
import type { BenchSummary, ChoreDetail, FeaturedStatus, ProofRow } from "../../lib/contract";
import { reasonOf, useMain } from "../store";
import {
  ENGINE_WORD,
  OP_WORD,
  SENSE_WORD,
  STATUS,
  VERDICT,
  backendLines,
  benchCommand,
  count,
  figure,
  minutes,
  passTone,
  usd,
  when,
} from "./words";

/** One chore, read from the daemon on open; back returns to the catalogue. */
export function ChoreScene({ id }: { id: string }) {
  const navigate = useMain((s) => s.navigate);
  const [detail, setDetail] = useState<ChoreDetail | null>(null);
  const [problem, setProblem] = useState("");

  const load = useCallback(async () => {
    setProblem("");
    setDetail(null);
    try {
      setDetail(await api.chore(id));
    } catch (e) {
      setProblem(reasonOf(e, "Could not read the chore"));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="m-level m-chore">
      <button type="button" className="btn btn-quiet m-back" onClick={() => navigate({ view: "chores" })}>
        All chores
      </button>
      {problem && (
        <div className="plane m-problem" role="alert">
          <p>{problem}</p>
          <button type="button" className="btn" onClick={() => void load()}>
            Try again
          </button>
        </div>
      )}
      {!detail && !problem && (
        <span className="badge" data-tone="info" role="status">
          reading
        </span>
      )}
      {detail && <ChoreDetailView detail={detail} />}
    </div>
  );
}

/** Pure: the preview renders it with fixtures. */
export function ChoreDetailView({ detail }: { detail: ChoreDetail }) {
  const { chore } = detail;
  const status = STATUS[chore.featured];
  return (
    <>
      <section className="plane m-section">
        <p className="m-eyebrow">Chore</p>
        <h1 className="m-title">{chore.title}</h1>
        <p className="m-lead">{chore.promise}</p>
        <div className="m-row">
          {chore.senses.map((s) => (
            <span key={s} className="badge">
              {SENSE_WORD[s]}
            </span>
          ))}
          <span className="badge" data-tone={status.tone}>
            <i className="m-chores__dot" aria-hidden="true" />
            {status.word}
          </span>
        </div>
        <dl className="m-chore__facts">
          <div>
            <dt>For</dt>
            <dd>{detail.persona}</dd>
          </div>
          <div>
            <dt>Works in</dt>
            <dd>
              <ul className="m-chips">
                {detail.apps.map((a) => (
                  <li key={a.app_id} className="badge">
                    {a.name}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        </dl>
        <div className="m-chore__brief">
          <Brief text={detail.brief} />
        </div>
      </section>
      <Proofs proofs={detail.proofs} backends={detail.backends} featured={chore.featured} />
      <Bench id={chore.id} bench={chore.bench} />
    </>
  );
}

function Proofs({
  proofs,
  backends,
  featured,
}: {
  proofs: ProofRow[];
  backends: Record<string, string>;
  featured: FeaturedStatus;
}) {
  const lines = backendLines(backends);
  return (
    <section className="plane m-section" aria-labelledby="chore-proofs">
      <h2 id="chore-proofs" className="m-h2">
        Proofs
      </h2>
      {lines.length > 0 && <p className="m-muted">{lines.join("; ")}</p>}
      {proofs.length === 0 ? (
        <p className="m-muted">No proofs measured yet.</p>
      ) : (
        <div className="m-table-wrap">
          <table className="m-table m-chore__proofs">
            <thead>
              <tr>
                <th scope="col">Sense</th>
                <th scope="col">Proof</th>
                <th scope="col">Question</th>
                <th scope="col" className="m-num">
                  Measured
                </th>
                <th scope="col" className="m-num">
                  Bar
                </th>
                <th scope="col" className="m-num">
                  n
                </th>
                <th scope="col">Result</th>
                <th scope="col">Note</th>
              </tr>
            </thead>
            <tbody>
              {proofs.map((p) => (
                <tr key={`${p.sense}/${p.id}`} title={p.note}>
                  <td>{SENSE_WORD[p.sense]}</td>
                  <td className="m-mono">{p.id}</td>
                  <td className="m-chore__question">{p.question}</td>
                  <td className="m-num">{p.measured === undefined ? "not measured" : figure(p.measured)}</td>
                  <td className="m-num">
                    {OP_WORD[p.op]} {figure(p.bar)}
                  </td>
                  <td className="m-num">{p.n.toLocaleString("en-US")}</td>
                  <td>
                    <span className="badge" data-tone={passTone(p.passed, featured)}>
                      {p.passed ? "passed" : "failed"}
                    </span>
                  </td>
                  <td>
                    {p.note ? (
                      <details className="m-chore__note">
                        <summary>Note</summary>
                        <p>{p.note}</p>
                      </details>
                    ) : (
                      <span className="m-muted">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Bench({ id, bench }: { id: string; bench?: BenchSummary }) {
  if (!bench) {
    return (
      <section className="plane m-section" aria-labelledby="chore-bench">
        <h2 id="chore-bench" className="m-h2">
          Bench
        </h2>
        <p>Not rehearsed yet.</p>
        <p className="m-muted">Rehearse it with:</p>
        <code className="m-mono m-chore__command">{benchCommand(id)}</code>
      </section>
    );
  }
  const verdict = VERDICT[bench.verdict];
  return (
    <section className="plane m-section" aria-labelledby="chore-bench">
      <h2 id="chore-bench" className="m-h2">
        Bench
        <span className="badge" data-tone={verdict.tone}>
          {verdict.word}
        </span>
      </h2>
      {bench.reasons.length > 0 && (
        <ul className="m-chore__reasons">
          {bench.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
      <dl className="m-chore__facts m-chore__bench">
        <Fact term="Found">
          {bench.found} of {bench.eligible}
        </Fact>
        <Fact term="Value found">
          {usd(bench.value_found_usd)} of {usd(bench.value_total_usd)}
        </Fact>
        <Fact term="False claims">{bench.false_claims}</Fact>
        <Fact term="Duplicates">{bench.duplicates}</Fact>
        <Fact term="Traps filed">{bench.traps_filed}</Fact>
        <Fact term="Turns">{count(bench.turns, "turn", "turns")}</Fact>
        <Fact term="Time">{minutes(bench.minutes)}</Fact>
        <Fact term="Cost">{bench.cost_usd === undefined ? "unpriced" : `est. ${usd(bench.cost_usd)}`}</Fact>
      </dl>
      <p className="m-muted">
        Ran on {ENGINE_WORD[bench.engine]} (<span className="m-mono">{bench.model}</span>), {when(bench.run_at)}
      </p>
    </section>
  );
}

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** The brief is light markdown: paragraphs, "- " lists and **bold**. Rendered as text, never as HTML. */
export function Brief({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length === 0) return;
    blocks.push(
      <ul key={`l${blocks.length}`}>
        {list.map((l, i) => (
          <li key={i}>{bold(l)}</li>
        ))}
      </ul>,
    );
    list = [];
  };
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (/^[-*] /.test(line)) {
      list.push(line.slice(2));
      continue;
    }
    flush();
    if (line) blocks.push(<p key={`p${blocks.length}`}>{bold(line)}</p>);
  }
  flush();
  return <>{blocks}</>;
}

function bold(line: string): ReactNode[] {
  return line.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part));
}
