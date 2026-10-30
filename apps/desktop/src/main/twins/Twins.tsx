// The twins page and its nested pages (Passport): one store, one stylesheet scoped under
// [data-twins-view="passport"]. The overview and the nested pages sit under the app's own header; a
// twin's setup takes the whole window, like the stage, with its own header. It talks to the daemon;
// the invented example plays only when the person asks for it, and says so.

import { useCallback, useEffect, useRef, type ReactNode } from "react";
import type { AppEvent, TwinDetail } from "../../lib/contract";
import { toggleAthena } from "../../lib/windows";
import { Seal } from "../../theme";
import { useAppEvents } from "../../ui";
import type { Route } from "../route";
import { useMain } from "../store";
import { Icon, InventedBadge } from "./marks";
import { DraftPage, MissionPage, VoicePage } from "./Nested";
import { Overview } from "./Overview";
import { Setup } from "./Setup";
import { useTwins, type TwinsStore } from "./store";
import { TWINS_WORDS as w } from "./words";
import "./shell.css";
import "./overview.css";
import "./document.css";
import "./work.css";
import "./frame.css";

export type TwinRoute = Extract<Route, { view: "twins" | "twin" | "twin_voice" | "twin_mission" | "twin_draft" }>;

export interface TwinsViewProps {
  route: TwinRoute;
  /** The app's own header over the overview and the nested pages; `extra` sits in it (the example's label). */
  top: (extra?: ReactNode) => ReactNode;
  navigate: (route: Route) => void;
  /** The store to draw; the preview harness hands in one playing the example. */
  store?: TwinsStore;
}

/** Whether a route is a twin's setup: a new twin, or one still being issued. */
function isSetup(route: TwinRoute, st: TwinsStore): boolean {
  if (route.view !== "twin") return false;
  if (route.id === null) return true;
  if (st.setup.twin?.id === route.id) return true;
  const t = st.page?.twins.find((x) => x.id === route.id);
  return t?.state === "setting_up";
}

/** What the daemon publishes that changes the twins page: a card filed or decided (a twin's draft
 * waits, or was signed), and a Project changed (a mission was worked, by the poller or a signature). */
const CHANGES: ReadonlySet<AppEvent["type"]> = new Set(["card_filed", "card_resolved", "space_changed"]);
const REFRESH_MS = 400;

/** Live daemon events, folded into one read of the page a moment later. */
function useRefreshOnEvents(st: TwinsStore, enabled: boolean) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refresh = st.refresh;
  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);
  useAppEvents((e) => {
    if (!CHANGES.has(e.type)) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      timer.current = null;
      void refresh();
    }, REFRESH_MS);
  }, enabled);
}

