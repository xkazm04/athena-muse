// What Settings says about this computer, derived from the daemon's answer at render (ADR 0012).
//
// Ported from portable's setup module (its `readiness.ts`): the one place the facts become words, so
// the overview and a level cannot disagree, and no verdict is stored that could have been read. A
// surface that kept "the engine is ready" after the program was uninstalled is not a state this
// file can reach: every fact is recomputed from the last `SettingsView` and connection list.

import type { DevicesView } from "../../lib/fleet";
import type {
  Connection,
  EngineId,
  EngineOption,
  Look,
  MotionChoice,
  SettingsView,
  ThemeChoice,
  TypeScale,
} from "../../lib/contract";

/** The overview's tiles, in the order a person wants them resolved. */
export const ITEMS = ["engine", "look", "accounts", "data", "devices"] as const;
export type Item = (typeof ITEMS)[number];

export function isItem(name: string): name is Item {
  return (ITEMS as readonly string[]).includes(name);
}

export const ITEM_NAME: Record<Item, string> = {
  engine: "Engine",
  look: "Look",
  accounts: "Accounts",
  data: "Data",
  devices: "Devices",
};

/**
 * Four words. `unknown` is the one a boolean could not say: the daemon has not answered, which is not
 * the same fact as nothing being set.
 */
export type Standing = "done" | "todo" | "missing" | "unknown";

export const STANDING_WORD: Record<Standing, string> = {
  done: "set",
  todo: "not yet",
  missing: "needs you",
  unknown: "checking",
};

/** The badge tone beside the word; "not yet" is no state at all, so it has none. */
export const STANDING_TONE: Record<Standing, string | undefined> = {
  done: "success",
  todo: undefined,
  missing: "warning",
  unknown: "info",
};

export interface Fact {
  /** `null` for a tile that has a word but no standing (the look, the data). */
  standing: Standing | null;
  word: string;
  line: string;
}

export const ENGINE_LABEL: Record<EngineId, string> = {
  muse: "Muse",
  muse_code: "Muse Code",
  claude_code: "Claude Code",
  scripted: "Simulated",
};

export const ENGINE_HINT: Record<EngineId, string> = {
  muse: "Meta's API, on your key. Every call is metered in the ledger.",
  muse_code: "Muse Code on your own plan, through the `muse` program.",
  claude_code: "Claude Code on your own plan, through the `claude` program.",
  scripted: "No model at all: replies are simulated and labelled as such.",
};

export const THEME_HINT: Record<ThemeChoice, string> = {
  auto: "Follow the system, and switch when it does.",
  dark: "Night water, whatever the system says.",
  light: "Pale water, whatever the system says.",
};

export const TYPE_SCALE_HINT: Record<TypeScale, string> = {
  standard: "The sizes Loop Tide is drawn at.",
  large: "Two pixels more on everything under the headings.",
};

export const MOTION_HINT: Record<MotionChoice, string> = {
  system: "Follow the system's reduced-motion setting.",
  calm: "Nothing drifts or eases; every change lands at once.",
};

const fact = (standing: Standing | null, line: string, word?: string): Fact => ({
  standing,
  word: word ?? (standing ? STANDING_WORD[standing] : ""),
  line,
});

export function optionOf(view: SettingsView, id: EngineId): EngineOption | undefined {
  return view.engines.find((o) => o.id === id);
}

/** Why an engine cannot be picked here, shown on the control; `undefined` when it can. */
export function engineBlocked(view: SettingsView, id: EngineId): string | undefined {
  const option = optionOf(view, id);
  if (option && (option.readiness === "no_key" || option.readiness === "not_installed")) return option.reason;
  return undefined;
}

/**
 * The engine her next turn runs on, in words. "Ready" here means found (a key on file, a program on
 * PATH); whether Meta accepts the key is the probe's to say, and the engine level offers it.
 */
