---
product: "Athena on Muse"
stack: "Python daemon (uv, Starlette, SQLite) + Tauri 2 / React / TS desktop"
vault: ["./.spark"]
vault_subdir: Spark
base_branch: main
locale_count: 1
---

## Gates
always: `node scripts/check.mjs`; `uv run ruff check src tests`; `uv run ruff format --check src tests`; `uv run mypy`; `uv run pytest -q`; `pnpm -C apps/desktop typecheck`; `pnpm -C apps/desktop lint`; `pnpm -C apps/desktop test`
when src-tauri changed: `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`
builder: the `always` set for the side it touched (Python or desktop); when a gate's output is piped (`| tail`), run it under `set -o pipefail` - a piped failure once reached a commit

## Rituals
none

## Repo law
Read AGENTS.md first. Built core: ADRs 0002-0007; the plan of record (built): docs/concepts/chore-onboarding-v2/README.md; the stage's two views share one store and parts under apps/desktop/src/main/stage/, and each view's CSS is scoped under its own `[data-stage-view]` root. The wire contract types every response envelope, not just items (parity test). The Director commits the wire contract and compilable stubs before any parallel package. No secrets, no machine paths. Meta API facts are tagged measured / press / unverified.

A stream route's contract names its protocol, not just its event types: event order, where the stream ends, and what a follow-up call (a mark, a retry) does to it. A parallel UI built against types alone guessed it wrong (twin-module WP5: rehearsal assumed to pause per draft).

Status lines in a shared design doc belong to the Director: builders put theirs in the final report, and the Director writes the line at commit. Three parallel packages writing "done" lines into one README conflicted at every rebase (twin-module).

## Wave defaults
default

## Question taste
- Concepts the owner calls consistent with earlier work: ask for the design record before wave 1 and offer it as the recommended option.
- Taste forks the owner will not settle in the abstract: build behind a switch and let them choose (blue-hour-onboarding rail build-up, "prototype all three").

- A visual the design proposes as a source of truth: offer "a sketch for understanding, the real artefact written once after agreement" as an option; the owner chose it via Other on chore-onboarding-v2.

- Reaching another app (YouTube, mail, Gravitone): the owner wants it reached through the app's own surface (the internal browser, the peer's MCP), not a connector or wrapper, even at higher engineering cost; lead with that option (business-channel, three overrides in one direction).
- A capability the owner names that lives only in a sibling repo ("the app's connectors" = athena-portable's Gmail/Notion): ask where it lives in wave 1, and include a repo-native mechanism (chores, ADR 0005) as an option for any new tool use; the owner chose "preset chores, catalogue grows" via Other on twin-module.
- The owner leans toward full scope and real behaviour when a tested rule holds the risk: Auto in v1 over "Auto locked", any recipient over a recipients list, "Everything, in order" over a foundation-only fire (twin-module). Recommend the bolder option when its safety is a tested rule, and name that rule in the option.

## Skill improvement log
- 2026-10-26 (athena-core): the brief named list answers as `{spaces: ...}` in prose but the contract typed only the items; a parallel package guessed bare arrays and both sides' tests passed. Put every response envelope in contracts.py + contract.ts with a parity test, not in the brief's prose.
- 2026-10-26: the Bash tool mis-parses long heredocs containing apostrophes; write files with Write and keep shell scripts short.
- 2026-10-27 (chore-onboarding-v2): plan-only spark; scouting the parked plan of record first turned the supersede question into one click.
- 2026-10-28 (business-channel): athena-portable (sibling, built browser + gate + MCP client) was missed by targeting and surfaced only via the owner's doctrine; scout `../athena-*` sibling repos for prior art in Phase 2 of any spark touching hands, engines or apps.
- 2026-10-29 (onboarding-v2 build): a generated fixture in exact wire shape, produced through the daemon's own rules and used as the store's oracle, caught three contract gaps before any view was built (an extra event field, the open question not stored, the quote not kept). Generate fixtures through the real code, never by hand.
- 2026-10-29: parallel UI builders need distinct dev-server ports written into each brief, and `pnpm -C <dir> dev -- --port N` passes a literal `--` to Vite: use `pnpm -C <dir> exec vite --port N --strictPort`.
- 2026-10-29: `uv run <daemon>` starts the daemon as a child; terminating the wrapper leaves it serving its port, and a later run silently talked to the stale one. End the process tree (`taskkill /T`) and assert the engine you asked for answered.
- 2026-10-29: the live seam on the built app found the one defect no unit test could (an authored world whose last phase could not act: 1 of 5). Measure the fix live before and after; it scored 5 of 5.
- 2026-10-29 (twin-module): one Director-written verifier (Playwright on the installed Chrome, every state x 2 sizes: page scroll, 12 px floor, banned words, console errors) handed to three parallel UI builders made their "0 failures" comparable and caught a banned word in the Director's own fixture; run the banned-word check over generated fixtures at build time too.
- 2026-10-30 (twin-module build): the 2026-10-26 lesson (the contract types the shape, prose carries the rest) recurred one level up: WP5 built the rehearsal UI against event types and guessed the stream's protocol wrong; promoted to Repo law. README "done" lines from parallel builders conflicted at three rebases; promoted to Repo law. Re-running a builder's changed rule with the fix reverted (fail) and restored (pass) caught that no existing test covered the first-message rule.
