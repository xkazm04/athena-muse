---
vault: ["./.contest"]
vault_subdir: Contest
arena: .contest/arena
participants: ""
judges: ""
variants: 3
timeout_min: 90
---

## Engines

PATH lookup (`claude` is on PATH on the development machine).

## Data

The host stages by hand under `.contest/stage/<id>/`: a `src/` generator for computed fixtures, `data/` with the material, `SCHEMA.md` and `states.md`, and `data/loop-tide/` copied verbatim from `apps/desktop/src/theme/` (tokens, base, coat, the Outfit woff2 files with a local `fonts.css`). Screenshots of the real app come from a throwaway daemon (`ATHENA_ENGINE=scripted`, a scratch `--data` dir, invented projects) plus `pnpm -C apps/desktop dev`, opened in a browser with `?daemon=&token=` and the `athena.firstRun.skipped` local-storage flag set.

## Taste

- Built on the current Loop Tide design, at app quality, not a mock.
- Plain words for non-developers. No machinery words on screen.
- One frame at a time, no page scroll; the 12 px floor and reduced motion are hard limits.

## Skill improvement log
