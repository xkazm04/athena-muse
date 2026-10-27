"""How two reads of one printed value are compared, and how a read value is stored.

Two reads agree when they are equal after normalising: whitespace and case; `$`, commas and spaces
off money; any date written out (`August 3, 2026`, `08/03/2026`, `3 August 2026`) to ISO. The same
normaliser compares a read value with the answer key.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        [
            *("january", "february", "march", "april", "may", "june"),
            *("july", "august", "september", "october", "november", "december"),
        ]
    )
}
MONEY = re.compile(r"^\s*(-?)\s*\$?\s*(-?)\s*([0-9][0-9,\s]*(?:\.[0-9]+)?)\s*$")
SLASHED = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
MONTH_FIRST = re.compile(r"^([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})$")
DAY_FIRST = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\.?,?\s+(\d{4})$")


def as_text(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def collapse(text: str) -> str:
    return " ".join(text.split())


def money(value: Any) -> float | None:
    """A dollar amount as a number, or None when the value is not one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    m = MONEY.match(str(value))
    if not m:
        return None
    sign = "-" if (m.group(1) or m.group(2)) else ""
    try:
        return float(sign + re.sub(r"[,\s]", "", m.group(3)))
    except ValueError:
        return None


def iso_date(value: Any) -> str | None:
    """Any whole-value date to `YYYY-MM-DD`, or None when the value is not a date."""
    text = collapse(str(value)).lower()
    parts: tuple[int, int, int] | None = None
    if m := ISO.match(text):
        parts = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    elif m := SLASHED.match(text):
        parts = (int(m.group(3)), int(m.group(1)), int(m.group(2)))  # US month/day/year
    elif (m := MONTH_FIRST.match(text)) and m.group(1) in MONTHS:
        parts = (int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
    elif (m := DAY_FIRST.match(text)) and m.group(2) in MONTHS:
        parts = (int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    if parts is None:
        return None
    try:
        return date(*parts).isoformat()
    except ValueError:
        return None


def is_money_field(name: str) -> bool:
    return name.endswith("_usd")


def comparable(name: str, value: Any) -> str:
    """The form two values of one field are compared in."""
    if is_money_field(name):
        amount = money(value)
        if amount is not None:
            return f"${amount:.2f}"
    day = iso_date(value)
    if day is not None:
        return day
    return "".join(as_text(value).split()).casefold()


def stored(name: str, value: str) -> Any:
    """The value a sensed table keeps: money as a number, a date as ISO, other text as printed."""
    if is_money_field(name):
        amount = money(value)
        if amount is not None:
            return amount
    day = iso_date(value)
    if day is not None:
        return day
    return collapse(value)


def agree(name: str, a: str, b: str) -> bool:
    return comparable(name, a) == comparable(name, b)
