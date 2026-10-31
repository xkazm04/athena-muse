# 0011 - Loop Tide follows the winning theme variant

Status: accepted
Date: 2026-10-31

## Context

Loop Tide is the theme the owner chose in a theme contest run on the earlier Athena desktop (the
winning variant, B/1 "Loop Tide"; the contest arena lives outside this repo). This app took the
variant's palette token for token, its seal and the rim arc of her window's coat, but its own
primitives drifted from the variant's language: rounder controls (10 px buttons and fields, 16 px
cards), bold titles everywhere, grey eyebrows, a flat backdrop with wide diagonal light bands, and a
rule under the top bar.

How the variant maps onto this app:

| Variant | Here |
|---|---|
| palette (dark, light), `--lt-*` arc and current tokens | `theme/tokens.css` (already equal) |
| depth tones `--depth-0..3`, `--vignette`, the water lit from above | `.backdrop` tone and vignette (`theme/base.css`) |
| four masked light shafts swaying on their own clocks | `.backdrop__shafts i` (`Backdrop.tsx` renders four) |
| the particle current on three loops | `theme/current.ts` (already equal) |
| radii: 6 px interactive and input, 10 px card | `--r-interactive`, `--r-card`; `.btn`, `.field`, `.plane`, chore tiles |
| the coat (16 px cobalt lens, rim arc) | `--r-coat`, `theme/coat.css` (already equal) |
| surface marquee: large light words, tight tracking | `.marquee`, `--fs-display` 48 px, `--fw-display` 300; the first act's titles |
| eyebrow: uppercase, 0.14em, interface blue | `.eyebrow`, `.m-eyebrow`, `--tracking-eyebrow` |
| depth titles: heavy | `.m-title` at 700 |
| breadcrumb and dock: no rule, the water shows through; the current place is accent words in an outlined pill | `.m-top` loses its rule; `.m-nav__link[aria-current]` |
| her window's answers are pills | `.her-app .btn` |
| home surface with the bell, depth rail, dock, five depths | no counterpart; the layouts here stay (projects field, chores, stage, twins) |

## Decision

The variant's language is the reference for the look of both windows. Tokens carry it: semantic radii
(`--r-interactive`, `--r-card`, `--r-coat`) over the scale, display and eyebrow type tokens, and the
water's depth tones. Primitives in `theme/` read the semantic tokens; surfaces only use them. Layouts,
data roles, copy and behaviour do not change, and the type floor (12 px), tokens-only sizes and a
reduced-motion block per stylesheet hold.

## Consequences

- One place to move the look again: a later re-skin changes tokens and the two primitives' sheets.
- The stage and the twins pages keep their own scoped sheets; they pick up the new backdrop, radii
  and buttons through the shared primitives, so their fidelity checks against the older prototypes
  see the water and control corners move. Their structural roles are unchanged.
- The variant set body text in the system face (Segoe UI) and only display words in Outfit; this app
  keeps Outfit throughout until the owner says otherwise.
