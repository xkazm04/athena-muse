# Athena on Muse

A private desktop companion that thinks with Meta's Muse. You connect your own Muse key, keep your
work in **Projects** whose memory stays walled off from each other, and talk with Athena in her small
always-on-top window. Anything she wants to change stops at a card you sign, and it runs once. Every
Muse call is metered, with its estimated cost, in a ledger you can read.

Status: **core built in the event window** (from 2026-10-26). Built for the Meta Global AI Developer
Hackathon, Startup track. Not yet in this build: Chores, Settings, the Blue Hour onboarding interview
and test run (see [the plan](docs/concepts/blue-hour-onboarding/README.md)).

| You are | Go to |
|---|---|
| Evaluating | this README, then [the architecture](docs/adr/0002-two-windows-over-one-loopback-daemon.md) |
| Contributing | [AGENTS.md](AGENTS.md) |
| Looking for a decision | [docs/adr](docs/adr/0001-repo-posture.md) |
| Checking Meta API facts | [meta-api-facts](docs/hackathon/meta-api-facts.md) (every row tagged measured / press / unverified) |
| Submitting | [submission checklist](docs/hackathon/submission-checklist.md) |

## What is in it

- **Two windows over one local daemon.** The main window holds the first run, your Projects and the
  Athena view; her window holds the conversation. Both talk to a Python daemon on `127.0.0.1` behind
  a per-launch token ([ADR 0002](docs/adr/0002-two-windows-over-one-loopback-daemon.md)).
- **First run: connect Muse.** Paste your Meta key, Athena asks Muse to answer and shows how fast it
  did. No key? She runs simulated, and says so on screen.
- **Projects are walled spaces.** A brief, apps and a memory of their own; core is visible
  everywhere; erase takes a project's memory with it ([ADR 0003](docs/adr/0003-projects-are-walled-spaces.md)).
- **The gate.** Changing a brief, adding an app or forgetting a memory files a card; nothing happens
  until you sign; it runs once ([ADR 0004](docs/adr/0004-muse-engine-key-custody-and-the-gate.md)).
- **The ledger.** One row per Muse call: tokens, estimated cost from Meta's published prices,
  latency.
- **Loop Tide.** A cobalt theme derived from the Meta and Muse identities (never their marks): a
  living current behind the main window and her animated seal in a cobalt-lens window.

## Setup

```bash
node scripts/preflight.mjs        # toolchain: node, pnpm, uv, python, cargo
uv sync && pnpm install           # dependencies
pnpm -C apps/desktop app          # build and open Athena (spawns the daemon)
```

Optional: `META_API_KEY` in the environment (or paste it in the first run). `pnpm -C apps/desktop dev`
then `/preview.html` shows the theme without the daemon.

## Prior art

The concepts (walled projects, single-use cards, the Loop Tide theme) come from
[athena-portable](https://github.com/xkazm04/athena-portable). The code here is new, written from
scratch in the event window ([ADR 0001](docs/adr/0001-repo-posture.md)).

Licence: Apache-2.0.
