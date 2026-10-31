# 0012 - Settings live in the daemon, and the engine choice needs no restart

Status: accepted
Date: 2026-10-31

## Context

The README said Settings was not in this build. Athena Portable has one: its setup module
(`modules/setup/`, portable ADRs 0024, 0029, 0054, 0085, 0094, 0028/0092), where four stores meet:
`settings` (the engine, the theme, the text size, Calm motion, the brain path, the style, the avatar,
whether the first act was read), `tabs` (whether a page is open), `daemon` (the running engine and
the restart) and `voice` (whether the daemon can hear). Its rows sit in a Tauri-side SQLite store
behind four generic commands (portable ADR 0016), and its readiness is derived at render, never
stored.

This repo's architecture is different (ADR 0002): two windows over one loopback Python daemon that
already keeps a key/value `settings` table, and an engine chosen by `ATHENA_ENGINE` (ADR 0006) that
is built anew for every request. The port has to keep the module's scope and its rules, in this
architecture.

## Decision

1. **The rows live in the daemon, behind typed routes.** `GET /settings` answers one `SettingsView`
   (the look, the engine her next turn runs on, who decided it, every engine with its readiness, the
   data folder). `POST /settings/look` takes any of `theme`, `type_scale`, `motion` and writes all or
   none; `POST /settings/engine` takes one engine. Each write answers the whole view. An unknown
   stored value reads as its default. There are no generic store commands on the wire.
2. **The look: theme, text size, Calm.** `theme` is `auto | dark | light` (the theme's own
   `applyTheme`). `type_scale` is `standard | large`: large overrides `--fs-xs`, `--fs-sm` and
   `--fs-md` by 2px each in `ui/look.css` (portable ADR 0054's step; the headings keep theirs), and a
   test reads `tokens.css` so a re-themed size is caught. Portable's `compact` is dropped: the
   standard sizes already sit on the 12px floor. `motion` is `system | calm`: calm stills every
   animation and transition, as `base.css`'s reduced-motion block does, and the backdrop's current
   paints its still frame. Portable's `full` (keep motion when the system asks for less) is dropped:
   every sheet here honours `prefers-reduced-motion` on its own, and overriding that is not a choice
   this app offers.
3. **Both windows wear it.** Each window reads `/settings` at boot and paints it; a write publishes a
   `settings` event with the look, and both windows repaint (portable ADR 0026's `store:changed`,
   as an SSE event). The look is painted before it is written, as in portable; a refusal is shown
   beside its control and the stored look is read and painted again.
4. **The engine choice is a row the next turn reads.** `engine.decide(keys, stored)`: `ATHENA_ENGINE`
   still wins (source `env`, and a choice is then refused with that reason); else the stored choice
   (source `setting`); else Muse with a key, else Simulated (source `default`). A stored Muse choice
   with no key runs simulated, as before, and Settings says so. A write is refused when the engine
   cannot run here (no key, program not on PATH), in the daemon's words. Every site that builds an
   engine in the daemon (turns, the probe, drafts, twins, the poller) passes the stored choice.
5. **No restart, so no restart flow.** Portable's 13-state engine machine, its restart notice and its
   "a first-run choice moves the daemon" rule (portable ADR 0085) exist because its daemon is started
   on one engine. Here the engine is built per request, so a choice reaches the next turn at once; the
   readiness facts collapse to: not read yet, simulated, chosen but blocked (with the reason), ready.
   "Ready" means found (a key on file, a program on PATH); the key's acceptance is the probe's to say,
   and the engine level carries the existing Muse key section with its check.
6. **An overview that reads, a level that writes** (portable ADR 0029), in this window's idiom:
   `#settings` shows a tile per item (Engine, Look, Accounts, Data) with a standing word and a line;
   `#settings/<item>` holds its controls. Portable's sheet (`Layer`) is not ported; the hash route is
   how this window opens a level (Projects, Chores).
7. **What is carried over as it was.** The data folder is shown read-only (portable's store path).
   "Show the welcome again" draws the first run again from a flag and changes no row (portable ADR
   0094). Connected accounts (ADR 0008) are read on an Accounts level, with their changes left to the
   Twins page where they are made, as portable's Mind linked out to Apps and Voice.

## Not ported, and why

- **Voice and the microphone** (portable ADRs 0028, 0092): this repo has no voice engine and no
  microphone path. Nothing to set.
- **Tabs, the page, the browser**: there is no browser in this app.
- **The brain path**: memory here is rows in the daemon's database, not a markdown folder, and the
  data folder is fixed by the shell when it spawns the daemon. Moving it would need a respawn; the
  folder is shown instead.
- **Style (skin) and avatar** (portable ADR 0142): Loop Tide is the only theme (ADR 0011), and she has
  one seal. A skin layer would be a decision for the theme, not for Settings.
- **Devices and sleep**: shown in portable's Mind, but they belong to other modules, not setup.

## Consequences

- The contract grows: `ThemeChoice`, `TypeScale`, `MotionChoice`, `EngineSource`, `EngineReadiness`,
  `Look`, `LookBody`, `EngineOption`, `SettingsView`, `EngineChoiceBody`; the `settings` event type
  and `AppEvent.look`; routes `settings`, `settings_look`, `settings_engine`. The parity test covers
  every one.
- `ATHENA_ENGINE` keeps its meaning for development and the bench; the CLIs pass no stored choice.
- The first frame of a window paints the default look until `/settings` answers (a few ms on
  loopback). Caching the look per window would remove the flash; it is not done.
- `--fs-*` overrides for large text live outside `tokens.css`; a re-theme that changes those sizes
  fails `look.test.ts` until `look.css` follows.
