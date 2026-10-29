# 0008 - Twins speak through connected accounts

Status: accepted
Date: 2026-10-29

## Context

A twin is a clone that speaks for the person: it reads a conversation, drafts the next message in their voice and, when allowed, sends it ([Twin module](../concepts/twin-module/README.md)). It needs the person's Gmail to read threads and send, and their Notion to read what it may know, file outcomes and rehearse on a practice page.

The scout (2026-10-29) found that this repository has no connectors, no twin and no delegated mail. The [business channel](../concepts/business-channel/README.md) plan held the opposite doctrine: apps are reached the way the owner reaches them, through her browser and an app's own MCP, never through per-service connectors. That plan also had Twins reach the mailbox through the browser.

The earlier sibling, athena-portable, already has what a twin needs, built and used:
- connectors as data: `gmail.json`, which signs in with Google through a loopback flow with PKCE on the person's own Google client and can read and send, and `notion.json`, which takes a pasted integration key and can search, read, append and create;
- one vault that seals every credential with DPAPI or the keyring, probes a credential before keeping it, keeps writes off by default and refuses any write outside an allow-list;
- a Connect screen with idle, waiting for the browser, failed, needs sign-in again and connected states.

The owner chose to port these. Rejected: reaching mail through her browser, a connector now with the browser later, and building the Twin in athena-portable.

## Decision

1. **Twin channels are connected accounts.** athena-portable's vault, seal, Google sign-in, Gmail and Notion connectors are ported into `src/athena/connectors/`. Its MCP client is not ported, and its manifest types are stubbed. Gmail gains reading a whole thread and sending into it (`thread_id`, `In-Reply-To`).
2. **Credentials stay sealed on the machine.** The vault lives under the daemon's data dir and seals each credential with DPAPI on Windows or the keyring elsewhere. A credential is probed before it is kept, and one that fails its probe is not saved. A credential never crosses the wire: `Connection` carries the kind, the status, the account name, whether it may write, when it was last checked and a problem line. Nothing logs a credential.
3. **Google sign-in uses the person's own Google client.** Setup walks the person through making one, in plain words, and asks only to read and send mail: never to delete mail, and never for contacts or the calendar. Notion takes a pasted key and sees only the pages the person shares with it.
4. **Writes are off until a twin needs them.** A connection is created read-only. Twin Gmail sends may go to any recipient: for twins only, this replaces the vault's rule that an empty allow-list refuses every write. The send rule and the risk list ([ADR 0009](0009-one-send-rule-for-every-twin-draft.md)) are the guard. Every other write keeps the vault's allow-list.
5. **The doctrine is amended for Twins only.** The business channel's "no per-service connectors" still holds everywhere else: there Athena reaches apps the way the owner does.

The wire contract names the connector routes (`/connectors`, `/connectors/{kind}/connect`, `/flow`, `/disconnect`, `/probe`) and the `Connection`, `ConnectionList` and `ConnectFlow` shapes. The screen says "sign in with Google" and "your Notion key", never the names of the protocols.

## Consequences

- From v1, real email can leave the machine in the person's name. The send rule is load-bearing, and tests use fakes. No test starts a real Gmail or Notion call, and the one real send (WP6) runs only with the owner present.
- The person must make their own Google client once. That is friction, and the setup step has to carry it in plain words.
- The routes are keyed by kind, so v1 holds one account per kind. The design example's second Gmail account (Family admin) needs an account key on the wire later.
- A connector for another tool (a calendar, Slack) follows the same vault, and a preset chore lists it as "coming" until then.
