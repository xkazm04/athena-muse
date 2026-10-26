import { useEffect, useRef, useState } from "react";
import { APPS_MAX, BRIEF_MAX, NAME_MAX, type SpaceSummary } from "../../lib/contract";
import { DaemonError } from "../../lib/daemon";
import { hueColor } from "../../ui";
import { reasonOf, useMain } from "../store";

const memoriesLine = (episodes: number, facts: number) =>
  `${episodes} ${episodes === 1 ? "episode" : "episodes"}, ${facts} ${facts === 1 ? "fact" : "facts"}`;

export function Level({ id }: { id: string }) {
  const space = useMain((s) => s.spaces.find((x) => x.id === id));
  const load = useMain((s) => s.spacesLoad);
  const navigate = useMain((s) => s.navigate);

  if (!space) {
    return (
      <section className="plane m-level">
        {load === "reading" || load === "idle" ? (
          <span className="badge" data-tone="info">
            reading
          </span>
        ) : (
          <>
            <p>This project is not here any more.</p>
            <button type="button" className="btn" onClick={() => navigate({ view: "projects" })}>
              Back to your projects
            </button>
          </>
        )}
      </section>
    );
  }
  return <LevelBody key={space.id} space={space} />;
}

/** A text the person edits in place; saved when it loses focus (and on Enter for one line). */
function useDraft(value: string) {
  const [draft, setDraft] = useState(value);
  const editing = useRef(false);
  // A change from elsewhere (her window signed a brief) shows up unless the person is mid-edit.
  useEffect(() => {
    if (!editing.current) setDraft(value);
  }, [value]);
  return { draft, setDraft, editing };
}

function LevelBody({ space }: { space: SpaceSummary }) {
  const active = useMain((s) => s.active);
  const updateSpace = useMain((s) => s.updateSpace);
  const setActive = useMain((s) => s.setActive);
  const navigate = useMain((s) => s.navigate);
  const name = useDraft(space.name);
  const brief = useDraft(space.brief);
  const [problem, setProblem] = useState("");
  const [saved, setSaved] = useState("");

  const save = async (patch: { name?: string; brief?: string }, what: string) => {
    setProblem("");
    try {
      await updateSpace(space.id, patch);
      setSaved(what);
    } catch (e) {
      setProblem(reasonOf(e, "Could not save"));
    }
  };

  const saveName = () => {
    name.editing.current = false;
    const clean = name.draft.trim();
    if (!clean) {
      name.setDraft(space.name);
      return;
    }
    if (clean !== space.name) void save({ name: clean }, "Name saved");
  };

  const saveBrief = () => {
    brief.editing.current = false;
    if (brief.draft !== space.brief) void save({ brief: brief.draft }, "Brief saved");
  };

  return (
    <div className="m-level">
      <button type="button" className="btn btn-quiet m-back" onClick={() => navigate({ view: "projects" })}>
        All projects
      </button>
      <section className="plane m-section" style={{ ["--hue" as string]: hueColor(space.hue) }}>
        <label className="m-sr" htmlFor="level-name">
          Project name
        </label>
        <input
          id="level-name"
          className="m-name"
          value={name.draft}
          maxLength={NAME_MAX}
          onFocus={() => (name.editing.current = true)}
          onChange={(e) => name.setDraft(e.target.value)}
          onBlur={saveName}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
        />
        {active === space.id ? (
          <p className="m-active">
            <span className="badge" data-tone="success">
              active
            </span>{" "}
            Athena is working in this project
          </p>
        ) : (
          <p className="m-active">
            <button type="button" className="btn" onClick={() => void setActive(space.id)}>
              Work here
            </button>
          </p>
        )}
        <label className="m-label" htmlFor="level-brief">
          Brief
        </label>
        <p className="m-muted" id="level-brief-help">
          Athena reads this every time she works in this project.
        </p>
        <textarea
          id="level-brief"
          className="field m-brief"
          rows={6}
          maxLength={BRIEF_MAX}
          aria-describedby="level-brief-help"
          value={brief.draft}
          onFocus={() => (brief.editing.current = true)}
          onChange={(e) => brief.setDraft(e.target.value)}
          onBlur={saveBrief}
        />
        <div className="m-under">
          <span className="m-muted" aria-live="polite">
            {saved}
          </span>
          <span className="m-muted m-counter">
            {brief.draft.length}/{BRIEF_MAX}
          </span>
        </div>
        {problem && (
          <p className="m-error" role="alert">
            {problem}
          </p>
        )}
      </section>
      <Apps space={space} />
      <section className="plane m-section">
        <h2 className="m-h2">Memory</h2>
        <p>
          {memoriesLine(space.counts.episodes, space.counts.facts)}.{" "}
          <a className="m-link" href={`#projects/${encodeURIComponent(space.id)}/memory`}>
            See what Athena remembers here
          </a>
        </p>
      </section>
      <Erase space={space} />
    </div>
  );
}

