# 0013 - Her browser: tabs, hands, and trust per origin

Status: accepted; point 3 amended by [0014](0014-a-chores-onboarding-signs-in-to-its-real-sites-and-only-onboarding-grants-trust.md) (trust reads the project's sites, set up only by a chore's onboarding, not its apps)
Date: 2026-10-31

## Context

The business channel (docs/concepts/business-channel, gaps G2, G4, G10, G14, G19, G20) reaches
YouTube Studio and the mailbox the way the owner does: through a browser holding the owner's sessions,
not through per-service connectors. athena-portable built such a browser (Tauri child webviews with an
injected `hands.js`, ten generic hands on DOM text and opaque refs, a per-origin trust gate, approvals
bound to the tab and the page load). It had no upload, no download, and stopped at iframes and shadow
DOM, all of which Studio needs. Uploading a file in WebView2 was the plan's riskiest piece: WebView2
has no CDP `setFileInputFiles`.

## Decision

1. **The shell owns the tabs; the daemon owns every decision.** A tab is its own window labelled
   `page-<n>` with `hands.js` injected into its top document and a per-tab nonce baked in. All tabs
   share the app's one signed-in WebView2 profile (per-project profiles stay a non-goal). The shell
   long-polls the daemon (`GET /browser/next`) and answers each call once (`POST /browser/done`); the
   protocol is in `contracts.py`. A page can call exactly one command, `browser_reply`, through the
   `page` capability; the app ACL manifest (`build.rs`) keeps every other command away from pages.
   Director default, overridable: a window per tab rather than portable's child webviews in one
   window, so no `unstable` Tauri feature and no layout code; the tab comes forward by focusing it.
2. **The hands** are portable's, ported to this repo and extended: every walk goes through open shadow
   roots and same-origin frames (cross-origin frames stay unreachable); a hidden file input is still
   findable. Shell hands: `open`, `tabs`, `tab`, `close`, `wheel`, `upload`, `download`. Page hands:
   `page_read`, `page_find`, `page_wait`, `page_scroll`, `page_click`, `page_fill`, `page_select`,
   `page_submit`, `page_upload`. Every hand answers `{ok, output, reason?}` and never throws.
3. **Trust is per origin and per project: the project's apps are the browser's trust list.** The
   catalog class is the floor and trust only tightens it: an AUTO hand (`page_open`, `page_read`,
   `page_find`, `page_wait`, `page_scroll`) runs at once on a trusted site and files a card on any
   other; a GATED hand (`page_click`, `page_fill`, `page_select`, `page_submit`, `page_upload`,
   `page_download`, `wheel_handoff`) always files a card. What a page says comes back fenced as page
   data, named by its site.
4. **An approval is spent on the page it was given for.** A card carries the tab, the page load and the
   address it was asked on; the shell answers `moved` and does nothing when the tab has left that
   page, and the card stays waiting. An acting hand also checks the label it was shown (`expect`).
5. **Privacy is private, always.** An acting hand refuses any control whose label reads "Public" or
   "Unlisted", signed or not.
6. **Upload: the shell stages the file into the page in base64 parts through `eval`** (512 KiB raw per
   part), and the page builds a `File` in the input's own realm and assigns it through a
   `DataTransfer`, then fires `input` and `change`. The shell reads only a file inside a project's
   files folder; the model names a file only by its id.
7. **Download: only an armed tab may download.** `page_download` arms its tab, clicks the ref, and
   the shell's download handler lands the file in `<data>/spaces/<id>/files/incoming/`; the daemon
   hashes it into `files/<sha256>` and keeps one `files` row per (project, digest): name, MIME, size,
   SHA-256 and the site it came from. Every download the shell did not arm is cancelled. Erasing a
   project removes its rows and its folder. Phase 1's records adopt this table as the `file` kind.
8. **Hand the wheel.** `wheel_handoff` (gated) brings the tab forward with her one line in its title;
   the shell watches the page and posts `back` when it moves on (or `closed`, or `timeout` after 30
   minutes), which the daemon publishes as the `wheel` app event. Athena never solves a check.

## Measured

On the local simulated reproduction (WebView2, the built shell, `scripts/browser_seam.py`); the
figures are in the concept doc's Phase 0 section. The real YouTube Studio dialog is not measured:
it needs the owner's account.

## Consequences

- Her browser runs only while the desktop app runs; a hand with no shell polling answers
  `no_browser` at once.
- A page can forge nothing but its own answers: it holds no command but `browser_reply`, and the
  nonce ties an answer to its tab.
- A large upload costs one `eval` per 512 KiB; very large files are slow but bounded (2 GB cap).
- A single-page app that changes its address without a load is caught by the address half of the
  binding, not by the load count.
