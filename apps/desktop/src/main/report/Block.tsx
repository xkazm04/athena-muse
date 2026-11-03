// One part of the report: a frame (its title, how old it is when the report is old, the pin) around
// what it shows. Every figure comes from the daemon's values for the part's id; a part whose value is
// missing says it could not be read, and an unknown sort says it could not be shown (the daemon
// validates, so neither should reach the screen).

import { useState, type ReactNode } from "react";
import type { Block as BlockSpec, BlockValue, Card, DecisionEdit, ThreadChannel, TrackVerdictBody, Verdict } from "../../lib/contract";
import { openExternal } from "../../lib/windows";
import { CardView, StatStrip } from "../../ui";
import { reasonOf } from "../store";
import { Funnel } from "./Funnel";
import { Queue } from "./Queue";
import { Sparkline } from "./Sparkline";
import { CHANNEL_WORD, cellText, creatorName, fieldWord, figure, rel, str } from "./format";

export interface BlockContext {
  now: Date;
  genres: string[];
  callout?: string;
  onVerdict: (recordId: string, body: TrackVerdictBody) => Promise<unknown>;
  /** Absent where a part cannot be pinned (a part in her reply, ADR 0022): no pin is drawn. */
  onPin?: (blockId: string, on: boolean) => Promise<void>;
  onDecide: (cardId: string, verdict: Verdict, edited?: DecisionEdit) => Promise<Card>;
  onResolved?: () => void;
}

const spanOf = (span: number) => Math.min(12, Math.max(1, Math.round(span) || 12));

const conf = (b: BlockSpec, key: string): unknown => (b.config ? b.config[key] : undefined);
const confText = (b: BlockSpec, key: string): string | undefined => {
  const v = conf(b, key);
  return typeof v === "string" && v ? v : undefined;
};

export function Block({
  block,
  value,
  pinned,
  stale,
  ctx,
}: {
  block: BlockSpec;
  value: BlockValue | undefined;
  pinned: boolean;
  /** "as of 3 h ago" when the report is old, else undefined. */
  stale?: string;
  ctx: BlockContext;
}) {
  const [pinBusy, setPinBusy] = useState(false);
  const [pinProblem, setPinProblem] = useState("");
  const headId = `rp-h-${block.id}`;

  const pin = async () => {
    if (!ctx.onPin) return;
    setPinBusy(true);
    setPinProblem("");
    try {
      await ctx.onPin(block.id, !pinned);
    } catch (e) {
      setPinProblem(reasonOf(e, "Could not pin this"));
    } finally {
      setPinBusy(false);
    }
  };

  const stat = block.kind === "stat";
  return (
    <section
      className="rp-block"
      data-role="report-block"
      data-kind={block.kind}
      data-pinned={String(pinned)}
      style={{ gridColumn: `span ${spanOf(block.span)}` }}
      aria-labelledby={headId}
    >
      <header className="rp-block__head">
        <h3 id={headId} className={stat ? "m-sr" : "rp-block__title"}>
          {block.title}
        </h3>
        {stale && <span className="rp-block__stale">{stale}</span>}
        {ctx.onPin && (
          <button
            type="button"
            className="rp-pin"
            data-role="pin"
            aria-pressed={pinned}
            aria-label={pinned ? `Unpin ${block.title}` : `Pin ${block.title}`}
            title={pinned ? "Pinned: it stays when Athena rearranges the page" : "Pin it so it stays when Athena rearranges the page"}
            disabled={pinBusy}
            onClick={() => void pin()}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 3h6l-1 6 4 4H6l4-4-1-6zM12 13v8" />
            </svg>
          </button>
        )}
      </header>
      <div className="rp-block__body">{body(block, value, ctx)}</div>
      {pinProblem && (
        <p className="m-error" role="alert">
          {pinProblem}
        </p>
      )}
    </section>
  );
}

const unread = <p className="rp-error">This part could not be read. It comes back when the page is read again.</p>;

