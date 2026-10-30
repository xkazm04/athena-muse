// Hash routes of the main window. `core` stands for the core space in a path (the wire's "").
// A leading slash is accepted (`#/chores`) and written without one, like every other route.

import { CORE, CORE_ITEM } from "../lib/contract";

export type Route =
  | { view: "projects" }
  | { view: "project"; id: string }
  | { view: "core" }
  | { view: "memory"; id: string }
  | { view: "athena" }
  | { view: "chores" }
  | { view: "chore"; id: string }
  /** The stage (onboarding v2): a draft by id, or `null` for `#stage/new`, the describe step. */
  | { view: "stage"; id: string | null }
  /** The twins page (Passport): the stat strip, the wallet and the ledger. */
  | { view: "twins" }
  /** One twin: its setup while it is being issued (`null` for `#twin/new`), else its open document. */
  | { view: "twin"; id: string | null }
  /** The nested pages: its voice, one mission as a script, one draft beside the message it answers, and
   * the new entry (giving it a mission). */
  | { view: "twin_voice"; id: string }
  | { view: "twin_entry"; id: string }
  | { view: "twin_mission"; id: string; mission: string }
  | { view: "twin_draft"; id: string; draft: string };

/** `id` is a space id or CORE (""). */
export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "athena") return { view: "athena" };
  if (parts[0] === "chores") return parts[1] ? { view: "chore", id: parts[1] } : { view: "chores" };
  if (parts[0] === "stage") return { view: "stage", id: parts[1] && parts[1] !== STAGE_NEW ? parts[1] : null };
  if (parts[0] === "twins") return { view: "twins" };
  if (parts[0] === "twin") return twinRoute(parts.slice(1));
  if (parts[0] !== "projects" || parts.length === 1) return { view: "projects" };
  const ref = parts[1] ?? "";
  const id = ref === CORE_ITEM ? CORE : ref;
  if (parts[2] === "memory") return { view: "memory", id };
  if (id === CORE) return { view: "core" };
  return { view: "project", id };
}

/** `#stage/new`: the describe step, before there is a draft. */
export const STAGE_NEW = "new";
/** `#twin/new`: a twin's describe step, before there is a twin. */
export const TWIN_NEW = "new";

function twinRoute([id, what, sub]: string[]): Route {
  if (!id) return { view: "twins" };
  if (id === TWIN_NEW) return { view: "twin", id: null };
  if (what === "voice") return { view: "twin_voice", id };
  if (what === "entry") return { view: "twin_entry", id };
  if (what === "mission" && sub) return { view: "twin_mission", id, mission: sub };
  if (what === "draft" && sub) return { view: "twin_draft", id, draft: sub };
  return { view: "twin", id };
}

/** The twins page and its nested pages, which share one store and one stylesheet. */
export const isTwinRoute = (r: Route): r is Extract<Route, { view: `twin${string}` }> => r.view.startsWith("twin");

const ref = (id: string) => (id === CORE ? CORE_ITEM : encodeURIComponent(id));

export function toHash(route: Route): string {
  switch (route.view) {
    case "athena":
      return "#athena";
    case "chores":
      return "#chores";
    case "chore":
      return `#chores/${encodeURIComponent(route.id)}`;
    case "stage":
      return `#stage/${route.id === null ? STAGE_NEW : encodeURIComponent(route.id)}`;
    case "twins":
      return "#twins";
    case "twin":
      return `#twin/${route.id === null ? TWIN_NEW : encodeURIComponent(route.id)}`;
    case "twin_voice":
      return `#twin/${encodeURIComponent(route.id)}/voice`;
    case "twin_entry":
      return `#twin/${encodeURIComponent(route.id)}/entry`;
    case "twin_mission":
      return `#twin/${encodeURIComponent(route.id)}/mission/${encodeURIComponent(route.mission)}`;
    case "twin_draft":
      return `#twin/${encodeURIComponent(route.id)}/draft/${encodeURIComponent(route.draft)}`;
    case "core":
      return "#projects/core";
    case "project":
      return `#projects/${ref(route.id)}`;
    case "memory":
      return `#projects/${ref(route.id)}/memory`;
    default:
      return "#projects";
  }
}

/** The space a route is about, when it is about one project (not core). */
export function routeSpace(route: Route): string | undefined {
  if ((route.view === "project" || route.view === "memory") && route.id !== CORE) return route.id;
  return undefined;
}
