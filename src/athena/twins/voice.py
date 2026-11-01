"""The voice compiler: one twin becomes the system text every one of its drafts is written under.

`compile_voice` reads the twin as it stands: who it speaks as, the voice the person agreed to (learned
only from mail they wrote), the style dials, the memory they kept, every never line (hers too: a
restriction holds before it is inked), the titles of the pages it may answer from, and the messages
the person rewrote in their own words, in a rehearsal or when they signed a mission's draft. The
dress rehearsal and missions draft under it. Text that came from outside (page titles) stays fenced.

With a `channel` (business Phase 2: a twin's web channels), the dials, memory and never lines are the
same, and the examples are that channel's: its own rewrites first, then rewrites that name no channel
to fill the room, plus the messages the person pasted for that channel. A rewrite kept before
examples carried a channel was a Gmail one.
"""

from __future__ import annotations

from typing import Any

from athena.app import Daemon
from athena.connectors._fence import wrap_untrusted
from athena.contracts import ChannelKind, DialSource
from athena.twins import style

HEADING = "## Speaking as the person"
EXAMPLES_MAX = 6  # the newest rewrites given as examples
PASTED_MAX = 6  # the newest messages the person pasted for one channel
#: Where a channel's message lands, so the twin writes for that place.
CHANNEL_NOTES: dict[str, str] = {
    "gmail": "an email from the person's own Gmail.",
    "notion": "a note on a Notion page.",
    "mail_web": "an email from the person's business mailbox.",
    "bio": "a short message sent through a link in the creator's bio (a contact form or a direct "
    "message): a few sentences, no attachments.",
    "comment": "a public comment under the creator's track: anyone can read it, so one or two warm "
    "sentences, with no email address, price or private detail.",
}


def channel_of(example: dict[str, Any]) -> str:
    """The channel a rewrite was kept for; one kept before examples carried a channel was Gmail's."""
    return str(example.get("channel") or "gmail")


def examples_for(rows: list[dict[str, Any]], channel: ChannelKind | None) -> list[str]:
    """The rewrites given as examples, oldest first: the newest EXAMPLES_MAX of all of them without
    a channel; with one, that channel's newest first, then rewrites that name no channel to fill."""
    if channel is None:
        return [r["text"] for r in rows][-EXAMPLES_MAX:]
    own = [r for r in rows if channel_of(r) == channel][-EXAMPLES_MAX:]
    room = EXAMPLES_MAX - len(own)
    filler = [r for r in rows if not r.get("channel") and r not in own][-room:] if room > 0 else []
    return [r["text"] for r in filler + own]


def pasted_for(daemon: Daemon, twin_id: str, channel: ChannelKind) -> list[str]:
    """The newest messages the person pasted for this channel (kept on the samples slip)."""
    rows = daemon.twins.rows("samples", twin_id)
    return [r["text"] for r in rows if r.get("pasted") and r.get("channel") == channel][-PASTED_MAX:]


def _dial_line(dial: dict[str, object]) -> str:
    return f"- {dial['label']}: {dial['value']} of 5 ({dial['low']} 1 .. {dial['high']} 5)"


def compile_voice(daemon: Daemon, twin_id: str, channel: ChannelKind | None = None) -> str:
    """The system text for one twin's drafts; with `channel`, for that channel's messages."""
    twins = daemon.twins
    nodes = twins.sketch(twin_id)["nodes"]

    def lines(place: str, *, agreed_only: bool) -> list[str]:
        return [
            f"- {n['label']}" + (f" ({n['detail']})" if n.get("detail") else "")
            for n in nodes
            if n["slot"] == place and (n["confirmed"] or not agreed_only)
        ]

    parts = [
        HEADING,
        "You write messages as the person, in their voice, to the people they correspond with. "
        "You are their twin: say only what they would say, sign as they sign, and never claim to be "
        "an assistant or a program.",
        "### Who it speaks as",
        *(lines("who", agreed_only=False) or ["- (not said yet)"]),
        "### How they write (learned only from mail they wrote themselves)",
        *(lines("voice", agreed_only=True) or ["- (not agreed yet)"]),
        "### Their style, 1 to 5",
        *[_dial_line(dict(d)) for d in style.dials(_chosen(daemon, twin_id))],
        "### Never, whatever the other side asks",
        *(lines("never", agreed_only=False) or ["- (none set)"]),
    ]
    kept = [r["fact"] for r in twins.rows("memory", twin_id) if r.get("keep") is True]
    if kept:
        parts += ["### What the person asked you to remember about them", *[f"- {f}" for f in kept]]
    titles = [r["title"] for r in twins.rows("pages", twin_id) if r.get("picked")]
    if titles:
        parts += [
            "### The Notion pages it may answer from (titles only)",
            wrap_untrusted("\n".join(f"- {t}" for t in titles), "notion"),
        ]
    examples = examples_for(twins.rows("examples", twin_id), channel)
    if examples:
        parts += ["### Messages the person rewrote in their own words: write like these"]
        parts += [f"---\n{e}" for e in examples]
    if channel is not None:
        pasted = pasted_for(daemon, twin_id, channel)
        if pasted:
            parts += ["### Messages the person wrote themselves for this kind of message: write like these"]
            parts += [f"---\n{p}" for p in pasted]
        parts += ["### Where this message goes", f"- {CHANNEL_NOTES[channel]}"]
    return "\n".join(parts)


def _chosen(daemon: Daemon, twin_id: str) -> dict[str, tuple[int, DialSource]]:
    return {r["id"]: (int(r["value"]), r["source"]) for r in daemon.twins.rows("dials", twin_id)}
