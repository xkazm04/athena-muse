// The main window's frame (ADR 0016), after the variant the owner chose: no top nav. A thin bar at
// the top says where you are (rise one level, the mark, the trail), a rail down the left marks how
// deep you are, and a dock at the bottom holds her pill and the five places. The surface (home) has
// no dock: its tiles are the places.

import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { CORE } from "../../lib/contract";
import { toggleAthena } from "../../lib/windows";
import { Backdrop, Seal } from "../../theme";
import { ProjectPill } from "../../ui";
import { isTwinRoute, type Route } from "../route";
import { ENGINE_LABEL } from "../settings/model";
import { useMain } from "../store";
import { useTwins } from "../twins/store";
import "./depth.css";
import "./idiom.css";

/** The five places, in the dock's order and the surface's. */
export const PLACES = [
  { key: "projects", label: "Projects", route: { view: "projects" } },
  { key: "chores", label: "Chores", route: { view: "chores" } },
  { key: "twins", label: "Twins", route: { view: "twins" } },
  { key: "athena", label: "Athena", route: { view: "athena" } },
  { key: "settings", label: "Settings", route: { view: "settings", item: null } },
] as const satisfies readonly { key: string; label: string; route: Route }[];

export type PlaceKey = (typeof PLACES)[number]["key"];

/** Which place a route belongs to; `null` on the surface. */
export function placeOf(route: Route): PlaceKey | null {
  switch (route.view) {
    case "home":
      return null;
    case "chores":
    case "chore":
    case "stage":
      return "chores";
    case "athena":
      return "athena";
    case "settings":
      return "settings";
    default:
      return isTwinRoute(route) ? "twins" : "projects";
  }
}

/** How deep a route sits: the surface 0, a place 1, one thing in it 2, a page under that 3. */
export function depthOf(route: Route): 0 | 1 | 2 | 3 {
  switch (route.view) {
    case "home":
      return 0;
    case "projects":
    case "chores":
    case "twins":
    case "athena":
      return 1;
    case "settings":
      return route.item === null ? 1 : 2;
    case "memory":
    case "twin_voice":
    case "twin_entry":
    case "twin_mission":
    case "twin_draft":
      return 3;
    default:
      return 2;
  }
}

export interface Crumb {
  label: string;
  route: Route;
}

export interface Names {
  space: (id: string) => string;
  chore: (id: string) => string;
  twin: (id: string) => string;
}

/** The trail after the mark: each place and level down to the current one (the last is "here"). */
export function trailOf(route: Route, names: Names): Crumb[] {
  const place = PLACES.find((p) => p.key === placeOf(route));
  if (!place) return [];
  const root: Crumb = { label: place.label, route: place.route };
  switch (route.view) {
    case "project":
      return [root, { label: names.space(route.id), route }];
    case "core":
      return [root, { label: "Core", route }];
    case "memory": {
      const level: Route = route.id === CORE ? { view: "core" } : { view: "project", id: route.id };
      return [root, { label: route.id === CORE ? "Core" : names.space(route.id), route: level }, { label: "Memory", route }];
    }
    case "chore":
      return [root, { label: names.chore(route.id), route }];
    case "stage":
      return [root, { label: route.id === null ? "Describe a need" : "A new chore", route }];
    case "settings":
      return route.item === null ? [root] : [root, { label: SETTING_NAMES[route.item] ?? route.item, route }];
    case "twin":
      return [root, { label: route.id === null ? "A new twin" : names.twin(route.id), route }];
    case "twin_voice":
    case "twin_entry":
    case "twin_mission":
    case "twin_draft": {
      const leaf = { twin_voice: "Its voice", twin_entry: "A mission", twin_mission: "Mission", twin_draft: "Draft" }[route.view];
      return [root, { label: names.twin(route.id), route: { view: "twin", id: route.id } }, { label: leaf, route }];
    }
    default:
      return [root];
  }
}

const SETTING_NAMES: Record<string, string> = { engine: "Engine", look: "Look", accounts: "Accounts", data: "Data" };

function useNames(): Names {
  const spaces = useMain((s) => s.spaces);
  const chores = useMain((s) => s.chores);
  const twins = useTwins((s) => s.page?.twins);
  return {
    space: (id) => spaces.find((s) => s.id === id)?.name ?? "A project",
    chore: (id) => (Array.isArray(chores) ? chores : []).find((c) => c.id === id)?.short_title ?? "A chore",
    twin: (id) => twins?.find((t) => t.id === id)?.name ?? "A twin",
  };
}

/** The Athena mark: the A in a rounded square, the variant's brand. */
export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg className="m-mark" viewBox="0 0 32 32" width={size} height={size} aria-hidden="true" focusable="false">
      <rect x="1.5" y="1.5" width="29" height="29" rx="8" />
      <g>
        <path d="M8.6 24.4 16 7.4l7.4 17" />
        <path d="M11.9 19.2l3.2 3 5.2-6.2" strokeWidth="2.3" />
      </g>
    </svg>
  );
}

