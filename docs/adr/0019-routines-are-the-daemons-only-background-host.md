# 0019 - Routines are the daemon's only background host, and a twin speaks on the web through her browser

Status: accepted
Date: 2026-11-01

## Context

The business channel ([concept](../concepts/business-channel/README.md), plan of record Phase 2) needs work that happens while nobody watches:
- watching creators for new tracks;
- reading the mailbox for replies;
- reading the channel's figures;
- drafting offers.

Before this ADR the only background loop was the Twins poller (ADR 0009). It had no spend ceiling and no tool list, it ran beside live turns, and it reached mail only through the Gmail API. The 10-28 doctrine says apps are reached the way the owner reaches them: through her browser, not per-service connectors. The registry's `companion-runtime/autonomous-cycle-hosting` sets the standard:
- one admission owner;
- named refusals;
- single flight;
- a default ceiling;
- counts with denominators.

## Decision

- **One host.**
  - A routine is a project's recurring job: a kind, a cadence, a spend ceiling ($0.25 per run by default) and a state.
  - The host (`routines/host.py`) is the one admission decision. It records as a named skipped run:
    - `paused`;
    - `running` (an in-process claim, released on every exit);
    - `live_turn` (a chat turn open in its space; `busy.live` counts chat turns only);
    - `no_engine`.
  - A routine is due a cadence after its last *completed* run. Catch-up runs once and never back-fills.
  - A repeated skip is written once.
- **The Twins poller is folded in.** Each live twin has a `twin:<id>` routine.
- **Code reads, one model call extracts.** A routine reads a page in a hidden tab of her browser, with its links listed with their addresses (`page_links`). It makes tool-less model calls on surface `routine`, with the page fenced as data.
  - The ceiling is checked before every call. A run that reaches it ends `partial` and says so.
  - Rejected: an agent run with allowed tools (on Claude Code, spend is known only at the end), and pure parsing (it breaks on every page change).
- **What a routine may change alone.**
  - Its finds are kept at once, by `routine`: creator, track, thread, stat.
  - An agreement, file, render or release files a card.
  - Every message is a card.
- **Kinds.**
  - `watch`: new uploads become tracks.
  - `inbox`: replies matched to creators by their emails become threads, and the twin drafts one answer.
  - `stats`: the analytics page's figures become stats, measured at the read time.
  - `outreach`: a kept track's creator with no conversation gets one drafted offer, by mail, else bio link, else comment.
- **The twin's web channels.**
  - A twin may speak on `mail_web`, `bio` and `comment` with no connector. The voice comes from messages the person pastes, per channel.
  - A web message always waits (`web_channel`).
  - On sign, one recipe finds each control again by its label:
    - a mail reply, a new mail, or a comment is sent in her browser;
    - a bio link opens in front of the person, who sends it.
  - A missing control stops, names the step, and leaves the card waiting.
  - Only an edited, signed message becomes an example, for its channel.
- **A tool round runs only what it was offered.** This closes a gap found while scouting.

## Consequences

- **The desktop must be running for a routine that reads a page.** Without it the run skips `no_browser`, and nothing runs while the app is closed (the plan's non-goal).
- **Routine timing changes.** A Twins mission now waits for a live chat turn in its space.
- **Measured.** The seam on the built shell (`scripts/routines_seam.py`, Claude Code, 2026-11-01) passed 9 of 9 for $0.09 est. Without `page_links` it passed 3 of 9: page text carries no addresses.
- **Known gaps:**
  - The mailbox site is recognised by "mail" or "proton" in its address or name, or by the compose page set on the channel.
  - The wheel's line is cut at 200 characters.
  - Proton's real page is the end-to-end run's first unknown.