export function engineFact(view: SettingsView | null): Fact {
  if (!view) return fact("unknown", "Athena has not said which engine she is on yet.");
  const label = ENGINE_LABEL[view.engine];
  const option = optionOf(view, view.engine);
  const blocked = option && option.readiness !== "ready" && option.readiness !== "simulated";
  if (view.choice && view.choice !== view.engine) {
    const chosen = optionOf(view, view.choice);
    return fact(
      "missing",
      `${ENGINE_LABEL[view.choice]} is chosen but cannot run here. ${said(chosen?.reason)} ${label} runs her turns until it can.`,
    );
  }
  if (view.engine === "scripted") {
    return view.source === "setting"
      ? fact("todo", "Simulated is chosen: no model runs, and every reply says so.")
      : fact("todo", "No engine yet: replies are simulated until you add a Meta key or install Claude Code or Muse Code.");
  }
  if (blocked) {
    const who = view.source === "env" ? `ATHENA_ENGINE sets ${label}.` : `${label} is chosen.`;
    return fact("missing", `${who} ${said(option?.reason)}`);
  }
  if (view.source === "env") return fact("done", `${label} runs her turns, set by ATHENA_ENGINE until you choose here.`);
  if (view.source === "default") return fact("done", `${label} runs her turns, picked because nothing is chosen yet.`);
  return fact("done", `${label} runs her turns.`);
}

export function lookFact(look: Look | null): Fact {
  if (!look) return fact("unknown", "The look has not been read yet.");
  return fact(
    null,
    `Theme ${look.theme}, ${look.type_scale} text, ${look.motion === "calm" ? "calm" : "system"} motion.`,
    `${look.theme} theme`,
  );
}

const ACCOUNT_LABEL: Record<Connection["kind"], string> = { gmail: "Gmail", notion: "Notion" };

export function accountLabel(kind: Connection["kind"]): string {
  return ACCOUNT_LABEL[kind];
}

/** Connected accounts (ADR 0008): read here, connected and changed where a twin is set up. */
export function accountsFact(connections: readonly Connection[] | null, problem = ""): Fact {
  if (problem) return fact("unknown", `The accounts could not be read: ${problem}`);
  if (!connections) return fact("unknown", "The accounts have not been read yet.");
  const lapsed = connections.filter((c) => c.status === "needs_sign_in");
  if (lapsed.length > 0) {
    return fact("missing", `${lapsed.map((c) => accountLabel(c.kind)).join(" and ")} needs you to sign in again.`);
  }
  const on = connections.filter((c) => c.status === "connected").length;
  if (on === 0) return fact("todo", "No account connected. A twin connects Gmail and Notion when it needs them.");
  return fact("done", `${on} of ${connections.length} connected.`);
}

export function dataFact(view: SettingsView | null): Fact {
  if (!view) return fact("unknown", "Athena has not said where she keeps her files yet.");
  return view.data_dir
    ? fact(null, "Everything she keeps is in one folder on this computer.", "local")
    : fact(null, "Nothing is kept on disk: this daemon runs in memory.", "in memory");
}

/** The daemon's reason as a sentence of its own, verbatim. */
function said(text: string | undefined): string {
  if (!text) return "It cannot run here.";
  return /[.!?]$/.test(text) ? text : `${text}.`;
}

/**
 * The other computers and phones (ADR 0017), worded from `GET /devices`. `null` is "not read": the
 * daemon did not answer, which is not the same fact as nothing being paired.
 */
export function devicesFact(view: DevicesView | null): Fact {
  if (!view || !Array.isArray(view.peers)) return fact("unknown", "Athena has not said which devices are paired yet.");
  const waiting = view.pending.length;
  if (waiting > 0) {
    return fact("missing", `${waiting} ${waiting === 1 ? "device is" : "devices are"} waiting for you to let ${waiting === 1 ? "it" : "them"} in.`, `${waiting} waiting for you`);
  }
  const paired = view.peers.length;
  if (paired === 0) return fact("todo", "No other device is paired. Add a phone or another computer and they share one Athena.", "No other device paired");
  return fact("done", `${view.self.name} is paired with ${paired} other ${paired === 1 ? "device" : "devices"}.`, `${paired} paired`);
}
