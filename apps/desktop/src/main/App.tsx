import { useCallback, useEffect, useState, type ReactNode } from "react";
import * as api from "../lib/api";
import { getConnection, UNREACHABLE } from "../lib/daemon";
import { toggleAthena } from "../lib/windows";
import { Backdrop, Seal } from "../theme";
import { ProjectPill, useAppEvents } from "../ui";
import { AthenaView } from "./athena/AthenaView";
import { ChoreScene } from "./chores/ChoreScene";
import { Chores } from "./chores/Chores";
import { FirstRun, readSkipped } from "./onboarding/FirstRun";
import { Field } from "./projects/Field";
import { Level } from "./projects/Level";
import { CoreLevel, Memory } from "./projects/Memory";
import { isTwinRoute } from "./route";
import { Stage } from "./stage/Stage";
import { TwinsView } from "./twins/Twins";
import { reasonOf, useMain } from "./store";

type Boot = { phase: "waking" } | { phase: "down"; reason: string } | { phase: "up"; firstRun: boolean };

export function App() {
  const [boot, setBoot] = useState<Boot>({ phase: "waking" });
  const setEngine = useMain((s) => s.setEngine);
  const loadAll = useMain((s) => s.loadAll);
  const navigate = useMain((s) => s.navigate);

  const wake = useCallback(async () => {
    setBoot({ phase: "waking" });
    try {
      await getConnection();
      const engine = await api.engine();
      setEngine(engine);
      setBoot({ phase: "up", firstRun: engine.key === "absent" && !readSkipped() });
      void loadAll();
    } catch (e) {
      setBoot({ phase: "down", reason: reasonOf(e, UNREACHABLE) });
    }
  }, [setEngine, loadAll]);

  useEffect(() => {
    void wake();
  }, [wake]);

  if (boot.phase === "waking") {
    return (
      <Centered>
        <Seal state="rest" size={96} label="Athena" />
        <p className="m-lead" role="status">
          Waking Athena
        </p>
      </Centered>
    );
  }
  if (boot.phase === "down") {
    return (
      <Centered>
        <Seal state="rest" size={96} label="Athena" />
        <p className="m-lead" role="alert">
          {boot.reason}
        </p>
        <button type="button" className="btn btn-primary" onClick={() => void wake()}>
          Try again
        </button>
      </Centered>
    );
  }
  if (boot.firstRun) {
    return (
      <FirstRun
        onDone={(toProjects) => {
          setBoot({ phase: "up", firstRun: false });
          if (toProjects) navigate({ view: "projects" });
        }}
      />
    );
  }
  return <Shell />;
}

function Centered({ children }: { children: ReactNode }) {
  return (
    <div className="m-firstrun">
      <Backdrop />
      <main className="m-firstrun__stage m-boot">{children}</main>
    </div>
  );
}

export function Shell() {
  const route = useMain((s) => s.route);
  const notice = useMain((s) => s.notice);
  const syncRoute = useMain((s) => s.syncRoute);
  const handleEvent = useMain((s) => s.handleEvent);
  const clearNotice = useMain((s) => s.clearNotice);
  const navigate = useMain((s) => s.navigate);

  useAppEvents(handleEvent);

  useEffect(() => {
    const on = () => syncRoute(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, [syncRoute]);

  if (route.view === "stage") {
    // The stage owns the window: one frame, its own header, no page scroll (onboarding v2).
    return (
      <div className="m-shell">
        <Backdrop />
        <Stage id={route.id} />
      </div>
    );
  }

  if (isTwinRoute(route)) {
    // The twins page fills the window under the header; a twin's setup owns it, like the stage.
    return (
      <div className="m-shell">
        <Backdrop />
        <TwinsView route={route} top={(extra) => <MainTop extra={extra} />} navigate={navigate} />
      </div>
    );
  }

  return (
    <div className="m-shell">
      <Backdrop />
      <MainTop />
      {notice && (
        <div className="plane m-notice" role="alert">
          <span>{notice}</span>
          <button type="button" className="btn btn-quiet" onClick={clearNotice}>
            Dismiss
          </button>
        </div>
      )}
      <main className="m-content">
        {route.view === "projects" && <Field />}
        {route.view === "project" && <Level id={route.id} />}
        {route.view === "core" && <CoreLevel />}
        {route.view === "memory" && <Memory id={route.id} />}
        {route.view === "athena" && <AthenaView />}
        {route.view === "chores" && <Chores />}
        {route.view === "chore" && <ChoreScene id={route.id} />}
      </main>
    </div>
  );
}

/** The main window's header: her seal, the project pill, the engine lamp, the places, her window. */
export function MainTop({ extra }: { extra?: ReactNode }) {
  const engine = useMain((s) => s.engine);
  const spaces = useMain((s) => s.spaces);
  const active = useMain((s) => s.active);
  const waiting = useMain((s) => s.waiting.length);
  const route = useMain((s) => s.route);
  const setActive = useMain((s) => s.setActive);
  const onAthena = route.view === "athena";
  const onChores = route.view === "chores" || route.view === "chore";
  const onTwins = isTwinRoute(route);
  const here = (on: boolean) => (on ? "page" : undefined);

  return (
    <header className="m-top">
      <Seal
        state={waiting > 0 ? "waiting" : "rest"}
        size={36}
        count={waiting}
        label={waiting > 0 ? `${waiting} waiting on you` : "Athena"}
      />
      <span className="m-wordmark">Athena</span>
      <ProjectPill spaces={spaces} activeId={active} onSelect={(id) => void setActive(id)} />
      {engine &&
        (engine.simulated ? (
          <span className="badge m-lamp" data-tone="warning" title="No Muse key; replies are simulated">
            Simulated
          </span>
        ) : (
          <span className="badge m-lamp" data-tone="success" title={engine.model}>
            Muse
          </span>
        ))}
      {extra}
      <nav className="m-nav" aria-label="Main">
        <a href="#projects" className="m-nav__link" aria-current={here(!onAthena && !onChores && !onTwins)}>
          Projects
        </a>
        <a href="#chores" className="m-nav__link" aria-current={here(onChores)}>
          Chores
        </a>
        <a href="#twins" className="m-nav__link" aria-current={here(onTwins)}>
          Twins
        </a>
        <a href="#athena" className="m-nav__link" aria-current={here(onAthena)}>
          Athena
        </a>
      </nav>
      <button type="button" className="btn btn-primary m-talk" onClick={() => void toggleAthena()}>
        Talk to Athena
      </button>
    </header>
  );
}
