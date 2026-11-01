"""The watch routine (business Phase 2): every followed creator's uploads, kept as new tracks.

For each creator the project follows it reads `<channel>/videos` in her browser, asks one tool-less
model call for the uploads on that page, and keeps each upload it has not kept before as a `track`
(found now, by that creator). A track already kept is left alone, so finding it again appends nothing
and never touches the person's verdict. A creator page that cannot be read is skipped and the run ends
partial, saying how many were not read.
"""

from __future__ import annotations

from urllib.parse import urljoin

from athena.errors import ApiError
from athena.records.kinds import normalise_url
from athena.routines import pages
from athena.routines.context import Partial, RunContext, Skip

TASK = (
    "You read a creator's videos page and list the uploads it shows. Answer "
    '{"tracks": [{"url": "...", "title": "...", "published": "YYYY-MM-DD"}]}: one entry per upload, '
    "its address as the page links it, its title as shown, and published only when the page shows a "
    "date (omit it otherwise; never guess). No upload on the page: an empty list."
)


def videos_url(channel_url: str) -> str:
    return channel_url.rstrip("/") + "/videos"


def run(ctx: RunContext) -> None:
    creators = [
        c["body"] for c in ctx.daemon.records.latest(ctx.space_id, "creator") if c["body"].get("followed")
    ]
    if not creators:
        raise Skip("nothing_to_do", "no creator is followed yet")
    ctx.of = len(creators)
    unread = 0
    new = 0
    for creator in creators:
        channel = str(creator["channel_url"])
        try:
            page = pages.checked(ctx.read(videos_url(channel)))
        except Partial:
            unread += 1
            continue
        answer = ctx.extract(
            pages.system(TASK),
            f"The creator: {creator.get('name', channel)}.\n\n{pages.fenced(page)}",
            "tracks",
        )
        for upload in pages.items(answer, "tracks"):
            ctx.found += 1
            if _keep(ctx, page.url, channel, upload):
                new += 1
    read = len(creators) - unread
    ctx.note = (
        f"Read {read} of {pages.plural(len(creators), 'followed creator')}: "
        f"{pages.plural(ctx.found, 'upload')} seen, {pages.plural(new, 'new track')}."
    )
    if unread:
        ctx.note += f" {pages.plural(unread, 'creator page')} could not be read."
        raise Partial(ctx.note)


def _keep(ctx: RunContext, page_url: str, creator_key: str, upload: dict[str, object]) -> bool:
    """Keeps one upload as a new track; False when it is known already or not a usable upload."""
    raw = pages.text(upload.get("url"))
    title = pages.text(upload.get("title"))
    if not raw or not title:
        return False
    try:
        url = normalise_url(urljoin(page_url, raw))
    except ApiError:
        return False
    if ctx.daemon.records.latest(ctx.space_id, "track", url):
        return False  # known: the key dedups by address, and a known track appends nothing
    body = {"url": url, "title": title, "creator_key": creator_key, "found_at": pages.iso(pages.now())}
    return ctx.put("track", body) is not None
