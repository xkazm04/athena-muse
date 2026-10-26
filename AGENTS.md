# AGENTS.md - agent guidance for athena-meta

## What this is

Athena on Muse: the Blue Hour onboarding for the Meta hackathon. The plan of record is
`docs/concepts/blue-hour-onboarding/README.md` (flow, four work packages, wire contract, risks).
Prior art is athena-portable; read it, never paste from it without the disclosure in ADR 0001.

## Commands

```bash
node scripts/preflight.mjs   # toolchain
node scripts/check.mjs       # docs gate (links, no machine paths)
```

Product gates (typecheck, lint, test) are added by the first work package that creates code, in
the same commit, and declared in `.ai/manifest.yaml` `capabilities`. Run the gate before claiming
anything works; report output faithfully.

## Rules

- **One commit per feature.** Code, tests and the doc line together. Message `type(scope): sentence`.
- **One decision, one ADR.** `docs/adr/NNNN-slug.md` from `0000-template.md`, same commit.
- **Contracts first.** The Director commits the wire contract and compilable stubs before parallel packages start.
- **Every number carries its measurement.** Muse costs are estimates and tagged est.; Meta API facts are tagged measured / press / unverified in `docs/hackathon/meta-api-facts.md`.
- **No secrets.** Keys come from the environment; never log, commit or film one.
- **No machine paths** in committed files. Repo-relative only.
- **Simulated means labelled.** Fixtures and recorded runs say so on screen.
