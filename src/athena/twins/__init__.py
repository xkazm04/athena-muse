"""Twins: a clone that speaks for the person on Gmail and Notion, set up with Athena (ADR 0008-0010).

A twin is set up in one shaping conversation on the drafts machinery with its own rubric (ADR 0010),
then rehearsed on a Notion practice page with Athena playing the other side, then goes live. Live, it
works missions (a goal on one conversation) and every draft passes the one send rule (ADR 0009).

Modules: `store` (the tables), `rubric` (places, coverage, readiness, pieces), `style` (the dials),
`catalogue` and `presets/` (the ready-made chores, as data), `reach` (Gmail and Notion through the
vault), `setup` (the setup turn), `panels` (the working slips), `voice` (the voice compiler),
`decide` (the send rule), `rehearse` (the dress rehearsal, marks, going live), `view` (the wire
shapes and the stat strip), `missions` (the runner and the signature cards), `poller` (the Gmail
threads with an open mission, while the daemon runs), `preview` (how it sounds now) and `routes`.
"""

from __future__ import annotations

TWIN_PREFIX = "tw_"
