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
builder: the `always` set for the side it touched (Python or desktop)

## Rituals
none

## Repo law
Read AGENTS.md first. Built core: ADRs 0002-0004; the onboarding plan of record (not yet built past key + probe): docs/concepts/blue-hour-onboarding/README.md. The wire contract types every response envelope, not just items (parity test). The Director commits the wire contract and compilable stubs before any parallel package. No secrets, no machine paths. Meta API facts are tagged measured / press / unverified.

## Wave defaults
default

## Question taste
- Concepts the owner calls consistent with earlier work: ask for the design record before wave 1 and offer it as the recommended option.
- Taste forks the owner will not settle in the abstract: build behind a switch and let them choose (blue-hour-onboarding rail build-up, "prototype all three").

- A visual the design proposes as a source of truth: offer "a sketch for understanding, the real artefact written once after agreement" as an option; the owner chose it via Other on chore-onboarding-v2.

## Skill improvement log
- 2026-10-26 (athena-core): the brief named list answers as `{spaces: ...}` in prose but the contract typed only the items; a parallel package guessed bare arrays and both sides' tests passed. Put every response envelope in contracts.py + contract.ts with a parity test, not in the brief's prose.
- 2026-10-26: the Bash tool mis-parses long heredocs containing apostrophes; write files with Write and keep shell scripts short.
- 2026-10-27 (chore-onboarding-v2): plan-only spark; scouting the parked plan of record first turned the supersede question into one click.
