import { useCallback, useEffect, useState, type ReactNode } from "react";
import * as api from "../lib/api";
import { getConnection, UNREACHABLE } from "../lib/daemon";
import { Backdrop, Seal } from "../theme";
import { useAppEvents } from "../ui";
import { AthenaView } from "./athena/AthenaView";
import { ChoreScene } from "./chores/ChoreScene";
import { Chores } from "./chores/Chores";
import { FirstRun, readSkipped } from "./onboarding/FirstRun";
import { Field } from "./projects/Field";
import { Level } from "./projects/Level";
import { CoreLevel, Memory } from "./projects/Memory";
import { isTwinRoute } from "./route";
import { SettingsView } from "./settings/Settings";
import { Stage } from "./stage/Stage";
import { TwinsView } from "./twins/Twins";
import { DepthFrame, InBar } from "./shell/Depth";
import { Surface } from "./shell/Surface";
import { reasonOf, useMain } from "./store";

type Boot = { phase: "waking" } | { phase: "down"; reason: string } | { phase: "up"; firstRun: boolean };

export function App() {
  const [boot, setBoot] = useState<Boot>({ phase: "waking" });
  const setEngine = useMain((s) => s.setEngine);
  const loadAll = useMain((s) => s.loadAll);
  const navigate = useMain((s) => s.navigate);
  // Settings' "Show the welcome again": the first run is drawn over the shell; no row changes.
  const welcome = useMain((s) => s.welcome);
  const setWelcome = useMain((s) => s.setWelcome);

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
  if (boot.firstRun || welcome) {
    return (
      <FirstRun
        onDone={(toProjects) => {
          setWelcome(false);
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
  const syncRoute = useMain((s) => s.syncRoute);
  const handleEvent = useMain((s) => s.handleEvent);
  const navigate = useMain((s) => s.navigate);

  useAppEvents(handleEvent);

  useEffect(() => {
    const on = () => syncRoute(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, [syncRoute]);

  if (route.view === "stage") {
    // The stage keeps its own frame (no page scroll, onboarding v2) inside the shell's body.
    return (
      <DepthFrame route={route}>
        <Stage id={route.id} />
      </DepthFrame>
    );
  }

  if (isTwinRoute(route)) {
    // The twins page fills the body; a twin's setup keeps its own header, like the stage.
    return (
      <DepthFrame route={route}>
        <TwinsView route={route} top={(extra) => (extra ? <InBar>{extra}</InBar> : null)} navigate={navigate} />
      </DepthFrame>
    );
  }

  return (
    <DepthFrame route={route}>
      <main className={route.view === "home" ? "m-content m-content--surface" : "m-content"}>
        {route.view === "home" && <Surface />}
        {route.view === "projects" && <Field />}
        {route.view === "project" && <Level id={route.id} />}
        {route.view === "core" && <CoreLevel />}
        {route.view === "memory" && <Memory id={route.id} />}
        {route.view === "athena" && <AthenaView />}
        {route.view === "chores" && <Chores />}
        {route.view === "chore" && <ChoreScene id={route.id} />}
        {route.view === "settings" && <SettingsView item={route.item} />}
      </main>
    </DepthFrame>
  );
}

