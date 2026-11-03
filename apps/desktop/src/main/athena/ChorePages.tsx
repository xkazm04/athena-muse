// A chore being drawn, as a spread of the book (ADR 0024): the person's need and what she still needs
// on the left; the sketch place by place on the right, ink and pencil, with the open question. Inking a
// guess or rubbing it out acts on the draft itself; answering goes on, on the stage.

import { useState } from "react";
import * as api from "../../lib/api";
import type { CoverageValue, Draft, SketchNode } from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import { SLOTS } from "../stage/select";
import { NEED_PHRASE, SLOT_TITLE, STAGE_WORDS } from "../stage/words";
import { useMain } from "../store";

const COVERAGE: Record<string, string> = { "1": "agreed", "0.5": "her pencil only", "0": "empty", skipped: "skipped" };
const coverageWords = (c: CoverageValue | undefined) => (c === undefined ? "" : (COVERAGE[String(c)] ?? ""));

function day(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function ChoreLeft({ draft }: { draft: Draft }) {
  const navigate = useMain((s) => s.navigate);
  const missing = SLOTS.filter((s) => draft.coverage[s] === 0).map((s) => NEED_PHRASE[s]);
  return (
    <div>
      <p className="sp-kicker">
        <span className="eyebrow">A chore being drawn</span>
        <span className="badge" data-tone={draft.agreed ? "success" : "info"}>
          {draft.agreed ? "Agreed" : "Not agreed yet"}
        </span>
      </p>
      <h2 className="sp-ask">{draft.need}</h2>
      <p className="sp-when">Started {day(draft.created)} · in your words</p>
      <h3 className="sp-h">Where it stands</h3>
      <p className="sp-foot">{draft.agreed ? STAGE_WORDS.ready : missing.length > 0 ? `${STAGE_WORDS.stillNeeds} ${missing.join(" and ")}.` : "Every place has something in it."}</p>
      <div className="sp-controls">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate({ view: "stage", id: draft.id })}>
          Go on drawing it
        </button>
      </div>
    </div>
  );
}

function Node({ node, draftId, leads, onChange }: { node: SketchNode; draftId: string; leads: string[]; onChange: (d: Draft) => void }) {
  const [problem, setProblem] = useState("");
  const pencil = !node.confirmed;
  const act = async (fn: typeof api.draftConfirm) => {
    try {
      onChange(await fn(draftId, [node.id]));
    } catch (e) {
      setProblem(e instanceof DaemonError ? e.reason : "That did not reach her");
    }
  };
  return (
    <div className={`sp-nd${node.origin === "you" ? " is-you" : ""}${pencil ? " is-pencil" : ""}`} data-role="node">
      <strong>{node.label}</strong>
      <p className="sp-nd-meta">{node.origin === "you" ? STAGE_WORDS.youWrote : pencil ? STAGE_WORDS.herGuess : STAGE_WORDS.herInked}</p>
      {node.quote && <p>&ldquo;{node.quote}&rdquo;</p>}
      {node.detail && <p className="sp-nd-meta">{node.detail}</p>}
      {node.site && <p className="sp-nd-meta">At {node.site.url}</p>}
      {leads.length > 0 && <p className="sp-nd-meta">Leads to {leads.map((l) => `“${l}”`).join(" and ")}</p>}
      {pencil && (
        <div className="sp-nd-actions">
          <button type="button" className="btn btn-sm" onClick={() => void act(api.draftConfirm)}>
            {STAGE_WORDS.inkIt}
          </button>
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => void act(api.draftDrop)}>
            {STAGE_WORDS.dropIt}
          </button>
        </div>
      )}
      {problem && (
        <p className="sp-note" role="alert">
          {problem}
        </p>
      )}
    </div>
  );
}

export function ChoreRight({ draft, onChange }: { draft: Draft; onChange: (d: Draft) => void }) {
  const navigate = useMain((s) => s.navigate);
  const label = (id: string) => draft.sketch.nodes.find((n) => n.id === id)?.label ?? "a step";
  const leads = (id: string) => draft.sketch.edges.filter((e) => e.from === id).map((e) => label(e.to));
  return (
    <div>
      <p className="sp-her">
        <span className="eyebrow">The sketch, place by place</span>
      </p>
      <p className="sp-note">Solid lines are ink: your words, or her ideas you agreed to. Dashed lines are her pencil: a guess waiting for your yes.</p>
      {SLOTS.map((slot) => {
        const nodes = draft.sketch.nodes.filter((n) => n.slot === slot);
        return (
          <section key={slot} className="sp-place" data-slot={slot}>
            <div className="sp-place-h">
              <h4>{SLOT_TITLE[slot]}</h4>
              <span className="sp-cov" data-c={String(draft.coverage[slot])}>
                {coverageWords(draft.coverage[slot])}
              </span>
            </div>
            <div className="sp-nds">
              {nodes.length === 0 && <p className="sp-note">Empty: {NEED_PHRASE[slot]}.</p>}
              {nodes.map((n) => (
                <Node key={n.id} node={n} draftId={draft.id} leads={leads(n.id)} onChange={onChange} />
              ))}
            </div>
            {draft.ask?.slot === slot && (
              <div className="sp-ask-box" data-role="open-question">
                <p>{draft.ask.text}</p>
                <div className="sp-sugg" role="group" aria-label={STAGE_WORDS.suggestions}>
                  {draft.ask.suggestions.map((s) => (
                    <span key={s} className="sp-chip">
                      {s}
                    </span>
                  ))}
                </div>
                <button type="button" className="btn btn-sm" onClick={() => navigate({ view: "stage", id: draft.id })}>
                  Answer on the stage
                </button>
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
