# Settings - the engine, the look, the accounts and the data, in one place

Built 2026-10-31. Decision: [ADR 0012](../adr/0012-settings-live-in-the-daemon-and-the-engine-choice-needs-no-restart.md). Ported from Athena Portable's setup module (its Mind depth); what was not ported, and why, is in the ADR.

## What it does

`#settings` in the main window (**Settings** in the dock, or its tile on the surface) is an overview in the variant's mind idiom (ADR 0016): five instruments, each
a glyph with a standing word and one line.

| Tile | Standing | Level (`#settings/<item>`) |
|---|---|---|
| Engine | set / not yet / needs you / checking | Choose which engine runs her turns (Muse, Muse Code, Claude Code, Simulated). An engine that cannot run here is shown with the reason and cannot be picked. The Muse key section (add, replace, remove, check) sits below. |
| Look | the theme | Theme (auto, dark, light), text size (standard, large), motion (system, calm). Both windows change at once. |
| Accounts | set / not yet / needs you | Gmail and Notion as connected for Twins, read-only, with a link to Twins where they are connected. |
| Data | local | The folder this computer's Athena keeps everything in, and what is in it. |
| Devices | N paired / none yet / N waiting for you / checking | Pair a phone or another computer: [Devices](devices.md) (ADR 0017). |

Below the instruments, **Show the welcome again** draws the first run again. Nothing already set changes.

A write that the daemon refuses is shown beside the control that made it, in the daemon's words,
and the stored choice is shown again.

## How it works

- **Daemon.** The rows are in the daemon's `settings` table (`src/athena/settings.py`): `theme`,
  `type_scale`, `motion`, `engine`, beside the existing `active_space_id`. Routes in
  `src/athena/routes_settings.py`: `GET /settings` (a `SettingsView`), `POST /settings/look` (any of
  the three, all or none), `POST /settings/engine` (one engine). Each write answers the whole view.
- **Engine.** `engine.decide(keys, stored)` (`src/athena/engine/__init__.py`, ADR 0012 as amended):
  the stored choice first, whenever it can run; then `ATHENA_ENGINE`; then Muse with a key, else the
  first installed CLI wrapper (Claude Code, then Muse Code), else Simulated. A choice that cannot run
  falls through, and Settings names both engines. The Meta key section lives on the Engine level only. `engine.options(keys)` says, without calling anything, whether each engine
  can run: a key on file, a program on PATH. The engine is built per request, so a choice reaches
  the next turn with no restart; choosing announces the `engine` event so both windows' lamps follow. The bar's lamp names the engine (Claude Code, Muse Code, Muse) with the model in its title, or says Simulated.
- **Look.** `ui/look.ts` paints `data-theme` (through the theme's `applyTheme`), `data-type-scale`
  and `data-motion` on the document; `ui/look.css` holds the large-text sizes and the calm rule. The
  backdrop's current treats calm as reduced motion. Each window reads `/settings` at boot; a write
  publishes `{type: "settings", look}` and both windows repaint.
- **Page.** `apps/desktop/src/main/settings/`: `model.ts` turns the view into words (pure, derived
  at render, never stored), `Settings.tsx` draws the overview, the levels and the refusals.

## Verified

- `tests/test_settings.py` (18 cases, through the real app): defaults, a look written and heard as
  an event, partial writes, every bad look refused whole, unknown stored rows read as defaults,
  engine readiness per engine, a choice moving `/engine` and the next build, refusals (no key, not
  installed, unknown), a choice beating `ATHENA_ENGINE`, a choice that cannot run falling through to the default, a key saved making Muse choosable, the data folder and a
  look surviving a reopen. `tests/test_contract_parity.py::test_settings_match` covers every new
  enum and shape. `tests/test_engine_choice.py` checks every route hands over the stored choice.
- Desktop: `main/settings/model.test.ts` (the facts), `main/settings/settings.test.tsx` (the
  overview, a refused read, the welcome, an unknown item, the look painted before the write and
  settling back on refusal, a look from the other window, engine options, choice, refusal and the
  choice open while `ATHENA_ENGINE` is set, accounts, data), `ui/look.test.ts` (the attributes, large sizes checked
  against `tokens.css`, the calm rule), `main/settings/settings.css.test.ts`, her window wearing the
  look (`athena/App.test.tsx`), and the three API paths (`lib/api.test.ts`).
- Not yet seen in a running Tauri window; the gates above are the evidence.

## Limits

- A window paints the default look until `/settings` answers on boot (a loopback round trip).
- "Ready" for a CLI engine means the program is on PATH, not that it is signed in; the first turn
  or the probe says that.
- Large text overrides three `--fs-*` tokens outside `tokens.css`; a re-themed size fails
  `ui/look.test.ts` until `look.css` follows.
- Not ported: voice and the microphone, tabs, the brain folder, skins and avatars (no counterpart
  here; reasons in the ADR).
