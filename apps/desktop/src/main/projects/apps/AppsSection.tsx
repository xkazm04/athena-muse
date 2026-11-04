// A project's apps by kind (ADR 0025), each with what the last look found and, for a program, its
// tools and its instances: this computer's, and a paired computer's copy attached to it (ADR 0026).
// Plain words only: the kinds are "A website", "A page on this computer", "An app on this computer",
// "A tool she starts".

import { useEffect, useState } from "react";
import * as api from "../../../lib/api";
import { APPS_MAX, type App, type AppRemote, type OfferedApp } from "../../../lib/contract";
import type { PeerView } from "../../../lib/fleet";
import { reasonOf, useMain } from "../../store";
import { AddApp } from "./AddApp";
import { RemoveInPlace, StatusBadge, ToolList } from "./parts";
import { useAppList } from "./useApps";
import { KIND_ORDER, KIND_WORDS, isProcess, toolsLine } from "./words";

/** The paired computers (never a phone): the ones whose copy of an app may be attached. */
function usePairedPcs(wanted: boolean): PeerView[] {
  const [pcs, setPcs] = useState<PeerView[]>([]);
  useEffect(() => {
    if (!wanted) return;
    let live = true;
    api.devices().then(
      (view) => {
        if (live) setPcs((view?.peers ?? []).filter((p) => p.kind === "pc"));
      },
      () => undefined, // no devices to offer: the control is simply not shown
    );
    return () => {
      live = false;
    };
  }, [wanted]);
  return pcs;
}

export function AppsSection({ spaceId }: { spaceId: string }) {
  const loadSites = useMain((s) => s.loadSites);
  const { apps, problem, put, drop } = useAppList(spaceId, () => api.spaceApps(spaceId), "Could not read the project's apps");
  const pcs = usePairedPcs(apps.some((a) => isProcess(a.kind)));

  // Wiring a page on this computer writes its site (ADR 0025); the project's addresses themselves
  // follow the daemon's `space_changed`.
  const touched = (app: App) => {
    if (app.kind === "local_page") void loadSites(spaceId).catch(() => undefined);
  };

  return (
    <section className="plane m-section" data-role="apps">
      <h2 className="m-h2">Apps</h2>
      <p className="m-muted">
        What this project works with: websites and pages she opens in her browser, and programs on this computer she can use.
      </p>
      {apps.length > 0 ? (
        <ul className="m-apps">
          {apps.map((a) => (
            <AppRow
              key={a.app_id}
              app={a}
              spaceId={spaceId}
              pcs={pcs}
              onChanged={put}
              onRemoved={() => {
                drop(a.app_id);
                touched(a);
              }}
            />
          ))}
        </ul>
      ) : (
        <p className="m-muted">No apps yet.</p>
      )}
      <AddApp
        kinds={KIND_ORDER}
        full={apps.length >= APPS_MAX}
        add={(body) => api.addSpaceApp(spaceId, body)}
        probe={(appId) => api.probeSpaceApp(spaceId, appId)}
        onAdded={(app) => {
          put(app);
          touched(app);
        }}
      />
      {apps.length >= APPS_MAX && <p className="m-muted">A project holds at most {APPS_MAX} apps.</p>}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </section>
  );
}

interface RowProps {
  app: App;
  spaceId: string;
  pcs: PeerView[];
  onChanged: (app: App) => void;
  onRemoved: () => void;
}

function AppRow({ app, spaceId, pcs, onChanged, onRemoved }: RowProps) {
  const [looking, setLooking] = useState(false);
  const [problem, setProblem] = useState("");
  const program = isProcess(app.kind);

  const look = async () => {
    setLooking(true);
    setProblem("");
    try {
      onChanged(await api.probeSpaceApp(spaceId, app.app_id));
    } catch (e) {
      setProblem(reasonOf(e, "Athena could not look at it"));
    }
    setLooking(false);
  };

  return (
    <li className="m-app" data-role="app" data-kind={app.kind} data-status={app.status}>
      <div className="m-app__head">
        <div className="m-app__name">
          <p>
            <strong>{app.label}</strong> <span className="m-muted">{KIND_WORDS[app.kind]}</span>
          </p>
          <p className="m-mono m-app__address">{app.address}</p>
        </div>
        <StatusBadge status={app.status} />
        <button type="button" className="btn btn-quiet" disabled={looking} onClick={() => void look()}>
          {looking ? "Looking..." : "Check again"}
        </button>
      </div>
      {app.reason && <p className="m-muted">{app.reason}</p>}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
      {program && (
        <details className="m-app__tools">
          <summary>{toolsLine(app)}</summary>
          <ToolList tools={app.tools} />
        </details>
      )}
      {program && <Instances app={app} spaceId={spaceId} pcs={pcs} onChanged={onChanged} />}
      <RemoveInPlace
        label={app.label}
        what={`Athena stops using ${app.label} in this project.`}
        remove={async () => {
          await api.removeSpaceApp(spaceId, app.app_id);
          onRemoved();
        }}
      />
    </li>
  );
}

