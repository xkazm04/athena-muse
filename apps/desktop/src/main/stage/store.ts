// The stage's one model (onboarding v2). `reduce` folds the daemon's streams into StageState and is
// pure, so the generated fixture can drive it with no daemon. The view preference is per device.
// Stubbed by WP3-0: the signatures are final, the bodies arrive with WP3-1.

import { create } from "zustand";
import type { StageView } from "../../lib/contract";
import type { StageAction, StageEvent, StageFrame, StageState } from "./types";

export const VIEW_KEY = "athena.stage.view";
export const DEFAULT_VIEW: StageView = "drawing";

/** The view this device used last; storage may be blocked, so it falls back to the default. */
export function readView(): StageView {
  try {
    const v = localStorage.getItem(VIEW_KEY);
    return v === "drawing" || v === "orbit" ? v : DEFAULT_VIEW;
  } catch {
    return DEFAULT_VIEW;
  }
}

export function writeView(view: StageView): void {
  try {
    localStorage.setItem(VIEW_KEY, view);
  } catch {
    // a per-device convenience: when storage is blocked the stage still works on the default
  }
}

export const EMPTY_FRAME: StageFrame = { line: "", ask: null, youSaid: "", phase: "idle", problem: "", lastOps: [] };

export function initialStage(view: StageView = DEFAULT_VIEW): StageState {
  return {
    draft: null,
    frame: EMPTY_FRAME,
    view,
    places: { drawing: {}, orbit: {} },
    dropping: [],
    author: [],
    rehearsal: [],
    marks: {},
    missing: [],
    never: [],
  };
}

/** Folds one daemon event into the state. Pure. WP3-1 builds it; until then nothing changes. */
export function reduce(state: StageState, event: StageEvent): StageState {
  void event;
  return state;
}

interface StageStore extends StageState {
  /** Opens a draft by id, or starts `#stage/new` when null. */
  open: (draftId: string | null) => Promise<void>;
  dispatch: (action: StageAction) => void;
}

export const useStage = create<StageStore>()((set) => ({
  ...initialStage(readView()),
  open: async () => {},
  dispatch: (action) => {
    if (action.type === "switch_view") {
      writeView(action.view);
      set({ view: action.view });
    }
  },
}));
