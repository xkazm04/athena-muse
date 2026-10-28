// The two views behind the stage's switch. Only the chosen one is mounted.

import type { ComponentType } from "react";
import type { StageView } from "../../lib/contract";
import { DrawingView } from "./drawing/DrawingView";
import { OrbitView } from "./orbit/OrbitView";
import type { StageViewProps } from "./types";

export const VIEWS: Record<StageView, ComponentType<StageViewProps>> = {
  drawing: DrawingView,
  orbit: OrbitView,
};
