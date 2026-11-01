// A twin on web channels, DERIVED from the generated twins fixture (it has no twin on a web channel
// yet): the paste panel on the samples slip, the clearance slip with a web channel beside Gmail, and
// the overview's visa marks. The example's routes answer, so a paste is kept and listed, with no daemon.

import { useMemo, useState } from "react";
import { createExampleIo } from "../main/twins/example";
import { TWIN_FIXTURE } from "../main/twins/fixture/twins";
import { stateOf, webIo, type TwinStateId } from "../main/twins/states";
import { createTwinsStore } from "../main/twins/store";
import { TwinsView } from "../main/twins/Twins";

const WEB_STATES: { id: TwinStateId; name: string }[] = [
  { id: "setup-web-paste", name: "your own messages" },
  { id: "setup-web-clearance", name: "clearance" },
  { id: "overview-web", name: "overview" },
];

function useWebStore(id: TwinStateId) {
  return useMemo(() => {
    const shown = stateOf(id);
    const io = createExampleIo(TWIN_FIXTURE, { pace: 0 });
    const store = createTwinsStore(io, { pollMs: 0 });
    store.getState().useExample(shown.state.setup.twin ? webIo(io, shown.state.setup.twin) : io);
    store.setState(shown.state);
    return { store, route: shown.route };
  }, [id]);
}

export function TwinsWebSection() {
  const [at, setAt] = useState(0);
  const { store, route } = useWebStore(WEB_STATES[at]!.id);
  const st = store();
  return (
    <section className="pv-section" aria-labelledby="pv-twins-web">
      <h2 id="pv-twins-web">Twins on web channels (invented example; web channels derived from the generated fixture)</h2>
      <div className="pv-row" role="group" aria-label="Twins web state">
        {WEB_STATES.map((s, i) => (
          <button key={s.id} type="button" className={i === at ? "btn btn-primary" : "btn"} aria-pressed={i === at} onClick={() => setAt(i)}>
            {s.name}
          </button>
        ))}
      </div>
      <div className="pv-twins" key={WEB_STATES[at]!.id}>
        <TwinsView route={route} top={(extra) => <header className="pv-row">{extra}</header>} navigate={() => undefined} store={st} />
      </div>
    </section>
  );
}
