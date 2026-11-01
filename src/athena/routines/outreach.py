"""The outreach routine (business Phase 2): an offer drafted to each creator of a kept track not yet asked.

A creator is eligible when one of their tracks has the verdict keep, and there is no conversation with
them yet: no `thread` record, no `agreement` record and no waiting `twin_send_web` card for them. The
channel is the most direct one the creator record allows: mail when it has an email address, else a
bio message when it has bio links, else a comment on the kept track. Each offer is drafted in the
project's twin's voice as a card the person signs; at most one per creator and five per run.
"""

from __future__ import annotations

from typing import Any

from athena.contracts import ChannelKind, RecordItem
from athena.errors import ApiError
from athena.records.kinds import normalise_ref
from athena.routines import pages
from athena.routines.context import RunContext, Skip

PER_RUN = 5


def channel_for(creator: dict[str, Any]) -> ChannelKind:
    """Mail when they have an email address, else a bio message, else a comment on the track."""
    if creator.get("emails"):
        return "mail_web"
    if creator.get("bio_links"):
        return "bio"
    return "comment"


def run(ctx: RunContext) -> None:
    records = ctx.daemon.records
    space = ctx.space_id
    asked = {normalise_ref(str(r["body"].get("creator_key", ""))) for r in records.latest(space, "thread")}
    asked |= {
        normalise_ref(str(r["body"].get("creator_key", ""))) for r in records.latest(space, "agreement")
    }
    asked |= _waiting(ctx)
    creators = {r["key"]: r["body"] for r in records.latest(space, "creator")}

    picked: dict[str, RecordItem] = {}  # creator key -> their newest kept track
    for track in records.latest(space, "track"):
        if track["body"].get("verdict") != "keep":
            continue
        who = normalise_ref(str(track["body"].get("creator_key", "")))
        if who and who not in asked and who not in picked:
            picked[who] = track
    if not picked:
        raise Skip("nothing_to_do", "every creator of a kept track has been written to")

    ctx.found = len(picked)
    basics = _basics(ctx)
    drafted = 0
    for who, track in list(picked.items())[:PER_RUN]:
        creator = creators.get(who) or {"channel_url": who}
        channel = channel_for(creator)
        card = ctx.draft(channel, who, "offer", context=_context(creator, track, channel, basics))
        if card is None:
            raise Skip("no_twin", "set up the project's twin to draft offers")
        drafted += 1
    ctx.note = f"Drafted {pages.plural(drafted, 'offer')} for the person to sign."
    if len(picked) > drafted:
        ctx.note += f" {pages.plural(len(picked) - drafted, 'more creator')} wait for the next run."


def _waiting(ctx: RunContext) -> set[str]:
    """Creators with an offer or reply waiting for the person's signature in this project."""
    out: set[str] = set()
    for card in ctx.daemon.gate.list("waiting"):
        if card["space_id"] == ctx.space_id and card["action"] == "twin_send_web":
            key = card["args"].get("creator_key")
            if isinstance(key, str) and key:
                out.add(normalise_ref(key))
    return out


def _basics(ctx: RunContext) -> str:
    try:
        space = ctx.daemon.spaces.get(ctx.space_id)
    except ApiError:
        return ""
    brief = str(space.get("brief") or "").strip()
    return f"Our channel: {space['name']}." + (f" {brief}" if brief else "")


def _context(creator: dict[str, Any], track: RecordItem, channel: ChannelKind, basics: str) -> str:
    body = track["body"]
    lines = [
        f'Their song: "{body.get("title", "")}" at {body.get("url", track["key"])}.',
        f"The creator: {creator.get('name', 'unnamed')} ({creator['channel_url']}).",
    ]
    if channel == "mail_web":
        lines.append(f"Write to: {', '.join(creator.get('emails') or [])}.")
    elif channel == "bio":
        lines.append(f"Their bio links: {', '.join(creator.get('bio_links') or [])}.")
    else:
        lines.append(f"Post as a comment under the song at {body.get('url', track['key'])}.")
    if basics:
        lines.append(basics)
    return "\n".join(lines)
