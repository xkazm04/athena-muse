import { useState } from "react";
import type { EngineStatus } from "../../lib/contract";
import { ProbeLine, useProbe } from "../onboarding/probe";
import { useMain } from "../store";

/** The Meta key for the Muse engine: add, replace, remove, check. It lives in Settings only. */
const SOURCE: Record<EngineStatus["key"], string> = {
  env: "The key comes from this computer's environment.",
  file: "The key is saved on this computer.",
  absent: "No key yet.",
};

export function MuseKey() {
  const engine = useMain((s) => s.engine);
  const { state, check, removeKey } = useProbe();
  const [key, setKey] = useState("");
  const [replacing, setReplacing] = useState(false);
  const [asking, setAsking] = useState(false);
  const checking = state.phase === "checking";

  return (
    <section className="plane m-section" aria-labelledby="av-muse">
      <h2 id="av-muse" className="m-h2">
        Muse connection
      </h2>
      {engine ? (
        <p>
          {engine.simulated ? (
            <span className="badge" data-tone="warning">
              Simulated
            </span>
          ) : (
            <span className="badge" data-tone="success">
              Muse
            </span>
          )}{" "}
          <span className="m-mono">{engine.model}</span>. {SOURCE[engine.key]}
          {engine.simulated && " Replies are simulated and labelled as such until a key is connected."}
        </p>
      ) : (
        <span className="badge" data-tone="info">
          reading
        </span>
      )}
      <div className="m-row">
        {/* With no key the daemon probes its scripted engine, which always answers; that is not Muse. */}
        {engine && engine.key !== "absent" && (
          <button type="button" className="btn" disabled={checking} onClick={() => void check()}>
            Check again
          </button>
        )}
        <button type="button" className="btn btn-quiet" onClick={() => setReplacing((v) => !v)}>
          {engine?.key === "absent" ? "Add a key" : "Replace the key"}
        </button>
        {engine?.key === "file" && !asking && (
          <button type="button" className="btn btn-quiet" onClick={() => setAsking(true)}>
            Remove the key
          </button>
        )}
      </div>
      {asking && (
        <div className="m-confirm" role="group" aria-label="Confirm remove key">
          <p>Athena will run simulated until you add a key again. Remove the key?</p>
          <div className="m-row">
            <button
              type="button"
              className="btn m-btn-danger"
              onClick={() => {
                setAsking(false);
                void removeKey();
              }}
            >
              Remove the key
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => setAsking(false)}>
              Keep it
            </button>
          </div>
        </div>
      )}
      {replacing && (
        <form
          className="m-row"
          onSubmit={(e) => {
            e.preventDefault();
            const clean = key.trim();
            if (!clean) return;
            void check(clean).then(() => setKey(""));
          }}
        >
          <label className="m-sr" htmlFor="av-key">
            New Muse key
          </label>
          <input
            id="av-key"
            className="field"
            type="password"
            autoComplete="off"
            spellCheck={false}
            placeholder="Paste the new key"
            value={key}
            disabled={checking}
            onChange={(e) => setKey(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={!key.trim() || checking}>
            Save and check
          </button>
        </form>
      )}
      <ProbeLine state={state} />
    </section>
  );
}