/** The page's own view of the store, for the app (the hook) or the harness (a snapshot). */
export function TwinsView({ route, top, navigate, store }: TwinsViewProps) {
  const hooked = useTwins();
  const st = store ?? hooked;
  const simulated = useMain((s) => s.engine?.simulated ?? false);
  const { loadPage, openSetup, loadDetail, loadPreview } = st;
  const setup = isSetup(route, st);
  const id = "id" in route ? route.id : null;
  const go = useCallback((r: Route) => navigate(r), [navigate]);
  const example = st.mode === "example";

  useRefreshOnEvents(st, !store && !example);

  useEffect(() => {
    if (!setup && st.pageLoad === "idle") void loadPage();
  }, [setup, st.pageLoad, loadPage]);

  useEffect(() => {
    if (setup) void openSetup(id);
  }, [setup, id, openSetup]);

  // a new twin gets its own address once the daemon made it, so a reload opens the same setup
  const made = route.view === "twin" && route.id === null ? st.setup.twin?.id : undefined;
  useEffect(() => {
    if (made) go({ view: "twin", id: made });
  }, [made, go]);

  const detailId = route.view === "twin_voice" ? route.id : null;
  const known = detailId ? st.details[detailId] : undefined;
  useEffect(() => {
    if (detailId && !known && st.setup.twin?.id !== detailId) void loadDetail(detailId);
  }, [detailId, known, st.setup.twin?.id, loadDetail]);

  // the voice page reads how it sounds now: one engine call, which the daemon keeps until the voice changes
  const voiceOf: TwinDetail | undefined = detailId ? (st.setup.twin?.id === detailId ? st.setup.twin : known) : undefined;
  const voiced = !!voiceOf?.pieces.some((p) => p.place === "voice" && p.confirmed);
  const asked = detailId ? st.previews[detailId]?.load : undefined;
  useEffect(() => {
    if (detailId && voiced && !store && asked === undefined) void loadPreview(detailId);
  }, [detailId, voiced, store, asked, loadPreview]);

  const now = st.now();
  const label = example ? (
    <InventedBadge title={w.inventedTitle}>{w.invented}</InventedBadge>
  ) : undefined;

  if (setup) {
    const name = st.setup.twin?.name && st.setup.twin.pieces.length ? st.setup.twin.name : "a new twin";
    return (
      <div className="tw-frame tw-frame--setup" data-twins-view="passport" data-work={st.setup.work ?? ""} data-phase={st.setup.phase}>
        <header className="tw-top">
          <a className="tw-brand" href="#twins" onClick={(e) => (e.preventDefault(), go({ view: "twins" }))} aria-label="Athena: your twins">
            <Seal state={st.setup.work ? "working" : "rest"} size={34} label="Athena" />
            <b>Athena</b>
          </a>
          {label}
          {!example && simulated && (
            <span className="badge" data-tone="warning" data-role="simulated" title={w.simulatedTitle}>
              {w.simulated}
            </span>
          )}
          <span className="tw-top__where">Setting up {name}</span>
          <span className="tw-top__gap" />
          <button type="button" className="btn" onClick={() => void toggleAthena()} title="The whole conversation so far is in her window">
            <Icon name="chat" />
            {w.herWindow}
          </button>
          <button type="button" className="btn btn-quiet" onClick={() => go({ view: "twins" })}>
            <Icon name="back" />
            {w.twins}
          </button>
        </header>
        <main className="view view--setup">
          <Setup
            s={st.setup}
            dispatch={st.dispatch}
            onBack={() => go({ view: "twins" })}
            onVoice={() => st.setup.twin && go({ view: "twin_voice", id: st.setup.twin.id })}
          />
        </main>
      </div>
    );
  }

  const twin = id ? (st.page?.twins.find((t) => t.id === id) ?? (st.setup.twin?.id === id ? st.setup.twin : undefined)) : undefined;
  let body: ReactNode;
  if (route.view === "twins" || route.view === "twin" || (id && !twin)) {
    body = (
      <Overview
        state={st}
        open={route.view === "twin" ? route.id : null}
        now={now}
        go={go}
        onRetry={() => void loadPage()}
        onExample={example || store ? undefined : () => st.useExample()}
        onLive={example && !store ? st.useLive : undefined}
        onSignIn={(tid) => void st.signInAgain(tid)}
        onResume={(tid) => void st.resume(tid)}
        onFlashOff={st.clearFlash}
      />
    );
  } else if (route.view === "twin_voice" && twin) {
    body = (
      <VoicePage
        twin={twin}
        detail={voiceOf}
        preview={st.previews[twin.id]}
        onPreview={store ? undefined : () => void loadPreview(twin.id)}
        now={now}
        go={go}
      />
    );
  } else if (route.view === "twin_mission" && twin) {
    const fromSetup = st.setup.twin?.rehearsal?.id === route.mission ? st.setup.twin.rehearsal : undefined;
    body = <MissionPage twin={twin} mission={twin.missions.find((m) => m.id === route.mission) ?? fromSetup} now={now} go={go} onTakeOver={st.takeOver} />;
  } else if (route.view === "twin_draft" && twin) {
    const draft = st.done[route.draft] ? undefined : twin.waiting.find((d) => d.id === route.draft);
    body = <DraftPage key={route.draft} twin={twin} draft={draft} now={now} go={go} onSign={st.sign} onDecline={st.decline} />;
  }
  return (
    <div className="tw-frame" data-twins-view="passport">
      {top(label)}
      <main className={`view ${route.view === "twins" || route.view === "twin" ? "view--overview" : "view--nested"}`}>{body}</main>
    </div>
  );
}