/** The engine lamp: simulated is always labelled (AGENTS.md); a real engine is named, so a run on Claude Code never reads as Muse. */
export function Lamp() {
  const engine = useMain((s) => s.engine);
  if (!engine) return null;
  return engine.simulated ? (
    <span className="badge m-lamp" data-tone="warning" title="No Muse key; replies are simulated">
      Simulated
    </span>
  ) : (
    <span className="badge m-lamp" data-tone="success" title={engine.model}>
      {ENGINE_LABEL[engine.engine]}
    </span>
  );
}

/** The bar at the top: rise one level, the mark, the trail; the project pill and the lamp trail it. */
export function Crumbs({ route, extra }: { route: Route; extra?: ReactNode }) {
  const navigate = useMain((s) => s.navigate);
  const spaces = useMain((s) => s.spaces);
  const active = useMain((s) => s.active);
  const setActive = useMain((s) => s.setActive);
  const trail = trailOf(route, useNames());
  const parent: Crumb = trail.length > 1 ? trail[trail.length - 2]! : { label: "Athena", route: { view: "home" } };

  return (
    <header className="m-bar">
      {route.view !== "home" && (
        <button type="button" className="m-bar__rise" onClick={() => navigate(parent.route)}>
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">
            <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" />
          </svg>
          <span>
            Rise to <b>{parent.label}</b>
          </span>
        </button>
      )}
      <a className="m-bar__brand" href="#home" aria-label="Athena, back to the surface">
        <Mark />
        <span>Athena</span>
      </a>
      <nav className="m-bar__crumbs" aria-label="Where you are">
        {trail.map((c, i) => (
          <span key={i} className="m-bar__crumb">
            <span aria-hidden="true">/</span>
            {i === trail.length - 1 ? (
              <b aria-current="location">{c.label}</b>
            ) : (
              <button type="button" onClick={() => navigate(c.route)}>
                {c.label}
              </button>
            )}
          </span>
        ))}
      </nav>
      <div className="m-bar__trailing">
        <span id={BAR_SLOT} className="m-bar__slot" />
        {extra}
        <ProjectPill spaces={spaces} activeId={active} onSelect={(id) => void setActive(id)} />
        <Lamp />
      </div>
    </header>
  );
}

const BAR_SLOT = "m-bar-slot";

/** Puts a page's own label (the twins' "Invented example") in the bar, beside the engine lamp. */
export function InBar({ children }: { children: ReactNode }) {
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  useEffect(() => setSlot(document.getElementById(BAR_SLOT)), []);
  return slot ? createPortal(children, slot) : null;
}

/** The depth rail down the left: four marks, the reached ones lit, a bead at the current depth. */
export function Rail({ depth }: { depth: number }) {
  return (
    <aside className="m-rail" aria-hidden="true" data-depth={depth}>
      <div className="m-rail__line">
        {[0, 1, 2, 3].map((d) => (
          <i key={d} data-reached={d <= depth ? "true" : "false"} />
        ))}
        <b />
      </div>
    </aside>
  );
}

/** Her state in the dock's words. */
export function stateWords(waiting: number): string {
  return waiting > 0 ? `${waiting} waiting on you` : "resting";
}

/** The dock: her pill (opens her window) at the left, the five places at the right. */
export function Dock({ route }: { route: Route }) {
  const waiting = useMain((s) => s.waiting.length);
  const here = placeOf(route);
  return (
    <footer className="m-dock">
      <button
        type="button"
        className="m-dock__athena"
        aria-label="Talk to Athena"
        title="Talk to Athena: her own window"
        onClick={() => void toggleAthena()}
      >
        <Seal state={waiting > 0 ? "waiting" : "rest"} size={34} count={waiting} label={waiting > 0 ? `${waiting} waiting on you` : "Athena"} />
        <span>
          <b>Athena</b>
          {waiting > 0 ? <em>{stateWords(waiting)}</em> : <small>{stateWords(waiting)}</small>}
        </span>
      </button>
      <nav className="m-dock__places" aria-label="Main">
        {PLACES.map((p) => (
          <a
            key={p.key}
            href={p.key === "settings" ? "#settings" : `#${p.key}`}
            className="m-dock__place"
            aria-current={here === p.key ? "page" : undefined}
          >
            {p.label}
          </a>
        ))}
      </nav>
    </footer>
  );
}

/** One frame for every route: the water, the bar, the rail, the body, and (below the surface) the dock. */
export function DepthFrame({ route, extra, children }: { route: Route; extra?: ReactNode; children: ReactNode }) {
  const depth = depthOf(route);
  const notice = useMain((s) => s.notice);
  const clearNotice = useMain((s) => s.clearNotice);
  return (
    <div className="m-shell" data-depth={depth} data-place={placeOf(route) ?? "surface"}>
      <Backdrop />
      <Crumbs route={route} extra={extra} />
      <Rail depth={depth} />
      {notice && (
        <div className="plane m-notice" role="alert">
          <span>{notice}</span>
          <button type="button" className="btn btn-quiet" onClick={clearNotice}>
            Dismiss
          </button>
        </div>
      )}
      <div className="m-depth">{children}</div>
      {/* the surface has its tiles; the stage owns its window, like the variant's stage */}
      {depth > 0 && route.view !== "stage" && <Dock route={route} />}
    </div>
  );
}
