import { useEffect, useRef, type MouseEvent } from "react";
import { hideThisWindow, isTauri, startDrag } from "../lib/windows";
import { Seal } from "../theme";
import { ProjectPill, useAppEvents } from "../ui";
import { Composer } from "./Composer";
import { STATE_WORDS, sealOf, useHer, waitingCount } from "./store";
import { Transcript } from "./Transcript";
import "./her.css";

// Pressing on these must do their own thing, never start a window drag.
const NO_DRAG = "button, a, input, textarea, select, [role='menu']";

function Head() {
  const seal = useHer(sealOf);
  const count = useHer(waitingCount);
  const settle = useHer((s) => s.settle);
  const spaces = useHer((s) => s.spaces);
  const activeId = useHer((s) => s.activeId);
  const pendingId = useHer((s) => s.pendingId);
  const select = useHer((s) => s.select);
  const words = STATE_WORDS[seal];

  const onMouseDown = (e: MouseEvent<HTMLElement>) => {
    if (e.button !== 0 || (e.target as Element).closest(NO_DRAG)) return;
    void startDrag();
  };

  return (
    <header className="her-head" onMouseDown={onMouseDown}>
      <Seal
        state={seal}
        size={56}
        count={count}
        label={count > 0 ? `Athena - ${words}, ${count} waiting` : `Athena - ${words}`}
        onSettled={settle}
      />
      <div className="her-who">
        <h1 className="her-name">Athena</h1>
        <p className="her-state" data-state={seal}>
          {words}
        </p>
      </div>
      <ProjectPill compact spaces={spaces} activeId={activeId} pendingId={pendingId} onSelect={(id) => void select(id)} />
      <button type="button" className="her-hide" aria-label="Hide Athena" title="Hide (Esc)" onClick={() => void hideThisWindow()}>
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
          <path d="M4 4 L12 12 M12 4 L4 12" />
        </svg>
      </button>
    </header>
  );
}

export function App() {
  const boot = useHer((s) => s.boot);
  const onEvent = useHer((s) => s.onEvent);
  const simulated = useHer((s) => s.engine?.simulated === true);
  const streaming = useHer((s) => s.streaming);
  const composer = useRef<HTMLTextAreaElement>(null);

  useAppEvents(onEvent);

  useEffect(() => {
    void boot();
  }, [boot]);

  // When she is shown (the shortcut, or a click on her), the person can type at once.
  useEffect(() => {
    const onFocus = () => composer.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      // Escape first closes the project menu; only a second one puts her away.
      if (e.key !== "Escape" || !isTauri() || document.querySelector(".pill-menu")) return;
      void hideThisWindow();
    };
    window.addEventListener("focus", onFocus);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  // The composer is disabled while she writes; hand focus back when she is done.
  useEffect(() => {
    if (!streaming) composer.current?.focus();
  }, [streaming]);

  return (
    <main className="her-app coat">
      <Head />
      {simulated && (
        <p className="her-band" role="note">
          Simulated - connect Muse in the main window for real answers
        </p>
      )}
      <Transcript />
      <Composer ref={composer} />
    </main>
  );
}
