# AGENTS.md - agent guidance for athena-meta

## What this is

Athena on Muse: the Blue Hour onboarding for the Meta hackathon. The plan of record is
`docs/concepts/blue-hour-onboarding/README.md` (flow, four work packages, wire contract, risks).
Prior art is athena-portable; read it, never paste from it without the disclosure in ADR 0001.

## Commands

```bash
node scripts/preflight.mjs   # toolchain
node scripts/check.mjs       # docs gate (links, no machine paths)
uv sync && pnpm install      # dependencies
uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy && uv run pytest -q
pnpm -C apps/desktop typecheck && pnpm -C apps/desktop lint && pnpm -C apps/desktop test
```

The gates are declared in `.ai/manifest.yaml` `capabilities`. Run them before claiming anything
works; report output faithfully. Architecture: [ADR 0002](docs/adr/0002-two-windows-over-one-loopback-daemon.md).
The wire contract is `src/athena/contracts.py` + `apps/desktop/src/lib/contract.ts`; change both
in one commit (the parity test fails otherwise).

## Rules

- **One commit per feature.** Code, tests and the doc line together. Message `type(scope): sentence`.
- **One decision, one ADR.** `docs/adr/NNNN-slug.md` from `0000-template.md`, same commit.
- **Contracts first.** The Director commits the wire contract and compilable stubs before parallel packages start.
- **Every number carries its measurement.** Muse costs are estimates and tagged est.; Meta API facts are tagged measured / press / unverified in `docs/hackathon/meta-api-facts.md`.
- **No secrets.** Keys come from the environment; never log, commit or film one.
- **No machine paths** in committed files. Repo-relative only.
- **Simulated means labelled.** Fixtures and recorded runs say so on screen.
