# 0014 - A chore's onboarding signs in to its real sites, and only onboarding grants trust

Status: accepted
Date: 2026-10-31

## Context

Her browser (ADR 0013) trusted a site when it was one of the project's `apps`, a free-text list the
person (or a signed `add_app` card) could grow at any time. The owner answered the business channel's
open questions on 2026-10-31 (docs/concepts/business-channel, "Owner's answers (2026-10-31)"):

- access is part of chore onboarding: the stage (ADR 0007) tests the flow, then leads the person to
  sign in to each real web app the chore needs, in Athena's own browser, so next time she reaches it
  on her own;
- trust comes only from onboarding: the sites a chore needs become the project's trusted sites during
  its onboarding, and nowhere else;
- a lapsed sign-in is a blocker on the project overview, naming the site and the way back in.

## Decision

1. **Sites are separate from apps.** A project has typed **sites**: `{origin, label, probe_url,
   access: signed_in | signed_out | unknown, blocks, checked_at?, reason?}` (`contracts.Site`, table
   `sites`). The browser's trust check reads sites only (`Sites.trusted`). `apps` stays the project's
   descriptive list: `add_app`, the overview's Apps form and `POST /spaces` still edit it, and it grants
   nothing. Erasing a project erases its sites (ADR 0003).
2. **The only writer of a site is the onboarding access step** (`drafts/access.begin`, at the keep).
   A look ("Sign in again" on the overview, a hand, the overview opening) changes only `access`,
   `checked_at` and `reason`. There is no route that adds a site.
3. **The sketch names real sites.** An `app` node may carry `site: {origin, url, label, confirmed}`.
   Athena proposes it with the `sketch` tool's `site` argument, always in pencil, even on the person's
   own node (the node keeps its ink); confirming the node inks its site; rubbing out an agreed node's
   pencilled site removes only the site. Only confirmed sites on confirmed app nodes go to access. Her
   practice apps (the test run's invented world) never do.
4. **A new step `access`**, between `verdict` (keep) and `saved`. `keep` makes each confirmed site the
   project's site (access `unknown`) and opens the step; a chore with no real site goes straight to
   `saved`. `POST /drafts/{id}/access {origin, act}`: `sign_in` opens the site's address in her
   browser, in front, and hands the person the wheel; `check` looks now (done when the look says
   signed in, else the site stays open with the reason); `skip` keeps the site as signed out, a
   blocker from day one. With no site open the draft is `saved`. A `wheel` event for the site's tab is
   the desktop's cue to send `check`. The step never asks for, sees or stores a password: signing in
   happens only on the site's own page.
5. **The look** is one daemon function (`browser/sites.check`) used by onboarding, the overview and
   her hands. It opens `probe_url` in a hidden tab, waits a moment for a script's redirect, reads the
   address the tab ended on and asks the page for a visible password field (`page_find role=password`),
   then closes the tab. Decision table (`sites.decide`):

   | What her browser saw | access | reason (shown) |
   | --- | --- | --- |
   | her browser not open | no verdict | stored site unchanged |
   | page not reached (failed, timeout) | `unknown` | "Athena could not reach <site>: ..." |
   | ended on another origin | `signed_out` | "<site> sent her to <host> to sign in." |
   | path has a sign-in segment (`login`, `signin`, `auth`, `sso`, `oauth`, ...) | `signed_out` | "<site> showed its sign-in page." |
   | a visible password field | `signed_out` | "<site> asked for a password." |
   | otherwise | `signed_in` | "<site> opened without asking her to sign in." |

   A look stands `SITE_FRESH_S` (300 s): `GET /spaces/{id}/sites` looks again, on worker threads, only
   at stale sites, and `page_open` on a trusted site looks first (cached) and refuses a signed-out site
   with the way back in. At most one look per site runs at a time. A change is published as the `site`
   app event, so the overview follows it live.
6. **The overview's blocker.** The project view shows a band for every `signed_out` site: the site,
   the chores it blocks, and "Sign in again" (`POST /spaces/{id}/sites/sign_in`, then a look when the
   `wheel` event for that tab arrives, or when the person says they have signed in). `unknown` reads
   "checking" (or "could not check" with the reason), never fine. Screen words: signed in, sign in
   again, her browser, site; never token, cookie, session, OAuth or origin.

## Consequences

- Projects that relied on `apps` for trust lose it until a chore's onboarding signs them in; the
  browser seam now sets its fixture site up through onboarding (`access_seam.onboard`).
- The shell's `open` hand takes `hidden: true` (a window nobody sees) for looks; a look costs one
  short-lived hidden tab.
- A site whose sign-in lands on a different origin of the same company (a `www.` to `studio.` hop)
  reads as signed out by design; its probe address should be on the origin it trusts.
- Her browser must be running for a look; without it the overview shows what the last look found.
- Measured on the local simulated reproduction (`scripts/access_seam.py`, WebView2, the built shell):
  the walk's checks and timings are in the builder's report; no real account was used.

## Amendment (2026-10-31, owner)

- **The stage keeps checking.** While a site's tab is open and it is not signed in, the stage looks
  again every 4 s (one look at a time, at most 45 looks), so a sign-in that takes two pages is caught
  when it finishes. After that the person's "I have signed in" stays.
- **Onboarding catches a move to another site.** A look that ends on another site's page that is not
  a sign-in (another address of the same company, `www.` to `studio.`) reads signed out with "sent her
  on to X, a different site", and the step offers "Use X instead" (`use_moved`): X replaces the site in
  the Project, carrying the chores it blocks. Each site's check page stays on the site it trusts.
- **The step checks every site once more before it ends.** When no site is open, each signed-in site
  is looked at again; one that is no longer signed in (a sign-in on one site signed her out of another)
  opens again with "After the last sign-in, ...". Then the draft is saved.
- No notice for projects whose old `apps` granted trust (owner). A site not yet checked does not block
  her hands; only signed out does (owner).
