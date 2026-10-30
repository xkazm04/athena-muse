// The daemon routes the twins page uses, as one interface: the live one is lib/api; the example one
// plays the generated fixture (example.ts). Tests hand in either.

import * as api from "../../lib/api";
import type { TwinSayBody } from "../../lib/contract";

export type TwinsIo = Pick<
  typeof api,
  | "twins"
  | "twin"
  | "createTwin"
  | "twinSay"
  | "twinConfirm"
  | "twinSamples"
  | "twinDials"
  | "twinPages"
  | "twinChores"
  | "twinAutonomy"
  | "twinMemory"
  | "twinRehearse"
  | "twinMark"
  | "twinGoLive"
  | "twinPreview"
  | "mission"
  | "connect"
  | "connectFlow"
  | "decide"
> & {
  /** The example only: a quiet note when the person's answer differs from the path it plays. */
  noteFor?: (body: TwinSayBody) => string;
  /** The example only: "now" for its relative times. */
  now?: () => Date;
};

export const liveIo: TwinsIo = {
  twins: api.twins,
  twin: api.twin,
  createTwin: api.createTwin,
  twinSay: api.twinSay,
  twinConfirm: api.twinConfirm,
  twinSamples: api.twinSamples,
  twinDials: api.twinDials,
  twinPages: api.twinPages,
  twinChores: api.twinChores,
  twinAutonomy: api.twinAutonomy,
  twinMemory: api.twinMemory,
  twinRehearse: api.twinRehearse,
  twinMark: api.twinMark,
  twinGoLive: api.twinGoLive,
  twinPreview: api.twinPreview,
  mission: api.mission,
  connect: api.connect,
  connectFlow: api.connectFlow,
  decide: api.decide,
};
