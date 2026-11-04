// The plain words for the outside agents a person lets into a project (spark agent-leases), and the
// pure pieces of the connect form: which tool names the daemon offers for the project's apps, and the
// exact body a connect sends. The screen never says how an agent is spoken to; the one developer
// caption on the config block is the only exception.

import {
  AGENT_CALLS_MAX,
  AGENT_FILE_MB_MAX,
  AGENT_LABEL_MAX,
  AGENT_MINUTES_DEFAULT,
  APP_TOOL_NAME_MAX,
  type AgentLease,
  type AgentLeaseNew,
  type App,
  type AppTool,
} from "../../../lib/contract";
import { clockOf } from "../../../lib/time";
import { isProcess } from "../apps/words";

// --- tool names, as the daemon offers them (src/athena/apps/tools.py) ---

const SEPARATOR = "__";
const REMOTE = "_on_";
const NAME = /^[a-zA-Z0-9_-]{1,64}$/;

/** A device's name as a tool-name part: lowercase [a-z0-9_] ("Studio PC" -> "studio_pc"). Mirrors `device_slug`. */
export function deviceSlug(device: string): string {
  const slug = device
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return slug.replace(/_+/g, "_") || "device";
}

const fits = (name: string): boolean => name.length <= APP_TOOL_NAME_MAX && NAME.test(name);

/** One tool the daemon offers for a project's apps: its full name, the app (and paired computer) it is on. */
export interface OfferedTool {
  name: string;
  tool: AppTool;
  app: string;
  /** The paired computer's name for its copy; absent for this computer's. */
  device?: string;
}

/**
 * Every app tool the daemon offers in this project, in its order: `<slug>__<tool>` for this computer's
 * copy, `<slug>_on_<device>__<tool>` for a paired computer's. A name that does not fit is not offered;
 * a name taken twice is offered once (the first). Mirrors `_entries`.
 */
export function offeredTools(apps: readonly App[]): OfferedTool[] {
  const out = new Map<string, OfferedTool>();
  for (const app of apps) {
    if (!isProcess(app.kind)) continue;
    for (const tool of app.tools) {
      const name = `${app.slug}${SEPARATOR}${tool.name}`;
      if (fits(name) && !out.has(name)) out.set(name, { name, tool, app: app.label });
    }
    for (const remote of app.remotes) {
      const prefix = `${app.slug}${REMOTE}${deviceSlug(remote.device)}`;
      for (const tool of remote.tools) {
        const name = `${prefix}${SEPARATOR}${tool.name}`;
        if (fits(name) && !out.has(name)) out.set(name, { name, tool, app: app.label, device: remote.device });
      }
    }
  }
  return [...out.values()];
}

/** The tools that ask the person first: the only ones that may run without asking, once signed. */
export const askingTools = (apps: readonly App[]): OfferedTool[] => offeredTools(apps).filter((t) => t.tool.access === "gated");

export const whereOf = (t: Pick<OfferedTool, "app" | "device">): string => (t.device ? `${t.app} on ${t.device}` : t.app);

// --- what the agent may use: the collaboration set, in groups a person reads ---

export type Group = "apps" | "files" | "notes" | "report";
export const GROUP_ORDER: readonly Group[] = ["apps", "files", "notes", "report"];

export const GROUP_WORDS: Readonly<Record<Group, { name: string; hint: string }>> = {
  apps: { name: "The project's apps", hint: "It uses them the way Athena does: what asks you first still asks you first." },
  files: { name: "Bringing files home", hint: "It can bring a file an app made into the project's files, and see what is there." },
  notes: { name: "Notes", hint: "It can leave a note for the next agent, and read the ones left before." },
  report: { name: "The report", hint: "It can show the project's report." },
};

/** Fixed tools per group; the apps group adds the project's app tools by name. */
const GROUP_TOOLS: Readonly<Record<Exclude<Group, "apps">, readonly string[]>> = {
  files: ["app_fetch", "file_list"],
  notes: ["note_add", "note_list"],
  report: ["show_report"],
};
/** Always sent: how the agent reads your answer to what it asked. */
const ANSWERS = "card_status";

// --- the connect form ---

export const LENGTHS: readonly { minutes: number; words: string }[] = [
  { minutes: AGENT_MINUTES_DEFAULT, words: "30 min" },
  { minutes: 60, words: "1 h" },
  { minutes: 240, words: "4 h" },
];

export const CALLS_DEFAULT = 10;

