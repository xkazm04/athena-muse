"""The stats routine (business Phase 2): the channel's numbers from Studio's analytics page, kept as stats.

It reads the analytics page the routine names in her browser, asks one tool-less model call for the
readings it shows, and keeps one `stat` per reading, measured at the time of this read. A date the page
claims is never used: a series is the run's own clock, so two reads of the same day stay two points.
"""

from __future__ import annotations

import re

from athena.routines import pages
from athena.routines.context import RunContext, Skip

TASK = (
    "You read a channel's analytics page and report the numbers it shows. Answer "
    '{"readings": [{"metric": "...", "value": 0}]}: one entry per figure shown, such as views, '
    "subscribers and watch_hours (watch time in hours), the metric as a short lower_snake name and the "
    "value as a plain number (1.2K is 1200). Report only figures the page shows; never guess one."
)
METRIC_MAX = 40
_SNAKE = re.compile(r"[^a-z0-9]+")
#: The names a page's own labels come back as, so a series keeps one name across reads.
ALIASES = {"watch_time": "watch_hours", "watch_time_hours": "watch_hours", "subscriber": "subscribers"}


def metric_name(raw: str) -> str:
    name = _SNAKE.sub("_", raw.lower()).strip("_")[:METRIC_MAX].strip("_")
    return ALIASES.get(name, name)


def run(ctx: RunContext) -> None:
    url = pages.text(ctx.routine.get("url"))
    if not url:
        raise Skip("nothing_to_do", "set the analytics page's address")
    page = pages.checked(ctx.read(url))
    measured_at = pages.iso(pages.now())  # the read time, never a date the page claims
    answer = ctx.extract(pages.system(TASK), pages.fenced(page), "readings")
    seen: set[str] = set()
    for reading in pages.items(answer, "readings"):
        metric = metric_name(pages.text(reading.get("metric")))
        value = pages.number(reading.get("value"))
        if not metric or value is None or metric in seen:
            continue
        seen.add(metric)
        ctx.found += 1
        ctx.put("stat", {"metric": metric, "value": value, "measured_at": measured_at})
    ctx.note = f"Read {pages.plural(ctx.found, 'figure')}."
