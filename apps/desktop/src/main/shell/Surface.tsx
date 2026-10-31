// The surface (ADR 0016), the default landing, after the variant's home: her seal large at the left,
// her state as an eyebrow and a light marquee, an ask that hands the words to her own window, and a
// tile per depth with a live line from the stores. The tiles are this depth's places; no dock here.

import { useEffect, useState, type FormEvent } from "react";
import { handToAthena, toggleAthena } from "../../lib/windows";
import { Seal } from "../../theme";
import { count } from "../chores/words";
import { ENGINE_LABEL } from "../settings/model";
import { useMain } from "../store";
import { useTwins } from "../twins/store";
import { PLACES, type PlaceKey } from "./Depth";
import { Glyph } from "./glyphs";
import "./surface.css";

export const ASK_NOTE = "Your words go to her own window, where she answers and where you approve.";
export const ASK_AWAY = "Her window lives in the desktop app; the words stay here.";

interface Light {
  stat: string;
  /** Something here waits on the person: the tile carries the pink mark. */
  attention?: boolean;
}

/** Each place's line, from what the stores already hold. */
function useLights(): Record<PlaceKey, Light> {
  const spaces = useMain((s) => s.spaces);
  const spacesLoad = useMain((s) => s.spacesLoad);
  const chores = useMain((s) => s.chores);
  const choresLoad = useMain((s) => s.choresLoad);
  const waiting = useMain((s) => s.waiting.length);
  const engine = useMain((s) => s.engine);
  const twins = useTwins((s) => s.page?.twins);
  const twinsLoad = useTwins((s) => s.pageLoad);

  const proven = chores.filter((c) => c.featured === "proven").length;
  const drafts = twins?.reduce((n, t) => n + t.waiting_count, 0) ?? 0;
  const live = twins?.filter((t) => t.state === "live").length ?? 0;

  return {
    projects: {
      stat: spacesLoad !== "ready" ? "reading" : spaces.length === 0 ? "none yet, core only" : count(spaces.length, "project", "projects"),
    },
    chores: {
      stat:
        choresLoad !== "ready"
          ? "reading"
          : chores.length === 0
            ? "none yet"
            : `${count(chores.length, "chore", "chores")}${proven ? `, ${proven} proven on Meta` : ", none proven on Meta"}`,
    },
    twins: {
      stat:
        twinsLoad !== "ready" || !twins
          ? "reading"
          : twins.length === 0
            ? "none yet"
            : drafts > 0
              ? `${count(drafts, "draft", "drafts")} to sign`
              : `${count(twins.length, "twin", "twins")}, ${live} live`,
      attention: drafts > 0,
    },
    athena: {
      stat: waiting > 0 ? `${waiting} waiting on you` : "nothing waits on you",
      attention: waiting > 0,
    },
    settings: {
      stat: !engine ? "checking the engine" : engine.simulated ? "simulated, no Muse key" : `thinks with ${ENGINE_LABEL[engine.engine]}`,
    },
  };
}

export function Surface() {
  const waiting = useMain((s) => s.waiting.length);
  const navigate = useMain((s) => s.navigate);
  const loadChores = useMain((s) => s.loadChores);
  const choresLoad = useMain((s) => s.choresLoad);
  const twinsLoad = useTwins((s) => s.pageLoad);
  const loadTwins = useTwins((s) => s.loadPage);
  const lights = useLights();
  const [ask, setAsk] = useState("");
  const [note, setNote] = useState(ASK_NOTE);

  // the tiles' lines read the chores and the twins once, like their own pages do
  useEffect(() => {
    if (choresLoad === "idle") void loadChores();
  }, [choresLoad, loadChores]);
  useEffect(() => {
    if (twinsLoad === "idle") void loadTwins();
  }, [twinsLoad, loadTwins]);

  const asking = waiting > 0;
  const words = asking ? "waiting on you" : "resting";
  const clean = ask.trim();

  const hand = async (e: FormEvent) => {
    e.preventDefault();
    if (!clean) return;
    const handed = await handToAthena(clean).catch(() => false);
    if (handed) {
      setAsk("");
      setNote(ASK_NOTE);
    } else setNote(ASK_AWAY);
  };

  return (
    <div className="m-surface" data-pose={asking ? "asking" : "resting"}>
      <div className="m-surface__seal">
        <Seal
          state={asking ? "waiting" : "rest"}
          size={320}
          count={waiting}
          label="Talk to Athena"
          onClick={() => void toggleAthena()}
        />
      </div>
      <div className="m-surface__words">
        <p className="eyebrow m-surface__eyebrow" data-tone={asking ? "human" : undefined}>
          {words}
        </p>
        <h1 className="marquee marquee--surface">{asking ? `${waiting} ${waiting === 1 ? "thing waits" : "things wait"} on you` : "Athena is resting"}</h1>
        <p className="m-surface__line" aria-live="polite">
          {asking ? "Sign or decline in her window, or on the Athena page." : "Ask her for a chore, or dive into a depth below."}
        </p>
        <form className="m-surface__ask" onSubmit={(e) => void hand(e)}>
          <label className="m-surface__ask-label" htmlFor="surface-ask">
            Ask her
          </label>
          <div className="m-surface__ask-row">
            <input
              id="surface-ask"
              className="m-surface__input"
              placeholder="Find what my mother's insurer still owes her"
              autoComplete="off"
              value={ask}
              onChange={(e) => setAsk(e.target.value)}
            />
            <button type="submit" className="m-surface__send" disabled={!clean}>
              Hand it to her
            </button>
          </div>
          <p className="m-surface__note" role="status" data-tone={note === ASK_AWAY ? "away" : undefined}>
            {note}
          </p>
        </form>
      </div>
      <ul className="m-surface__lights" aria-label="Depths">
        {PLACES.map((p) => {
          const light = lights[p.key];
          return (
            <li key={p.key}>
              <a
                className="m-surface__light"
                href={p.key === "settings" ? "#settings" : `#${p.key}`}
                aria-label={`${p.label}, ${light.stat}`}
                data-attention={light.attention ? "true" : "false"}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(p.route);
                }}
              >
                <Glyph place={p.key} />
                <span className="m-surface__light-name">{p.label}</span>
                <span className="m-surface__light-stat">{light.stat}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
