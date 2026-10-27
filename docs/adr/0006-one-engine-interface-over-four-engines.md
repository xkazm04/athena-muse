# 0006 - One engine interface over four engines

Status: accepted
Date: 2026-10-27

## Context

ADR 0005 lets a run pick its engine: `muse` (Meta's API, the submission's engine), `muse_code` (Muse
Code on the person's plan, the pre-submission check), `claude_code` (development) or `scripted`.
Until now the choice was made in three places (building the engine, reporting its status, and the
probe route, which even named `muse` by hand), and only the two in-process engines existed. The two
CLI engines have no function-calling API that Athena can bind, and each must stay on the person's plan.

## Decision

1. **One choice function.** `engine.choose(keys)` reads `ATHENA_ENGINE` (`muse`, `muse_code`,
   `claude_code`, `scripted`); unset, it picks `muse` when a key exists, else `scripted`. Building
   the engine, `GET /engine`, the probe and `/run` all ask it. A bad name, `muse` with no key, or a
   CLI engine whose program is not on PATH is an `EngineError` in plain words naming the fix.
   `status()` reports the engine chosen; `simulated` is true only for `scripted`.
2. **Models.** `ATHENA_MODEL` overrides the model of every real engine; `META_MODEL` still works for
   `muse`. Defaults: `muse-spark-1.3` for both Muse engines, `sonnet` for Claude Code. The scripted
   engine's model is always `scripted` (a label on a simulated row, not a model). Contributor model ids
   are refused for both Muse engines.
3. **Costs.** `muse` prices from `prices.py` (an estimate). `claude_code` passes on the CLI's own
   `total_cost_usd` when present, marked estimated (list prices; the plan is the real bill).
   `muse_code` and `scripted` report no cost.
4. **Op lines are the tool grammar of a CLI engine** (`engine/oplines.py`). The tools are written into
   the system message; a call is one line `OP: {"tool": "<name>", "args": {...}}`; everything else is
   what the person reads. A line is read on its own; a trailing comma and bare keys are forgiven. A
   line that still cannot be read is dropped and handed back to the model as a tool result. When the
   reply also made a good call, that note rides into the next call; when it made none (the turn would
   end with nothing done), the engine asks again once, at once. The conversation is rendered as one
   prompt, so every call is a single stateless CLI run in a fresh temp directory. Call ids are
   `call_<n>`, counting across the turn.
5. **The children stay on the plan.** Neither child inherits `ANTHROPIC_API_KEY` or `META_API_KEY`
   (the first would move Claude Code to the API, the second Muse Code to pay-as-you-go).
6. **Claude Code** (measured on 2.1.311, 2026-10-27): `claude -p --output-format stream-json --verbose
   --model <m> --system-prompt-file <file> --tools "" --strict-mcp-config --setting-sources ""
   --no-session-persistence`, transcript on stdin. `--tools ""` is the flag that turns every built-in
   tool off on this version (the init line lists no tools). `--setting-sources ""` skips the person's
   hooks; `--bare` was rejected because it never reads the plan sign-in. Tokens come from the final
   `result` line; cached input (`cache_creation_input_tokens`, `cache_read_input_tokens`) counts as input.
7. **Muse Code** (measured on 1.4.13, 2026-10-27): `muse exec --json --prompt-file <file> --model <m>
   --contributor-mode off --preset empty --no-session-log --disable-shell --disable-write
   --disable-web-tools --disable-reminders --no-foreign-personal-context --reasoning-effort low`; the
   system message, tools and transcript all go in the prompt file. The program is found with
   `shutil.which`, so the Windows `.cmd` shim works.

## Measured

One live two-tool turn each, through `run_turn` on a throwaway daemon, the person asking Athena to
remember a fact and look up another (2026-10-27, n=1 each):

| Engine | Model | Wall time | Model calls | Tool calls back | Input tokens (both calls) |
| --- | --- | --- | --- | --- | --- |
| claude_code | sonnet | 7.8 s | 2 (3.1 s, 4.7 s) | `remember`, `recall` in one reply | 2,219 |
| muse_code | muse-spark-1.3 | 11.8 s | 2 (5.2 s, 6.7 s) | `remember`, `recall` in one reply | 31,079 |

Muse Code's input is mostly its own instructions (about 15k tokens a call): plan allowance, not money.

## Consequences

- A chore runs on any of the four engines by one environment flag; every number names the engine.
- A CLI engine answers in one piece (the OP lines must be read before the person sees the reply), so
  its text does not stream word by word.
- The CLI engines cost seconds per call and a fixed instruction overhead; they are a check and a
  development tool, not the submission's engine.
