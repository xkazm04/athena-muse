"""The voice compiler: one twin becomes the system text every one of its drafts is written under.

`compile_voice` reads the twin as it stands: who it speaks as, the voice the person agreed to (learned
only from mail they wrote), the style dials, the memory they kept, every never line (hers too: a
restriction holds before it is inked), the titles of the pages it may answer from, and the messages
the person rewrote in their own words during a rehearsal. The dress rehearsal drafts under it now;
missions draft under it in WP4. Text that came from outside (page titles) stays fenced.
"""

from __future__ import annotations

from athena.app import Daemon
from athena.connectors._fence import wrap_untrusted
from athena.contracts import DialSource
from athena.twins import style

HEADING = "## Speaking as the person"
EXAMPLES_MAX = 6  # the newest rewrites given as examples


def _dial_line(dial: dict[str, object]) -> str:
    return f"- {dial['label']}: {dial['value']} of 5 ({dial['low']} 1 .. {dial['high']} 5)"


def compile_voice(daemon: Daemon, twin_id: str) -> str:
    """The system text for one twin's drafts."""
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
    examples = [r["text"] for r in twins.rows("examples", twin_id)][-EXAMPLES_MAX:]
    if examples:
        parts += ["### Messages the person rewrote in their own words: write like these"]
        parts += [f"---\n{e}" for e in examples]
    return "\n".join(parts)


def _chosen(daemon: Daemon, twin_id: str) -> dict[str, tuple[int, DialSource]]:
    return {r["id"]: (int(r["value"]), r["source"]) for r in daemon.twins.rows("dials", twin_id)}