/** Where the app runs: this computer, and each paired computer whose copy is attached. */
function Instances({ app, spaceId, pcs, onChanged }: { app: App; spaceId: string; pcs: PeerView[]; onChanged: (a: App) => void }) {
  const attached = new Set(app.remotes.map((r) => r.peer_id));
  const more = pcs.filter((p) => !attached.has(p.peer_id));
  return (
    <div className="m-instances">
      <ul className="m-instances__list" aria-label={`Where ${app.label} runs`}>
        <li className="m-instance" data-role="instance" data-where="here">
          <span>This computer</span>
          <StatusBadge status={app.status} />
        </li>
        {app.remotes.map((r) => (
          <RemoteRow key={r.peer_id} app={app} remote={r} spaceId={spaceId} onChanged={onChanged} />
        ))}
      </ul>
      {more.map((pc) => (
        <Attach key={pc.peer_id} app={app} spaceId={spaceId} pc={pc} onChanged={onChanged} />
      ))}
    </div>
  );
}

interface RemoteProps {
  app: App;
  remote: AppRemote;
  spaceId: string;
  onChanged: (a: App) => void;
}

/** A paired computer's copy, with "Detach" confirmed by a second press in place. */
function RemoteRow({ app, remote, spaceId, onChanged }: RemoteProps) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  const detach = async () => {
    setBusy(true);
    setProblem("");
    try {
      const apps = await api.detachRemote(spaceId, app.app_id, remote.peer_id);
      const now = (apps ?? []).find((a) => a.app_id === app.app_id);
      onChanged(now ?? { ...app, remotes: app.remotes.filter((r) => r.peer_id !== remote.peer_id) });
    } catch (e) {
      setProblem(reasonOf(e, `Could not detach ${remote.device}'s copy`));
      setBusy(false);
    }
  };

  return (
    <li className="m-instance" data-role="instance" data-where={remote.peer_id}>
      <span>on {remote.device}</span>
      <StatusBadge status={remote.status} />
      <span className="m-muted">{toolsLine(remote)}</span>
      {remote.reason && <span className="m-muted m-instance__why">{remote.reason}</span>}
      {asking ? (
        <div className="m-confirm" role="group" aria-label={`Confirm detaching ${remote.device}'s copy`}>
          <p>
            Athena stops using {app.label} on {remote.device} in this project. {remote.device} keeps the app.
          </p>
          <div className="m-row">
            <button type="button" className="btn m-btn-danger" disabled={busy} onClick={() => void detach()}>
              {busy ? "Detaching..." : "Detach"}
            </button>
            <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => setAsking(false)}>
              Keep it
            </button>
          </div>
        </div>
      ) : (
        <button type="button" className="btn btn-quiet" aria-label={`Detach ${remote.device}'s copy`} onClick={() => setAsking(true)}>
          Detach
        </button>
      )}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </li>
  );
}

type Offers = { at: "closed" } | { at: "asking" } | { at: "open"; offered: OfferedApp[] };

/** "Add <device>'s copy": ask that computer what it offers, and attach the one the person picks. */
function Attach({ app, spaceId, pc, onChanged }: { app: App; spaceId: string; pc: PeerView; onChanged: (a: App) => void }) {
  const [offers, setOffers] = useState<Offers>({ at: "closed" });
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  const ask = async () => {
    setProblem("");
    setOffers({ at: "asking" });
    try {
      setOffers({ at: "open", offered: (await api.peerOffers(pc.peer_id)) ?? [] });
    } catch (e) {
      setProblem(reasonOf(e, `Could not ask ${pc.name} what it offers`));
      setOffers({ at: "closed" });
    }
  };

  const attach = async (offer: OfferedApp) => {
    setBusy(true);
    setProblem("");
    try {
      onChanged(await api.attachRemote(spaceId, app.app_id, { peer_id: pc.peer_id, remote_app_id: offer.app_id }));
      setOffers({ at: "closed" });
    } catch (e) {
      setProblem(reasonOf(e, `Could not add ${pc.name}'s copy`));
    }
    setBusy(false);
  };

  return (
    <div className="m-attach" data-role="attach" data-peer={pc.peer_id}>
      {offers.at === "open" ? (
        <div className="m-confirm" role="group" aria-label={`What ${pc.name} offers`}>
          {offers.offered.length ? (
            <>
              <p>Which of {pc.name}&apos;s apps is the same as {app.label}?</p>
              <ul className="m-offers">
                {offers.offered.map((o) => (
                  <li key={o.app_id} className="m-row">
                    <span>
                      <strong>{o.label}</strong> <span className="m-muted">{KIND_WORDS[o.kind]}, {toolsLine(o)}</span>
                    </span>
                    <button type="button" className="btn" disabled={busy} onClick={() => void attach(o)} aria-label={`Use ${o.label} on ${pc.name}`}>
                      Use this one
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="m-muted">{pc.name} offers no apps to this computer yet. On {pc.name}, add one in Settings, Devices.</p>
          )}
          <div className="m-row">
            <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => setOffers({ at: "closed" })}>
              Never mind
            </button>
          </div>
        </div>
      ) : (
        <button type="button" className="btn btn-quiet" disabled={offers.at === "asking"} onClick={() => void ask()}>
          {offers.at === "asking" ? `Asking ${pc.name}...` : `Add ${pc.name}'s copy`}
        </button>
      )}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </div>
  );
}
