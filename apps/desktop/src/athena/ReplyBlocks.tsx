// Report parts in her reply (ADR 0022): the report's own `Block` components, one per row at chat width,
// with the figures the daemon computed when she showed them. They only read here: no pin, no verdict,
// no signature (the daemon never sends a queue or a cards part to the chat). What the door dropped is
// said, with its reasons, the way the report says it.

import { useMemo } from "react";
import type { ShownBlocks } from "../lib/contract";
import { Block, type BlockContext } from "../main/report/Block";
import { droppedLine } from "../main/report/format";
import "../main/report/report.css";

const elsewhere = (): Promise<never> => Promise.reject(new Error("That is done on the project's report."));

export function ReplyBlocks({ shown }: { shown: ShownBlocks }) {
  const ctx = useMemo<BlockContext>(() => ({ now: new Date(), genres: [], onVerdict: elsewhere, onDecide: elsewhere }), []);
  return (
    <div className="her-blocks" data-role="reply-blocks">
      {shown.blocks.map((b) => (
        <Block key={b.id} block={b} value={shown.values[b.id]} pinned={false} ctx={ctx} />
      ))}
      {shown.dropped > 0 && (
        <details className="rp-dropped her-blocks__dropped" data-role="dropped">
          <summary>{droppedLine(shown.dropped)}</summary>
          {shown.reasons.length > 0 && (
            <ul>
              {shown.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </details>
      )}
    </div>
  );
}
