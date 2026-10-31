// A project's sites on its overview (ADR 0014): the band that names a site the person is signed out
// of, with "Sign in again", and the list of sites with what the last look found. Sites are set up only
// by a chore's onboarding; nothing here adds one. Plain words: signed in, sign in again, her browser,
// site. A site not looked at yet reads "checking", never fine.

import { useEffect, useRef, useState } from "react";
import * as api from "../../lib/api";
import type { Site } from "../../lib/contract";
import { reasonOf, useMain } from "../store";

const NO_SITES: Site[] = [];

export const hostOf = (origin: string): string => origin.replace(/^https?:\/\//, "");

export type SiteTone = "success" | "warning" | "info";

/** What the last look found, in plain words. */
export function siteState(site: Site): { tone: SiteTone; words: string } {
  if (site.access === "signed_in") return { tone: "success", words: "signed in" };
  if (site.access === "signed_out") return { tone: "warning", words: "not signed in" };
  return site.reason ? { tone: "info", words: "could not check" } : { tone: "info", words: "checking" };
}

/** The project's sites, read when the overview opens; later looks arrive as `site` events. */
export function useSites(spaceId: string): { sites: Site[]; problem: string } {
  const sites = useMain((s) => s.sites[spaceId]) ?? NO_SITES;
  const loadSites = useMain((s) => s.loadSites);
  const [problem, setProblem] = useState("");
  useEffect(() => {
    loadSites(spaceId).then(
      () => setProblem(""),
      (e: unknown) => setProblem(reasonOf(e, "Could not read the project's sites")),
    );
  }, [spaceId, loadSites]);
  return { sites, problem };
}

type Phase = { at: "idle" } | { at: "signing"; tab: number } | { at: "checking" };

/**
 * "Sign in again": her browser opens the site in front and the person has the wheel; when the page
 * moves on (the `wheel` event for that tab) or the person says they are done, she looks again.
 */
export function useSignInAgain(spaceId: string, origin: string) {
  const putSite = useMain((s) => s.putSite);
  const wheel = useMain((s) => s.wheel);
  const [phase, setPhase] = useState<Phase>({ at: "idle" });
  const [problem, setProblem] = useState("");
  const seen = useRef(wheel?.n ?? 0);

  const check = async () => {
    setPhase({ at: "checking" });
    setProblem("");
    try {
      putSite(spaceId, await api.siteCheck(spaceId, origin));
    } catch (e) {
      setProblem(reasonOf(e, "Could not look at the site"));
    }
    setPhase({ at: "idle" });
  };

  const start = async () => {
    setProblem("");
    try {
      const started = await api.siteSignIn(spaceId, origin);
      seen.current = useMain.getState().wheel?.n ?? 0;
      setPhase({ at: "signing", tab: started.tab });
    } catch (e) {
      setProblem(reasonOf(e, "Her browser could not open the site"));
    }
  };

  useEffect(() => {
    if (!wheel || wheel.n === seen.current) return;
    seen.current = wheel.n;
    if (phase.at === "signing" && wheel.tab === phase.tab) void check();
    // check is recreated each render; the wheel event alone decides when to look
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wheel, phase]);

  return { phase, problem, start, check };
}

function Blocker({ spaceId, site }: { spaceId: string; site: Site }) {
  const { phase, problem, start, check } = useSignInAgain(spaceId, site.origin);
  const blocks = site.blocks.length ? site.blocks.join(", ") : "her work on this site";
  return (
    <li className="m-blocker__row" data-role="blocker" data-origin={site.origin}>
      <p>
        <strong>Athena is not signed in to {site.label}</strong> <span className="m-mono">{hostOf(site.origin)}</span>
      </p>
      <p className="m-muted">
        This blocks: {blocks}.{site.reason ? ` ${site.reason}` : ""}
      </p>
      {phase.at === "signing" ? (
        <div className="m-row">
          <p className="m-muted">Sign in on the page in her browser. Athena never sees your password.</p>
          <button type="button" className="btn" data-role="signed-in" onClick={() => void check()}>
            I have signed in
          </button>
        </div>
      ) : (
        <div className="m-row">
          <button
            type="button"
            className="btn btn-primary"
            data-role="sign-in-again"
            disabled={phase.at === "checking"}
            onClick={() => void start()}
          >
            {phase.at === "checking" ? "Looking..." : "Sign in again"}
          </button>
        </div>
      )}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </li>
  );
}

/** The band on top of the overview: every site the person is signed out of, and the way back in. */
export function SiteBlockers({ spaceId, sites }: { spaceId: string; sites: Site[] }) {
  const out = sites.filter((s) => s.access === "signed_out");
  if (!out.length) return null;
  return (
    <section className="plane m-section m-blocker" data-role="blockers" aria-label="Blocked">
      <h2 className="m-h2">Blocked</h2>
      <ul className="m-blocker__list">
        {out.map((s) => (
          <Blocker key={s.origin} spaceId={spaceId} site={s} />
        ))}
      </ul>
    </section>
  );
}

function SiteRow({ spaceId, site }: { spaceId: string; site: Site }) {
  const { phase, problem, check } = useSignInAgain(spaceId, site.origin);
  const state = siteState(site);
  return (
    <li className="m-site" data-role="site" data-access={site.access}>
      <div>
        <p>
          {site.label} <span className="m-mono">{hostOf(site.origin)}</span>
        </p>
        {site.reason && <p className="m-muted">{site.reason}</p>}
        {problem && (
          <p className="m-error" role="alert">
            {problem}
          </p>
        )}
      </div>
      <span className="badge" data-tone={state.tone}>
        {state.words}
      </span>
      <button type="button" className="btn btn-quiet" disabled={phase.at === "checking"} onClick={() => void check()}>
        {phase.at === "checking" ? "Looking..." : "Check again"}
      </button>
    </li>
  );
}

/** The sites Athena opens on her own here, each with what the last look found. */
export function SitesSection({ spaceId, sites, problem }: { spaceId: string; sites: Site[]; problem: string }) {
  return (
    <section className="plane m-section" data-role="sites">
      <h2 className="m-h2">Sites</h2>
      <p className="m-muted">
        The sites Athena opens on her own in this project, in her browser. A chore&apos;s onboarding signs you in to the sites it needs; nothing else adds one.
      </p>
      {sites.length > 0 ? (
        <ul className="m-sites">
          {sites.map((s) => (
            <SiteRow key={s.origin} spaceId={spaceId} site={s} />
          ))}
        </ul>
      ) : (
        <p className="m-muted">No sites yet.</p>
      )}
      {problem && (
        <p className="m-error" role="alert">
          {problem}
        </p>
      )}
    </section>
  );
}
