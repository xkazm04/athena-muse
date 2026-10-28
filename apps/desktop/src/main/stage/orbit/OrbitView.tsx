// The Orbit view: a port of the contest's A/3 "Orbit" (WP3-3). The question card is the centre and
// the largest thing on screen; what she has understood circles it in six zones.
// Stubbed by WP3-0 so the shared stage and the Drawing view can build against it.

import type { StageViewProps } from "../types";

export function OrbitView({ words }: StageViewProps) {
  return <section data-stage-view="orbit" aria-label={words.view.orbit} />;
}
