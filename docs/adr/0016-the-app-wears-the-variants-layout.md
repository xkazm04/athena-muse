# 0016 - The app wears the variant's layout, not only its tokens

Status: accepted
Date: 2026-10-31

## Context

ADR 0011 took the winning theme variant's tokens, radii, type and water, and kept this app's own
layouts: a top nav bar, a card grid on Chores, an orbit field on Projects. It named the variant's
home surface, depth rail, dock and breadcrumb "no counterpart". The owner opened the app and did not
see one module that looked like the variant. The variant's look is its layout as much as its colours:
a surface with her seal and an ask, depths reached by tiles, a bar that says where you are, a rail
that says how deep, a dock with her pill and the places, and tables with eyebrow heads instead of
cards.

## Decision

Every surface of the main window wears the variant's layout. The variant's modules are another
app's; each of this app's surfaces takes the one closest to it:

| Variant screen | Here | Route |
|---|---|---|
| bar: "Rise to", the mark, the trail | `shell/Depth.tsx` `Crumbs` (rises one level; the project pill and the engine lamp trail it) | every route |
| depth rail with a bead at the current depth | `Rail`: surface 0, a place 1, one thing in it 2, a page under that 3 | every route |
| dock: her pill bottom left, places bottom right, the current one outlined | `Dock`: her seal, name and state (pink when something waits), Projects, Chores, Twins, Athena, Settings | every route below the surface |
| surface (home): the seal large, an eyebrow state, a light marquee, "Ask her" with "Hand it to her", a tile per depth with a line-art glyph and a status line | `shell/Surface.tsx`: her seal (the owner's drawing, at size), the ask hands the words to her window (`handToAthena`, a Tauri event her window takes as the next turn, or keeps in its composer while she writes), tiles for the five places with lines from the stores | `#home`, the default landing |
| chores: heavy title with the totals inline, "New chore" at the right, area tabs with counts, job chips with dots, a segmented order, a table | `chores/Chores.tsx`: the same areas and jobs (`playbooks/taxonomy.json`, held equal by a test), "Describe a need" as the primary action, orders from what the bench measured (proven first, most found, best recall), columns Chore, Job, Status, Bench, Found; the parts are `shell/idiom.css` | `#chores` |
| a playbook's topic page: the way back, the brief at the left, figures as cards at the right | `ChoreScene.tsx`: "All chores", the chore at the left (its whole brief behind a fold), the bench as three figure cards and its facts at the right, the proofs in the table idiom below | `#chores/<id>` |
| a depth in the same idiom (the variant has no projects) | `projects/Field.tsx`: the title row with the totals and "New project" as the primary action, the orbit field stays as the depth's figure, and beside it the one in focus over a table of the core and every project (apps, episodes, facts); a project's level, the core and memory open with the variant's "back" link | `#projects`, `#projects/<id>`, `#projects/core`, `.../memory` |
| mind: an eyebrow, a light marquee, a line, then figures and cards | `athena/AthenaView.tsx`: her state as the marquee (pink when something waits), four figures (waiting, decided, in core, cost), then the cards at the left and the core line and the costs table at the right, each column scrolling on its own so the page itself fits | `#athena` |
| the slip: what waits on you signs in the person's pink, answers are pills | `ui/CardView.tsx` (both windows): "Sign" is a pink pill, "Decline" an outlined pill, a waiting card's words are larger | every waiting card |
| mind and accounts: instruments (a glyph, a name, a status chip with a dot), cards for what is set up elsewhere; a level with its glyph at the left | `settings/Settings.tsx`: "How Athena is set up" over Engine, Look, Accounts and Data as instruments with their standing and line, cards for the welcome, Twins and her window; a setting's level puts its glyph and standing at the left and its choices at the right | `#settings`, `#settings/<item>` |
| a depth's head and table | `twins/Overview.tsx` and `overview.css`: the heavy title with its line beside it and "New twin" at the right, the six stat tiles as figure cards in one row (`data-role="stat-tile"` kept), the ledger as the variant's table (no box, eyebrow heads, light rules); the wallet, the queue and the open spread keep Passport's structure. The invented example's label sits in the bar beside the engine lamp. A twin's setup keeps its own row (what is set up, simulated, her window, back) without the brand the bar already shows | `#twins`, `#twin/...` |

The body face is the system face (Segoe UI), as the variant set it; Outfit stays for the display lines
of her window. A depth's title is heavy (`.title-depth`, 40 px); the surface's marquee grows with the
window (`.marquee--surface`).

Behaviour, routes, data roles and copy do not change except where a layout needs a word the old one
did not (the trail, the dock's state). The type floor (12 px), tokens-only sizes and a reduced-motion
block per stylesheet hold; the new sheets are under the same test as `main.css`.

## Consequences

- The window never scrolls: the body between the bar and the dock scrolls inside when a page is
  longer than its depth.
- The stage and the twins pages keep their own frames inside the body; their fidelity checks see the
  shell around them and the system face.
- Supersedes ADR 0011's "no counterpart" row; its tokens stand.
