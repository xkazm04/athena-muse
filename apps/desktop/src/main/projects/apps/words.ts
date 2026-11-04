// The plain words for apps by kind (ADR 0025, 0026). The wire names its kinds for the daemon; the
// screen names them for a person and never says how an app is spoken to.

import type { ActionClass, App, AppKind, AppNew, AppStatus } from "../../../lib/contract";

export const KIND_WORDS: Readonly<Record<AppKind, string>> = {
  website: "A website",
  local_page: "A page on this computer",
  mcp_http: "An app on this computer",
  mcp_stdio: "A tool she starts",
};

/** One line under each choice in the kind chooser. */
export const KIND_HINTS: Readonly<Record<AppKind, string>> = {
  website: "A site on the internet. Athena opens it in her browser.",
  local_page: "A web page served on this computer, such as one a project runs while you work on it.",
  mcp_http: "A program on this computer that answers Athena at its own address.",
  mcp_stdio: "A program Athena starts herself, from a command, when she needs it.",
};

export const KIND_ORDER: readonly AppKind[] = ["website", "local_page", "mcp_http", "mcp_stdio"];
/** The kinds that run as a program; only these have tools, instances, and can be offered to another computer. */
export const PROCESS_KINDS: readonly AppKind[] = ["mcp_http", "mcp_stdio"];
export const isProcess = (kind: AppKind): boolean => PROCESS_KINDS.includes(kind);

export type Tone = "success" | "warning" | "error" | "info";

/** What the last look found. Not looked at yet is never "fine". */
export function statusOf(status: AppStatus): { tone: Tone; words: string } {
  switch (status) {
    case "ok":
      return { tone: "success", words: "ok" };
    case "unreachable":
      return { tone: "warning", words: "can't reach" };
    case "refused":
      return { tone: "error", words: "refused" };
    default:
      return { tone: "info", words: "not checked yet" };
  }
}

export const ACCESS_WORDS: Readonly<Record<ActionClass, string>> = {
  auto: "on its own",
  gated: "asks you first",
};

export const toolsLine = (app: Pick<App, "tools">): string =>
  `${app.tools.length} ${app.tools.length === 1 ? "tool" : "tools"}`;

/**
 * The tool kind's command: one argument per line; a single line is split at its spaces. Blank lines
 * are dropped, so a trailing newline changes nothing.
 */
export function argvOf(text: string): string[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length === 1) return lines[0]!.split(/\s+/);
  return lines;
}

/** The fields of the kind-first form, as typed. */
export interface AppForm {
  address: string;
  key: string;
  command: string;
  label: string;
  outputDir: string;
  offered: boolean;
}

export const EMPTY_FORM: AppForm = { address: "", key: "", command: "", label: "", outputDir: "", offered: false };

/**
 * The POST body for one kind: an address for the web kinds and the app on this computer, an access
 * key only for that app, argv only for the tool. `device` adds the offer switch (device level only).
 */
export function bodyOf(kind: AppKind, form: AppForm, device = false): AppNew {
  const body: AppNew = { kind };
  const label = form.label.trim();
  const outputDir = form.outputDir.trim();
  if (kind === "mcp_stdio") body.argv = argvOf(form.command);
  else body.address = form.address.trim();
  if (kind === "mcp_http" && form.key) body.token = form.key;
  if (isProcess(kind)) {
    if (label) body.label = label;
    if (outputDir) body.output_dir = outputDir;
  }
  if (device) body.offered = form.offered;
  return body;
}

/** Whether the form holds enough to send. */
export function ready(kind: AppKind, form: AppForm): boolean {
  return kind === "mcp_stdio" ? argvOf(form.command).length > 0 : form.address.trim().length > 0;
}
