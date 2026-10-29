"""Twins: a clone that speaks for the person on Gmail and Notion, set up with Athena (ADR 0008-0010).

A twin is set up in one shaping conversation on the drafts machinery with its own rubric (ADR 0010),
then rehearsed on a Notion practice page with Athena playing the other side, then goes live. Live, it
works missions (a goal on one conversation) and every draft passes the one send rule (ADR 0009).

Modules: `decide` (the send rule) and `routes`. The store, the rubric, setup, the rehearsal (WP3)
and missions with the poller (WP4) land with their packages; until then each route answers 501.
"""

from __future__ import annotations

TWIN_PREFIX = "tw_"