function body(block: BlockSpec, v: BlockValue | undefined, ctx: BlockContext): ReactNode {
  if (block.kind === "callout") {
    return ctx.callout ? <p className="rp-callout">{ctx.callout}</p> : <p className="rp-empty">Athena has nothing to add here yet.</p>;
  }
  if (!v) return unread;
  switch (block.kind) {
    case "stat": {
      const n = v.count ?? v.value;
      return <StatStrip className="rp-stat" label={block.title} tiles={[{ key: block.id, label: block.title, value: figure(n), unit: confText(block, "unit") }]} />;
    }
    case "trend":
      return v.series?.length ? (
        <Sparkline series={v.series} unit={confText(block, "unit")} title={block.title} />
      ) : (
        <p className="rp-empty">No readings yet.</p>
      );
    case "queue":
      return v.items?.length ? (
        <Queue blockId={block.id} items={v.items} genres={ctx.genres} now={ctx.now} onVerdict={ctx.onVerdict} />
      ) : (
        <p className="rp-empty">No tracks waiting for you.</p>
      );
    case "pipeline":
      return v.stages?.length ? <Funnel stages={v.stages} title={block.title} /> : <p className="rp-empty">No stages yet.</p>;
    case "list":
      return <List block={block} v={v} now={ctx.now} />;
    case "thread":
      return <Threads v={v} now={ctx.now} />;
    case "cards":
      return v.cards?.length ? (
        <div className="rp-cards">
          {v.cards.map((c) => (
            <CardView key={c.id} card={c} onDecide={(verdict, edited) => ctx.onDecide(c.id, verdict, edited)} onResolved={() => ctx.onResolved?.()} />
          ))}
        </div>
      ) : (
        <p className="rp-empty">Nothing waits for your signature.</p>
      );
    default:
      return <p className="rp-error">This part could not be shown.</p>;
  }
}

function List({ block, v, now }: { block: BlockSpec; v: BlockValue; now: Date }) {
  const raw = conf(block, "fields");
  const fields = Array.isArray(raw) ? raw.filter((f): f is string => typeof f === "string") : ["title"];
  if (!v.items?.length) return <p className="rp-empty">Nothing here yet.</p>;
  return (
    <table className="m-grid rp-list">
      <thead>
        <tr>
          {fields.map((f) => (
            <th key={f} scope="col">
              {fieldWord(f)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {v.items.map((it) => (
          <tr key={it.id}>
            {fields.map((f) => (
              <td key={f} data-field={f}>
                {cellText(it, f, now)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Threads({ v, now }: { v: BlockValue; now: Date }) {
  if (!v.items?.length) return <p className="rp-empty">No conversations yet.</p>;
  return (
    <ul className="rp-threads">
      {v.items.map((it) => {
        const who = creatorName(str(it, "creator_key"));
        const where = CHANNEL_WORD[str(it, "channel") as ThreadChannel] ?? "";
        const url = str(it, "url");
        const subject = str(it, "subject") ?? `Conversation with ${who}`;
        return (
          <li key={it.id} className="rp-thread">
            <p className="rp-thread__head">
              {url ? (
                <a
                  href={url}
                  className="rp-thread__subject"
                  onClick={(e) => {
                    e.preventDefault();
                    void openExternal(url);
                  }}
                >
                  {subject}
                </a>
              ) : (
                <b className="rp-thread__subject">{subject}</b>
              )}
              <span className="rp-thread__when">{rel(str(it, "last_at"), now)}</span>
            </p>
            <p className="rp-thread__meta">
              {who}
              {where ? ` · ${where}` : ""}
            </p>
            {str(it, "snippet") && <p className="rp-thread__snippet">{str(it, "snippet")}</p>}
          </li>
        );
      })}
    </ul>
  );
}

/** A quiet frame while the report is first read: no fake numbers. */
export function BlockSkeleton({ span }: { span: number }) {
  return (
    <div className="rp-block rp-block--wait" style={{ gridColumn: `span ${span}` }} aria-hidden="true">
      <span className="rp-sk rp-sk--l" />
      <span className="rp-sk" />
      <span className="rp-sk rp-sk--s" />
    </div>
  );
}
