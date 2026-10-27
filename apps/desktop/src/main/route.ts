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
  | { view: "chore"; id: string };

/** `id` is a space id or CORE (""). */
export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "athena") return { view: "athena" };
  if (parts[0] === "chores") return parts[1] ? { view: "chore", id: parts[1] } : { view: "chores" };
  if (parts[0] !== "projects" || parts.length === 1) return { view: "projects" };
  const ref = parts[1] ?? "";
  const id = ref === CORE_ITEM ? CORE : ref;
  if (parts[2] === "memory") return { view: "memory", id };
  if (id === CORE) return { view: "core" };
  return { view: "project", id };
}

const ref = (id: string) => (id === CORE ? CORE_ITEM : encodeURIComponent(id));

export function toHash(route: Route): string {
  switch (route.view) {
    case "athena":
      return "#athena";
    case "chores":
      return "#chores";
    case "chore":
      return `#chores/${encodeURIComponent(route.id)}`;
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
