# Athena on Muse

A guided first act for non-developers: connect Meta's Muse, show Athena one of your web apps, answer a few suggested questions while your work rail draws itself, then run one live test that stops at a red signal only you can clear.

Status: **pre-hackathon scaffold.** No product code yet. Built for the Meta Global AI Developer Hackathon, Startup track.

| You are | Go to |
|---|---|
| Evaluating | [the design](docs/concepts/blue-hour-onboarding/README.md) and its [reference demo](docs/concepts/blue-hour-onboarding/reference/index.html) (opens from disk, all data fictional) |
| Starting the build | [T0 runbook](docs/hackathon/T0.md) |
| Contributing | [AGENTS.md](AGENTS.md) |
| Looking for a decision | [docs/adr](docs/adr/0001-repo-posture.md) |
| Submitting | [submission checklist](docs/hackathon/submission-checklist.md) |

## Prior art

Athena on Muse extends [athena-portable](https://github.com/xkazm04/athena-portable), an agent whose environment is the web apps the user already has open. Which parts are carried over, and how that is disclosed, is decided in [ADR 0001](docs/adr/0001-repo-posture.md).

## Setup

```bash
node scripts/preflight.mjs   # toolchain versions; key present/absent only
node scripts/check.mjs       # docs gate
```

Licence: Apache-2.0.