function Apps({ space }: { space: SpaceSummary }) {
  const updateSpace = useMain((s) => s.updateSpace);
  const [origin, setOrigin] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const full = space.apps.length >= APPS_MAX;

  const put = async (apps: string[]) => {
    setBusy(true);
    setProblem("");
    try {
      await updateSpace(space.id, { apps });
      return true;
    } catch (e) {
      setProblem(reasonOf(e, "Could not change the apps"));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const add = async () => {
    const clean = origin.trim();
    if (!clean) return;
    if (await put([...space.apps, clean])) setOrigin("");
  };

  return (
    <section className="plane m-section">
      <h2 className="m-h2">Apps</h2>
      <p className="m-muted">The web apps Athena may work with in this project.</p>
      {space.apps.length > 0 ? (
        <ul className="m-chips">
          {space.apps.map((a) => (
            <li key={a} className="m-chip">
              <span className="m-mono">{a}</span>
              <button
                type="button"
                className="m-chip__x"
                aria-label={`Remove ${a}`}
                disabled={busy}
                onClick={() => void put(space.apps.filter((x) => x !== a))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="m-muted">No apps yet.</p>
      )}
      <form
        className="m-row"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <label className="m-sr" htmlFor="level-app">
          App address
        </label>
        <input
          id="level-app"
          className="field"
          placeholder="https://example.com"
          value={origin}
          disabled={busy || full}
          onChange={(e) => setOrigin(e.target.value)}
        />
        <button type="submit" className="btn" disabled={busy || full || !origin.trim()}>
          Add app
        </button>
      </form>
      {full && <p className="m-muted">A project holds at most {APPS_MAX} apps.</p>}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </section>
  );
}

function Erase({ space }: { space: SpaceSummary }) {
  const eraseSpace = useMain((s) => s.eraseSpace);
  const navigate = useMain((s) => s.navigate);
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const n = space.counts.episodes + space.counts.facts;

  const erase = async () => {
    setBusy(true);
    setProblem("");
    try {
      await eraseSpace(space.id);
      navigate({ view: "projects" });
    } catch (e) {
      setProblem(
        e instanceof DaemonError && e.error === "space_busy"
          ? "Athena is working in this project; try again when she is done"
          : reasonOf(e, "Could not erase the project"),
      );
      setBusy(false);
    }
  };

  return (
    <section className="plane m-section m-danger">
      <h2 className="m-h2">Erase</h2>
      {!asking ? (
        <button type="button" className="btn" onClick={() => setAsking(true)}>
          Erase this project
        </button>
      ) : (
        <div className="m-confirm" role="group" aria-label="Confirm erase">
          <p>
            This erases {n} {n === 1 ? "memory" : "memories"} and the conversation. Chores are not affected.
          </p>
          <div className="m-row">
            <button type="button" className="btn m-btn-danger" disabled={busy} onClick={() => void erase()}>
              {busy ? "Erasing..." : `Erase ${space.name}`}
            </button>
            <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => setAsking(false)}>
              Keep it
            </button>
          </div>
        </div>
      )}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </section>
  );
}
