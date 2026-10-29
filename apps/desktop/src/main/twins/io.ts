// The daemon routes the twins page uses, as one interface: the live one is lib/api; the example one
// plays the generated fixture (example.ts). Tests hand in either.

import * as api from "../../lib/api";
import { ROUTES, type Card, type DecisionBody, type TwinSayBody } from "../../lib/contract";
import { request } from "../../lib/daemon";

/**
 * POST /decisions/{card_id} with the person's own words. lib/api's `decide` takes a verdict only; the
 * contract's DecisionBody also carries `edited` for a twin draft's card (reported for api.ts).
 */
export const decideDraft = (cardId: string, body: DecisionBody) =>
  request<Card>("POST", ROUTES.decision.replace("{card_id}", encodeURIComponent(cardId)), body);

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
  | "mission"
  | "connect"
  | "connectFlow"
> & {
  decideDraft: typeof decideDraft;
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
  mission: api.mission,
  connect: api.connect,
  connectFlow: api.connectFlow,
  decideDraft,
};
