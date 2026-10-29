// The stage (onboarding v2, ADR 0007): one frame with no page scroll. The header holds her seal, the
// step rail, the switcher (Drawing | Orbit) and the way to the history in her window; the chosen view
// fills the rest, and only that one is mounted. Before there is a draft the shell asks for the need.

import { useEffect, useMemo } from "react";
import type { StageView } from "../../lib/contract";
import { toggleAthena } from "../../lib/windows";
import { useMain } from "../store";
import { useShownPhase } from "./hooks";
import { useStageKeys, type StageKey } from "./keymap";
import { Describe, ReplyNotice, StageSeal, StepRail, UndoToast } from "./parts";
import { isPencil, sealOf, stepOf } from "./select";
import { useStage } from "./store";
import { ViewSwitch } from "./Switcher";
import type { Place, StageAction, StageState } from "./types";
import { VIEWS } from "./views";
import { STAGE_WORDS } from "./words";
import "./stage.css";

export interface StageScreenProps {
  state: StageState;
  dispatch: (action: StageAction) => void;
  place: (view: StageView, nodeId: string, place: Place) => void;
  /** Set when an invented example drives the stage (the preview harness); said on screen. */
  invented?: string;
  /** Overrides the shown reply phase (the harness steps to "slow" without waiting 8 s). */
  phase?: StageState["frame"]["phase"];
  onLeave?: () => void;
  onHistory?: () => void;
}

/** The stage on any state: the app drives it from the store, the preview harness from the fixture. */
export function StageScreen({ state, dispatch, place, invented, phase: forced, onLeave, onHistory }: StageScreenProps) {
  const words = STAGE_WORDS;
  const shown = useShownPhase(state.frame, state.work, state.heardAt);
  const phase = forced ?? shown;
  const frame = useMemo(() => (phase === state.frame.phase ? state.frame : { ...state.frame, phase }), [state.frame, phase]);
  const step = stepOf(state.draft);
  const seal = sealOf(state, phase);
  const View = VIEWS[state.view];
  const asking = step === "shape" && !!frame.ask && !state.work && phase === "idle";
  // a draft opened by its address: no describe form while it is read, or when it could not be
  const opening = state.work === "open" || state.failed?.type === "reload";

  useStageKeys({ step, asking, suggestions: frame.ask?.suggestions.length ?? 0 }, (key: StageKey, e) =>
    onKey(key, e, state, dispatch),
  );

  const dropping = useMemo(() => {
    const ids = new Set(state.dropping);
    return state.draft?.sketch.nodes.filter((n) => ids.has(n.id)).map((n) => n.label) ?? [];
  }, [state.draft, state.dropping]);

  return (
    <div className="st-stage" data-step={step} data-phase={phase}>
      <header className="st-head">
        <StageSeal state={seal.state} count={seal.count} label={seal.count ? "Athena, waiting on you" : "Athena"} />
        <span className="st-head__name">Athena</span>
        {invented && (
          <span className="badge" data-tone="warning" title={invented} data-role="invented">
            {words.invented}
          </span>
        )}
        <StepRail step={step} words={words} />
        <div className="st-head__tools">
          <ViewSwitch view={state.view} onSwitch={(view) => dispatch({ type: "switch_view", view })} words={words} />
          <button type="button" className="btn btn-quiet" title={words.historyHint} onClick={onHistory} data-role="history">
            {words.history}
          </button>
          {onLeave && (
            <button type="button" className="btn btn-quiet" onClick={onLeave}>
              {words.leave}
            </button>
          )}
        </div>
      </header>
      <div className="st-body">
        {state.draft ? (
          <View draft={state.draft} frame={frame} state={state} dispatch={dispatch} words={words} place={place} />
        ) : (
          <div className="st-describe">
            {opening ? (
              <ReplyNotice phase={phase === "failed" ? "idle" : "thinking"} problem="" onRetry={() => undefined} words={words} />
            ) : (
              <Describe
                sending={state.work === "describe"}
                sent={frame.youSaid}
                onDescribe={(need) => dispatch({ type: "describe", need })}
                words={words}
              />
            )}
            {phase === "failed" && (
              <p className="st-problem" role="alert">
                {frame.problem}{" "}
                {state.failed && (
                  <button type="button" className="btn" onClick={() => dispatch({ type: "retry" })}>
                    {words.retry}
                  </button>
                )}
              </p>
            )}
          </div>
        )}
      </div>
      <div className="st-toast">
        <UndoToast labels={dropping} onUndo={() => dispatch({ type: "undo_drop" })} words={words} />
      </div>
    </div>
  );
}

/** The focused piece, or the one whose card is open. */
function focusedNode(state: StageState): string | null {
  const el = document.activeElement instanceof HTMLElement ? document.activeElement.closest<HTMLElement>("[data-node-id]") : null;
  return el?.dataset.nodeId ?? state.card;
}

function checkCards(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>('[data-role="check-card"]')];
}

/** What a key does, for both views: the views mark their elements with the shared data hooks. */
function onKey(key: StageKey, e: KeyboardEvent, state: StageState, dispatch: (a: StageAction) => void): void {
  const d = state.draft;
  switch (key.type) {
    case "close":
      if (state.card) dispatch({ type: "close_card" });
      return;
    case "pick": {
      const choice = state.frame.ask?.suggestions[key.index];
      if (choice) dispatch({ type: "pick", choice });
      return;
    }
    case "ink":
    case "drop": {
      const id = focusedNode(state);
      const node = d?.sketch.nodes.find((n) => n.id === id);
      if (node && isPencil(node)) dispatch(key.type === "ink" ? { type: "ink", node_ids: [node.id] } : { type: "drop", node_ids: [node.id] });
      return;
    }
    case "mark": {
      const focused = e.target instanceof HTMLElement ? e.target.closest<HTMLElement>('[data-role="check-card"]') : null;
      const id = focused?.dataset.expectedId ?? d?.expected?.find((c) => !state.marks[c.id])?.id;
      if (id) dispatch({ type: "mark", expected_id: id, mark: key.mark });
      return;
    }
    case "move": {
      const cards = checkCards();
      if (!cards.length) return;
      const at = cards.findIndex((c) => c.contains(document.activeElement));
      const next = cards[Math.min(cards.length - 1, Math.max(0, at < 0 ? 0 : at + key.by))];
      next?.focus();
      return;
    }
  }
}

/** The stage on the app's store: opens the draft in the address and follows a new draft to its own. */
export function Stage({ id }: { id: string | null }) {
  const state = useStage();
  const navigate = useMain((s) => s.navigate);
  const draftId = state.draft?.id ?? null;
  const open = state.open;

  useEffect(() => {
    void open(id);
  }, [id, open]);

  useEffect(() => {
    // #stage/new became a draft: give it its own address (open() then finds it already on stage)
    const current = useStage.getState().draft;
    if (id === null && current && current.id === draftId) navigate({ view: "stage", id: current.id });
  }, [id, draftId, navigate]);

  return (
    <StageScreen
      state={state}
      dispatch={state.dispatch}
      place={state.place}
      onLeave={() => navigate({ view: "projects" })}
      onHistory={() => void toggleAthena()}
    />
  );
}
