import { useEffect, type MouseEvent } from "react";
import { hideThisWindow, isTauri, onHanded, onSetupStart, startDrag } from "../lib/windows";
import { Spread } from "../spread/Spread";
import { useAppEvents } from "../ui";
import { useHer } from "./store";
import "./her.css";

// Pressing on these must do their own thing, never start a window drag.
const NO_DRAG = "button, a, input, textarea, select, [role='menu']";

function Hide() {
  return (
    <button type="button" className="her-hide" aria-label="Hide Athena" title="Hide (Esc)" onClick={() => void hideThisWindow()}>
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
        <path d="M4 4 L12 12 M12 4 L4 12" />
      </svg>
    </button>
  );
}

const drag = (e: MouseEvent<HTMLElement>) => {
  if (e.button !== 0 || (e.target as Element).closest(NO_DRAG)) return;
  void startDrag();
};

/** Her window (ADR 0024): the conversation as a book folded to one page. */
export function App() {
  const boot = useHer((s) => s.boot);
  const onEvent = useHer((s) => s.onEvent);

  useAppEvents(onEvent);

  useEffect(() => {
    void boot();
  }, [boot]);

  // The surface's ask (ADR 0016): the main window hands words over and shows this window.
  const hand = useHer((s) => s.hand);
  useEffect(() => {
    let off: (() => void) | undefined;
    let live = true;
    void onHanded((text) => void hand(text)).then((fn) => (live ? (off = fn) : fn()));
    return () => {
      live = false;
      off?.();
    };
  }, [hand]);

  // "Set up with Athena" (ADR 0017): the main window shows this one and she speaks first.
  const beginSetup = useHer((s) => s.beginSetup);
  useEffect(() => {
    let off: (() => void) | undefined;
    let live = true;
    void onSetupStart(() => void beginSetup()).then((fn) => (live ? (off = fn) : fn()));
    return () => {
      live = false;
      off?.();
    };
  }, [beginSetup]);

  // Escape first closes the project menu; only a second one puts her away.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || !isTauri() || document.querySelector(".pill-menu")) return;
      void hideThisWindow();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <main className="her-app coat">
      <Spread layout="folded" pill chrome={<Hide />} onHeadMouseDown={drag} />
    </main>
  );
}
