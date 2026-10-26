# 0002 - Two windows over one loopback daemon

Status: accepted
Date: 2026-10-26

## Context

Athena on Muse is a desktop companion: a main window where the person connects Muse and keeps
Projects, and her small always-on-top window where they talk and sign what she asks to do. Both
windows must agree on the active project, the conversation and the cards waiting.

## Decision

- **Tauri 2 + React/TypeScript** for the two windows (`main`, `athena`), one Vite build with two
  entries. **A Python daemon** (`athena-daemon`, uv) owns every piece of state and every model call.
- The daemon binds `127.0.0.1` on a free port and writes `daemon.json` `{port, token, pid}`
  (owner-only) into the app's data dir; the shell spawns it, reads the file and hands `{url, token}`
  to each window. Every route needs the bearer token except `/health`; `/events` takes it in the
  query because EventSource cannot send headers. CORS allows the app's origins only.
- **One SQLite file** (WAL) is the truth: spaces, memory, conversations, ledger, cards, settings.
- **One SSE stream** `/events` keeps both windows in step; the active project lives in the daemon.
- The wire contract is `src/athena/contracts.py` and `apps/desktop/src/lib/contract.ts`, held equal
  by `tests/test_contract_parity.py`.

## Consequences

The companion runtime is testable with no window: every daemon test builds it over `:memory:`. The
webview-to-loopback seam (port, token, CORS) is new and is smoke-tested on the real Tauri build.
Packaging the daemon as a signed sidecar is not in this session; dev launches it with `uv run`.
