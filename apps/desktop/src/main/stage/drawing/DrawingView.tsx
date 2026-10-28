// The Drawing view: a port of the contest's A/1 "Pencil & Ink" (WP3-2). The sketch fills the window
// as territories; her guesses are pencil, the person inks them; the question is a note pinned below.
// Stubbed by WP3-0 so the shared stage and the Orbit view can build against it.

import type { StageViewProps } from "../types";

export function DrawingView({ words }: StageViewProps) {
  return <section data-stage-view="drawing" aria-label={words.view.drawing} />;
}