export interface ConnectForm {
  label: string;
  minutes: number;
  groups: Record<Group, boolean>;
  /** "Let it run some calls without asking". */
  unattended: boolean;
  /** Full tool names ticked to run without asking. */
  free: string[];
  calls: string;
  freeMinutes: string;
  fileMb: string;
}

export const emptyForm = (): ConnectForm => ({
  label: "",
  minutes: AGENT_MINUTES_DEFAULT,
  groups: { apps: true, files: true, notes: true, report: true },
  unattended: false,
  free: [],
  calls: String(CALLS_DEFAULT),
  freeMinutes: String(AGENT_MINUTES_DEFAULT),
  fileMb: "",
});

const whole = (text: string): number | null => (/^\s*\d+\s*$/.test(text) ? Number(text.trim()) : null);

/** What is still wrong with the form, in plain words; "" when it can be sent. */
export function problemOf(form: ConnectForm): string {
  if (!form.label.trim()) return "Give it a name.";
  if (form.label.trim().length > AGENT_LABEL_MAX) return `A name is at most ${AGENT_LABEL_MAX} characters.`;
  if (!GROUP_ORDER.some((g) => form.groups[g])) return "Tick at least one thing it may use.";
  if (!form.unattended) return "";
  if (!form.free.length) return "Tick the calls it may run without asking.";
  const calls = whole(form.calls);
  if (calls === null || calls < 1 || calls > AGENT_CALLS_MAX) return `Calls without asking: a number from 1 to ${AGENT_CALLS_MAX}.`;
  const minutes = whole(form.freeMinutes);
  if (minutes === null || minutes < 1 || minutes > form.minutes) return `Minutes without asking: a number from 1 to ${form.minutes}.`;
  if (form.fileMb.trim()) {
    const mb = whole(form.fileMb);
    if (mb === null || mb < 1 || mb > AGENT_FILE_MB_MAX) return `Files without asking: a number of MB from 1 to ${AGENT_FILE_MB_MAX}, or leave it empty.`;
  }
  return "";
}

/**
 * The exact body a connect sends. Every group ticked sends no `tools`, so the daemon gives its own
 * collaboration set (which keeps up with tools an app gains later); fewer sends their names, and how
 * the agent reads your answers. The calls without asking are sent only when switched on.
 */
export function bodyOf(form: ConnectForm, apps: readonly App[]): AgentLeaseNew {
  const body: AgentLeaseNew = { label: form.label.trim(), minutes: form.minutes };
  if (!GROUP_ORDER.every((g) => form.groups[g])) {
    const tools: string[] = [];
    if (form.groups.apps) tools.push(...offeredTools(apps).map((t) => t.name));
    for (const g of ["files", "notes", "report"] as const) if (form.groups[g]) tools.push(...GROUP_TOOLS[g]);
    tools.push(ANSWERS);
    body.tools = tools;
  }
  if (form.unattended) {
    const offered = new Set(askingTools(apps).map((t) => t.name));
    body.ceiling = {
      tools: form.free.filter((n) => offered.has(n)),
      max_calls: Number(form.calls.trim()),
      minutes: Number(form.freeMinutes.trim()),
    };
    if (form.fileMb.trim()) body.ceiling.file_mb = Number(form.fileMb.trim());
  }
  return body;
}

// --- a connected agent's standing ---

export type Tone = "success" | "warning" | "error" | "info";

/** All the calls it may run without asking are spent (it still works; each call asks). */
export const usedUp = (lease: AgentLease): boolean =>
  !!lease.ceiling && lease.ceiling.signed && lease.ceiling.used >= lease.ceiling.max_calls;

export function standingOf(lease: AgentLease): { tone: Tone; words: string } {
  switch (lease.state) {
    case "waiting":
      return { tone: "warning", words: "Waiting for your signature to run calls unattended" };
    case "connected":
      return { tone: "success", words: `Connected, ends at ${clockOf(lease.expires)}` };
    default:
      return { tone: "info", words: "Ended" };
  }
}

/** "Calls without asking: 3 of 10 used", only once signed. */
export function usedLine(lease: AgentLease): string {
  const c = lease.ceiling;
  if (!c || !c.signed) return "";
  const spent = usedUp(lease) && lease.state !== "ended";
  return `Calls without asking: ${c.used} of ${c.max_calls} used${spent ? ". Each call asks you now." : ""}`;
}

export const notesLine = (n: number): string => `${n} ${n === 1 ? "note" : "notes"}`;
