// The access step's shared part (ADR 0014): each real site the chore needs, signed in to in her
// browser or skipped. Both views draw this one list; each skins it under its own root. The person
// signs in on the site's own page: nothing here asks for or holds a password.

import type { AccessAct, DraftSite } from "../../../lib/contract";
import type { StageWords } from "../words";

const host = (origin: string) => origin.replace(/^https?:\/\//, "");

export interface AccessListProps {
  sites: readonly DraftSite[];
  busy?: boolean;
  onAct: (origin: string, act: AccessAct) => void;
  words: StageWords;
}

function badge(site: DraftSite, words: StageWords): { tone: "success" | "warning" | "info"; text: string } {
  if (site.state === "signed_in") return { tone: "success", text: words.signedIn };
  if (site.state === "skipped") return { tone: "warning", text: words.skipped };
  return { tone: "info", text: words.toDo };
}

/** One row per site: sign in (her browser opens it, the person has the wheel), I have signed in, skip. */
export function AccessList({ sites, busy = false, onAct, words }: AccessListProps) {
  const done = sites.filter((s) => s.state !== "open").length;
  return (
    <section className="sp-access" data-role="access" aria-label={words.accessTitle}>
      <ul className="sp-access__list" aria-label={words.accessList}>
        {sites.map((site) => {
          const b = badge(site, words);
          const signing = site.state !== "signed_in" && site.tab !== undefined;
          return (
            <li key={site.origin} className="sp-access__site" data-role="access-site" data-state={site.state} data-origin={site.origin}>
              <div className="sp-access__words">
                <p className="sp-access__label">
                  {site.label} <span className="sp-access__host">{host(site.origin)}</span>
                </p>
                {signing && <p className="sp-access__note">{words.signingIn}</p>}
                {site.reason && site.state !== "signed_in" && <p className="sp-access__note">{site.reason}</p>}
                {site.state === "skipped" && <p className="sp-access__note">{words.skippedHint}</p>}
              </div>
              <span className="badge" data-tone={b.tone}>
                {b.text}
              </span>
              <div className="sp-access__actions">
                {signing && (
                  <button type="button" className="btn btn-primary" data-role="access-check" disabled={busy} onClick={() => onAct(site.origin, "check")}>
                    {words.signedInNow}
                  </button>
                )}
                {site.state === "open" && (
                  <button
                    type="button"
                    className={signing ? "btn" : "btn btn-primary"}
                    data-role="access-sign-in"
                    disabled={busy}
                    onClick={() => onAct(site.origin, "sign_in")}
                  >
                    {signing ? words.signInAgain : words.signIn}
                  </button>
                )}
                {site.state === "open" && (
                  <button type="button" className="btn btn-quiet" data-role="access-skip" disabled={busy} onClick={() => onAct(site.origin, "skip")}>
                    {words.skipSite}
                  </button>
                )}
                {site.state === "skipped" && (
                  <button type="button" className="btn" data-role="access-sign-in" disabled={busy} onClick={() => onAct(site.origin, "sign_in")}>
                    {signing ? words.signInAgain : words.signInAfterAll}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="sp-access__count" data-role="access-count">
        {done} {words.of} {sites.length} {words.accessDone}
      </p>
    </section>
  );
}
