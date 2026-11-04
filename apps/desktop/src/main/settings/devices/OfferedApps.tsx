// This computer's own apps, outside every project, and which of them it offers its paired computers
// (ADR 0026). Only the two program kinds; an offered app names the one folder files may come from.
// Whether it is offered, and that folder, are set when it is added.

import * as api from "../../../lib/api";
import { DEVICE_APPS_MAX, type App } from "../../../lib/contract";
import { AddApp } from "../../projects/apps/AddApp";
import { RemoveInPlace, StatusBadge, ToolList } from "../../projects/apps/parts";
import { useAppList } from "../../projects/apps/useApps";
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
            <OfferedRow key={a.app_id} app={a} onRemoved={() => drop(a.app_id)} />
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

function OfferedRow({ app, onRemoved }: { app: App; onRemoved: () => void }) {
  return (
    <li className="m-app" data-role="device-app" data-offered={app.offered ? "yes" : "no"}>
      <div className="m-app__head">
        <div className="m-app__name">
          <p>
            <strong>{app.label}</strong> <span className="m-muted">{KIND_WORDS[app.kind]}</span>
          </p>
          <p className="m-muted">
            {app.offered ? "Offered to paired computers" : "Kept to this computer"}
            {app.output_dir ? (
              <>
                {", files from "}
                <span className="m-mono">{app.output_dir}</span>
              </>
            ) : null}
          </p>
        </div>
        <StatusBadge status={app.status} />
      </div>
      {app.reason && <p className="m-muted">{app.reason}</p>}
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
