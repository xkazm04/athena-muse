// The main window's Athena place (ADR 0024): the conversation as an open book, both pages side by side
// and the ribbon below, with the back pages that need this window's width and stores: the project's
// report, a chore being drawn, the report as other assistants see it, and what it cost.

import { useEffect, useMemo, useState } from "react";
import { useHer } from "../../athena/store";
import * as api from "../../lib/api";
import type { Draft, HostReport, ReportView } from "../../lib/contract";
import { Spread } from "../../spread/Spread";
import type { BackPage } from "../../spread/pages";
import { useAppEvents } from "../../ui";
import { useMain } from "../store";
import { ChoreLeft, ChoreRight } from "./ChorePages";
import { CostsLeft, CostsRight, money } from "./CostsPage";
import { ElsewherePage } from "./ElsewherePage";
import { ReportLeft, ReportRight } from "./ReportPages";
import "./book.css";

/** The open draft of a project while it is still being drawn, read from the daemon; null otherwise. */
function useDrawing(draftId: string | undefined, step: string | undefined): [Draft | null, (d: Draft) => void] {
  const [draft, setDraft] = useState<Draft | null>(null);
  useEffect(() => {
    let live = true;
    if (!draftId || step !== "shape") {
      setDraft(null);
      return;
    }
    api.getDraft(draftId).then(
      (d) => live && setDraft(d),
      () => live && setDraft(null),
    );
    return () => {
      live = false;
    };
  }, [draftId, step]);
  return [draft, setDraft];
}

interface BackPageData {
  spaceId: string;
  /** The active project's report, when it keeps records and has been read. */
  view: ReportView | null;
  /** Its open draft while it is still being drawn. */
  draft: Draft | null;
  setDraft: (d: Draft) => void;
  ledgerTotal: number | undefined;
  /** How the report seen elsewhere is read (the preview passes its fixture). */
  readElsewhere?: (spaceId: string) => Promise<HostReport>;
}

/** The back pages this window adds after the conversation, each only when its data exists. */
export function backPages({ spaceId, view, draft, setDraft, ledgerTotal, readElsewhere }: BackPageData): BackPage[] {
  const back: BackPage[] = [];
  if (view) {
    back.push({
      key: "report",
      glyph: "≡",
      label: "The project's report",
      sub: view.default ? "the first layout" : "her arrangement",
      left: <ReportLeft spaceId={spaceId} view={view} />,
      right: <ReportRight spaceId={spaceId} view={view} />,
      leftLabel: "Left page: what the report is, and your standing rules",
      rightLabel: "Right page: the report",
    });
  }
  if (draft) {
    back.push({
      key: "chore",
      glyph: "✎",
      label: "A chore being drawn",
      sub: draft.agreed ? "agreed" : "not agreed yet",
      left: <ChoreLeft draft={draft} />,
      right: <ChoreRight draft={draft} onChange={setDraft} />,
      leftLabel: "Left page: the chore in your words",
      rightLabel: "Right page: the sketch, place by place",
    });
  }
  if (view) {
    back.push({
      key: "elsewhere",
      glyph: "↗",
      label: "Seen in another assistant",
      sub: "stylised",
      single: true,
      left: <ElsewherePage spaceId={spaceId} {...(readElsewhere ? { read: readElsewhere } : {})} />,
      right: null,
      leftLabel: "Seen in another assistant",
      rightLabel: "",
    });
  }
  back.push({
    key: "costs",
    glyph: "$",
    label: "What it cost",
    sub: ledgerTotal === undefined ? "" : `est. ${money(ledgerTotal)}`,
    left: <CostsLeft />,
    right: <CostsRight />,
    leftLabel: "Left page: what running her cost",
    rightLabel: "Right page: every call",
  });
  return back;
}

export function AthenaBook({ page }: { page?: string | undefined }) {
  const boot = useHer((s) => s.boot);
  const onEvent = useHer((s) => s.onEvent);
  useAppEvents(onEvent);
  useEffect(() => {
    void boot();
  }, [boot]);

  const activeId = useHer((s) => s.activeId);
  const space = useMain((s) => s.spaces.find((x) => x.id === activeId));
  const keeps = (space?.kinds?.length ?? 0) > 0;
  const view = useMain((s) => (keeps ? s.reports[activeId]?.view : undefined)) ?? null;
  const loadReport = useMain((s) => s.loadReport);
  const loadLedger = useMain((s) => s.loadLedger);
  const ledger = useMain((s) => s.ledger);
  const [draft, setDraft] = useDrawing(space?.draft?.id, space?.draft?.step);

  useEffect(() => {
    if (keeps) void loadReport(activeId);
  }, [keeps, activeId, loadReport]);
  useEffect(() => {
    void loadLedger();
  }, [loadLedger]);

  const back = backPages({ spaceId: activeId, view, draft, setDraft, ledgerTotal: ledger?.totals.cost_usd });
  const open = useMemo(() => (page ? { key: page } : null), [page]);
  return <Spread layout="open" back={back} open={open} />;
}
