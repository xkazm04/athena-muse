// This computer's own apps, outside every project, and which of them it offers its paired computers
// (ADR 0026). Only the two program kinds; an offered app names the one folder files may come from.
// Whether it is offered, and that folder, are set when it is added and changed on its row.

import { useState } from "react";
import * as api from "../../../lib/api";
import { DEVICE_APPS_MAX, type App, type AppPatch } from "../../../lib/contract";
import { AddApp } from "../../projects/apps/AddApp";
import { RemoveInPlace, StatusBadge, ToolList } from "../../projects/apps/parts";
import { useAppList } from "../../projects/apps/useApps";
import { reasonOf } from "../../store";
import { KIND_WORDS, PROCESS_KINDS, toolsLine } from "../../projects/apps/words";

export function OfferedApps() {
  const { apps, problem, put, drop } = useAppList("", () => api.deviceApps(), "Could not read this computer's apps");
  const full = apps.length >= DEVICE_APPS_MAX;
  return (
    <section className="plane m-section" data-role="offered-apps" aria-labelledby="offered-apps-h">
      <h2 className="m-h2" id="offered-apps-h">
        Apps this computer offers
      </h2>
      <p className="m-muted">
        Paired computers with the &ldquo;use the apps this computer offers&rdquo; permission can use the apps switched on here.
      </p>
      {apps.length > 0 ? (
        <ul className="m-apps">
          {apps.map((a) => (
            <OfferedRow key={a.app_id} app={a} onChanged={put} onRemoved={() => drop(a.app_id)} />
          ))}
        </ul>
      ) : (
        <p className="m-muted">No apps on this computer yet.</p>
      )}
      <AddApp kinds={PROCESS_KINDS} device full={full} add={api.addDeviceApp} probe={api.probeDeviceApp} onAdded={put} />
      {full && <p className="m-muted">This computer holds at most {DEVICE_APPS_MAX} apps.</p>}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </section>
  );
}

function OfferedRow({ app, onChanged, onRemoved }: { app: App; onChanged: (a: App) => void; onRemoved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const offered = app.offered === true;

  const change = async (body: AppPatch): Promise<boolean> => {
    setBusy(true);
    setProblem("");
    try {
      onChanged(await api.patchDeviceApp(app.app_id, body));
      setBusy(false);
      return true;
    } catch (e) {
      setProblem(reasonOf(e, `Could not change ${app.label}`));
      setBusy(false);
      return false;
    }
  };

  return (
    <li className="m-app" data-role="device-app" data-offered={offered ? "yes" : "no"}>
      <div className="m-app__head">
        <div className="m-app__name">
          <p>
            <strong>{app.label}</strong> <span className="m-muted">{KIND_WORDS[app.kind]}</span>
          </p>
          <div className="m-row">
            <button
              type="button"
              role="switch"
              aria-checked={offered}
              aria-label={`Offer ${app.label} to paired computers`}
              className="btn btn-pill"
              disabled={busy}
              onClick={() => void change({ offered: !offered })}
            >
              {offered ? "On" : "Off"}
            </button>
            <span className="m-muted">{offered ? "Offered to paired computers" : "Kept to this computer"}</span>
          </div>
        </div>
        <StatusBadge status={app.status} />
      </div>
      <OutputFolder app={app} busy={busy} save={(dir) => change({ output_dir: dir })} />
      {app.reason && <p className="m-muted">{app.reason}</p>}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
      <details className="m-app__tools">
        <summary>{toolsLine(app)}</summary>
        <ToolList tools={app.tools} />
      </details>
      <RemoveInPlace
        label={app.label}
        what={`Paired computers can no longer use ${app.label}.`}
        remove={async () => {
          await api.removeDeviceApp(app.app_id);
          onRemoved();
        }}
      />
    </li>
  );
}

/** The one folder files may be brought from: shown, and changed in place (empty clears it). */
function OutputFolder({ app, busy, save }: { app: App; busy: boolean; save: (dir: string) => Promise<boolean> }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const id = `output-${app.app_id}`;

  if (!editing) {
    return (
      <div className="m-row" data-role="output-folder">
        <span className="m-muted">
          {app.output_dir ? (
            <>
              {"Files from "}
              <span className="m-mono">{app.output_dir}</span>
            </>
          ) : (
            "No output folder"
          )}
        </span>
        <button
          type="button"
          className="btn btn-quiet"
          aria-label={`Change ${app.label}'s output folder`}
          disabled={busy}
          onClick={() => {
            setValue(app.output_dir ?? "");
            setEditing(true);
          }}
        >
          Change folder
        </button>
      </div>
    );
  }
  return (
    <form
      className="m-confirm"
      aria-label={`${app.label}'s output folder`}
      onSubmit={(e) => {
        e.preventDefault();
        void save(value.trim()).then((ok) => ok && setEditing(false));
      }}
    >
      <label htmlFor={id}>Output folder</label>
      <p className="m-muted">The one folder Athena may bring files from. Leave it empty for none.</p>
      <input id={id} className="field m-mono" value={value} disabled={busy} onChange={(e) => setValue(e.target.value)} />
      <div className="m-row">
        <button type="submit" className="btn" disabled={busy}>
          {busy ? "Saving..." : "Save folder"}
        </button>
        <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => setEditing(false)}>
          Never mind
        </button>
      </div>
    </form>
  );
}
