# 0004 - The Muse engine, who holds the key, and the gate

Status: accepted
Date: 2026-10-26

## Context

Athena on Muse thinks with Meta's Muse models. The person brings their own Meta key and pays their
own bill. Meta's API shape is known only from its published pages (see
[meta-api-facts](../hackathon/meta-api-facts.md)); nobody on the team has measured it yet. Some
things Athena might do change the person's work and must not happen without them.

## Decision

- **One engine seam, two engines.** `muse` speaks OpenAI-compatible Chat Completions at
  `https://api.meta.ai/v1` (override `META_BASE_URL`), model `muse-spark-1.3` (override
  `META_MODEL`), streamed, with a JSON fallback and plain-words errors. `scripted` is a
  deterministic engine used when no key exists; it is labelled **simulated** everywhere it shows.
  The engine is built per request, so a key saved a second ago takes effect.
- **Contributor model ids are refused.** They train on the person's content.
- **The daemon holds the key.** `META_API_KEY` in the environment wins; otherwise
  `POST /engine/key` writes `meta-key.json` (owner-only) into the data dir. The key is never
  returned, logged, or sent back to a window.
- **Every model call is one ledger row**: surface, space, engine, model, tokens, estimated cost from
  Meta's published prices (`cost_estimated`), latency, ok. An unlisted model is unpriced, never $0.
- **A closed action catalog with classes.** AUTO actions run inside the turn (`recall`,
  `remember`). GATED actions (`propose_brief`, `add_app`, `forget`) file a **card** and end the
  turn waiting. A card resolves exactly once (one conditional UPDATE); the daemon executes the
  approved action itself, once, for the winner only. Athena is told never to claim she did what a
  card still waits on.

## Consequences

The product works without a key (simulated, labelled), and with one the person sees what each Muse
call cost before anyone else does. The API facts move from press to measured when the first key
arrives; the client's shape adapts behind the seam. SAM, Llama and voice are not in this decision.
