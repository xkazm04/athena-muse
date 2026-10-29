// The switcher tab in the stage's header: Drawing | Orbit. A pure view change; the store keeps the
// draft, the frame, the open question and each view's places.

import type { StageView } from "../../lib/contract";
import type { StageWords } from "./words";

const ORDER: readonly StageView[] = ["drawing", "orbit"];

export interface ViewSwitchProps {
  view: StageView;
  onSwitch: (view: StageView) => void;
  words: StageWords;
}

export function ViewSwitch({ view, onSwitch, words }: ViewSwitchProps) {
  return (
    <div className="st-switch" role="tablist" aria-label={words.views} data-role="switcher">
      {ORDER.map((v) => (
        <button
          key={v}
          type="button"
          role="tab"
          className="st-switch__tab"
          data-view={v}
          aria-selected={v === view}
          tabIndex={v === view ? 0 : -1}
          onClick={() => v !== view && onSwitch(v)}
          onKeyDown={(e) => {
            if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
            e.preventDefault();
            const next = ORDER[(ORDER.indexOf(v) + 1) % ORDER.length]!;
            onSwitch(next);
            const tabs = e.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
            tabs?.[ORDER.indexOf(next)]?.focus();
          }}
        >
          {words.view[v]}
        </button>
      ))}
    </div>
  );
}
